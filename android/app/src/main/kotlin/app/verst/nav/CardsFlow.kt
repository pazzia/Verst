package app.verst.nav

import app.verst.core.model.EngineResult
import app.verst.core.model.dto.StopDto
import app.verst.analytics.AnalyticsEvent
import java.util.UUID
import kotlinx.coroutines.launch

/** HYG-02: Place cards (5.9) and the D-7 report — `VerstFlow` extensions (the state stays in the class). */

// ---- cards (5.9)

/** Tappable rows only (M§15.5): a sight, or a night with a hotel. */
fun VerstFlow.tappable(s: StopDto): Boolean = s.kind == "sight" || (s.kind == "overnight" && s.hotelOptions.isNotEmpty())

/** A Road-ahead row → its card; the row is the focus for the way back. */
fun VerstFlow.openCard(stop: StopDto) {
    if (!tappable(stop)) return
    roadFocusId = stop.id
    val hotel = stop.kind == "overnight"
    val option = if (hotel) stop.hotelOptions.firstOrNull { it.placeId == stop.selectedHotelId } ?: stop.hotelOptions.firstOrNull() else null
    val placeId = if (hotel) option?.placeId ?: stop.placeId else stop.placeId
    val base = app.verst.feature.card.CardUi(
        name = stop.name, sign = stop.sign, tags = stop.tags, kind = if (hotel) "hotel" else "sight",
        loading = placeId != null, offline = !connectivity.online, hotel = option, booked = isBooked(stop.id),
        canReplace = stop.replaceable && stop.alternatives.isNotEmpty(),
    )
    card = CardState(CardSource.ROAD, stop.id, placeId, base)
    loadCard(placeId, stop.id)
}

/** A walk stop → its card (sights / museums: sight card; bars: bar card with the ODbL line). */
fun VerstFlow.openWalkCard(ws: app.verst.core.model.dto.WalkStopDto) {
    if (!ws.tappable) return
    val base = app.verst.feature.card.CardUi(
        name = ws.nameRu, sign = if (ws.isBar) "service" else "tourist", tags = listOf(ws.kind), kind = if (ws.isBar) "bar" else "sight",
        loading = ws.poiId != null, offline = !connectivity.online, walkStop = true,
    )
    card = CardState(CardSource.WALK, ws.id, ws.poiId, base)
    walkFocusId = ws.id
    loadCard(ws.poiId, ws.id)
}

internal fun VerstFlow.loadCard(placeId: String?, rowId: String) {
    if (placeId == null) return
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
