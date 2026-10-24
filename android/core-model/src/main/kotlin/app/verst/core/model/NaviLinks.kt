package app.verst.core.model

import app.verst.core.model.dto.DayDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.dto.TripDto
import java.util.Locale

/** A coordinate of a hand-off link. */
data class LatLon(val lat: Double, val lon: Double) {
    init {
        require(lat in -90.0..90.0 && lon in -180.0..180.0) { "bad point $lat,$lon" }
    }
}

/** Driving or walking (the city mode of a later round). */
enum class RouteMode(val rtt: String) { DRIVE("auto"), WALK("pd") }

/** What to open: the navigator app link, the maps-app link and the web fallback for the same route. */
data class NaviHandoff(val navi: String?, val mapsApp: String, val web: String, val points: List<LatLon>)

/**
 * CEO 4 / S3-R1 hand-off links (A§ hand-off; no engine call — the trip carries the stop coordinates).
 *
 * - Yandex Navigator: `yandexnavi://build_route_on_map?lat_from=…&lon_from=…&lat_to=…&lon_to=…&lat_via_0=…&lon_via_0=…`
 *   (driving only). Without a «from» the navigator starts from the phone's position.
 * - Yandex Maps web: `https://yandex.ru/maps/?rtext=lat,lon~lat,lon~…&rtt=auto|pd` (the browser fallback).
 * - Yandex Maps app: `yandexmaps://maps.yandex.ru/?rtext=…&rtt=…` (walking routes of the city mode).
 *
 * Coordinates: dot decimal, 6 places (≈ 0.1 m), whatever the phone's locale. Via points keep their order; above
 * the limit they are thinned evenly, the first and the last via always kept.
 */
object NaviLinks {
    const val NAVI_PACKAGE = "ru.yandex.yandexnavi"
    const val MAPS_PACKAGE = "ru.yandex.yandexmaps"

    /** Decision (dev-notes S3-R1): the navigator takes 8 via points, the web route 10 points in all. */
    const val MAX_NAVI_VIA = 8
    const val MAX_WEB_POINTS = 10

    fun coord(v: Double): String = String.format(Locale.US, "%.6f", v)

    /** [via] thinned to at most [max] points, in order, keeping the first and the last. */
    fun <T> thin(via: List<T>, max: Int): List<T> {
        if (via.size <= max) return via
        if (max <= 0) return emptyList()
        if (max == 1) return listOf(via.first())
        return (0 until max).map { i -> via[Math.round(i * (via.size - 1).toDouble() / (max - 1)).toInt()] }
    }

    /** Yandex Navigator route [from] (null = here) → [to] through [via]. */
    fun naviRoute(from: LatLon?, to: LatLon, via: List<LatLon>): String = buildString {
        append("yandexnavi://build_route_on_map?")
        val q = mutableListOf<String>()
        if (from != null) {
            q += "lat_from=${coord(from.lat)}"
            q += "lon_from=${coord(from.lon)}"
        }
        q += "lat_to=${coord(to.lat)}"
        q += "lon_to=${coord(to.lon)}"
        thin(via, MAX_NAVI_VIA).forEachIndexed { i, p ->
            q += "lat_via_$i=${coord(p.lat)}"
            q += "lon_via_$i=${coord(p.lon)}"
        }
        append(q.joinToString("&"))
    }

    private fun rtext(points: List<LatLon>): String {
        require(points.isNotEmpty()) { "no points" }
        // A single point: a route from the phone's position («~lat,lon» with an empty start).
        val pts = if (points.size == 1) points else listOf(points.first()) + thin(points.subList(1, points.size - 1), MAX_WEB_POINTS - 2) + points.last()
        val body = pts.joinToString("~") { "${coord(it.lat)},${coord(it.lon)}" }
        return if (points.size == 1) "~$body" else body
    }

    /** Yandex Maps in the browser: the same route (the fallback when the navigator is not installed). */
    fun webRoute(points: List<LatLon>, mode: RouteMode = RouteMode.DRIVE): String =
        "https://yandex.ru/maps/?rtext=${rtext(points)}&rtt=${mode.rtt}"

    /** Yandex Maps app deep link (walking routes of the city mode; driving works too). */
    fun mapsAppRoute(points: List<LatLon>, mode: RouteMode = RouteMode.DRIVE): String =
        "yandexmaps://maps.yandex.ru/?rtext=${rtext(points)}&rtt=${mode.rtt}"

    /** A walking route (city mode, R2+): the maps app link and the web fallback. */
    fun walking(points: List<LatLon>): NaviHandoff =
        NaviHandoff(null, mapsAppRoute(points, RouteMode.WALK), webRoute(points, RouteMode.WALK), points)

    /** One driving route through [points] (first = from, last = to). */
    fun driving(points: List<LatLon>, fromHere: Boolean = false): NaviHandoff {
        require(points.isNotEmpty()) { "no points" }
        val to = points.last()
        val from = if (fromHere || points.size == 1) null else points.first()
        val via = if (points.size <= 2) emptyList() else points.subList(1, points.size - 1)
        val web = if (fromHere) listOf(to) else points
        return NaviHandoff(naviRoute(from, to, via), mapsAppRoute(web), webRoute(web), points)
    }

    private fun StopDto.point(): LatLon? {
        val la = lat ?: return null
        val lo = lon ?: return null
        return runCatching { LatLon(la, lo) }.getOrNull()
    }

    /** Consecutive duplicates (a stop at the same place as the one before) are dropped. */
    private fun points(stops: List<StopDto>): List<LatLon> =
        stops.mapNotNull { it.point() }.fold(mutableListOf()) { acc, p -> if (acc.lastOrNull() != p) acc += p; acc }

    /** «в навигатор ↗» of [day]: its first stop → its last stop through the stops between; null without coordinates. */
    fun day(day: DayDto): NaviHandoff? = points(day.stops).takeIf { it.isNotEmpty() }?.let { driving(it) }

    /**
     * Long-press «навигатор отсюда» on [stopId]: from that stop to the end of its day through the rest of the day.
     * On the day's last stop: the next day's route from here; on the trip's last stop: to it from the phone's
     * position.
     */
    fun fromStop(trip: TripDto, stopId: String): NaviHandoff? {
        val di = trip.daysList.indexOfFirst { d -> d.stops.any { it.id == stopId } }
        if (di < 0) return null
        val stops = trip.daysList[di].stops
        val si = stops.indexOfFirst { it.id == stopId }
        val rest = points(stops.drop(si))
        return when {
            rest.size >= 2 -> driving(rest)
            di + 1 < trip.daysList.size -> points(stops.subList(si, si + 1) + trip.daysList[di + 1].stops).takeIf { it.size >= 2 }?.let { driving(it) }
            else -> rest.takeIf { it.isNotEmpty() }?.let { driving(it, fromHere = true) }
        }
    }
}
