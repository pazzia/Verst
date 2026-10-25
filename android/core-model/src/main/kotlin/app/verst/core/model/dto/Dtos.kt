package app.verst.core.model.dto

import kotlinx.serialization.Serializable

import kotlinx.serialization.Transient

/** DEV-SLICE subset of the engine JSON (M§4 `dto/`): only the fields the slice renders. */

@Serializable
data class ReadyRouteDto(
    val id: String,
    val title: String,
    val subtitle: String = "",
    val kmTotal: Int,
    val kmSign: Int,
    val ring: String? = null,
    val roundTrip: Boolean = true,
    val daysMin: Int = 1,
    val daysMax: Int = 1,
    val hubTownId: String? = null,
    val bearing8: String = "N",
)

@Serializable
data class SuggestionDto(
    val kind: String,
    val name: String,
    val subtitle: String = "",
    val lat: Double,
    val lon: Double,
    val id: String? = null,
    /** OI-39: «Ярославля» / «Ярославле» for towns (null for places). */
    val nameGenRu: String? = null,
    /** v2 `geo_search` extras (ADR-0012 §5). */
    val namePrepRu: String? = null,
    val population: Int? = null,
    val regionRu: String? = null,
    val poiKind: String? = null,
    val hasPhoto: Boolean = false,
) {
    /** Key of the row's engine road km («lat,lon»). */
    val pointKey: String get() = "$lat,$lon"
}

@Serializable
data class StopDto(
    val id: String,
    val seq: Int = 0,
    val day: Int = 1,
    val kind: String,
    val sign: String,
    val name: String,
    val note: String? = null,
    val reason: String? = null,
    val arriveAt: String? = null,
    val departAt: String? = null,
    val kmFromPrev: Int = 0,
    val kmAt: Int = 0,
    val dwellMin: Int = 0,
    val tags: List<String> = emptyList(),
    val costRub: Int = 0,
    val verified: Boolean = true,
    val townId: String? = null,
    val placeId: String? = null,
    /** Stop coordinates (engine `lat`/`lon`) for the navigator hand-off (S3-R1); null in old saved trips. */
    val lat: Double? = null,
    val lon: Double? = null,
    val replaceable: Boolean = false,
    val alternatives: List<AlternativeDto> = emptyList(),
    /** Engine copy «Других вариантов…» / «Нашли только один вариант…» when < 2 alternatives. */
    val alternativesNote: String? = null,
    /** Overnight stops: up to 3 hotels (the engine's choice first) and the selected one (5.7). */
    val hotelOptions: List<HotelOptionDto> = emptyList(),
    val selectedHotelId: String? = null,
    /** API v3 (ADR-0015 §7): driven km from the trip start (detours included) and the rest of the trip. */
    val kmDriven: Int? = null,
    val kmLeft: Int? = null,
    /** API v3 (ADR-0015 §2): the whitelist kind of a sight (`museum`, `park`, …) — `kind` is the stop kind. */
    val poiKind: String? = null,
    val quality: Int? = null,
    /** API v3 (ADR-0015 §5): a «Весело и познавательно» stop and whom it is for (child / dog / adults). */
    val funFor: List<String> = emptyList(),
    /** API v3 (ADR-0015 §4): the zone tariff of the stop; null with a parking-aware engine = unknown. */
    val parking: ParkingDto? = null,
    /** Rest areas: what OSM says is there (`toilets`, `tables`, `shelter`, `cafe`, `playground`). */
    val amenities: List<String> = emptyList(),
) {
    /** A «Разминка» stop of the fun mood (5.5 §10.4). */
    val stretch: Boolean get() = funFor.isNotEmpty()
}

/**
 * ADR-0015 §4 stop parking: `rub` = the stay (rounded to 10 ₽), `rubPerHour` the zone rate, `source`
 * zone | osm | free | unknown. The Russian texts are optional engine extras for the sheet (5.5 §10.6).
 */
@Serializable
data class ParkingDto(
    val rubPerHour: Int? = null,
    val rub: Int? = null,
    val source: String? = null,
    val hours: Double? = null,
    val zoneRu: String? = null,
    val whereRu: String? = null,
    val sundayRu: String? = null,
    val freeRu: String? = null,
    val noteRu: String? = null,
) {
    val free: Boolean get() = source == "free" || (rub == 0 && source != "unknown")
    val known: Boolean get() = free || (rub != null && source != "unknown")
}

/** A 5.7 hotel option: price per night for the whole crew, distance route → hotel for the exit sign. */
@Serializable
data class HotelOptionDto(
    val placeId: String,
    val name: String,
    val tags: List<String> = emptyList(),
    val priceNightRub: Int = 0,
    val rooms: Int = 1,
    val priceCrewRub: Int = 0,
    val verified: Boolean = true,
    /** OI-41: route (motorway exit) → hotel, metres; 0 = unknown. */
    val exitDistanceM: Int = 0,
)

/** One D-6 alternative of a stop (A§6.11, A§16.6): the stop it would become and its deltas. */
@Serializable
data class AlternativeDto(
    val id: String,
    val placeId: String? = null,
    val name: String,
    val deltaMin: Int = 0,
    val deltaRub: Int = 0,
    val shiftMin: Int = 0,
    val stop: StopDto? = null,
    /** ADR-0011: choosing this alternative would take the trip over the allowed budget. */
    val breaksBudget: Boolean = false,
)

@Serializable
data class DayDto(
    val day: Int,
    val km: Int,
    val driveMin: Int = 0,
    val startAt: String? = null,
    val endAt: String? = null,
    val overBudget: Boolean = false,
    val stops: List<StopDto> = emptyList(),
)

@Serializable
data class CostBreakdownDto(val label: String, val formula: String = "", val rub: Int = 0)

/** One Waybill line (A§7.2): key fuel|tolls|lodging|food|tickets|reserve, engine title and formula text. */
@Serializable
data class CostLineDto(
    val key: String,
    val title: String,
    val rub: Int = 0,
    val formula: String = "",
    val asOf: String? = null,
    val enabled: Boolean = true,
    val breakdown: List<CostBreakdownDto> = emptyList(),
    /** ADR-0015 §4 «Парковки»: stops without tariff data («+ ещё 2 места без данных»). */
    val unknownCount: Int = 0,
)

@Serializable
data class CostDto(
    val totalRub: Int,
    val perPersonRub: Int = 0,
    val budgetRub: Int? = null,
    val remainingRub: Int? = null,
    val overBudget: Boolean = false,
    val lines: List<CostLineDto> = emptyList(),
    val reserveOn: Boolean = true,
    val subtotalRub: Int = 0,
    val hints: List<String> = emptyList(),
    val pricesAsOf: String? = null,
)

@Serializable
data class WarningDto(
    val code: String,
    val day: Int? = null,
    val message: String? = null,
    /** release-s3: `"info"` = a notice (5.5 §9 info line, not a yellow plate); absent = a warning about this trip. */
    val level: String? = null,
)

@Serializable
data class CrewDto(val adults: Int = 1, val children: Int = 0, val dog: Boolean = false)

@Serializable
data class TripInputDto(
    val crew: CrewDto = CrewDto(),
    val dailyKm: Int = 300,
    val budget: Int? = null,
    val startAt: String? = null,
    val reserveOn: Boolean = true,
    val readyRouteId: String? = null,
)

@Serializable
data class TripDto(
    val id: String? = null,
    val title: String,
    val km: Int,
    val days: Int,
    val nights: Int = 0,
    val roundTrip: Boolean = false,
    val daysList: List<DayDto>,
    val cost: CostDto,
    val warnings: List<WarningDto> = emptyList(),
    val input: TripInputDto = TripInputDto(),
    /** ADR-0011: present when the engine fitted the plan to the budget. */
    val budgetFit: BudgetFitDto? = null,
    /** ADR-0012 §4: the route left the fixture road graph (synthetic) — distances are approximate. */
    val approxDistances: Boolean = false,
)

@Serializable
data class StopEventDto(val id: String? = null, val kind: String? = null, val sign: String? = null, val name: String? = null)

/** One progress event of `mobile.plan` (`events.event_to_json`): `stage` or `stop`. */
@Serializable
data class PlanEventDto(
    val event: String,
    val key: String? = null,
    val text: String? = null,
    val progress: Double? = null,
    val day: Int? = null,
    val stop: StopEventDto? = null,
)

/** `mobile.py` error object; `message` is diagnostic English, the UI chooses copy by `code` only. */
@Serializable
data class EngineErrorDto(
    val code: String,
    val message: String? = null,
    val field: String? = null,
    val reason: String? = null,
    val pointIndex: Int? = null,
    val roadKm: Double? = null,
    val detail: String? = null,
    /**
     * API v3 (ADR-0015 §6): `NOT_ENOUGH_POIS` options the engine has checked — each differs from the request and
     * succeeds. Kept raw: `{"durationMin": null}` (explicit null) means «без ограничения».
     */
    val suggestions: kotlinx.serialization.json.JsonArray? = null,
    /** v3: how many places were found for the failed request (the «Нашли N» line). */
    val count: Int? = null,
) {
    /** The engine's verified suggestions, decoded defensively (unknown shapes are skipped). */
    val walkSuggestions: List<WalkSuggestion>
        get() = suggestions.orEmpty().mapNotNull { WalkSuggestion.from(it) }
}

/** One `NOT_ENOUGH_POIS` suggestion: a duration (null = unlimited), a preset, or «return the removed places». */
data class WalkSuggestion(
    val durationMin: Int? = null,
    val unlimited: Boolean = false,
    val preset: String? = null,
    val clearExclude: Boolean = false,
    val count: Int? = null,
) {
    companion object {
        fun from(e: kotlinx.serialization.json.JsonElement): WalkSuggestion? {
            val o = e as? kotlinx.serialization.json.JsonObject ?: return null
            fun prim(k: String) = o[k] as? kotlinx.serialization.json.JsonPrimitive
            val count = prim("count")?.content?.toIntOrNull()
            return when {
                prim("clearExclude")?.content == "true" -> WalkSuggestion(clearExclude = true, count = count)
                o.containsKey("preset") -> prim("preset")?.takeIf { it.isString }?.content?.let { WalkSuggestion(preset = it, count = count) }
                o.containsKey("durationMin") -> {
                    val d = o["durationMin"]
                    if (d is kotlinx.serialization.json.JsonNull) WalkSuggestion(unlimited = true, count = count)
                    else prim("durationMin")?.content?.toIntOrNull()?.let { WalkSuggestion(durationMin = it, count = count) }
                }
                else -> null
            }
        }
    }
}

/**
 * `plan` / `replace_stop` / `patch_cost` result. [tripJson] is the engine's private trip verbatim (with
 * `engineState`): the input of every later engine call on this trip and what is saved (M§6.3).
 */
@Serializable
data class PlanResultDto(
    val trip: TripDto,
    val shareText: String = "",
    val pricesMonthRu: String? = null,
    val pricesYear: String? = null,
    /** townId → prepositional name («Ярославле») for 5.7 copy. */
    val townPrepRu: Map<String, String> = emptyMap(),
    /** townId → genitive name («Ярославля»). */
    val townGenRu: Map<String, String> = emptyMap(),
    @Transient val tripJson: String = "",
)

/** `mobile.estimate`: the engine's km and days of a trip input before Road ahead (equal to its plan). */
@Serializable
data class EstimateDto(
    val km: Int,
    val days: Int,
    /** v2 (ADR-0011): `plan` | `no_fit`, the total and `fits` | `small_overrun` | null. */
    val outcome: String? = null,
    val totalRub: Int? = null,
    val budgetStatus: String? = null,
)

/** `mobile.reverse`: the town at a point with its name forms (OI-39). */
@Serializable
data class PlaceNameDto(val name: String, val subtitle: String = "", val nameGenRu: String? = null, val namePrepRu: String? = null)
