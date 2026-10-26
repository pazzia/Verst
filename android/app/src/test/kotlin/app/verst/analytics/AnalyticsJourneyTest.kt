package app.verst.analytics

import androidx.compose.runtime.snapshots.Snapshot
import app.verst.core.model.EngineJson
import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.core.model.PlanRequest
import app.verst.core.model.dto.EstimateDto
import app.verst.core.model.dto.HandoffLinksDto
import app.verst.core.model.dto.NoFitDto
import app.verst.core.model.dto.PlaceNameDto
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlanOutcome
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.SuggestionDto
import app.verst.data.MemoryTripStore
import app.verst.engine.PlannerGateway
import app.verst.nav.DrivenAnswer
import app.verst.nav.HandoffLauncher
import app.verst.nav.HandoffTarget
import app.verst.nav.Route
import app.verst.nav.VerstFlow
import java.io.File
import java.time.LocalDate
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * ENG-05: the events [VerstFlow] sends on a fake engine (golden trip G01 Москва → Ярославль), recorded by
 * [RecordingAnalytics]: the funnel journey's exact sequence and properties, the `trip_id` rules (tracking plan §2.5
 * q3) and the rest of the tracking plan's events. Values that come from the golden trip (its night, total, start
 * date) are read from it, so a regenerated golden does not break these tests; today: night `d1s06` at 6 000 ₽,
 * start 2026-10-24, 2 days.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class AnalyticsJourneyTest {
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")
    private val text = root.resolve("backend/planner/tests/golden/snapshots/G01_msk_yar_round.json").readText()
    private val planned = PlanResultDto(EngineJson.trip(text), "share", "октябрь", "2026", tripJson = text)
    private val night = planned.trip.daysList.flatMap { it.stops }.first { it.kind == "overnight" }
    private val nightPrice = night.hotelOptions.first { it.placeId == (night.selectedHotelId ?: night.hotelOptions.first().placeId) }.priceCrewRub
    private val startDate = LocalDate.parse(planned.trip.daysList.first().startAt!!.substring(0, 10))
    private val lastDay = startDate.plusDays(planned.trip.days - 1L)
    private val yar = SuggestionDto("city", "Ярославль", "город · Ярославская область", 57.6261, 39.8845, "t_yaroslavl")

    private inner class FakeGateway : PlannerGateway {
        override var world: String = "central_russia_v1"
        val routes = listOf(
            ReadyRouteDto("rr_golden_ring", "Золотое кольцо", kmTotal = 540, kmSign = 540),
            ReadyRouteDto("rr_tula_yasnaya", "Тула и Ясная Поляна", kmTotal = 414, kmSign = 414),
        )

        /** The engine's time for a plan (the `latency_ms` the app must report). */
        var planMs = 1_200L

        /** Set: the plan answers «no trip within the budget» with [planned] as the minimum. */
        var noFit: NoFitDto? = null

        override suspend fun setClock(spec: String): EngineResult<Unit> = EngineResult.Ok(Unit)
        override suspend fun readyRoutes(origin: GeoPoint): EngineResult<List<ReadyRouteDto>> = EngineResult.Ok(routes)
        override suspend fun suggest(query: String, near: GeoPoint?): EngineResult<List<SuggestionDto>> = EngineResult.Ok(listOf(yar))
        override suspend fun popular(): EngineResult<List<SuggestionDto>> = EngineResult.Ok(listOf(yar))
        override suspend fun reverse(point: GeoPoint): EngineResult<PlaceNameDto?> =
            EngineResult.Ok(PlaceNameDto("Москва", "город · Москва", "Москвы", "Москве"))
        override suspend fun estimatePoints(origin: GeoPoint, points: List<GeoPoint>): EngineResult<List<Int?>> = EngineResult.Ok(points.map { 263 })
        override suspend fun estimate(requestId: String, request: PlanRequest): EngineResult<EstimateDto> = EngineResult.Ok(EstimateDto(540, 2))
        override suspend fun plan(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanResultDto> {
            onEvent(PlanEventDto("stage", text = "Прокладываем дорогу", progress = 0.1))
            delay(planMs)
            return EngineResult.Ok(planned)
        }
        override suspend fun planOutcome(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanOutcome> {
            val nf = noFit ?: return super.planOutcome(requestId, request, onEvent)
            delay(planMs)
            return EngineResult.Ok(PlanOutcome.NoFit(nf))
        }
        override suspend fun replaceStop(tripJson: String, stopId: String, altId: String): EngineResult<PlanResultDto> =
            EngineResult.Ok(planned.copy(trip = planned.trip.copy(km = planned.trip.km + 1)))
        override suspend fun patchCost(tripJson: String, patchJson: String): EngineResult<PlanResultDto> = EngineResult.Ok(planned)
    }

    /** The navigator app is installed and opens. */
    private val launcher = object : HandoffLauncher {
        override fun navigatorInstalled() = true
        override fun open(links: HandoffLinksDto, walk: Boolean) = HandoffTarget.Navigator
    }

    private fun TestScope.settle(ms: Long = 1_000) {
        Snapshot.sendApplyNotifications()
        advanceTimeBy(ms)
        runCurrent()
    }

    private fun TestScope.newFlow(gw: FakeGateway = FakeGateway(), rec: RecordingAnalytics = RecordingAnalytics()): VerstFlow {
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { testScheduler.currentTime }) {}
        flow.analytics = rec
        flow.handoffLauncher = launcher
        return flow
    }

    /** Windshield → the second ready route → Instruments → ПОЕХАЛИ → Road ahead. */
    private fun TestScope.toRoad(flow: VerstFlow) {
        settle()
        flow.selectReadyRoute(1)
        flow.openReadyRoute()
        settle()
        flow.go()
        settle(10_000)
        assertEquals(Route.Road, flow.top)
    }

    @Test
    fun funnelJourneySendsTheExactEventsInOrder() = runTest {
        val rec = RecordingAnalytics()
        val flow = newFlow(rec = rec)
        toRoad(flow)
        flow.save()
        settle()
        flow.openExit(night.id)
        flow.book()

        val t = flow.tripId!!
        assertEquals(36, t.length) // a random UUID made on the phone
        assertEquals(
            listOf(
                "ready_route_shown" to mapOf("count" to 2, "start_city" to "Москва"),
                "ready_route_selected" to mapOf("route_id" to "rr_tula_yasnaya", "rank" to 2),
                "plan_requested" to mapOf(
                    "km_bucket" to "500-800", "days" to 2, "dog" to false, "children" to "0", "mood" to "fun",
                    "ready_route_id" to "rr_tula_yasnaya",
                ),
                "plan_succeeded" to mapOf("trip_id" to t, "latency_ms" to 1_200L, "routing_source" to "road", "ready_route_id" to "rr_tula_yasnaya"),
                "trip_saved" to mapOf(
                    "trip_id" to t, "start_date" to startDate.toString(), "days" to planned.trip.days, "ready_route_id" to "rr_tula_yasnaya",
                ),
                // the selected hotel of the night, for the crew
                "hotel_link_clicked" to mapOf("trip_id" to t, "stop_id" to night.id, "price_bucket" to Buckets.price(nightPrice)),
            ),
            rec.sent,
        )
        assertEquals(t, flow.saved.single().id) // the saved trip is keyed by its trip_id
        TrackingPlanContract.assertClean(rec.all)
    }

    @Test
    fun noAnalyticsMeansNoEventsAndNoExtraEngineCalls() = runTest {
        var reverses = 0
        val gw = object : PlannerGateway by FakeGateway() {
            override suspend fun reverse(point: GeoPoint): EngineResult<PlaceNameDto?> {
                reverses += 1
                return EngineResult.Ok(null)
            }
        }
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { testScheduler.currentTime }) {}
        settle()
        val before = reverses // the origin's name forms (OI-39) only
        flow.openReadyRoute()
        flow.back()
        settle()
        assertEquals(before, reverses) // `start_city` is not looked up for the no-op
        assertTrue(flow.analytics === NoopAnalytics)
    }

    @Test
    fun tripIdIsKeptThroughReplaceRefitSaveAndReopenAndRenewedByPoexali() = runTest {
        val rec = RecordingAnalytics()
        val flow = newFlow(rec = rec)
        toRoad(flow)
        val t = flow.tripId!!

        // D-6 replace: the same trip
        val stop = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.replaceable && it.alternatives.size >= 2 }
        flow.openReplace(stop)
        flow.pickAlternative(stop.alternatives[1].id)
        flow.confirmReplace()
        settle()
        assertEquals(AnalyticsEvent.StopReplaced(t, stop.kind, 2), rec.events.last())

        // «Подогнать под бюджет» on the unsaved trip: planned again, the same trip
        flow.openWaybill()
        flow.refit()
        settle(10_000)
        assertEquals(t, flow.tripId)

        // saved under its trip_id; reopened from «Мои поездки» with the same id
        flow.save()
        settle()
        assertEquals(t, flow.saved.single().id)
        flow.openSaved(t)
        flow.openWaybill()
        assertEquals(t, (rec.events.last() as AnalyticsEvent.WaybillOpened).tripId)

        // the refit of a saved trip becomes a second saved trip: a new id
        flow.refit()
        settle(10_000)
        val refitted = flow.tripId!!
        assertNotEquals(t, refitted)

        // ПОЕХАЛИ again: a new id
        flow.openReadyRoute()
        flow.go()
        settle(10_000)
        val again = flow.tripId!!
        assertNotEquals(t, again)
        assertNotEquals(refitted, again)

        assertEquals(listOf(t, t, refitted, again), rec.events.filterIsInstance<AnalyticsEvent.PlanSucceeded>().map { it.tripId })
        assertEquals(2, rec.events.count { it is AnalyticsEvent.PlanRequested }) // the two refits are not «requested»
        TrackingPlanContract.assertClean(rec.all)
    }

    @Test
    fun failedAndNoFitPlansReportTheCodeAndTheEngineLatency() = runTest {
        val gw = FakeGateway()
        val rec = RecordingAnalytics()
        val flow = newFlow(gw, rec)
        settle()
        flow.openReadyRoute()
        settle()

        flow.debugForceError = "UNREACHABLE"
        flow.go()
        settle(10_000)
        assertEquals(AnalyticsEvent.PlanFailed(VerstFlow.STEP_GAP_MS, "UNREACHABLE"), rec.events.last())
        flow.debugForceError = null
        flow.back() // Drive → Instruments

        gw.noFit = NoFitDto(budgetRub = 20_000, minimum = planned)
        flow.go()
        settle(10_000)
        assertEquals(mapOf("latency_ms" to 1_200L, "error_code" to "NO_FIT"), rec.events.last().params())
        assertEquals(Route.NoFit, flow.top)
        // «Показать самый экономный вариант» shows the request's trip: saving it keeps the request's trip_id
        flow.showMinimum()
        flow.save()
        settle()
        val saved = rec.events.last() as AnalyticsEvent.TripSaved
        assertEquals(flow.tripId, saved.tripId)
        assertEquals(2, rec.events.count { it is AnalyticsEvent.PlanRequested })
        assertTrue(rec.events.none { it is AnalyticsEvent.PlanSucceeded })
        TrackingPlanContract.assertClean(rec.all)
    }

    @Test
    fun searchInstrumentsWaybillHandoffReportShareAndDrivenEvents() = runTest {
        val rec = RecordingAnalytics()
        val flow = newFlow(rec = rec)
        settle()
        flow.appOpened(AnalyticsEvent.StartType.COLD)

        // Navigator: the first request of the visit and the pick (length and row only, never the query)
        flow.openNavigator()
        flow.updateQuery("Яр")
        flow.updateQuery("Ярос")
        settle()
        flow.pick(yar)
        flow.openInstrumentsFree()
        settle()
        val nav = rec.sent.dropWhile { it.first != "search_started" }.take(2)
        assertEquals(
            listOf(
                "search_started" to mapOf<String, Any>("query_len" to 2),
                "search_selected" to mapOf<String, Any>("query_len" to 4, "result_type" to "city", "rank" to 1),
            ),
            nav,
        )

        // Instruments: one event per value that moved
        rec.clear()
        flow.cycleSeat(0) // empty → adult
        flow.cycleSeat(0) // adult → child: adults and children both move
        flow.toggleDog()
        flow.toggleFrontAdult()
        flow.stepKm(50)
        flow.stepBudget(1) // 40 000 → 60 000
        assertEquals(
            listOf(
                "adults" to "3", "adults" to "2", "children" to "1", "dog" to "yes", "adults" to "1",
                "pace" to flow.dailyKm.toString(), "budget" to "60k",
            ),
            rec.events.map { (it as AnalyticsEvent.ParamsChanged).field.wire to it.valueBucket },
        )

        settle() // the estimate of the changed request
        rec.clear()
        flow.go()
        settle(10_000)
        assertEquals(
            mapOf("km_bucket" to "500-800", "days" to 2, "dog" to true, "children" to "1", "mood" to "fun", "ready_route_id" to "none"),
            rec.events.first { it is AnalyticsEvent.PlanRequested }.params(),
        )
        val t = flow.tripId!!

        rec.clear()
        flow.openWaybill()
        flow.toggleReserve()
        settle()
        flow.back()
        flow.openDayMenu(1)
        settle()
        flow.dayMenuGo()
        val stop = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.kind == "sight" }
        flow.openReport(stop)
        flow.pickReportReason("closed")
        flow.setReportCommentText("Иван, +7 916 123-45-67") // the comment stays in the local queue
        flow.sendReport()
        flow.tripShared()
        assertEquals(
            listOf(
                "waybill_opened" to mapOf("trip_id" to t, "total_bucket" to Buckets.total(planned.trip.cost.totalRub), "over_budget" to planned.trip.cost.overBudget),
                "reserve_toggled" to mapOf("trip_id" to t, "state" to if (planned.trip.cost.reserveOn) "off" else "on"),
                "navigator_opened" to mapOf("trip_id" to t, "app" to "yandex_navigator", "day" to 1),
                "feedback_sent" to mapOf("trip_id" to t, "kind" to "closed"),
                "trip_shared" to mapOf("trip_id" to t, "channel" to "unknown"),
            ),
            rec.sent,
        )

        // «Вы съездили?» (last day E = start + days − 1): «Нет», an unsaved trip and a trip not over yet send nothing
        rec.clear()
        assertFalse(flow.answerTripDriven(t, DrivenAnswer.FULL, lastDay.plusDays(2))) // not saved yet
        flow.save()
        settle()
        rec.clear()
        assertFalse(flow.answerTripDriven(t, DrivenAnswer.NO, lastDay.plusDays(2)))
        assertFalse(flow.answerTripDriven(t, DrivenAnswer.FULL, lastDay)) // the trip's own last day: not over yet
        assertTrue(flow.answerTripDriven(t, DrivenAnswer.PARTIAL, lastDay.plusDays(2)))
        assertEquals(
            listOf(
                "trip_driven_confirmed" to mapOf(
                    "trip_id" to t, "completion" to "partial", "days_since_end" to 2, "km_bucket" to Buckets.km(planned.trip.km),
                    // the saved trip's own crew (the engine trip's input), not the Instruments draft
                    "dog" to planned.trip.input.crew.dog, "children" to Buckets.children(planned.trip.input.crew.children),
                    "source" to "in_app_prompt",
                ),
            ),
            rec.sent,
        )

        // the whole session: the tracking plan's events, less the ones the other tests drive (ready-route row, replace,
        // failed plan, hotel link) and the two without a UI yet (excursion link, Pro form: PrivacyGuardTest builds them)
        val elsewhere = setOf("ready_route_selected", "stop_replaced", "plan_failed", "hotel_link_clicked", "excursion_link_clicked", "pro_waitlist_joined")
        assertEquals(TrackingPlanContract.EVENTS.keys - elsewhere, rec.all.map { it.name }.toSet())
        TrackingPlanContract.assertClean(rec.all)
    }
}
