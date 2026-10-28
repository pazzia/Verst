package app.verst.core.model

import kotlinx.serialization.Serializable
import kotlin.math.roundToLong

/** Interface language (D-IR-20). The engine's own texts (reasons, place descriptions) stay Russian for now. */
@Serializable
enum class AppLanguage(val tag: String) { RU("ru-RU"), EN("en-US") }

/** NIGHT is the original «За рулём» palette; DAY is «Дневная трасса» (design/tokens-day.json). */
@Serializable
enum class AppTheme { NIGHT, DAY, SYSTEM }

/** Where saved trips live. CLOUD needs accounts and the server; it is shown, not selectable yet. */
@Serializable
enum class TripStorage { DEVICE, FOLDER, CLOUD }

/** The settings of the personal cabinet (D-IR-20), kept on the device in `files/settings.json`. */
@Serializable
data class AppSettings(
    val language: AppLanguage = AppLanguage.RU,
    val currency: String = Money.RUB,
    val theme: AppTheme = AppTheme.NIGHT,
    val storage: TripStorage = TripStorage.DEVICE,
    /** SAF tree URI of the folder that mirrors saved trips (storage = FOLDER). */
    val folderUri: String? = null,
    /** The folder's display name, for the settings row. */
    val folderName: String? = null,
    /** SRV-01: build the trip on the server (`POST /v1/trips/plan`) when online; the phone engine otherwise. */
    val planOnServer: Boolean = false,
    /** Security review 28.10 (В-1): the user read what goes to the server and agreed; asked once, before the switch. */
    val serverConsent: Boolean = false,
    /** The car (traveller К4): litres per 100 km (engine range 4–20), fuel `ai92` / `ai95` / `dt`, tank 20–150 l. */
    val consumption: Double = Car.DEFAULT_CONSUMPTION,
    val fuelType: String = Car.DEFAULT_FUEL,
    val tankL: Int = Car.DEFAULT_TANK,
    val avoidTolls: Boolean = false,
) {
    /** A setting that only takes effect after the app restarts (the palette is read once per process). */
    fun needsRestartComparedTo(old: AppSettings): Boolean = theme != old.theme

    companion object {
        fun decode(text: String?): AppSettings = try {
            if (text.isNullOrBlank()) AppSettings() else EngineJson.json.decodeFromString(serializer(), text).sanitized()
        } catch (_: Exception) {
            AppSettings()
        }

        fun encode(s: AppSettings): String = EngineJson.json.encodeToString(serializer(), s)
    }

    /** An unknown currency (an older build's list) falls back to roubles; a folder without a URI to the device. */
    fun sanitized(): AppSettings = copy(
        currency = currency.takeIf { it in Money.SUPPORTED } ?: Money.RUB,
        consumption = consumption.coerceIn(Car.CONSUMPTION_MIN, Car.CONSUMPTION_MAX),
        fuelType = fuelType.takeIf { it in Car.FUELS } ?: Car.DEFAULT_FUEL,
        tankL = tankL.coerceIn(Car.TANK_MIN, Car.TANK_MAX),
        planOnServer = planOnServer && serverConsent,
        storage = if (storage == TripStorage.FOLDER && folderUri == null) TripStorage.DEVICE
        else if (storage == TripStorage.CLOUD) TripStorage.DEVICE else storage,
    )
}

/** The car of the cost (engine `Vehicle`: consumption 4–20 l/100 km, tank 20–150 l). */
object Car {
    const val DEFAULT_CONSUMPTION = 8.0
    const val DEFAULT_FUEL = "ai95"
    const val DEFAULT_TANK = 50
    const val CONSUMPTION_MIN = 4.0
    const val CONSUMPTION_MAX = 20.0
    const val CONSUMPTION_STEP = 0.5
    const val TANK_MIN = 20
    const val TANK_MAX = 150
    const val TANK_STEP = 5
    val FUELS = listOf("ai92", "ai95", "dt")
}

/** Central Bank of Russia rates, fetched at build time (tools/ci/fetch_rates.py → assets/rates.json). */
@Serializable
data class RatesDto(
    /** Date of the CBR rate, `yyyy-MM-dd`; null when the build could not fetch rates. */
    val asOf: String? = null,
    val source: String = "",
    /** Roubles per one unit of the currency (CBR Value / Nominal). */
    val rubPerUnit: Map<String, Double> = emptyMap(),
) {
    fun has(code: String): Boolean = code == Money.RUB || (rubPerUnit[code] ?: 0.0) > 0.0

    companion object {
        fun decode(text: String?): RatesDto = try {
            if (text.isNullOrBlank()) RatesDto() else EngineJson.json.decodeFromString(serializer(), text)
        } catch (_: Exception) {
            RatesDto()
        }
    }
}

/**
 * Amounts are computed in roubles by the engine; this shows them in the chosen currency at the CBR rate of the build.
 * Without a rate for the currency the rouble amount is shown, so a price is never invented.
 */
object Money {
    const val RUB = "RUB"
    val SUPPORTED = listOf(RUB, "USD", "EUR", "CNY", "KZT", "BYN", "TRY", "AED", "GEL", "AMD", "THB", "IDR")
    private val SYMBOL = mapOf(
        RUB to "₽", "USD" to "$", "EUR" to "€", "CNY" to "¥", "KZT" to "₸", "BYN" to "Br", "TRY" to "₺",
        "AED" to "AED", "GEL" to "₾", "AMD" to "֏", "THB" to "฿", "IDR" to "Rp",
    )
    /** Symbols written before the number ($15); the rest follow it (15 ₸), as in Russian typography for ₽. */
    private val PREFIX = setOf("USD", "EUR", "CNY")
    private const val NBSP = "\u00A0"

    fun symbol(code: String): String = SYMBOL[code] ?: code

    /** The currency actually shown: [code] if the build has its rate, else roubles. */
    fun effective(code: String, rates: RatesDto): String = if (rates.has(code)) code else RUB

    /** Rounded amount in [code] (whole units; ≥ 10 000 to tens; IDR to thousands). */
    fun convert(rub: Int, code: String, rates: RatesDto): Long {
        val c = effective(code, rates)
        if (c == RUB) return rub.toLong()
        val v = rub / rates.rubPerUnit.getValue(c)
        val step = when {
            c == "IDR" -> 1_000.0
            v >= 10_000 -> 10.0
            else -> 1.0
        }
        return ((v / step).roundToLong() * step).toLong()
    }

    /** «18 000 ₽», «$215», «1 540 ₸». Digits are grouped with a thin space like [RuFormat.thousands]. */
    fun format(rub: Int, code: String, rates: RatesDto): String {
        val c = effective(code, rates)
        val n = convert(rub, c, rates)
        val digits = group(n)
        return if (c in PREFIX) symbol(c) + digits else digits + NBSP + symbol(c)
    }

    private fun group(n: Long): String {
        if (n in Int.MIN_VALUE..Int.MAX_VALUE) return RuFormat.thousands(n.toInt())
        val digits = kotlin.math.abs(n).toString()
        val sb = StringBuilder()
        for ((i, ch) in digits.withIndex()) {
            if (i > 0 && (digits.length - i) % 3 == 0) sb.append(RuFormat.THIN)
            sb.append(ch)
        }
        return (if (n < 0) "−" else "") + sb
    }
}
