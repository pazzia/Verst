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
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotSelected
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.assertIsOn
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performSemanticsAction
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
import app.verst.feature.road.ParkingTotal
import app.verst.feature.road.RoadActions
import app.verst.feature.road.parkingOf
import app.verst.feature.road.parkingTotal
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

    /**
     * Engine km of the ready routes — the Windshield never shows the template km. Each is the engine's `estimate` of
     * that ready route for one crew (`docs/contracts/v2/estimate-ready-*.json`, G02's crew): Ярославль is the ready
     * route `rr_yaroslavl` (536 km), not the free trip G01 (542 km) the fixture used to take.
     */
    private val engineKm by lazy {
        mapOf(
            "rr_golden_ring" to v2("estimate-ready-golden-ring.json", EngineJson::estimate).km,
            "rr_yaroslavl" to v2("estimate-ready-yaroslavl.json", EngineJson::estimate).km,
            "rr_tula_yasnaya" to v2("estimate-ready-tula.json", EngineJson::estimate).km,
        )
    }

    @Test
    fun readyRouteKmIsTheReadyRoutes() {
        assertEquals(536, engineKm.getValue("rr_yaroslavl"))
        assertEquals(snapshot("G02_golden_ring").km, engineKm.getValue("rr_golden_ring")) // same input as G02
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

    /** CEO 29.10: КУДА abroad — the honest plate instead of a plan, its button opens the road in the maps app. */
    @Test
    fun navigatorAbroadPlate() {
        val prague = SuggestionDto("address", "Прага", "Прага · Чехия", 50.0874, 14.4213, countryCode = "cz")
        var maps = 0
        shot("navigator", "abroad") {
            NavigatorScreen(navigator("Прага", emptyList(), prague).copy(abroad = true), {}, {}, {}, {}, {}, onAbroadMaps = { maps++ })
        }
        compose.onNodeWithTag("navigator.abroad", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("Маршруты за границу Верста пока не строит", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("смету мы считаем только по России", substring = true, useUnmergedTree = true).assertExists()
        compose.onNodeWithText("«Прага»", substring = true, useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("navigator.abroad.maps").performScrollTo().performClick()
        compose.waitForIdle()
        assertEquals(1, maps)
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

    /** 5.3 §9 (S4): the three MoodCards, fun selected with a child and the dog → the yellow crew line (tall window). */
    @Test
    @Config(qualifiers = "ru-rRU-w390dp-h1060dp-port-xxhdpi")
    fun instrumentsFunMoodWithChildAndDog() {
        shot("instruments", "s4-mood-fun-child-dog", 390, 1060) {
            InstrumentsScreen(
                InstrumentsUi("Золотое кольцо", "Москва", true, 761, true, listOf(Seat.CHILD, Seat.EMPTY, Seat.ADULT), true, 3, 1, 300, 2, Mood.FUN, days = 3, originGen = "Москвы"),
                noActions,
            )
        }
        compose.onNodeWithTag("instruments.mood.crew", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("Под ваш экипаж", substring = true).assertExists()
        compose.onNodeWithTag("instruments.mood.fun").assertIsSelected()
        compose.onNodeWithTag("instruments.mood.calm").assertIsNotSelected()
        compose.onNodeWithText("весело и познавательно", substring = true).assertExists() // the caption meta suffix
    }

    @Test
    fun instrumentsJustDriveAdults() {
        shot("instruments", "s4-mood-just-drive") {
            InstrumentsScreen(
                InstrumentsUi("Москва → Казань", "Москва", false, 820, true, listOf(Seat.EMPTY, Seat.EMPTY, Seat.EMPTY), false, 2, 0, 500, 2, Mood.JUST_DRIVE, days = 2, originGen = "Москвы"),
                noActions,
            )
        }
        compose.onNodeWithTag("instruments.mood.crew", useUnmergedTree = true).assertDoesNotExist()
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
        // ADR-0019 E-6: G02's crew has a dog and nobody checked whether the first sight lets dogs in
        compose.onNodeWithTag("road.unknown.d1s02", useUnmergedTree = true).assertExists()
    }

    /** ADR-0019 E-2: a sight whose ticket price is unknown is never «вход свободный» on its row. */
    @Test
    fun roadUnknownTicket() {
        val t = snapshot("G02_golden_ring")
        val trip = t.copy(daysList = t.daysList.map { d ->
            d.copy(stops = d.stops.map { s -> if (s.id == "d1s02") s.copy(costRub = 0, unknownFacts = s.unknownFacts + "ticket") else s })
        })
        shot("road", "unknown-ticket") { RoadScreen(RoadUi(trip, "NE"), noRoad) }
        compose.onNodeWithText("цена билета неизвестна", useUnmergedTree = true).assertExists()
    }

    /**
     * S4 fixture (API v3 shape, the engine milestone with tags/parking is pending): G02 with `kmDriven`, whitelist
     * kinds on sights, one «Разминка» fun stop, one open-data sight, zone parking on sights (one unknown), free
     * parking at rest areas / nights, rest amenities, and the «Парковки» line.
     */
    private fun s4Trip(): TripDto {
        val t = snapshot("G02_golden_ring")
        var driven = 0
        var sights = 0
        val kinds = listOf("monastery", "kremlin", "museum", "park", "nature", "viewpoint")
        val days = t.daysList.map { d ->
            d.copy(stops = d.stops.map { st ->
                driven += st.kmFromPrev
                val sight = st.kind == "sight"
                val k = if (sight) sights++ else -1
                st.copy(
                    kmDriven = driven, kmLeft = (t.km - driven).coerceAtLeast(0),
                    poiKind = if (sight) kinds[k % kinds.size] else null,
                    funFor = if (k == 1) listOf("child") else emptyList(),
                    dwellMin = if (k == 1) 30 else st.dwellMin,
                    verified = if (k == 2) false else st.verified,
                    parking = when {
                        sight && k == 3 -> null
                        sight -> app.verst.core.model.dto.ParkingDto(rubPerHour = 150, rub = 300, source = "zone", hours = 2.0, zoneRu = "платная зона", whereRu = "у входа и на соседних улицах")
                        st.kind == "rest" -> app.verst.core.model.dto.ParkingDto(rub = 0, source = "free", freeRu = "площадка отдыха у трассы")
                        // M9: cafés carry an object (unknown here: «P ?»); hotels carry none (a hotel fact)
                        st.kind == "food" -> app.verst.core.model.dto.ParkingDto(rub = null, source = "unknown")
                        else -> null
                    },
                    amenities = if (st.kind == "rest" || st.kind == "fuel") listOf("toilets", "tables", "shelter") else emptyList(), // G02 has no rest areas
                )
            })
        }
        val parkingRub = days.sumOf { d -> d.stops.sumOf { it.parking?.rub ?: 0 } }
        val lines = t.cost.lines.filter { it.key != "reserve" } +
            app.verst.core.model.dto.CostLineDto("parking", "Парковки", parkingRub, "${days.sumOf { d -> d.stops.count { it.parking?.rubPerHour != null } }} стоянки", unknownCount = days.sumOf { d -> d.stops.count { it.kind in setOf("sight", "food", "rest", "overnight") && it.parking == null } }) +
            t.cost.lines.filter { it.key == "reserve" }
        return t.copy(daysList = days, cost = t.cost.copy(lines = lines))
    }

    /** 5.6 §9 (S4) «Парковки» expanded: paid rows, the free ones in one 0 row, the unknown ones with «?». */
    @Test
    @Config(qualifiers = "ru-rRU-w390dp-h1200dp-port-xxhdpi")
    fun waybillS4Parking() {
        val trip = s4Trip()
        shot("waybill", "s4-parking", 390, 1200) { WaybillScreen(WaybillUi(trip, 1, false, "parking"), noWaybill) }
        compose.onNodeWithTag("waybill.line.parking").assertExists()
        compose.onNodeWithTag("waybill.parking.unknown", useUnmergedTree = true).assertExists()
        assertTrue(compose.onAllNodesWithTag("waybill.breakdown.parking.0", useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty())
        // parity: the line = Σ known stays = the Road-ahead footer
        val known = trip.daysList.flatMap { it.stops }.sumOf { it.parking?.rub ?: 0 }
        assertEquals(known, trip.cost.lines.first { it.key == "parking" }.rub)
    }

    /**
     * S4-RELEASE (Manager, Golden Ring shot 124: «P ?» on Ростовский кремль but «из них парковки бесплатно»): while any
     * stop's parking is unknown no total claims free or exact — footer, day headers and the Waybill line.
     */
    @Test
    fun parkingTotalRuleNeverClaimsFreeOrExactWithUnknowns() {
        assertEquals(ParkingTotal.FREE, parkingTotal(0, 0, 3))
        assertEquals(ParkingTotal.SUM, parkingTotal(380, 0, 2))
        assertEquals(ParkingTotal.SUM_PLUS_UNKNOWN, parkingTotal(380, 1, 2))
        assertEquals(ParkingTotal.FREE_PLUS_UNKNOWN, parkingTotal(0, 2, 2))
        assertEquals(ParkingTotal.UNKNOWN, parkingTotal(0, 1, 0))
        for (rub in listOf(0, 80, 380)) for (unknown in 1..3) for (known in 0..3) {
            val t = parkingTotal(rub, unknown, known)
            assertTrue("$rub/$unknown/$known → $t", t != ParkingTotal.FREE && t != ParkingTotal.SUM)
        }
    }

    /** The Golden Ring case: the known stays are free, two stops unknown → «бесплатно + ?» / «0 + ?», never «бесплатно». */
    @Test
    @Config(qualifiers = "ru-rRU-w390dp-h1200dp-port-xxhdpi")
    fun parkingFreePlusUnknownOnRoadAndWaybill() {
        val base = s4Trip()
        val days = base.daysList.map { d ->
            d.copy(stops = d.stops.map { st ->
                val p = st.parking
                if (p != null && p.known) st.copy(parking = app.verst.core.model.dto.ParkingDto(rub = 0, source = "free", freeRu = "бесплатно у входа")) else st
            })
        }
        val trip = base.copy(daysList = days, cost = base.cost.copy(lines = base.cost.lines.map { if (it.key == "parking") it.copy(rub = 0) else it }))
        val sum = parkingOf(trip)
        assertTrue("fixture has unknown and free stops: $sum", sum.unknown > 0 && sum.known > 0 && sum.rub == 0)
        val ctx = org.robolectric.RuntimeEnvironment.getApplication()
        val freePlus = ctx.getString(UiR.string.road_parking_free_unknown)
        val free = ctx.getString(UiR.string.road_parking_inline_free)
        shot("road", "s4-parking-free-unknown") { RoadScreen(RoadUi(trip, "NE"), noRoad) }
        compose.onNodeWithTag("road.total.parking.value", useUnmergedTree = true).assertTextEquals(freePlus)
        // every day header follows the same rule
        trip.daysList.forEach { d ->
            val p = parkingOf(d)
            if (p.unknown > 0) assertTrue("day ${d.day}: $p", parkingTotal(p) != ParkingTotal.FREE)
        }
        assertTrue(compose.onAllNodesWithText(freePlus, useUnmergedTree = true).fetchSemanticsNodes().size >= 2) // footer + a day
        assertTrue("no bare «$free» total", freePlus != free) // the footer value is asserted equal to «бесплатно + ?» above
    }

    @Test
    @Config(qualifiers = "ru-rRU-w390dp-h1200dp-port-xxhdpi")
    fun parkingFreePlusUnknownWaybillLine() {
        val base = s4Trip()
        val trip = base.copy(
            daysList = base.daysList.map { d -> d.copy(stops = d.stops.map { st -> if (st.parking?.known == true) st.copy(parking = app.verst.core.model.dto.ParkingDto(rub = 0, source = "free")) else st }) },
            cost = base.cost.copy(lines = base.cost.lines.map { if (it.key == "parking") it.copy(rub = 0) else it }),
        )
        shot("waybill", "s4-parking-free-unknown", 390, 1200) { WaybillScreen(WaybillUi(trip, 1, false, null), noWaybill) }
        compose.onNodeWithTag("waybill.sum.parking", useUnmergedTree = true).assertTextEquals("0 + ?")
    }

    /** Paid + unknown (the s4 fixture): footer «≈ N ₽ + ?», Waybill «N + ?». */
    @Test
    fun parkingSumPlusUnknownFooter() {
        val trip = s4Trip()
        val sum = parkingOf(trip)
        val line = trip.cost.lines.first { it.key == "parking" }.rub
        assertTrue(sum.unknown > 0 && line > 0)
        val ctx = org.robolectric.RuntimeEnvironment.getApplication()
        shot("road", "s4-parking-sum-unknown") { RoadScreen(RoadUi(trip, "NE"), noRoad) }
        compose.onNodeWithTag("road.total.parking.value", useUnmergedTree = true)
            .assertTextEquals(ctx.getString(UiR.string.road_parking_day_unknown, app.verst.settings.AppPrefs.money(line)))
    }

    /** M6+ contract (a Moscow zone stop): the engine's P part, the sheet from `zoneRu` / `whereRu` / `sundayRu`. */
    @Test
    fun roadM6MoscowParkingContract() {
        val trip = v2PlanTrip("plan-moscow-parking.json").trip
        // data-independent: since G15 the calm Москва → Тула keeps Высоцкий монастырь + Тульский кремль (free)
        // instead of the paid Кремль — every stop with a parking object carries its P part either way
        val withParking = trip.daysList.flatMap { it.stops }.filter { it.parking != null }
        assertTrue("the contract has parking objects", withParking.isNotEmpty())
        shot("road", "m6-moscow-parking") { RoadScreen(RoadUi(trip, "N"), noRoad) }
        withParking.forEach { compose.onNodeWithTag("road.stop.${it.id}.parking", useUnmergedTree = true).assertExists() }
        compose.onNodeWithTag("road.total.parking", useUnmergedTree = true).assertExists()
        // the line is Σ of the stops' stays
        assertEquals(withParking.sumOf { it.parking?.rub ?: 0 }, trip.cost.lines.first { it.key == "parking" }.rub)
        assertTrue("no «не проверено» on rows", compose.onAllNodesWithText("не проверено", substring = true, useUnmergedTree = true).fetchSemanticsNodes().isEmpty())
    }

    @Test
    fun roadM6ParkingSheetContract() {
        val trip = v2PlanTrip("plan-moscow-parking.json").trip
        val stops = trip.daysList.flatMap { it.stops }
        val stop = stops.firstOrNull { (it.parking?.rub ?: 0) > 0 } ?: stops.first { it.parking != null }
        shot("road", "m6-parking-sheet") { RoadScreen(RoadUi(trip, "N", parking = stop), noRoad) }
        val p = stop.parking!!
        if ((p.rubPerHour ?: 0) > 0) {
            compose.onNodeWithTag("parking.detail", useUnmergedTree = true).assertTextContains("${p.rubPerHour}", substring = true)
        } else {
            compose.onNodeWithTag("parking.ok", useUnmergedTree = true).assertExists()
        }
        if (p.sundayRu != null) assertTrue(compose.onAllNodesWithText("воскресенье", substring = true, ignoreCase = true).fetchSemanticsNodes().isNotEmpty())
    }

    /** CEO 29.10: «Вести по картам» names the app it opens (and the browser when that app is missing). */
    @Test
    fun roadHandoffCtaGoogle() {
        shot("road", "cta-google") {
            RoadScreen(RoadUi(s4Trip(), "NE", carTarget = HandoffTarget.Google, maps = app.verst.nav.HandoffApp.GOOGLE), noRoad)
        }
        compose.onNodeWithText("Вести по картам", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("road.handoff.sub", useUnmergedTree = true).assertTextEquals("Google Карты · все точки дня 1")
    }

    @Test
    fun roadHandoffCtaYandex() {
        shot("road", "cta-yandex") { RoadScreen(RoadUi(s4Trip(), "NE", carTarget = HandoffTarget.Maps), noRoad) }
        compose.onNodeWithTag("road.handoff.sub", useUnmergedTree = true).assertTextEquals("Яндекс Карты · все точки дня 1")
    }

    @Test
    fun roadS4Top() {
        shot("road", "s4-top") { RoadScreen(RoadUi(s4Trip(), "NE"), noRoad) }
        compose.onNodeWithTag("road.handoff").assertExists()
        compose.onNodeWithTag("road.handoff.sub", useUnmergedTree = true).assertTextContains("в браузере", substring = true) // no maps app
        compose.onNodeWithTag("road.day.1.navigator").assertExists()
        compose.onNodeWithTag("road.day.1.parking", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("road.total.parking", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("road.legend.kmpost", useUnmergedTree = true).assertExists()
        // the old standalone «не проверено» badge stays off rows; ADR-0019 fact lines («… — не проверено») are allowed
        compose.onNodeWithText("не проверено").assertDoesNotExist()
    }

    /** The long list at once: km posts, tags (Разминка, kinds, the open-data ring), costs lines with the P part. */
    @Test
    @Config(qualifiers = "ru-rRU-w390dp-h2400dp-port-xxhdpi")
    fun roadS4Rows() {
        shot("road", "s4-rows", 390, 2400) { RoadScreen(RoadUi(s4Trip(), "NE"), noRoad) }
        assertTrue(compose.onAllNodesWithTag("road.kmpost", useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty())
        assertTrue(compose.onAllNodesWithTag("tag.kind", useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty())
        assertTrue(compose.onAllNodesWithTag("tag.stretch", useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty())
        assertTrue(compose.onAllNodesWithText("Разминка", substring = true).fetchSemanticsNodes().isNotEmpty())
        assertTrue(compose.onAllNodesWithTag("tag.opendata", useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty())
        assertTrue(compose.onAllNodesWithText("туалет", substring = true).fetchSemanticsNodes().isNotEmpty())
        // S4-QA P1-01 + M9: cafés have a P part («P ?» when unknown); fuel and the hotel have none
        val trip = s4Trip()
        trip.daysList.flatMap { it.stops }.filter { it.kind == "food" }.take(2).forEach { st ->
            compose.onNodeWithTag("road.stop.${st.id}.parking", useUnmergedTree = true).assertExists()
        }
        trip.daysList.flatMap { it.stops }.filter { it.kind == "fuel" || it.kind == "overnight" }.take(2).forEach { st ->
            compose.onNodeWithTag("road.stop.${st.id}.parking", useUnmergedTree = true).assertDoesNotExist()
        }
    }

    @Test
    fun roadS4ParkingSheet() {
        val trip = s4Trip()
        val stop = trip.daysList.flatMap { it.stops }.first { it.parking?.rubPerHour != null }
        shot("road", "s4-parking-sheet") { RoadScreen(RoadUi(trip, "NE", parking = stop), noRoad) }
        compose.onNodeWithTag("parking.detail", useUnmergedTree = true).assertTextContains("платная зона", substring = true)
        assertTrue(compose.onAllNodesWithText("150", substring = true).fetchSemanticsNodes().isNotEmpty()) // the tariff row
        compose.onNodeWithTag("parking.ok").assertExists()
    }

    @Test
    fun roadS4ParkingSheetUnknown() {
        val trip = s4Trip()
        val stop = trip.daysList.flatMap { it.stops }.first { it.kind == "sight" && it.parking == null }
        shot("road", "s4-parking-unknown") { RoadScreen(RoadUi(trip, "NE", parking = stop), noRoad) }
        compose.onNodeWithTag("parking.note", useUnmergedTree = true).assertTextContains("Тариф неизвестен", substring = true) // S4-QA P1-04
        compose.onAllNodesWithText("уточните", substring = true).fetchSemanticsNodes().isNotEmpty().let(::assertTrue)
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

    /**
     * CEO 29.10, in Russia: day 1 → Яндекс Карты first with «рекомендуем здесь», Google Карты second (not installed →
     * the browser), the Навигатор last, to the next point only, with the 5-a-day note.
     */
    @Test
    fun handoffSheetDayUnsigned() {
        val h = v2<app.verst.core.model.dto.HandoffDto>("handoff-car-day.json", EngineJson::handoff)
        val ui = app.verst.feature.road.HandoffSheetUi(app.verst.nav.HandoffSheet(1, h, 1), mapsInstalled = true, naviInstalled = true, remember = false)
        shot("handoff", "s4-day-unsigned") { RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE", handoff = ui), noRoad) }
        compose.onNodeWithTag("handoff.maps.badge", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("рекомендуем здесь", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("handoff.google.badge", useUnmergedTree = true).assertDoesNotExist()
        compose.onNodeWithTag("handoff.google.note", useUnmergedTree = true).assertTextContains("браузере", substring = true)
        compose.onNodeWithTag("handoff.navi.note", useUnmergedTree = true).assertTextContains("5 раз", substring = true)
        compose.onNodeWithText("только до следующей точки", substring = true, useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("handoff.tab.1").assertIsSelected()
        // the Яндекс Карты card is above the Google one, the Навигатор last
        val y = { tag: String -> compose.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode().boundsInRoot.top }
        assertTrue(y("handoff.maps") < y("handoff.google"))
        assertTrue(y("handoff.google") < y("handoff.navi"))
    }

    /** CEO 29.10, abroad: Google Карты first with «рекомендуем здесь»; the user's own choice says «ваш выбор». */
    @Test
    fun handoffSheetGoogleFirstAbroad() {
        val h = v2<app.verst.core.model.dto.HandoffDto>("handoff-car-day.json", EngineJson::handoff)
        val ui = app.verst.feature.road.HandoffSheetUi(
            app.verst.nav.HandoffSheet(1, h, 1), mapsInstalled = false, naviInstalled = false, remember = false,
            preferred = app.verst.nav.HandoffApp.GOOGLE, googleInstalled = true,
        )
        shot("handoff", "google-first") { RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE", handoff = ui), noRoad) }
        compose.onNodeWithTag("handoff.google.badge", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("рекомендуем здесь", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("handoff.maps.badge", useUnmergedTree = true).assertDoesNotExist()
        compose.onNodeWithTag("handoff.google.note", useUnmergedTree = true).assertDoesNotExist() // installed
        compose.onNodeWithText("(до 9)", substring = true, useUnmergedTree = true).assertExists()
        val y = { tag: String -> compose.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode().boundsInRoot.top }
        assertTrue(y("handoff.google") < y("handoff.maps"))
    }

    @Test
    fun handoffSheetUsersChoice() {
        val h = v2<app.verst.core.model.dto.HandoffDto>("handoff-car-day.json", EngineJson::handoff)
        val ui = app.verst.feature.road.HandoffSheetUi(
            app.verst.nav.HandoffSheet(1, h, 1), mapsInstalled = true, naviInstalled = true, remember = true,
            preferred = app.verst.nav.HandoffApp.GOOGLE, googleInstalled = false, chosen = true,
        )
        shot("handoff", "google-chosen") { RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE", handoff = ui), noRoad) }
        compose.onNodeWithTag("handoff.google.badge", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("ваш выбор", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("handoff.google.note", useUnmergedTree = true).assertTextContains("до 3", substring = true)
    }

    /** «До след.» with the Навигатор not installed: it dims with «Установить…»; Карты (web) keeps its place. */
    @Test
    fun handoffSheetNextNaviMissing() {
        val h = v2<app.verst.core.model.dto.HandoffDto>("handoff-car-day.json", EngineJson::handoff)
        val ui = app.verst.feature.road.HandoffSheetUi(app.verst.nav.HandoffSheet(null, h, 1), mapsInstalled = false, naviInstalled = false, remember = true)
        shot("handoff", "s4-next-missing") { RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE", handoff = ui), noRoad) }
        compose.onNodeWithTag("handoff.navi.install", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("handoff.maps.note", useUnmergedTree = true).assertTextContains("браузере", substring = true)
        compose.onNodeWithTag("handoff.tab.next").assertIsSelected()
        compose.onNodeWithTag("handoff.remember").assertIsOn()
    }

    @Test
    fun roadDayMenu() {
        val h = v2<app.verst.core.model.dto.HandoffDto>("handoff-car-day.json", EngineJson::handoff)
        shot("road", "day-menu") { RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE", dayMenu = 1, dayHandoff = h, carTarget = HandoffTarget.Maps), noRoad) }
        compose.onNodeWithText("По картам: день 1").assertExists()
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
        // R-09 (ODbL package): the extract credit names CC BY-SA 4.0 and the abridgement, and opens the article
        assertTrue(d.extractSource!!.url!!.startsWith("https://www.wikidata.org/wiki/Special:GoToLinkedPage/ruwiki/"))
        val source = compose.onNodeWithTag("card.desc.source", useUnmergedTree = true)
        source.assertTextEquals("Из статьи Википедии, текст сокращён · CC BY-SA 4.0")
        assertTrue(source.fetchSemanticsNode().config.contains(SemanticsActions.OnClick))
    }

    /**
     * CEO 29.10: the address under the kind line, with the town the address does not name («ул. Ленина, 5 · Фрязино»);
     * a tap copies it with «Адрес скопирован»; TalkBack reads it with the card's title.
     */
    @Test
    fun cardAddressLineCopiesTheAddress() {
        val d = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-sight.json", EngineJson::poiDetails).copy(townName = "Фрязино")
        shot("card", "address") { CardOverRoad(card(d.nameRu, "sight", "tourist", d).copy(address = "ул. Ленина, 5")) }
        val line = compose.onNodeWithTag("card.address", useUnmergedTree = true)
        line.assertTextEquals("ул. Ленина, 5 · Фрязино")
        compose.onNodeWithTag("card.address.loading", useUnmergedTree = true).assertDoesNotExist()
        line.performClick()
        compose.waitForIdle()
        val clipboard = compose.activity.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
        assertEquals("ул. Ленина, 5 · Фрязино", clipboard.primaryClip!!.getItemAt(0).text.toString())
        assertEquals("Адрес скопирован", org.robolectric.shadows.ShadowToast.getTextOfLatestToast())
        assertEquals("ул. Ленина, 5 · Фрязино", app.verst.feature.card.cardAddressLine("ул. Ленина, 5", "Фрязино"))
        assertEquals("Фрязино, ул. Ленина, 5", app.verst.feature.card.cardAddressLine("Фрязино, ул. Ленина, 5", "Фрязино"))
        assertEquals("ул. Ленина, 5", app.verst.feature.card.cardAddressLine("ул. Ленина, 5", null))
    }

    /** «О данных» (ODbL package, CEO D-IR-07): sources and licences, the three links, the APK's full notice in place. */
    @Test
    @Config(qualifiers = "ru-rRU-w390dp-h1000dp-port-xxhdpi")
    fun aboutData() {
        shot("road", "about-data", 390, 1000) { RoadScreen(RoadUi(snapshot("G02_golden_ring"), "NE", aboutData = true), noRoad) }
        compose.onNodeWithText("данные доступны по лицензии ODbL 1.0", substring = true).assertExists()
        compose.onNodeWithText("в демо-сборке вымышленные", substring = true).assertExists()
        for (tag in listOf("aboutdata.copy", "aboutdata.odbl", "aboutdata.osm")) {
            assertTrue(tag, compose.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode().config.contains(SemanticsActions.OnClick))
        }
        // assets/licenses/data.txt (core-ui) ships in the APK and opens under the links
        compose.onNodeWithTag("aboutdata.notice.text", useUnmergedTree = true).assertDoesNotExist()
        compose.onNodeWithTag("aboutdata.notice", useUnmergedTree = true).performClick()
        compose.waitForIdle()
        val notice = compose.onNodeWithTag("aboutdata.notice.text", useUnmergedTree = true)
        notice.assertTextContains("© участники OpenStreetMap, данные доступны по лицензии", substring = true)
        notice.assertTextContains("https://opendatacommons.org/licenses/odbl/1-0/", substring = true)
        notice.assertTextContains("https://github.com/pazzia/Verst/tree/main/data/catalogue", substring = true)
        compose.onNodeWithText("Скрыть уведомление").assertExists()
    }

    @Test
    fun cardHotelArea() {
        // the placeholder state, deterministically: no URL (the runner has internet, Coil could load the real file)
        val real = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-hotel.json", EngineJson::poiDetails)
        val d = real.copy(image = real.image?.copy(card = null, thumb = null))
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

    /** 5.9 §9 (S4) level 4: no photo → the category illustration; «Почему здесь», the source line, fact chips. */
    @Test
    @Config(qualifiers = "ru-rRU-w390dp-h1000dp-port-xxhdpi")
    fun cardS4IllustrationAndChips() {
        val real = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-sight.json", EngineJson::poiDetails)
        val d = real.copy(
            poiKind = "museum", image = null, verified = false,
            descriptionRu = "Музей под открытым небом: избы, церкви и мельницы XVII–XIX веков, свезённые со всей области.",
            whyRu = "объект наследия федерального значения · есть в Викигиде", descSource = "wikipedia",
            hours = app.verst.core.model.dto.PoiHoursDto(textRu = "11:00–20:00", verified = false, todayRu = "11:00–20:00", openNow = true),
            dogsAllowed = false,
            parking = app.verst.core.model.dto.ParkingDto(rubPerHour = 80, rub = 160, source = "zone"),
        )
        shot("card", "s4-illustration-chips", 390, 1000) { CardOverRoad(card(d.nameRu, "sight", "tourist", d)) }
        compose.onNodeWithTag("photo.illustration", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("photo.illustration.none", useUnmergedTree = true).assertDoesNotExist()
        compose.onNodeWithTag("card.why", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("card.desc.source", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("card.facts", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("card.opendata", useUnmergedTree = true).assertExists()
        // no standalone «не проверено» badge; ADR-0019 fact lines («… — не проверено») are allowed
        assertTrue(compose.onAllNodesWithText("не проверено").fetchSemanticsNodes().isEmpty())
    }

    /** Level 5 (OSM-only): no photo and no description → the illustration with «фото пока нет». */
    @Test
    fun cardS4OsmOnly() {
        val real = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-sight.json", EngineJson::poiDetails)
        val d = real.copy(poiKind = "park", image = null, descriptionRu = null, extractRu = null, extractSource = null, ticket = null, descSource = "osm", whyRu = null, wikidataId = null, attributionRu = emptyList())
        shot("card", "s4-osm-only") { CardOverRoad(card(d.nameRu, "sight", "tourist", d)) }
        compose.onNodeWithTag("photo.illustration.none", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("card.osm", useUnmergedTree = true).assertExists() // S4-QA P1-05 (ODbL)
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

    /** Investor-readiness: a Wikidata text names its source once — never «Описание: Описание: Викиданные». */
    @Test
    fun cardWikidataSourceOnce() {
        val real = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-sight.json", EngineJson::poiDetails)
        val d = real.copy(
            extractRu = "Музей в историческом центре города.",
            extractSource = app.verst.core.model.dto.ExtractSourceDto(key = "wikidata", nameRu = "Описание: Викиданные", licence = "CC0"),
        )
        shot("card", "wikidata-source") { CardOverRoad(card(d.nameRu, "sight", "tourist", d)) }
        compose.onNodeWithTag("card.desc.source", useUnmergedTree = true).assertTextEquals("Описание: Викиданные · CC0")
    }

    /** ADR-0019 E-1 / E-2: unknown hours and an unknown ticket price are said; neither reads as open or free. */
    @Test
    fun cardUnknownHoursAndTicket() {
        val d = v2<app.verst.core.model.dto.PoiDetailsDto>("poi_details-ticket-unknown.json", EngineJson::poiDetails)
        shot("card", "unknown-facts") { CardOverRoad(card(d.nameRu, "sight", "tourist", d)) }
        compose.onNodeWithText("часы не известны — уточните", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("цена билета неизвестна", useUnmergedTree = true).assertExists()
        // only inside the card: the Road ahead behind it legitimately shows confirmed-free sights (Лавра)
        compose.onAllNodes(
            androidx.compose.ui.test.hasText("вход свободный") and androidx.compose.ui.test.hasAnyAncestor(androidx.compose.ui.test.hasTestTag("card")),
            useUnmergedTree = true,
        ).assertCountEquals(0)
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
            // G02 with the unconfirmed breakfasts costed (ADR-0019 E-3) is 37 200 ₽: a 40 000 ₽ budget keeps it fitted
            cost = trip.cost.copy(budgetRub = 40_000, remainingRub = 40_000 - trip.cost.totalRub, overBudget = false),
            budgetFit = app.verst.core.model.dto.BudgetFitDto(
                "fits", 40_000, 42_000, trip.cost.totalRub + 10_700, trip.cost.totalRub,
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
        override fun interest(i: String) = Unit
        override fun toggleReturn() = Unit
        override fun closeCustom() = Unit
        override fun buildCustom() = Unit
        override fun age(yes: Boolean) = Unit
        override fun suggestion(s: app.verst.core.model.dto.WalkSuggestion) = Unit
        override fun openPicker(p: app.verst.nav.CityPicker) = Unit
    }

    private val dogPreset = app.verst.core.model.dto.CityPresetDto(preset = "dog_walk", count = 9, defaultDurationMin = 120, titleRu = "Прогулка с собакой")

    private fun cityUi(
        error: String? = null, custom: Boolean = false, age: Boolean = false, building: Boolean = false, children: Int = 0, dog: Boolean = false,
        selected: String = "overview", duration: Int? = 240, few: app.verst.nav.WalkFew? = null, picker: app.verst.nav.CityPicker? = null,
    ): app.verst.feature.city.CityUi {
        val presets = v2<app.verst.core.model.dto.CityPresetsDto>("city_presets.json", EngineJson::cityPresets)
        // M6 contracts carry «Прогулка с собакой» themselves; it shows only with the dog, first
        val dogP = presets.presets.firstOrNull { it.preset == "dog_walk" } ?: dogPreset
        val shown = presets.presets.filter { it.available && it.preset != "dog_walk" }.let { if (dog) listOf(dogP) + it else it }
        return app.verst.feature.city.CityUi(
            town = if (error == "NO_CITY") null else presets.town?.name,
            startLabel = if (error == "NO_CITY") "Толбухино" else "Советская пл., 1",
            fromGps = true, presets = if (error == "NO_CITY") emptyList() else shown, loading = false, error = error, selected = selected,
            durationMin = duration, interests = listOf("parks", "views"), pace = "normal", budget = null, returnToStart = true,
            customSheet = custom, ageGate = age, building = building, adults = 2, children = children, dog = dog, startTime = "11:00",
            few = few, picker = picker,
        )
    }

    @Test
    fun cityPresets() {
        shot("city", "presets") { app.verst.feature.city.CityScreen(cityUi(), noCity) }
        compose.onNodeWithTag("city.preset.overview", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("city.start", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("city.crew.dog", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("city.duration.unlimited", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("city.pref.pace", useUnmergedTree = true).assertExists()
    }

    @Test
    fun cityChildAndBeerWarns() {
        // S4: children never block a preset — the walk is allowed and the plate says what to expect
        shot("city", "child-beer") { app.verst.feature.city.CityScreen(cityUi(children = 1, selected = "beer"), noCity) }
        compose.onNodeWithTag("city.warn.childbars", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("city.go").assertIsEnabled()
    }

    @Test
    fun cityDogWalkFirst() {
        shot("city", "dog") { app.verst.feature.city.CityScreen(cityUi(dog = true, selected = "museums"), noCity) }
        compose.onNodeWithTag("city.preset.dog_walk", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("city.warn.dogindoor", useUnmergedTree = true).assertExists()
    }

    @Test
    fun cityUnlimited() {
        shot("city", "unlimited") { app.verst.feature.city.CityScreen(cityUi(duration = null), noCity) }
        compose.onNodeWithText("без расписания", substring = true).assertExists()
    }

    @Test
    fun cityCustomSheet() = shot("city", "custom-sheet") { app.verst.feature.city.CityScreen(cityUi(custom = true, selected = "custom"), noCity) }

    @Test
    fun cityPacePicker() = shot("city", "pace-picker") { app.verst.feature.city.CityScreen(cityUi(picker = app.verst.nav.CityPicker.PACE), noCity) }

    @Test
    fun cityAgeGate() {
        shot("city", "age-gate") { app.verst.feature.city.CityScreen(cityUi(age = true), noCity) }
        compose.onNodeWithText("Вам есть 18?").assertExists()
    }

    @Test
    fun cityBuilding() = shot("city", "building") { app.verst.feature.city.CityScreen(cityUi(building = true), noCity) }

    @Test
    fun cityNoCity() = shot("city", "no-city") { app.verst.feature.city.CityScreen(cityUi(error = "NO_CITY"), noCity) }

    @Test
    fun cityNotEnoughWithEngineSuggestions() {
        // 5.11 §10.5: only the engine's verified suggestions — never «Гулять 4 ч» while 4 ч is selected
        val few = app.verst.nav.WalkFew(
            480, false,
            listOf(
                app.verst.core.model.dto.WalkSuggestion(durationMin = 360, count = 7),
                app.verst.core.model.dto.WalkSuggestion(unlimited = true, count = 9),
                app.verst.core.model.dto.WalkSuggestion(preset = "overview", count = 12),
            ),
            5,
        )
        shot("city", "not-enough") { app.verst.feature.city.CityScreen(cityUi(error = "NOT_ENOUGH_POIS", duration = 480, few = few), noCity) }
        compose.onNodeWithTag("walk.few.0", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("Гулять 8 ч").assertDoesNotExist()
    }

    @Test
    fun cityNotEnoughWithoutSuggestions() {
        val few = app.verst.nav.WalkFew(240, false, emptyList(), null)
        shot("city", "not-enough-none") { app.verst.feature.city.CityScreen(cityUi(error = "NOT_ENOUGH_POIS", few = few), noCity) }
        compose.onNodeWithText("Гулять", substring = true).assertDoesNotExist()
    }

    @Test
    fun cityNotEnoughNoData() {
        // CEO 29.10: `reason: "no_data"` — the engine's sentence (a gap of our base), not «мало мест»; other walks only
        val err = (EngineJson.walkRoute(root.resolve("docs/contracts/v2/city_route-error-no-data.json").readText().let {
            Json.parseToJsonElement(it).jsonObject["response"].toString()
        }) as EngineResult.Err).error
        val few = app.verst.nav.WalkFew.of(480, false, err)
        shot("city", "not-enough-no-data") { app.verst.feature.city.CityScreen(cityUi(error = "NOT_ENOUGH_POIS", duration = 480, few = few), noCity) }
        compose.onNodeWithText(err.messageRu!!).assertExists()
        compose.onNodeWithText("мало мест", substring = true).assertDoesNotExist()
        compose.onNodeWithText("Гулять", substring = true).assertDoesNotExist()
        compose.onNodeWithTag("walk.few.0", useUnmergedTree = true).assertExists()
    }

    @Test
    fun cityPresetWithoutData() {
        // CEO 29.10: a preset our catalogue has no places for here is listed, disabled, with the engine's reason
        val presets = v2<app.verst.core.model.dto.CityPresetsDto>("city_presets.json", EngineJson::cityPresets)
        val reason = "У нас пока нет данных о рюмочных в этом городе — это пробел нашей базы, а не города."
        val noData = presets.presets.filter { it.preset == "ryumochnye" }.map { it.copy(available = false, noData = true, noDataRu = reason) }
        shot("city", "preset-no-data") { app.verst.feature.city.CityScreen(cityUi().copy(noDataPresets = noData), noCity) }
        compose.onNodeWithTag("city.preset.nodata.ryumochnye", useUnmergedTree = true).assertExists()
        compose.onNodeWithText(reason).assertExists()
        compose.onNodeWithTag("city.preset.ryumochnye", useUnmergedTree = true).assertDoesNotExist()
    }

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
        // one button, or one per part when the engine split the walk (real catalogue: 2 parts)
        val tag = if (h.parts.size > 1) "walk.handoff.1" else "walk.handoff"
        compose.onNodeWithTag(tag, useUnmergedTree = true).assertExists()
    }

    @Test
    fun walkOverview() = walkShot("city_route-overview.json", "overview")

    /** CEO 29.10: a walker rides the walk column like the car on Road ahead — with the scroll, no TalkBack node. */
    @Test
    fun walkWalkerRidesTheColumn() {
        val w = v2<app.verst.core.model.dto.WalkRouteDto>("city_route-overview.json", EngineJson::walkRoute)
        assertTrue("a walk with stops", w.stops.isNotEmpty())
        shot("walk", "walker") { app.verst.feature.city.WalkScreen(app.verst.feature.city.WalkUi(w, null, HandoffTarget.Browser, saved = false, building = false), noWalk) }
        compose.onNodeWithTag("walk.stop.${w.stops.first().id}").performScrollTo()
        compose.waitForIdle()
        compose.onNodeWithTag("walk.walker", useUnmergedTree = true).assertExists()
        // decorative: cleared semantics (no text, no description for TalkBack)
        val node = compose.onNodeWithTag("walk.walker", useUnmergedTree = true).fetchSemanticsNode()
        assertTrue(node.children.isEmpty())
        assertFalse(node.config.contains(androidx.compose.ui.semantics.SemanticsProperties.ContentDescription))
    }

    private fun walkFilters(dog: Boolean = false, children: Int = 0, duration: Int? = 240) = app.verst.feature.city.PickerUi(
        duration, v2<app.verst.core.model.dto.CityPresetsDto>("city_presets.json", EngineJson::cityPresets).presets.filter { it.available },
        "overview", 2, children, dog, "normal", null,
    )

    private fun walkS4(state: String, ui: (app.verst.core.model.dto.WalkRouteDto) -> app.verst.feature.city.WalkUi) {
        val w = v2<app.verst.core.model.dto.WalkRouteDto>("city_route-overview.json", EngineJson::walkRoute)
        shot("walk", state) { app.verst.feature.city.WalkScreen(ui(w), noWalk) }
    }

    @Test
    fun walkFilterBarAndRebuilding() {
        walkS4("rebuilding") { w -> app.verst.feature.city.WalkUi(w, null, HandoffTarget.Browser, saved = false, building = true, filters = walkFilters()) }
        compose.onNodeWithTag("walk.filter.duration", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("walk.rebuilding", useUnmergedTree = true).assertExists()
    }

    @Test
    fun walkOtherNone() {
        walkS4("other-none") { w -> app.verst.feature.city.WalkUi(w, null, HandoffTarget.Browser, saved = false, building = false, filters = walkFilters(), otherNone = true) }
        compose.onNodeWithTag("walk.other.none", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("walk.other", useUnmergedTree = true).assertDoesNotExist()
    }

    @Test
    fun walkFewOnTheWalkScreen() {
        val few = app.verst.nav.WalkFew(480, false, listOf(app.verst.core.model.dto.WalkSuggestion(durationMin = 240, count = 6), app.verst.core.model.dto.WalkSuggestion(clearExclude = true, count = 3)), 4)
        walkS4("few") { w -> app.verst.feature.city.WalkUi(w, null, HandoffTarget.Browser, saved = false, building = false, filters = walkFilters(duration = 480), few = few) }
        compose.onNodeWithTag("walk.few", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("walk.total", useUnmergedTree = true).assertDoesNotExist()
    }

    @Test
    fun walkUntimedWithHoursPills() {
        val w0 = v2<app.verst.core.model.dto.WalkRouteDto>("city_route-overview.json", EngineJson::walkRoute)
        val hours = listOf(
            app.verst.core.model.dto.WalkHoursDto(todayRu = "10:00–18:00", openNow = true),
            app.verst.core.model.dto.WalkHoursDto(openNow = false, closedDayRu = "вторник"),
            app.verst.core.model.dto.WalkHoursDto(allDay = true),
            null,
        )
        val w = w0.copy(
            startAt = null, endAt = null,
            stops = w0.stops.mapIndexed { i, st -> st.copy(arriveAt = null, departAt = null, hours = hours[i % hours.size], poiKind = listOf("museum", "park", "square", "monument")[i % 4]) },
        )
        shot("walk", "untimed") { app.verst.feature.city.WalkScreen(app.verst.feature.city.WalkUi(w, null, HandoffTarget.Browser, saved = false, building = false, filters = walkFilters(duration = null)), noWalk) }
        compose.onNodeWithText("Порядок по пути", substring = true).assertExists()
        compose.onAllNodes(androidx.compose.ui.test.hasTestTag("hours.pill"), useUnmergedTree = true).fetchSemanticsNodes().let { assertTrue("pills ${it.size}", it.size >= 3) }
    }

    @Test
    fun walkDogWarning() {
        val w0 = v2<app.verst.core.model.dto.WalkRouteDto>("city_route-overview.json", EngineJson::walkRoute)
        val w = w0.copy(stops = w0.stops.mapIndexed { i, st -> if (i == 0) st.copy(poiKind = "museum") else st })
        shot("walk", "dog-warning") { app.verst.feature.city.WalkScreen(app.verst.feature.city.WalkUi(w, null, HandoffTarget.Browser, saved = false, building = false, filters = walkFilters(dog = true)), noWalk) }
        compose.onNodeWithTag("walk.warn.dog", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("С собакой внутрь обычно нельзя.", substring = true).assertExists() // ADR-0019 E-6
    }

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
    fun walkFoodStopsWithUnknownPrices() {
        // CEO 29.10: OSM restaurants and cafés — their own kind and sign, the cuisine in words (never the raw tag),
        // «цена не указана» instead of 0 ₽, our PRICE_UNKNOWN plate, and never «Бесплатно» in the footer
        val w0 = v2<app.verst.core.model.dto.WalkRouteDto>("city_route-overview.json", EngineJson::walkRoute)
        val food = listOf(
            Triple("restaurant", "Ресторан", "georgian;pizza;fusion"),
            Triple("cafe", "Кафе", "coffee_shop"),
            Triple("fast_food", "Фастфуд", "unknown_tag"),
        )
        val w = w0.copy(
            stops = w0.stops.mapIndexed { i, st ->
                val f = food.getOrNull(i) ?: return@mapIndexed st.copy(costRub = 0) // a free walk but for the cafés
                st.copy(kind = f.first, poiKind = f.first, poiKindRu = f.second, cuisine = f.third, costRub = 0, unknownFacts = listOf("price"), placeSource = "osm")
            },
            cost = w0.cost.copy(totalRub = 0),
            warnings = w0.warnings + app.verst.core.model.dto.WalkWarningDto("PRICE_UNKNOWN", "Цены в кафе и ресторанах в открытых данных не указаны — в сумму они не входят."),
        )
        shot("walk", "food") { app.verst.feature.city.WalkScreen(app.verst.feature.city.WalkUi(w, null, HandoffTarget.Browser, saved = false, building = false), noWalk) }
        compose.onAllNodesWithText("цена не указана", useUnmergedTree = true).assertCountEquals(food.size)
        compose.onNodeWithText("грузинская кухня, пицца", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("кофейня", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("unknown_tag", substring = true, useUnmergedTree = true).assertDoesNotExist()
        compose.onNodeWithText("georgian", substring = true, useUnmergedTree = true).assertDoesNotExist()
        compose.onNodeWithTag("walk.warn.price", useUnmergedTree = true).assertExists()
        compose.onNodeWithText("Цены в кафе и ресторанах не указаны — уточняйте на месте.", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("walk.free", useUnmergedTree = true).assertDoesNotExist()
        compose.onNodeWithTag("walk.price.unknown", useUnmergedTree = true).assertExists()
        assertEquals(listOf(app.verst.core.ui.components.Glyph.CUTLERY, app.verst.core.ui.components.Glyph.CUP, app.verst.core.ui.components.Glyph.CUTLERY, app.verst.core.ui.components.Glyph.MUG, app.verst.core.ui.components.Glyph.GLASS),
            listOf("restaurant", "cafe", "food_court", "pub", "ryumochnaya").map { app.verst.feature.city.walkSignGlyph(it) })
    }

    @Test
    fun walkShorterThanAsked() {
        // S3-QA P1-02 on every walk contract: the note shows exactly when the engine says the walk is shorter
        val files = listOf("city_route-shorter.json", "city_route-ryumochnye.json", "city_route-overview.json")
        val walks = files.map { v2<app.verst.core.model.dto.WalkRouteDto>(it, EngineJson::walkRoute) }
        val current = androidx.compose.runtime.mutableStateOf(walks[0])
        compose.setContent { app.verst.feature.city.WalkScreen(app.verst.feature.city.WalkUi(current.value, null, HandoffTarget.Browser, saved = false, building = false), noWalk) }
        for ((f, w) in files.zip(walks)) {
            compose.runOnIdle { current.value = w }
            compose.waitForIdle()
            val shown = compose.onAllNodes(androidx.compose.ui.test.hasTestTag("walk.shorter"), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty()
            assertEquals(f, w.shorterThanAsked, shown)
        }
    }


    @Test
    fun walkTomorrow() {
        // S3-QA P0-01: the walk moved to tomorrow's window → «Завтра: старт 09:00 · финиш ≈ 12:53»
        val w = v2<app.verst.core.model.dto.WalkRouteDto>("city_route-tomorrow.json", EngineJson::walkRoute)
        val day = java.time.LocalDate.now(java.time.ZoneId.of("Europe/Moscow")).plusDays(1)
        val t = w.copy(startAt = "${day}T09:00", endAt = "${day}T12:53")
        assertTrue(t.startsTomorrow())
        shot("walk", "tomorrow") { app.verst.feature.city.WalkScreen(app.verst.feature.city.WalkUi(t, null, HandoffTarget.Browser, saved = false, building = false), noWalk) }
        compose.onNodeWithText("Завтра", substring = true).assertExists()
    }

    @Test
    fun walkShorterEngineReason() {
        // the engine's `shorter` («places»). The real data may fill the asked time (release-s3 museum walks),
        // so the shot sets a shorter result on the contract walk to keep the state covered.
        val w = v2<app.verst.core.model.dto.WalkRouteDto>("city_route-shorter.json", EngineJson::walkRoute)
        val asked = w.requestedMin ?: 480
        val s = w.copy(durationMin = asked - 150, shorter = w.shorter ?: app.verst.core.model.dto.WalkShorterDto("places", asked, asked - 150, null))
        shot("walk", "shorter-engine") { app.verst.feature.city.WalkScreen(app.verst.feature.city.WalkUi(s, null, HandoffTarget.Browser, saved = false, building = false), noWalk) }
        compose.onNodeWithTag("walk.shorter", useUnmergedTree = true).assertExists()
    }

    @Test
    fun cityCaptionTomorrow() {
        shot("city", "caption-tomorrow") { app.verst.feature.city.CityScreen(cityUi().copy(startTime = "09:00", startTomorrow = true), noCity) }
        compose.onNodeWithText("завтра", substring = true).assertExists()
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
        compose.onNodeWithText("Пейте умеренно, чередуйте с водой и едой. За руль\u00A0— только трезвым.").assertExists() // S3-FINAL P2-01: NBSP before the dash
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
        compose.onNodeWithTag("waybill.total.note", useUnmergedTree = true).assertDoesNotExist()
    }

    /** ADR-0019 E-2: the total says it leaves out the tickets whose price is unknown. */
    @Test
    fun waybillTotalNote() {
        val t = snapshot("G02_golden_ring")
        val trip = t.copy(cost = t.cost.copy(totalNoteRu = "Без билетов в 1 место — цена неизвестна"))
        shot("waybill", "total-note") { WaybillScreen(waybill(trip), noWaybill) }
        compose.onNodeWithTag("waybill.total.note", useUnmergedTree = true).assertTextEquals("Без билетов в 1 место — цена неизвестна")
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

    // ------------------------------------------------------------------ D-IR-20 personal cabinet

    private val settingsUi = app.verst.feature.settings.SettingsUi(
        app.verst.core.model.AppSettings(currency = "USD"),
        app.verst.core.model.RatesDto("2026-10-27", "cbr", mapOf("USD" to 80.0)),
        app.verst.feature.settings.BuildLines("0.1.147", 147, "eff752f1a2b3", "2026-10-27 09:00 UTC", "0.9.0", "3.11.9", "2026.10 · 2026-10-20"),
        listOf(app.verst.settings.BuildSeen(147, "0.1.147", "eff752f1a2b3", "2026-10-27 09:00 UTC", 1_793_000_000_000L)),
        null, themePending = false,
    )

    private class SettingsSpy : app.verst.feature.settings.SettingsActions {
        val calls = mutableListOf<String>()
        override fun back() { calls += "back" }
        override fun language(l: app.verst.core.model.AppLanguage) { calls += "language:$l" }
        override fun currency(code: String) { calls += "currency:$code" }
        override fun theme(t: app.verst.core.model.AppTheme) { calls += "theme:$t" }
        override fun restart() { calls += "restart" }
        override fun storageDevice() { calls += "device" }
        override fun pickFolder() { calls += "folder" }
        override fun writeFolderNow() { calls += "now" }
        override fun copyBuild() { calls += "copy" }
        override fun developer() { calls += "dev" }
        override fun planOnServer(on: Boolean) { calls += "server:$on" }
        override fun checkServer() { calls += "check" }
        override fun serverConsent(agree: Boolean) { calls += "consent:$agree" }
        override fun openPrivacy() { calls += "privacy" }
        override fun forgetServer() { calls += "forget" }
        override fun consumption(steps: Int) { calls += "consumption:$steps" }
        override fun tank(steps: Int) { calls += "tank:$steps" }
        override fun fuel(type: String) { calls += "fuel:$type" }
        override fun avoidTolls(on: Boolean) { calls += "tolls:$on" }
        override fun mapsApp(choice: app.verst.core.model.MapsChoice) { calls += "maps:$choice" }
    }

    /** CEO 29.10 «Навигация»: the automatic choice says what it does where the phone is; the user can override it. */
    @Test
    fun settingsMapsInRussia() {
        val spy = SettingsSpy()
        shot("settings", "maps-russia") { app.verst.feature.settings.SettingsScreen(settingsUi.copy(country = "RU"), spy) }
        compose.onNodeWithTag("settings.maps.AUTO").performScrollTo().assertIsSelected()
        compose.onNodeWithTag("settings.maps.line", useUnmergedTree = true).assertTextEquals("Сейчас вы в России — маршрут откроют Яндекс Карты")
        compose.onNodeWithTag("settings.maps.GOOGLE").performScrollTo().performClick()
        assertEquals(listOf("maps:GOOGLE"), spy.calls)
    }

    @Test
    fun settingsMapsAbroad() {
        shot("settings", "maps-abroad") { app.verst.feature.settings.SettingsScreen(settingsUi.copy(country = "DE"), SettingsSpy()) }
        compose.onNodeWithTag("settings.maps.line", useUnmergedTree = true).assertTextContains("за рубежом", substring = true)
        compose.onNodeWithTag("settings.maps.line", useUnmergedTree = true).assertTextContains("Google Карты", substring = true)
    }

    @Test
    fun settingsMapsUsersChoiceWins() {
        val chosen = settingsUi.copy(settings = settingsUi.settings.copy(mapsApp = app.verst.core.model.MapsChoice.YANDEX), country = "DE")
        shot("settings", "maps-chosen") { app.verst.feature.settings.SettingsScreen(chosen, SettingsSpy()) }
        compose.onNodeWithTag("settings.maps.YANDEX").performScrollTo().assertIsSelected()
        compose.onNodeWithTag("settings.maps.line", useUnmergedTree = true).assertTextEquals("Маршрут дня всегда откроют Яндекс Карты")
    }

    @Test
    fun settingsMapsUnknownCountry() {
        shot("settings", "maps-unknown") { app.verst.feature.settings.SettingsScreen(settingsUi, SettingsSpy()) }
        compose.onNodeWithTag("settings.maps.line", useUnmergedTree = true).assertTextContains("откроем Яндекс Карты", substring = true)
    }

    @Test
    fun settingsDefault() {
        val spy = SettingsSpy()
        shot("settings", "default") { app.verst.feature.settings.SettingsScreen(settingsUi, spy) }
        compose.onNodeWithTag("settings.currency.USD").assertIsSelected()
        compose.onNodeWithTag("settings.currency.RUB").assertIsNotSelected()
        compose.onNodeWithTag("settings.language.RU").assertIsSelected()
        compose.onNodeWithTag("settings.storage.cloud").assertIsNotEnabled()
        assertTrue(compose.onAllNodesWithText("0.1.147", substring = true).fetchSemanticsNodes().isNotEmpty())
        // the «Навигация» section pushed these below the fold: a click by semantics, not by the touch position
        compose.onNodeWithTag("settings.currency.EUR").performScrollTo().performSemanticsAction(androidx.compose.ui.semantics.SemanticsActions.OnClick)
        compose.onNodeWithTag("settings.theme.DAY").performScrollTo().performSemanticsAction(androidx.compose.ui.semantics.SemanticsActions.OnClick)
        assertEquals(listOf("currency:EUR", "theme:DAY"), spy.calls)
        assertTrue(compose.onAllNodesWithTag("settings.restart").fetchSemanticsNodes().isEmpty())
        // acceptance 28.10: the screen is «Настройки», the car is set here (traveller К4)
        compose.onNodeWithText("Настройки").assertExists()
        compose.onNodeWithTag("settings.consumption.value", useUnmergedTree = true).assertTextEquals("8 л на 100 км")
        compose.onNodeWithTag("settings.fuel.ai95").assertIsSelected()
        compose.onNodeWithTag("settings.tolls.false").assertIsSelected()
        compose.onNodeWithTag("settings.consumption.more").performScrollTo().performClick()
        compose.onNodeWithTag("settings.tolls.true").performScrollTo().performClick()
        assertEquals(listOf("consumption:1", "tolls:true"), spy.calls.drop(2))
    }

    @Test
    fun settingsServerConsentAndForget() {
        val spy = SettingsSpy()
        val withServer = settingsUi.copy(serverUrl = "https://212-108-82-26.sslip.io", serverConsentAsk = true)
        shot("settings", "server-consent") { app.verst.feature.settings.SettingsScreen(withServer, spy) }
        compose.onNodeWithTag("settings.server.consent").assertIsDisplayed()
        compose.onNodeWithText("Нидерландах", substring = true).assertExists()
        compose.onNodeWithTag("settings.server.consent.yes").performClick()
        assertEquals(listOf("consent:true"), spy.calls)
        assertTrue(compose.onAllNodesWithTag("settings.server.forget").fetchSemanticsNodes().isEmpty()) // no consent yet
    }

    @Test
    fun settingsDayPaletteAndRestart() {
        val day = app.verst.core.ui.theme.Palette.day
        app.verst.core.ui.theme.Palette.day = true
        try {
            shot("settings", "day") { app.verst.feature.settings.SettingsScreen(settingsUi.copy(themePending = true), SettingsSpy()) }
            compose.onNodeWithTag("settings.restart").performScrollTo().assertIsDisplayed()
        } finally {
            app.verst.core.ui.theme.Palette.day = day
        }
    }

    @Test
    fun windshieldDayPalette() {
        val day = app.verst.core.ui.theme.Palette.day
        app.verst.core.ui.theme.Palette.day = true
        try {
            shot("windshield", "day") { WindshieldScreen(windshield(WindshieldData.Routes(routes)), {}, {}, {}, {}) }
            compose.onNodeWithTag("windshield.settings").assertExists()
        } finally {
            app.verst.core.ui.theme.Palette.day = day
        }
    }

    @Test
    fun buildTextIsOneFactPerLine() {
        val t = app.verst.feature.settings.buildText(settingsUi.build, app.verst.core.model.AppLanguage.EN, "USD", "2026-10-27")
        assertTrue(t, t.startsWith("Verst 0.1.147 (build 147)\ncommit eff752f1a2b3\nbuilt 2026-10-27 09:00 UTC"))
        assertTrue(t, t.contains("settings EN · USD · rates 2026-10-27"))
    }
}
