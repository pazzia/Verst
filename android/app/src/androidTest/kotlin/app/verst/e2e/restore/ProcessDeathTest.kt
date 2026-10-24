package app.verst.e2e.restore

import android.graphics.Bitmap
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.verst.MainActivity
import app.verst.VerstApp
import app.verst.e2e.E2e
import app.verst.nav.Route
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Release review P1-2 / M§11 step 8. `run_e2e.sh` runs the two phases as separate instrumentations (each a
 * fresh app process) with HOME + `am force-stop` + `am kill` between them: after the relaunch Road ahead shows
 * the same, unsaved trip (restored from `files/trips/last.json`).
 */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
class ProcessDeathTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    private val flow get() = (InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as VerstApp).flow
    private val marker get() = File(E2e.dir(), "process-death.txt")

    private fun waitTag(tag: String, ms: Long = 30_000) =
        compose.waitUntil(ms) { compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty() }

    private fun shot(name: String) {
        compose.waitForIdle()
        Thread.sleep(300)
        val dir = File(E2e.dir(), "screens").apply { mkdirs() }
        val bmp = InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
        File(dir, "$name.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    @Test
    fun phase1PlanAndLeave() {
        E2e.awaitReady(30_000)
        compose.runOnUiThread { while (flow.back()) Unit }
        waitTag("windshield.navi")
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.to")
        compose.onNodeWithTag("navigator.to").performTextInput("Яро")
        waitTag("navigator.suggestion.0")
        compose.onNodeWithTag("navigator.suggestion.0").performScrollTo().performClick()
        waitTag("navigator.start", 10_000)
        compose.onNodeWithTag("navigator.start").performClick()
        waitTag("instruments.start")
        compose.onNodeWithTag("instruments.start").performClick()
        waitTag("road.total", 45_000)
        assertEquals(Route.Road, flow.top)
        val trip = flow.result!!.trip
        assertTrue("unsaved", flow.savedId == null)
        // S3-R1: scroll down; the top visible row goes to last.json with the trip.
        val last = trip.daysList.last().stops.last()
        compose.onNodeWithTag("road.stop.${last.id}").performScrollTo()
        // The top row is reported 250 ms after scrolling settles (composition time: advance the test clock).
        compose.mainClock.advanceTimeBy(1_000)
        compose.waitUntil(5_000) { flow.roadTopId != null }
        val top = flow.roadTopId!!
        Thread.sleep(1_500) // last.json is written 300 ms after a change
        marker.writeText("${trip.title}|${trip.km}|${trip.cost.totalRub}|$top")
        shot("31-before-process-death")
    }

    @Test
    fun phase2RelaunchRestoresRoadAhead() {
        val (title, km, total, top) = marker.readText().split("|")
        waitTag("road.total", 20_000) // no engine needed: the trip comes from last.json
        assertEquals(Route.Road, flow.top)
        val trip = flow.result!!.trip
        assertEquals(title, trip.title)
        assertEquals(km.toInt(), trip.km)
        assertEquals(total.toInt(), trip.cost.totalRub)
        compose.onNodeWithTag("road.back", useUnmergedTree = true).assertExists()
        // S3-R1: the scroll position comes back too (the row that was on top is in view).
        assertEquals(top, flow.roadTopId)
        compose.waitUntil(5_000) {
            val list = compose.onNodeWithTag("road.list").fetchSemanticsNode().boundsInRoot
            val row = compose.onNodeWithTag("road.stop.$top", useUnmergedTree = true).fetchSemanticsNode().boundsInRoot
            row.bottom > list.top && row.top < list.bottom
        }
        compose.onNodeWithText("Дорога впереди").assertExists()
        shot("32-restored-after-process-death")
        compose.runOnUiThread { while (flow.back()) Unit }
        assertEquals(Route.Windshield, flow.top)
    }
}
