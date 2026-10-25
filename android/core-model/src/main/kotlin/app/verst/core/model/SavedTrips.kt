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
    val townGenRu: Map<String, String> = emptyMap(),
    /** D-10 / 5.7 §8: per overnight stop id, the hotel the crew marked «Забронировали» (one per night). */
    val bookedHotels: Map<String, String> = emptyMap(),
    /** The engine's private trip (empty for a walk). */
    val trip: JsonObject = JsonObject(emptyMap()),
    /** DEV-308 schema 2: `trip` | `walk`. Schema 1 entries are trips. */
    val kind: String = "trip",
    /** DEV-308: the `city_route` result verbatim for a walk. */
    val walk: JsonObject? = null,
    /** ADR-0011: `fits` / `small_overrun` (fitted plans) or `over` (a minimum shown over budget), for the D-1 dot. */
    val budgetStatus: String? = null,
)

/**
 * P1-2 `last.json`: the current trip (saved or not) and where the user was, so a process death or a
 * force-stop + relaunch comes back to the same screen. [screen]: "road" | "waybill" | "exit" | null (elsewhere).
 */
@Serializable
data class LastTripDto(
    val schema: Int = SavedTrips.SCHEMA,
    val trip: SavedTripDto,
    val savedId: String? = null,
    val screen: String? = null,
    val exitStopId: String? = null,
    /** S3-R1 focus restore: the Road-ahead row acted on (Exit, replace, stop menu) and the top visible row. */
    val roadFocusId: String? = null,
    val roadTopId: String? = null,
    /** 5.9 §5: the exact scroll offset (px) of Road ahead. */
    val roadScrollY: Int? = null,
)

/** Release review P2-10 / M§6.2: the last crew, pace, budget, mood and origin, restored on the next start. */
@Serializable
data class DefaultsDto(
    val schema: Int = SavedTrips.SCHEMA,
    val frontAdult: Boolean = true,
    val seats: List<String> = listOf("EMPTY", "EMPTY", "EMPTY"),
    val dog: Boolean = false,
    /** null = the pace was never chosen (the route's default applies). */
    val dailyKm: Int? = null,
    val budgetIndex: Int = 2,
    val mood: String? = null,
    val moodTouched: Boolean = false,
    val originLabel: String = "Москва",
    val originLat: Double = 55.7558,
    val originLon: Double = 37.6173,
    val originGen: String = "Москвы",
    /** S3-R1 GPS: the location rationale was answered (allow / «не разрешать»); the origin came from GPS. */
    val locationAsked: Boolean = false,
    val originFromGps: Boolean = false,
    /** S4 (5.10 §10): the walk's own crew, remembered for walks only. */
    val walkAdults: Int = 2,
    val walkChildren: Int = 0,
    val walkDog: Boolean = false,
)

@Serializable
data class SavedTripsFile(val schema: Int = SavedTrips.SCHEMA, val trips: List<SavedTripDto> = emptyList())

/** Pure rules of the saved-trips file (M§6: schema 1, ≤ 50, warning from 45); the app adds the file I/O. */
object SavedTrips {
    /** last.json / defaults.json schema. */
    const val SCHEMA = 1
    /** DEV-308: saved.json schema (2 = `kind` + walks); 1 is read and written back as 2 on the next save. */
    const val TRIPS_SCHEMA = 2
    const val LIMIT = 50
    const val WARN_FROM = 45

    /** An unreadable file or an unknown schema gives an empty list (never a crash at start). */
    fun decode(text: String?): List<SavedTripDto> = decodeOrNull(text) ?: emptyList()

    /** Like [decode] but tells "unreadable" (null) apart from "empty" (P1-1: an unreadable file is kept aside). */
    fun decodeOrNull(text: String?): List<SavedTripDto>? {
        if (text.isNullOrBlank()) return emptyList()
        return try {
            val f = EngineJson.json.decodeFromString(SavedTripsFile.serializer(), text)
            if (f.schema in 1..TRIPS_SCHEMA) f.trips else null // an unknown (newer) schema: kept aside by the store
        } catch (_: Exception) {
            null
        }
    }

    fun encodeDefaults(d: DefaultsDto): String = EngineJson.json.encodeToString(DefaultsDto.serializer(), d)

    fun decodeDefaults(text: String?): DefaultsDto? = try {
        text?.takeIf { it.isNotBlank() }?.let { EngineJson.json.decodeFromString(DefaultsDto.serializer(), it) }?.takeIf { it.schema == SCHEMA }
    } catch (_: Exception) {
        null
    }

    fun encodeLast(l: LastTripDto): String = EngineJson.json.encodeToString(LastTripDto.serializer(), l)

    fun decodeLast(text: String?): LastTripDto? = try {
        text?.takeIf { it.isNotBlank() }?.let { EngineJson.json.decodeFromString(LastTripDto.serializer(), it) }?.takeIf { it.schema == SCHEMA }
    } catch (_: Exception) {
        null
    }

    fun encode(trips: List<SavedTripDto>): String = EngineJson.json.encodeToString(SavedTripsFile.serializer(), SavedTripsFile(TRIPS_SCHEMA, trips))

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

    fun entry(id: String, now: Long, r: PlanResultDto, bearing8: String, booked: Map<String, String> = emptyMap()): SavedTripDto {
        val t = r.trip
        return SavedTripDto(
            id = id, savedAt = now, title = t.title, km = t.km, days = t.days, totalRub = t.cost.totalRub,
            startAt = t.input.startAt, adults = t.input.crew.adults, children = t.input.crew.children,
            dog = t.input.crew.dog, bearing8 = bearing8, shareText = r.shareText, pricesMonthRu = r.pricesMonthRu,
            pricesYear = r.pricesYear, townPrepRu = r.townPrepRu, townGenRu = r.townGenRu, bookedHotels = booked,
            trip = EngineJson.json.parseToJsonElement(r.tripJson) as JsonObject,
            budgetStatus = t.budgetFit?.status ?: if (t.cost.overBudget && t.cost.budgetRub != null) "over" else null,
        )
    }

    /** DEV-308: a walk for «Мои поездки» (title, ≈ km, the total, the walk verbatim). */
    fun walkEntry(id: String, now: Long, w: app.verst.core.model.dto.WalkRouteDto): SavedTripDto = SavedTripDto(
        id = id, savedAt = now, title = w.titleRu, km = kotlin.math.round(w.walkKm).toInt(), days = 0,
        totalRub = w.cost.totalRub, startAt = w.startAt, adults = w.people, kind = "walk",
        walk = EngineJson.json.parseToJsonElement(w.json) as JsonObject,
    )

    /** A saved trip back as an engine result (the same shape `plan` returns). */
    fun result(s: SavedTripDto): PlanResultDto = PlanResultDto(
        trip = EngineJson.json.decodeFromJsonElement(app.verst.core.model.dto.TripDto.serializer(), s.trip),
        shareText = s.shareText,
        pricesMonthRu = s.pricesMonthRu,
        pricesYear = s.pricesYear,
        townPrepRu = s.townPrepRu,
        townGenRu = s.townGenRu,
        tripJson = s.trip.toString(),
    )

    /** Order of D-1: by start date, then by save time. */
    fun ordered(trips: List<SavedTripDto>): List<SavedTripDto> = trips.sortedWith(compareBy({ it.startAt ?: "" }, { it.savedAt }))
}
