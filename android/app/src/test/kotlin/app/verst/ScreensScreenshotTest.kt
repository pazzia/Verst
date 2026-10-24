package app.verst

import androidx.activity.ComponentActivity
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
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
            InstrumentsUi("Москва → Ярославль", "Москва", false, 265, true, listOf(Seat.EMPTY, Seat.EMPTY, Seat.EMPTY), false, 2, 0, 300, 2, null, days = 1),
            noActions,
        )
    }

    private fun windshield(data: WindshieldData) = WindshieldUi("Москва", data, 0, 2, 1, true)

    @Test
    fun windshieldDefault() {
        shot("windshield", "default") { WindshieldScreen(windshield(WindshieldData.Routes(routes)), {}, {}, {}, {}) }
        compose.onNodeWithTag("windshield.route.0").assertExists()
        compose.onNodeWithText("РЯДОМ С ВАМИ · ИЗ МОСКВЫ").assertExists()
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
                InstrumentsUi("Золотое кольцо", "Москва", true, 761, true, listOf(Seat.CHILD, Seat.EMPTY, Seat.ADULT), true, 3, 1, 300, 2, Mood.CALM, days = 3),
                noActions,
            )
        }
        compose.onNodeWithText("3 взрослых · 1 ребёнок · собака").assertExists() // Russian plural rules (ru locale)
    }

    @Test
    fun driveProgress() = shot("drive", "t1500") {
        DriveScreen(
            DriveUi(listOf("Прокладываем дорогу", "Делим кольцо на 3 дня по ≈ 250 км", "Ищем отели, куда пустят с собакой"), 0.45f, days = 3),
            "745", { DriveAction.RETRY }, {}, {}, { _, _ -> },
        )
    }

    @Test
    fun driveDone() = shot("drive", "done") {
        DriveScreen(
            DriveUi(listOf("Делим кольцо на 3 дня", "Сверяем часы работы", "Считаем бензин: 8,0 л на 100 км", "Считаем, сколько стоит поездка"), 1f, days = 3, done = true),
            "745", { DriveAction.RETRY }, {}, {}, { _, _ -> },
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
            DriveScreen(DriveUi(error = EngineErrorDto("INTERNAL")), "745", { DriveAction.RETRY }, {}, {}, { _, _ -> })
        }
        compose.onNodeWithText("Попробовать ещё раз").assertExists()
    }

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

    @Test
    fun engineEnvelopeErrorsNeverThrow() {
        assertEquals("INTERNAL", (EngineJson.planResult("") as EngineResult.Err).error.code)
    }
}
