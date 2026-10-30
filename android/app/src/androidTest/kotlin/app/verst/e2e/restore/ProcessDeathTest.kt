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
    @get:Rule(order = 0) val compose = createAndroidComposeRule<MainActivity>()

    @get:Rule(order = 1) val onFailure = object : org.junit.rules.TestWatcher() {
        override fun failed(e: Throwable?, description: org.junit.runner.Description) {
            runCatching {
                android.util.Log.i("VerstE2e", "ProcessDeath failed: top=${flow.top} stack=${flow.stack} toast=${flow.toast} result=${flow.result != null}")
                shot("zz-failed-${description.methodName}")
            }
        }
    }

    private val flow get() = (InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as VerstApp).flow
    private val marker get() = File(E2e.dir(), "process-death.txt")

    private fun waitTag(tag: String, ms: Long = 30_000) =
        compose.waitUntil(ms) { compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty() }

    private fun has(tag: String) = compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty()

    private fun back() = compose.runOnUiThread { compose.activity.onBackPressedDispatcher.onBackPressed() }

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
        E2e.noRealNominatim()
        compose.runOnUiThread {
            while (flow.back()) Unit
            // Earlier tests (Sprint4Test GPS cases) leave the origin at Ярославль; planning «Яро» from there is
            // a 0 km trip (TOO_SHORT, PR #1 run 128). Pin the default origin like Sprint4Test/Sprint4DataTest do.
            flow.debugResetOrigin()
            flow.debugLocationAnswered()
        }
        assertEquals("Москва", flow.origin.label)
        waitTag("windshield.navi")
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.to")
        compose.onNodeWithTag("navigator.to").performTextInput("Яро")
        // the town, not the first row: with the catalogue loaded a POI («Ярославский вокзал», in Москва) can lead
        // the list, and a trip to it ends on the Drive error (the runs 94 / 101 / 112 flake)
        compose.waitUntil(15_000) { flow.suggestions.any { it.name == "Ярославль" } }
        val i = flow.suggestions.indexOfFirst { it.name == "Ярославль" }
        android.util.Log.i("VerstE2e", "ProcessDeath suggestions: ${flow.suggestions.map { "${it.kind}:${it.name}" }}")
        compose.onNodeWithTag("navigator.suggestion.$i").performScrollTo().performClick()
        waitTag("navigator.start", 10_000)
        compose.onNodeWithTag("navigator.start").performClick()
        waitTag("instruments.start")
        android.util.Log.i("VerstE2e", "ProcessDeath instruments: mood=${flow.mood} budget=${flow.budgetIndex} seats=${flow.seats.toList()} dog=${flow.dog}")
        val t0 = System.nanoTime()
        compose.onNodeWithTag("instruments.start").performClick()
        // diagnostics (runs 94 / 101): how long the first plan of a fresh process takes
        compose.waitUntil(150_000) { flow.top == Route.Road || flow.top == Route.NoFit || has("drive.error.cta") }
        android.util.Log.i("VerstE2e", "ProcessDeath after start: top=${flow.top} after ${(System.nanoTime() - t0) / 1_000_000} ms error=${flow.drive.error} lines=${flow.drive.lines}")
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
