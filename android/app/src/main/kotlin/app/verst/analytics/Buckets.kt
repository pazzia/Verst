package app.verst.analytics

import java.time.LocalDate

/**
 * Value buckets of the tracking plan §2.4. A bucket holds its lower bound: 150 km → `150-300`, 1 200 km → `>1200`,
 * 3 000 ₽ → `3-5k`. Amounts are roubles, distances kilometres.
 */
object Buckets {
    /** No figure for the request yet (ПОЕХАЛИ beat the first estimate). */
    const val UNKNOWN = "unknown"

    private val KM = listOf(150 to "<150", 300 to "150-300", 500 to "300-500", 800 to "500-800", 1_200 to "800-1200")
    private val TOTAL = listOf(10_000 to "<10k", 20_000 to "10-20k", 40_000 to "20-40k", 80_000 to "40-80k")
    private val PRICE = listOf(3_000 to "<3k", 5_000 to "3-5k", 8_000 to "5-8k", 12_000 to "8-12k")

    private fun pick(value: Int, bounds: List<Pair<Int, String>>, top: String): String =
        bounds.firstOrNull { value < it.first }?.second ?: top

    /** `km_bucket`: route length. */
    fun km(km: Int?): String = km?.let { pick(it, KM, ">1200") } ?: UNKNOWN

    /** `total_bucket`: the Waybill total. */
    fun total(rub: Int): String = pick(rub, TOTAL, ">80k")

    /** `price_bucket`: one night of the selected hotel for the crew (the price 5.7 shows). */
    fun price(rub: Int?): String = rub?.takeIf { it > 0 }?.let { pick(it, PRICE, ">12k") } ?: UNKNOWN

    /** `children`: `0`, `1`, `2`, `3+`. */
    fun children(n: Int): String = if (n >= 3) "3+" else n.coerceAtLeast(0).toString()

    /** `params_changed` adults: `1` … `7`. */
    fun adults(n: Int): String = n.coerceIn(1, 7).toString()

    /** `params_changed` pace: the km/day step itself (150 … 900, steps of 50, as on Instruments). */
    fun pace(dailyKm: Int): String = (dailyKm / 50 * 50).toString()

    /** `params_changed` budget: the preset (`20k` … `80k`) or `none` («не важно»). */
    fun budget(rub: Int?): String = rub?.let { "${it / 1_000}k" } ?: "none"

    /** `yes` / `no`. */
    fun yesNo(on: Boolean): String = if (on) "yes" else "no"

    /** `start_date`: the trip's first day `yyyy-mm-dd` from an engine time («2026-10-24T08:00»); null if unreadable. */
    fun date(engineTime: String?): String? =
        engineTime?.takeIf { it.length >= 10 }?.let { runCatching { LocalDate.parse(it.substring(0, 10)) }.getOrNull() }?.toString()

    /** An engine code or kind as a short token (`UNREACHABLE`, `sight`); anything else becomes `OTHER`. */
    fun token(value: String?): String = value?.takeIf { TOKEN.matches(it) } ?: "OTHER"

    private val TOKEN = Regex("[A-Za-z0-9_]{1,32}")
}
