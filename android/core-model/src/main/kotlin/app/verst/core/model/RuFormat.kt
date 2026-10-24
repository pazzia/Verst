package app.verst.core.model

import kotlin.math.asin
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

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

/** Estimates of 5.3 §3 / A§11.11 before the plan exists. */
object TripMath {
    /** Great-circle distance in km. */
    fun haversineKm(a: GeoPoint, b: GeoPoint): Double {
        val r = 6371.0
        val dLat = Math.toRadians(b.lat - a.lat)
        val dLon = Math.toRadians(b.lon - a.lon)
        val h = sin(dLat / 2) * sin(dLat / 2) +
            cos(Math.toRadians(a.lat)) * cos(Math.toRadians(b.lat)) * sin(dLon / 2) * sin(dLon / 2)
        return 2 * r * asin(sqrt(h))
    }

    /** Road km estimate of a free trip: straight line × 1.25 (A§11.11). */
    fun roadKmEstimate(a: GeoPoint, b: GeoPoint): Int = (haversineKm(a, b) * 1.25).roundToInt()

    /** «≈ X ч Y мин» of a day: round(km / 70 × 60 / 10) × 10 minutes (A§11.11). */
    fun driveMinutes(dailyKm: Int): Int = (dailyKm / 70.0 * 60.0 / 10.0).roundToInt() * 10

    fun days(tripKm: Int, dailyKm: Int): Int = maxOf(1, ceil(tripKm.toDouble() / dailyKm).toInt())

    /** Odometer default (5.3 §3): 300 if the trip is < 800 km, 500 otherwise. */
    fun defaultDailyKm(tripKm: Int): Int = if (tripKm < 800) 300 else 500

    const val KM_MIN = 150
    const val KM_MAX = 900
    const val KM_STEP = 50
}
