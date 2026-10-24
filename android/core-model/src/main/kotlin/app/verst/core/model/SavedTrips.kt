package app.verst.core.model

import app.verst.core.model.dto.PlanResultDto
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/**
 * One saved trip (M§6.1 subset, DEV-SLICE-2): list fields for «Мои поездки» plus the engine's private trip JSON
 * verbatim, so a reopened trip can be replaced, re-costed and shared on the engine exactly like a fresh one.
 */
@Serializable
data class SavedTripDto(
    val id: String,
    val savedAt: Long,
    val title: String,
    val km: Int,
    val days: Int,
    val totalRub: Int,
    val startAt: String? = null,
    val adults: Int = 1,
    val children: Int = 0,
    val dog: Boolean = false,
    val bearing8: String = "N",
    val shareText: String = "",
    val pricesMonthRu: String? = null,
    val pricesYear: String? = null,
    val townPrepRu: Map<String, String> = emptyMap(),
    /** Overnight stop ids the crew marked «Забронировали» (D-10). */
    val bookedStops: List<String> = emptyList(),
    val trip: JsonObject,
)

@Serializable
data class SavedTripsFile(val schema: Int = SavedTrips.SCHEMA, val trips: List<SavedTripDto> = emptyList())

/** Pure rules of the saved-trips file (M§6: schema 1, ≤ 50, warning from 45); the app adds the file I/O. */
object SavedTrips {
    const val SCHEMA = 1
    const val LIMIT = 50
    const val WARN_FROM = 45

    /** An unreadable file or an unknown schema gives an empty list (never a crash at start). */
    fun decode(text: String?): List<SavedTripDto> {
        if (text.isNullOrBlank()) return emptyList()
        return try {
            val f = EngineJson.json.decodeFromString(SavedTripsFile.serializer(), text)
            if (f.schema == SCHEMA) f.trips else emptyList()
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun encode(trips: List<SavedTripDto>): String = EngineJson.json.encodeToString(SavedTripsFile.serializer(), SavedTripsFile(SCHEMA, trips))

    sealed interface Upsert {
        /** Saved; [count] trips now, [nearLimit] from 45 (toast «Сохранено N из 50 …»). */
        data class Saved(val trips: List<SavedTripDto>, val count: Int, val nearLimit: Boolean) : Upsert
        data object LimitReached : Upsert
    }

    /** Delete (D-1) keeping the position, so «Вернуть» puts it back where it was. */
    fun remove(trips: List<SavedTripDto>, id: String): Pair<List<SavedTripDto>, Pair<Int, SavedTripDto>?> {
        val i = trips.indexOfFirst { it.id == id }
        if (i < 0) return trips to null
        return trips.filterIndexed { j, _ -> j != i } to (i to trips[i])
    }

    fun restore(trips: List<SavedTripDto>, removed: Pair<Int, SavedTripDto>): List<SavedTripDto> =
        trips.toMutableList().apply { add(removed.first.coerceAtMost(size), removed.second) }

    /** Replaces the entry with the same id in place (re-save after a replace or a reserve toggle) or appends. */
    fun upsert(trips: List<SavedTripDto>, entry: SavedTripDto): Upsert {
        val i = trips.indexOfFirst { it.id == entry.id }
        val next = when {
            i >= 0 -> trips.toMutableList().also { it[i] = entry }
            trips.size >= LIMIT -> return Upsert.LimitReached
            else -> trips + entry
        }
        return Upsert.Saved(next, next.size, next.size >= WARN_FROM)
    }

    fun entry(id: String, now: Long, r: PlanResultDto, bearing8: String, booked: List<String> = emptyList()): SavedTripDto {
        val t = r.trip
        return SavedTripDto(
            id = id, savedAt = now, title = t.title, km = t.km, days = t.days, totalRub = t.cost.totalRub,
            startAt = t.input.startAt, adults = t.input.crew.adults, children = t.input.crew.children,
            dog = t.input.crew.dog, bearing8 = bearing8, shareText = r.shareText, pricesMonthRu = r.pricesMonthRu,
            pricesYear = r.pricesYear, townPrepRu = r.townPrepRu, bookedStops = booked,
            trip = EngineJson.json.parseToJsonElement(r.tripJson) as JsonObject,
        )
    }

    /** A saved trip back as an engine result (the same shape `plan` returns). */
    fun result(s: SavedTripDto): PlanResultDto = PlanResultDto(
        trip = EngineJson.json.decodeFromJsonElement(app.verst.core.model.dto.TripDto.serializer(), s.trip),
        shareText = s.shareText,
        pricesMonthRu = s.pricesMonthRu,
        pricesYear = s.pricesYear,
        townPrepRu = s.townPrepRu,
        tripJson = s.trip.toString(),
    )

    /** Order of D-1: by start date, then by save time. */
    fun ordered(trips: List<SavedTripDto>): List<SavedTripDto> = trips.sortedWith(compareBy({ it.startAt ?: "" }, { it.savedAt }))
}
