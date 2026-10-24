package app.verst.e2e

import android.graphics.Bitmap
import android.util.Log
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTouchInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.verst.MainActivity
import app.verst.VerstApp
import app.verst.core.model.NaviLinks
import app.verst.nav.GpsState
import app.verst.nav.HandoffTarget
import app.verst.nav.Route
import java.io.File
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TestWatcher
import org.junit.runner.Description
import org.junit.runner.RunWith

/**
 * Sprint 3 round R1 on the device: focus restore (CEO 2.1), the navigator hand-off links (CEO 4) and the GPS
 * origin with the debug mock location (CEO 3). Screens 40–49.
 */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
class RoundR1Test {
    @get:Rule(order = 0) val compose = createAndroidComposeRule<MainActivity>()

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
            flow.debugHandoffDryRun = true
        }
    }

    @After
    fun cleanUp() {
        compose.runOnUiThread {
            flow.debugHandoffDryRun = false
            flow.setOffline(false)
            flow.debugResetOrigin()
            while (flow.back()) Unit
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
    }

    /** Is [tag]'s node inside the Road-ahead list viewport (not scrolled away)? */
    private fun inListViewport(tag: String): Boolean {
        val list = compose.onNodeWithTag("road.list").fetchSemanticsNode().boundsInRoot
        val row = compose.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode().boundsInRoot
        return row.top >= list.top - 1 && row.top < list.bottom && row.bottom > list.top
    }

    private fun goldenRingRoad() {
        waitTag("windshield.route.0")
        val i = (flow.windshield as app.verst.nav.WindshieldData.Routes).routes.indexOfFirst { it.id == "rr_golden_ring" }
        compose.onNodeWithTag("windshield.route.$i").performClick()
        compose.waitUntil(5_000) { flow.selected?.id == "rr_golden_ring" }
        compose.onNodeWithTag("windshield.start").performClick()
        waitTag("instruments.start")
        compose.onNodeWithTag("instruments.start").performClick()
        waitTag("road.total", 45_000)
        assertEquals(Route.Road, flow.top)
    }

    @Test
    fun focusComesBackToTheSecondNightAfterBooking() {
        goldenRingRoad()
        val nights = flow.result!!.trip.daysList.flatMap { it.stops }.filter { it.kind == "overnight" }
        assertTrue("2 nights", nights.size >= 2)
        val night = nights[1]
        assertTrue(night.hotelOptions.isNotEmpty())
        compose.onNodeWithTag("road.hotel.${night.id}").performScrollTo()
        compose.waitForIdle()
        assertTrue(inListViewport("road.stop.${night.id}"))
        shot("40-road-second-night")
        compose.onNodeWithTag("road.hotel.${night.id}").performClick()
        waitTag("exit.panel")
        assertEquals(Route.Exit, flow.top)
        compose.onNodeWithTag("exit.book").performClick()
        waitTag("partner")
        compose.onNodeWithTag("partner.back").performScrollTo().performClick()
        waitTag("booked")
        compose.onNodeWithTag("booked.yes").performClick()
        compose.waitUntil(5_000) { flow.isBooked(night.id) }
        back()
        assertEquals(Route.Road, flow.top)
        // No performScrollTo: the restore itself brings the row back (and highlights it).
        compose.waitUntil(5_000) { runCatching { inListViewport("road.stop.${night.id}") }.getOrDefault(false) }
        compose.onNodeWithTag("road.stop.${night.id}", useUnmergedTree = true).assertIsDisplayed()
        shot("41-road-focus-restored")
        compose.waitUntil(5_000) { flow.roadFocusId == null } // the highlight was shown and consumed
        // Waybill and back: the position stays (no highlight).
        compose.mainClock.advanceTimeBy(1_000)
        compose.waitForIdle()
        val top = flow.roadTopId
        compose.onNodeWithTag("road.total").performClick()
        waitTag("waybill.sheet")
        back()
        waitTag("road.total")
        compose.waitUntil(5_000) { runCatching { inListViewport("road.stop.${night.id}") }.getOrDefault(false) }
        assertEquals(top, flow.roadTopId)
    }

    @Test
    fun dayLinkAndLongPressHandOffToTheNavigatorWithViaPoints() {
        goldenRingRoad()
        val trip = flow.result!!.trip
        val d1 = trip.daysList.first()
        compose.onNodeWithTag("road.day.1.navigator", useUnmergedTree = true).performClick()
        compose.waitUntil(5_000) { flow.lastHandoff != null }
        val (h, target) = flow.lastHandoff!!
        Log.i("VerstE2e", "handoff day 1 $target navi=${h.navi} web=${h.web}")
        assertEquals(if (flow.navigatorInstalled) HandoffTarget.NavigatorDryRun else HandoffTarget.BrowserDryRun, target)
        assertEquals(NaviLinks.day(d1), h)
        assertTrue(h.navi!!.startsWith("yandexnavi://build_route_on_map?lat_from=${NaviLinks.coord(d1.stops.first().lat!!)}"))
        assertTrue(h.navi!!.contains("lat_via_0=${NaviLinks.coord(d1.stops[1].lat!!)}"))
        assertTrue(h.web.startsWith("https://yandex.ru/maps/?rtext="))

        // Long-press a row → D-5 → «ОТКРЫТЬ В НАВИГАТОРЕ ОТСЮДА».
        val stop = d1.stops[1]
        compose.onNodeWithTag("road.stop.${stop.id}").performScrollTo().performTouchInput { longClick() }
        waitTag("stopmenu")
        assertEquals(stop.id, flow.stopMenu?.id)
        shot("42-stop-menu")
        compose.onNodeWithTag("stopmenu.navigator", useUnmergedTree = true).performClick()
        compose.waitUntil(5_000) { flow.stopMenu == null }
        val from = flow.lastHandoff!!.first
        assertEquals(NaviLinks.fromStop(trip, stop.id), from)
        assertTrue(from.navi!!.contains("lat_from=${NaviLinks.coord(stop.lat!!)}"))
        assertTrue(from.navi!!.contains("lat_to=${NaviLinks.coord(d1.stops.last().lat!!)}"))

        // Offline: the day link reads «в навигатор» and explains itself.
        compose.runOnUiThread { flow.setOffline(true) }
        compose.waitUntil(5_000) { compose.onAllNodes(androidx.compose.ui.test.hasText("в навигатор"), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty() }
        val before = flow.lastHandoff
        compose.onNodeWithTag("road.day.1.navigator", useUnmergedTree = true).performClick()
        compose.onNodeWithText("Нужен интернет, чтобы открыть навигатор").assertExists()
        assertEquals(before, flow.lastHandoff)
        shot("43-road-offline-navigator")
    }

    @Test
    fun locationRationaleDenyThenMockLocationSetsTheOrigin() {
        compose.runOnUiThread { flow.debugResetOrigin() }
        waitTag("windshield.navi")
        // First «Куда угодно»: the rationale; «Не разрешать» keeps Москва.
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.location")
        shot("44-navigator-location-rationale")
        compose.onNodeWithTag("navigator.location.deny", useUnmergedTree = true).performClick()
        compose.onNodeWithText("Хорошо, старт — Москва. Изменить можно в навигаторе").assertExists()
        assertFalse(flow.locationPrompt)
        assertEquals("Москва", flow.origin.label)
        shot("45-navigator-location-denied")
        back()

        // Debug panel → mock location «Ярославль» → the origin is the nearest town, «ВЫ: ЯРОСЛАВЛЬ».
        compose.runOnUiThread { flow.openDebug() }
        waitTag("debug")
        compose.onNodeWithTag("debug.mock.Ярославль", useUnmergedTree = true).performScrollTo().performClick()
        compose.waitUntil(15_000) { flow.gps == GpsState.On && flow.origin.label == "Ярославль" }
        assertTrue(flow.originFromGps)
        shot("46-debug-mock-location")
        back()
        waitTag("windshield.navi")
        compose.onNodeWithText("ВЫ: ЯРОСЛАВЛЬ").assertExists()
        compose.waitUntil(20_000) { flow.windshield is app.verst.nav.WindshieldData.Routes || flow.windshield is app.verst.nav.WindshieldData.NoRoutes }
        shot("47-windshield-gps-origin")
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.gps.on")
        shot("48-navigator-gps-on")
        back()
    }
}
