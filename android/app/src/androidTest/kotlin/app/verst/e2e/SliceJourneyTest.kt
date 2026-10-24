package app.verst.e2e

import android.graphics.Bitmap
import android.util.Log
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.verst.MainActivity
import app.verst.VerstApp
import app.verst.nav.Route
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * DEV-SLICE journey on the real engine: Windshield → (own route) Navigator → Instruments → Drive → Road ahead,
 * back to the Windshield, then a ready route → Instruments → Drive → Road ahead. Screens go to
 * `files/e2e/screens/NN-name.png` (ci-logs `runs/<R>/e2e/screens/`).
 */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
class SliceJourneyTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    private val flow get() = (InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as VerstApp).flow

    @Before
    fun toRoot() {
        E2e.awaitReady(30_000)
        compose.runOnUiThread { while (flow.back()) Unit }
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

    private fun totalText(): String {
        val node = compose.onNodeWithTag("road.total.amount", useUnmergedTree = true).fetchSemanticsNode()
        return node.config.getOrNull(SemanticsProperties.Text)?.joinToString("") { it.text }.orEmpty()
    }

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
        compose.onNodeWithTag("navigator.suggestion.0").performClick()
        waitTag("navigator.start", 10_000)
        compose.onNodeWithTag("navigator.start").assertIsEnabled()
        shot("03-navigator-picked")
        compose.onNodeWithTag("navigator.start").performClick()

        waitTag("instruments.start")
        compose.onNodeWithTag("instruments.seat.0").performClick()
        compose.onNodeWithTag("instruments.seat.0").performClick() // adult → child
        shot("04-instruments")
        assertEquals(1, flow.children)
        compose.onNodeWithTag("instruments.start").performClick()

        waitTag("drive.back")
        shot("05-drive")
        assertRoadAhead("own")
        shot("06-road-ahead")
        assertEquals("Москва → Ярославль", flow.result!!.trip.title)
        compose.onNodeWithTag("road.list").performScrollToIndex(5)
        shot("07-road-ahead-scrolled")

        back()
        assertEquals(Route.Instruments, flow.top)
        back()
        assertEquals(Route.Navigator, flow.top)
        back()
        assertEquals(Route.Windshield, flow.top)
        waitTag("windshield.route.0")
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
        assertRoadAhead("ready")
        shot("10-road-ahead-golden-ring")
        assertTrue(flow.result!!.trip.days >= 3)
        back()
        assertEquals(Route.Instruments, flow.top)
        back()
        assertEquals(Route.Windshield, flow.top)
    }
}
