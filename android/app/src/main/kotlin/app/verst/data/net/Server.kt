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
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

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
 * Transport trouble (no server, 5xx, timeout, bad stream) is a [ServerUnavailable] so the caller can fall back to
 * the phone; an `error` event or a 4xx is the engine's answer and comes back as an [EngineResult.Err].
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

    /** The plan on the server; [onEvent] gets the progress events on the calling dispatcher's thread. */
    suspend fun plan(inputJson: String, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanOutcome> = withContext(Dispatchers.IO) {
        val base = baseUrl()?.trimEnd('/') ?: throw ServerUnavailable("no server in this build")
        var token = token(base)
        repeat(2) { attempt ->
            val req = Request.Builder().url("$base/v1/trips/plan")
                .header("Authorization", "Bearer $token")
                .header("Accept", "text/event-stream")
                .post(inputJson.toRequestBody(JSON))
                .build()
            val response = try {
                http().newCall(req).execute()
            } catch (e: IOException) {
                throw ServerUnavailable(e.message ?: e.javaClass.simpleName)
            }
            response.use { r ->
                when {
                    r.code == 401 && attempt == 0 -> {
                        store.save(null) // the server forgot us (a restore, a wipe): register again once
                        token = token(base)
                    }
                    r.code >= 500 -> throw ServerUnavailable("HTTP ${r.code}")
                    r.code != 200 -> return@withContext engineError(r.body?.string())
                    !(r.header("Content-Type") ?: "").startsWith("text/event-stream") ->
                        // a plain JSON answer: the proxy or the server did not stream
                        return@withContext EngineJson.planOutcome(wrapOk(r.body?.string() ?: ""))
                    else -> return@withContext readStream(r.body!!.source(), onEvent)
                }
            }
        }
        throw ServerUnavailable("unauthorised after a new registration")
    }

    private fun readStream(source: okio.BufferedSource, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanOutcome> {
        var event: String? = null
        val data = StringBuilder()
        while (true) {
            val line = try {
                source.readUtf8Line()
            } catch (e: IOException) {
                throw ServerUnavailable("stream: ${e.message}")
            } ?: throw ServerUnavailable("stream ended without done")
            when {
                line.isEmpty() -> {
                    val payload = data.toString()
                    data.setLength(0)
                    when (event) {
                        "stage", "stop" -> EngineJson.event(payload)?.let(onEvent)
                        "done" -> return EngineJson.planOutcome(wrapOk(payload))
                        "error" -> return engineError("""{"error":$payload}""")
                    }
                    event = null
                }
                line.startsWith(":") -> Unit // heartbeat
                line.startsWith("event:") -> event = line.substring(6).trim()
                line.startsWith("data:") -> data.append(line.substring(5).trimStart())
            }
        }
    }

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

    private fun engineError(body: String?): EngineResult<PlanOutcome> {
        val err = try {
            (EngineJson.json.parseToJsonElement(body ?: "").jsonObject["error"] as? JsonObject)
                ?.let { EngineJson.json.decodeFromJsonElement(EngineErrorDto.serializer(), it) }
        } catch (_: Exception) {
            null
        }
        return EngineResult.Err(err ?: EngineErrorDto("INTERNAL", "server: undecodable error"))
    }

    companion object {
        private const val TAG = "VerstServer"
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
