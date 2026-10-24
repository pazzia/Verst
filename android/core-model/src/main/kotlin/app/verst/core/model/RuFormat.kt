package app.verst.core.model

import kotlin.math.roundToInt

/** UI number formatting (M§4 `format/RuFormat`, DEV-SLICE subset): U+202F thousands separator. */
object RuFormat {
    const val THIN = ' '

    fun thousands(n: Int): String {
        val digits = kotlin.math.abs(n).toString()
        val sb = StringBuilder()
        for ((i, c) in digits.withIndex()) {
            if (i > 0 && (digits.length - i) % 3 == 0) sb.append(THIN)
            sb.append(c)
        }
        return if (n < 0) "−$sb" else sb.toString()
    }

    /** «HH:mm» of an engine local datetime «2026-11-07T09:05», or null. */
    fun clock(localDateTime: String?): String? =
        localDateTime?.takeIf { it.length >= 16 && it[10] == 'T' }?.substring(11, 16)
}

/**
 * Per-day estimates of 5.3 §3 (A§11.11). Trip km and days are *not* estimated here: they come from the engine
 * (`TripFigures`, DEV-SLICE-2 P0).
 */
object TripMath {
    /** «≈ X ч Y мин» of a day: round(km / 70 × 60 / 10) × 10 minutes (A§11.11). */
    fun driveMinutes(dailyKm: Int): Int = (dailyKm / 70.0 * 60.0 / 10.0).roundToInt() * 10

    /** Odometer default (5.3 §3): 300 if the trip is < 800 km, 500 otherwise. */
    fun defaultDailyKm(tripKm: Int): Int = if (tripKm < 800) 300 else 500

    /** Initial bearing a → b snapped to 8 directions (N, NE … NW) for the Road-ahead arrow of a free trip. */
    fun bearing8(a: GeoPoint, b: GeoPoint): String {
        val f1 = Math.toRadians(a.lat)
        val f2 = Math.toRadians(b.lat)
        val dl = Math.toRadians(b.lon - a.lon)
        val y = kotlin.math.sin(dl) * kotlin.math.cos(f2)
        val x = kotlin.math.cos(f1) * kotlin.math.sin(f2) - kotlin.math.sin(f1) * kotlin.math.cos(f2) * kotlin.math.cos(dl)
        val deg = (Math.toDegrees(kotlin.math.atan2(y, x)) + 360.0) % 360.0
        return listOf("N", "NE", "E", "SE", "S", "SW", "W", "NW")[((deg + 22.5) / 45.0).toInt() % 8]
    }

    const val KM_MIN = 150
    const val KM_MAX = 900
    const val KM_STEP = 50
}
