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
import app.verst.core.model.Mood
import app.verst.core.model.dto.StopDto
import app.verst.nav.GpsState
import app.verst.nav.Route
import app.verst.nav.Seat
import java.io.File
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
 * Sprint 4 on the real catalogue (wd-20261025-r7.3, Architect M7): the journeys the Manager reviews —
 * Фрязино Golden Ring, a Moscow stop with zone parking, «Весело и познавательно» Москва → СПб, Фрязино 4 h custom
 * walk, Казань unlimited and dog walks, cards at data levels 1–4. Screens 120–149; facts go to the log.
 */
@OptIn(ExperimentalTestApi::class)
@RunWith(AndroidJUnit4::class)
class Sprint4DataTest {
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
            flow.debugHandoffDryRun = true
            flow.debugLocationAnswered()
            flow.frontAdult = true
            for (i in flow.seats.indices) flow.seats[i] = Seat.EMPTY
            flow.dog = false
        }
    }

    @After
    fun cleanUp() {
        compose.runOnUiThread {
            flow.debugHandoffDryRun = false
            flow.debugResetOrigin()
            flow.debugLocationAnswered()
            for (i in flow.seats.indices) flow.seats[i] = Seat.EMPTY
            flow.dog = false
            flow.pickMood(Mood.FUN)
            flow.pickCityDog(false)
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
        compose.waitUntil(timeoutMs) { has(tag) }
    }

    private fun has(tag: String) = compose.onAllNodes(hasTestTag(tag), useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty()

    private fun from(town: String, lat: Double, lon: Double) {
        compose.runOnUiThread {
            while (flow.back()) Unit
            flow.debugMockLocation = GeoPoint(town, lat, lon)
            flow.locate()
        }
        compose.waitUntil(20_000) { flow.gps == GpsState.On && flow.origin.label == town }
    }

    private fun stops(): List<StopDto> = flow.result!!.trip.daysList.flatMap { it.stops }

    private fun logTrip(tag: String) {
        val t = flow.result!!.trip
        Log.i("VerstE2e", "S4D $tag «${t.title}» ${t.km} km ${t.days} d total=${t.cost.totalRub} parking=${t.cost.lines.firstOrNull { it.key == "parking" }?.rub}")
        t.daysList.forEach { d ->
            Log.i("VerstE2e", "S4D $tag day ${d.day}: " + d.stops.joinToString(" | ") { s ->
                "${s.kind}:${s.name}${s.poiKind?.let { " [$it]" } ?: ""}${if (s.stretch) " fun=${s.funFor}" else ""}${s.parking?.let { p -> " P=${p.rub}/${p.source}" } ?: ""} @${s.kmDriven}"
            })
        }
    }

    private fun scrollShot(s: StopDto, name: String) {
        compose.onNodeWithTag("road.stop.${s.id}").performScrollTo()
        shot(name)
    }

    /** Navigator → [query] → Instruments with [mood] → Road ahead. */
    private fun planTo(query: String, mood: Mood, child: Boolean = false, dog: Boolean = false, dailyKm: Int? = null) {
        compose.runOnUiThread {
            if (child) flow.seats[0] = Seat.CHILD
            flow.dog = dog
        }
        waitTag("windshield.navi")
        compose.onNodeWithTag("windshield.navi").performClick()
        waitTag("navigator.to")
        compose.onNodeWithTag("navigator.to").performTextInput(query)
        // the town itself (not a POI or a ready route that happens to be first)
        compose.waitUntil(15_000) { flow.suggestions.any { it.name == query } }
        val town = flow.suggestions.first { it.name == query }
        Log.i("VerstE2e", "S4D destination $query → ${town.kind} ${town.name} (${flow.suggestions.map { "${it.kind}:${it.name}" }})")
        compose.runOnUiThread { flow.pick(town) }
        waitTag("navigator.start", 15_000)
        compose.onNodeWithTag("navigator.start").performClick()
        waitTag("instruments.start")
        compose.runOnUiThread {
            flow.pickMood(mood)
            if (dailyKm != null) flow.stepKm(dailyKm - flow.dailyKm)
        }
        compose.onNodeWithTag("instruments.start").performClick()
        compose.waitUntil(120_000) { flow.top == Route.Road || flow.top == Route.NoFit }
        if (flow.top == Route.NoFit) Log.i("VerstE2e", "S4D no-fit for $query")
        waitTag("road.total", 60_000)
    }

    @Test
    fun s4dFryazinoGoldenRing() {
        from("Фрязино", 55.9606, 38.0456)
        waitTag("windshield.route.0")
        val routes = (flow.windshield as app.verst.nav.WindshieldData.Routes).routes
        val i = routes.indexOfFirst { it.id == "rr_golden_ring" }
        assertTrue("Golden Ring offered from Фрязино: ${routes.map { it.id }}", i >= 0)
        compose.onNodeWithTag("windshield.route.$i").performClick()
        compose.waitUntil(5_000) { flow.selected?.id == "rr_golden_ring" }
        compose.onNodeWithTag("windshield.start").performClick()
        waitTag("instruments.start")
        compose.onNodeWithTag("instruments.start").performClick()
        compose.waitUntil(120_000) { flow.top == Route.Road || flow.top == Route.NoFit }
        waitTag("road.total", 60_000)
        logTrip("fryazino-ring")
        shot("120-fryazino-ring-top")
        val sights = stops().filter { it.kind == "sight" }
        assertTrue("sights on the ring", sights.isNotEmpty())
        sights.getOrNull(1)?.let { scrollShot(it, "121-fryazino-ring-sights") }
        sights.getOrNull(sights.size / 2)?.let { scrollShot(it, "122-fryazino-ring-middle") }
        compose.onNodeWithTag("road.total").performClick()
        waitTag("waybill.sheet")
        shot("123-fryazino-ring-waybill")
        cardsAtEveryLevel("fryazino")
    }

    @Test
    fun s4dMoscowParkingStop() {
        compose.runOnUiThread { flow.debugResetOrigin() }
        planTo("Тула", Mood.CALM)
        logTrip("moscow-tula")
        val paid = stops().firstOrNull { it.parking?.rub?.let { r -> r > 0 } == true }
        Log.i("VerstE2e", "S4D paid parking stop: ${paid?.name} ${paid?.parking}")
        if (paid != null) {
            scrollShot(paid, "125-moscow-parking-row")
            compose.onNodeWithTag("road.stop.${paid.id}.parking", useUnmergedTree = true).performClick()
            waitTag("parking.ok")
            shot("126-moscow-parking-sheet")
            compose.onNodeWithTag("parking.ok", useUnmergedTree = true).performClick()
        }
        compose.onNodeWithTag("road.total").performClick()
        waitTag("waybill.sheet")
        compose.onNodeWithTag("waybill.line.parking").performScrollTo().performClick()
        shot("127-moscow-waybill-parking")
        assertTrue("a «Парковки» line", flow.result!!.trip.cost.lines.any { it.key == "parking" })
    }

    @Test
    fun s4dFunMoscowSpbWithChildAndDog() {
        compose.runOnUiThread { flow.debugResetOrigin() }
        planTo("Санкт-Петербург", Mood.FUN, child = true, dog = true)
        logTrip("fun-msk-spb")
        shot("130-fun-msk-spb-top")
        val funStops = stops().filter { it.stretch }
        Log.i("VerstE2e", "S4D fun stops: ${funStops.map { "${it.name} ${it.funFor} ${it.poiKind}" }}")
        funStops.take(2).forEachIndexed { i, s -> scrollShot(s, "13${1 + i}-fun-stop-$i") }
        assertTrue("«Разминка» stops on M-11", funStops.isNotEmpty())
        cardsAtEveryLevel("msk-spb")
    }

    /** M8 / G18: Москва → Казань по М-12, 2 взр., 500 км/день — Покрова на Нерли with «Крюк ≈ 30 мин». */
    @Test
    fun s4dMoscowKazanM12() {
        compose.runOnUiThread { flow.debugResetOrigin() }
        planTo("Казань", Mood.CALM, dailyKm = 500)
        logTrip("msk-kazan")
        val detours = stops().filter { (it.note ?: it.reason)?.contains("Крюк") == true }
        Log.i("VerstE2e", "S4D Крюк rows: ${detours.map { "${it.name}: ${it.note ?: it.reason}" }}")
        val pokrov = stops().firstOrNull { it.name.contains("Покрова") } ?: detours.firstOrNull()
        assertTrue("a quality detour on М-12", pokrov != null)
        scrollShot(pokrov!!, "150-msk-kazan-pokrov")
        compose.onNodeWithTag("road.total").performClick()
        waitTag("waybill.sheet")
        shot("151-msk-kazan-waybill")
    }

    /** M8 / G14: Фрязино → Екатеринбург, 2 взр. + ребёнок, 600 км/день — day 1 through Владимир. */
    @Test
    fun s4dFryazinoEkaterinburgDay1() {
        from("Фрязино", 55.9606, 38.0456)
        planTo("Екатеринбург", Mood.CALM, child = true, dailyKm = 600)
        logTrip("fryazino-ekb")
        val day1 = flow.result!!.trip.daysList.first().stops
        val vladimir = day1.firstOrNull { it.name.contains("Владимир") || it.townId?.contains("vladimir") == true }
        Log.i("VerstE2e", "S4D day 1 Владимир: ${vladimir?.name}")
        shot("152-fryazino-ekb-top")
        (vladimir ?: day1.getOrNull(2))?.let { scrollShot(it, "153-fryazino-ekb-day1-vladimir") }
    }

    @Test
    fun s4dWalks() {
        // Фрязино: «Свой маршрут» 4 h
        from("Фрязино", 55.9606, 38.0456)
        compose.onNodeWithTag("windshield.city").performClick()
        compose.waitUntil(20_000) { !flow.cityLoading && flow.cityPresets != null }
        compose.runOnUiThread {
            flow.selectCityPreset("custom")
            flow.setCityDuration(240)
        }
        compose.runOnUiThread { flow.buildCustomWalk() }
        compose.waitUntil(30_000) { flow.top == Route.Walk || flow.walkFew != null }
        Log.i("VerstE2e", "S4D Фрязино custom 4 h: top=${flow.top} stops=${flow.walk?.stops?.size} ${flow.walk?.stops?.map { it.nameRu }}")
        shot("140-fryazino-custom-4h")
        Log.i("VerstE2e", "S4D Фрязино custom interests=${flow.cityInterests} pace=${flow.cityPace}")
        if (flow.top == Route.Walk) assertTrue("Фрязино custom walk has places", flow.walk!!.stops.size >= 5)
        // Казань: «без ограничения», then the dog walk
        from("Казань", 55.7963, 49.1088)
        compose.onNodeWithTag("windshield.city").performClick()
        compose.waitUntil(20_000) { !flow.cityLoading && flow.cityPresets?.town?.name == "Казань" }
        compose.runOnUiThread {
            flow.selectCityPreset("overview")
            flow.setCityDuration(null)
        }
        compose.onNodeWithTag("city.go").performClick()
        compose.waitUntil(30_000) { flow.top == Route.Walk }
        Log.i("VerstE2e", "S4D Казань unlimited: ${flow.walk?.stops?.size} stops untimed=${flow.walk?.untimed} ${flow.walk?.stops?.map { "${it.nameRu} ${it.hours?.todayRu}" }}")
        assertTrue(flow.walk!!.untimed)
        shot("141-kazan-unlimited")
        compose.runOnUiThread { flow.back() }
        compose.waitUntil(5_000) { flow.top == Route.City }
        compose.runOnUiThread {
            flow.pickCityDog(true)
            flow.selectCityPreset("dog_walk")
            flow.setCityDuration(120)
        }
        compose.onNodeWithTag("city.go").performClick()
        compose.waitUntil(30_000) { flow.top == Route.Walk && flow.walk?.preset == "dog_walk" }
        Log.i("VerstE2e", "S4D Казань dog walk: ${flow.walk?.stops?.map { "${it.nameRu} [${it.kind}]" }}")
        assertTrue("no indoor stop on the dog walk", flow.walk!!.stops.none { it.indoor })
        shot("142-kazan-dog-walk")
    }

    /** Opens sight cards until one of each data level 1–4 was seen (or the trip runs out). */
    private fun cardsAtEveryLevel(tag: String) {
        compose.runOnUiThread { while (flow.top != Route.Road && flow.back()) Unit }
        waitTag("road.total")
        val seen = mutableSetOf<Int>()
        for (s in stops().filter { it.kind == "sight" }) {
            if (seen.size == 4) break
            compose.runOnUiThread { flow.openCard(s) }
            compose.waitUntil(15_000) { flow.card?.ui?.details != null || flow.card?.ui?.loading == false }
            val lvl = flow.card?.ui?.details?.cardLevel
            Log.i("VerstE2e", "S4D card ${s.name}: level=$lvl photo=${flow.card?.ui?.details?.image?.source} text=${flow.card?.ui?.details?.textSource} why=${flow.card?.ui?.details?.whyRu}")
            if (lvl != null && seen.add(lvl)) {
                compose.waitUntil(20_000) { has("photo.loaded") || has("photo.error") || has("photo.none") || has("photo.offline") }
                shot("14${4 + lvl}-$tag-card-level-$lvl")
            }
            compose.runOnUiThread { flow.closeCard() }
            compose.waitUntil(5_000) { flow.card == null }
        }
        Log.i("VerstE2e", "S4D card levels seen on $tag: $seen")
    }
}
