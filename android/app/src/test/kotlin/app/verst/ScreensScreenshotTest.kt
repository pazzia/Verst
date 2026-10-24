package app.verst

import androidx.activity.ComponentActivity
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
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
import app.verst.feature.road.RoadScreen
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
            InstrumentsUi("Москва → Ярославль", "Москва", false, 312, true, listOf(Seat.EMPTY, Seat.EMPTY, Seat.EMPTY), false, 2, 0, 300, 2, null),
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
        NavigatorScreen(navigator("Яро", listOf(yaroslavl), null), {}, {}, {}, {}, {})
    }

    @Test
    fun navigatorPicked() = shot("navigator", "destination-picked") {
        NavigatorScreen(navigator("Ярославль", emptyList(), yaroslavl), {}, {}, {}, {}, {})
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
                InstrumentsUi("Золотое кольцо", "Москва", true, 745, true, listOf(Seat.CHILD, Seat.EMPTY, Seat.ADULT), true, 3, 1, 300, 2, Mood.CALM),
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

    @Test
    fun roadG02() {
        val trip = EngineJson.trip(root.resolve("backend/planner/tests/golden/snapshots/G02_golden_ring.json").readText())
        shot("road", "g02-top") { RoadScreen(trip, "NE") {} }
        compose.onNodeWithTag("road.total").assertExists()
        compose.onNodeWithText("Дорога впереди").assertExists()
    }

    @Test
    fun roadNoLodging() {
        val trip = EngineJson.trip(root.resolve("backend/planner/tests/golden/snapshots/G05_edge_no_dog_lodging.json").readText())
        shot("road", "no-lodging") { RoadScreen(trip, "E") {} }
    }

    @Test
    fun engineEnvelopeErrorsNeverThrow() {
        assertEquals("INTERNAL", (EngineJson.planResult("") as EngineResult.Err).error.code)
    }
}
