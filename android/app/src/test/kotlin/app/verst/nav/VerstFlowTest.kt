package app.verst.nav

import app.verst.feature.card.cleanDescription

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
        var reverseName: String? = "Москва"
        var suggestRows = listOf(yar)
        var popularRows = listOf(yar)
        override suspend fun reverse(point: GeoPoint): EngineResult<PlaceNameDto?> =
            EngineResult.Ok(
                when (reverseName) {
                    null -> null
                    "Москва" -> PlaceNameDto("Москва", "город · Москва", "Москвы", "Москве")
                    else -> PlaceNameDto(reverseName!!, "город", null, null)
                },
            )
        var routes = emptyList<ReadyRouteDto>()
        override suspend fun readyRoutes(origin: GeoPoint) = EngineResult.Ok(routes)
        override suspend fun suggest(query: String, near: GeoPoint?) = EngineResult.Ok(suggestRows)
        override suspend fun popular() = EngineResult.Ok(popularRows)
        override suspend fun estimatePoints(origin: GeoPoint, points: List<GeoPoint>) = EngineResult.Ok(points.map { 263 as Int? })
        override suspend fun estimate(requestId: String, request: PlanRequest): EngineResult<EstimateDto> {
            estimates += request
            // a ready route: its round-trip km plus 10 per adult and 1 per child, so a crew change changes the number
            val rr = routes.firstOrNull { it.id == request.readyRouteId }
            return EngineResult.Ok(EstimateDto(rr?.let { it.kmTotal + 10 * request.adults + request.children } ?: estimateKm, 2))
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
        assertEquals(1, store.trips.size)
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
        assertEquals(1, store.trips.single().bookedHotels.size)
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
    fun windshieldRowsShowOnlyEngineKmSelectedFirstAndReestimateOnCrewChange() = runTest {
        val gw = FakeGateway()
        gw.routes = listOf(
            ReadyRouteDto("rr_tula_yasnaya", "Тула · Ясная Поляна", "2 дня · Толстой и пряники", 414, 207, "weekend", true, 2, 2, "t_moscow", "S"),
            ReadyRouteDto("rr_yaroslavl", "Ярославль", "2 дня · по М-8", 526, 263, "weekend", true, 2, 2, "t_moscow", "NE"),
        )
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        fun km(rr: Int) = rr + 10 * flow.adults + flow.children
        assertEquals(mapOf("rr_tula_yasnaya" to km(414), "rr_yaroslavl" to km(526)), flow.routeKm)
        val asked = gw.estimates.size
        settle()
        assertEquals("cached by request", asked, gw.estimates.size)

        flow.selectedRoute = 1
        val before = flow.routeKm
        flow.cycleSeat(1) // a crew change: new requests — no stale number, then the new estimates
        Snapshot.sendApplyNotifications()
        assertTrue(flow.routeKm.isEmpty())
        settle()
        assertEquals("rr_yaroslavl", gw.estimates[asked].readyRouteId) // the selected row first
        assertEquals(mapOf("rr_tula_yasnaya" to km(414), "rr_yaroslavl" to km(526)), flow.routeKm)
        assertTrue(before != flow.routeKm)
    }

    @Test
    fun focusIsRestoredOnEveryReturnToRoadAndAcrossProcessDeath() = runTest {
        val store = MemoryTripStore()
        val gw = FakeGateway()
        val flow = VerstFlow(gw, backgroundScope, store, io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        assertEquals(Route.Road, flow.top)
        val stops = flow.result!!.trip.daysList.flatMap { it.stops }
        val night = stops.first { it.kind == "overnight" }
        // Exit and back: the night row is the focus, and the return bumps the sequence.
        flow.roadTop(stops[2].id)
        flow.openExit(night.id)
        val seq = flow.roadFocusSeq
        assertTrue(flow.back())
        assertEquals(Route.Road, flow.top)
        assertEquals(night.id, flow.roadFocusId)
        assertEquals(seq + 1, flow.roadFocusSeq)
        flow.roadFocusShown()
        assertNull(flow.roadFocusId)
        // Waybill and back: no highlight, the top row comes back.
        flow.openWaybill()
        flow.roadTop("ignored while Waybill is on top")
        flow.back()
        assertEquals(stops[2].id, flow.roadTopId)
        assertEquals(seq + 2, flow.roadFocusSeq)
        // replace sheet / stop menu closed → a return too.
        flow.openStopMenu(stops[1]); flow.closeStopMenu()
        assertEquals(stops[1].id, flow.roadFocusId)
        assertEquals(seq + 3, flow.roadFocusSeq)
        // Process death: last.json carries both ids.
        flow.openExit(night.id)
        settle()
        assertEquals(night.id, store.last!!.roadFocusId)
        assertEquals(stops[2].id, store.last!!.roadTopId)
        val again = VerstFlow(FakeGateway(), backgroundScope, store, io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        assertEquals(listOf(Route.Windshield, Route.Road, Route.Exit), again.stack.toList())
        assertEquals(night.id, again.roadFocusId)
        assertEquals(stops[2].id, again.roadTopId)
    }

    @Test
    fun handoffDayMenuStopMenuTargetsAndFallbacks() = runTest {
        val gw = FakeGateway()
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        val opened = mutableListOf<Pair<app.verst.core.model.dto.HandoffLinksDto, Boolean>>()
        var navi = false
        var maps = false
        var result = HandoffTarget.Browser
        flow.handoffLauncher = object : HandoffLauncher {
            override fun navigatorInstalled() = navi
            override fun mapsInstalled() = maps
            override fun open(links: app.verst.core.model.dto.HandoffLinksDto, walk: Boolean): HandoffTarget {
                opened += links to walk
                return result
            }
        }
        settle()
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        val day = flow.result!!.trip.daysList.first()
        // The day menu: the engine has no `handoff` in the fake → the local ADR-0014 links of the day.
        flow.openDayMenu(day.day)
        settle()
        assertEquals(day.day, flow.dayMenu)
        assertEquals(HandoffTarget.Browser, flow.carTarget)
        val links = flow.dayHandoff!!.parts.single().links
        assertEquals(app.verst.core.model.NaviLinks.day(day)!!.navi, links.navigator)
        flow.dayMenuGo()
        assertNull(flow.dayMenu)
        assertEquals(links to false, opened.single())
        assertEquals(Toast.HandoffWeb(walk = false), flow.toast) // the web fallback says so
        // The stop menu with the navigator installed → no toast.
        navi = true
        result = HandoffTarget.Navigator
        flow.openStopMenu(day.stops[1])
        settle()
        assertEquals(HandoffTarget.Navigator, flow.carTarget)
        flow.navigatorFromStop()
        assertNull(flow.stopMenu)
        assertEquals(HandoffTarget.Navigator, flow.lastHandoff!!.second)
        assertTrue(opened.last().first.navigator!!.startsWith("yandexnavi://build_route_on_map?lat_from="))
        // Offline without an app → «нужен интернет», nothing opens; all links failing → «не получилось».
        navi = false
        flow.setOffline(true)
        flow.openDayMenu(day.day); settle(); flow.dayMenuGo()
        assertEquals(Toast.HandoffOffline, flow.toast)
        assertEquals(2, opened.size)
        flow.setOffline(false)
        result = HandoffTarget.None
        flow.openDayMenu(day.day); settle(); flow.dayMenuGo()
        assertEquals(Toast.HandoffFailed, flow.toast)
        // Maps only: the car label names Яндекс Карты.
        maps = true
        assertEquals(HandoffTarget.Maps, flow.carTarget)
        assertEquals(HandoffTarget.Maps, flow.walkTarget)
    }

    @Test
    fun gpsOriginRationaleManualDenyAndBlocked() = runTest {
        val gw = FakeGateway()
        val yarCity = yar.copy(nameGenRu = "Ярославля")
        gw.reverseName = "Ярославль"
        gw.suggestRows = listOf(yarCity)
        val address = FakeAddress()
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }, addressSearch = address) {}
        val asked = mutableListOf<Boolean>()
        var granted = false
        var precise = false
        flow.askLocationPermission = { asked += it }
        flow.locator = object : Locator {
            override fun granted() = granted
            override fun precise() = precise
            override suspend fun current() = GeoPoint("GPS", 57.63, 39.87)
        }
        settle()
        // First «Куда угодно»: the rationale sheet; «Выберу сам» → the ОТКУДА input, the sheet never comes back.
        flow.openNavigator()
        assertTrue(flow.locationSheet)
        flow.manualLocation()
        assertFalse(flow.locationSheet)
        assertTrue(flow.editingFrom)
        flow.back(); flow.back(); flow.openNavigator()
        assertFalse(flow.locationSheet)
        // «Моё местоположение» → the coarse dialog → granted → the fix's town (a gateway without geo_nearest).
        flow.useMyLocation()
        assertEquals(listOf(false), asked)
        granted = true
        flow.onLocationPermission(granted = true, blocked = false)
        settle()
        assertEquals(GpsState.On, flow.gps)
        assertEquals("Ярославль", flow.origin.label)
        assertEquals(57.63, flow.origin.lat, 0.0) // the trip starts at the fix
        assertEquals("Ярославля", flow.originGen)
        assertTrue(flow.originFromGps)
        assertTrue("coarse → «Точнее»", flow.gpsApprox)
        assertEquals("ул. Советская, 1", flow.originAddress) // online: the reverse-geocoded street
        flow.preciseLocation()
        assertEquals(listOf(false, true), asked)
        flow.onLocationPermission(granted = false, blocked = true)
        assertEquals(Toast.LocationBlocked, flow.toast)
        flow.onLocationPermission(granted = false, blocked = false)
        assertEquals(Toast.LocationDenied("Ярославль"), flow.toast)
        // No town within 30 km: the nearest popular town.
        gw.reverseName = null
        val tula = SuggestionDto("city", "Тула", "город", 54.1931, 37.6177, "t_tula", nameGenRu = "Тулы")
        gw.popularRows = listOf(yarCity, tula)
        flow.debugMockLocation = GeoPoint("mock", 54.0, 37.5)
        flow.locate()
        settle()
        assertEquals("Тула", flow.origin.label)
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

    @Test
    fun oneWriterLatestWinsAndFailuresAreReported() = runTest {
        val gw = FakeGateway()
        val store = MemoryTripStore()
        val flow = VerstFlow(gw, backgroundScope, store, io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        // A save before the stored trips are loaded is deferred (P1-1), not written over them.
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        flow.save()
        settle()
        assertEquals(1, store.trips.size)
        // 20 quick changes: saves, deletes and undos — the file ends with the last in-memory list.
        repeat(10) {
            flow.askDelete(flow.saved.single().id)
            flow.confirmDelete()
            flow.undoDelete()
        }
        flow.askDelete(flow.saved.single().id)
        flow.confirmDelete()
        settle()
        assertEquals(flow.saved.toList(), store.trips)
        assertTrue(store.trips.isEmpty())
        // A failed write: storage toast and the trip is not shown as saved.
        store.failWrites = true
        flow.openSaved("none") // no-op
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        flow.save()
        settle()
        assertEquals(Toast.StorageFull, flow.toast)
        assertFalse(flow.savedCurrent)
    }

    @Test
    fun lastTripIsWrittenAndRestored() = runTest {
        val gw = FakeGateway()
        val store = MemoryTripStore()
        val flow = VerstFlow(gw, backgroundScope, store, io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        flow.openWaybill()
        settle()
        val last = store.last!!
        assertEquals("waybill", last.screen)
        assertEquals(planned.trip.title, last.trip.title)
        // A new process: the flow comes back to Waybill over Road with the same trip.
        val again = VerstFlow(gw, backgroundScope, store, io = StandardTestDispatcher(testScheduler), now = { 8 }) {}
        settle()
        assertEquals(listOf(Route.Windshield, Route.Road, Route.Waybill), again.stack.toList())
        assertEquals(planned.trip.km, again.result!!.trip.km)
        // Back to the Windshield → the next start stays on the Windshield.
        while (again.back()) Unit
        settle()
        assertNull(store.last!!.screen)
        // Defaults (P2-10): the crew and pace survive too.
        again.cycleSeat(1)
        again.stepKm(50)
        settle()
        val third = VerstFlow(gw, backgroundScope, store, io = StandardTestDispatcher(testScheduler), now = { 9 }) {}
        settle()
        assertEquals(Seat.ADULT, third.seats[1])
        assertEquals(again.dailyKm, third.dailyKm)
        assertEquals(Route.Windshield, third.top)
    }

    /** DEV-302 fake: no network in unit tests. */
    private class FakeAddress : app.verst.data.net.AddressSearch {
        var searches = 0
        override suspend fun search(query: String): app.verst.data.net.AddressResult<List<SuggestionDto>> {
            searches++
            return app.verst.data.net.AddressResult.Ok(listOf(SuggestionDto("address", "ул. Советская, 1", "Ярославль", 57.6266, 39.8938)))
        }
        override suspend fun reverse(lat: Double, lon: Double) = app.verst.data.net.AddressResult.Ok<String?>("ул. Советская, 1")
    }

    @Test
    fun addressSearchOnlyOnSubmitAndOffline() = runTest {
        val address = FakeAddress()
        val flow = VerstFlow(FakeGateway(), backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }, addressSearch = address) {}
        settle()
        flow.openNavigator()
        flow.updateQuery("Ярославль Советская 1")
        settle()
        assertTrue(flow.looksLikeAddress(flow.query))
        assertFalse(flow.looksLikeAddress("Санкт"))
        assertEquals("typing never searches addresses", 0, address.searches)
        flow.submitAddress()
        settle()
        assertEquals(1, address.searches)
        assertEquals(AddressState.Done, flow.addressState)
        assertEquals("ул. Советская, 1", flow.addressResults.single().name)
        flow.pick(flow.addressResults.single())
        assertEquals("ул. Советская, 1", flow.destination!!.name)
        flow.setOffline(true)
        flow.updateQuery("Тверская 1")
        flow.submitAddress()
        assertEquals(AddressState.Offline, flow.addressState)
        assertEquals(1, address.searches)
    }

    @Test
    fun cardsOnlyForSightsAndHotelsAndFocusComesBack() = runTest {
        val flow = VerstFlow(FakeGateway(), backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        val stops = flow.result!!.trip.daysList.flatMap { it.stops }
        val sight = stops.first { it.kind == "sight" }
        stops.filter { it.kind in setOf("fuel", "rest", "start", "finish", "food") }.forEach { assertFalse(it.kind, flow.tappable(it)) }
        assertTrue(flow.tappable(sight))
        val seq = flow.roadFocusSeq
        flow.openCard(sight)
        assertEquals(sight.id, flow.card!!.rowId)
        assertEquals(sight.id, flow.roadFocusId)
        settle()
        flow.closeCard()
        assertNull(flow.card)
        assertEquals(seq + 1, flow.roadFocusSeq)
        // the hotel card «Выбрать отель» → 5.7 for that night
        val night = stops.first { it.kind == "overnight" && it.hotelOptions.isNotEmpty() }
        flow.openCard(night)
        assertEquals("hotel", flow.card!!.ui.kind)
        flow.cardPickHotel()
        assertEquals(Route.Exit, flow.top)
        assertEquals(night.id, flow.exitStopId)
    }

    @Test
    fun noFitOptionsGoBackToInstrumentsAndTheMinimumIsShownOverBudget() = runTest {
        val gw = object : PlannerGateway by FakeGateway() {
            override suspend fun planOutcome(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit) =
                EngineResult.Ok(
                    app.verst.core.model.dto.PlanOutcome.NoFit(
                        app.verst.core.model.dto.NoFitDto(
                            30_000, 31_500,
                            listOf(
                                app.verst.core.model.dto.BudgetOptionDto("cheaper_route", totalRub = 24_300, readyRouteId = "rr_tula_yasnaya", titleRu = "Тула · Ясная Поляна"),
                                app.verst.core.model.dto.BudgetOptionDto("raise_budget", budgetRub = 42_000),
                            ),
                            "не помещается", minimumTotalRub = 41_200, minimum = planned,
                        ),
                    ),
                )
        }
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree()
        flow.stepBudget(-1) // 30 000
        flow.go()
        settle(10_000)
        assertEquals(Route.NoFit, flow.top)
        assertTrue(flow.drive.noFit)
        flow.applyBudgetOption(flow.noFit!!.options[1])
        assertEquals(Route.Instruments, flow.top)
        assertEquals(42_000, flow.budgetCustom)
        assertEquals(42_000, flow.request().budgetRub)
        flow.stepBudget(1) // back to the presets: 60 000
        assertNull(flow.budgetCustom)
        assertEquals(60_000, flow.request().budgetRub)
        flow.go()
        settle(10_000)
        flow.showMinimum()
        assertEquals(Route.Road, flow.top)
        assertTrue(flow.showingMinimum)
        assertEquals(planned.trip.km, flow.result!!.trip.km)
    }

    @Test
    fun reportFromTheStopMenuAndTheCardIsQueuedWithTheRightToast() = runTest {
        val store = MemoryTripStore()
        val flow = VerstFlow(FakeGateway(), backgroundScope, store, io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        val sight = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.kind == "sight" }
        // D-5 → D-7: no reason → «Отправить» does nothing
        flow.openStopMenu(sight)
        flow.openReport(sight)
        assertNull(flow.stopMenu)
        assertEquals(sight.id, flow.report!!.stopId)
        flow.sendReport()
        assertEquals(sight.id, flow.report!!.stopId)
        flow.pickReportReason("nonsense")
        assertNull(flow.reportReason)
        flow.pickReportReason("price")
        flow.setReportCommentText("x".repeat(400))
        assertEquals(app.verst.core.model.Reports.COMMENT_MAX, flow.reportComment.length)
        flow.setReportCommentText("  Билет уже 600 ₽ ")
        val seq = flow.roadFocusSeq
        flow.sendReport()
        settle()
        assertNull(flow.report)
        assertEquals(Toast.ReportThanks, flow.toast)
        assertEquals(seq + 1, flow.roadFocusSeq) // the row gets focus back
        assertEquals(1, store.reports.size)
        assertEquals("Билет уже 600 ₽", store.reports[0].comment)
        assertEquals("road", store.reports[0].source)
        // offline, from the card: queued
        flow.setOffline(true)
        flow.openCard(sight)
        settle()
        flow.reportFromCard()
        assertNull(flow.card)
        assertEquals("card", flow.report!!.source)
        flow.pickReportReason("closed")
        flow.sendReport()
        settle()
        assertEquals(Toast.ReportQueued, flow.toast)
        assertEquals(listOf("price", "closed"), store.reports.map { it.reason })
        assertEquals(listOf(true, false), store.reports.map { it.online })
        // back closes the sheet without sending
        flow.openReport(sight)
        assertTrue(flow.back())
        assertNull(flow.report)
        settle()
        assertEquals(2, store.reports.size)
        flow.setOffline(false)
    }

    @Test
    fun cityPlateBreaksOnlyAtSpacesAndAfterHyphens() {
        assertEquals(listOf("САНКТ-", "ПЕТЕРБУРГ"), app.verst.core.ui.components.cityBreakPieces("Санкт-Петербург"))
        assertEquals(listOf("ПЕРЕСЛАВЛЬ-", "ЗАЛЕССКИЙ"), app.verst.core.ui.components.cityBreakPieces("Переславль-Залесский"))
        assertEquals(listOf("ВЕЛИКИЙ", "НОВГОРОД"), app.verst.core.ui.components.cityBreakPieces("Великий Новгород"))
        assertEquals(listOf("РОСТОВ-", "НА-", "ДОНУ"), app.verst.core.ui.components.cityBreakPieces("Ростов-на-Дону"))
    }

    @Test
    fun cardDescriptionThatOnlyRepeatsTheKindLineIsHidden() {
        val clean = ::cleanDescription
        assertNull(clean("площадь в г. Иваново", "площадь · Иваново", "Иваново"))
        assertNull(clean("монастырь в Костроме", "монастырь · Кострома", "Кострома"))
        assertEquals("Главный монастырь России, собор XV века.", clean("главный монастырь России, собор XV века", "монастырь · Сергиев Посад", "Сергиев Посад"))
        assertEquals("Музей под открытым небом.", clean("Музей под открытым небом.", "музей · Суздаль", "Суздаль"))
    }

    /**
     * S4 investigation (docs/bugs/s4-walk-filters.md): «Свой маршрут» in a town with few places (Фрязино). The fake
     * engine behaves like the real one there: the first walk succeeds, a walk that excludes its stops is
     * NOT_ENOUGH_POIS. Expected behaviour; this test FAILS on main (bugs a and c), the fix makes it pass.
     */
    @Test
    fun customWalkRecoversAfterOtherVariantRunsOutOfPlaces() = runTest {
        val root = java.io.File(System.getProperty("verst.repoRoot") ?: "../..")
        fun resp(f: String) = kotlinx.serialization.json.Json.parseToJsonElement(root.resolve("docs/contracts/v2/$f").readText())
            .let { (it as kotlinx.serialization.json.JsonObject)["response"].toString() }
        val presets = (app.verst.core.model.EngineJson.cityPresets(resp("city_presets.json")) as EngineResult.Ok).value
        val oneWalk = (app.verst.core.model.EngineJson.walkRoute(resp("city_route-custom.json")) as EngineResult.Ok).value
        val requests = mutableListOf<app.verst.core.model.WalkRequest>()
        val gw = object : PlannerGateway by FakeGateway() {
            override suspend fun cityPresets(point: GeoPoint) = EngineResult.Ok(presets)
            override suspend fun cityRoute(requestId: String, request: app.verst.core.model.WalkRequest): EngineResult<app.verst.core.model.dto.WalkRouteDto> {
                requests += request
                // like Фрязино: 3 places in reach; without them there is nothing left
                return if (oneWalk.stops.any { it.poiId != null && it.poiId in request.exclude }) {
                    EngineResult.Err(app.verst.core.model.dto.EngineErrorDto("NOT_ENOUGH_POIS", "not enough places", field = "preset"))
                } else EngineResult.Ok(oneWalk.copy(id = "w${requests.size}"))
            }
        }
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.debugLocationAnswered()
        flow.openCity()
        settle()
        flow.selectCityPreset("custom")
        flow.setCityDuration(240)
        flow.toggleCityInterest("architecture")
        flow.buildCustomWalk()
        settle()
        assertEquals(Route.Walk, flow.top)
        // «Другой вариант» → the engine runs out of places
        flow.otherWalk()
        settle()
        // (a) the screen drops out of the walk to the City plate…
        assertEquals("NOT_ENOUGH_POIS", flow.cityError)
        // …and every later build still excludes the first walk's stops, whatever the filters
        flow.selectCityPreset("custom") // «Другой маршрут»
        flow.setCityDuration(120)
        flow.toggleCityInterest("parks")
        flow.buildCustomWalk()
        settle()
        val last = requests.last()
        assertEquals("filters reach the request", 120, last.durationMin)
        assertTrue("filters reach the request", "parks" in last.interests)
        // EXPECTED (fails on main): a filter change starts a fresh walk — the exclusions of «Другой вариант» are dropped
        assertTrue("exclusions survive a filter change: ${last.exclude}", last.exclude.isEmpty())
        assertEquals(Route.Walk, flow.top)
        assertNull(flow.cityError)
    }
}
