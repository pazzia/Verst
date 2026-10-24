package app.verst.core.model

/**
 * The km and days of a trip (DEV-SLICE-2 P0 «one trip, one distance»). Every screen before Road ahead
 * (Navigator caption, Instruments, Drive header) and Road ahead itself show the engine's number:
 *  - after a plan: `trip.km` / `trip.days` of that plan;
 *  - before it: `mobile.estimate` of the same request, which *is* the engine's plan of it without events, so
 *    it equals the later plan exactly.
 * Nothing in the app computes trip km itself any more (the slice showed the straight line, its × 1.25 and the
 * engine's km for the same trip).
 */
data class TripFigures(val km: Int, val days: Int)

/** Which request a figure belongs to: same origin, destination and ready route = the same road. */
fun PlanRequest.sameRoad(other: PlanRequest): Boolean =
    origin == other.origin && destination == other.destination && readyRouteId == other.readyRouteId

object TripFiguresPick {
    /**
     * The figure for [request]: an exact match (estimate or plan of this very request) is exact; otherwise the
     * latest figure for the same road (crew or km/day just changed, the new estimate is on its way) is shown as
     * stale; a different road gives null (nothing is shown rather than a wrong number).
     */
    fun pick(request: PlanRequest?, known: List<Pair<PlanRequest, TripFigures>>): Picked? {
        if (request == null) return null
        known.lastOrNull { it.first == request }?.let { return Picked(it.second, stale = false) }
        return known.lastOrNull { it.first.sameRoad(request) }?.let { Picked(it.second, stale = true) }
    }

    data class Picked(val figures: TripFigures, val stale: Boolean)
}
