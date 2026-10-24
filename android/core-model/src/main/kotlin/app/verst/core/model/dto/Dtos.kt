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
    val replaceable: Boolean = false,
    val alternatives: List<AlternativeDto> = emptyList(),
    /** Engine copy «Других вариантов…» / «Нашли только один вариант…» when < 2 alternatives. */
    val alternativesNote: String? = null,
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
data class WarningDto(val code: String, val day: Int? = null, val message: String? = null)

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
)

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
    @Transient val tripJson: String = "",
)

/** `mobile.estimate`: the engine's km and days of a trip input before Road ahead (equal to its plan). */
@Serializable
data class EstimateDto(val km: Int, val days: Int)
