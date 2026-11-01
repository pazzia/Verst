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
    /** API v3 (ADR-0015 §3): `p18` | `wikipedia` | `nearby` (Commons geosearch ≤ 300 m → «ФОТО РЯДОМ»). */
    val source: String? = null,
)

@Serializable
data class PoiHoursDto(
    val textRu: String? = null,
    val verified: Boolean = false,
    /** API v3: today's hours («11:00–20:00»), open now, round the clock. */
    val todayRu: String? = null,
    val openNow: Boolean? = null,
    val allDay: Boolean = false,
    /** ADR-0019 E-1: false = nobody knows the hours («часы не известны — уточните»); absent in older engines. */
    val known: Boolean = true,
)

@Serializable
data class PoiTicketDto(
    val adultRub: Int? = null,
    val childRub: Int? = null,
    val estimate: Boolean = false,
    /** ADR-0019 E-2: false = the price is unknown («цена билета неизвестна»), never «вход свободный». */
    val known: Boolean = true,
)

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
    /** API v3 (ADR-0015 §2): «объект наследия федерального значения · есть в Викигиде». */
    val whyRu: String? = null,
    /** API v3 (ADR-0015 §3): where [descriptionRu] comes from: `wikipedia` | `wikivoyage` | `osm` | `wikidata`. */
    val descSource: String? = null,
    val dogsAllowed: Boolean? = null,
    val parking: ParkingDto? = null,
    /** M6 `poi_details` v3: the text (Wikipedia / Wikivoyage / OSM …) and where it comes from; the data level 1–4. */
    val extractRu: String? = null,
    val extractSource: ExtractSourceDto? = null,
    val cardLevel: Int? = null,
    val quality: Int? = null,
    val fee: String? = null,
    val website: String? = null,
    /** M9: the place's data comes from OpenStreetMap (ODbL attribution on the card). */
    val osmSource: Boolean? = null,
    /** M9: the category label as given; curated | wikidata | osm and the ODbL line for OSM-only places. */
    val poiKindRu: String? = null,
    val placeSource: String? = null,
    val placeAttributionRu: String? = null,
) {
    /** The card text: the v3 extract, else the Sprint 3 description. */
    val textRu: String? get() = extractRu?.takeIf { it.isNotBlank() } ?: descriptionRu
    /** `wikipedia` | `wikivoyage` | `osm` | `wikidata` … */
    val textSource: String? get() = extractSource?.key ?: descSource
}

/** R-09 (ODbL package): [url] = the article the extract comes from (Wikipedia / Wikivoyage), [abridged] = the text is cut. */
@Serializable
data class ExtractSourceDto(
    val key: String? = null,
    val nameRu: String? = null,
    val licence: String? = null,
    val url: String? = null,
    val licenceUrl: String? = null,
    val abridged: Boolean = false,
)

// ------------------------------------------------------------------------------------------ hand-off (ADR-0014)

@Serializable
data class HandoffPointDto(val lat: Double, val lon: Double, val nameRu: String? = null, val role: String? = null)

@Serializable
data class HandoffLinksDto(
    val navigator: String? = null,
    val maps: String? = null,
    val web: String? = null,
    /** API v3 (ADR-0015 §1): the Навигатор to the next point only (unsigned launches are limited to 5 a day). */
    val navigatorNext: String? = null,
)

@Serializable
data class HandoffPartDto(
    val index: Int = 1,
    val points: List<HandoffPointDto> = emptyList(),
    val links: HandoffLinksDto = HandoffLinksDto(),
    /** API v3: the next point of the day (the target of `navigatorNext`). */
    val next: HandoffPointDto? = null,
    /** API v3 with `signing`: the link strings the app signs (SHA256withRSA) and appends `&signature=` to. */
    val toSign: Map<String, String>? = null,
)

@Serializable
data class HandoffDto(
    val mode: String,
    val day: Int? = null,
    val parts: List<HandoffPartDto> = emptyList(),
    val truncated: Boolean = false,
    /** API v3: the engine's recommended order (`maps`, `navigatorNext`, `web` while unsigned). */
    val order: List<String> = emptyList(),
)

// ------------------------------------------------------------------------------------------ city (ADR-0013)

@Serializable
data class CityPresetDto(
    /** Architect (S3-QA P0-01), when it lands: the engine's default start of this preset («2026-10-24T10:00»). */
    val startAt: String? = null,
    /** Architect S3-QA: [startAt] is on the next day (the window is over for today). */
    val startsTomorrow: Boolean? = null,
    val preset: String,
    val available: Boolean = true,
    val count: Int = 0,
    val defaultDurationMin: Int = 240,
    val defaultPace: String? = null,
    val adultOnly: Boolean = false,
    val titleRu: String = "",
    /** CEO 29.10: not available because our catalogue has no such places in this town (a gap of our base). */
    val noData: Boolean = false,
    /** CEO 29.10: the engine's reason for [noData] («У нас пока нет данных о рюмочных в этом городе — …»). */
    val noDataRu: String? = null,
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
    /** API v3: today's hours (untimed walks show them as a pill; timed ones as «открыто до …»). */
    val hours: WalkHoursDto? = null,
    /** API v3: the whitelist kind (ADR-0015 §2) for the `KindTag`; the old `kind` stays the pictogram key. */
    val poiKind: String? = null,
    /** API v3: `osm | wikidata | default` — replaces `hoursVerified`. */
    val hoursSource: String? = null,
    /** M9: the category label to show as given, and where the place comes from. */
    val poiKindRu: String? = null,
    val placeSource: String? = null,
    /** CEO 29.10: facts open data does not give («price» for OSM restaurants and cafés: `costRub` 0 is not «free»). */
    val unknownFacts: List<String> = emptyList(),
    /** CEO 29.10: the OSM `cuisine` tag of a food place as given («georgian;pizza»); shown only through [cuisineTags] words. */
    val cuisine: String? = null,
) {
    val isBar: Boolean get() = kind in BarKinds
    /** CEO 29.10: a restaurant, café, fast food or food court from OSM (`catalogue_food`). */
    val isFood: Boolean get() = kind in FoodKinds
    /** CEO 29.10: the engine does not know the price — never show 0 ₽ or «бесплатно» for it. */
    val priceUnknown: Boolean get() = "price" in unknownFacts
    /** Indoor places a dog usually may not enter (5.11 §10.4 `walk_stop_dog_no`). */
    val indoor: Boolean get() = isBar || (poiKind ?: kind) in IndoorKinds
}

/** `stops[].hours` (v3): «10:00–18:00» today, open now (null = unknown), where the hours come from. */
@Serializable
data class WalkHoursDto(val todayRu: String? = null, val openNow: Boolean? = null, val source: String? = null, val closedDayRu: String? = null, val allDay: Boolean = false)

/** ADR-0015 §6 (engine `INDOOR_KINDS`); CEO 29.10: restaurants, cafés and food courts are indoor too (fast food is often a kiosk). */
val IndoorKinds = setOf("museum", "theatre", "interactive", "gallery", "cafe", "restaurant", "food_court")

/** CEO 29.10: the engine's food kinds (`FOOD_KINDS`). */
val FoodKinds = setOf("restaurant", "cafe", "fast_food", "food_court")

/**
 * CEO 29.10: the OSM `cuisine` tags of a food place («georgian;pizza» → georgian, pizza), in tag order. The app shows
 * only the ones it has words for (`feature.common.cuisineWords`) — never a raw English tag.
 */
fun cuisineTags(cuisine: String?): List<String> =
    cuisine.orEmpty().split(';', ',').map { it.trim().lowercase().replace(' ', '_') }.filter { it.isNotEmpty() }.distinct()

val BarKinds = setOf("bar", "ryumochnaya", "pub", "craft", "beer")

@Serializable
data class WalkCostLineDto(val key: String, val rub: Int = 0)

@Serializable
data class WalkCostDto(val totalRub: Int = 0, val lines: List<WalkCostLineDto> = emptyList(), val budgetRub: Int? = null)

/** `city_route.shorter`: `reason` places | budget, the minutes, the engine's sentence. */
@Serializable
data class WalkShorterDto(val reason: String = "places", val requestedMin: Int? = null, val actualMin: Int? = null, val messageRu: String? = null)

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
    /** API v3: a hash of the input; a result whose key is not the current request's is stale (5.11 §10.2). */
    val requestKey: String? = null,
    /** Architect S3-QA P1-02: why the walk is shorter than asked (null = it is not). */
    val shorter: WalkShorterDto? = null,
    val requestedDurationMin: Int? = null,
    /** M4: «без ограничения» answered (no times; `durationMin`, `endAt`, the stop times are null). */
    val unlimited: Boolean = false,
    /** M4: crew notes («С собакой: в закрытые места кто-то зайдёт один…»). */
    val crewNotesRu: List<String> = emptyList(),
    val interestsWidened: Boolean = false,
    @Transient val json: String = "",
) {
    val adultOnly: Boolean get() = responsibleNoteRu != null
    /** CEO 29.10: a stop whose price open data does not give (OSM restaurants, cafés) — the total leaves it out. */
    val priceUnknown: Boolean get() = stops.any { it.priceUnknown }

    /** «без ограничения» (v3 `durationMin: null`): no times, the hours of each place instead. */
    val untimed: Boolean get() = unlimited || input?.get("durationMin") is kotlinx.serialization.json.JsonNull ||
        (startAt == null && stops.isNotEmpty() && stops.all { it.arriveAt == null })

    /**
     * S3-QA P0-01: the walk starts on a later day than «now» in the town's time zone. The engine's flag
     * (`startsTomorrow`) wins when present; otherwise derived from `startAt` + `tz`.
     */
    fun startsTomorrow(nowMs: Long = System.currentTimeMillis()): Boolean {
        // the date of `startAt` against today in the town zone (a saved walk reopened the next day is «today»);
        // the engine flag only when there is no start time
        val at = startAt ?: return startsTomorrowFlag ?: false
        val zone = runCatching { java.time.ZoneId.of(tz ?: "Europe/Moscow") }.getOrNull() ?: return startsTomorrowFlag ?: false
        val day = runCatching { java.time.LocalDateTime.parse(at).toLocalDate() }.getOrNull() ?: return startsTomorrowFlag ?: false
        return day.isAfter(java.time.Instant.ofEpochMilli(nowMs).atZone(zone).toLocalDate())
    }

    /** The asked duration: the engine's `requestedDurationMin`, else the request echoed in `input`. */
    val requestedMin: Int? get() = requestedDurationMin
        ?: (input?.get("durationMin") as? kotlinx.serialization.json.JsonPrimitive)?.content?.toIntOrNull()

    /**
     * 5.11 §9 (S3-QA P1-02): the engine's `shorter` decides (an engine that reports `requestedDurationMin` is
     * authoritative); an older walk without the field falls back to «≥ 30 min shorter than asked».
     */
    val shorterThanAsked: Boolean get() = when {
        shorter != null -> true
        requestedDurationMin != null -> false
        else -> requestedMin?.let { it - durationMin >= 30 } ?: false
    }
    val people: Int get() = (input?.get("crew") as? JsonObject)?.let { c ->
        ((c["adults"] as? kotlinx.serialization.json.JsonPrimitive)?.content?.toIntOrNull() ?: 0) +
            ((c["children"] as? kotlinx.serialization.json.JsonPrimitive)?.content?.toIntOrNull() ?: 0)
    }?.takeIf { it > 0 } ?: 2
}
