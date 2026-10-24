package app.verst.core.model

import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

/**
 * The 5.10 caption's start time (5.11 §9, S3-QA P0-01), the same rule as the engine: now rounded up to 15 min,
 * inside the day window (day walks 09:00, museums 10:00 → end by 22:00; drink walks 18:00 → end by 23:00).
 * Later than the window → the window's opening on the next day. Computed in the town's zone.
 */
object WalkStart {
    data class Start(val time: LocalTime, val tomorrow: Boolean) {
        val label: String get() = "%02d:%02d".format(time.hour, time.minute)
    }

    private val DRINK = setOf("ryumochnye", "beer")

    fun isDrink(preset: String, interests: Collection<String>) = preset in DRINK || "bars" in interests

    fun of(preset: String, interests: Collection<String>, durationMin: Int, now: ZonedDateTime): Start {
        val drink = isDrink(preset, interests)
        val open = LocalTime.of(if (drink) 18 else if (preset == "museums") 10 else 9, 0)
        val endBy = if (drink) 23 * 60 else 22 * 60
        val latestMin = endBy - durationMin.coerceIn(30, 12 * 60)
        val n = now.toLocalDateTime().withSecond(0).withNano(0)
        val rounded = n.plusMinutes(((15 - n.minute % 15) % 15).toLong())
        val sameDay = rounded.toLocalDate() == n.toLocalDate()
        val minute = rounded.hour * 60 + rounded.minute
        return when {
            !sameDay -> Start(open, tomorrow = true)
            minute < open.hour * 60 + open.minute -> Start(open, tomorrow = false)
            minute > latestMin -> Start(open, tomorrow = true)
            else -> Start(rounded.toLocalTime(), tomorrow = false)
        }
    }

    /** The engine's `startAt` («2026-10-24T10:00») against now in [zone]. */
    fun fromEngine(startAt: String, zone: ZoneId, now: ZonedDateTime): Start? = runCatching {
        val at = LocalDateTime.parse(startAt)
        Start(at.toLocalTime(), at.toLocalDate().isAfter(now.withZoneSameInstant(zone).toLocalDate()))
    }.getOrNull()

    fun zone(tz: String?): ZoneId = runCatching { ZoneId.of(tz ?: "Europe/Moscow") }.getOrDefault(ZoneId.of("Europe/Moscow"))
}
