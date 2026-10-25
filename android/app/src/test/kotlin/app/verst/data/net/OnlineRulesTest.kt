package app.verst.data.net

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * ADR-0016 OR-1…OR-8 on MockWebServer (CEO S4: airplane mode, a slow network, HTTP 500 and garbage replies):
 * every case ends as «no data» (`AddressResult.Failed` / `Offline`, the screen then says «уточним при интернете»),
 * never an exception; the breaker stops calls; the counters count.
 */
class OnlineRulesTest {
    private val server = MockWebServer()
    private var online = true
    private var clock = 0L
    private lateinit var breaker: CircuitBreaker
    private lateinit var client: NominatimClient
    private val ok = """[{"place_id": 7, "lat": "57.6266", "lon": "39.8938", "display_name": "1, Советская улица, Ярославль",
        "address": {"house_number": "1", "road": "Советская улица", "city": "Ярославль"}}]"""
    private var n = 0

    /** A fresh query each call (the 24 h cache would answer a repeated one). */
    private fun q() = "Советская ${++n}"

    private fun json(body: String) = MockResponse().setHeader("Content-Type", "application/json").setBody(body)

    @Before
    fun start() {
        server.start()
        OnlineStats.reset()
        breaker = CircuitBreaker(now = { clock })
        // the OR-1 limits scaled down 10 × so the slow case runs in a second (the defaults are pinned below)
        val http = Net.client(connectMs = 300, readMs = 500, callTimeoutMs = 1_500, guard = OnlineInterceptor(breaker, jitterMs = { 50 }))
        client = NominatimClient({ http }, server.url("/").toString(), { online }, minGapMs = 0)
    }

    @After
    fun stop() = server.shutdown()

    @Test
    fun theDefaultLimitsAreOr1() {
        val c = Net.client()
        assertEquals(3_000, c.connectTimeoutMillis)
        assertEquals(5_000, c.readTimeoutMillis)
        assertTrue("both attempts + jitter fit the call timeout", c.callTimeoutMillis in 12_000..14_000)
        assertTrue(c.interceptors.any { it is OnlineInterceptor })
    }

    @Test
    fun airplaneModeSendsNothing() = runBlocking {
        online = false
        repeat(3) { assertEquals(AddressResult.Offline, client.search(q())) }
        assertEquals(AddressResult.Offline, client.reverse(57.6, 39.8))
        assertEquals(0, server.requestCount)
        assertEquals(0, OnlineStats.total)
    }

    @Test
    fun aSlowServerEndsAtTheReadTimeoutAsNoData() = runBlocking {
        // 2 s latency per attempt against a 0.5 s read timeout: two attempts, then «no data», well under the call limit
        server.enqueue(json(ok).setHeadersDelay(2, TimeUnit.SECONDS))
        server.enqueue(json(ok).setHeadersDelay(2, TimeUnit.SECONDS))
        val t0 = System.nanoTime()
        val r = client.search(q())
        val ms = (System.nanoTime() - t0) / 1_000_000
        assertTrue(r is AddressResult.Failed)
        assertTrue("ended at the limits: $ms ms", ms < 1_900)
        // a slow body (throttled to 20 KB/s) that still arrives in time is used
        server.enqueue(json(ok).throttleBody(20 * 1024, 1, TimeUnit.SECONDS))
        assertTrue(client.search(q()) is AddressResult.Ok)
    }

    @Test
    fun http500IsRetriedOnceThenNoData() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(500))
        server.enqueue(json(ok))
        assertTrue("the retry answers", client.search(q()) is AddressResult.Ok)
        assertEquals(2, server.requestCount)
        server.enqueue(MockResponse().setResponseCode(503))
        server.enqueue(MockResponse().setResponseCode(500))
        assertTrue(client.search(q()) is AddressResult.Failed)
        assertEquals(4, server.requestCount)
        // 429: no retry
        server.enqueue(MockResponse().setResponseCode(429))
        assertTrue(client.search(q()) is AddressResult.Failed)
        assertEquals(5, server.requestCount)
    }

    @Test
    fun garbageRepliesAreNoDataAndCounted() = runBlocking {
        val host = server.url("/").host
        server.enqueue(MockResponse().setHeader("Content-Type", "text/html").setBody("<html>Too many requests</html>"))
        assertTrue(client.search(q()) is AddressResult.Failed)
        server.enqueue(json("""[{"place_id": 7, "lat": "57.6"""))
        assertTrue(client.search(q()) is AddressResult.Failed)
        // wrong types: rows without usable fields are skipped, never a crash
        server.enqueue(json("""[{"lat": {"x": 1}, "lon": [1], "address": "nope"}, 42, "x", null]"""))
        assertEquals(AddressResult.Ok(emptyList<app.verst.core.model.dto.SuggestionDto>()), client.search(q()))
        server.enqueue(json("""{"unexpected": "object"}"""))
        assertEquals(AddressResult.Ok(emptyList<app.verst.core.model.dto.SuggestionDto>()), client.search(q()))
        // a 5 MB body is dropped
        server.enqueue(json("[" + "\"x\",".repeat(1_250_000) + "\"x\"]"))
        assertTrue(client.search(q()) is AddressResult.Failed)
        // the connection dropped mid-reply
        server.enqueue(json(ok).setSocketPolicy(SocketPolicy.DISCONNECT_DURING_RESPONSE_BODY))
        server.enqueue(json(ok).setSocketPolicy(SocketPolicy.DISCONNECT_DURING_RESPONSE_BODY))
        assertTrue(client.search(q()) is AddressResult.Failed)
        assertTrue("dropped counted: ${OnlineStats.snapshot()}", (OnlineStats.snapshot()[host]?.dropped ?: 0) >= 3)
    }

    @Test
    fun theBreakerStopsCallsForFiveMinutes() = runBlocking {
        repeat(3) { server.enqueue(MockResponse().setResponseCode(500)) }
        assertTrue(client.search(q()) is AddressResult.Failed) // 2 requests (retry)
        assertTrue(client.search(q()) is AddressResult.Failed) // 3rd failure opens the breaker → no retry
        val sent = server.requestCount
        assertEquals(3, sent)
        repeat(3) { assertTrue(client.search(q()) is AddressResult.Failed) }
        assertEquals("no requests while open", sent, server.requestCount)
        assertTrue((OnlineStats.snapshot()[server.url("/").host]?.blocked ?: 0) >= 3)
        clock += 5 * 60_000 + 1
        server.enqueue(json(ok))
        assertTrue("closed again after 5 min", client.search(q()) is AddressResult.Ok)
    }
}
