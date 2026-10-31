package app.verst.core.model.cost

import app.verst.core.model.dto.TripDto

/**
 * Local-first display (M§6.3): the trip with the [CostNumbers] of [LocalCost] applied — line sums, totals,
 * remainder, the reserve flag and, for a hotel choice, the overnight stop's selection and cost. The engine's
 * answer replaces the whole trip moments later (formulas and breakdowns come only from the engine).
 */
object CostApply {
    fun apply(trip: TripDto, n: CostNumbers, reserveOn: Boolean, hotel: Pair<String, String>? = null): TripDto {
        val c = trip.cost
        val cost = c.copy(
            lines = c.lines.map { l -> n.lines[l.key]?.let { l.copy(rub = it, enabled = if (l.key == "reserve") reserveOn else l.enabled) } ?: l },
            reserveOn = reserveOn,
            subtotalRub = n.subtotalRub,
            totalRub = n.totalRub,
            perPersonRub = n.perPersonRub,
            remainingRub = n.remainingRub,
            overBudget = n.overBudget,
        )
        val days = if (hotel == null) trip.daysList else trip.daysList.map { d ->
            d.copy(stops = d.stops.map { s ->
                if (s.id != hotel.first) s else {
                    val opt = s.hotelOptions.firstOrNull { it.placeId == hotel.second }
                    s.copy(selectedHotelId = hotel.second, costRub = opt?.priceCrewRub ?: s.costRub, tags = opt?.tags ?: s.tags)
                }
            })
        }
        return trip.copy(cost = cost, daysList = days)
    }
}
