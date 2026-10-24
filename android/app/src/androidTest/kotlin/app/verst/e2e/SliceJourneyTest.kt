package app.verst.e2e

import android.graphics.Bitmap
import android.util.Log
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeUp
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.verst.MainActivity
import app.verst.VerstApp
import app.verst.nav.Route
import app.verst.nav.Toast
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TestWatcher
import org.junit.runner.Description
import org.junit.runner.RunWith

/**
 * DEV-SLICE(-2) journey on the real engine: Windshield → (own route) Navigator → Instruments → Drive → Road ahead
 * with one distance on every screen, then Waybill (expand a line, reserve off), replace a stop, save, back to
 * the Windshield and reopen the trip from «Мои поездки»; and a ready route → Instruments → Drive → Road ahead.
 * Screens go to `files/e2e/screens/NN-name.png` (ci-logs `runs/<R>/e2e/screens/`).
 */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
class SliceJourneyTest {
    @get:Rule(order = 0) val compose = createAndroidComposeRule<MainActivity>()

    /** Inner rule: on a failure the activity is still up, so the screen at the moment of failure is kept. */
    @get:Rule(order = 1) val onFailure = object : TestWatcher() {
        override fun failed(e: Throwable?, description: Description) {
            runCatching { shot("zz-failed-${description.methodName}") }
        }
    }

    private val flow get() = (InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as VerstApp).flow

    @Before
    fun toRoot() {
        E2e.awaitReady(30_000)
        compose.runOnUiThread {
            while (flow.back()) Unit
            flow.clearSaved()
            flow.debugForceError = null
        }
    }

    private fun shot(name: String) {
        compose.waitForIdle()
        Thread.sleep(300)
        val dir = File(E2e.dir(), "screens").apply { mkdirs() }
        val bmp = InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
        File(dir, "$name.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        Log.i("VerstE2e", "screen $name route=${flow.top}")
    }

    private fun waitTag(tag: String, timeoutMs: Long = 30_000) {
        compose.waitUntil(timeoutMs) { compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty() }
    }

    private fun back() {
        compose.runOnUiThread { compose.activity.onBackPressedDispatcher.onBackPressed() }
        compose.waitForIdle()
    }

    /** Text of a tagged node, "" when it is not (yet) in the tree — safe inside `waitUntil`. */
    private fun textOf(tag: String): String {
        val nodes = compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true).fetchSemanticsNodes()
        return nodes.firstOrNull()?.config?.getOrNull(SemanticsProperties.Text)?.joinToString("") { it.text }.orEmpty()
    }

    private fun totalText() = textOf("road.total.amount")

    /** The first number in a text («265 км · город …» → 265, «1 234» → 1234). */
    private fun number(text: String): Int? =
        Regex("""\d[\d\u202F\u00A0 ]*""").find(text)?.value?.filter { it.isDigit() }?.toIntOrNull()

    private fun assertRoadAhead(prefix: String) {
        waitTag("road.total", 45_000)
        assertEquals(Route.Road, flow.top)
        val total = totalText()
        Log.i("VerstE2e", "$prefix total=$total")
        assertTrue("total shown: '$total'", total.startsWith("≈") && total.endsWith("₽") && total.any { it.isDigit() })
        val trip = flow.result!!.trip
        assertTrue("days > 0", trip.daysList.isNotEmpty())
        compose.onNodeWithText("Дорога впереди").assertExists()
    }

    @Test
    fun ownRouteToRoadAheadAndBack() {
        waitTag("windshield.route.0")
        shot("01-windshield")

        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.to")
        compose.onNodeWithTag("navigator.to").performTextInput("Яро")
        waitTag("navigator.suggestion.0")
        shot("02-navigator-query")
        compose.onNodeWithTag("navigator.suggestion.0").performScrollTo().assertIsDisplayed().performClick()
        waitTag("navigator.start", 10_000)
        compose.onNodeWithTag("navigator.start").assertIsEnabled()
        // P0: the caption shows the engine's km of this very trip (estimate = plan), not a straight line.
        compose.waitUntil(15_000) { flow.figures?.stale == false && number(textOf("navigator.meta")) != null }
        val navKm = number(textOf("navigator.meta"))!!
        assertEquals(flow.figures!!.figures.km, navKm)
        shot("03-navigator-picked")
        compose.onNodeWithTag("navigator.start").performClick()

        waitTag("instruments.start")
        compose.waitUntil(15_000) { number(textOf("instruments.meta")) != null }
        assertEquals(navKm, number(textOf("instruments.meta"))) // same request → same number
        compose.onNodeWithTag("instruments.seat.0").performClick()
        compose.onNodeWithTag("instruments.seat.0").performClick() // adult → child
        assertEquals(1, flow.children)
        compose.waitUntil(15_000) { flow.figures?.stale == false } // the engine re-estimated with the child
        val instrumentsKm = number(textOf("instruments.meta"))!!
        assertEquals(flow.figures!!.figures.km, instrumentsKm)
        shot("04-instruments")
        compose.onNodeWithTag("instruments.start").performClick()

        waitTag("drive.back")
        compose.waitUntil(10_000) { flow.drive.lines.size >= 2 || flow.drive.done } // paced steps on the device
        shot("05-drive")
        assertRoadAhead("own")
        shot("06-road-ahead")
        val trip = flow.result!!.trip
        assertEquals("Москва → Ярославль", trip.title)
        // One trip, one distance: Instruments == the plan == the Road-ahead sign.
        Log.i("VerstE2e", "km navigator=$navKm instruments=$instrumentsKm plan=${trip.km} road=${textOf("road.km")}")
        assertEquals(instrumentsKm, trip.km)
        assertEquals(trip.km, number(textOf("road.km")))
        compose.onNodeWithTag("road.list").performTouchInput { swipeUp() }
        shot("07-road-ahead-scrolled")

        // Waybill: open from the footer, expand the fuel line, switch the reserve off.
        compose.onNodeWithTag("road.total").performClick()
        waitTag("waybill.sheet")
        assertEquals(Route.Waybill, flow.top)
        assertEquals(trip.cost.totalRub, number(textOf("waybill.total")))
        shot("11-waybill")
        compose.onNodeWithTag("waybill.line.fuel").performScrollTo().performClick()
        waitTag("waybill.breakdown.fuel.0")
        assertEquals("fuel", flow.expandedLine)
        shot("12-waybill-fuel-open")
        compose.onNodeWithTag("waybill.line.fuel").performScrollTo().performClick() // collapse again
        val before = flow.result!!.trip.cost
        assertTrue(before.reserveOn)
        compose.onNodeWithTag("waybill.reserve").performScrollTo().performClick()
        compose.waitUntil(10_000) { !flow.result!!.trip.cost.reserveOn }
        val after = flow.result!!.trip.cost
        assertTrue("total drops: ${before.totalRub} → ${after.totalRub}", after.totalRub < before.totalRub)
        compose.waitUntil(5_000) { number(textOf("waybill.total")) == after.totalRub }
        assertEquals("—", textOf("waybill.reserve.sum"))
        compose.onNodeWithTag("waybill.total", useUnmergedTree = true).performScrollTo()
        shot("13-waybill-reserve-off")
        back()
        assertEquals(Route.Road, flow.top)
        compose.waitUntil(5_000) { number(totalText()) == after.totalRub }

        // Replace a stop with the engine's first alternative.
        val stop = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.alternatives.isNotEmpty() }
        val alt = stop.alternatives.first()
        compose.onNodeWithTag("road.swap.${stop.id}").performScrollTo().performClick()
        waitTag("replace")
        shot("14-replace-sheet")
        compose.onNodeWithTag("replace.alt.0", useUnmergedTree = true).performScrollTo().performClick()
        compose.onNodeWithTag("replace.confirm", useUnmergedTree = true).performScrollTo()
        compose.onNodeWithText("ЗАМЕНИТЬ").performClick()
        compose.waitUntil(15_000) { flow.replace == null && flow.toast is Toast.Replaced }
        val replaced = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.id == stop.id }
        assertEquals(alt.name, replaced.name)
        assertEquals((flow.toast as Toast.Replaced).totalRub, flow.result!!.trip.cost.totalRub)
        compose.waitUntil(5_000) { number(totalText()) == flow.result!!.trip.cost.totalRub }
        shot("15-replaced")

        // Save, then reopen from «Мои поездки».
        compose.onNodeWithTag("road.save").performClick()
        compose.waitUntil(5_000) { flow.savedCurrent && flow.saved.size == 1 }
        shot("16-saved")
        val savedTotal = flow.result!!.trip.cost.totalRub

        back()
        assertEquals(Route.Instruments, flow.top)
        back()
        assertEquals(Route.Navigator, flow.top)
        back()
        assertEquals(Route.Windshield, flow.top)
        waitTag("windshield.trips")
        shot("17-windshield-my-trips")
        compose.onNodeWithTag("windshield.trips").performClick()
        waitTag("trips.row.0")
        shot("18-trips-sheet")
        compose.onNodeWithTag("trips.row.0").performClick()
        waitTag("road.total")
        assertEquals(Route.Road, flow.top)
        assertTrue(flow.openedFromSaved)
        assertEquals("Москва → Ярославль", flow.result!!.trip.title)
        assertEquals(savedTotal, flow.result!!.trip.cost.totalRub)
        assertEquals(alt.name, flow.result!!.trip.daysList.flatMap { it.stops }.first { it.id == stop.id }.name)
        compose.onNodeWithText("К лобовому").assertExists()
        shot("19-road-from-saved")
        back()
        assertEquals(Route.Windshield, flow.top)
        waitTag("windshield.route.0")

        // D-1 delete with undo (long-press the row → dialog → «Удалить» → toast «Вернуть»).
        compose.onNodeWithTag("windshield.trips").performClick()
        waitTag("trips.row.0")
        compose.onNodeWithTag("trips.row.0").performTouchInput { longClick() }
        waitTag("delete")
        shot("20-trips-delete-dialog")
        compose.onNodeWithTag("delete.yes").performClick()
        compose.waitUntil(5_000) { flow.saved.isEmpty() && flow.canUndoDelete }
        shot("21-trip-deleted-toast")
        compose.onNodeWithTag("toast.action", useUnmergedTree = true).performClick()
        compose.waitUntil(5_000) { flow.saved.size == 1 }
        waitTag("windshield.trips")
        compose.runOnUiThread { flow.clearSaved() }
    }

    @Test
    fun readyRouteToRoadAhead() {
        waitTag("windshield.route.0")
        compose.onNodeWithText("Золотое кольцо").performClick()
        compose.waitUntil(5_000) { flow.selected?.id == "rr_golden_ring" }
        shot("08-windshield-golden-ring")
        compose.onNodeWithTag("windshield.start").performClick()
        waitTag("instruments.start")
        shot("09-instruments-golden-ring")
        compose.onNodeWithTag("instruments.start").performClick()
        val t0 = System.nanoTime()
        assertRoadAhead("ready")
        val planMs = (System.nanoTime() - t0) / 1_000_000
        shot("10-road-ahead-golden-ring")
        assertTrue(flow.result!!.trip.days >= 3)

        // 5.7 Exit: night 1 → another hotel (local first, engine after) → mock partner → «Забронировали?» → booked.
        val night = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.kind == "overnight" && it.hotelOptions.size >= 2 }
        compose.onNodeWithTag("road.hotel.${night.id}").performScrollTo().performClick()
        waitTag("exit.panel")
        assertEquals(Route.Exit, flow.top)
        shot("22-exit")
        val before = flow.result!!.trip.cost.totalRub
        val pick = night.hotelOptions[1]
        compose.onNodeWithTag("exit.option.1", useUnmergedTree = true).performScrollTo().performClick()
        compose.waitUntil(10_000) { !flow.costBusy && flow.result!!.trip.daysList.flatMap { it.stops }.first { it.id == night.id }.selectedHotelId == pick.placeId }
        Log.i("VerstE2e", "hotel ${pick.placeId} total $before → ${flow.result!!.trip.cost.totalRub}")
        shot("23-exit-other-hotel")
        compose.onNodeWithTag("exit.book").performClick()
        waitTag("partner")
        compose.onNodeWithTag("partner.badge", useUnmergedTree = true).assertExists()
        shot("24-mock-partner")
        compose.onNodeWithTag("partner.back").performScrollTo().performClick()
        waitTag("booked")
        shot("25-booked-dialog")
        compose.onNodeWithTag("booked.yes").performClick()
        compose.waitUntil(5_000) { flow.isBooked(night.id) }
        shot("26-exit-booked")
        compose.onNodeWithText("Открыть бронирование").assertExists()
        back()
        assertEquals(Route.Road, flow.top)
        compose.onNodeWithTag("road.hotel.${night.id}").performScrollTo()
        shot("27-road-booked-row")

        back()
        assertEquals(Route.Instruments, flow.top)
        back()
        assertEquals(Route.Windshield, flow.top)
        val engine = (E2e.engine.status.value as app.verst.engine.EngineStatus.Ready).info.timings
        File(E2e.dir(), "budgets.json").writeText(
            """{"engineStartMs":${engine.totalMs},"planGoldenRingMs":$planMs,"startBudgetMs":4000,"planBudgetMs":10000}""",
        )
        Log.i("VerstE2e", "budgets engine=${engine.totalMs} ms plan=$planMs ms")
        assertTrue("engine start ${engine.totalMs} ms ≤ 4000", engine.totalMs <= 4_000)
    }

    @Test
    fun errorPathAndDebugPanel() {
        waitTag("windshield.route.0")
        // DEV-127: 2 s long-press on «НАВИГАТОР» → debug panel; force UNREACHABLE for the next plan.
        compose.onNodeWithTag("windshield.debug", useUnmergedTree = true).performTouchInput { down(center); advanceEventTime(2_300); up() }
        waitTag("debug")
        compose.onNodeWithTag("debug.error.UNREACHABLE", useUnmergedTree = true).performScrollTo().performClick()
        shot("28-debug-panel")
        back()
        assertEquals(Route.Windshield, flow.top)
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.to")
        compose.onNodeWithTag("navigator.to").performTextInput("Тула")
        waitTag("navigator.suggestion.0")
        compose.onNodeWithTag("navigator.suggestion.0").performScrollTo().performClick()
        waitTag("navigator.start", 10_000)
        compose.onNodeWithTag("navigator.start").performClick()
        waitTag("instruments.start")
        compose.onNodeWithTag("instruments.start").performClick()
        waitTag("drive.error.cta", 20_000)
        shot("29-drive-error-unreachable")
        compose.onNodeWithTag("drive.error.cta").performClick() // «Изменить маршрут» → Navigator with the error
        compose.waitUntil(5_000) { flow.top == Route.Navigator && flow.routeError != null }
        shot("30-navigator-route-error")
        compose.runOnUiThread { flow.debugForceError = null }
        back()
        assertEquals(Route.Windshield, flow.top)
    }
}
