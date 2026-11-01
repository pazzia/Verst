package app.verst.nav

import app.verst.core.model.EngineArgs
import app.verst.core.model.EngineResult
import app.verst.core.model.TripFigures
import app.verst.core.model.cost.CostApply
import app.verst.core.model.cost.LocalCost
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.StopDto
import app.verst.analytics.AnalyticsEvent
import app.verst.analytics.Buckets
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** HYG-02: Exit 5.7 / D-10 — `VerstFlow` extensions (the state stays in the class). */

// ---- exit 5.7

/** Road-ahead night row «Выбрать отель →» → 5.7 for that night. */
fun VerstFlow.openExit(stopId: String) {
    exitStopId = stopId
    roadFocusId = stopId
    partnerOpen = false
    bookedDialog = false
    push(Route.Exit)
}

/** A hotel option: local recompute + selection now, `patch_cost {hotelChoice}` overwrites. */
fun VerstFlow.selectHotel(stopId: String, placeId: String) {
    val r = result ?: return
    val stop = r.trip.daysList.flatMap { it.stops }.firstOrNull { it.id == stopId } ?: return
    if (stop.selectedHotelId == placeId || costBusy) return
    costBusy = true
    val session = tripSession
    localCost(r) { trip -> CostApply.apply(r.trip, LocalCost.hotel(trip, stopId, placeId), r.trip.cost.reserveOn, stopId to placeId) }
    scope.launch {
        val p = gateway.patchCost(r.tripJson, EngineArgs.hotelPatch(stopId, placeId))
        costBusy = false
        if (session != tripSession) return@launch // P2-1
        when (p) {
            is EngineResult.Ok -> updateTrip(p.value)
            is EngineResult.Err -> {
                result = r
                showToast(Toast.EngineFailed)
            }
        }
    }
}

/**
 * «Забронировать ночь» / «Открыть бронирование» (ENG-03, CEO 01.11): the real hotel search for the night's town,
 * date and crew opens in the browser (or the partner's app): the partner link from the server when the tester
 * agreed to the server, else the plain search built on the phone. «Забронировали?» waits for the return.
 * Offline → toast. Without a launcher (unit tests) or in the e2e dry run the link is only recorded ([lastBookingUrl]).
 */
fun VerstFlow.book() {
    if (!connectivity.online) {
        showToast(Toast.NeedInternet)
        return
    }
    val sid = exitStopId ?: return
    val r = result ?: return
    val stop = r.trip.daysList.flatMap { it.stops }.firstOrNull { it.id == sid } ?: return
    // ENG-05 `hotel_link_clicked`
    track {
        val hotel = stop.hotelOptions.firstOrNull { it.placeId == selectedHotel(sid) }
        AnalyticsEvent.HotelLinkClicked(tripId, sid, Buckets.price(hotel?.priceCrewRub))
    }
    val q = app.verst.core.model.HotelLinks.forStop(stop, r.trip.input.crew, tripId, selectedHotel(sid))
    if (q == null) {
        showToast(Toast.BookingFailed)
        return
    }
    val source = hotelLinks
    if (source == null) {
        openBooking(sid, q.plainUrl())
    } else {
        scope.launch { openBooking(sid, source(q) ?: q.plainUrl()) }
    }
}

private fun VerstFlow.openBooking(stopId: String, url: String) {
    lastBookingUrl = url
    val launcher = handoffLauncher
    if (launcher != null && !debugHandoffDryRun) {
        val target = launcher.open(app.verst.core.model.dto.HandoffLinksDto(web = url), walk = true)
        if (target == HandoffTarget.None) {
            showToast(Toast.BookingFailed)
            return
        }
    }
    if (exitStopId == stopId && !isBooked(stopId)) bookedDialog = true
}

fun VerstFlow.needInternet() = showToast(Toast.NeedInternet)

internal fun VerstFlow.selectedHotel(stopId: String): String? =
    result?.trip?.daysList?.flatMap { it.stops }?.firstOrNull { it.id == stopId }?.let { it.selectedHotelId ?: it.hotelOptions.firstOrNull()?.placeId }

/** The selected hotel of [stopId] is the booked one (Road «Забронировано», 5.7 booked CTA). */
fun VerstFlow.isBooked(stopId: String): Boolean = booked[stopId] != null && booked[stopId] == selectedHotel(stopId)

/** Sheet dismissed (button, ×, back) → «Забронировали?» unless the selected hotel is already booked. */
fun VerstFlow.closePartner() {
    partnerOpen = false
    val sid = exitStopId ?: return
    if (!isBooked(sid)) bookedDialog = true
}

/** «Да, забронировали» marks the selected hotel (moving the mark, one per night) + toast with «Вернуть». */
fun VerstFlow.answerBooked(yes: Boolean) {
    bookedDialog = false
    val sid = exitStopId ?: return
    val pid = selectedHotel(sid) ?: return
    if (yes) {
        undoBooked = booked[sid] ?: ""
        booked[sid] = pid
        persistBooking()
        showToast(Toast.Booked(sid))
    }
}

/** «Вернуть» on the booked toast: the previous mark (or none). */
fun VerstFlow.undoBooking() {
    val sid = exitStopId ?: return
    val prev = undoBooked ?: return
    undoBooked = null
    if (prev.isEmpty()) booked.remove(sid) else booked[sid] = prev
    persistBooking()
    dismissToast()
}

internal fun VerstFlow.persistBooking() {
    savedCurrent = false
    if (savedId != null) save(silent = true) // a saved trip keeps its booking at once
}

/** The origin's name forms from the engine (OI-39). */
internal fun VerstFlow.loadOriginForms() {
    val o = origin
    scope.launch {
        val r = gateway.reverse(o)
        if (r is EngineResult.Ok && o == origin) r.value?.nameGenRu?.let { originGen = it }
    }
}

internal fun VerstFlow.updateTrip(r: PlanResultDto) {
    result = r
    savedCurrent = false
    resultRequest?.let { record(it, TripFigures(r.trip.km, r.trip.days)) }
}

/** «заменить» on a stop → D-6 sheet. */
fun VerstFlow.openReplace(stop: StopDto) {
    roadFocusId = stop.id
    replace = ReplaceUi(stop)
}

fun VerstFlow.pickAlternative(altId: String?) {
    replace = replace?.copy(picked = altId)
}

fun VerstFlow.closeReplace() {
    if (replace?.busy != true) {
        replace = null
        roadFocusSeq += 1
    }
}

/** «ЗАМЕНИТЬ»: the engine's `replace_stop`; the trip and the total update, toast with «Вернуть». */
fun VerstFlow.confirmReplace() {
    val ui = replace ?: return
    val alt = ui.picked ?: return
    val r = result ?: return
    replace = ui.copy(busy = true)
    // Local total first (the row itself changes with the engine's answer a moment later).
    localCost(r) { trip -> CostApply.apply(r.trip, LocalCost.replace(trip, ui.stop.id, alt) ?: error("no units"), r.trip.cost.reserveOn) }
    val session = tripSession
    scope.launch {
        val n = gateway.replaceStop(r.tripJson, ui.stop.id, alt)
        if (session != tripSession) return@launch // P2-1
        when (n) {
            is EngineResult.Ok -> {
                undoTrip = r
                updateTrip(n.value)
                replace = null
                roadFocusSeq += 1
                showToast(Toast.Replaced(n.value.trip.cost.totalRub))
                track { AnalyticsEvent.StopReplaced(tripId, ui.stop.kind, ui.stop.alternatives.indexOfFirst { it.id == alt } + 1) }
            }
            is EngineResult.Err -> {
                result = r
                replace = null
                roadFocusSeq += 1
                showToast(Toast.EngineFailed)
            }
        }
    }
}

/** «Вернуть» on the replace toast: the trip before the replace. */
fun VerstFlow.undo() {
    val prev = undoTrip ?: return
    undoTrip = null
    updateTrip(prev)
    dismissToast()
}

val VerstFlow.canUndo: Boolean get() = undoTrip != null && toast is Toast.Replaced

internal fun VerstFlow.showToast(t: Toast) {
    toast = t
    toastJob?.cancel()
    toastJob = scope.launch {
        delay(
            when {
                t is Toast.Replaced || t is Toast.TripDeleted || t is Toast.Booked -> 6_000
                t is Toast.HandoffOpen -> 1_000 // 5.13 §5: a 1 s toast, then the app
                else -> 3_000
            },
        )
        toast = null
        if (t is Toast.Replaced) undoTrip = null
        if (t is Toast.TripDeleted) lastDeleted = null
    }
}

fun VerstFlow.dismissToast() {
    toastJob?.cancel()
    toast = null
}
