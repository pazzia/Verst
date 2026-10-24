package app.verst.core.model.dto

import kotlinx.serialization.Serializable

/** DEV-SLICE subset of the engine JSON (M§4 `dto/`): only the fields the thin slice renders. */

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
)

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
data class CostDto(
    val totalRub: Int,
    val perPersonRub: Int = 0,
    val budgetRub: Int? = null,
    val remainingRub: Int? = null,
    val overBudget: Boolean = false,
)

@Serializable
data class WarningDto(val code: String, val day: Int? = null, val message: String? = null)

@Serializable
data class CrewDto(val adults: Int = 1, val children: Int = 0, val dog: Boolean = false)

@Serializable
data class TripInputDto(val crew: CrewDto = CrewDto(), val dailyKm: Int = 300, val budget: Int? = null)

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

@Serializable
data class PlanResultDto(val trip: TripDto, val shareText: String = "")
