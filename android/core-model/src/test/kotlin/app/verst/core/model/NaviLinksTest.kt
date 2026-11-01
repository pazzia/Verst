package app.verst.core.model

import java.io.File
import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** S3-R1 hand-off URL builders: coordinate format, via order, limits, day / from-here routes on a golden trip. */
class NaviLinksTest {
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")
    private val g02 = EngineJson.trip(root.resolve("backend/planner/tests/golden/snapshots/G02_golden_ring.json").readText())

    private val msk = LatLon(55.7558, 37.6173)
    private val yar = LatLon(57.6261, 39.8845)

    @Test
    fun coordinatesAreDotDecimalSixPlacesInAnyLocale() {
        val saved = Locale.getDefault()
        try {
            Locale.setDefault(Locale.forLanguageTag("ru-RU")) // the Russian locale writes «55,755800»
            assertEquals("55.755800", NaviLinks.coord(55.7558))
            assertEquals("-0.000001", NaviLinks.coord(-0.000001))
            assertEquals(
                "yandexnavi://build_route_on_map?lat_from=55.755800&lon_from=37.617300&lat_to=57.626100&lon_to=39.884500",
                NaviLinks.naviRoute(msk, yar, emptyList()),
            )
            assertEquals("https://yandex.ru/maps/?rtext=55.755800,37.617300~57.626100,39.884500&rtt=auto", NaviLinks.webRoute(listOf(msk, yar)))
        } finally {
            Locale.setDefault(saved)
        }
    }

    @Test
    fun viaPointsKeepTheirOrderAndIndices() {
        val via = (1..3).map { LatLon(56.0 + it / 10.0, 38.0) }
        val url = NaviLinks.naviRoute(msk, yar, via)
        assertTrue(url, url.endsWith("&lat_via_0=56.100000&lon_via_0=38.000000&lat_via_1=56.200000&lon_via_1=38.000000&lat_via_2=56.300000&lon_via_2=38.000000"))
        val web = NaviLinks.webRoute(listOf(msk) + via + yar)
        assertEquals("55.755800,37.617300~56.100000,38.000000~56.200000,38.000000~56.300000,38.000000~57.626100,39.884500", web.substringAfter("rtext=").substringBefore("&"))
    }

    @Test
    fun limitsThinEvenlyKeepingEnds() {
        val via = (0 until 20).map { LatLon(50.0 + it / 100.0, 30.0) }
        val url = NaviLinks.naviRoute(null, yar, via)
        assertFalse("no from = from the phone", url.contains("lat_from"))
        assertTrue(url.contains("lat_via_7="))
        assertFalse(url.contains("lat_via_8="))
        assertTrue(url.contains("lat_via_0=50.000000"))
        assertTrue(url.contains("lat_via_7=50.190000")) // the last via kept
        val thinned = NaviLinks.thin(via, 8)
        assertEquals(thinned.sortedBy { it.lat }, thinned) // order kept
        assertEquals(thinned.toSet().size, 8)
        val web = NaviLinks.webRoute(listOf(msk) + via + yar).substringAfter("rtext=").substringBefore("&").split("~")
        assertEquals(NaviLinks.MAX_WEB_POINTS, web.size)
        assertEquals("55.755800,37.617300", web.first())
        assertEquals("57.626100,39.884500", web.last())
        assertEquals(listOf(1, 2, 3), NaviLinks.thin(listOf(1, 2, 3), 8))
        assertEquals(listOf(1, 5), NaviLinks.thin(listOf(1, 2, 3, 4, 5), 2))
    }

    @Test
    fun walkingUsesPedestrianMode() {
        val h = NaviLinks.walking(listOf(msk, LatLon(55.76, 37.62)))
        assertNull(h.navi) // the navigator drives only
        assertTrue(h.web, h.web.endsWith("&rtt=pd"))
        assertTrue(h.mapsApp, h.mapsApp.startsWith("yandexmaps://maps.yandex.ru/?rtext=55.755800,37.617300~55.760000,37.620000&rtt=pd"))
    }

    @Test
    fun dayRouteGoesFromTheFirstToTheLastStopThroughTheRest() {
        val d1 = g02.daysList.first()
        val h = NaviLinks.day(d1)!!
        val first = d1.stops.first()
        val last = d1.stops.last()
        assertTrue(h.navi!!, h.navi!!.startsWith("yandexnavi://build_route_on_map?lat_from=${NaviLinks.coord(first.lat!!)}&lon_from=${NaviLinks.coord(first.lon!!)}"))
        assertTrue(h.navi!!.contains("lat_to=${NaviLinks.coord(last.lat!!)}&lon_to=${NaviLinks.coord(last.lon!!)}"))
        assertTrue(h.web.startsWith("https://yandex.ru/maps/?rtext=${NaviLinks.coord(first.lat!!)},"))
        // the second stop of the day is the first via
        assertTrue(h.navi!!.contains("lat_via_0=${NaviLinks.coord(d1.stops[1].lat!!)}"))
    }

    @Test
    fun fromStopRunsToTheEndOfItsDayOrIntoTheNextDay() {
        val d1 = g02.daysList.first()
        val mid = d1.stops[1]
        val h = NaviLinks.fromStop(g02, mid.id)!!
        assertTrue(h.navi!!.startsWith("yandexnavi://build_route_on_map?lat_from=${NaviLinks.coord(mid.lat!!)}"))
        assertTrue(h.navi!!.contains("lat_to=${NaviLinks.coord(d1.stops.last().lat!!)}"))
        // the day's last stop: the next day from here
        val night = d1.stops.last()
        val next = NaviLinks.fromStop(g02, night.id)!!
        assertTrue(next.navi!!.contains("lat_to=${NaviLinks.coord(g02.daysList[1].stops.last().lat!!)}"))
        // the trip's last stop: to it from the phone
        val end = g02.daysList.last().stops.last()
        val home = NaviLinks.fromStop(g02, end.id)!!
        assertFalse(home.navi!!.contains("lat_from"))
        assertTrue(home.web, home.web.contains("rtext=~"))
        assertNull(NaviLinks.fromStop(g02, "nope"))
    }
    /** CEO 29.10 (C): Google Maps directions — origin, destination, the waypoints in order, driving. */
    @Test
    fun googleRouteFormat() {
        val via = listOf(LatLon(56.3, 38.1), LatLon(56.7, 38.8))
        assertEquals(
            "https://www.google.com/maps/dir/?api=1&origin=55.755800,37.617300&destination=57.626100,39.884500" +
                "&waypoints=56.300000,38.100000%7C56.700000,38.800000&travelmode=driving",
            NaviLinks.googleRoute(listOf(msk) + via + yar),
        )
        // two points: no waypoints at all
        assertEquals(
            "https://www.google.com/maps/dir/?api=1&origin=55.755800,37.617300&destination=57.626100,39.884500&travelmode=driving",
            NaviLinks.googleRoute(listOf(msk, yar)),
        )
        // from the phone: no origin, every point but the last is a waypoint; a single point is from the phone too
        assertEquals(
            "https://www.google.com/maps/dir/?api=1&destination=57.626100,39.884500&waypoints=55.755800,37.617300&travelmode=driving",
            NaviLinks.googleRoute(listOf(msk, yar), fromHere = true),
        )
        assertEquals("https://www.google.com/maps/dir/?api=1&destination=57.626100,39.884500&travelmode=driving", NaviLinks.googleRoute(listOf(yar)))
    }

    @Test
    fun googleRouteThinsToEightWaypointsKeepingOrderAndEnds() {
        val via = (0 until 20).map { LatLon(50.0 + it / 100.0, 30.0) }
        val url = NaviLinks.googleRoute(listOf(msk) + via + yar)
        val wp = url.substringAfter("waypoints=").substringBefore("&").split("%7C")
        assertEquals(NaviLinks.MAX_GOOGLE_WAYPOINTS, wp.size)
        assertEquals("50.000000,30.000000", wp.first())
        assertEquals("50.190000,30.000000", wp.last())
        assertEquals(wp.sortedBy { it.substringBefore(",").toDouble() }, wp) // order kept
        assertTrue(url, url.contains("origin=55.755800,37.617300&destination=57.626100,39.884500&"))
        // from the phone: 8 waypoints + the destination (the app takes 9)
        val here = NaviLinks.googleRoute(via + yar, fromHere = true)
        assertFalse(here.contains("origin="))
        assertEquals(8, here.substringAfter("waypoints=").substringBefore("&").split("%7C").size)
    }

    @Test
    fun googleRouteWalkingAndFromHandoffPoints() {
        assertTrue(NaviLinks.googleRoute(listOf(msk, LatLon(55.76, 37.62)), RouteMode.WALK).endsWith("&travelmode=walking"))
        val p = { lat: Double, role: String -> app.verst.core.model.dto.HandoffPointDto(lat, 37.6, "x", role) }
        // the engine's car day «from here»: no origin point → Google starts at the phone
        val day = NaviLinks.googleOf(listOf(p(55.8, "via"), p(55.9, "destination")), RouteMode.DRIVE)!!
        assertFalse(day, day.contains("origin="))
        assertTrue(day, day.contains("destination=55.900000,37.600000&waypoints=55.800000,37.600000&travelmode=driving"))
        // a car part with an origin starts there
        assertTrue(NaviLinks.googleOf(listOf(p(55.7, "origin"), p(55.9, "destination")), RouteMode.DRIVE)!!.contains("origin=55.700000,37.600000"))
        // a later part of a split walk starts at its boundary point, never at the phone
        val walk = NaviLinks.googleOf(listOf(p(55.7, "via"), p(55.8, "via"), p(55.9, "destination")), RouteMode.WALK)!!
        assertTrue(walk, walk.contains("origin=55.700000,37.600000&destination=55.900000,37.600000&waypoints=55.800000,37.600000&travelmode=walking"))
        assertNull(NaviLinks.googleOf(emptyList(), RouteMode.DRIVE))
    }

    @Test
    fun localDayHandoffKnowsWhereItStarts() {
        val d1 = g02.daysList.first()
        assertFalse(NaviLinks.day(d1)!!.fromHere)
        val end = g02.daysList.last().stops.last()
        assertTrue(NaviLinks.fromStop(g02, end.id)!!.fromHere)
    }
}
