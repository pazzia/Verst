package app.verst

import androidx.compose.ui.res.stringResource
import app.verst.core.ui.R as UiR
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import app.verst.feature.report.ReportSheet
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.unit.dp
import app.verst.core.ui.theme.DesignTokens
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import app.verst.feature.common.NaviDialog
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import app.verst.core.model.DefaultOrigin
import app.verst.core.model.EngineJson
import app.verst.core.model.EngineResult
import app.verst.core.model.Mood
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.SuggestionDto
import app.verst.feature.drive.DriveScreen
import app.verst.feature.instruments.InstrumentsActions
import app.verst.feature.instruments.InstrumentsScreen
import app.verst.feature.instruments.InstrumentsUi
import app.verst.feature.navigator.NavigatorScreen
import app.verst.feature.navigator.NavigatorUi
import app.verst.core.model.SavedTrips
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.dto.TripDto
import app.verst.feature.road.RoadActions
import app.verst.feature.road.RoadFocus
import app.verst.nav.GpsState
import app.verst.nav.HandoffTarget
import app.verst.nav.AddressState
import androidx.compose.ui.semantics.SemanticsActions
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import app.verst.core.model.GeoPoint
import app.verst.feature.road.RoadScreen
import app.verst.feature.road.RoadUi
import app.verst.feature.waybill.WaybillActions
import app.verst.feature.waybill.WaybillScreen
import app.verst.feature.waybill.WaybillUi
import app.verst.nav.ReplaceUi
import app.verst.nav.Toast
import app.verst.feature.windshield.WindshieldScreen
import app.verst.feature.windshield.WindshieldUi
import app.verst.nav.DriveAction
import app.verst.nav.DriveUi
import app.verst.nav.Seat
import app.verst.nav.WindshieldData
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * DEV-SLICE screens rendered from fixtures (real engine output: `ready_routes` from Москва and the G02 golden
 * snapshot) → `screenshots/<screen>/<state>@390x844.png` in ci-logs.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(qualifiers = "ru-rRU-w390dp-h844dp-port-xxhdpi")
class ScreensScreenshotTest {
    @get:Rule val compose = createAndroidComposeRule<ComponentActivity>()

    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")

    private val routes = listOf(
        ReadyRouteDto("rr_tula_yasnaya", "Тула · Ясная Поляна", "2 дня · Толстой и пряники", 414, 207, "weekend", true, 2, 2, "t_moscow", "S"),
        ReadyRouteDto("rr_yaroslavl", "Ярославль", "2 дня · по М-8", 526, 263, "weekend", true, 2, 2, "t_moscow", "NE"),
        ReadyRouteDto("rr_golden_ring", "Золотое кольцо", "3 дня · 8 городов · по кругу", 745, 745, "long", true, 3, 4, "t_moscow", "NE"),
    )
    private val yaroslavl = SuggestionDto("city", "Ярославль", "город · Ярославская область", 57.6261, 39.8845, "t_yaroslavl")

    private fun shot(screen: String, state: String, w: Int = 390, h: Int = 844, content: @Composable () -> Unit) {
        compose.setContent(content)
        compose.waitForIdle()
        var bitmap = Screenshot.drawDecorView(compose.activity)
        if (Screenshot.isUniform(bitmap)) bitmap = compose.onRoot().captureToImage().asAndroidBitmap()
        assertEquals(w * 3, bitmap.width)
        Screenshot.write(bitmap, screen, state, w, h)
        // Release review P0-1: no real brand in any rendered text or TalkBack label of any screen state.
        BrandDenyList.allow(compose.activity) // only the hand-off app names (S3-R1)
        val texts = BrandDenyList.texts(compose.onRoot(useUnmergedTree = true).fetchSemanticsNode())
        assertEquals("$screen/$state", emptyList<String>(), texts.flatMap { BrandDenyList.hits(it) })
    }

    @Test
    @Config(qualifiers = "ru-rRU-w360dp-h640dp-port-xxhdpi")
    fun windshieldShort() = shot("windshield", "default", 360, 640) {
        WindshieldScreen(windshield(WindshieldData.Routes(routes)), {}, {}, {}, {})
    }

    @Test
    @Config(qualifiers = "ru-rRU-w360dp-h640dp-port-xxhdpi")
    fun instrumentsShort() = shot("instruments", "default", 360, 640) {
        InstrumentsScreen(
            InstrumentsUi("Москва → Ярославль", "Москва", false, 265, true, listOf(Seat.EMPTY, Seat.EMPTY, Seat.EMPTY), false, 2, 0, 300, 2, null, days = 1, originGen = "Москвы"),
            noActions,
        )
    }

    /** Engine km of the ready routes (golden plans) — the Windshield never shows the template km. */
    private val engineKm by lazy {
        mapOf(
            "rr_golden_ring" to snapshot("G02_golden_ring").km,
            "rr_yaroslavl" to snapshot("G01_msk_yar_round").km,
            "rr_tula_yasnaya" to snapshot("G07_tula_yasnaya").km,
        )
    }

    private fun windshield(data: WindshieldData) =
        WindshieldUi("Москва", data, 0, 2, 1, true, originGen = "Москвы", routeKm = engineKm) // the engine's `reverse` form (OI-39)

    @Test
    fun windshieldDefault() {
        shot("windshield", "default") { WindshieldScreen(windshield(WindshieldData.Routes(routes)), {}, {}, {}, {}) }
        compose.onNodeWithTag("windshield.route.0").assertExists()
        compose.onNodeWithText("РЯДОМ С ВАМИ · ИЗ МОСКВЫ").assertExists()
    }

    @Test
    fun windshieldEstimating() {
        // Manager release return: rows whose estimate is not in yet show a placeholder, never the template km.
        shot("windshield", "estimating") {
            WindshieldScreen(windshield(WindshieldData.Routes(routes)).copy(routeKm = engineKm.filterKeys { it == routes[0].id }), {}, {}, {}, {})
        }
        compose.onNodeWithTag("windshield.route.0.km", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("windshield.route.1.km.pending", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("windshield.route.1.km", useUnmergedTree = true).assertDoesNotExist()
        for (r in routes) compose.onAllNodesWithText(r.kmSign.toString()).assertCountEquals(0)
    }

    @Test
    fun windshieldLoading() = shot("windshield", "loading") { WindshieldScreen(windshield(WindshieldData.Loading), {}, {}, {}, {}) }

    @Test
    fun windshieldEngineFailed() {
        shot("windshield", "engine-failed") { WindshieldScreen(windshield(WindshieldData.Failed(true)), {}, {}, {}, {}) }
        compose.onNodeWithTag("windshield.retry").assertExists()
    }

    @Test
    fun windshieldNoRoutes() = shot("windshield", "no-routes") { WindshieldScreen(windshield(WindshieldData.NoRoutes), {}, {}, {}, {}) }

    private fun navigator(query: String, results: List<SuggestionDto>, dest: SuggestionDto?, error: String? = null) =
        NavigatorUi(DefaultOrigin, false, query, false, results, emptyList(), false, dest, error)

    @Test
    fun navigatorQuery() = shot("navigator", "default-query-yaro") {
        NavigatorScreen(navigator("Яро", listOf(yaroslavl), null).copy(rowKm = mapOf(yaroslavl.pointKey to 263)), {}, {}, {}, {}, {})
    }

    @Test
    fun navigatorPicked() {
        shot("navigator", "destination-picked") {
            NavigatorScreen(navigator("Ярославль", emptyList(), yaroslavl).copy(tripKm = 265), {}, {}, {}, {}, {})
        }
        // The engine's km (estimate = plan), not ≈ 249 / ≈ 312; the copy uses U+00A0 before «км».
        compose.onNodeWithTag("navigator.meta", useUnmergedTree = true).assertTextContains("265", substring = true)
        compose.onNodeWithText("≈", substring = true, useUnmergedTree = true).assertDoesNotExist()
    }

    @Test
    fun navigatorTooShort() = shot("navigator", "error-too-short") {
        NavigatorScreen(navigator("Химки", emptyList(), yaroslavl.copy(name = "Химки")).copy(tripErrorCode = "TOO_SHORT"), {}, {}, {}, {}, {})
    }

    @Test
    fun navigatorLocationRationale() = shot("navigator", "location-rationale") {
        NavigatorScreen(navigator("", emptyList(), null).copy(locationSheet = true), {}, {}, {}, {}, {})
    }

    @Test
    fun navigatorGpsOrigin() = shot("navigator", "gps-origin") {
        NavigatorScreen(navigator("", emptyList(), null).copy(origin = GeoPoint("Ярославль", 57.6261, 39.8845), gps = GpsState.On), {}, {}, {}, {}, {})
    }

    @Test
    fun navigatorNoResults() = shot("navigator", "no-results") {
        NavigatorScreen(navigator("Жжж", emptyList(), null), {}, {}, {}, {}, {})
    }

    private val noActions = object : InstrumentsActions {
        override fun back() {}
        override fun seat(i: Int) {}
        override fun front() {}
        override fun dog() {}
        override fun km(delta: Int) {}
        override fun budget(delta: Int) {}
        override fun mood(m: Mood) {}
        override fun go() {}
    }

    @Test
    fun instrumentsDefault() {
        shot("instruments", "default") {
            InstrumentsScreen(
                InstrumentsUi("Золотое кольцо", "Москва", true, 761, true, listOf(Seat.CHILD, Seat.EMPTY, Seat.ADULT), true, 3, 1, 300, 2, Mood.CALM, days = 3, originGen = "Москвы"),
                noActions,
            )
        }
        compose.onNodeWithText("3 взрослых · 1 ребёнок · собака").assertExists() // Russian plural rules (ru locale)
    }

    @Test
    fun driveProgress() = shot("drive", "t1500") {
        DriveScreen(
            DriveUi(listOf("Прокладываем дорогу", "Делим кольцо на 3 дня по ≈ 250 км", "Ищем отели, куда пустят с собакой"), 0.45f, days = 3),
            "761", { DriveAction.RETRY }, {}, {}, { _, _ -> },
        )
    }

    @Test
    fun driveDone() = shot("drive", "done") {
        DriveScreen(
            DriveUi(listOf("Делим кольцо на 3 дня", "Сверяем часы работы", "Считаем бензин: 8,0 л на 100 км", "Считаем, сколько стоит поездка"), 1f, days = 3, done = true),
            "761", { DriveAction.RETRY }, {}, {}, { _, _ -> },
        )
    }

    @Test
    fun driveErrorUnreachable() {
        shot("drive", "error-unreachable") {
            DriveScreen(DriveUi(error = EngineErrorDto("UNREACHABLE")), "≈ 900", { DriveAction.CHANGE_ROUTE }, {}, {}, { _, _ -> })
        }
        compose.onNodeWithText("Не нашли дорогу на машине до этой точки").assertExists()
        compose.onNodeWithText("Изменить маршрут").assertExists()
    }

    @Test
    fun driveErrorInternal() {
        shot("drive", "error-internal") {
            DriveScreen(DriveUi(error = EngineErrorDto("INTERNAL")), "761", { DriveAction.RETRY }, {}, {}, { _, _ -> })
        }
        compose.onNodeWithText("Попробовать ещё раз").assertExists()
    }

    private fun <T> v2(file: String, decode: (String) -> EngineResult<T>): T {
        val doc = Json.parseToJsonElement(root.resolve("docs/contracts/v2/$file").readText()).jsonObject
        return (decode(doc["response"].toString()) as EngineResult.Ok).value
    }

    private fun v2PlanTrip(file: String): PlanResultDto =
        ((v2(file, EngineJson::planOutcome)) as app.verst.core.model.dto.PlanOutcome.Plan).result

    private fun snapshot(name: String): TripDto = EngineJson.trip(root.resolve("backend/planner/tests/golden/snapshots/$name.json").readText())

    private fun result(name: String): PlanResultDto {
        val text = root.resolve("backend/planner/tests/golden/snapshots/$name.json").readText()
        return PlanResultDto(EngineJson.trip(text), "share", "октябрь", "2026", tripJson = text)
    }

    private val noRoad = object : RoadActions {
        override fun back() {}
        override fun waybill() {}
        override fun save() {}
        override fun share() {}
        override fun replace(stop: StopDto) {}
        override fun pick(altId: String?) {}
        override fun confirmReplace() {}
        override fun closeReplace() {}
        override fun undo() {}
        override fun hotel(stopId: String) {}
    }

    private val noWaybill = object : WaybillActions {
        override fun back() {}
        override fun toggleLine(key: String) {}
        override fun toggleReserve() {}
        override fun save() {}
        override fun share() {}
    }

    @Test
    fun roadG02() {
        shot("road", "g02-top") { RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE"), noRoad) }
        compose.onNodeWithTag("road.total").assertExists()
        compose.onNodeWithTag("road.save").assertExists()
        compose.onNodeWithText("Дорога впереди").assertExists()
    }

    @Test
    fun roadNoLodging() = shot("road", "no-lodging") { RoadScreen(RoadUi(snapshot("G05_edge_no_dog_lodging"), "E"), noRoad) }

    @Test
    fun roadSavedFromTripsWithToast() = shot("road", "saved-toast") {
        RoadScreen(RoadUi(snapshot("G01_msk_yar_round"), "NE", fromSaved = true, saved = true, toast = Toast.Saved), noRoad)
    }

    @Test
    fun roadReplaceSheet() {
        val trip = snapshot("G02_golden_ring")
        val stop = trip.daysList.flatMap { it.stops }.first { it.alternatives.size >= 2 }
        shot("road", "replace-sheet") { RoadScreen(RoadUi(trip, "NE", replace = ReplaceUi(stop, picked = stop.alternatives[1].id)), noRoad) }
        compose.onNodeWithTag("replace.alt.1", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("Варианты в то же время, ± 45 минут").assertExists()
    }

    @Test
    fun roadReplaceSheetNone() {
        val trip = snapshot("G02_golden_ring")
        val stop = trip.daysList.flatMap { it.stops }.firstOrNull { it.replaceable && it.alternatives.isEmpty() && it.alternativesNote != null }
            ?: trip.daysList.flatMap { it.stops }.first { it.replaceable }.let { it.copy(alternatives = emptyList(), alternativesNote = "Других вариантов в это время поблизости нет.") }
        shot("road", "replace-none-note") { RoadScreen(RoadUi(trip, "NE", replace = ReplaceUi(stop)), noRoad) }
    }

    @Test
    fun roadStopMenu() {
        // S3-R1 D-5: long-press menu; the navigator is not installed → Yandex Maps in the browser (allow-listed name).
        val trip = snapshot("G02_golden_ring")
        val stop = trip.daysList.first().stops[1]
        val h = v2<app.verst.core.model.dto.HandoffDto>("handoff-car-from-stop.json", EngineJson::handoff)
        shot("road", "stop-menu") { RoadScreen(RoadUi(trip, "NE", stopMenu = stop, stopHandoff = h, carTarget = HandoffTarget.Browser), noRoad) }
        compose.onNodeWithTag("stopmenu.navigator", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("stopmenu.report", useUnmergedTree = true).assertExists() // components §22 (3)
        compose.onNodeWithText("Открыть Яндекс Карты в браузере").assertExists()
    }

    @Test
    fun roadStopMenuNavigatorOffline() {
        val trip = snapshot("G02_golden_ring")
        val stop = trip.daysList.flatMap { it.stops }.first { it.alternatives.size >= 2 }
        val h = v2<app.verst.core.model.dto.HandoffDto>("handoff-car-from-stop.json", EngineJson::handoff).copy(truncated = true)
        shot("road", "stop-menu-navigator") { RoadScreen(RoadUi(trip, "NE", stopMenu = stop, stopHandoff = h, carTarget = HandoffTarget.Navigator), noRoad) }
        compose.onNodeWithTag("stopmenu.navigator.truncated", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("stopmenu.swap", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("road.day.1.navigator", useUnmergedTree = true).assertExists()
    }

    @Test
    fun roadFocusRestored() {
        // S3-R1: back from the 2nd night's Exit — that row is scrolled into view and highlighted.
        val trip = snapshot("G02_golden_ring")
        val night = trip.daysList.flatMap { it.stops }.filter { it.kind == "overnight" }[1]
        shot("road", "focus-restored") { RoadScreen(RoadUi(trip, "NE", focus = RoadFocus(night.id, null, 1)), noRoad) }
        compose.onNodeWithTag("road.stop.${night.id}", useUnmergedTree = true).assertIsDisplayed()
    }

    @Test
    fun roadDayMenu() {
        val h = v2<app.verst.core.model.dto.HandoffDto>("handoff-car-day.json", EngineJson::handoff)
        shot("road", "day-menu") { RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE", dayMenu = 1, dayHandoff = h, carTarget = HandoffTarget.Maps), noRoad) }
        compose.onNodeWithText("В навигатор: день 1").assertExists()
        compose.onNodeWithText("Открыть в Яндекс Картах").assertExists()
    }

    @Test
    fun roadSyntheticApprox() {
        val r = v2PlanTrip("plan-synthetic.json")
        shot("road", "approx-distances") { RoadScreen(RoadUi(r.trip, "E"), noRoad) }
        compose.onNodeWithTag("road.approx", useUnmergedTree = true).assertExists()
    }

    @Test
    fun roadAboutData() = shot("road", "about-data") { RoadScreen(RoadUi(v2PlanTrip("plan-synthetic.json").trip, "E", aboutData = true), noRoad) }

    @Test
    fun roadRowsTappableOnlyForSightsAndHotels() {
        // DEV-304: a sight row has click semantics, a fuel / rest row has none (M§15.5).
        val trip = snapshot("G02_golden_ring")
        compose.setContent { RoadScreen(RoadUi(trip, "NE"), noRoad) }
        compose.waitForIdle()
        val all = trip.daysList.flatMap { it.stops }
        val sight = all.first { it.kind == "sight" }
        assertTrue(compose.onNodeWithTag("road.stop.${sight.id}").fetchSemanticsNode().config.contains(SemanticsActions.OnClick))
        all.filter { it.kind == "fuel" || it.kind == "rest" || it.kind == "start" || it.kind == "food" }.forEach { s ->
            assertFalse(s.kind, compose.onNodeWithTag("road.stop.${s.id}").fetchSemanticsNode().config.contains(SemanticsActions.OnClick))
        }
    }

    @Test
    fun roadFitBadge() {
        val trip = snapshot("G02_golden_ring")
        val budgeted = trip.copy(cost = trip.cost.copy(budgetRub = 40_000, overBudget = false))
        shot("road", "fit-badge") { RoadScreen(RoadUi(budgeted, "NE"), noRoad) }
        compose.onNodeWithTag("road.fit", useUnmergedTree = true).assertExists()
    }

    @Test
    fun roadTightBadge() {
        val trip = snapshot("G02_golden_ring")
        // S3-QA P2-06: a consistent small overrun — the total is ≈ 3 % over the budget (inside the 5 % tolerance)
        val total = trip.cost.totalRub
        val budget = (total * 0.97 / 100).toInt() * 100
        val tight = trip.copy(
            cost = trip.cost.copy(budgetRub = budget, overBudget = true),
            budgetFit = app.verst.core.model.dto.BudgetFitDto("small_overrun", budget, budget + budget / 20, total + 8_000, total),
        )
        shot("road", "tight-badge") { RoadScreen(RoadUi(tight, "NE"), noRoad) }
        compose.onNodeWithTag("road.tight", useUnmergedTree = true).assertExists()
    }

    @Test
    fun roadMinimumOver() {
        val trip = snapshot("G02_golden_ring")
        val budgeted = trip.copy(cost = trip.cost.copy(budgetRub = 40_000, overBudget = false))
        shot("road", "minimum-over") { RoadScreen(RoadUi(budgeted.copy(cost = budgeted.cost.copy(budgetRub = 30_000, overBudget = true)), "NE", minimum = true), noRoad) }
        compose.onNodeWithTag("road.over", useUnmergedTree = true).assertExists()
    }

    @Test
    fun roadReplaceSheetBreaksBudget() {
        val trip = snapshot("G02_golden_ring")
        val stop = trip.daysList.flatMap { it.stops }.first { it.alternatives.size >= 2 }
        // S3-QA P2-06: only a dearer alternative can break the budget
        val flagged = stop.copy(alternatives = stop.alternatives.mapIndexed { i, a -> if (i == 0) a.copy(breaksBudget = true, deltaRub = maxOf(a.deltaRub, 600)) else a })
        shot("road", "replace-breaks-budget") { RoadScreen(RoadUi(trip, "NE", replace = ReplaceUi(flagged)), noRoad) }
        compose.onNodeWithTag("replace.alt.0.breaks", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("не в бюджете").assertExists()
    }

    // ---------------------------------------------------------------------------------------- 5.9 cards

    private fun card(name: String, kind: String, sign: String, details: app.verst.core.model.dto.PoiDetailsDto?, hotel: app.verst.core.model.dto.HotelOptionDto? = null) =
        app.verst.feature.card.CardUi(name, sign, kind = kind, details = details, hotel = hotel)

    private val noCard = object : app.verst.feature.card.CardActions {
        override fun close() = Unit
    }

    @Composable
    private fun CardOverRoad(ui: app.verst.feature.card.CardUi) {
        Box(Modifier.fillMaxSize()) {
            RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE", card = ui), object : RoadActions by noRoad {
                override fun card(): app.verst.feature.card.CardActions = noCard
            })
        }
    }

    @Test
    fun cardSight() {
        val d = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-sight.json", EngineJson::poiDetails)
        shot("card", "sight-placeholder") { CardOverRoad(card(d.nameRu, "sight", "tourist", d)) }
        compose.onNodeWithText("цена примерная", substring = true).assertExists() // the deck uses NBSPs in the ticket line
    }

    @Test
    fun cardHotelArea() {
        val d = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-hotel.json", EngineJson::poiDetails)
        val night = snapshot("G02_golden_ring").daysList.flatMap { it.stops }.first { it.kind == "overnight" && it.hotelOptions.isNotEmpty() }
        shot("card", "hotel-area") { CardOverRoad(card(d.nameRu, "hotel", "hotel", d, night.hotelOptions.first())) }
        compose.onNodeWithTag("card.fictional", useUnmergedTree = true).assertExists()
        // S3-QA P1-05: while the frame is a placeholder (Robolectric never loads the URL) — no credit, the short note,
        // no engine «Демо: вымышленная гостиница» line; the mini sign sits in the title row (§19 C2)
        compose.onNodeWithText("Фото района: Ярославль · Wikimedia Commons").assertDoesNotExist()
        compose.onNodeWithText("Гостиница в демо-сборке вымышленная").assertExists()
        compose.onNodeWithText("Демо: вымышленная гостиница").assertDoesNotExist()
        compose.onNodeWithTag("card.sign", useUnmergedTree = true).assertExists()
    }

    @Test
    fun cardBar() {
        val d = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-bar.json", EngineJson::poiDetails)
        shot("card", "bar") { CardOverRoad(card(d.nameRu, "bar", "service", d)) }
        compose.onNodeWithTag("card.osm", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("card.report", useUnmergedTree = true).assertExists()
    }

    @Test
    fun cardFixtureSight() {
        val d = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-fixture-sight.json", EngineJson::poiDetails)
        shot("card", "fixture-sight") { CardOverRoad(card(d.nameRu, "sight", "tourist", d)) }
    }

    @Test
    fun photoFrameStates() {
        // DEV-300: loading, loaded (a fake image, crop and contain), error and offline — the frame never changes size.
        val fake = androidx.compose.ui.graphics.painter.ColorPainter(androidx.compose.ui.graphics.Color(0xFF5A7C99))
        shot("card", "photo-states") {
            androidx.compose.foundation.layout.Column(
                Modifier.fillMaxSize().background(DesignTokens.color.dash.raised).padding(20.dp),
                verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp),
            ) {
                val ph = app.verst.feature.card.Placeholder.MUSEUM
                app.verst.feature.card.PhotoFrameContent(app.verst.feature.card.PhotoState.Loading, ph, null, false, "loading", Modifier.fillMaxWidth(0.42f))
                app.verst.feature.card.PhotoFrameContent(app.verst.feature.card.PhotoState.Loaded(fake, contain = false, portrait = false), ph, "Фото: Wikimedia Commons · Анна П. · CC BY-SA 4.0", false, "loaded", Modifier.fillMaxWidth(0.42f))
                app.verst.feature.card.PhotoFrameContent(app.verst.feature.card.PhotoState.Error, app.verst.feature.card.Placeholder.CHURCH, null, false, "error", Modifier.fillMaxWidth(0.42f))
                app.verst.feature.card.PhotoFrameContent(app.verst.feature.card.PhotoState.Offline, app.verst.feature.card.Placeholder.PARK, null, false, "offline", Modifier.fillMaxWidth(0.42f))
                app.verst.feature.card.PhotoFrameContent(app.verst.feature.card.PhotoState.Loaded(fake, contain = false, portrait = false), app.verst.feature.card.Placeholder.CITY, "Фото района: Ярославль · Wikimedia Commons", true, "area", Modifier.fillMaxWidth(0.42f))
            }
        }
        compose.onNodeWithTag("photo.offline", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("photo.error", useUnmergedTree = true).assertExists()
        assertTrue(app.verst.feature.card.containFor(200, 150, false))
        assertTrue(app.verst.feature.card.containFor(6000, 1200, false))
        assertTrue(app.verst.feature.card.containFor(800, 600, true))
        assertFalse(app.verst.feature.card.containFor(4000, 3000, false))
    }

    // ---------------------------------------------------------------------------------------- 5.8 budget

    @Test
    fun noFitScreen() {
        val trip = (Json.parseToJsonElement(root.resolve("docs/contracts/v2/plan-synthetic.json").readText()).jsonObject["response"]!!.jsonObject["result"]!!.jsonObject)["trip"].toString()
        val env = """{"ok": true, "result": {"outcome": "no_fit", "budgetRub": 30000, "allowedRub": 31500,
            "minimum": {"totalRub": 41200, "levers": [], "trip": $trip, "shareText": "s"},
            "options": [{"kind": "shorten", "days": 2, "totalRub": 29700, "readyRouteId": "rr_golden_ring_short", "titleRu": "Золотое кольцо · коротко"},
              {"kind": "cheaper_route", "totalRub": 24300, "readyRouteId": "rr_yaroslavl", "titleRu": "Ярославль"},
              {"kind": "raise_budget", "budgetRub": 42000}],
            "textRu": "В 30 000 ₽ эта поездка не помещается даже в самом экономном варианте — минимум ≈ 41 200 ₽."}, "ms": 1}"""
        val nf = ((EngineJson.planOutcome(env) as EngineResult.Ok).value as app.verst.core.model.dto.PlanOutcome.NoFit).noFit
        shot("budget", "no-fit") {
            app.verst.feature.budget.NoFitScreen(nf, object : app.verst.feature.budget.NoFitActions {
                override fun back() = Unit
                override fun option(o: app.verst.core.model.dto.BudgetOptionDto) = Unit
                override fun showMinimum() = Unit
            })
        }
        compose.onNodeWithText("Не помещается в бюджет").assertExists()
        compose.onNodeWithTag("nofit.option.2", useUnmergedTree = true).assertExists()
    }

    @Test
    fun waybillFitted() {
        val trip = snapshot("G02_golden_ring")
        val fitted = trip.copy(
            cost = trip.cost.copy(budgetRub = 35_000, remainingRub = 35_000 - trip.cost.totalRub, overBudget = false),
            budgetFit = app.verst.core.model.dto.BudgetFitDto(
                "fits", 35_000, 36_700, trip.cost.totalRub + 10_700, trip.cost.totalRub,
                listOf(app.verst.core.model.dto.BudgetLeverDto("lodging_cheap", 6_000), app.verst.core.model.dto.BudgetLeverDto("food_economy", 4_700)),
            ),
        )
        shot("waybill", "fitted") { WaybillScreen(waybill(fitted), noWaybill) }
        compose.onNodeWithTag("waybill.levers", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("дешевле ночёвки").assertExists()
    }

    @Test
    fun waybillOverRefit() {
        val trip = snapshot("G02_golden_ring")
        val over = trip.copy(cost = trip.cost.copy(budgetRub = 30_000, remainingRub = 30_000 - trip.cost.totalRub, overBudget = true))
        shot("waybill", "over-refit") { WaybillScreen(waybill(over).copy(minimum = true), noWaybill) }
        compose.onNodeWithTag("waybill.refit", useUnmergedTree = true).assertExists()
    }

    // ---------------------------------------------------------------------------------------- 5.10 / 5.11 city

    private val noCity = object : app.verst.feature.city.CityActions {
        override fun back() = Unit
        override fun changeStart() = Unit
        override fun preset(p: String) = Unit
        override fun go() = Unit
        override fun duration(min: Int) = Unit
        override fun interest(i: String) = Unit
        override fun pace(p: String) = Unit
        override fun budget(rub: Int?) = Unit
        override fun toggleReturn() = Unit
        override fun closeCustom() = Unit
        override fun buildCustom() = Unit
        override fun age(yes: Boolean) = Unit
        override fun longer() = Unit
        override fun otherPreset() = Unit
    }

    private fun cityUi(error: String? = null, custom: Boolean = false, age: Boolean = false, building: Boolean = false, children: Boolean = false): app.verst.feature.city.CityUi {
        val presets = v2<app.verst.core.model.dto.CityPresetsDto>("city_presets.json", EngineJson::cityPresets)
        return app.verst.feature.city.CityUi(
            if (error == "NO_CITY") null else presets.town?.name, if (error == "NO_CITY") "Толбухино" else "Советская пл., 1", true, if (error == "NO_CITY") emptyList() else presets.presets, false, error, "overview",
            240, listOf("parks", "views"), "normal", null, true, custom, age, building, children, "11:00",
        )
    }

    @Test
    fun cityPresets() {
        shot("city", "presets") { app.verst.feature.city.CityScreen(cityUi(), noCity) }
        compose.onNodeWithTag("city.preset.overview", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("city.preset.beer", useUnmergedTree = true).assertDoesNotExist() // `available: false` is hidden
    }

    @Test
    fun cityKidsBlocked() = shot("city", "kids-blocked") { app.verst.feature.city.CityScreen(cityUi(children = true), noCity) }

    @Test
    fun cityCustomSheet() = shot("city", "custom-sheet") { app.verst.feature.city.CityScreen(cityUi(custom = true), noCity) }

    @Test
    fun cityAgeGate() {
        shot("city", "age-gate") { app.verst.feature.city.CityScreen(cityUi(age = true), noCity) }
        compose.onNodeWithText("Маршрут для взрослых").assertExists()
    }

    @Test
    fun cityBuilding() = shot("city", "building") { app.verst.feature.city.CityScreen(cityUi(building = true), noCity) }

    @Test
    fun cityNoCity() = shot("city", "no-city") { app.verst.feature.city.CityScreen(cityUi(error = "NO_CITY"), noCity) }

    @Test
    fun cityNotEnough() = shot("city", "not-enough") { app.verst.feature.city.CityScreen(cityUi(error = "NOT_ENOUGH_POIS"), noCity) }

    private val noWalk = object : app.verst.feature.city.WalkActions {
        override fun back() = Unit
        override fun save() = Unit
        override fun share() = Unit
        override fun stop(s: app.verst.core.model.dto.WalkStopDto) = Unit
        override fun handoff(part: Int) = Unit
        override fun other() = Unit
        override fun card(): app.verst.feature.card.CardActions = noCard
    }

    private fun walkShot(file: String, state: String) {
        val w = v2<app.verst.core.model.dto.WalkRouteDto>(file, EngineJson::walkRoute)
        val h = v2<app.verst.core.model.dto.HandoffDto>("handoff-walk.json", EngineJson::handoff)
        shot("walk", state) { app.verst.feature.city.WalkScreen(app.verst.feature.city.WalkUi(w, h, HandoffTarget.Browser, saved = false, building = false), noWalk) }
        compose.onNodeWithTag("walk.handoff", useUnmergedTree = true).assertExists()
    }

    @Test
    fun walkOverview() = walkShot("city_route-overview.json", "overview")

    @Test
    fun walkFreeFooter() {
        // S3-QA P1-03: total 0 ₽ → «Бесплатно · вход везде свободный», no per-person line
        val w = v2<app.verst.core.model.dto.WalkRouteDto>("city_route-overview.json", EngineJson::walkRoute)
        val free = w.copy(cost = w.cost.copy(totalRub = 0))
        shot("walk", "free") { app.verst.feature.city.WalkScreen(app.verst.feature.city.WalkUi(free, null, HandoffTarget.Browser, saved = false, building = false), noWalk) }
        compose.onNodeWithTag("walk.free", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("вход везде свободный").assertExists()
    }

    @Test
    fun walkShorterThanAsked() {
        // S3-QA P1-02: 4 ч asked, 2,5 ч built → the note; «≈ 2,4 км» without a trailing zero rule check
        walkShot("city_route-ryumochnye.json", "shorter")
        compose.onNodeWithTag("walk.shorter", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("вместо", substring = true).assertExists() // the deck string uses NBSPs before «ч»
    }

    @Test
    fun roadReportSheet() {
        // D-7 over Road ahead: a reason picked, a comment, «ОТПРАВИТЬ» enabled
        val trip = snapshot("G02_golden_ring")
        val stop = trip.daysList.flatMap { it.stops }.first { it.kind == "sight" }
        shot("road", "report") {
            androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxSize()) {
                val h = maxHeight
                Box(Modifier.fillMaxSize()) {
                    RoadScreen(RoadUi(trip, "NE"), noRoad)
                    ReportSheet(
                        app.verst.feature.report.ReportUi(stop.name, "price", "Билет уже 600 ₽"), h,
                        object : app.verst.feature.report.ReportActions {
                            override fun close() = Unit
                            override fun reason(r: String) = Unit
                            override fun comment(t: String) = Unit
                            override fun send() = Unit
                        },
                    )
                }
            }
        }
        compose.onNodeWithTag("report.send", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("Что не так с местом?").assertExists()
    }

    @Test
    fun roadReportSheetEmpty() {
        val trip = snapshot("G02_golden_ring")
        shot("road", "report-empty") {
            androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxSize()) {
                val h = maxHeight
                Box(Modifier.fillMaxSize()) {
                    RoadScreen(RoadUi(trip, "NE"), noRoad)
                    ReportSheet(
                        app.verst.feature.report.ReportUi("Ростовский кремль"), h,
                        object : app.verst.feature.report.ReportActions {
                            override fun close() = Unit
                            override fun reason(r: String) = Unit
                            override fun comment(t: String) = Unit
                            override fun send() = Unit
                        },
                    )
                }
            }
        }
        compose.onNodeWithTag("report.send").assertIsNotEnabled()
    }

    @Test
    fun walkMuseumsSpb() = walkShot("city_route-museums-spb.json", "museums-spb")

    @Test
    fun walkCustom() = walkShot("city_route-custom.json", "custom")

    @Test
    fun walkRyumochnye() {
        walkShot("city_route-ryumochnye.json", "ryumochnye")
        compose.onNodeWithTag("walk.responsible", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("Пейте умеренно, чередуйте с водой и едой. За руль — только трезвым.").assertExists()
    }

    // ---------------------------------------------------------------------------------------- 5.12 location / addresses

    @Test
    fun navigatorAddressResults() {
        val rows = listOf(SuggestionDto("address", "Советская улица, 1", "Ярославль", 57.6266, 39.8938))
        shot("navigator", "address-results") {
            NavigatorScreen(navigator("Советская 1", emptyList(), null).copy(addressQuery = true, addressState = AddressState.Done, addressResults = rows), {}, {}, {}, {}, {})
        }
        compose.onNodeWithTag("address.attribution", useUnmergedTree = true).assertExists()
    }

    @Test
    fun navigatorAddressFind() = shot("navigator", "address-find") {
        NavigatorScreen(navigator("Советская 1", emptyList(), null).copy(addressQuery = true), {}, {}, {}, {}, {})
    }

    @Test
    fun navigatorAddressOffline() = shot("navigator", "address-offline") {
        NavigatorScreen(navigator("Советская 1", emptyList(), null).copy(addressQuery = true, online = false), {}, {}, {}, {}, {})
    }

    @Test
    fun navigatorOutsideRussia() = shot("navigator", "outside-russia") {
        NavigatorScreen(navigator("", emptyList(), null).copy(outsideRussia = true), {}, {}, {}, {}, {})
    }

    @Test
    fun navigatorGpsApprox() = shot("navigator", "gps-approx") {
        NavigatorScreen(
            navigator("", emptyList(), null).copy(origin = GeoPoint("Ярославль", 57.6261, 39.8845), gps = GpsState.On, originFromGps = true, gpsApprox = true, originAddress = "ул. Советская, 1"),
            {}, {}, {}, {}, {},
        )
    }

    @Test
    fun roadReplacedToast() = shot("road", "replaced-toast") {
        RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE", toast = Toast.Replaced(33_800), canUndo = true), noRoad)
    }

    private fun waybill(trip: TripDto, expanded: String? = null, saved: Boolean = false) =
        WaybillUi(trip, 1, saved, expanded, monthRu = "октябрь", year = "2026")

    @Test
    fun waybillDefault() {
        shot("waybill", "default") { WaybillScreen(waybill(snapshot("G02_golden_ring")), noWaybill) }
        compose.onNodeWithTag("waybill.line.fuel", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("ПУТЕВОЙ ЛИСТ").assertExists()
    }

    @Test
    @Config(qualifiers = "ru-rRU-w360dp-h640dp-port-xxhdpi")
    fun waybillShort() = shot("waybill", "default", 360, 640) { WaybillScreen(waybill(snapshot("G02_golden_ring")), noWaybill) }

    @Test
    fun waybillExpandedFuel() = shot("waybill", "line-expanded") {
        WaybillScreen(waybill(snapshot("G02_golden_ring"), expanded = "fuel"), noWaybill)
    }

    @Test
    fun waybillReserveOffOverBudget() {
        val t = snapshot("G02_golden_ring")
        val c = t.cost
        val reserve = c.lines.first { it.key == "reserve" }.rub
        val total = c.totalRub - reserve
        val off = t.copy(cost = c.copy(reserveOn = false, totalRub = total, budgetRub = 30_000, remainingRub = 30_000 - total, overBudget = 30_000 < total))
        shot("waybill", "reserve-off-over-budget") { WaybillScreen(waybill(off, saved = true), noWaybill) }
        compose.onNodeWithText("Перерасход").assertExists()
    }

    @Test
    fun waybillBudgetNone() {
        val t = snapshot("G01_msk_yar_round")
        shot("waybill", "budget-none") { WaybillScreen(waybill(t.copy(cost = t.cost.copy(budgetRub = null, remainingRub = null, overBudget = false))), noWaybill) }
    }

    private fun savedTrips() = listOf(
        SavedTrips.entry("a", 1, result("G02_golden_ring"), "NE"),
        SavedTrips.entry("b", 2, result("G01_msk_yar_round"), "NE"),
    )

    @Test
    fun windshieldWithTrips() {
        shot("windshield", "saved-trips") { WindshieldScreen(windshield(WindshieldData.Routes(routes)).copy(trips = savedTrips()), {}, {}, {}, {}) }
        compose.onNodeWithTag("windshield.trips").assertExists()
    }

    @Test
    @Config(qualifiers = "ru-rRU-w360dp-h640dp-port-xxhdpi")
    fun windshieldWithTripsShort() = shot("windshield", "saved-trips", 360, 640) {
        WindshieldScreen(windshield(WindshieldData.Routes(routes)).copy(trips = savedTrips()), {}, {}, {}, {})
    }

    @Test
    fun windshieldTripsSheet() {
        shot("windshield", "trips-sheet") {
            WindshieldScreen(windshield(WindshieldData.Routes(routes)).copy(trips = savedTrips(), tripsSheet = true), {}, {}, {}, {})
        }
        compose.onNodeWithTag("trips.row.1", useUnmergedTree = true).assertExists()
    }

    private val noExit = object : app.verst.feature.exit.ExitActions {
        override fun back() {}
        override fun select(placeId: String) {}
        override fun book() {}
        override fun closePartner() {}
        override fun answer(booked: Boolean) {}
        override fun needInternet() {}
        override fun undoBooking() {}
    }

    private fun exitUi(bookedFirst: Boolean = false, offline: Boolean = false, partner: Boolean = false, dialog: Boolean = false, trip: TripDto = snapshot("G02_golden_ring")): app.verst.feature.exit.ExitUi {
        val nights = trip.daysList.flatMap { it.stops }.filter { it.kind == "overnight" }
        val stop = nights.first()
        return app.verst.feature.exit.ExitUi(
            trip, stop, 1, nights.size, if (bookedFirst) stop.selectedHotelId else null, offline, "Ярославле", partner, dialog,
        )
    }

    @Test
    fun exitDefault() {
        shot("exit", "default") { app.verst.feature.exit.ExitScreen(exitUi(), noExit) }
        compose.onNodeWithTag("exit.option.0", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("exit.sign", useUnmergedTree = true).assertExists()
    }

    @Test
    @Config(qualifiers = "ru-rRU-w360dp-h640dp-port-xxhdpi")
    fun exitShort() = shot("exit", "default", 360, 640) { app.verst.feature.exit.ExitScreen(exitUi(), noExit) }

    @Test
    fun exitOffline() {
        shot("exit", "offline") { app.verst.feature.exit.ExitScreen(exitUi(offline = true), noExit) }
        compose.onNodeWithTag("exit.offline", useUnmergedTree = true).assertExists()
    }

    @Test
    fun exitMockPartner() {
        shot("exit", "mock-partner-sheet") { app.verst.feature.exit.ExitScreen(exitUi(partner = true), noExit) }
        compose.onNodeWithTag("partner.badge", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("Яндекс", substring = true, useUnmergedTree = true).assertDoesNotExist() // OI-40
    }

    @Test
    fun exitBookedDialog() = shot("exit", "booked-dialog") { app.verst.feature.exit.ExitScreen(exitUi(dialog = true), noExit) }

    @Test
    fun exitBooked() {
        shot("exit", "booked") { app.verst.feature.exit.ExitScreen(exitUi(bookedFirst = true), noExit) }
        compose.onNodeWithText("Открыть бронирование", useUnmergedTree = true).assertExists()
    }

    @Test
    fun exitNoLodging() {
        val t = snapshot("G05_edge_no_dog_lodging")
        shot("exit", "no-lodging") { app.verst.feature.exit.ExitScreen(exitUi(trip = t), noExit) }
    }

    @Test
    fun roadBookedRow() = shot("road", "booked-row") {
        val t = snapshot("G02_golden_ring")
        val night = t.daysList.flatMap { it.stops }.first { it.kind == "overnight" }
        RoadScreen(RoadUi(t, "NE", booked = setOf(night.id)), noRoad)
    }

    @Test
    fun waybillStamp() = shot("waybill", "stamp-final") { WaybillScreen(waybill(snapshot("G02_golden_ring")).copy(stamp = false), noWaybill) }

    @Test
    fun tripsDeleteDialog() = shot("windshield", "trips-delete-dialog") {
        Box(Modifier.fillMaxSize()) {
            WindshieldScreen(windshield(WindshieldData.Routes(routes)).copy(trips = savedTrips(), tripsSheet = true), {}, {}, {}, {})
            NaviDialog("Удалить поездку «Золотое кольцо»?", "Она пропадёт с этого телефона", "Удалить", "Оставить", "delete", {}, {})
        }
    }

    @Test
    fun limitDialog() = shot("road", "limit-dialog") {
        Box(Modifier.fillMaxSize()) {
            RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE"), noRoad)
            NaviDialog(
                stringResource(UiR.string.common_storage_full_title), stringResource(UiR.string.common_storage_full_body),
                stringResource(UiR.string.common_storage_full_open), stringResource(UiR.string.common_dialog_cancel), "limit", {}, {},
            ) // the very keys MainActivity uses
        }
    }

    @Test
    fun engineEnvelopeErrorsNeverThrow() {
        assertEquals("INTERNAL", (EngineJson.planResult("") as EngineResult.Err).error.code)
    }
}
