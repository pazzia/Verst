package app.verst.data.net

import android.util.Log
import app.verst.core.model.EngineJson
import app.verst.core.model.EngineResult
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlanOutcome
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import okhttp3.Call
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response

/** The device's registration on one server (ADR-0007): the bearer token is shown once, the app keeps it here. */
@Serializable
data class ServerAuth(val baseUrl: String, val deviceId: String, val token: String)

/** What «Проверить соединение» found. */
sealed interface ServerCheck {
    data class Ok(val ms: Long, val registered: Boolean) : ServerCheck
    data class Failed(val reason: String) : ServerCheck
}

/** How the server could not be used for a plan (the phone engine took over). */
class ServerUnavailable(message: String) : IOException(message)

/**
 * SRV-01: the verst-api client (ADR-0020). Device registration (`POST /v1/devices`, the token kept by [store]),
 * the health check and the server plan: `POST /v1/trips/plan` with `Accept: text/event-stream`, whose `stage` /
 * `stop` events are the same JSON the phone engine emits (ADR-0006) and whose `done` body is the engine's result.
 * Anything but the engine's verdict about the trip is a [ServerUnavailable] so the caller falls back to the phone.
 */
class ServerClient(
    private val baseUrl: () -> String?,
    private val store: AuthStore,
    private val appVersion: String,
    private val locale: () -> String,
    private val http: () -> OkHttpClient = { planClient },
) {
    interface AuthStore {
        fun load(): ServerAuth?
        fun save(auth: ServerAuth?)
    }

    val configured: Boolean get() = !baseUrl().isNullOrBlank()

    /** `GET /healthz`; registers the device on the way when it is not yet. */
    suspend fun check(): ServerCheck = withContext(Dispatchers.IO) {
        val base = baseUrl()?.trimEnd('/') ?: return@withContext ServerCheck.Failed("no server in this build")
        val t0 = System.nanoTime()
        try {
            http().newCall(Request.Builder().url("$base/healthz").build()).execute().use { r ->
                if (r.code != 200) return@withContext ServerCheck.Failed("HTTP ${r.code}")
            }
            val registered = try {
                token(base)
                true
            } catch (e: IOException) {
                Log.w(TAG, "registration failed: ${e.message}")
                false
            }
            ServerCheck.Ok((System.nanoTime() - t0) / 1_000_000, registered)
        } catch (e: IOException) {
            ServerCheck.Failed(e.message ?: e.javaClass.simpleName)
        }
    }

    /**
     * «Отвязать от сервера» (security review М-2): `DELETE /v1/devices/me` deletes the device, its saved trips and
     * feedback on the server, then the token is forgotten here. False (token kept, to repeat) when the server did not
     * confirm.
     */
    suspend fun forget(): Boolean = withContext(Dispatchers.IO) {
        val auth = store.load() ?: return@withContext true
        val base = baseUrl()?.trimEnd('/')
        if (base == null || auth.baseUrl != base) {
            store.save(null) // a token of another server: nothing to delete here
            return@withContext true
        }
        val req = Request.Builder().url("$base/v1/devices/me").header("Authorization", "Bearer ${auth.token}").delete().build()
        val done = try {
            http().newCall(req).execute().use { it.code == 204 || it.code == 401 } // 401: already gone
        } catch (e: IOException) {
            Log.w(TAG, "forget failed: ${e.message}")
            false
        }
        if (done) store.save(null) // kept on failure, so «Отвязать» can be repeated online
        done
    }

    /**
     * The plan on the server; [onEvent] gets the progress events on the reading thread. Only the engine's own verdict
     * about the trip ([FINAL]) comes back as an [EngineResult.Err]; every other failure — transport, 5xx, 429, 413,
     * a request the server's schema rejects, `UPSTREAM` in the stream — is a [ServerUnavailable], so the phone engine
     * plans instead (acceptance 28.10, QA B-3). Cancelling the caller cancels the HTTP call.
     */
    suspend fun plan(inputJson: String, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanOutcome> {
        val base = baseUrl()?.trimEnd('/') ?: throw ServerUnavailable("no server in this build")
        var token = withContext(Dispatchers.IO) { token(base) }
        repeat(2) { attempt ->
            val req = Request.Builder().url("$base/v1/trips/plan")
                .header("Authorization", "Bearer $token")
                .header("Accept", "text/event-stream")
                .post(inputJson.toRequestBody(JSON))
                .build()
            val answer = execute(http().newCall(req)) { r ->
                when {
                    r.code == 401 && attempt == 0 -> null
                    r.code != 200 -> final(engineError(r.peekBody(MAX_BODY).string()), "HTTP ${r.code}")
                    !(r.header("Content-Type") ?: "").startsWith("text/event-stream") ->
                        // a plain JSON answer: the proxy or the server did not stream
                        decoded(EngineJson.planOutcome(wrapOk(r.peekBody(MAX_BODY).string())))
                    else -> readStream(r.body!!.source(), onEvent)
                }
            }
            if (answer != null) return answer
            store.save(null) // the server forgot us (a restore, a wipe): register again once
            token = withContext(Dispatchers.IO) { token(base) }
        }
        throw ServerUnavailable("unauthorised after a new registration")
    }

    /** Runs [call] on the IO pool; cancelling the caller cancels the call, so a blocked read ends at once. */
    private suspend fun <T> execute(call: Call, read: (Response) -> T): T = coroutineScope {
        val watcher = launch {
            try {
                awaitCancellation()
            } finally {
                call.cancel()
            }
        }
        try {
            withContext(Dispatchers.IO) {
                val response = try {
                    call.execute()
                } catch (e: IOException) {
                    throw ServerUnavailable(e.message ?: e.javaClass.simpleName)
                }
                response.use(read)
            }
        } finally {
            watcher.cancel()
        }
    }

    private fun readStream(source: okio.BufferedSource, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanOutcome> {
        var event: String? = null
        val data = StringBuilder()
        while (true) {
            val line = try {
                source.readUtf8LineStrict(MAX_BODY)
            } catch (e: java.io.EOFException) {
                throw ServerUnavailable("stream ended without done")
            } catch (e: IOException) {
                throw ServerUnavailable("stream: ${e.message}")
            }
            when {
                line.isEmpty() -> {
                    val payload = data.toString()
                    data.setLength(0)
                    when (event) {
                        "stage", "stop" -> EngineJson.event(payload)?.let(onEvent)
                        "done" -> return decoded(EngineJson.planOutcome(wrapOk(payload)))
                        "error" -> return final(engineError("""{"error":$payload}"""), "stream error")
                    }
                    event = null
                }
                line.startsWith(":") -> Unit // heartbeat
                line.startsWith("event:") -> event = line.substring(6).trim()
                line.startsWith("data:") -> data.append(line.substring(5).trimStart())
            }
            if (data.length > MAX_BODY) throw ServerUnavailable("stream: event too large")
        }
    }

    /** The engine's verdict is final only for [FINAL] codes; the phone engine retries the rest. */
    private fun final(r: EngineResult.Err, context: String): EngineResult<PlanOutcome> =
        if (r.error.code in FINAL) r else throw ServerUnavailable(if (r.error.code == "INTERNAL") context else "${r.error.code} ($context)")

    /** A `done` the app cannot decode (a newer server) is the server's problem, not the trip's. */
    private fun decoded(r: EngineResult<PlanOutcome>): EngineResult<PlanOutcome> =
        if (r is EngineResult.Err && r.error.code == "INTERNAL") throw ServerUnavailable("undecodable plan") else r

    /** The stored token for [base], or a fresh registration (`POST /v1/devices`). */
    private fun token(base: String): String {
        store.load()?.takeIf { it.baseUrl == base }?.let { return it.token }
        val body = buildJsonObject {
            put("appVersion", appVersion.filter { it.isLetterOrDigit() || it in ".+_-" }.take(32).ifEmpty { "0" })
            put("locale", locale())
        }.toString()
        val req = Request.Builder().url("$base/v1/devices").post(body.toRequestBody(JSON)).build()
        try {
            http().newCall(req).execute().use { r ->
                if (r.code != 201) throw ServerUnavailable("register: HTTP ${r.code}")
                val o = EngineJson.json.parseToJsonElement(r.body?.string() ?: "").jsonObject
                val auth = ServerAuth(base, o.str("deviceId"), o.str("token"))
                store.save(auth)
                return auth.token
            }
        } catch (e: IOException) {
            throw ServerUnavailable("register: ${e.message}")
        } catch (e: IllegalArgumentException) {
            throw ServerUnavailable("register: bad answer")
        }
    }

    /** `{"error": {code, message, details: {…}}}` (verst-api) → the engine's flat error object. */
    private fun engineError(body: String?): EngineResult.Err {
        val err = try {
            (EngineJson.json.parseToJsonElement(body ?: "").jsonObject["error"] as? JsonObject)?.let { e ->
                val flat = JsonObject(e.filterKeys { it != "details" } + ((e["details"] as? JsonObject) ?: emptyMap()))
                EngineJson.json.decodeFromJsonElement(EngineErrorDto.serializer(), flat)
            }
        } catch (_: Exception) {
            null
        }
        return EngineResult.Err(err ?: EngineErrorDto("INTERNAL", "server: undecodable error"))
    }

    companion object {
        private const val TAG = "VerstServer"

        /** Engine answers about the trip itself: the phone engine would say the same, so they are not retried. */
        val FINAL = setOf("UNREACHABLE", "TOO_SHORT")

        /** Security review М-3: a line of the stream or a JSON body above this is a broken server, not a plan. */
        const val MAX_BODY = 4L * 1024 * 1024
        private val JSON = "application/json; charset=utf-8".toMediaType()

        /** A plan streams up to `plan_timeout_s` (25 s) with a heartbeat every 5 s: a long read timeout, no retry. */
        val planClient: OkHttpClient by lazy {
            Net.okHttp.newBuilder().readTimeout(20, TimeUnit.SECONDS).callTimeout(45, TimeUnit.SECONDS).build()
        }

        /** The engine's envelope around the server's bare result, so `EngineJson` decodes both the same way. */
        internal fun wrapOk(result: String): String = """{"ok":true,"result":$result}"""

        private fun JsonObject.str(key: String): String =
            (this[key] as? JsonPrimitive)?.contentOrNull ?: throw IllegalArgumentException(key)
    }
}
