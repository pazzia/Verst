package app.verst.nav

import app.verst.core.model.EngineResult
import app.verst.core.model.dto.StopDto
import app.verst.analytics.AnalyticsEvent
import java.util.UUID
import kotlinx.coroutines.launch

/** HYG-02: Place cards (5.9) and the D-7 report — `VerstFlow` extensions (the state stays in the class). */

// ---- cards (5.9)

/** Tappable rows only (M§15.5): a sight, a night with a hotel; CEO 29.10: a border crossing (its sheet). */
fun VerstFlow.tappable(s: StopDto): Boolean =
    s.kind == "sight" || (s.kind == "overnight" && s.hotelOptions.isNotEmpty()) || isBorder(s)

/** CEO 29.10 (trips abroad): a crossing with the engine's facts to show. */
internal fun isBorder(s: StopDto): Boolean = s.kind == "border" && s.border != null

/** A Road-ahead row → its card (a border row → its sheet); the row is the focus for the way back. */
fun VerstFlow.openCard(stop: StopDto) {
    if (!tappable(stop)) return
    roadFocusId = stop.id
    if (isBorder(stop)) {
        roadBorder = stop
        return
    }
    val hotel = stop.kind == "overnight"
    val option = if (hotel) stop.hotelOptions.firstOrNull { it.placeId == stop.selectedHotelId } ?: stop.hotelOptions.firstOrNull() else null
    val placeId = if (hotel) option?.placeId ?: stop.placeId else stop.placeId
    val base = app.verst.feature.card.CardUi(
        name = stop.name, sign = stop.sign, tags = stop.tags, kind = if (hotel) "hotel" else "sight",
        loading = placeId != null, offline = !connectivity.online, hotel = option, booked = isBooked(stop.id),
        canReplace = stop.replaceable && stop.alternatives.isNotEmpty(),
        town = if (hotel) stop.name else null, // a night's row is named by its town
    )
    card = CardState(CardSource.ROAD, stop.id, placeId, base)
    val lat = stop.lat
    val lon = stop.lon
    val point = if (lat != null && lon != null) lat to lon else null
    if (hotel && placeId != null) {
        // the night's point is the town's: the hotel's own coordinates come with its `poi_details`
        loadCard(placeId, stop.id, addressPoint = point)
    } else {
        loadCard(placeId, stop.id)
        loadCardAddress(placeId ?: stop.id, point)
    }
}

/**
 * A walk stop → its card (sights / museums: sight card; bars: bar card with the ODbL line; CEO 29.10: OSM
 * restaurants and cafés: a food card, OSM too).
 */
fun VerstFlow.openWalkCard(ws: app.verst.core.model.dto.WalkStopDto) {
    if (!ws.tappable) return
    val kind = when {
        ws.isBar -> "bar"
        ws.isFood -> "food"
        else -> "sight"
    }
    val base = app.verst.feature.card.CardUi(
        name = ws.nameRu, sign = if (ws.isBar || ws.isFood) "service" else "tourist", tags = listOf(ws.kind), kind = kind,
        loading = ws.poiId != null, offline = !connectivity.online, walkStop = true, town = walk?.townName,
    )
    card = CardState(CardSource.WALK, ws.id, ws.poiId, base)
    walkFocusId = ws.id
    loadCard(ws.poiId, ws.id)
    loadCardAddress(ws.poiId ?: ws.id, ws.lat to ws.lon)
}

/**
 * [addressPoint]: a hotel card asks its address after `poi_details` (the hotel's coordinates), with this point (the
 * night's) when the details give none.
 */
internal fun VerstFlow.loadCard(placeId: String?, rowId: String, addressPoint: Pair<Double, Double>? = null) {
    if (placeId == null) return
    if (addressPoint != null && connectivity.online && placeId !in cardAddresses) {
        card?.let { c -> card = c.copy(ui = c.ui.copy(addressLoading = true)) } // «Адрес уточняется…» meanwhile
    }
    scope.launch {
        val r = gateway.poiDetails(placeId)
        val c = card ?: return@launch
        if (c.rowId != rowId) return@launch
        var d = (r as? EngineResult.Ok)?.value
        // S3-R3 debug: real Commons files instead of the catalogue's (round robin) — real photos before the data run
        if (d != null && debugRealPhotos) {
            val files = app.verst.core.model.CommonsPhotos.DEBUG_FILES
            d = d.copy(image = app.verst.core.model.CommonsPhotos.debugImage(d.image, files[debugPhotoIndex++ % files.size]))
        }
        card = c.copy(ui = c.ui.copy(loading = false, details = d, offline = !connectivity.online))
        if (addressPoint != null) {
            val lat = d?.lat
            val lon = d?.lon
            loadCardAddress(placeId, if (lat != null && lon != null) lat to lon else addressPoint)
        }
    }
}

/**
 * CEO 29.10: the card's street address. The catalogue has none, so online the place's coordinates are reverse
 * geocoded — Nominatim (`streetLabel`: «улица, дом»), else the phone's geocoder, as `locate()` does — and kept per
 * place ([key]: the place id, else the row id) for the session. An answer that comes back after another card
 * opened is dropped. Offline, or with no coordinates, nothing is asked and nothing is shown.
 */
internal fun VerstFlow.loadCardAddress(key: String, point: Pair<Double, Double>?) {
    val c = card ?: return
    if ((c.poiId ?: c.rowId) != key) return
    val known = cardAddresses[key]
    if (known != null) {
        card = c.copy(ui = c.ui.copy(address = known, addressLoading = false))
        return
    }
    if (point == null || !connectivity.online) {
        card = c.copy(ui = c.ui.copy(addressLoading = false))
        return
    }
    card = c.copy(ui = c.ui.copy(addressLoading = true))
    val (lat, lon) = point
    scope.launch {
        val street = (address.reverse(lat, lon) as? app.verst.data.net.AddressResult.Ok)?.value?.takeIf { it.isNotBlank() }
            ?: (addressFallback?.reverse(lat, lon) as? app.verst.data.net.AddressResult.Ok)?.value?.takeIf { it.isNotBlank() }
        if (street != null) cardAddresses[key] = street
        val cur = card ?: return@launch
        if ((cur.poiId ?: cur.rowId) != key) return@launch // another card is open now: not its address
        card = cur.copy(ui = cur.ui.copy(address = street, addressLoading = false))
    }
}

fun VerstFlow.closeCard() {
    val c = card ?: return
    card = null
    if (c.source == CardSource.ROAD) roadFocusSeq += 1 else walkFocusSeq += 1
}

// ---- D-7 report

/** D-5 «Сообщить об ошибке» and the row's TalkBack action. */
fun VerstFlow.openReport(stop: StopDto) {
    stopMenu = null
    stopHandoff = null
    roadFocusId = stop.id
    startReport(ReportTarget(stop.name, stop.placeId, stop.id, "road", fromWalk = false))
}

/** 5.9 C10 «Сообщить об ошибке» on a card (road or walk). */
fun VerstFlow.reportFromCard() {
    val c = card ?: return
    card = null
    val walk = c.source == CardSource.WALK
    startReport(ReportTarget(c.ui.details?.nameRu ?: c.ui.name, c.poiId, c.rowId, if (walk) "walk" else "card", fromWalk = walk))
}

internal fun VerstFlow.startReport(t: ReportTarget) {
    report = t
    reportReason = null
    reportComment = ""
}

fun VerstFlow.pickReportReason(r: String) {
    if (r in app.verst.core.model.Reports.REASONS) reportReason = r
}

fun VerstFlow.setReportCommentText(t: String) {
    reportComment = t.take(app.verst.core.model.Reports.COMMENT_MAX)
}

fun VerstFlow.closeReport() {
    val t = report ?: return
    report = null
    if (t.fromWalk) walkFocusSeq += 1 else roadFocusSeq += 1
}

/** «Отправить»: queued on the device (no endpoint yet); event `feedback_sent`. */
fun VerstFlow.sendReport() {
    val t = report ?: return
    val reason = reportReason ?: return
    val online = connectivity.online
    val r = app.verst.core.model.ReportDto(
        id = java.util.UUID.randomUUID().toString(), at = now(), reason = reason, comment = reportComment.trim(),
        name = t.name, placeId = t.placeId, stopId = t.stopId, source = t.source, world = gateway.world, online = online,
    )
    pendingReports += r
    writes.trySend(Unit)
    track { AnalyticsEvent.FeedbackSent(if (t.fromWalk) null else tripId, reason) } // the comment never leaves the queue
    reportsSent += 1
    closeReport()
    showToast(if (online) Toast.ReportThanks else Toast.ReportQueued)
}

/** Hotel card «Выбрать отель» → 5.7 for that night. */
fun VerstFlow.cardPickHotel() {
    val c = card ?: return
    card = null
    openExit(c.rowId)
}

/** Sight card «Заменить» → D-6. */
fun VerstFlow.cardReplace() {
    val c = card ?: return
    val stop = result?.trip?.daysList?.flatMap { it.stops }?.firstOrNull { it.id == c.rowId } ?: return
    card = null
    openReplace(stop)
}

/** Walk card «Убрать эту точку»: the walk is solved again without it. */
fun VerstFlow.cardRemoveWalkStop() {
    val c = card ?: return
    card = null
    c.poiId?.let { if (it !in walkExclude) walkExclude += it }
    lastOtherAdded = listOfNotNull(c.poiId)
    buildWalk(WalkBuild.REMOVE)
}

fun VerstFlow.openAboutData() {
    aboutData = true
}

fun VerstFlow.openParking(stop: StopDto) {
    roadParking = stop
}

fun VerstFlow.closeParking() {
    roadParking = null
}

/** CEO 29.10: the border sheet closes; focus goes back to its row. */
fun VerstFlow.closeBorder() {
    roadBorder = null
    roadFocusSeq += 1
}

/**
 * 5.5 §10.1: the day «Вести в навигаторе» starts with — the trip's day of today when the trip is under way
 * (start date ≤ today ≤ last day), else day 1.
 */
fun VerstFlow.handoffDay(trip: app.verst.core.model.dto.TripDto, today: java.time.LocalDate = java.time.LocalDate.now()): Int {
    val first = trip.daysList.firstOrNull()?.day ?: 1
    val start = (trip.daysList.firstOrNull()?.startAt ?: trip.input.startAt)?.takeIf { it.length >= 10 }
        ?.let { runCatching { java.time.LocalDate.parse(it.substring(0, 10)) }.getOrNull() } ?: return first
    val n = java.time.temporal.ChronoUnit.DAYS.between(start, today).toInt() + first
    return if (trip.daysList.any { it.day == n }) n else first
}

fun VerstFlow.closeAboutData() {
    aboutData = false
}

fun VerstFlow.walkFocusShown() {
    walkFocusId = null
}
