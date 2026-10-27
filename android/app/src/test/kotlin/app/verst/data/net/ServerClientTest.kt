package app.verst.data.net

import app.verst.core.model.EngineResult
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlanOutcome
import java.io.File
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** SRV-01 on MockWebServer: registration once, the SSE plan, the engine's error, 401 → re-register, 5xx → unavailable. */
class ServerClientTest {
    private val server = MockWebServer()
    private val store = object : ServerClient.AuthStore {
        var auth: ServerAuth? = null
        override fun load() = auth
        override fun save(auth: ServerAuth?) {
            this.auth = auth
        }
    }
    private lateinit var client: ServerClient
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")
    private val result: String by lazy {
        Json.parseToJsonElement(root.resolve("docs/contracts/v2/plan-synthetic.json").readText())
            .jsonObject["response"]!!.jsonObject["result"]!!.toString()
    }
    private val input = """{"origin":{"lat":56.8389,"lon":60.6057,"label":"Екатеринбург"},"crew":{"adults":2},"dailyKm":500}"""

    @Before
    fun start() {
        server.start()
        val http = OkHttpClient.Builder().addInterceptor(Net.userAgent).build()
        client = ServerClient({ server.url("/").toString() }, store, "0.2.150-mock", { "ru-RU" }, { http })
    }

    @After
    fun stop() = server.shutdown()

    private fun registered() = MockResponse().setResponseCode(201).setBody("""{"deviceId":"d1","token":"${"t".repeat(43)}"}""")

    private fun sse(vararg frames: String) = MockResponse().setHeader("Content-Type", "text/event-stream; charset=utf-8")
        .setBody(frames.joinToString("\n\n", postfix = "\n\n"))

    @Test
    fun registersOnceThenStreamsThePlan() = runBlocking {
        server.enqueue(registered())
        server.enqueue(
            sse(
                "event: stage\ndata: {\"event\":\"stage\",\"key\":\"route\",\"text\":\"Прокладываем дорогу\",\"progress\":0.2}",
                ": ping",
                "event: stop\ndata: {\"event\":\"stop\",\"day\":1,\"stop\":{\"id\":\"s1\",\"kind\":\"sight\",\"sign\":\"sight\",\"name\":\"Музей\",\"kmAt\":120,\"provisional\":false}}",
                "event: done\ndata: $result",
            ),
        )
        val events = mutableListOf<PlanEventDto>()
        val r = client.plan(input) { events += it }
        assertTrue(r.toString(), r is EngineResult.Ok && (r as EngineResult.Ok).value is PlanOutcome.Plan)
        assertEquals(listOf("stage", "stop"), events.map { it.event })
        assertEquals("Музей", events[1].stop?.name)
        assertEquals(2, server.requestCount)
        val reg = server.takeRequest()
        assertEquals("/v1/devices", reg.path)
        assertEquals("""{"appVersion":"0.2.150-mock","locale":"ru-RU"}""", reg.body.readUtf8())
        val plan = server.takeRequest()
        assertEquals("/v1/trips/plan", plan.path)
        assertEquals("Bearer ${"t".repeat(43)}", plan.getHeader("Authorization"))
        assertEquals("text/event-stream", plan.getHeader("Accept"))
        assertEquals(Net.USER_AGENT, plan.getHeader("User-Agent"))
        assertEquals(input, plan.body.readUtf8())

        // the token is kept: the next plan sends no registration
        server.enqueue(sse("event: done\ndata: $result"))
        client.plan(input) {}
        assertEquals(3, server.requestCount)
        assertEquals("/v1/trips/plan", server.takeRequest().path)
    }

    @Test
    fun theEnginesErrorComesBackAsAnEngineError() = runBlocking {
        store.auth = ServerAuth(server.url("/").toString().trimEnd('/'), "d1", "x".repeat(43))
        server.enqueue(sse("event: error\ndata: {\"code\":\"UNREACHABLE\",\"message\":\"…\",\"details\":{\"pointIndex\":1}}"))
        val r = client.plan(input) {}
        assertEquals("UNREACHABLE", (r as EngineResult.Err).error.code)
        // a 4xx before the stream is the same
        server.enqueue(MockResponse().setResponseCode(422).setBody("""{"error":{"code":"INVALID_INPUT","message":"…","details":{"field":"dailyKm"}}}"""))
        assertEquals("INVALID_INPUT", (client.plan(input) {} as EngineResult.Err).error.code)
    }

    @Test
    fun aForgottenTokenIsRegisteredAgainOnce() = runBlocking {
        store.auth = ServerAuth(server.url("/").toString().trimEnd('/'), "old", "o".repeat(43))
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"error":{"code":"UNAUTHORIZED","message":"","details":{}}}"""))
        server.enqueue(registered())
        server.enqueue(sse("event: done\ndata: $result"))
        val r = client.plan(input) {}
        assertTrue(r is EngineResult.Ok)
        assertEquals(listOf("/v1/trips/plan", "/v1/devices", "/v1/trips/plan"), (1..3).map { server.takeRequest().path })
        assertEquals("d1", store.auth?.deviceId)
    }

    @Test
    fun serverTroubleIsUnavailableNotAnEngineAnswer() = runBlocking {
        store.auth = ServerAuth(server.url("/").toString().trimEnd('/'), "d1", "x".repeat(43))
        server.enqueue(MockResponse().setResponseCode(503).setBody("""{"error":{"code":"UPSTREAM"}}"""))
        val e = runCatching { client.plan(input) {} }.exceptionOrNull()
        assertTrue(e.toString(), e is ServerUnavailable)
        // a stream cut before `done`
        server.enqueue(sse("event: stage\ndata: {\"event\":\"stage\",\"key\":\"route\",\"text\":\"…\",\"progress\":0.1}"))
        val cut = runCatching { client.plan(input) {} }.exceptionOrNull()
        assertTrue(cut.toString(), cut is ServerUnavailable)
        // nothing listening
        server.shutdown()
        assertTrue(runCatching { client.plan(input) {} }.exceptionOrNull() is ServerUnavailable)
    }

    @Test
    fun checkReportsTheRoundTripAndRegisters() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"status":"ok"}"""))
        server.enqueue(registered())
        val ok = client.check() as ServerCheck.Ok
        assertTrue(ok.registered)
        assertEquals("d1", store.auth?.deviceId)
        server.enqueue(MockResponse().setResponseCode(502))
        assertEquals(ServerCheck.Failed("HTTP 502"), client.check())
    }

    @Test
    fun noServerInTheBuild() = runBlocking {
        val none = ServerClient({ null }, store, "0.2", { "ru-RU" })
        assertTrue(!none.configured)
        assertTrue(none.check() is ServerCheck.Failed)
        assertNull(store.auth)
    }
}
