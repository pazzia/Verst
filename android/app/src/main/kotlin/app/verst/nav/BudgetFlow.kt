package app.verst.nav

import app.verst.core.model.TripMath
import app.verst.core.model.dto.EstimateDto
import java.util.UUID

/** HYG-02: Budget fit (5.8) — `VerstFlow` extensions (the state stays in the class). */

// ---- budget (5.8)

/** Drive «Смотреть варианты» / auto-advance: Drive is replaced by the no-fit screen. */
fun VerstFlow.openNoFit() {
    if (noFit == null) return
    if (top == Route.Drive) stack[stack.lastIndex] = Route.NoFit else push(Route.NoFit)
}

/** An option → Instruments with it applied; the user presses ПОЕХАЛИ again (5.8 §2). */
fun VerstFlow.applyBudgetOption(o: app.verst.core.model.dto.BudgetOptionDto) {
    when (o.kind) {
        "raise_budget" -> o.budgetRub?.let { budgetCustom = it }
        "shorten", "cheaper_route" -> {
            val id = o.readyRouteId
            if (id != null) {
                val known = (windshield as? WindshieldData.Routes)?.routes?.firstOrNull { it.id == id }
                val base = known ?: readyRoute
                if (base != null) {
                    readyRoute = if (known != null) known else base.copy(id = id, title = o.titleRu ?: base.title, subtitle = "")
                    destination = null
                }
            } else {
                // a free trip: the same route in fewer days → a longer daily pace
                val days = o.days
                val km = figures?.figures?.km ?: noFit?.minimum?.trip?.km
                if (days != null && days > 0 && km != null) {
                    dailyKmTouched = true
                    dailyKm = (((km + days - 1) / days + 49) / 50 * 50).coerceIn(TripMath.KM_MIN, TripMath.KM_MAX)
                }
            }
        }
    }
    backToInstruments()
}

internal fun VerstFlow.backToInstruments() {
    val i = stack.lastIndexOf(Route.Instruments)
    if (i >= 0) {
        while (stack.size > i + 1) stack.removeAt(stack.lastIndex)
    } else {
        while (stack.lastOrNull() == Route.NoFit) stack.removeAt(stack.lastIndex)
        push(Route.Instruments)
    }
}

/** «Показать самый экономный вариант»: Road ahead with the minimum, over budget everywhere. */
fun VerstFlow.showMinimum() {
    val nf = noFit ?: return
    val m = nf.minimum ?: return
    showTrip(m, lastPlanRequest, readyRoute?.bearing8 ?: "N", savedId = null, fromSaved = false, tripId = planTripId)
    showingMinimum = true
    if (top == Route.NoFit) stack[stack.lastIndex] = Route.Road else push(Route.Road)
}

/** Waybill over budget «Подогнать под бюджет»: the same trip planned again (the fitter runs) → Drive. */
fun VerstFlow.refit() {
    val req = resultRequest ?: lastPlanRequest ?: return
    val i = stack.lastIndexOf(Route.Road)
    if (i >= 0) while (stack.size > i) stack.removeAt(stack.lastIndex)
    push(Route.Drive)
    // ENG-05: the fitted plan is the same trip while it is unsaved; a saved trip's refit is saved as a new trip
    // (a new entry in «Мои поездки»), so it gets a new trip_id.
    startPlan(req, planId = tripId?.takeIf { savedId == null } ?: UUID.randomUUID().toString())
}

/** Instruments caption: the engine's budget verdict for the current draft (`estimate.outcome`). */
val VerstFlow.budgetEstimate: EstimateDto?
    get() = draft()?.let { estimates[it] }?.takeIf { it.outcome != null && request().budgetRub != null }
