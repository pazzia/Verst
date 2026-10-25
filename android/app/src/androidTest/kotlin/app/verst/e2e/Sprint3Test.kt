package app.verst.e2e

import android.graphics.Bitmap
import android.util.Log
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.performTextClearance
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.verst.MainActivity
import app.verst.VerstApp
import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.engine.ChaquopyPlannerGateway
import app.verst.nav.GpsState
import app.verst.nav.HandoffTarget
import app.verst.nav.Route
import app.verst.nav.Seat
import java.io.File
import java.util.UUID
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import app.verst.core.model.dto.BudgetOptionDto
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TestWatcher
import org.junit.runner.Description
import org.junit.runner.RunWith

/**
 * Sprint 3 journeys S3-1…S3-6 (docs/backlog-sprint3.md DEV-309) on the real engine and `russia_v1`.
 * Screens 60–79; budgets go to `files/e2e/budgets_s3.json`.
 */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
class Sprint3Test {
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
            flow.debugLocationAnswered()
            // the default crew and budget for the journeys after this class
            flow.frontAdult = true
            for (i in flow.seats.indices) flow.seats[i] = Seat.EMPTY
            flow.dog = false
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

    private fun has(tag: String) = compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty()

    private fun back() {
        compose.runOnUiThread { compose.activity.onBackPressedDispatcher.onBackPressed() }
    }

    private fun budgets(key: String, value: Long) {
        val f = File(E2e.dir(), "budgets_s3.json")
        val j = if (f.exists()) JSONObject(f.readText()) else JSONObject()
        f.writeText(j.put(key, value).toString(2))
    }

    private fun inListViewport(list: String, tag: String): Boolean {
        val l = compose.onNodeWithTag(list).fetchSemanticsNode().boundsInRoot
        val r = compose.onNodeWithTag(tag, useUnmergedTree = true).fetchSemanticsNode().boundsInRoot
        return r.bottom > l.top && r.top < l.bottom
    }

    private fun focused(tag: String): Boolean = runCatching {
        compose.onNodeWithTag(tag).fetchSemanticsNode().config.getOrElse(androidx.compose.ui.semantics.SemanticsProperties.Focused) { false }
    }.getOrDefault(false)

    private fun goldenRingRoad(): List<app.verst.core.model.dto.StopDto> {
        readyRoute("rr_golden_ring")
        compose.onNodeWithTag("instruments.start").performClick()
        waitTag("road.total", 60_000)
        return flow.result!!.trip.daysList.flatMap { it.stops }
    }

    private fun readyRoute(id: String) {
        waitTag("windshield.route.0")
        val i = (flow.windshield as app.verst.nav.WindshieldData.Routes).routes.indexOfFirst { it.id == id }
        assertTrue("$id on the sign", i >= 0)
        compose.onNodeWithTag("windshield.route.$i").performClick()
        compose.waitUntil(5_000) { flow.selected?.id == id }
        compose.onNodeWithTag("windshield.start").performClick()
        waitTag("instruments.start")
    }

    /** S3-1: Золотое кольцо, 4 adults + 1 child + dog, budget 30 000 → fitted ≤ 31 500, or the no-fit screen → Тула → fits. */
    @Test
    fun s31CeoBudgetCaseFitsOrShowsTheNoFitScreen() {
        readyRoute("rr_golden_ring")
        compose.runOnUiThread {
            flow.frontAdult = true // driver + front passenger
            flow.seats[0] = Seat.ADULT
            flow.seats[1] = Seat.ADULT
            flow.seats[2] = Seat.CHILD
            flow.dog = true
            while (flow.budgetRub != 30_000) flow.stepBudget(if ((flow.budgetRub ?: Int.MAX_VALUE) > 30_000) -1 else 1)
        }
        assertEquals(4, flow.adults)
        assertEquals(1, flow.children)
        // ARCH-301 (M2): the engine fits the CEO case — either a fitted plan ≤ 31 500 or the no-fit screen
        val req = flow.request()
        val est = runBlocking { ChaquopyPlannerGateway(E2e.engine).estimate(UUID.randomUUID().toString(), req) }
        val e = (est as EngineResult.Ok).value
        Log.i("VerstE2e", "S3-1 estimate outcome=${e.outcome} total=${e.totalRub} status=${e.budgetStatus}")
        compose.waitUntil(20_000) { has("instruments.budget") }
        shot("60-instruments-ceo-budget")
        val t0 = System.nanoTime()
        compose.onNodeWithTag("instruments.start").performClick()
        compose.waitUntil(60_000) { flow.top == Route.Road || flow.top == Route.NoFit }
        budgets("ceoPlanMs", (System.nanoTime() - t0) / 1_000_000)
        if (flow.top == Route.Road) {
            waitTag("road.total")
            val total = flow.result!!.trip.cost.totalRub
            Log.i("VerstE2e", "S3-1 fitted total=$total fit=${flow.result!!.trip.budgetFit}")
            assertTrue("CEO case ≤ 31 500: $total", total <= 31_500)
            shot("61-road-ceo-fitted")
            compose.onNodeWithTag("road.total").performClick()
            waitTag("waybill.sheet")
            shot("62-waybill-ceo-fitted")
            // S3-R3: the lever lines «Подогнали под бюджет» on screen
            waitTag("waybill.levers")
            compose.onNodeWithTag("waybill.levers", useUnmergedTree = true).performScrollTo()
            shot("62b-waybill-ceo-levers")
        } else {
            waitTag("nofit")
            shot("61-nofit-ceo")
            val nf = flow.noFit!!
            assertTrue("≥ 2 options", nf.options.size >= 2)
            Log.i("VerstE2e", "S3-1 no_fit options=${nf.options.map { "${it.kind}:${it.totalRub ?: it.budgetRub}:${it.fits}" }}")
            // an option that fits: the cheaper route (Тула first), else shorten, else raise the budget
            val i = listOf<(BudgetOptionDto) -> Boolean>(
                { it.fits && it.readyRouteId == "rr_tula_yasnaya" },
                { it.fits && it.kind == "cheaper_route" },
                { it.fits && it.kind == "shorten" },
                { it.kind == "raise_budget" },
            ).firstNotNullOfOrNull { p -> nf.options.indexOfFirst(p).takeIf { it >= 0 } } ?: -1
            assertTrue("an option that fits", i >= 0)
            compose.onNodeWithTag("nofit.option.$i").performScrollTo().performClick()
            compose.waitUntil(5_000) { flow.top == Route.Instruments }
            compose.onNodeWithTag("instruments.start").performClick()
            compose.waitUntil(60_000) { flow.top == Route.Road }
            waitTag("road.total")
            val total = flow.result!!.trip.cost.totalRub
            val limit = nf.options[i].budgetRub?.let { it + it / 20 } ?: nf.allowedRub ?: 31_500
            assertTrue("the option fits: $total ≤ $limit", total <= limit)
            shot("62-road-option-fits")
        }
    }

    /** S3-2 + S3-3: a sight card (photo or its placeholder), the hotel card «Фото района», the row back in view. */
    @Test
    fun s32CardsAndS33FocusAfterTheCard() {
        readyRoute("rr_golden_ring")
        compose.onNodeWithTag("instruments.start").performClick()
        waitTag("road.total", 60_000)
        val stops = flow.result!!.trip.daysList.flatMap { it.stops }
        val sight = stops.filter { it.kind == "sight" }[1]
        compose.onNodeWithTag("road.stop.${sight.id}").performScrollTo().performClick()
        waitTag("card")
        // the photo settles: loaded (online, a real Commons file) or the placeholder (the sample catalogue's names)
        compose.waitUntil(20_000) { has("photo.loaded") || has("photo.error") || has("photo.none") }
        Log.i("VerstE2e", "S3-2 sight ${sight.placeId} photo loaded=${has("photo.loaded")} error=${has("photo.error")} none=${has("photo.none")}")
        shot("63-card-sight")
        back()
        compose.waitUntil(5_000) { flow.card == null }
        compose.waitUntil(5_000) { runCatching { inListViewport("road.list", "road.stop.${sight.id}") }.getOrDefault(false) }
        // S3-R3 (5.9 §5): TalkBack focus is back on the row (input focus → TYPE_VIEW_FOCUSED)
        compose.waitUntil(5_000) { focused("road.stop.${sight.id}") }
        shot("64-road-after-card")
        val night = stops.first { it.kind == "overnight" && it.hotelOptions.isNotEmpty() }
        compose.onNodeWithTag("road.stop.${night.id}").performScrollTo().performClick()
        waitTag("card.fictional")
        compose.waitUntil(20_000) { has("photo.loaded") || has("photo.error") || has("photo.none") }
        if (has("photo.loaded")) compose.onNodeWithText("ФОТО РАЙОНА").assertExists()
        shot("65-card-hotel-area")
        back()
        // fuel / rest rows have no click semantics (M§15.5)
        stops.filter { it.kind == "fuel" || it.kind == "rest" }.take(2).forEach { s ->
            val node = compose.onNodeWithTag("road.stop.${s.id}").fetchSemanticsNode()
            assertTrue("${s.kind} not clickable", !node.config.contains(androidx.compose.ui.semantics.SemanticsActions.OnClick))
        }
        // offline: an uncached photo → «Фото загрузится, когда будет интернет»
        compose.runOnUiThread { flow.setOffline(true) }
        val other = stops.filter { it.kind == "sight" }.last()
        compose.onNodeWithTag("road.stop.${other.id}").performScrollTo().performClick()
        waitTag("card")
        compose.waitUntil(20_000) { has("photo.offline") || has("photo.none") || has("photo.loaded") }
        shot("66-card-offline")
        back()
    }

    /** S3-4: GPS Ярославль → «По городу» → Обзорный → the walk → «Пешком в Яндекс Картах» = the web URL. */
    @Test
    fun s34CityWalkInYaroslavl() {
        compose.runOnUiThread {
            flow.debugMockLocation = GeoPoint("Ярославль", 57.6261, 39.8845)
            flow.locate()
        }
        compose.waitUntil(15_000) { flow.gps == GpsState.On && flow.origin.label == "Ярославль" }
        waitTag("windshield.city")
        compose.onNodeWithTag("windshield.city").performClick()
        waitTag("city.preset.overview", 20_000)
        shot("67-city-presets")
        compose.onNodeWithTag("city.preset.overview").performClick()
        val t0 = System.nanoTime()
        compose.onNodeWithTag("city.go").performClick()
        compose.waitUntil(20_000) { flow.top == Route.Walk }
        budgets("cityRouteMs", (System.nanoTime() - t0) / 1_000_000)
        waitTag("walk.total")
        val w = flow.walk!!
        Log.i("VerstE2e", "S3-4 walk ${w.titleRu} ${w.walkKm} km ${w.stops.size} stops")
        assertTrue(w.stops.size >= 2)
        shot("68-walk-result")
        compose.waitUntil(10_000) { flow.walkHandoff != null }
        // one button, or one per part when the engine split a long walk
        val hTag = if ((flow.walkHandoff?.parts?.size ?: 1) > 1) "walk.handoff.1" else "walk.handoff"
        compose.onNodeWithTag(hTag, useUnmergedTree = true).performScrollTo().performClick()
        compose.waitUntil(5_000) { flow.lastHandoff != null }
        val (links, target) = flow.lastHandoff!!
        Log.i("VerstE2e", "S3-4 walk handoff $target ${links.web}")
        assertEquals(HandoffTarget.BrowserDryRun, target) // no Yandex apps on the emulator
        assertTrue(links.web!!.startsWith("https://yandex.ru/maps/?rtext="))
        assertTrue(links.web!!.endsWith("&rtt=pd"))
        // 18+: «По рюмочным» asks every time; «Нет» sends nothing
        back()
        waitTag("city.go")
        if (has("city.preset.ryumochnye")) {
            compose.onNodeWithTag("city.preset.ryumochnye").performClick()
            waitTag("agegate")
            shot("69-city-age-gate")
            compose.onNodeWithTag("agegate.no", useUnmergedTree = true).performClick()
            assertEquals("overview", flow.cityPreset)
        }
    }

    /** S3-5: «Пермь» from the catalogue → a synthetic route with «Расстояния приблизительные». */
    @Test
    fun s35PermOnASyntheticRoute() {
        waitTag("windshield.navi")
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.to")
        compose.onNodeWithTag("navigator.to").performTextInput("Пермь")
        compose.waitUntil(15_000) { flow.suggestions.any { it.name == "Пермь" } }
        val i = flow.suggestions.indexOfFirst { it.name == "Пермь" }
        compose.onNodeWithTag("navigator.suggestion.$i").performScrollTo().performClick()
        waitTag("navigator.start", 10_000)
        compose.waitUntil(30_000) { flow.figures?.stale == false }
        compose.onNodeWithTag("navigator.start").performClick()
        waitTag("instruments.start")
        compose.onNodeWithTag("instruments.start").performClick()
        compose.waitUntil(90_000) { flow.top == Route.Road || flow.drive.error != null }
        assertEquals("plan: ${flow.drive.error}", Route.Road, flow.top)
        waitTag("road.total")
        assertTrue("synthetic", flow.result!!.trip.approxDistances)
        waitTag("road.approx")
        shot("70-road-perm-approx")
        compose.onNodeWithTag("road.approx.more", useUnmergedTree = true).performClick()
        waitTag("aboutdata")
        shot("71-about-data")
        back()
    }

    /** S3-6: «Найти адрес» on the online emulator against MockWebServer (one request, UA, © OpenStreetMap). */
    @Test
    fun s36AddressSearchAgainstMockWebServer() {
        val server = MockWebServer()
        server.enqueue(
            MockResponse().setHeader("Content-Type", "application/json").setBody(
                """[{"place_id": 101, "lat": "57.6266", "lon": "39.8938", "display_name": "1, Советская улица, Ярославль",
                   "address": {"house_number": "1", "road": "Советская улица", "city": "Ярославль"}}]""",
            ),
        )
        server.start()
        try {
            (flow.address as app.verst.data.net.NominatimClient).baseUrl = server.url("/").toString()
            waitTag("windshield.navi")
            compose.onNodeWithTag("windshield.navi").performClick()
            waitTag("navigator.to")
            compose.onNodeWithTag("navigator.to").performTextInput("Советская 1")
            waitTag("address.find", 10_000)
            assertEquals("typing sends nothing", 0, server.requestCount)
            shot("72-address-find-row")
            compose.onNodeWithTag("address.find").performScrollTo().performClick()
            waitTag("address.row.0", 15_000)
            waitTag("address.attribution")
            shot("73-address-results")
            assertEquals(1, server.requestCount)
            val rq = server.takeRequest()
            Log.i("VerstE2e", "S3-6 ${rq.path} UA=${rq.getHeader("User-Agent")}")
            assertTrue(rq.getHeader("User-Agent")!!.startsWith("Verst/0.3"))
            assertTrue(rq.path!!.contains("countrycodes=ru"))
            compose.onNodeWithTag("address.row.0").performClick()
            compose.waitUntil(5_000) { flow.destination?.kind == "address" }
            assertEquals("Советская улица, 1", flow.destination!!.name)
        } finally {
            E2e.noRealNominatim()
            server.shutdown()
        }
    }

    /** S3-R3: cards on real Commons files (debug override, ADR-0012 §6 URLs; CI has internet) — ≥ 3 of 5 load. */
    @Test
    fun r3RealCommonsPhotosOnTheCards() {
        compose.runOnUiThread {
            flow.debugRealPhotos = true
            flow.debugPhotoIndex = 0
        }
        try {
            val stops = goldenRingRoad()
            val sights = stops.filter { it.kind == "sight" && it.placeId != null }
            val night = stops.firstOrNull { it.kind == "overnight" && it.hotelOptions.isNotEmpty() }
            val targets = (sights.take(4) + listOfNotNull(night)).take(5)
            var loaded = 0
            targets.forEachIndexed { i, s ->
                compose.onNodeWithTag("road.stop.${s.id}").performScrollTo().performClick()
                waitTag("card")
                compose.waitUntil(30_000) { has("photo.loaded") || has("photo.error") || has("photo.none") }
                val state = when {
                    has("photo.loaded") -> "loaded"
                    has("photo.error") -> "error"
                    else -> "none"
                }
                if (state == "loaded") loaded++
                val file = app.verst.core.model.CommonsPhotos.DEBUG_FILES[i % app.verst.core.model.CommonsPhotos.DEBUG_FILES.size]
                Log.i("VerstE2e", "R3 commons «$file» on ${s.kind} ${s.placeId}: $state")
                if (s.kind == "overnight" && state == "loaded") compose.onNodeWithText("ФОТО РАЙОНА").assertExists()
                Thread.sleep(500) // photoFadeIn
                shot("80-commons-$i")
                back()
                compose.waitUntil(5_000) { flow.card == null }
            }
            assertTrue("≥ 3 real Commons photos loaded, got $loaded of ${targets.size}", loaded >= 3)
        } finally {
            compose.runOnUiThread { flow.debugRealPhotos = false }
        }
    }

    /** S3-R3 D-7: «Сообщить об ошибке» from the stop menu (online) and from a card (offline → queued). */
    @Test
    fun r3ReportFromTheStopMenuAndTheCard() {
        val stops = goldenRingRoad()
        val queue = File(InstrumentationRegistry.getInstrumentation().targetContext.filesDir, "reports/queue.json")
        val before = if (queue.exists()) app.verst.core.model.Reports.decode(queue.readText()).size else 0
        val sight = stops.filter { it.kind == "sight" && it.placeId != null }[0]
        compose.onNodeWithTag("road.stop.${sight.id}").performScrollTo().performTouchInput { longClick() }
        waitTag("stopmenu.report")
        shot("83-stopmenu-report")
        compose.onNodeWithTag("stopmenu.report").performClick()
        waitTag("report")
        compose.onNodeWithTag("report.send").assertIsNotEnabled()
        compose.onNodeWithTag("report.reason.price").performClick()
        compose.onNodeWithTag("report.send").assertIsEnabled()
        compose.onNodeWithTag("report.comment").performTextInput("Билет уже 600 ₽")
        shot("84-report-sheet")
        compose.onNodeWithTag("report.send").performScrollTo().performClick()
        compose.waitUntil(5_000) { flow.report == null && flow.toast == app.verst.nav.Toast.ReportThanks }
        compose.waitUntil(5_000) { focused("road.stop.${sight.id}") }
        shot("85-report-thanks")
        // offline, from the card: «Отправим, когда появится сеть»
        compose.runOnUiThread { flow.setOffline(true) }
        compose.onNodeWithTag("road.stop.${sight.id}").performScrollTo().performClick()
        waitTag("card.report")
        compose.onNodeWithTag("card.report").performScrollTo().performClick()
        waitTag("report")
        compose.onNodeWithTag("report.reason.closed").performClick()
        compose.onNodeWithTag("report.send").performScrollTo().performClick()
        compose.waitUntil(5_000) { flow.report == null && flow.toast == app.verst.nav.Toast.ReportQueued }
        shot("86-report-queued")
        compose.runOnUiThread { flow.setOffline(false) }
        compose.waitUntil(5_000) { queue.exists() && app.verst.core.model.Reports.decode(queue.readText()).size >= before + 2 }
        val mine = app.verst.core.model.Reports.decode(queue.readText()).takeLast(2)
        Log.i("VerstE2e", "R3 reports ${mine.map { "${it.reason}/${it.source}/${it.online}/${it.comment}" }}")
        assertEquals(listOf("price", "closed"), mine.map { it.reason })
        assertEquals(listOf("road", "card"), mine.map { it.source })
        assertEquals(listOf(true, false), mine.map { it.online })
        assertEquals("Билет уже 600 ₽", mine[0].comment)
        assertEquals(sight.placeId, mine[1].placeId)
    }

    // ------------------------------------------------------------------------------------ S3-R4 real catalogue

    /** R4: «Куда угодно» finds big towns across the country and a small one (offline catalogue `geo_search`). */
    @Test
    fun r4NavigatorFindsTownsAcrossRussia() {
        waitTag("windshield.navi")
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.to")
        for ((i, name) in listOf("Екатеринбург", "Владивосток", "Казань", "Сочи", "Мышкин").withIndex()) {
            compose.onNodeWithTag("navigator.to").performTextClearance()
            compose.onNodeWithTag("navigator.to").performTextInput(name)
            compose.waitUntil(10_000) { flow.suggestions.any { it.name == name } }
            val row = flow.suggestions.indexOfFirst { it.name == name }
            val s = flow.suggestions[row]
            Log.i("VerstE2e", "R4 search «$name» → row $row ${s.kind} ${s.subtitle} pop=${s.population}")
            assertTrue("$name is a town", s.kind == "city" || s.kind == "town")
            waitTag("navigator.suggestion.$row")
            if (name == "Владивосток" || name == "Мышкин") shot("90-search-${if (name == "Мышкин") "myshkin" else "vladivostok"}")
        }
    }

    /** R4: a sight card on Золотое кольцо with a REAL catalogue photo (no debug override) and its author / licence. */
    @Test
    fun r4RealCatalogueCardPhotoWithCredit() {
        assertTrue("the debug override defaults off", !flow.debugRealPhotos)
        val stops = goldenRingRoad()
        var loaded = 0
        var shots = 0
        for (s in stops.filter { it.kind == "sight" && it.placeId != null }.take(8)) {
            compose.onNodeWithTag("road.stop.${s.id}").performScrollTo().performClick()
            waitTag("card")
            compose.waitUntil(30_000) { flow.card?.ui?.loading == false && (has("photo.loaded") || has("photo.error") || has("photo.none")) }
            val img = flow.card?.ui?.details?.image
            val state = when {
                has("photo.loaded") -> "loaded"
                has("photo.error") -> "error"
                else -> "none"
            }
            Log.i("VerstE2e", "R4 card ${s.placeId} «${s.name}» $state author=${img?.credit?.author} licence=${img?.credit?.licence} url=${img?.card}")
            if (state == "loaded" && img?.credit?.author != null && img.credit?.licence != null) {
                loaded++
                compose.onNodeWithTag("photo.credit", useUnmergedTree = true).assertExists()
                Thread.sleep(500) // photoFadeIn
                if (shots < 4) shot("91-card-real-${shots++}")
            }
            back()
            compose.waitUntil(5_000) { flow.card == null }
        }
        assertTrue("≥ 1 real photo with author and licence on Золотое кольцо, got $loaded", loaded >= 1)
    }

    private fun walkIn(town: String, lat: Double, lon: Double, preset: String, shotName: String): Boolean {
        compose.runOnUiThread {
            while (flow.back()) Unit
            // adults only (an 18+ preset with a child in the crew shows the «не с детьми» toast instead of the gate)
            flow.frontAdult = true
            for (i in flow.seats.indices) flow.seats[i] = Seat.EMPTY
            flow.debugMockLocation = GeoPoint(town, lat, lon)
            flow.locate()
        }
        compose.waitUntil(20_000) { flow.gps == GpsState.On && flow.origin.label == town }
        waitTag("windshield.city")
        compose.onNodeWithTag("windshield.city").performClick()
        compose.waitUntil(20_000) { !flow.cityLoading && (flow.cityPresets?.town?.name == town || flow.cityError != null) }
        val p = flow.cityPresets?.presets?.firstOrNull { it.preset == preset }
        Log.i("VerstE2e", "R4 presets $town: ${flow.cityPresets?.presets?.map { "${it.preset}:${it.available}:${it.count}" }} tz=${flow.cityPresets?.town?.tz}")
        if (p == null || !p.available) return false
        waitTag("city.preset.$preset")
        // the plate tap itself is covered by S3-4; here the preset is chosen through the flow (a plate half under
        // the caption row must not decide a data journey)
        compose.runOnUiThread { flow.selectCityPreset(preset) }
        if (p.adultOnly) {
            compose.waitUntil(5_000) { flow.ageGate != null || flow.toast != null }
            Log.i("VerstE2e", "R4 age gate $town/$preset gate=${flow.ageGate} toast=${flow.toast} children=${flow.children}")
            waitTag("agegate")
            shot("$shotName-agegate")
            compose.onNodeWithTag("agegate.yes", useUnmergedTree = true).performClick()
        }
        compose.waitUntil(5_000) { flow.cityPreset == preset }
        compose.onNodeWithTag("city.go").performClick()
        compose.waitUntil(30_000) { flow.top == Route.Walk }
        waitTag("walk.total")
        val w = flow.walk!!
        Log.i("VerstE2e", "R4 walk $town/$preset «${w.titleRu}» ${w.walkKm} km ${w.durationMin} min ${w.stops.size} stops start=${w.startAt} tz=${w.tz} shorter=${w.shorter} stops=${w.stops.map { it.nameRu }}")
        assertTrue("$town/$preset has stops", w.stops.size >= 2)
        shot(shotName)
        return true
    }

    /** R4: Казань «Обзорный», Санкт-Петербург «Музейный», «Пивной» in a town ≥ 100 k (the first that has it). */
    @Test
    fun r4WalksKazanSpbAndBeer() {
        assertTrue("Казань overview", walkIn("Казань", 55.7963, 49.1088, "overview", "92-walk-kazan-overview"))
        assertTrue("СПб museums", walkIn("Санкт-Петербург", 59.9386, 30.3141, "museums", "93-walk-spb-museums"))
        val beer = listOf(
            Triple("Санкт-Петербург", 59.9386, 30.3141), Triple("Москва", 55.7558, 37.6173),
            Triple("Екатеринбург", 56.8389, 60.6057), Triple("Новосибирск", 55.0302, 82.9204), Triple("Казань", 55.7963, 49.1088),
        ).firstOrNull { (t, la, lo) -> walkIn(t, la, lo, "beer", "94-walk-beer-${t.take(3)}") }
        Log.i("VerstE2e", "R4 beer walk in ${beer?.first}")
        assertTrue("a «Пивной» walk in a town ≥ 100 k", beer != null)
    }
}
