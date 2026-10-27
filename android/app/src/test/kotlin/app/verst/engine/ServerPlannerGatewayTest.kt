package app.verst.engine

import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.core.model.PlanRequest
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.EstimateDto
import app.verst.core.model.dto.PlaceNameDto
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlanOutcome
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.SuggestionDto
import app.verst.data.net.ServerAuth
import app.verst.data.net.ServerClient
import java.io.File
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** SRV-01: the server plans when enabled and reachable; the phone engine otherwise, with the reason recorded. */
class ServerPlannerGatewayTest {
    private class Phone : PlannerGateway {
        var plans = 0
        override var world = "central_russia_v1"
        override suspend fun readyRoutes(origin: GeoPoint) = EngineResult.Ok(emptyList<ReadyRouteDto>())
        override suspend fun suggest(query: String, near: GeoPoint?) = EngineResult.Ok(emptyList<SuggestionDto>())
        override suspend fun popular() = EngineResult.Ok(emptyList<SuggestionDto>())
        override suspend fun plan(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanResultDto> {
            plans++
            return EngineResult.Err(EngineErrorDto("PHONE", "the phone engine answered"))
        }
        override suspend fun estimate(requestId: String, request: PlanRequest): EngineResult<EstimateDto> = EngineResult.Err(EngineErrorDto("NOT_SUPPORTED"))
        override suspend fun setClock(spec: String) = EngineResult.Ok(Unit)
        override suspend fun reverse(point: GeoPoint): EngineResult<PlaceNameDto?> = EngineResult.Ok(null)
        override suspend fun estimatePoints(origin: GeoPoint, points: List<GeoPoint>) = EngineResult.Ok(points.map { null as Int? })
        override suspend fun replaceStop(tripJson: String, stopId: String, altId: String): EngineResult<PlanResultDto> = EngineResult.Err(EngineErrorDto("NOT_SUPPORTED"))
        override suspend fun patchCost(tripJson: String, patchJson: String): EngineResult<PlanResultDto> = EngineResult.Err(EngineErrorDto("NOT_SUPPORTED"))
    }

    private val server = MockWebServer()
    private val phone = Phone()
    private var enabled = true
    private var online = true
    private val store = object : ServerClient.AuthStore {
        var auth: ServerAuth? = null
        override fun load() = auth
        override fun save(auth: ServerAuth?) {
            this.auth = auth
        }
    }
    private lateinit var gateway: ServerPlannerGateway
    private val request = PlanRequest(GeoPoint("Екатеринбург", 56.8389, 60.6057), GeoPoint("Тюмень", 57.153, 65.5343))
    private val result: String by lazy {
        val root = File(System.getProperty("verst.repoRoot") ?: "../..")
        Json.parseToJsonElement(root.resolve("docs/contracts/v2/plan-synthetic.json").readText())
            .jsonObject["response"]!!.jsonObject["result"]!!.toString()
    }

    @Before
    fun start() {
        server.start()
        store.auth = ServerAuth(server.url("/").toString().trimEnd('/'), "d1", "x".repeat(43))
        val http = OkHttpClient.Builder().build()
        val client = ServerClient({ server.url("/").toString() }, store, "0.2", { "ru-RU" }, { http })
        gateway = ServerPlannerGateway(phone, client, { enabled }, { online })
    }

    @After
    fun stop() = server.shutdown()

    @Test
    fun theServerPlansWhenEnabledAndReachable() = runBlocking {
        server.enqueue(MockResponse().setHeader("Content-Type", "text/event-stream").setBody("event: done\ndata: $result\n\n"))
        val r = gateway.planOutcome("r1", request) {}
        assertTrue(r is EngineResult.Ok && (r as EngineResult.Ok).value is PlanOutcome.Plan)
        assertEquals(0, phone.plans)
        assertTrue(gateway.lastPlan!!.server)
        assertNull(gateway.lastPlan!!.fallbackReason)
    }

    @Test
    fun thePhonePlansWhenTheSettingIsOffOrThePhoneIsOffline() = runBlocking {
        enabled = false
        assertEquals("PHONE", (gateway.planOutcome("r1", request) {} as EngineResult.Err).error.code)
        assertNull(gateway.lastPlan) // not a fallback: the phone was the choice
        enabled = true
        online = false
        assertEquals("PHONE", (gateway.planOutcome("r2", request) {} as EngineResult.Err).error.code)
        assertEquals("offline", gateway.lastPlan!!.fallbackReason)
        assertEquals(0, server.requestCount)
        assertEquals(2, phone.plans)
    }

    @Test
    fun serverTroubleFallsBackToThePhoneWithTheReason() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(503).setBody("{}"))
        assertEquals("PHONE", (gateway.planOutcome("r1", request) {} as EngineResult.Err).error.code)
        assertFalse(gateway.lastPlan!!.server)
        assertEquals("HTTP 503", gateway.lastPlan!!.fallbackReason)
        assertEquals(1, phone.plans)
    }

    @Test
    fun theEnginesAnswerFromTheServerIsFinal() = runBlocking {
        server.enqueue(MockResponse().setHeader("Content-Type", "text/event-stream").setBody("event: error\ndata: {\"code\":\"NO_ROUTE\",\"message\":\"\"}\n\n"))
        assertEquals("NO_ROUTE", (gateway.planOutcome("r1", request) {} as EngineResult.Err).error.code)
        assertEquals(0, phone.plans)
        assertTrue(gateway.lastPlan!!.server)
    }
}
