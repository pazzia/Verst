package app.verst.nav

import app.verst.feature.card.cleanDescription

import androidx.compose.runtime.snapshots.Snapshot
import app.verst.core.model.EngineArgs
import app.verst.core.model.EngineJson
import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.core.model.LatLon
import app.verst.core.model.MapsChoice
import app.verst.core.model.NaviLinks
import app.verst.core.model.PlanRequest
import app.verst.core.model.TripFigures
import app.verst.core.model.dto.EstimateDto
import app.verst.core.model.dto.HandoffLinksDto
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
import org.junit.Assert.assertNotNull
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
        /** Plans asked (CEO 29.10: never one for a destination abroad). */
        var plans = 0
        override suspend fun plan(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanResultDto> {
            plans++
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

    /**
     * CEO 29.10: «Вести по картам» opens the preferred maps app directly with the whole day (Яндекс Карты in Russia);
     * in the sheet Google Карты get the same points (an https link), the Навигатор the next point only (both tabs);
     * «Запомнить выбор» stores the maps app as the «Навигация» setting, never the Навигатор.
     */
    @Test
    fun handoffSheetRoutesAndRememberedChoice() = runTest {
        val gw = FakeGateway()
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        var choice = MapsChoice.AUTO
        flow.mapsChoiceRead = { choice }
        flow.mapsChoiceWrite = { choice = it }
        flow.countrySource = CountrySource { "ru" }
        val opened = mutableListOf<Triple<HandoffApp, String?, String?>>()
        flow.handoffLauncher = object : HandoffLauncher {
            override fun navigatorInstalled() = true
            override fun mapsInstalled() = true
            override fun googleInstalled() = true
            override fun open(links: HandoffLinksDto, walk: Boolean) = HandoffTarget.None
            override fun openIn(app: HandoffApp, uri: String?, web: String?): HandoffTarget {
                opened += Triple(app, uri, web)
                return when (app) {
                    HandoffApp.NAVI -> HandoffTarget.Navigator
                    HandoffApp.MAPS -> HandoffTarget.Maps
                    HandoffApp.GOOGLE -> HandoffTarget.Google
                }
            }
        }
        settle()
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        val day = flow.result!!.trip.daysList.first()
        val local = NaviLinks.day(day)!!
        // «Вести по картам»: in Russia Яндекс Карты open directly with the whole day — no sheet, no Навигатор
        assertEquals(HandoffApp.MAPS, flow.preferredMaps)
        flow.handoff(day.day); settle()
        assertNull(flow.handoffSheet)
        assertEquals(Triple(HandoffApp.MAPS, local.mapsApp, local.web), opened.single())
        assertEquals(HandoffTarget.Maps, flow.lastHandoff!!.second)
        // the sheet (a day's «вести» / a long-press): Google Карты get the same points by https
        flow.openHandoffSheet(day.day); settle()
        assertEquals(day.day, flow.handoffSheet!!.day)
        assertNotNull(flow.handoffSheet!!.handoff)
        flow.handoffPick(HandoffApp.GOOGLE)
        assertNull(flow.handoffSheet)
        val g = opened.last()
        assertEquals(HandoffApp.GOOGLE, g.first)
        assertEquals(NaviLinks.googleRoute(local.points), g.second)
        assertEquals(g.second, g.third) // without the app, the same link in the browser
        assertTrue(g.second!!, g.second!!.endsWith("&travelmode=driving"))
        assertEquals(Toast.HandoffOpen(HandoffApp.GOOGLE), flow.toast)
        assertEquals(MapsChoice.AUTO, choice) // «Запомнить выбор» is off
        // «До след.»: the Навигатор to the next point only (no vias) — and so is the day scope
        flow.openHandoffSheet(day.day); settle()
        flow.handoffScope(null)
        flow.handoffPick(HandoffApp.NAVI)
        val navi = opened.last()
        assertEquals(HandoffApp.NAVI, navi.first)
        assertTrue(navi.second!!.startsWith("yandexnavi://build_route_on_map?lat_to="))
        assertFalse(navi.second!!.contains("lat_via_0"))
        flow.openHandoffSheet(day.day); settle()
        flow.handoffPick(HandoffApp.NAVI)
        assertFalse(opened.last().second!!.contains("lat_via_0"))
        // «Запомнить выбор» + Google Карты → the «Навигация» setting; «Вести по картам» then opens Google Карты
        flow.openHandoffSheet(day.day); settle()
        flow.toggleHandoffRemember()
        flow.handoffPick(HandoffApp.GOOGLE)
        assertEquals(MapsChoice.GOOGLE, choice)
        assertEquals(HandoffApp.GOOGLE, flow.preferredMaps) // the user's choice wins over Russia
        val n = opened.size
        flow.handoff(day.day); settle()
        assertNull(flow.handoffSheet)
        assertEquals(n + 1, opened.size)
        assertEquals(HandoffApp.GOOGLE, opened.last().first)
        // the Навигатор is never remembered
        flow.openHandoffSheet(day.day); settle()
        flow.handoffPick(HandoffApp.NAVI)
        assertEquals(MapsChoice.GOOGLE, choice)
        flow.openHandoffSheet(day.day); settle()
        assertNotNull(flow.handoffSheet)
        flow.back()
        assertNull(flow.handoffSheet)
    }

    /**
     * CEO 29.10: the day menu, the stop menu and walks open the preferred maps app — Яндекс Карты in Russia and when
     * the country is unknown, Google Карты abroad, the user's choice over both; the browser and offline fallbacks.
     */
    @Test
    fun handoffDayMenuStopMenuTargetsAndFallbacks() = runTest {
        val gw = FakeGateway()
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        var choice = MapsChoice.AUTO
        flow.mapsChoiceRead = { choice }
        flow.mapsChoiceWrite = { choice = it }
        var country: String? = "RU"
        flow.countrySource = CountrySource { country }
        val opened = mutableListOf<Triple<HandoffApp, String?, String?>>()
        var maps = false
        var google = false
        var result = HandoffTarget.Browser
        flow.handoffLauncher = object : HandoffLauncher {
            override fun navigatorInstalled() = true
            override fun mapsInstalled() = maps
            override fun googleInstalled() = google
            override fun open(links: HandoffLinksDto, walk: Boolean) = HandoffTarget.None
            override fun openIn(app: HandoffApp, uri: String?, web: String?): HandoffTarget {
                opened += Triple(app, uri, web)
                return result
            }
        }
        settle()
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        val day = flow.result!!.trip.daysList.first()
        // The day menu: the engine has no `handoff` in the fake → the local links; Яндекс Карты missing → the browser.
        flow.openDayMenu(day.day)
        settle()
        assertEquals(day.day, flow.dayMenu)
        assertEquals(HandoffTarget.Browser, flow.carTarget)
        val links = flow.dayHandoff!!.parts.single().links
        flow.dayMenuGo()
        assertNull(flow.dayMenu)
        assertEquals(Triple(HandoffApp.MAPS, links.maps, links.web), opened.single()) // never the Навигатор, though installed
        assertEquals(Toast.HandoffWeb(walk = false), flow.toast) // the web fallback says so
        // The stop menu: from this stop to the end of its day, in Яндекс Карты.
        maps = true
        result = HandoffTarget.Maps
        flow.openStopMenu(day.stops[1])
        settle()
        assertEquals(HandoffTarget.Maps, flow.carTarget)
        flow.navigatorFromStop()
        assertNull(flow.stopMenu)
        assertEquals(HandoffTarget.Maps, flow.lastHandoff!!.second)
        assertEquals(NaviLinks.fromStop(flow.result!!.trip, day.stops[1].id)!!.mapsApp, opened.last().second)
        // Abroad: Google Карты lead; not installed → the browser label, installed → the app.
        country = "DE"
        assertEquals(HandoffApp.GOOGLE, flow.preferredMaps)
        assertEquals(HandoffTarget.Browser, flow.carTarget)
        google = true
        assertEquals(HandoffTarget.Google, flow.carTarget)
        result = HandoffTarget.Google
        flow.openDayMenu(day.day); settle(); flow.dayMenuGo()
        val g = opened.last()
        assertEquals(HandoffApp.GOOGLE, g.first)
        assertTrue(g.second!!, g.second!!.startsWith("https://www.google.com/maps/dir/?api=1&origin="))
        assertEquals(Toast.HandoffOpen(HandoffApp.GOOGLE), flow.toast)
        // Walks: the same preference, in walking mode.
        flow.walkHandoff = NaviLinks.walking(listOf(LatLon(57.62, 39.88), LatLon(57.625, 39.885), LatLon(57.63, 39.89))).toDto(null, mode = "walk")
        flow.walkHandoffGo(1)
        assertEquals(HandoffApp.GOOGLE, opened.last().first)
        assertTrue(opened.last().second!!, opened.last().second!!.endsWith("&travelmode=walking"))
        assertTrue(opened.last().second!!, opened.last().second!!.contains("origin=57.620000,39.880000"))
        // the user's choice wins over the country
        choice = MapsChoice.YANDEX
        assertEquals(HandoffApp.MAPS, flow.preferredMaps)
        flow.walkHandoffGo(1)
        assertEquals(HandoffApp.MAPS, opened.last().first)
        assertTrue(opened.last().second!!, opened.last().second!!.endsWith("&rtt=pd"))
        // unknown country → Яндекс Карты
        choice = MapsChoice.AUTO
        country = null
        assertEquals(HandoffApp.MAPS, flow.preferredMaps)
        // Offline without the app → «нужен интернет», nothing opens; the launcher failing → «не получилось».
        maps = false
        val before = opened.size
        flow.setOffline(true)
        flow.openDayMenu(day.day); settle(); flow.dayMenuGo()
        assertEquals(Toast.HandoffOffline, flow.toast)
        assertEquals(before, opened.size)
        flow.setOffline(false)
        result = HandoffTarget.None
        flow.openDayMenu(day.day); settle(); flow.dayMenuGo()
        assertEquals(Toast.HandoffFailed, flow.toast)
        // the walk label follows the same app
        assertEquals(HandoffTarget.Browser, flow.walkTarget)
        maps = true
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
        var near: app.verst.core.model.GeoPoint? = null
        /** CEO 29.10: what `search` answers (a foreign row for the abroad tests). */
        var rows = listOf(SuggestionDto("address", "ул. Советская, 1", "Ярославль", 57.6266, 39.8938))
        /** CEO 29.10: the reverse lookups asked, and how long each answer takes / what it is (by the point). */
        val reverses = mutableListOf<Pair<Double, Double>>()
        var reverseDelayMs: (Double, Double) -> Long = { _, _ -> 0L }
        var reverseAnswer: (Double, Double) -> String? = { _, _ -> "ул. Советская, 1" }
        override suspend fun search(query: String, near: app.verst.core.model.GeoPoint?): app.verst.data.net.AddressResult<List<SuggestionDto>> {
            searches++
            this.near = near
            return app.verst.data.net.AddressResult.Ok(rows)
        }
        override suspend fun reverse(lat: Double, lon: Double): app.verst.data.net.AddressResult<String?> {
            reverses += lat to lon
            val wait = reverseDelayMs(lat, lon)
            if (wait > 0) kotlinx.coroutines.delay(wait)
            return app.verst.data.net.AddressResult.Ok(reverseAnswer(lat, lon))
        }
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
        assertEquals("the user's place biases the search", flow.origin, address.near)
        // CEO 29.10: a bare street is searchable too
        assertTrue(flow.looksLikeAddress("улица Мира"))
        assertTrue(flow.looksLikeAddress("проспект Мира"))
        assertFalse(flow.looksLikeAddress("Ленина"))
        assertTrue(flow.addressOffered("Ленина"))
        assertFalse(flow.addressOffered("Ле"))
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
        val flow = VerstFlow(FakeGateway(), backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }, addressSearch = FakeAddress()) {}
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

    /**
     * CEO 29.10: a card asks its street address online (Nominatim, else the phone's geocoder) and keeps it per place
     * for the session; a late answer for a card that is no longer open never lands on the open one; offline: nothing.
     */
    @Test
    fun cardAddressIsReverseGeocodedAndALateAnswerIsDropped() = runTest {
        val address = FakeAddress()
        val flow = VerstFlow(FakeGateway(), backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }, addressSearch = address) {}
        settle()
        flow.openNavigator(); flow.pick(yar); flow.openInstrumentsFree(); flow.go()
        settle(10_000)
        val sights = flow.result!!.trip.daysList.flatMap { it.stops }.filter { it.kind == "sight" && it.lat != null }
        val first = sights[0]
        val second = sights[1]
        // opening a card fills the address (the loading line meanwhile)
        flow.openCard(first)
        assertTrue(flow.card!!.ui.addressLoading)
        assertNull(flow.card!!.ui.address)
        settle()
        assertEquals("ул. Советская, 1", flow.card!!.ui.address)
        assertFalse(flow.card!!.ui.addressLoading)
        assertEquals(listOf(first.lat!! to first.lon!!), address.reverses)
        flow.closeCard()
        // the first place answers slowly, the second at once: the first's late answer must not land on the second
        address.reverseDelayMs = { lat, _ -> if (lat == sights[2].lat) 5_000L else 0L }
        address.reverseAnswer = { lat, _ -> if (lat == sights[2].lat) "ул. Поздняя, 9" else "ул. Ленина, 5" }
        val slow = sights[2]
        flow.openCard(slow)
        settle(100)
        assertTrue(flow.card!!.ui.addressLoading)
        flow.closeCard()
        flow.openCard(second)
        settle(100)
        assertEquals("ул. Ленина, 5", flow.card!!.ui.address)
        settle(10_000) // the slow answer arrives now
        assertEquals(second.id, flow.card!!.rowId)
        assertEquals("ул. Ленина, 5", flow.card!!.ui.address)
        // the session cache: reopening the first card asks nothing
        flow.closeCard()
        val asked = address.reverses.size
        flow.openCard(first)
        assertEquals("ул. Советская, 1", flow.card!!.ui.address)
        assertFalse(flow.card!!.ui.addressLoading)
        assertEquals(asked, address.reverses.size)
        // Nominatim knows nothing → the phone's geocoder answers
        flow.closeCard()
        address.reverseAnswer = { _, _ -> null }
        flow.addressFallback = object : app.verst.data.net.AddressSearch {
            override suspend fun search(query: String, near: GeoPoint?) = app.verst.data.net.AddressResult.Ok(emptyList<SuggestionDto>())
            override suspend fun reverse(lat: Double, lon: Double) = app.verst.data.net.AddressResult.Ok<String?>("Соборная площадь, 1")
        }
        val third = sights.getOrNull(3) ?: sights.last()
        flow.openCard(third)
        settle()
        assertEquals("Соборная площадь, 1", flow.card!!.ui.address)
        // offline: no lookup, no loading line, no address
        flow.closeCard()
        flow.setOffline(true)
        val before = address.reverses.size
        val fresh = flow.result!!.trip.daysList.flatMap { it.stops }.last { it.kind == "sight" && it.lat != null && it.id !in setOf(first.id, second.id, slow.id, third.id) }
        flow.openCard(fresh)
        settle()
        assertNull(flow.card!!.ui.address)
        assertFalse(flow.card!!.ui.addressLoading)
        assertEquals(before, address.reverses.size)
        flow.setOffline(false)
    }

    /**
     * CEO 29.10: an address abroad («Прага») is found, but the engine plans only in Russia: no estimate, no plan —
     * the Navigator's plate, and its button opens the road in the preferred maps app with ОТКУДА and КУДА.
     */
    @Test
    fun aForeignAddressIsNotPlannedAndHandsOffToTheMaps() = runTest {
        val gw = FakeGateway()
        val address = FakeAddress()
        val prague = SuggestionDto("address", "Прага", "Прага · Чехия", 50.0874, 14.4213, countryCode = "cz")
        address.rows = listOf(prague)
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }, addressSearch = address) {}
        flow.mapsChoiceRead = { MapsChoice.AUTO }
        flow.countrySource = CountrySource { "ru" }
        val opened = mutableListOf<Triple<HandoffApp, String?, String?>>()
        flow.handoffLauncher = object : HandoffLauncher {
            override fun navigatorInstalled() = true
            override fun mapsInstalled() = true
            override fun open(links: HandoffLinksDto, walk: Boolean) = HandoffTarget.None
            override fun openIn(app: HandoffApp, uri: String?, web: String?): HandoffTarget {
                opened += Triple(app, uri, web)
                return HandoffTarget.Maps
            }
        }
        settle()
        flow.openNavigator()
        settle()
        val estimatesBefore = gw.estimates.size
        flow.updateQuery("Прага")
        flow.submitAddress()
        settle()
        assertEquals(listOf(prague), flow.addressResults)
        assertFalse("no engine km for a row abroad", prague.pointKey in flow.rowKm)
        flow.pick(flow.addressResults.single())
        settle()
        assertTrue(flow.destinationAbroad)
        assertEquals(estimatesBefore, gw.estimates.size) // no doomed estimate
        // ПОЕХАЛИ cannot plan: the Navigator stays, nothing goes to the engine
        flow.openInstrumentsFree()
        assertEquals(Route.Navigator, flow.top)
        flow.go()
        settle(10_000)
        assertEquals(0, gw.plans)
        assertEquals(Route.Navigator, flow.top)
        assertNull(flow.result)
        // the plate's button: Яндекс Карты (Russia) with two points, ОТКУДА → Прага
        val points = listOf(LatLon(flow.origin.lat, flow.origin.lon), LatLon(prague.lat, prague.lon))
        assertEquals(HandoffTarget.Maps, flow.abroadHandoff())
        assertEquals(Triple(HandoffApp.MAPS, NaviLinks.mapsAppRoute(points), NaviLinks.webRoute(points)), opened.single())
        // with Google Карты chosen: the Google directions link with the same two points
        flow.mapsChoiceRead = { MapsChoice.GOOGLE }
        flow.abroadHandoff()
        val google = NaviLinks.googleRoute(points)
        assertEquals(Triple(HandoffApp.GOOGLE, google, google), opened.last())
        assertTrue(google.contains("origin=") && google.contains("destination=50.087400,14.421300"))
        // a Russian destination plans again as before
        flow.pick(yar)
        assertFalse(flow.destinationAbroad)
        assertNull(flow.abroadHandoff())
        flow.openInstrumentsFree()
        flow.go()
        settle(10_000)
        assertEquals(1, gw.plans)
    }

    // ---- CEO 29.10: trips abroad, wave 1 — only the server plans them

    /** The server of the abroad tests (no network in unit tests): what it answers, what it was asked. */
    private class FakeServer : app.verst.data.net.PlanServer {
        var present = true
        val inputs = mutableListOf<String>()
        /** null: the server is unavailable (transport, 5xx). */
        var answer: EngineResult<app.verst.core.model.dto.PlanOutcome>? = null
        override val configured: Boolean get() = present
        override suspend fun plan(inputJson: String, onEvent: (PlanEventDto) -> Unit): EngineResult<app.verst.core.model.dto.PlanOutcome> {
            inputs += inputJson
            return answer ?: throw app.verst.data.net.ServerUnavailable("HTTP 503")
        }
    }

    /** Real engine output: Владикавказ → Тбилиси on the server's `world_v1` (core-model test resources). */
    private val abroadPlan: EngineResult<app.verst.core.model.dto.PlanOutcome> by lazy {
        val result = root.resolve("android/core-model/src/test/resources/abroad/plan-vladikavkaz-tbilisi.json").readText()
        EngineJson.planOutcome("""{"ok":true,"result":$result}""")
    }
    private val tbilisi = SuggestionDto("address", "Тбилиси", "Тбилиси · Грузия", 41.7151, 44.8271, countryCode = "ge")
    private val baku = SuggestionDto("address", "Баку", "Баку · Азербайджан", 40.4093, 49.8671, countryCode = "az")

    /**
     * «Где строить маршрут»: Телефон (`enabled = false`), yet a destination abroad goes to the server — after the
     * tester's consent (the settings' dialog), and a Russian destination still plans on the phone.
     */
    @Test
    fun aTripAbroadGoesToTheServerEvenWithThePhoneSettingAfterTheConsent() = runTest {
        val phone = FakeGateway()
        val server = FakeServer().apply { answer = abroadPlan }
        val net = app.verst.engine.Connectivity()
        var consent = false
        val gw = app.verst.engine.ServerPlannerGateway(phone, server, enabled = { false }, online = { net.online }, consent = { consent })
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }, connectivity = net) {}
        flow.serverConsentRead = { consent }
        flow.serverConsentWrite = { consent = true }
        settle()
        flow.openNavigator()
        settle()
        val estimatesBefore = phone.estimates.size
        flow.pick(tbilisi)
        settle()
        assertTrue(flow.destinationAbroad)
        assertTrue(flow.abroadOnServer)
        assertFalse("no plate: the server plans it", flow.abroadBlocked)
        assertEquals("no estimate abroad on the phone", estimatesBefore, phone.estimates.size)
        flow.openInstrumentsFree()
        assertEquals(Route.Instruments, flow.top)

        // no consent yet: the dialog, nothing sent; «Не сейчас» (or back) keeps the Instruments
        flow.go()
        assertTrue(flow.abroadConsentAsk)
        assertEquals(Route.Instruments, flow.top)
        flow.answerAbroadConsent(false)
        assertFalse(flow.abroadConsentAsk)
        assertFalse(consent)
        flow.go()
        assertTrue(flow.abroadConsentAsk)
        assertTrue(flow.back())
        assertFalse(flow.abroadConsentAsk)
        assertEquals(Route.Instruments, flow.top)
        settle(10_000)
        assertTrue(server.inputs.isEmpty())

        // «Согласен»: the consent is kept and the trip is planned on the server
        flow.go()
        flow.answerAbroadConsent(true)
        assertTrue(consent)
        settle(10_000)
        assertEquals(1, server.inputs.size)
        assertTrue(server.inputs.single().contains("44.8271"))
        assertFalse("routing only", server.inputs.single().contains("abroad"))
        assertEquals(0, phone.plans)
        assertTrue(flow.lastPlanRequest!!.abroad)
        assertEquals(Route.Road, flow.top)
        val trip = flow.result!!.trip
        assertTrue(trip.abroad!!.roubleTotalIncomplete)
        assertTrue(trip.daysList.flatMap { it.stops }.any { it.kind == "border" && it.border != null })
        assertTrue(gw.lastPlan!!.server)

        // the border row opens its sheet; back closes it
        val border = trip.daysList.flatMap { it.stops }.first { it.kind == "border" }
        assertTrue(flow.tappable(border))
        flow.openCard(border)
        assertEquals(border, flow.roadBorder)
        assertNull(flow.card)
        assertTrue(flow.back())
        assertNull(flow.roadBorder)
        assertEquals(Route.Road, flow.top)

        // a Russian destination with the phone setting: the phone plans, as before
        while (flow.back()) Unit
        flow.openNavigator()
        flow.pick(yar)
        assertFalse(flow.destinationAbroad)
        flow.openInstrumentsFree()
        flow.go()
        settle(10_000)
        assertEquals(1, phone.plans)
        assertEquals(1, server.inputs.size)
        assertFalse(flow.lastPlanRequest!!.abroad)
    }

    /**
     * Offline (or no server in the build): the plate with the maps hand-off, nothing planned. The server's verdict on
     * a closed border is shown in its own words and goes back to the Navigator; neither it nor a server failure falls
     * back to the phone.
     */
    @Test
    fun aTripAbroadOfflineShowsThePlateAndTheServersVerdictIsShownWithoutThePhone() = runTest {
        val phone = FakeGateway()
        val server = FakeServer()
        val net = app.verst.engine.Connectivity()
        val gw = app.verst.engine.ServerPlannerGateway(phone, server, enabled = { true }, online = { net.online }, consent = { true })
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }, connectivity = net) {}
        flow.serverConsentRead = { true }
        settle()
        flow.openNavigator()
        settle()
        flow.pick(baku)

        // offline: the honest plate, ПОЕХАЛИ does nothing
        flow.setOffline(true)
        assertTrue(flow.abroadBlocked)
        assertFalse(flow.abroadOnServer)
        flow.openInstrumentsFree()
        assertEquals(Route.Navigator, flow.top)
        flow.go()
        settle(10_000)
        assertEquals(Route.Navigator, flow.top)
        assertTrue(server.inputs.isEmpty())
        assertEquals(0, phone.plans)
        // no server in the build: the plate too (its other reason)
        flow.setOffline(false)
        server.present = false
        assertTrue(flow.abroadBlocked)
        assertFalse(flow.serverConfigured())
        server.present = true
        assertTrue(flow.abroadOnServer)

        // Азербайджан: the server's verdict, final — shown as is, «Изменить маршрут» back to the Navigator
        val sentence = "Граница закрыта для легковых до 2 января 2027: сухопутные границы Азербайджана закрыты. Не проверено."
        server.answer = EngineResult.Err(
            app.verst.core.model.dto.EngineErrorDto(
                "INVALID_INPUT", sentence, field = "destination", reason = "border_closed", country = "AZ", until = "2027-01-02T06:00:00+04:00",
            ),
        )
        flow.openInstrumentsFree()
        flow.go()
        settle(10_000)
        assertEquals(Route.Drive, flow.top)
        val err = flow.drive.error!!
        assertEquals("border_closed", err.reason)
        assertEquals(sentence, err.abroadText)
        assertEquals(DriveAction.CHANGE_ROUTE, flow.driveAction(err))
        assertEquals(0, phone.plans)
        flow.onDriveError(flow.driveAction(err), err.abroadText!!)
        assertEquals(Route.Navigator, flow.top)
        assertEquals(sentence, flow.routeError)

        // server trouble for a trip abroad: an error to retry, never a phone plan (it would reject the point)
        flow.pick(tbilisi)
        assertNull(flow.routeError)
        server.answer = null
        flow.openInstrumentsFree()
        flow.go()
        settle(10_000)
        assertEquals("UPSTREAM", flow.drive.error!!.code)
        assertEquals(DriveAction.RETRY, flow.driveAction(flow.drive.error!!))
        assertEquals(2, server.inputs.size)
        assertEquals(0, phone.plans)
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
        // designer В-1: no stress marks, no word cut in half, no lone bracket
        assertEquals("Церковь Илии Пророка.", clean("Це\u0301рковь Или\u0301и Проро\u0301ка", "церковь · Ярославль", "Ярославль"))
        assertEquals(
            "Выставка достижений народного хозяйства … Всероссийский выставочный центр — выставочный комплекс…",
            clean(
                "Вы\u0301ставка достиже\u0301ний наро\u0301дного хозя\u0301йства … Всеросси\u0301йский вы\u0301ставочный центр) — выставочный комплекс в…",
                "выставка · Москва", "Москва",
            ),
        )
        assertEquals(
            "Кремль XV века. Построен при Иване III.",
            clean("Кремль XV века. Построен при Иване III. Стены из красного кирп…", "кремль · Коломна", "Коломна"),
        )
        assertEquals("Усадьба Шереметевых.", clean("усадьба Шереметевых (XVIII век, парк и пруд", "усадьба · Москва", "Москва"))
    }

    /** S4 card chips: raw OSM hours never show in English. */
    @Test
    fun cardHoursAreNeverRawOsm() {
        assertEquals("{daily} 05:00–21:00", app.verst.feature.card.hoursRu("Mo-Su 05:00-21:00"))
        assertEquals("{24}", app.verst.feature.card.hoursRu("24/7"))
        assertEquals("вт–вс 10:00–18:00; пн выходной", app.verst.feature.card.hoursRu("Tu-Su 10:00-18:00; Mo off"))
        assertNull(app.verst.feature.card.hoursRu("sunrise-sunset"))
        assertEquals("10:00–18:00", app.verst.feature.card.hoursRu("10:00–18:00"))
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
        // (a) «Другой вариант» with nothing new: the walk stays, the button is disabled, the stops come back
        flow.otherWalk()
        settle()
        assertEquals(Route.Walk, flow.top)
        assertTrue(flow.walkOtherNone)
        assertNull(flow.walkFew)
        assertNull(flow.cityError)
        flow.otherWalk() // disabled: no request
        settle()
        val before = requests.size
        // (b) a filter change on 5.11 clears the exclusions and rebuilds there after 400 ms
        flow.setCityDuration(120)
        flow.toggleCityInterest("parks")
        settle(300)
        assertEquals("debounced: nothing yet", before, requests.size)
        settle(1_000)
        assertEquals("one rebuild for two quick changes", before + 1, requests.size)
        val last = requests.last()
        assertEquals("filters reach the request", 120, last.durationMin)
        assertTrue("filters reach the request", "parks" in last.interests)
        assertTrue("exclusions survive a filter change: ${last.exclude}", last.exclude.isEmpty())
        assertEquals(Route.Walk, flow.top)
        assertFalse(flow.walkOtherNone)
        assertNull(flow.cityError)
        // the user's custom values persist when the sheet reopens
        flow.back()
        flow.selectCityPreset("custom")
        assertEquals(120, flow.cityDurationMin)
        assertTrue("parks" in flow.cityInterests)
    }

    @Test
    fun walkCrewIsTheWalksOwnAndChildrenNeverBlock() = runTest {
        val root = java.io.File(System.getProperty("verst.repoRoot") ?: "../..")
        fun resp(f: String) = kotlinx.serialization.json.Json.parseToJsonElement(root.resolve("docs/contracts/v2/$f").readText())
            .let { (it as kotlinx.serialization.json.JsonObject)["response"].toString() }
        val p0 = (app.verst.core.model.EngineJson.cityPresets(resp("city_presets.json")) as EngineResult.Ok).value
        // v3 shape: a beer preset (18+) and the dog walk
        val presets = p0.copy(presets = p0.presets.map { if (it.preset == "beer") it.copy(available = true, adultOnly = true) else it }.let { ps ->
            if (ps.any { it.preset == "dog_walk" }) ps else ps + app.verst.core.model.dto.CityPresetDto(preset = "dog_walk", count = 9, defaultDurationMin = 120)
        })
        val oneWalk = (app.verst.core.model.EngineJson.walkRoute(resp("city_route-overview.json")) as EngineResult.Ok).value
        val requests = mutableListOf<app.verst.core.model.WalkRequest>()
        val gw = object : PlannerGateway by FakeGateway() {
            override suspend fun cityPresets(point: GeoPoint) = EngineResult.Ok(presets)
            override suspend fun cityRoute(requestId: String, request: app.verst.core.model.WalkRequest): EngineResult<app.verst.core.model.dto.WalkRouteDto> {
                requests += request
                return EngineResult.Ok(oneWalk)
            }
        }
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.debugLocationAnswered()
        flow.openCity()
        settle()
        // the dog walk shows only with the dog, first
        assertFalse(flow.visibleCityPresets().any { it.preset == "dog_walk" })
        flow.pickCityDog(true)
        assertEquals("dog_walk", flow.visibleCityPresets().first().preset)
        flow.pickCityChildren(1)
        flow.pickCityAdults(3)
        // 18+: the age question only; a child does not block the drink preset
        flow.selectCityPreset("beer")
        assertNotNull(flow.ageGate)
        flow.answerAge(false)
        assertEquals("«Нет» keeps the previous preset", "overview", flow.cityPreset)
        flow.selectCityPreset("beer")
        flow.answerAge(true)
        assertEquals("beer", flow.cityPreset)
        flow.setCityDuration(null)
        flow.buildWalk()
        settle()
        val r = requests.single()
        assertEquals(3, r.adults)
        assertEquals(1, r.children)
        assertTrue(r.dog)
        assertTrue(r.unlimited)
        assertTrue(r.adultConfirmed)
        assertTrue(r.toInputJson().contains("\"durationMin\":null"))
        assertTrue(r.toInputJson().contains("\"dog\":true"))
        // the car crew is untouched
        assertEquals(flow.adults, flow.adults)
    }

    /**
     * M6 `requestKey`: a filter change that leads back to a request the engine already answered with the walk on
     * screen sends nothing; an answer whose key is not the key of the request sent is dropped as stale.
     */
    @Test
    fun walkRequestKeyDropsStaleAnswersAndSkipsSameRequests() = runTest {
        val root = java.io.File(System.getProperty("verst.repoRoot") ?: "../..")
        val resp = { f: String -> app.verst.core.model.EngineJson.json.parseToJsonElement(root.resolve("docs/contracts/v2/$f").readText())
            .let { (it as kotlinx.serialization.json.JsonObject)["response"].toString() } }
        val oneWalk = (app.verst.core.model.EngineJson.walkRoute(resp("city_route-overview.json")) as EngineResult.Ok).value
        val requests = mutableListOf<app.verst.core.model.WalkRequest>()
        var lie = false
        val gw = object : PlannerGateway by FakeGateway() {
            override suspend fun cityRoute(requestId: String, request: app.verst.core.model.WalkRequest): EngineResult<app.verst.core.model.dto.WalkRouteDto> {
                requests += request
                val key = Integer.toHexString(request.toInputJson().hashCode()) + if (lie) "x" else ""
                return EngineResult.Ok(oneWalk.copy(id = "w${requests.size}", requestKey = key))
            }
        }
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.debugLocationAnswered()
        flow.openCity()
        settle()
        flow.buildWalk()
        settle()
        assertEquals(Route.Walk, flow.top)
        val first = flow.walk!!
        flow.pickCityPace("slow")
        settle(300); settle(1_000)
        assertEquals(2, requests.size)
        assertEquals("w2", flow.walk!!.id)
        flow.pickCityPace("normal") // back to the first request: its key is known, but the screen shows w2 → sent
        settle(300); settle(1_000)
        assertEquals(3, requests.size)
        assertEquals(first.requestKey, flow.walk!!.requestKey)
        // the same request again through another filter round trip: the shown walk answers it, nothing is sent
        flow.pickCityBudget(1_000)
        flow.pickCityBudget(null)
        settle(300); settle(1_000)
        assertEquals(3, requests.size)
        // an answer under another key than the request sent is stale: the walk on screen stays
        lie = true
        flow.pickCityPace("slow")
        settle(300); settle(1_000)
        assertEquals(4, requests.size)
        assertEquals(first.requestKey, flow.walk!!.requestKey)
        assertFalse(flow.walkBuilding)
    }

    @Test
    fun notEnoughShowsOnlyTheEnginesSuggestions() = runTest {
        val root = java.io.File(System.getProperty("verst.repoRoot") ?: "../..")
        fun resp(f: String) = kotlinx.serialization.json.Json.parseToJsonElement(root.resolve("docs/contracts/v2/$f").readText())
            .let { (it as kotlinx.serialization.json.JsonObject)["response"].toString() }
        val presets = (app.verst.core.model.EngineJson.cityPresets(resp("city_presets.json")) as EngineResult.Ok).value
        val oneWalk = (app.verst.core.model.EngineJson.walkRoute(resp("city_route-overview.json")) as EngineResult.Ok).value
        // the v3 error as JSON: «6 ч» checked, unlimited checked
        val err = app.verst.core.model.EngineJson.walkRoute(
            """{"ok": false, "error": {"code": "NOT_ENOUGH_POIS", "count": 4, "suggestions": [{"durationMin": 360, "count": 7}, {"durationMin": null, "count": 9}, {"weird": 1}]}}""",
        ) as EngineResult.Err
        assertEquals(2, err.error.walkSuggestions.size)
        assertTrue(err.error.walkSuggestions[1].unlimited)
        val requests = mutableListOf<app.verst.core.model.WalkRequest>()
        val gw = object : PlannerGateway by FakeGateway() {
            override suspend fun cityPresets(point: GeoPoint) = EngineResult.Ok(presets)
            override suspend fun cityRoute(requestId: String, request: app.verst.core.model.WalkRequest): EngineResult<app.verst.core.model.dto.WalkRouteDto> {
                requests += request
                return if (request.durationMin == 480) err else EngineResult.Ok(oneWalk)
            }
        }
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.debugLocationAnswered()
        flow.openCity()
        settle()
        flow.setCityDuration(480)
        flow.buildWalk()
        settle()
        assertEquals(Route.City, flow.top)
        assertEquals("NOT_ENOUGH_POIS", flow.cityError)
        assertEquals(listOf(360, null), flow.walkFew!!.suggestions.map { it.durationMin })
        flow.applyWalkSuggestion(flow.walkFew!!.suggestions[0])
        settle()
        assertEquals(Route.Walk, flow.top)
        assertEquals(360, requests.last().durationMin)
        assertNull(flow.walkFew)
    }

    /**
     * CEO 29.10: `NOT_ENOUGH_POIS` with `reason: "no_data"` (`city_route-error-no-data.json`, «Пивной» in Гороховец):
     * the plate carries the engine's `messageRu` («у нас пока нет данных … это пробел нашей базы»), not «мало мест»,
     * and offers only other walks — never a longer walk, as if the town were small. An unavailable preset with
     * `noData` is listed with its reason; one that is merely unavailable stays hidden.
     */
    @Test
    fun notEnoughNoDataCarriesTheEnginesMessage() = runTest {
        fun resp(f: String) = kotlinx.serialization.json.Json.parseToJsonElement(root.resolve("docs/contracts/v2/$f").readText())
            .let { (it as kotlinx.serialization.json.JsonObject)["response"].toString() }
        val p0 = (EngineJson.cityPresets(resp("city_presets.json")) as EngineResult.Ok).value
        val presets = p0.copy(
            presets = p0.presets.map {
                if (it.preset == "beer") it.copy(available = false, noData = true, noDataRu = "У нас пока нет данных о пивных барах в этом городе — это пробел нашей базы, а не города.") else it
            },
        )
        val err = EngineJson.walkRoute(resp("city_route-error-no-data.json")) as EngineResult.Err
        assertEquals("no_data", err.error.reason)
        assertEquals(listOf("beer"), err.error.noData)
        assertTrue(err.error.isNoData)
        val message = err.error.messageRu!!
        assertTrue(message, message.startsWith("У нас пока нет данных о пивных барах"))
        // the engine's suggestions plus a duration one: a longer walk must not be offered for missing data
        val withDuration = err.copy(
            error = err.error.copy(
                suggestions = kotlinx.serialization.json.buildJsonArray {
                    add(kotlinx.serialization.json.buildJsonObject { put("durationMin", kotlinx.serialization.json.JsonPrimitive(480)); put("count", kotlinx.serialization.json.JsonPrimitive(3)) })
                    err.error.suggestions.orEmpty().forEach { add(it) }
                },
            ),
        )
        val requests = mutableListOf<app.verst.core.model.WalkRequest>()
        val gw = object : PlannerGateway by FakeGateway() {
            override suspend fun cityPresets(point: GeoPoint) = EngineResult.Ok(presets)
            override suspend fun cityRoute(requestId: String, request: app.verst.core.model.WalkRequest): EngineResult<app.verst.core.model.dto.WalkRouteDto> {
                requests += request
                return withDuration
            }
        }
        val flow = VerstFlow(gw, backgroundScope, MemoryTripStore(), io = StandardTestDispatcher(testScheduler), now = { 7 }) {}
        settle()
        flow.debugLocationAnswered()
        flow.openCity()
        settle()
        // «Пивной» has no data here: listed with the engine's reason, not selectable; «По рюмочным» (unavailable,
        // data present) stays hidden
        assertFalse(flow.visibleCityPresets().any { it.preset == "beer" })
        assertEquals(listOf("beer"), flow.noDataCityPresets().map { it.preset })
        assertEquals(presets.presets.first { it.preset == "beer" }.noDataRu, flow.noDataCityPresets().single().noDataRu)
        assertFalse(flow.noDataCityPresets().any { it.preset == "ryumochnye" })
        flow.buildWalk()
        settle()
        assertEquals(1, requests.size)
        assertEquals(Route.City, flow.top)
        assertEquals("NOT_ENOUGH_POIS", flow.cityError)
        val few = flow.walkFew!!
        assertTrue(few.noData)
        assertEquals(message, few.messageRu)
        // only the engine's other walks («Обзорная прогулка», «Свой маршрут»), no «Гулять 8 ч»
        assertEquals(listOf("overview", "custom"), few.suggestions.map { it.preset })
        assertTrue(few.suggestions.none { it.durationMin != null || it.unlimited || it.clearExclude })
    }
}
