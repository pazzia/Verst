package app.verst.nav

import androidx.compose.runtime.snapshots.Snapshot
import app.verst.core.model.EngineArgs
import app.verst.core.model.EngineJson
import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.core.model.PlanRequest
import app.verst.core.model.TripFigures
import app.verst.core.model.dto.EstimateDto
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlaceNameDto
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.SuggestionDto
import app.verst.core.model.SavedTrips
import app.verst.data.MemoryTripStore
import app.verst.engine.PlannerGateway
import java.io.File
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * DEV-SLICE-2 flow on a fake engine: one trip shows one distance (estimate before, the plan's number after),
 * Waybill reserve via `patch_cost`, replace via `replace_stop` + undo, save and reopen from «Мои поездки».
 */
@OptIn(ExperimentalCoroutinesApi::class)
class VerstFlowTest {
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")
    private val text = root.resolve("backend/planner/tests/golden/snapshots/G01_msk_yar_round.json").readText()
    private val planned = PlanResultDto(EngineJson.trip(text), "share", "октябрь", "2026", tripJson = text)
    private val yar = SuggestionDto("city", "Ярославль", "город · Ярославская область", 57.6261, 39.8845, "t_yaroslavl")

    private inner class FakeGateway : PlannerGateway {
        val estimates = mutableListOf<PlanRequest>()
        val patches = mutableListOf<String>()
        val replaced = mutableListOf<Pair<String, String>>()

        /** What `estimate` answers; the plan answers [planned] (its km wins once it exists). */
        var estimateKm = 540

        override var world: String = "central_russia_v1"
        val hotelPatches = mutableListOf<String>()
        override suspend fun setClock(spec: String): EngineResult<Unit> = EngineResult.Ok(Unit)
        override suspend fun reverse(point: GeoPoint): EngineResult<PlaceNameDto?> =
            EngineResult.Ok(PlaceNameDto("Москва", "город · Москва", "Москвы", "Москве"))
        override suspend fun readyRoutes(origin: GeoPoint) = EngineResult.Ok(emptyList<ReadyRouteDto>())
        override suspend fun suggest(query: String, near: GeoPoint?) = EngineResult.Ok(listOf(yar))
        override suspend fun popular() = EngineResult.Ok(listOf(yar))
        override suspend fun estimatePoints(origin: GeoPoint, points: List<GeoPoint>) = EngineResult.Ok(points.map { 263 as Int? })
        override suspend fun estimate(requestId: String, request: PlanRequest): EngineResult<EstimateDto> {
            estimates += request
            return EngineResult.Ok(EstimateDto(estimateKm, 2))
        }
        override suspend fun plan(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanResultDto> {
            onEvent(PlanEventDto("stage", text = "Прокладываем дорогу", progress = 0.1))
            return EngineResult.Ok(planned)
        }
        override suspend fun replaceStop(tripJson: String, stopId: String, altId: String): EngineResult<PlanResultDto> {
            replaced += stopId to altId
            val t = planned.trip
            return EngineResult.Ok(planned.copy(trip = t.copy(km = t.km + 1, cost = t.cost.copy(totalRub = t.cost.totalRub + 100))))
        }
        override suspend fun patchCost(tripJson: String, patchJson: String): EngineResult<PlanResultDto> {
            if ("hotelChoice" in patchJson) {
                hotelPatches += patchJson
                return EngineResult.Ok(planned)
            }
            patches += patchJson
            val c = planned.trip.cost
            return EngineResult.Ok(planned.copy(trip = planned.trip.copy(cost = c.copy(reserveOn = false, totalRub = c.totalRub - 1000))))
        }
    }

    private fun TestScope.settle(ms: Long = 1_000) {
        Snapshot.sendApplyNotifications()
        advanceTimeBy(ms)
        runCurrent()
    }

    @Test
    fun oneTripOneDistanceThenWaybillReplaceSaveReopen() = runTest {
        val gw = FakeGateway()
        val store = MemoryTripStore()
        val flow = VerstFlow(gw, backgroundScope, store, io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()

        // Navigator: picking Ярославль estimates the trip on the engine (debounced), no straight line anywhere.
        flow.openNavigator()
        settle()
        assertEquals(263, flow.rowKm[yar.pointKey]) // popular rows: the engine's base-route km
        flow.pick(yar)
        Snapshot.sendApplyNotifications()
        assertNull(flow.figures) // nothing shown until the engine answers (never a guessed number)
        settle()
        assertEquals(1, gw.estimates.size)
        assertEquals(TripFigures(540, 2), flow.figures!!.figures)
        assertFalse(flow.figures!!.stale)

        // Instruments: same request → no new estimate; a child added → stale figure, then a new estimate.
        flow.openInstrumentsFree()
        settle()
        assertEquals(1, gw.estimates.size)
        flow.cycleSeat(0)
        flow.cycleSeat(0)
        Snapshot.sendApplyNotifications()
        assertTrue(flow.figures!!.stale)
        settle()
        assertEquals(2, gw.estimates.size)
        assertEquals(1, gw.estimates.last().children)

        // Plan: the engine's trip km is used everywhere afterwards, even if an estimate had said otherwise.
        assertEquals(542, planned.trip.km) // G01: the plan's number differs from what the fake estimate said
        flow.go()
        settle(10_000)
        assertEquals(Route.Road, flow.top)
        assertEquals(planned.trip.km, flow.result!!.trip.km)
        assertEquals(TripFigures(planned.trip.km, planned.trip.days), flow.figures!!.figures)

        // Waybill: expand one line at a time; reserve toggle goes through patch_cost.
        flow.openWaybill()
        assertEquals(Route.Waybill, flow.top)
        flow.toggleLine("fuel")
        flow.toggleLine("food")
        assertEquals("food", flow.expandedLine)
        flow.toggleReserve()
        settle(10_000)
        assertEquals(listOf(EngineArgs.reservePatch(false)), gw.patches)
        assertFalse(flow.result!!.trip.cost.reserveOn)
        assertTrue(flow.back())

        // Replace: sheet → pick → engine replace → total updated, toast with undo; undo restores.
        val stop = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.alternatives.isNotEmpty() }
        val before = flow.result!!.trip.cost.totalRub
        flow.openReplace(stop)
        flow.pickAlternative(stop.alternatives.first().id)
        flow.confirmReplace()
        runCurrent()
        assertEquals(listOf(stop.id to stop.alternatives.first().id), gw.replaced)
        assertNull(flow.replace)
        assertEquals(Toast.Replaced(planned.trip.cost.totalRub + 100), flow.toast)
        assertTrue(flow.canUndo)
        flow.undo()
        assertEquals(before, flow.result!!.trip.cost.totalRub)

        // Save → «Мои поездки» → reopen into Road ahead with the saved trip.
        flow.save()
        settle(10_000)
        assertEquals(1, flow.saved.size)
        assertEquals(1, store.load().size)
        assertTrue(flow.savedCurrent)
        assertEquals(1, flow.waybillNumber)
        while (flow.back()) Unit
        assertEquals(Route.Windshield, flow.top)
        flow.openTrips()
        assertTrue(flow.tripsSheet)
        flow.openSaved(flow.saved.single().id)
        assertEquals(listOf(Route.Windshield, Route.Road), flow.stack.toList())
        assertTrue(flow.openedFromSaved)
        assertEquals(planned.trip.title, flow.result!!.trip.title)
        assertEquals(EngineJson.json.parseToJsonElement(text), EngineJson.json.parseToJsonElement(flow.result!!.tripJson))
        // Saving again updates the same entry.
        flow.save()
        assertEquals(1, flow.saved.size)
    }

    @Test
    fun exitBookingDeleteAndLimit() = runTest {
        val gw = FakeGateway()
        val store = MemoryTripStore()
        val flow = VerstFlow(gw, backgroundScope, store, io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        assertEquals("Москвы", flow.originGen) // OI-39: the engine's genitive, not a Kotlin map
        flow.openNavigator()
        flow.pick(yar)
        flow.openInstrumentsFree()
        flow.go()
        settle(10_000)
        val night = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.kind == "overnight" && it.hotelOptions.size >= 2 }

        // Exit: a hotel choice is local first (selection + total), then the engine's patch.
        flow.openExit(night.id)
        assertEquals(Route.Exit, flow.top)
        val other = night.hotelOptions[1]
        flow.selectHotel(night.id, other.placeId)
        Snapshot.sendApplyNotifications()
        val local = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.id == night.id }
        assertEquals(other.placeId, local.selectedHotelId) // before the engine answers
        settle()
        assertEquals(1, gw.hotelPatches.size)
        assertTrue(gw.hotelPatches.single().contains(other.placeId))

        // Booking: CTA → mock partner sheet → dismissal → «Забронировали?» → yes → booked + toast with undo.
        flow.book()
        assertTrue(flow.partnerOpen)
        flow.closePartner()
        assertTrue(flow.bookedDialog)
        flow.answerBooked(true)
        val booked = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.id == night.id }
        assertEquals(booked.selectedHotelId ?: booked.hotelOptions.first().placeId, flow.booked[night.id])
        assertTrue(flow.isBooked(night.id))
        assertTrue(flow.toast is Toast.Booked)
        flow.undoBooking()
        assertNull(flow.booked[night.id])
        flow.book(); flow.closePartner(); flow.answerBooked(true)
        // Offline (debug): the CTA only says «Нужен интернет».
        flow.setOffline(true)
        flow.book()
        assertEquals(Toast.NeedInternet, flow.toast)
        flow.setOffline(false)

        // Save keeps the booking; delete with undo; the 50-trip limit opens the dialog.
        flow.save()
        settle()
        assertEquals(1, store.load().single().bookedHotels.size)
        while (flow.back()) Unit
        flow.askDelete(flow.saved.single().id)
        flow.confirmDelete()
        assertTrue(flow.saved.isEmpty())
        assertTrue(flow.canUndoDelete)
        flow.undoDelete()
        assertEquals(1, flow.saved.size)
        val full = (1..SavedTrips.LIMIT).map { flow.saved.single().copy(id = "t$it") }
        flow.clearSaved()
        flow.saved.addAll(full)
        flow.openTrips()
        flow.openSaved("t1")
        flow.save() // updates t1 in place even at the limit
        assertFalse(flow.limitDialog)
        flow.resetData()
        flow.saved.addAll(full)
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        flow.save()
        assertTrue(flow.limitDialog)
        flow.limitToTrips()
        assertTrue(flow.tripsSheet)
        assertEquals(Route.Windshield, flow.top)
    }

    @Test
    fun reserveIsLocalFirstThenEngine() = runTest {
        val gw = FakeGateway()
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        val before = flow.result!!.trip.cost
        flow.toggleReserve()
        // Local CostCalculator before the engine answers: reserve off, total without the reserve line.
        val local = flow.result!!.trip.cost
        assertFalse(local.reserveOn)
        assertEquals(before.subtotalRub.let { s -> ((s + 50) / 100) * 100 }, local.totalRub)
        settle()
        assertEquals(1, gw.patches.size)
    }
}

