package app.verst.e2e.gps

import android.graphics.Bitmap
import android.util.Log
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.verst.MainActivity
import app.verst.VerstApp
import app.verst.e2e.E2e
import app.verst.nav.GpsState
import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * S3-R1 GPS on the emulator's real location stack: `run_e2e.sh` grants the location permission and feeds
 * `adb emu geo fix` (Тула) while this runs as its own instrumentation, last (a granted permission changes what
 * the other journeys see). «Моё местоположение» → LocationManager fix → the nearest town → «ВЫ: ТУЛА».
 */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
class RealGpsTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    private val flow get() = (InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as VerstApp).flow

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
    fun myLocationUsesTheDeviceFix() {
        E2e.awaitReady(30_000)
        compose.runOnUiThread {
            while (flow.back()) Unit
            flow.debugResetOrigin()
        }
        assertTrue("permission granted by run_e2e.sh", flow.locator?.granted() == true)
        waitTag("windshield.navi")
        compose.onNodeWithTag("windshield.navi").performClick()
        // Granted and not asked yet: opening «Куда угодно» locates by itself.
        compose.waitUntil(60_000) { flow.gps == GpsState.On || flow.gps == GpsState.Failed }
        Log.i("VerstE2e", "auto gps ${flow.gps} origin=${flow.origin}")
        assertTrue("auto gps ${flow.gps}", flow.gps == GpsState.On)
        // «изменить» → «Моё местоположение» locates again and closes ОТКУДА.
        waitTag("navigator.change")
        compose.onNodeWithTag("navigator.change").performClick()
        waitTag("navigator.mylocation")
        compose.onNodeWithTag("navigator.mylocation").performClick()
        compose.waitUntil(60_000) { flow.gps == GpsState.On && !flow.editingFrom }
        Log.i("VerstE2e", "real gps ${flow.gps} origin=${flow.origin}")
        assertTrue("gps ${flow.gps}", flow.gps == GpsState.On)
        assertTrue(flow.origin.toString(), flow.origin.label == "Тула")
        waitTag("navigator.gps.on")
        shot("49-navigator-real-gps")
        compose.runOnUiThread { flow.back() }
        waitTag("windshield.navi")
        compose.onNodeWithText("ВЫ: ТУЛА").assertExists()
        shot("50-windshield-real-gps")
        compose.runOnUiThread { flow.debugResetOrigin() }
    }
}
