package app.verst.engine

import android.content.Context
import android.os.Build
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.util.concurrent.Callable
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.Future
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONObject

/** Engine start-up timings in milliseconds (logged under `VerstEngine`, written by `EngineStartupTest`). */
data class EngineTimings(
    val pythonStartMs: Long,
    val importMs: Long,
    val worldsMs: Long,
    val selfcheckMs: Long,
    val totalMs: Long,
    /** Sprint 3: `load_catalogue` (composes `russia_v1`, ADR-0012; M§15.2 budget ≤ 800 ms). */
    val catalogueMs: Long = 0,
)

data class EngineInfo(val engineVersion: String, val python: String, val timings: EngineTimings)

sealed interface EngineStatus {
    data class Starting(val phase: String) : EngineStatus
    data class Ready(val info: EngineInfo) : EngineStatus
    data class Failed(val code: String, val detail: String) : EngineStatus
}

/**
 * Java-visible progress listener handed to `mobile.plan` (M§5.2 `PlanEventListener`): Python calls
 * `listener.onEvent(json)` on the `verst-python` thread.
 */
class PlanEventListener(private val sink: (String) -> Unit) {
    fun onEvent(json: String) {
        try {
            sink(json)
        } catch (e: Throwable) {
            Log.w(EngineHost.TAG, "listener failed", e)
        }
    }
}

/**
 * The on-device planner (M§5.2): CPython via Chaquopy on the single thread `verst-python`, the module
 * `verst_planner.mobile`, both fixture worlds from the assets, the self-check. Every call except `cancel`
 * runs on that thread; `cancel` may be called from any thread while a `plan` is running.
 */
class EngineHost(private val context: Context) {
    private val thread: ExecutorService = Executors.newSingleThreadExecutor { Thread(it, "verst-python") }

    /** Coroutine dispatcher over the `verst-python` thread (M§5.2 `PythonThread`). */
    val dispatcher: CoroutineDispatcher = thread.asCoroutineDispatcher()
    private val _status = MutableStateFlow<EngineStatus>(EngineStatus.Starting("python"))
    val status: StateFlow<EngineStatus> = _status

    @Volatile private var module: PyObject? = null

    /**
     * S3-R4: the real catalogue (1 114 towns, 11 817 POIs) loads right after «ready» on the same engine thread,
     * so the first screen does not wait for it; every engine call queues behind it (FIFO, one thread). The value
     * is the load time in ms once done (null while loading).
     */
    private val _catalogueMs = MutableStateFlow<Long?>(null)
    val catalogueMs: StateFlow<Long?> = _catalogueMs

    fun start() {
        if (Build.FINGERPRINT == "robolectric") {
            _status.value = EngineStatus.Failed("NO_ENGINE", "Robolectric: no CPython in JVM unit tests")
            return
        }
        thread.execute { boot() }
    }

    /** Retry after `Failed` (5.1 engine-failed «Повторить»). */
    fun restart() {
        if (_status.value !is EngineStatus.Failed) return
        _status.value = EngineStatus.Starting("python")
        start()
    }

    private fun boot() {
        try {
            val t0 = SystemClock.elapsedRealtime()
            if (!Python.isStarted()) Python.start(AndroidPlatform(context))
            val t1 = SystemClock.elapsedRealtime()
            _status.value = EngineStatus.Starting("import")
            val mobile = Python.getInstance().getModule("verst_planner.mobile")
            val t2 = SystemClock.elapsedRealtime()
            _status.value = EngineStatus.Starting("worlds")
            for (name in WORLDS) {
                val text = context.assets.open("worlds/$name.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
                expectOk(mobile.callAttr("load_world", text).toString())
            }
            val t3 = SystemClock.elapsedRealtime()
            expectOk(mobile.callAttr("set_clock", "system").toString())
            _status.value = EngineStatus.Starting("selfcheck")
            val check = expectOk(mobile.callAttr("selfcheck").toString())
            val t4 = SystemClock.elapsedRealtime()
            module = mobile
            // «ready» without the catalogue: the app shows its first screen (shimmer until the first answer)
            val timings = EngineTimings(t1 - t0, t2 - t1, t3 - t2, t4 - t3, t4 - t0, catalogueMs = 0)
            Log.i(TAG, "ready $timings")
            _status.value = EngineStatus.Ready(
                EngineInfo(check.getString("engineVersion"), check.getString("python"), timings),
            )
            // then the catalogue (composes `russia_v1`) and the self-check again for its time zones
            val c0 = SystemClock.elapsedRealtime()
            expectOk(mobile.callAttr("load_catalogue").toString())
            expectOk(mobile.callAttr("selfcheck").toString())
            val c1 = SystemClock.elapsedRealtime()
            Log.i(TAG, "catalogue ${c1 - c0} ms (ready + catalogue ${c1 - t0} ms)")
            _catalogueMs.value = c1 - c0
        } catch (e: EngineCallFailed) {
            Log.e(TAG, "engine failed ${e.code}: ${e.detail}")
            _status.value = EngineStatus.Failed(e.code, e.detail)
        } catch (e: Throwable) {
            Log.e(TAG, "engine start failed", e)
            _status.value = EngineStatus.Failed("ENGINE_START", e.toString())
        }
    }

    /** Calls `verst_planner.mobile.<function>(args)` on the engine thread and returns the envelope JSON. */
    fun call(function: String, vararg args: Any?): String {
        val task: Future<String> = thread.submit(Callable { callHere(function, *args) })
        return task.get()
    }

    /**
     * Calls `mobile.<function>` on the current thread, which must be `verst-python` (use `withContext(dispatcher)`).
     * Never throws: a Kotlin/Chaquopy failure becomes an `INTERNAL` envelope, so every caller gets a screen.
     */
    fun callHere(function: String, vararg args: Any?): String {
        check(Looper.myLooper() != Looper.getMainLooper()) { "Python call on the main thread" }
        return try {
            val m = module ?: return errorEnvelope("NO_ENGINE", "engine not started: ${_status.value}")
            val t0 = System.nanoTime()
            m.callAttr(function, *args).toString().also {
                // OR-8 / S4 diagnostics: slow engine calls (they hold the one engine thread) go to the log
                val ms = (System.nanoTime() - t0) / 1_000_000
                if (ms >= 1_000) Log.i(TAG, "slow call $function: $ms ms")
            }
        } catch (e: Throwable) {
            Log.e(TAG, "call $function failed", e)
            errorEnvelope("INTERNAL", e.toString())
        }
    }

    /** `mobile.cancel(requestId)` directly on the calling (non-main) thread: the plan holds `verst-python`. */
    fun cancel(requestId: String) {
        try {
            val m = module ?: return
            Log.i(TAG, "cancel $requestId → ${m.callAttr("cancel", requestId)}")
        } catch (e: Throwable) {
            Log.w(TAG, "cancel failed", e)
        }
    }

    private class EngineCallFailed(val code: String, val detail: String) : Exception(code)

    private fun expectOk(envelope: String): JSONObject {
        val body = JSONObject(envelope)
        if (!body.getBoolean("ok")) {
            val err = body.getJSONObject("error")
            throw EngineCallFailed(err.getString("code"), err.optString("detail", err.optString("message")))
        }
        return body.optJSONObject("result") ?: JSONObject()
    }

    companion object {
        const val TAG = "VerstEngine"
        val WORLDS = listOf("central_russia_v1", "edge_cases_v1")

        fun errorEnvelope(code: String, message: String): String =
            JSONObject().put("ok", false).put("error", JSONObject().put("code", code).put("message", message)).toString()
    }
}
