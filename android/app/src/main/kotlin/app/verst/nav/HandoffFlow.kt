package app.verst.nav

import app.verst.core.model.EngineResult
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.NaviLinks
import app.verst.core.model.LatLon
import app.verst.core.model.HandoffArgs
import app.verst.core.model.MapsChoice
import app.verst.core.model.MapsCountries
import app.verst.core.model.RouteMode
import app.verst.core.model.dto.HandoffDto
import app.verst.core.model.dto.HandoffLinksDto
import app.verst.analytics.AnalyticsEvent
import kotlinx.coroutines.launch

/** HYG-02: Navigator hand-off (5.13, ADR-0014) and its sheet (5.13 §5) — `VerstFlow` extensions (the state stays in the class). */

// ---- which maps app (CEO 29.10)

/** The phone's country now (ISO alpha-2, upper case), or null when unknown. */
val VerstFlow.phoneCountry: String? get() = MapsCountries.normalize(countrySource?.country())

/**
 * CEO 29.10: the maps app that gets the day's route — the user's «Навигация» choice, else Яндекс Карты where Яндекс
 * routes with confidence (and when the country is unknown), Google Карты elsewhere.
 */
val VerstFlow.preferredMaps: HandoffApp get() = MapsCountries.preferred(mapsChoiceRead(), phoneCountry).handoffApp

/** The user chose the app in «Настройки» (not the automatic choice by the country). */
val VerstFlow.mapsChosen: Boolean get() = mapsChoiceRead() != MapsChoice.AUTO

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

/** «По картам: день N»: the preferred maps app with every point of the day. */
fun VerstFlow.dayMenuGo() {
    val h = dayHandoff ?: return
    val day = dayMenu
    dayMenu = null
    launchApp(preferredMaps, if (h.day == null && day != null) h.copy(day = day) else h, next = false)
}

/**
 * CEO 29.10 «Вести по картам» (the Road screen's main button): the preferred maps app ([preferredMaps]) opens
 * directly with every point of [day] in order — no sheet, never the Навигатор with one point.
 */
fun VerstFlow.handoff(day: Int) {
    val r = result ?: return
    val app = preferredMaps
    val session = tripSession
    scope.launch {
        val h = dayHandoffOf(r, day) ?: return@launch
        if (session == tripSession) launchApp(app, h, next = false)
    }
}

/** The sheet on [day]: a day's «вести» and a long-press of «Вести по картам» (the choice of the app). */
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
}

/**
 * A card of the sheet: open that app. With «Запомнить выбор» a maps app becomes the «Навигация» setting (the
 * Навигатор takes one point, so it is never the default).
 */
fun VerstFlow.handoffPick(app: HandoffApp) {
    val cur = handoffSheet ?: return
    val h = cur.handoff ?: return
    if (handoffRemember) {
        when (app) {
            HandoffApp.MAPS -> mapsChoiceWrite(MapsChoice.YANDEX)
            HandoffApp.GOOGLE -> mapsChoiceWrite(MapsChoice.GOOGLE)
            HandoffApp.NAVI -> Unit
        }
    }
    handoffSheet = null
    launchApp(app, h, next = cur.day == null)
    roadFocusSeq += 1
}

fun VerstFlow.handoffInstall(app: HandoffApp) {
    handoffLauncher?.openStore(app)
}

/**
 * Opens [app] with the hand-off [h] (part [partIndex] of a split walk): Яндекс / Google Карты with every point of
 * the part, or only to the next point ([next], the «До след.» tab); the Навигатор always to the next point only
 * (CEO 29.10: without a Яндекс-signed URL it takes one point from us). A maps app that is not installed → the same
 * route in the browser (offline: «нужен интернет»). [walk]: walking mode (`rtt=pd`, `travelmode=walking`), not
 * reported to analytics.
 */
internal fun VerstFlow.launchApp(app: HandoffApp, h: HandoffDto, next: Boolean, walk: Boolean = false, partIndex: Int = 1) {
    val part = h.parts.firstOrNull { it.index == partIndex } ?: h.parts.firstOrNull() ?: return
    val l = part.links
    val mode = if (walk) RouteMode.WALK else RouteMode.DRIVE
    val nextPt = part.next ?: part.points.firstOrNull { it.role != "origin" }
    // a pre-v3 / local hand-off has no `next`: the day's first stop after its start
    val nextMaps = nextPt?.let { runCatching { LatLon(it.lat, it.lon) }.getOrNull() }
        ?: h.day?.let { d -> result?.trip?.daysList?.firstOrNull { it.day == d } }?.stops?.drop(1)
            ?.firstOrNull { it.lat != null && it.lon != null }?.let { runCatching { LatLon(it.lat!!, it.lon!!) }.getOrNull() }
    val toNext = next && nextMaps != null
    val uri: String?
    val web: String?
    when (app) {
        HandoffApp.NAVI -> {
            uri = l.navigatorNext ?: nextMaps?.let { NaviLinks.naviRoute(null, it, emptyList()) }
            web = null
        }
        HandoffApp.MAPS -> {
            uri = if (toNext) NaviLinks.mapsAppRoute(listOfNotNull(nextMaps), mode) else l.maps
            web = if (toNext) NaviLinks.webRoute(listOfNotNull(nextMaps), mode) else l.web
        }
        HandoffApp.GOOGLE -> {
            // the same https link opens the app (8 waypoints + the destination) or, without it, the browser
            uri = if (toNext) NaviLinks.googleRoute(listOfNotNull(nextMaps), mode, fromHere = true) else NaviLinks.googleOf(part.points, mode)
            web = uri
        }
    }
    val installed = when (app) {
        HandoffApp.NAVI -> navigatorInstalled
        HandoffApp.MAPS -> handoffLauncher?.mapsInstalled() == true
        HandoffApp.GOOGLE -> handoffLauncher?.googleInstalled() == true
    }
    if (app != HandoffApp.NAVI && !installed && !connectivity.online) {
        showToast(Toast.HandoffOffline)
        return
    }
    val target = if (debugHandoffDryRun) {
        when {
            app == HandoffApp.NAVI -> HandoffTarget.NavigatorDryRun
            !installed -> HandoffTarget.BrowserDryRun
            app == HandoffApp.GOOGLE -> HandoffTarget.GoogleDryRun
            else -> HandoffTarget.MapsDryRun
        }
    } else {
        handoffLauncher?.openIn(app, uri, web) ?: HandoffTarget.None
    }
    lastHandoff = HandoffLinksDto(navigator = if (app == HandoffApp.NAVI) uri else null, maps = if (app != HandoffApp.NAVI) uri else null, web = web) to target
    if (!walk) naviApp(target)?.let { opened -> track { AnalyticsEvent.NavigatorOpened(tripId, opened, h.day) } }
    when (target) {
        HandoffTarget.Navigator, HandoffTarget.NavigatorDryRun -> showToast(Toast.HandoffOpen(HandoffApp.NAVI))
        HandoffTarget.Maps, HandoffTarget.MapsDryRun -> showToast(Toast.HandoffOpen(HandoffApp.MAPS))
        HandoffTarget.Google, HandoffTarget.GoogleDryRun -> showToast(Toast.HandoffOpen(HandoffApp.GOOGLE))
        HandoffTarget.Browser, HandoffTarget.BrowserDryRun -> showToast(Toast.HandoffWeb(walk, google = app == HandoffApp.GOOGLE))
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

/** «Вести по картам отсюда»: the preferred maps app from this stop to the end of its day. */
fun VerstFlow.navigatorFromStop() {
    val h = stopHandoff ?: return
    val day = stopMenu?.day
    stopMenu = null
    stopHandoff = null
    launchApp(preferredMaps, if (h.day == null && day != null) h.copy(day = day) else h, next = false)
    roadFocusSeq += 1 // back from the app: the row (5.9 §5)
}

/** «Заменить» in the stop menu → the D-6 sheet. */
fun VerstFlow.stopMenuReplace() {
    val s = stopMenu ?: return
    stopMenu = null
    stopHandoff = null
    openReplace(s)
}

/** What the car labels name: the preferred maps app ([preferredMaps]), or the browser when it is not installed. */
val VerstFlow.carTarget: HandoffTarget get() = mapsTarget(preferredMaps)

/** Walks use the same preference (walking mode). */
val VerstFlow.walkTarget: HandoffTarget get() = carTarget

/** Where [app] would open now. */
fun VerstFlow.mapsTarget(app: HandoffApp): HandoffTarget = when (app) {
    HandoffApp.MAPS -> if (handoffLauncher?.mapsInstalled() == true) HandoffTarget.Maps else HandoffTarget.Browser
    HandoffApp.GOOGLE -> if (handoffLauncher?.googleInstalled() == true) HandoffTarget.Google else HandoffTarget.Browser
    HandoffApp.NAVI -> if (navigatorInstalled) HandoffTarget.Navigator else HandoffTarget.None
}

/** Kept for the R1 callers: the navigator app is installed. */
val VerstFlow.navigatorInstalled: Boolean get() = handoffLauncher?.navigatorInstalled() ?: false

internal suspend fun VerstFlow.engineHandoff(routeJson: String, options: String): HandoffDto? =
    (gateway.handoff(routeJson, options) as? EngineResult.Ok)?.value?.takeIf { h -> h.parts.isNotEmpty() }
        ?.let { h -> handoffSigner?.sign(h) ?: h }
