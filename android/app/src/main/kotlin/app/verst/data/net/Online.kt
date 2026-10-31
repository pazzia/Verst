package app.verst.data.net

import java.io.IOException
import java.util.concurrent.ConcurrentHashMap
import kotlin.random.Random
import okhttp3.Interceptor
import okhttp3.Response

/*
 * ADR-0016 §4 OR-1…OR-8 for every online value (photos, the address search, and later the Wikipedia summaries):
 * the timeouts are on the shared client ([Net.client]); here are the one retry with jitter, the per-host circuit
 * breaker and the debug counters, as OkHttp interceptors so Coil and Nominatim get the same rules. Nothing in here
 * ever reaches the user: a failure is an `IOException` the caller turns into «no data» (OR-2, OR-4).
 */

/** OR-8: per-host counters for the debug panel (host → requests, failures, last code, last latency). */
object OnlineStats {
    data class Host(val requests: Int = 0, val failures: Int = 0, val lastCode: Int? = null, val lastMs: Long = 0, val blocked: Int = 0, val dropped: Int = 0)

    private val hosts = ConcurrentHashMap<String, Host>()

    /** Every request that reached the network, all hosts (the airplane-mode e2e expects this to stay put). */
    val total: Int get() = hosts.values.sumOf { it.requests }

    fun snapshot(): Map<String, Host> = HashMap(hosts)

    fun request(host: String, code: Int?, ms: Long, failed: Boolean) {
        hosts.compute(host) { _, h -> (h ?: Host()).let { it.copy(requests = it.requests + 1, failures = it.failures + if (failed) 1 else 0, lastCode = code, lastMs = ms) } }
    }

    fun blocked(host: String) {
        hosts.compute(host) { _, h -> (h ?: Host()).let { it.copy(blocked = it.blocked + 1) } }
    }

    /** OR-5: a 200 that was not data (HTML, truncated or garbage JSON, a body over 1 MB). */
    fun dropped(host: String) {
        hosts.compute(host) { _, h -> (h ?: Host()).let { it.copy(dropped = it.dropped + 1) } }
    }

    fun reset() = hosts.clear()
}

/** OR-6: 3 failures within 60 s for a host → no calls to it for 5 min. */
class CircuitBreaker(
    private val now: () -> Long = System::currentTimeMillis,
    private val failures: Int = 3,
    private val windowMs: Long = 60_000,
    private val openMs: Long = 5 * 60_000,
) {
    private val fails = ConcurrentHashMap<String, MutableList<Long>>()
    private val openUntil = ConcurrentHashMap<String, Long>()

    fun allowed(host: String): Boolean = (openUntil[host] ?: 0L) <= now()

    fun success(host: String) {
        fails.remove(host)
    }

    fun failure(host: String) {
        val t = now()
        val list = fails.getOrPut(host) { mutableListOf() }
        synchronized(list) {
            list += t
            list.removeAll { it < t - windowMs }
            if (list.size >= failures) {
                openUntil[host] = t + openMs
                list.clear()
            }
        }
    }

    fun reset() {
        fails.clear()
        openUntil.clear()
    }
}

/** The breaker is open for this host: the request was not sent (OR-6). */
class BreakerOpen(host: String) : IOException("breaker open: $host")

/**
 * OR-1 / OR-6 / OR-8 as one application interceptor: the breaker check, one retry with 0.5–1.5 s jitter for
 * idempotent GETs on an I/O error or a 5xx (never on 4xx, 429 included), the counters.
 */
class OnlineInterceptor(
    private val breaker: CircuitBreaker,
    private val jitterMs: () -> Long = { 500L + Random.nextLong(1_001) },
    private val sleep: (Long) -> Unit = { Thread.sleep(it) },
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val req = chain.request()
        val host = req.url.host
        if (!breaker.allowed(host)) {
            OnlineStats.blocked(host)
            throw BreakerOpen(host)
        }
        val idempotent = req.method == "GET" || req.method == "HEAD"
        var attempt = 0
        while (true) {
            attempt++
            val t0 = System.nanoTime()
            val result = runCatching { chain.proceed(req) }
            val ms = (System.nanoTime() - t0) / 1_000_000
            val r = result.getOrNull()
            val code = r?.code
            val serverError = code != null && code >= 500
            val failed = r == null || serverError || code == 429
            OnlineStats.request(host, code, ms, failed)
            if (!failed) {
                breaker.success(host)
                return r!!
            }
            breaker.failure(host)
            val retry = idempotent && attempt == 1 && (r == null || serverError) && breaker.allowed(host) && !chain.call().isCanceled()
            if (!retry) {
                return r ?: throw (result.exceptionOrNull() as? IOException ?: IOException(result.exceptionOrNull()))
            }
            r?.close()
            sleep(jitterMs())
        }
    }
}

/** OR-5: the body as text only when it is JSON and ≤ 1 MB; anything else is «no data» (an `IOException`). */
fun Response.jsonBodyOrNull(maxBytes: Long = 1_000_000): String? {
    val b = body ?: return null
    val type = b.contentType()
    if (type != null && type.subtype != "json" && !type.subtype.endsWith("+json")) return null
    if (b.contentLength() > maxBytes) return null
    val source = b.source()
    if (source.request(maxBytes + 1)) return null // more than maxBytes arrived → too big, dropped
    return source.buffer.readUtf8()
}
