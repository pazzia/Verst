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
import app.verst.nav.closeHandoffSheet
import app.verst.nav.isBooked
import app.verst.nav.navigatorInstalled

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
        E2e.noRealNominatim()
        compose.runOnUiThread {
            while (flow.back()) Unit
            flow.clearSaved()
            flow.debugForceError = null
            flow.debugHandoffDryRun = true
            flow.debugLocationAnswered()
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
    fun dayMenuAndStopMenuHandOffTheEngineLinks() {
        goldenRingRoad()
        val r = flow.result!!
        val gateway = app.verst.engine.ChaquopyPlannerGateway(E2e.engine, app.verst.core.model.DefaultWorld)
        // 5.13 §5 (S4): «вести» of day 1 → the hand-off sheet with the engine's v3 links (ADR-0015 §1).
        compose.onNodeWithTag("road.day.1.navigator", useUnmergedTree = true).performClick()
        waitTag("handoff")
        compose.waitUntil(10_000) { flow.handoffSheet?.handoff != null }
        shot("42-handoff-sheet")
        val engineDay = kotlinx.coroutines.runBlocking { gateway.handoff(r.tripJson, app.verst.core.model.HandoffArgs.day(1)) }
        val dayLinks = (engineDay as app.verst.core.model.EngineResult.Ok).value.parts.first().links
        assertEquals(dayLinks, flow.handoffSheet!!.handoff!!.parts.first().links)
        assertTrue(dayLinks.maps!!.startsWith("yandexmaps://maps.yandex.ru/?rtext="))
        assertTrue(dayLinks.navigatorNext!!.startsWith("yandexnavi://build_route_on_map?lat_to="))
        assertTrue(dayLinks.web!!.startsWith("https://yandex.ru/maps/?rtext="))
        // unsigned: Карты first with the whole day («весь день»)
        compose.onNodeWithTag("handoff.maps.badge", useUnmergedTree = true).assertExists()
        compose.onNodeWithTag("handoff.maps", useUnmergedTree = true).performClick()
        compose.waitUntil(5_000) { flow.lastHandoff != null }
        val (links, target) = flow.lastHandoff!!
        Log.i("VerstE2e", "handoff day 1 $target maps=${links.maps} web=${links.web}")
        val mapsApp = flow.handoffLauncher?.mapsInstalled() == true
        assertEquals(if (mapsApp) HandoffTarget.MapsDryRun else HandoffTarget.BrowserDryRun, target)
        assertEquals(dayLinks.maps, links.maps)
        assertEquals(dayLinks.web, links.web)
        // «До след.» → the Навигатор gets the next point only
        compose.onNodeWithTag("road.handoff", useUnmergedTree = true).performScrollTo().performClick()
        waitTag("handoff")
        compose.waitUntil(10_000) { flow.handoffSheet?.handoff != null }
        compose.onNodeWithTag("handoff.tab.next", useUnmergedTree = true).performClick()
        compose.waitUntil(5_000) { flow.handoffSheet?.day == null }
        shot("42b-handoff-next")
        if (flow.navigatorInstalled) {
            compose.onNodeWithTag("handoff.navi", useUnmergedTree = true).performClick()
            compose.waitUntil(5_000) { flow.lastHandoff?.second == HandoffTarget.NavigatorDryRun }
            assertEquals(dayLinks.navigatorNext, flow.lastHandoff!!.first.navigator)
        } else {
            compose.onNodeWithTag("handoff.navi.install", useUnmergedTree = true).assertExists()
            compose.runOnUiThread { flow.closeHandoffSheet() }
        }

        // Long-press a row → D-5 → «Открыть в навигаторе отсюда».
        val stop = r.trip.daysList.first().stops[1]
        compose.onNodeWithTag("road.stop.${stop.id}").performScrollTo().performTouchInput { longClick() }
        waitTag("stopmenu")
        assertEquals(stop.id, flow.stopMenu?.id)
        compose.waitUntil(10_000) { flow.stopHandoff != null }
        shot("43-stop-menu")
        compose.onNodeWithTag("stopmenu.navigator", useUnmergedTree = true).performClick()
        compose.waitUntil(5_000) { flow.stopMenu == null }
        val from = flow.lastHandoff!!.first
        val engineStop = kotlinx.coroutines.runBlocking { gateway.handoff(r.tripJson, app.verst.core.model.HandoffArgs.fromStop(stop.id)) }
        assertEquals((engineStop as app.verst.core.model.EngineResult.Ok).value.parts.first().links, from)

        // Offline without the Карты app: the button keeps its look; the tap explains it (5.13 §3).
        compose.runOnUiThread { flow.setOffline(true) }
        val before = flow.lastHandoff
        compose.onNodeWithTag("road.day.1.navigator", useUnmergedTree = true).performScrollTo().performClick()
        waitTag("handoff")
        compose.waitUntil(10_000) { flow.handoffSheet?.handoff != null }
        compose.onNodeWithTag("handoff.maps", useUnmergedTree = true).performClick()
        if (flow.handoffLauncher?.mapsInstalled() != true) {
            compose.onNodeWithText("открыть карту в браузере", substring = true).assertExists()
            assertEquals(before, flow.lastHandoff)
        }
        shot("44-handoff-offline")
    }

    @Test
    fun locationRationaleManualThenMockLocationSetsTheOrigin() {
        compose.runOnUiThread { flow.debugResetOrigin() }
        waitTag("windshield.navi")
        // 5.12: the first «Куда угодно» shows «Откуда поедем?»; «Выберу сам» opens the ОТКУДА input, Москва stays.
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("location")
        shot("45-location-rationale")
        compose.onNodeWithTag("location.manual", useUnmergedTree = true).performClick()
        compose.waitUntil(5_000) { !flow.locationSheet && flow.editingFrom }
        assertEquals("Москва", flow.origin.label)
        back()
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
