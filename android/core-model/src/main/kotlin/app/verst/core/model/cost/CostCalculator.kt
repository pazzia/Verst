package app.verst.core.model.cost

import java.math.BigDecimal
import java.math.RoundingMode
import kotlinx.serialization.Serializable

/*
 * DEV-104 (DEV-SLICE-3 subset): the numbers of `verst_planner/cost/recompute.py` on the phone, so a reserve
 * toggle, a hotel choice or a replace shows its new total at once; the engine call that follows overwrites the
 * trip (and brings the Russian formula text, which is not ported — see dev-notes). Money is `BigDecimal` with
 * HALF_UP, never Double; the only float is fuel km, which is a float in the units by contract.
 */

@Serializable
data class FuelRegionUnitDto(val regionCode: String, val regionName: String = "", val km: Double, val priceRub: String)

@Serializable
data class FuelUnitsDto(
    val consumption: Double,
    val fuelType: String = "ai95",
    val regions: List<FuelRegionUnitDto> = emptyList(),
    val asOf: String = "",
    val tripKm: Int? = null,
)

@Serializable
data class TollHitDto(val segmentId: String = "", val roadRef: String = "", val rub: Int, val night: Boolean = false)

@Serializable
data class HotelPriceDto(
    val placeId: String,
    val priceNightRub: Int,
    val breakfastIncluded: Boolean = true,
    /** ADR-0011: the room count the engine chose for this option (family rooms); null = `ceil(adults / 2)`. */
    val rooms: Int? = null,
)

@Serializable
data class NightUnitDto(
    val stopId: String,
    val day: Int,
    val townName: String = "",
    val selectedPlaceId: String? = null,
    val priceNightRub: Int,
    val options: List<HotelPriceDto> = emptyList(),
    val defaultPrice: Boolean = false,
    val breakfastIncluded: Boolean = true,
    val breakfastCheckRub: Int = 0,
    /** ADR-0011: explicit room count of the selected hotel (family rooms); null = `ceil(adults / 2)`. */
    val rooms: Int? = null,
)

@Serializable
data class MealUnitDto(val day: Int, val meal: String, val stopId: String? = null, val checkRub: Int)

/** ADR-0015 §4 `cost.units.parking[]`: one stop's stay, already rounded half-up to 10 ₽; `rub` null = unknown. */
@Serializable
data class ParkingUnitDto(
    val stopId: String,
    val rubPerHour: Int? = null,
    val hours: Double? = null,
    val rub: Int? = null,
    val source: String = "unknown",
)

@Serializable
data class TicketUnitDto(val stopId: String, val placeId: String? = null, val name: String = "", val adultRub: Int, val childRub: Int)

/** `cost.units` of the engine trip (codec `_units_to_json`). */
@Serializable
data class CostUnitsDto(
    val fuel: FuelUnitsDto,
    val tolls: List<TollHitDto> = emptyList(),
    val nights: List<NightUnitDto> = emptyList(),
    val meals: List<MealUnitDto> = emptyList(),
    val tickets: List<TicketUnitDto> = emptyList(),
    val reserveFrac: String = "0.10",
    val lineStep: Int = 10,
    val totalStep: Int = 100,
    val childAges: List<Int>? = null,
    val assumedChildAge: Int = 8,
    val childFoodWeightUnder7: String = "0.50",
    val moodJustDrive: Boolean = false,
    /** API v3: empty for an engine without parking (then there is no «Парковки» line at all). */
    val parking: List<ParkingUnitDto> = emptyList(),
)

/** `Alternative.units` (A§16.6): what a replace changes in the cost. */
@Serializable
data class AltUnitsDto(
    val deltaKm: Double = 0.0,
    val regionCode: String = "",
    val checkRub: Int? = null,
    val adultRub: Int? = null,
    val childRub: Int? = null,
    val name: String = "",
    val placeId: String? = null,
    val priceRub: String? = null,
    val regionName: String = "",
    val tripKmDelta: Int = 0,
    /** API v3: the alternative's own parking stay (rounded), when the engine knows it. */
    val parkingRub: Int? = null,
)

@Serializable
data class CostCrew(val adults: Int, val children: Int = 0, val dog: Boolean = false, val childAges: List<Int>? = null)

@Serializable
data class CostOverridesDto(val hotelByStop: Map<String, String> = emptyMap(), val replaced: Map<String, AltUnitsDto> = emptyMap())

data class CostNumbers(
    /** Line rubs by key: fuel, tolls, lodging, food, tickets, parking (API v3, when the units have it), reserve. */
    val lines: Map<String, Int>,
    val subtotalRub: Int,
    val totalRub: Int,
    val perPersonRub: Int,
    val remainingRub: Int?,
    val overBudget: Boolean,
    val hintKeys: List<String>,
    /** The km shown in the fuel formula (A§16.7), rounded half up. */
    val fuelFormulaKm: Int,
)

object CostCalculator {
    private const val CHILD_AGE_LIMIT = 7

    fun dec(x: Double): BigDecimal = BigDecimal(x.toString()) // shortest repr, like Python `Decimal(repr(x))`

    fun roundTo(x: BigDecimal, step: Int): Int =
        x.divide(BigDecimal(step), 12, RoundingMode.HALF_UP).setScale(0, RoundingMode.HALF_UP).toInt() * step

    fun roomsFor(adults: Int): Int = (adults + 1) / 2

    private fun childAges(u: CostUnitsDto, crew: CostCrew): List<Int> = when {
        crew.childAges != null -> crew.childAges
        u.childAges != null && u.childAges.size == crew.children -> u.childAges
        else -> List(crew.children) { u.assumedChildAge }
    }

    private fun foodPeople(u: CostUnitsDto, crew: CostCrew): BigDecimal {
        val w = BigDecimal(u.childFoodWeightUnder7)
        return childAges(u, crew).fold(BigDecimal(crew.adults)) { acc, a -> acc + if (a < CHILD_AGE_LIMIT) w else BigDecimal.ONE }
    }

    private data class Ticket(val adult: Int, val child: Int)

    private fun altTicket(a: AltUnitsDto): Ticket {
        val adult = a.adultRub ?: 0
        return Ticket(adult, a.childRub ?: adult)
    }

    /** A§16.11.4 rule 4: a replaced stop loses its ticket; a sight alternative brings its own. */
    private fun effectiveTickets(u: CostUnitsDto, ov: CostOverridesDto): List<Ticket> {
        val out = mutableListOf<Ticket>()
        for (t in u.tickets) {
            val alt = ov.replaced[t.stopId]
            when {
                alt == null -> out += Ticket(t.adultRub, t.childRub)
                alt.adultRub != null -> out += altTicket(alt)
            }
        }
        val ticketed = u.tickets.map { it.stopId }.toSet()
        ov.replaced.forEach { (sid, a) -> if (sid !in ticketed && a.adultRub != null) out += altTicket(a) }
        return out
    }

    fun recompute(u: CostUnitsDto, crew: CostCrew, reserveOn: Boolean, budgetRub: Int?, ov: CostOverridesDto = CostOverridesDto()): CostNumbers {
        val step = u.lineStep
        val lines = LinkedHashMap<String, Int>()

        // ---- fuel (rule 1: the alternative's region gets + Δkm; a new region at the alternative's price)
        val regions = u.fuel.regions.toMutableList()
        val kmByRegion = LinkedHashMap<String, BigDecimal>()
        regions.forEach { kmByRegion[it.regionCode] = dec(it.km) }
        for (alt in ov.replaced.values) {
            val cur = kmByRegion[alt.regionCode]
            if (cur != null) {
                kmByRegion[alt.regionCode] = cur + dec(alt.deltaKm)
            } else if (alt.priceRub != null && alt.deltaKm > 0) {
                regions += FuelRegionUnitDto(alt.regionCode, alt.regionName, 0.0, alt.priceRub)
                kmByRegion[alt.regionCode] = dec(alt.deltaKm)
            }
        }
        val cons = dec(u.fuel.consumption)
        var fuelExact = BigDecimal.ZERO
        for (r in regions) {
            val km = kmByRegion.getValue(r.regionCode).max(BigDecimal.ZERO)
            fuelExact += (km * cons).movePointLeft(2) * BigDecimal(r.priceRub) // exact ÷ 100 (Kotlin `/` keeps the scale)
        }
        val totalKm = kmByRegion.values.fold(BigDecimal.ZERO) { a, k -> a + k.max(BigDecimal.ZERO) }
        val shownKm = u.fuel.tripKm?.let { BigDecimal(it + ov.replaced.values.sumOf { a -> a.tripKmDelta }) } ?: totalKm
        lines["fuel"] = roundTo(fuelExact, step)

        // ---- tolls
        lines["tolls"] = roundTo(BigDecimal(u.tolls.sumOf { it.rub }), step)

        // ---- lodging (rooms × price after a hotel override) and breakfasts after nights without one
        val legacyRooms = roomsFor(crew.adults)
        var lodging = BigDecimal.ZERO
        val breakfasts = LinkedHashMap<Int, Int>()
        var cheaper = false
        for (n in u.nights) {
            val pick = ov.hotelByStop[n.stopId]?.let { pid -> n.options.firstOrNull { it.placeId == pid } }
            val price = pick?.priceNightRub ?: n.priceNightRub
            val breakfast = pick?.breakfastIncluded ?: n.breakfastIncluded
            val sel = pick?.placeId ?: n.selectedPlaceId
            // ADR-0011 explicit rooms: the picked option's count, else the night's, else the legacy rule.
            val rooms = if (pick != null) pick.rooms ?: legacyRooms else n.rooms ?: legacyRooms
            lodging += BigDecimal(rooms) * BigDecimal(price)
            if (!breakfast) breakfasts[n.day + 1] = n.breakfastCheckRub
            val nightCost = rooms.toLong() * price
            if (n.options.any { it.placeId != sel && (it.rooms ?: legacyRooms).toLong() * it.priceNightRub < nightCost }) cheaper = true
        }
        lines["lodging"] = roundTo(lodging, step)

        // ---- food: people × Σ checks, per day
        val people = foodPeople(u, crew)
        val perDay = sortedMapOf<Int, MutableList<Int>>()
        breakfasts.forEach { (d, c) -> perDay.getOrPut(d) { mutableListOf() } += c }
        for (m in u.meals) {
            val alt = m.stopId?.let { ov.replaced[it] }
            perDay.getOrPut(m.day) { mutableListOf() } += alt?.checkRub ?: m.checkRub
        }
        val food = perDay.values.fold(BigDecimal.ZERO) { a, checks -> a + people * BigDecimal(checks.sum()) }
        lines["food"] = roundTo(food, step)

        // ---- tickets
        val tickets = effectiveTickets(u, ov)
        val ticketExact = tickets.fold(BigDecimal.ZERO) { a, t -> a + BigDecimal(crew.adults * t.adult + crew.children * t.child) }
        val ticketsRub = roundTo(ticketExact, step)
        lines["tickets"] = ticketsRub

        // ---- parking (ADR-0015 §4): Σ of the per-stop stays (integers, already rounded); unknown stays add 0.
        // A replaced stop takes the alternative's stay when known; the engine's answer then overwrites it.
        if (u.parking.isNotEmpty()) {
            val parking = u.parking.sumOf { p -> ov.replaced[p.stopId]?.parkingRub ?: p.rub ?: 0 }
            lines["parking"] = roundTo(BigDecimal(parking), step)
        }

        // ---- totals (A§7.2)
        val subtotal = lines.values.sum()
        val reserve = roundTo(BigDecimal(u.reserveFrac) * BigDecimal(subtotal), step)
        lines["reserve"] = reserve
        val total = roundTo(BigDecimal(subtotal + if (reserveOn) reserve else 0), u.totalStep)
        val perPerson = roundTo(BigDecimal(total).divide(BigDecimal(crew.adults + crew.children), 12, RoundingMode.HALF_UP), u.totalStep)
        val remaining = budgetRub?.let { it - total }
        val over = remaining != null && remaining < 0
        val hints = buildList {
            if (over) {
                if (cheaper) add("cheaper_overnight")
                if (ticketsRub > 0 || tickets.isNotEmpty()) add("fewer_sights")
                if (!u.moodJustDrive) add("just_drive")
            }
        }
        return CostNumbers(lines, subtotal, total, perPerson, remaining, over, hints, shownKm.setScale(0, RoundingMode.HALF_UP).toInt())
    }
}
