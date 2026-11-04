package app.verst.e2e

import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.test.platform.app.InstrumentationRegistry
import app.verst.VerstApp
import app.verst.engine.EngineHost
import app.verst.engine.EngineStatus
import java.io.File
import org.junit.Assert.fail

/** Shared helpers of the emulator tests: the app's engine and the pulled `files/e2e/` directory. */
object E2e {
    val engine: EngineHost
        get() = (InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as VerstApp).engine

    /**
     * S3-6 / ADR-0012 §5: CI never talks to the real Nominatim. Every journey points the client at a closed loopback
     * port (S3-6 swaps in its MockWebServer).
     */
    fun noRealNominatim() {
        val flow = (InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as VerstApp).flow
        (flow.address as? app.verst.data.net.NominatimClient)?.baseUrl = "http://127.0.0.1:9"
        // nor the phone's geocoder (the CEO 29.10 fallback): the journeys assert the Nominatim replies
        flow.addressFallback = null
        // ADR-0016 OR-6: the app-wide breaker must not carry one journey's failures into the next
        app.verst.data.net.Net.breaker.reset()
    }

    fun dir(): File =
        File(InstrumentationRegistry.getInstrumentation().targetContext.getExternalFilesDir(null), "e2e").apply { mkdirs() }

    /** Waits for the engine; returns the Ready status and the wall time waited. */
    fun awaitReady(timeoutMs: Long): Pair<EngineStatus.Ready, Long> {
        val t0 = System.nanoTime()
        while (true) {
            val waited = (System.nanoTime() - t0) / 1_000_000
            when (val s = engine.status.value) {
                is EngineStatus.Ready -> return s to waited
                is EngineStatus.Failed -> fail("engine failed: ${s.code} ${s.detail}")
                is EngineStatus.Starting -> if (waited > timeoutMs) fail("engine not ready after $timeoutMs ms (${s.phase})")
            }
            Thread.sleep(20)
        }
    }
}

/**
 * ПОЕХАЛИ on Instruments. CEO 03.11: with a child aboard the app asks where lunch may be — answered here
 * «Только в городах» (the engine's own default with a child), or «И придорожные кафе» with [roadside].
 */
fun androidx.compose.ui.test.junit4.ComposeTestRule.pressStart(flow: app.verst.nav.VerstFlow, roadside: Boolean = false) {
    onNodeWithTag("instruments.start").performClick()
    waitForIdle()
    // CEO 04.11: an approximate long trip offers the server once — the journeys stay on the phone engine
    if (flow.longTripAsk) {
        // the question itself on screen once per run (the camper design): «Visible change = seen»
        val shot = java.io.File(java.io.File(E2e.dir(), "screens").apply { mkdirs() }, "05a-long-trip-question.png")
        if (!shot.exists()) {
            Thread.sleep(300)
            InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
                ?.let { bmp -> shot.outputStream().use { bmp.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it) } }
        }
        onNodeWithTag("long.trip.no").performClick()
        waitForIdle()
    }
    if (flow.roadsideFoodAsk) {
        onNodeWithTag(if (roadside) "roadside.food.yes" else "roadside.food.no").performClick()
        waitForIdle()
    }
}
