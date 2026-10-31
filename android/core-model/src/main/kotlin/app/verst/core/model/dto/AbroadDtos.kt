package app.verst.core.model.dto

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/*
 * CEO 29.10, trips abroad wave 1 (docs/plan/abroad-wave1-engine.md «Формат ответа»): only the server plans into
 * BY KZ GE AB AM UZ KG TR, so only a server trip carries these. Every field has a default: a trip planned in Russia
 * (or saved before) decodes exactly as before, and an engine field the app does not know yet is ignored.
 * Money abroad is in the local currency as the engine's decimal string («36.89»); `rub` is set only with a Bank of
 * Russia rate on the server.
 */

/** A source of a fact abroad: the page and its kind (`official` / `primary` / `secondary`, with the Russian word). */
@Serializable
data class SourceDto(
    val url: String = "",
    val type: String? = null,
    val typeRu: String? = null,
)

/** A fact, document, rule or risk abroad with its sources. [appliesOnTripDate]: a seasonal risk on the trip's dates. */
@Serializable
data class AbroadFactDto(
    val textRu: String = "",
    val sources: List<SourceDto> = emptyList(),
    val appliesOnTripDate: Boolean? = null,
)

/**
 * A fee or an insurance of the country entered. [counted]: the amount is in the trip's «учтённые суммы»
 * (mandatory, from an official or primary source, not contradicted); otherwise [notCountedRu] says why.
 */
@Serializable
data class AbroadFeeDto(
    val key: String = "",
    val textRu: String = "",
    val mandatory: Boolean = false,
    val counted: Boolean = false,
    val notCountedWhy: String? = null,
    val notCountedRu: String? = null,
    val currency: String? = null,
    val amount: String? = null,
    val periodDays: Int? = null,
    val rub: Int? = null,
    val inRoubleTotal: Boolean = false,
    val sources: List<SourceDto> = emptyList(),
    val ruleSources: List<SourceDto> = emptyList(),
    val unverified: Boolean = true,
)

/**
 * The `border` field of a `kind: "border"` stop: the crossing, its approximate point, the wait (unknown on every
 * crossing but Псоу — then [bufferMin] is the planner's own margin, not a fact), the facts, risks, documents, fees
 * and rules of the country entered. Nothing of it was checked ([unverified]).
 */
@Serializable
data class BorderDto(
    val crossingId: String = "",
    val nameRu: String? = null,
    val from: String? = null,
    val to: String? = null,
    val fromRu: String? = null,
    val toRu: String? = null,
    /** A border without a checkpoint (Россия — Беларусь): a mark on the road, no stop (0 min). */
    val marker: Boolean = false,
    val coordsApprox: Boolean = false,
    val coordsNoteRu: String? = null,
    val waitKnown: Boolean = false,
    val waitRu: String? = null,
    val waitSources: List<SourceDto> = emptyList(),
    val bufferMin: Int = 0,
    val bufferRu: String? = null,
    val facts: List<AbroadFactDto> = emptyList(),
    val risks: List<AbroadFactDto> = emptyList(),
    val documents: List<AbroadFactDto> = emptyList(),
    val fees: List<AbroadFeeDto> = emptyList(),
    val rules: List<AbroadFactDto> = emptyList(),
    val unverified: Boolean = true,
    val checkedAt: String? = null,
    val noteRu: String? = null,
)

/** Fuel in a country abroad: the litres, the sourced price per litre and the [amount] in [currency]. */
@Serializable
data class AbroadFuelDto(
    val fuelType: String? = null,
    val litres: Double = 0.0,
    val currency: String? = null,
    val sources: List<SourceDto> = emptyList(),
    val noteRu: String? = null,
    val unverified: Boolean = true,
    val pricePerLitre: String? = null,
    val priceRange: List<String>? = null,
    val validFrom: String? = null,
    /** null: no sourced price (Абхазия, Армения) — «не учтено». */
    val amount: String? = null,
    val rub: Int? = null,
    /** In the rouble fuel line (a Bank of Russia rate on the server); otherwise in [currency] only. */
    val inRoubleTotal: Boolean = false,
)

/** Toll roads of a country: `zero` (Беларусь for EAEU cars, counted as 0) or not counted, with the sources' text. */
@Serializable
data class AbroadTollsDto(
    val status: String? = null,
    val counted: Boolean = false,
    val textRu: String? = null,
    val sources: List<SourceDto> = emptyList(),
)

/** One country of a trip abroad. */
@Serializable
data class AbroadCountryDto(
    val code: String = "",
    val nameRu: String = "",
    val currency: String? = null,
    val km: Double = 0.0,
    val tz: List<String> = emptyList(),
    val fuel: AbroadFuelDto? = null,
    val tolls: AbroadTollsDto? = null,
    val fees: List<AbroadFeeDto> = emptyList(),
    val nightsUnpriced: Int = 0,
    val mealsUnpriced: Int = 0,
    val documents: List<AbroadFactDto> = emptyList(),
    val rules: List<AbroadFactDto> = emptyList(),
    val unverified: Boolean = true,
)

/** The counted sums abroad in one currency (fuel and counted fees), with roubles when the server has a rate. */
@Serializable
data class LocalTotalDto(
    val currency: String = "",
    val amount: String? = null,
    val rub: Int? = null,
)

/**
 * `trip.abroad`: per country, the counted local sums, the rates used, and [roubleTotalIncomplete] with
 * [notInRoubleTotalRu] — what the rouble total (`cost.totalRub`) leaves out.
 */
@Serializable
data class AbroadDto(
    val unverified: Boolean = true,
    val checkedAt: String? = null,
    val noteRu: String? = null,
    val countries: List<AbroadCountryDto> = emptyList(),
    val localTotals: List<LocalTotalDto> = emptyList(),
    val localTotalsRu: String? = null,
    /** `{asOf, source, rubPerUnit}` of the server's Bank of Russia rates; null without a rates file. */
    val rates: JsonObject? = null,
    val ratesNoteRu: String? = null,
    val roubleTotalIncomplete: Boolean = false,
    val notInRoubleTotalRu: List<String> = emptyList(),
    val totalNoteRu: String? = null,
)

/** Local money as people read it: «≈ 37 GEL» from the engine's «36.89» (whole units, thin-space thousands). */
object LocalMoney {
    /** The amount rounded half-up to whole units, or null when [amount] is not a number. */
    fun whole(amount: String?): Long? = amount?.trim()?.toBigDecimalOrNull()
        ?.setScale(0, java.math.RoundingMode.HALF_UP)?.toLong()

    /** «≈ 37 GEL»; null when the amount or the currency is unknown. */
    fun approx(amount: String?, currency: String?): String? {
        val n = whole(amount) ?: return null
        val c = currency?.takeIf { it.isNotBlank() } ?: return null
        val digits = if (n in Int.MIN_VALUE..Int.MAX_VALUE) app.verst.core.model.RuFormat.thousands(n.toInt()) else n.toString()
        return "≈ $digits $c"
    }
}
