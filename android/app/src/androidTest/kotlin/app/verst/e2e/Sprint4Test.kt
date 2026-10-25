package app.verst.e2e

import android.graphics.Bitmap
import android.util.Log
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.verst.MainActivity
import app.verst.VerstApp
import app.verst.core.model.GeoPoint
import app.verst.data.net.Net
import app.verst.data.net.NominatimClient
import app.verst.data.net.OnlineStats
import app.verst.nav.AddressState
import app.verst.nav.GpsState
import app.verst.nav.Route
import app.verst.nav.Seat
import java.io.File
import java.util.concurrent.TimeUnit
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TestWatcher
import org.junit.runner.Description
import org.junit.runner.RunWith

/**
 * Sprint 4 journeys on the real engine: ADR-0016 OR-1…OR-8 (CEO: airplane mode, a slow network, HTTP 500 and
 * garbage replies — nothing online may ever show an error) and the city mode on the walk screen (filters rebuild in
 * place, bugs (a)(b)(c)). Screens 100–119.
 */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
class Sprint4Test {
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
            flow.frontAdult = true
            for (i in flow.seats.indices) flow.seats[i] = Seat.EMPTY
        }
    }

    @After
    fun cleanUp() {
        compose.runOnUiThread {
            flow.debugHandoffDryRun = false
            flow.setOffline(false)
            flow.debugResetOrigin()
            flow.debugLocationAnswered()
            while (flow.back()) Unit
        }
        E2e.noRealNominatim()
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
        compose.waitUntil(timeoutMs) { has(tag) }
    }

    private fun has(tag: String) = compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty()

    private fun back() {
        compose.runOnUiThread { compose.activity.onBackPressedDispatcher.onBackPressed() }
    }

    /** Nothing that looks like an error surfaced: no error screen, no dialog, no «Ошибка». */
    private fun noErrorShown() {
        assertTrue("no engine error screen", !has("drive.error.cta"))
        assertTrue("no «Ошибка» anywhere", compose.onAllNodes(androidx.compose.ui.test.hasText("Ошибка", substring = true), useUnmergedTree = true).fetchSemanticsNodes().isEmpty())
    }

    private fun goldenRingRoad() {
        waitTag("windshield.route.0")
        val i = (flow.windshield as app.verst.nav.WindshieldData.Routes).routes.indexOfFirst { it.id == "rr_golden_ring" }
        assertTrue(i >= 0)
        compose.onNodeWithTag("windshield.route.$i").performClick()
        compose.waitUntil(5_000) { flow.selected?.id == "rr_golden_ring" }
        compose.onNodeWithTag("windshield.start").performClick()
        waitTag("instruments.start")
        compose.onNodeWithTag("instruments.start").performClick()
        waitTag("road.total", 60_000)
    }

    /** OR: airplane mode from launch — plan, Road ahead, a card, the Waybill, save and a walk all work; 0 requests. */
    @Test
    fun s4AirplaneModeEverythingWorksAndNothingIsSent() {
        val server = MockWebServer().apply { start() }
        try {
            val base = server.url("/").toString() // MockWebServer resolves its host: not on the main thread
            compose.runOnUiThread {
                (flow.address as NominatimClient).baseUrl = base
                flow.setOffline(true)
            }
            OnlineStats.reset()
            goldenRingRoad()
            shot("100-airplane-road")
            noErrorShown()
            // a card: offline data, the quiet «уточним при интернете» at most, never an error
            val sight = flow.result!!.trip.daysList.flatMap { it.stops }.first { it.kind == "sight" }
            compose.onNodeWithTag("road.stop.${sight.id}").performScrollTo().performClick()
            waitTag("card")
            compose.waitUntil(20_000) { has("photo.offline") || has("photo.none") || has("photo.loaded") }
            shot("101-airplane-card")
            noErrorShown()
            back()
            compose.waitUntil(5_000) { flow.card == null }
            compose.onNodeWithTag("road.save").performClick()
            compose.waitUntil(5_000) { flow.savedCurrent }
            compose.onNodeWithTag("road.total").performClick()
            waitTag("waybill.sheet")
            shot("102-airplane-waybill")
            back()
            waitTag("road.total")
            // the address search says it waits for the internet; a walk still builds
            compose.runOnUiThread { while (flow.back()) Unit }
            waitTag("windshield.navi")
            compose.onNodeWithTag("windshield.navi").performClick()
            waitTag("navigator.to")
            compose.onNodeWithTag("navigator.to").performTextInput("Советская 1")
            waitTag("address.offline", 10_000)
            shot("103-airplane-address")
            compose.runOnUiThread { while (flow.back()) Unit }
            compose.runOnUiThread {
                flow.debugMockLocation = GeoPoint("Ярославль", 57.6261, 39.8845)
                flow.locate()
            }
            compose.waitUntil(15_000) { flow.gps == GpsState.On && flow.origin.label == "Ярославль" }
            compose.onNodeWithTag("windshield.city").performClick()
            waitTag("city.preset.overview", 20_000)
            compose.runOnUiThread { flow.selectCityPreset("overview") }
            compose.onNodeWithTag("city.go").performClick()
            compose.waitUntil(30_000) { flow.top == Route.Walk }
            waitTag("walk.total")
            shot("104-airplane-walk")
            noErrorShown()
            assertEquals("the mock server saw nothing", 0, server.requestCount)
            assertEquals("no request left the app: ${OnlineStats.snapshot()}", 0, OnlineStats.total)
        } finally {
            server.shutdown()
        }
    }

    private fun addressSearch(server: MockWebServer, q: String) {
        val base = server.url("/").toString()
        compose.runOnUiThread {
            while (flow.back()) Unit
            Net.breaker.reset()
            (flow.address as NominatimClient).baseUrl = base
        }
        waitTag("windshield.navi")
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.to")
        compose.onNodeWithTag("navigator.to").performTextInput(q)
        waitTag("address.find", 10_000)
        compose.onNodeWithTag("address.find").performScrollTo().performClick()
    }

    /** OR-1: a slow server (2 s latency, a 20 KB/s body) — the screen stays usable, the call ends at the limits. */
    @Test
    fun s4SlowNetworkStaysUsable() {
        val server = MockWebServer().apply { start() }
        try {
            // headers after 7 s: beyond the 5 s read timeout on both attempts → «уточним при интернете»
            repeat(2) { server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("[]").setHeadersDelay(7, TimeUnit.SECONDS)) }
            val t0 = System.nanoTime()
            addressSearch(server, "Советская 1")
            // the screen answers at once (the field and the towns stay usable)
            compose.onNodeWithTag("navigator.to").assertExists()
            compose.waitUntil(16_000) { flow.addressState == AddressState.Later }
            val ms = (System.nanoTime() - t0) / 1_000_000
            Log.i("VerstE2e", "S4 slow address search ended after $ms ms, requests=${server.requestCount}")
            assertTrue("ended within the OR-1 call limit: $ms", ms < 16_000)
            waitTag("address.later")
            shot("105-slow-address")
            noErrorShown()
            // a slow but steady body (2 s latency, 20 KB/s) still arrives and is used
            server.enqueue(
                MockResponse().setHeader("Content-Type", "application/json").setHeadersDelay(2, TimeUnit.SECONDS).throttleBody(20 * 1024, 1, TimeUnit.SECONDS)
                    .setBody("""[{"place_id": 1, "lat": "57.6266", "lon": "39.8938", "address": {"house_number": "1", "road": "Советская улица", "city": "Ярославль"}}]"""),
            )
            addressSearch(server, "Советская 2")
            waitTag("address.row.0", 15_000)
            shot("106-slow-address-arrived")
        } finally {
            server.shutdown()
        }
    }

    /** OR: HTTP 500 (one retry), 429 (none) and garbage (HTML, truncated JSON, wrong types, 5 MB) → no data, no error. */
    @Test
    fun s4Http500AndGarbageRepliesShowNoError() {
        val server = MockWebServer().apply { start() }
        try {
            server.enqueue(MockResponse().setResponseCode(500))
            server.enqueue(MockResponse().setResponseCode(503))
            addressSearch(server, "Советская 1")
            compose.waitUntil(15_000) { flow.addressState == AddressState.Later }
            assertEquals("one retry", 2, server.requestCount)
            waitTag("address.later")
            shot("107-http-500")
            noErrorShown()
            val garbage = listOf(
                MockResponse().setHeader("Content-Type", "text/html").setBody("<html><body>502 Bad Gateway</body></html>"),
                MockResponse().setHeader("Content-Type", "application/json").setBody("""[{"place_id": 1, "lat": "57."""),
                MockResponse().setHeader("Content-Type", "application/json").setBody("[" + "\"x\",".repeat(1_250_000) + "\"x\"]"),
            )
            garbage.forEachIndexed { i, r ->
                server.enqueue(r)
                addressSearch(server, "Тверская ${i + 2}")
                compose.waitUntil(15_000) { flow.addressState == AddressState.Later }
                noErrorShown()
            }
            shot("108-garbage")
            // wrong types: the rows are skipped → «ничего не нашли», still no error
            server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""[{"lat": {"x": 1}, "lon": [1]}, 42, null]"""))
            addressSearch(server, "Ленина 5")
            compose.waitUntil(15_000) { flow.addressState == AddressState.None }
            noErrorShown()
            val host = server.url("/").host // test thread
            Log.i("VerstE2e", "S4 online stats ${OnlineStats.snapshot()}")
            assertTrue("garbage counted (OR-8)", (OnlineStats.snapshot()[host]?.dropped ?: 0) >= 3)
            // the planner never waits for any of it
            compose.runOnUiThread { while (flow.back()) Unit }
            goldenRingRoad()
            noErrorShown()
        } finally {
            server.shutdown()
        }
    }

    /** S4 city mode: on the walk screen a filter change rebuilds in place, «Другой вариант» never leaves 5.11. */
    @Test
    fun s4WalkFiltersRebuildOnTheWalkScreen() {
        compose.runOnUiThread {
            flow.debugMockLocation = GeoPoint("Ярославль", 57.6261, 39.8845)
            flow.locate()
        }
        compose.waitUntil(15_000) { flow.gps == GpsState.On && flow.origin.label == "Ярославль" }
        compose.onNodeWithTag("windshield.city").performClick()
        waitTag("city.preset.overview", 20_000)
        shot("110-city-start")
        compose.onNodeWithTag("city.go").performClick()
        compose.waitUntil(30_000) { flow.top == Route.Walk }
        waitTag("walk.total")
        val first = flow.walk!!
        Log.i("VerstE2e", "S4 walk 4 h: ${first.walkKm} km ${first.stops.size} stops")
        // the duration filter → 2 h: rebuilt on 5.11 (debounced), still on the walk screen
        compose.onNodeWithTag("walk.filter.duration").performClick()
        waitTag("city.picker")
        compose.onNodeWithTag("city.duration.120").performClick()
        compose.onNodeWithTag("city.picker.done").performClick()
        compose.waitUntil(30_000) { flow.walk !== first && !flow.walkBuilding }
        assertEquals(Route.Walk, flow.top)
        assertEquals(120, flow.cityDurationMin)
        shot("111-walk-rebuilt-2h")
        // «Другой вариант» until the town runs out: never leaves 5.11 (bug (b))
        var guard = 0
        while (!flow.walkOtherNone && guard++ < 6 && has("walk.other")) {
            compose.onNodeWithTag("walk.other").performScrollTo().performClick()
            compose.waitUntil(30_000) { !flow.walkBuilding }
            assertEquals(Route.Walk, flow.top)
        }
        shot("112-walk-other")
        // back and reopen: the custom values persist (bug (c))
        back()
        compose.waitUntil(5_000) { flow.top == Route.City }
        assertEquals(120, flow.cityDurationMin)
        // «без ограничения» (M4): no times, the hours of each place
        compose.runOnUiThread { flow.selectCityPreset("overview") }
        compose.onNodeWithTag("city.duration.unlimited").performScrollTo().performClick()
        compose.onNodeWithTag("city.go").performClick()
        compose.waitUntil(30_000) { flow.top == Route.Walk || flow.cityError != null || flow.walkFew != null || flow.toast != null }
        Log.i("VerstE2e", "S4 unlimited walk: top=${flow.top} untimed=${flow.walk?.untimed} stops=${flow.walk?.stops?.size} key=${flow.walk?.requestKey} error=${flow.cityError} toast=${flow.toast}")
        shot("113-walk-unlimited")
        noErrorShown()
        assertEquals(Route.Walk, flow.top)
        assertTrue("an untimed walk", flow.walk!!.untimed)
        assertTrue("every stop has today's hours", flow.walk!!.stops.all { it.hours != null })
        waitTag("walk.header")
        // the dog: «Прогулка с собакой» first, outdoor kinds only
        back()
        compose.waitUntil(5_000) { flow.top == Route.City }
        compose.onNodeWithTag("city.crew.dog").performScrollTo().performClick()
        compose.waitUntil(5_000) { flow.cityDog }
        if (flow.visibleCityPresets().any { it.preset == "dog_walk" && it.available }) {
            compose.runOnUiThread { flow.selectCityPreset("dog_walk") }
            compose.runOnUiThread { flow.setCityDuration(120) }
            compose.onNodeWithTag("city.go").performClick()
            compose.waitUntil(30_000) { flow.top == Route.Walk && flow.walk?.preset == "dog_walk" || flow.walkFew != null || flow.toast != null }
            Log.i("VerstE2e", "S4 dog walk: ${flow.walk?.titleRu} kinds=${flow.walk?.stops?.map { it.kind }} warnings=${flow.walk?.warnings?.map { it.code }}")
            shot("114-walk-dog")
            noErrorShown()
            if (flow.top == Route.Walk) assertTrue("no indoor stop on a dog walk", flow.walk!!.stops.none { it.indoor })
        } else {
            Log.i("VerstE2e", "S4 dog walk preset not offered in ${flow.cityPresets?.town?.name}: ${flow.cityPresets?.presets?.map { it.preset }}")
        }
        compose.runOnUiThread { flow.pickCityDog(false) }
    }
}
