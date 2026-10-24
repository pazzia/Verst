package app.verst.core.model.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.Transient
import kotlinx.serialization.json.JsonObject

/*
 * Sprint 3 mobile API v2 DTOs (M§5.4, docs/contracts/v2; ADR-0011…0014). Every field the app does not
 * need to branch on is optional, so additive engine changes never break decoding.
 */

/** `geo_nearest` / `city_presets` town. */
@Serializable
data class GeoTownDto(
    val id: String,
    val name: String,
    val nameGenRu: String? = null,
    val namePrepRu: String? = null,
    val regionRu: String? = null,
    val lat: Double,
    val lon: Double,
    val population: Int? = null,
    /** IANA zone (Architect, S3-QA P0-01: `city_presets.town.tz`); null until the data run. */
    val tz: String? = null,
)

/** `geo_nearest`: GPS → the origin town; `insideRussia` = the nearest town is ≤ 60 km away. */
@Serializable
data class GeoNearestDto(val town: GeoTownDto? = null, val distanceKm: Double? = null, val insideRussia: Boolean = true)

// ------------------------------------------------------------------------------------------ budget (ADR-0011)

@Serializable
data class BudgetLeverDto(val code: String, val savedRub: Int = 0)

/** `trip.budgetFit` (absent when the first plan fits or there is no budget). */
@Serializable
data class BudgetFitDto(
    val status: String,
    val budgetRub: Int? = null,
    val allowedRub: Int? = null,
    val initialTotalRub: Int? = null,
    val totalRub: Int? = null,
    val levers: List<BudgetLeverDto> = emptyList(),
    val textRu: String? = null,
    val variantOf: String? = null,
) {
    val smallOverrun: Boolean get() = status == "small_overrun"
}

/** One no-fit option, each verified by a plan: `shorten` / `cheaper_route` / `raise_budget`. */
@Serializable
data class BudgetOptionDto(
    val kind: String,
    val budgetRub: Int? = null,
    val days: Int? = null,
    val totalRub: Int? = null,
    val readyRouteId: String? = null,
    val titleRu: String? = null,
    val dailyKm: Double? = null,
    /** false: the cheapest candidate of its kind, still over the tolerance (a number, not a promise). */
    val fits: Boolean = true,
)

/** `plan` → `outcome = no_fit`: the minimum (a trip shown only on request) and the options. */
@Serializable
data class NoFitDto(
    val budgetRub: Int,
    val allowedRub: Int? = null,
    val options: List<BudgetOptionDto> = emptyList(),
    val textRu: String? = null,
    @Transient val minimumTotalRub: Int = 0,
    @Transient val minimumLevers: List<BudgetLeverDto> = emptyList(),
    @Transient val minimum: PlanResultDto? = null,
)

/** `plan` result: a trip, or «не помещается в бюджет». */
sealed interface PlanOutcome {
    data class Plan(val result: PlanResultDto) : PlanOutcome
    data class NoFit(val noFit: NoFitDto) : PlanOutcome
}

// ------------------------------------------------------------------------------------------ cards (ADR-0012 §6)

@Serializable
data class PhotoCreditDto(val author: String? = null, val licence: String? = null, val licenceUrl: String? = null)

@Serializable
data class PoiImageDto(
    val card: String? = null,
    val thumb: String? = null,
    val page: String? = null,
    val credit: PhotoCreditDto? = null,
    val isArea: Boolean = false,
    val labelRu: String? = null,
)

@Serializable
data class PoiHoursDto(val textRu: String? = null, val verified: Boolean = false)

@Serializable
data class PoiTicketDto(val adultRub: Int? = null, val childRub: Int? = null, val estimate: Boolean = false)

/** `poi_details`: sights, hotels and bars only (fuel / rest / start / finish → `NOT_FOUND`). */
@Serializable
data class PoiDetailsDto(
    val id: String,
    val kind: String,
    val poiKind: String? = null,
    val nameRu: String,
    val descriptionRu: String? = null,
    val townName: String? = null,
    val lat: Double? = null,
    val lon: Double? = null,
    val image: PoiImageDto? = null,
    val hours: PoiHoursDto? = null,
    val ticket: PoiTicketDto? = null,
    val isFictional: Boolean = false,
    val heritage: Boolean = false,
    val verified: Boolean = true,
    val attributionRu: List<String> = emptyList(),
    val wikidataId: String? = null,
)

// ------------------------------------------------------------------------------------------ hand-off (ADR-0014)

@Serializable
data class HandoffPointDto(val lat: Double, val lon: Double, val nameRu: String? = null, val role: String? = null)

@Serializable
data class HandoffLinksDto(val navigator: String? = null, val maps: String? = null, val web: String? = null)

@Serializable
data class HandoffPartDto(val index: Int = 1, val points: List<HandoffPointDto> = emptyList(), val links: HandoffLinksDto = HandoffLinksDto())

@Serializable
data class HandoffDto(val mode: String, val day: Int? = null, val parts: List<HandoffPartDto> = emptyList(), val truncated: Boolean = false)

// ------------------------------------------------------------------------------------------ city (ADR-0013)

@Serializable
data class CityPresetDto(
    /** Architect (S3-QA P0-01), when it lands: the engine's default start of this preset («2026-10-24T10:00»). */
    val startAt: String? = null,
    val preset: String,
    val available: Boolean = true,
    val count: Int = 0,
    val defaultDurationMin: Int = 240,
    val defaultPace: String? = null,
    val adultOnly: Boolean = false,
    val titleRu: String = "",
)

@Serializable
data class CityPresetsDto(val town: GeoTownDto? = null, val presets: List<CityPresetDto> = emptyList())

@Serializable
data class WalkPointDto(val lat: Double, val lon: Double, val label: String? = null)

@Serializable
data class WalkStopDto(
    val id: String,
    val poiId: String? = null,
    val kind: String,
    val nameRu: String,
    val lat: Double,
    val lon: Double,
    val arriveAt: String? = null,
    val departAt: String? = null,
    val dwellMin: Int = 0,
    val walkKmFromPrev: Double = 0.0,
    val walkMinFromPrev: Int = 0,
    val costRub: Int = 0,
    val hoursVerified: Boolean = false,
    val noteRu: String? = null,
    val hasPhoto: Boolean = false,
    val tappable: Boolean = true,
) {
    val isBar: Boolean get() = kind in BarKinds
}

val BarKinds = setOf("bar", "ryumochnaya", "pub", "craft", "beer")

@Serializable
data class WalkCostLineDto(val key: String, val rub: Int = 0)

@Serializable
data class WalkCostDto(val totalRub: Int = 0, val lines: List<WalkCostLineDto> = emptyList(), val budgetRub: Int? = null)

@Serializable
data class WalkWarningDto(val code: String, val messageRu: String? = null)

/** `city_route` → `WalkRoute` (ADR-0013 "Output"); [json] is the result verbatim (hand-off input, saving). */
@Serializable
data class WalkRouteDto(
    val kind: String = "walk",
    val id: String = "",
    val titleRu: String,
    val townId: String? = null,
    val townName: String? = null,
    val townPrep: String? = null,
    val preset: String,
    val startAt: String? = null,
    val endAt: String? = null,
    val tz: String? = null,
    val walkKm: Double = 0.0,
    val walkMin: Int = 0,
    val durationMin: Int = 0,
    val returnToStart: Boolean = true,
    val start: WalkPointDto,
    val finish: WalkPointDto? = null,
    val stops: List<WalkStopDto> = emptyList(),
    val cost: WalkCostDto = WalkCostDto(),
    val warnings: List<WalkWarningDto> = emptyList(),
    val responsibleNoteRu: String? = null,
    val approxDistances: Boolean = false,
    val input: JsonObject? = null,
    /** Architect (S3-QA P0-01), when it lands: the walk was moved to the next day's window. */
    @kotlinx.serialization.SerialName("startsTomorrow") val startsTomorrowFlag: Boolean? = null,
    /** Architect (S3-QA P1-02), when it lands: why the walk is shorter than asked (copy key or text). */
    val shorterReason: String? = null,
    @Transient val json: String = "",
) {
    val adultOnly: Boolean get() = responsibleNoteRu != null

    /**
     * S3-QA P0-01: the walk starts on a later day than «now» in the town's time zone. The engine's flag
     * (`startsTomorrow`) wins when present; otherwise derived from `startAt` + `tz`.
     */
    fun startsTomorrow(nowMs: Long = System.currentTimeMillis()): Boolean {
        startsTomorrowFlag?.let { return it }
        val at = startAt ?: return false
        val zone = runCatching { java.time.ZoneId.of(tz ?: "Europe/Moscow") }.getOrNull() ?: return false
        val day = runCatching { java.time.LocalDateTime.parse(at).toLocalDate() }.getOrNull() ?: return false
        return day.isAfter(java.time.Instant.ofEpochMilli(nowMs).atZone(zone).toLocalDate())
    }

    /** The asked duration (the request echoed in `input`); null when absent. */
    val requestedMin: Int? get() = (input?.get("durationMin") as? kotlinx.serialization.json.JsonPrimitive)?.content?.toIntOrNull()

    /** 5.11 §9 (S3-QA P1-02): the engine's walk is ≥ 30 min shorter than asked. */
    val shorterThanAsked: Boolean get() = requestedMin?.let { it - durationMin >= 30 } ?: false
    val people: Int get() = (input?.get("crew") as? JsonObject)?.let { c ->
        ((c["adults"] as? kotlinx.serialization.json.JsonPrimitive)?.content?.toIntOrNull() ?: 0) +
            ((c["children"] as? kotlinx.serialization.json.JsonPrimitive)?.content?.toIntOrNull() ?: 0)
    }?.takeIf { it > 0 } ?: 2
}
