package app.verst.nav

import app.verst.core.model.EngineResult
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.NaviLinks
import app.verst.core.model.LatLon
import app.verst.core.model.HandoffArgs
import app.verst.core.model.dto.HandoffDto
import app.verst.core.model.dto.HandoffLinksDto
import app.verst.analytics.AnalyticsEvent
import kotlinx.coroutines.launch

/** HYG-02: Navigator hand-off (5.13, ADR-0014) and its sheet (5.13 §5) — `VerstFlow` extensions (the state stays in the class). */

// ---- hand-off (5.13)

/** The day header link → the day menu «В навигатор: день N» (the engine's links resolved behind it). */
fun VerstFlow.openDayMenu(day: Int) {
    val r = result ?: return
    dayMenu = day
    dayHandoff = null
    val session = tripSession
    scope.launch {
        val h = engineHandoff(r.tripJson, HandoffArgs.day(day, handoffSigner?.client)) ?: r.trip.daysList.firstOrNull { it.day == day }?.let { NaviLinks.day(it) }?.toDto(day)
        if (session == tripSession && dayMenu == day) dayHandoff = h
    }
}

fun VerstFlow.closeDayMenu() {
    dayMenu = null
    dayHandoff = null
}

/** «В навигатор: день N». */
fun VerstFlow.dayMenuGo() {
    val h = dayHandoff ?: return
    val day = dayMenu
    dayMenu = null
    launchHandoff(h.parts.firstOrNull()?.links ?: return, walk = false, day = h.day ?: day)
}

/** «Вести в навигаторе» / a day's «вести»: the remembered app directly, else the sheet on [day]. */
fun VerstFlow.handoff(day: Int) {
    val app = handoffRememberedApp
    if (handoffRemember && app != null) {
        val r = result ?: return
        val session = tripSession
        scope.launch {
            val h = dayHandoffOf(r, day) ?: return@launch
            if (session == tripSession) launchApp(app, h, next = false)
        }
    } else {
        openHandoffSheet(day)
    }
}

/** The sheet on [day] (a long-press always opens it, even with «Запомнить выбор»). */
fun VerstFlow.openHandoffSheet(day: Int) {
    val r = result ?: return
    handoffSheet = HandoffSheet(day, null, day)
    loadSheet(r, day)
}

internal fun VerstFlow.loadSheet(r: PlanResultDto, day: Int) {
    val session = tripSession
    scope.launch {
        val h = dayHandoffOf(r, day)
        val cur = handoffSheet
        if (session == tripSession && cur != null && cur.handoffDay == day) handoffSheet = cur.copy(handoff = h)
    }
}

internal suspend fun VerstFlow.dayHandoffOf(r: PlanResultDto, day: Int): HandoffDto? =
    engineHandoff(r.tripJson, HandoffArgs.day(day, handoffSigner?.client)) ?: r.trip.daysList.firstOrNull { it.day == day }?.let { NaviLinks.day(it) }?.toDto(day)

/** A tab: «День N» or «До след.» ([day] = null, the next point of the sheet's day). */
fun VerstFlow.handoffScope(day: Int?) {
    val cur = handoffSheet ?: return
    val r = result ?: return
    if (day == null) {
        handoffSheet = cur.copy(day = null)
    } else if (day != cur.handoffDay) {
        handoffSheet = HandoffSheet(day, null, day)
        loadSheet(r, day)
    } else {
        handoffSheet = cur.copy(day = day)
    }
}

fun VerstFlow.closeHandoffSheet() {
    handoffSheet = null
    roadFocusSeq += 1
}

fun VerstFlow.toggleHandoffRemember() {
    handoffRemember = !handoffRemember
    if (!handoffRemember) handoffRememberedApp = null
}

/** A card of the sheet: open that app (and remember it when «Запомнить выбор» is on). */
fun VerstFlow.handoffPick(app: HandoffApp) {
    val cur = handoffSheet ?: return
    val h = cur.handoff ?: return
    if (handoffRemember) handoffRememberedApp = app
    handoffSheet = null
    launchApp(app, h, next = cur.day == null)
    roadFocusSeq += 1
}

fun VerstFlow.handoffInstall(app: HandoffApp) {
    handoffLauncher?.openStore(app)
}

/** The Навигатор / Карты link of [h]: unsigned the Навигатор gets the next point only (ADR-0015 §1). */
internal fun VerstFlow.launchApp(app: HandoffApp, h: HandoffDto, next: Boolean) {
    val part = h.parts.firstOrNull() ?: return
    val l = part.links
    val nextPt = part.next ?: part.points.firstOrNull { it.role != "origin" }
    // a pre-v3 / local hand-off has no `next`: the day's first stop after its start
    val nextMaps = nextPt?.let { runCatching { LatLon(it.lat, it.lon) }.getOrNull() }
        ?: h.day?.let { d -> result?.trip?.daysList?.firstOrNull { it.day == d } }?.stops?.drop(1)
            ?.firstOrNull { it.lat != null && it.lon != null }?.let { runCatching { LatLon(it.lat!!, it.lon!!) }.getOrNull() }
    val uri: String?
    val web: String?
    when (app) {
        HandoffApp.NAVI -> {
            uri = if (next || !handoffSigned) l.navigatorNext ?: nextMaps?.let { NaviLinks.naviRoute(null, it, emptyList()) } else l.navigator
            web = null
        }
        HandoffApp.MAPS -> {
            uri = if (next && nextMaps != null) NaviLinks.mapsAppRoute(listOf(nextMaps)) else l.maps
            web = if (next && nextMaps != null) NaviLinks.webRoute(listOf(nextMaps)) else l.web
        }
    }
    val mapsApp = handoffLauncher?.mapsInstalled() == true
    if (app == HandoffApp.MAPS && !mapsApp && !connectivity.online) {
        showToast(Toast.HandoffOffline)
        return
    }
    val target = if (debugHandoffDryRun) {
        when {
            app == HandoffApp.NAVI -> HandoffTarget.NavigatorDryRun
            mapsApp -> HandoffTarget.MapsDryRun
            else -> HandoffTarget.BrowserDryRun
        }
    } else {
        handoffLauncher?.openIn(app, uri, web) ?: HandoffTarget.None
    }
    lastHandoff = HandoffLinksDto(navigator = if (app == HandoffApp.NAVI) uri else null, maps = if (app == HandoffApp.MAPS) uri else null, web = web) to target
    naviApp(target)?.let { opened -> track { AnalyticsEvent.NavigatorOpened(tripId, opened, h.day) } }
    when (target) {
        HandoffTarget.Navigator, HandoffTarget.NavigatorDryRun -> showToast(Toast.HandoffOpen(navi = true))
        HandoffTarget.Maps, HandoffTarget.MapsDryRun -> showToast(Toast.HandoffOpen(navi = false))
        HandoffTarget.Browser, HandoffTarget.BrowserDryRun -> showToast(Toast.HandoffWeb(false))
        HandoffTarget.None -> showToast(Toast.HandoffFailed)
    }
}

/** D-5 stop menu on a long-press of a row. */
fun VerstFlow.openStopMenu(stop: StopDto) {
    val r = result ?: return
    roadFocusId = stop.id
    stopMenu = stop
    stopHandoff = null
    val session = tripSession
    scope.launch {
        val h = engineHandoff(r.tripJson, HandoffArgs.fromStop(stop.id, handoffSigner?.client)) ?: NaviLinks.fromStop(r.trip, stop.id)?.toDto(null)
        if (session == tripSession && stopMenu?.id == stop.id) stopHandoff = h
    }
}

fun VerstFlow.closeStopMenu() {
    stopMenu = null
    stopHandoff = null
    roadFocusSeq += 1
}

/** «Открыть в навигаторе отсюда»: from this stop to the end of its day. */
fun VerstFlow.navigatorFromStop() {
    val h = stopHandoff ?: return
    val day = stopMenu?.day
    stopMenu = null
    stopHandoff = null
    launchHandoff(h.parts.firstOrNull()?.links ?: return, walk = false, day = day)
    roadFocusSeq += 1 // back from the app: the row (5.9 §5)
}

/** «Заменить» in the stop menu → the D-6 sheet. */
fun VerstFlow.stopMenuReplace() {
    val s = stopMenu ?: return
    stopMenu = null
    stopHandoff = null
    openReplace(s)
}

/** 5.13 §2: what the car label names (navigator → maps → web), resolved from the installed apps. */
val VerstFlow.carTarget: HandoffTarget
    get() = when {
        handoffLauncher?.navigatorInstalled() == true -> HandoffTarget.Navigator
        handoffLauncher?.mapsInstalled() == true -> HandoffTarget.Maps
        else -> HandoffTarget.Browser
    }

/** Walk: maps → web. */
val VerstFlow.walkTarget: HandoffTarget
    get() = if (handoffLauncher?.mapsInstalled() == true) HandoffTarget.Maps else HandoffTarget.Browser

/** Kept for the R1 callers: the navigator app is installed. */
val VerstFlow.navigatorInstalled: Boolean get() = handoffLauncher?.navigatorInstalled() ?: false

internal suspend fun VerstFlow.engineHandoff(routeJson: String, options: String): HandoffDto? =
    (gateway.handoff(routeJson, options) as? EngineResult.Ok)?.value?.takeIf { h -> h.parts.isNotEmpty() }
        ?.let { h -> handoffSigner?.sign(h) ?: h }

/**
 * One tap opens the target (no chooser); a web fallback says so; offline without an app → «нужен интернет».
 * [day]: the trip day handed off (ENG-05 `navigator_opened`; walks are not reported).
 */
internal fun VerstFlow.launchHandoff(links: HandoffLinksDto, walk: Boolean, day: Int? = null) {
    val resolved = if (walk) walkTarget else carTarget
    if (resolved == HandoffTarget.Browser && !connectivity.online) {
        showToast(Toast.HandoffOffline)
        return
    }
    val target = if (debugHandoffDryRun) {
        when (resolved) {
            HandoffTarget.Navigator -> HandoffTarget.NavigatorDryRun
            HandoffTarget.Maps -> HandoffTarget.MapsDryRun
            else -> HandoffTarget.BrowserDryRun
        }
    } else {
        handoffLauncher?.open(links, walk) ?: HandoffTarget.None
    }
    lastHandoff = links to target
    if (!walk) naviApp(target)?.let { app -> track { AnalyticsEvent.NavigatorOpened(tripId, app, day) } }
    when (target) {
        HandoffTarget.Browser -> showToast(Toast.HandoffWeb(walk))
        HandoffTarget.None -> showToast(Toast.HandoffFailed)
        else -> Unit
    }
}
