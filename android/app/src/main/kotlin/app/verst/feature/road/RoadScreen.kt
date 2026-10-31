package app.verst.feature.road

import androidx.compose.foundation.background
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.customActions
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.model.dto.HandoffDto
import app.verst.feature.card.CardActions
import app.verst.feature.card.CardSheet
import app.verst.feature.card.CardUi
import app.verst.nav.HandoffTarget
import androidx.compose.ui.semantics.onClick
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeoutOrNull
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.ui.semantics.Role
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import app.verst.feature.common.scaled
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.focusable
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.AlternativeDto
import app.verst.core.model.dto.DayDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.dto.TripDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.RoadSign
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.arrowFor
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.lerp
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftIconTile
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.DashedDivider
import app.verst.core.ui.components.craftField
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.IconButton44
import app.verst.feature.common.PlateToast
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.toastText
import app.verst.nav.ReplaceUi
import app.verst.nav.Toast
import app.verst.feature.common.crewShort
import app.verst.feature.common.days
import app.verst.feature.common.rub
import kotlin.math.roundToInt
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** Everything Road ahead draws (stateless; `VerstRoot` maps `VerstFlow` into it). */
data class RoadUi(
    val trip: TripDto,
    val bearing8: String,
    val fromSaved: Boolean = false,
    val saved: Boolean = false,
    val replace: ReplaceUi? = null,
    val toast: Toast? = null,
    val canUndo: Boolean = false,
    /** Overnight stop ids marked as booked (D-10) → «Забронировано ✓». */
    val booked: Set<String> = emptySet(),
    /** townId → prepositional name (engine `townPrepRu`) for «Выбрать отель в Ярославле». */
    val townPrep: Map<String, String> = emptyMap(),
    /** 5.5 offline: day links become «в навигатор» (disabled look, toast on tap). */
    val online: Boolean = true,
    /** D-5 stop menu of a long-pressed row, with the engine's hand-off once known (the truncated note). */
    val stopMenu: StopDto? = null,
    val navigatorInstalled: Boolean = false,
    val stopHandoff: HandoffDto? = null,
    /** 5.13 day menu (day number) and its hand-off. */
    val dayMenu: Int? = null,
    val dayHandoff: HandoffDto? = null,
    /** 5.13 §2: what the car label names (Maps / Google / Browser). */
    val carTarget: HandoffTarget = HandoffTarget.Browser,
    /** CEO 29.10: the maps app «Вести по картам» opens (Яндекс Карты or Google Карты; the browser names it too). */
    val maps: app.verst.nav.HandoffApp = app.verst.nav.HandoffApp.MAPS,
    /** S3-R1 focus restore. */
    val focus: RoadFocus = RoadFocus(),
    /** 5.9: an open card. */
    val card: CardUi? = null,
    /** 5.12 §3 «О данных» sheet. */
    val aboutData: Boolean = false,
    /** 5.8: the minimum of a no-fit, shown over budget everywhere. */
    val minimum: Boolean = false,
    /** M§15.5: which rows open a card (sights, nights with a hotel); CEO 29.10: a border crossing opens its sheet. */
    val tappable: (StopDto) -> Boolean = {
        it.kind == "sight" || (it.kind == "overnight" && it.hotelOptions.isNotEmpty()) || (it.kind == "border" && it.border != null)
    },
    /** 5.5 §10.6: the stop whose ParkingSheet is open. */
    val parking: StopDto? = null,
    /** CEO 29.10 (trips abroad): the border stop whose sheet is open. */
    val border: StopDto? = null,
    /** 5.5 §10.1: the day «Вести в навигаторе» starts with (today's day of a running trip, else 1). */
    val handoffDay: Int = 1,
    /** 5.13 §5: the open hand-off sheet. */
    val handoff: HandoffSheetUi? = null,
)

/** S3-R1 (CEO 2.1): the row to bring back ([focusId], highlighted) or the top row to restore ([topId]); [seq] = a return. */
data class RoadFocus(val focusId: String? = null, val topId: String? = null, val seq: Int = 0, val scrollY: Int? = null)

interface RoadActions {
    fun back()
    fun waybill()
    fun save()
    fun share()
    fun replace(stop: StopDto)
    fun pick(altId: String?)
    fun confirmReplace()
    fun closeReplace()
    fun undo()
    /** «Выбрать отель →» on a night row → 5.7 for that night. */
    fun hotel(stopId: String)

    /** 5.13 hand-off: the day link opens the day menu; the D-5 stop menu. */
    fun dayNavigator(day: Int) = Unit
    fun dayMenuGo() = Unit
    fun closeDayMenu() = Unit
    fun stopMenu(stop: StopDto) = Unit
    fun closeStopMenu() = Unit
    fun navigatorFromStop() = Unit
    fun stopMenuReplace() = Unit
    /** D-7 from the stop menu / the row's TalkBack action. */
    fun stopMenuReport() = Unit
    fun reportStop(stop: StopDto) = Unit

    /** S3-R1 focus restore: the top visible row and the scroll (debounced) and «the highlight was shown». */
    fun topRow(id: String?, scrollY: Int = 0) = Unit
    fun focusShown() = Unit

    /** 5.9: a sight / hotel row → its card. */
    fun card(stop: StopDto) = Unit
    fun card(): CardActions = object : CardActions {
        override fun close() = Unit
    }

    /** 5.12 §3 «Расстояния приблизительные · О данных». */
    fun aboutData() = Unit
    fun closeAboutData() = Unit

    /**
     * CEO 29.10: «Вести по картам» → the preferred maps app with every point of the day; a day's «вести» and a long-press
     * of the button → the hand-off sheet on that day (the choice of the app).
     */
    fun handoff(day: Int) = dayNavigator(day)
    fun handoffSheet(day: Int) = handoff(day)

    /** 5.5 §10.6: the P part of a row → the ParkingSheet. */
    fun parking(stop: StopDto) = Unit
    fun closeParking() = Unit

    /** CEO 29.10: the border sheet (opened by a tap on the row, through [card]). */
    fun closeBorder() = Unit

    /** 5.13 §5 the hand-off sheet's actions. */
    fun handoffSheet(): HandoffSheetActions = object : HandoffSheetActions {
        override fun scope(day: Int?) = Unit
        override fun pick(which: app.verst.nav.HandoffApp) = Unit
        override fun install(which: app.verst.nav.HandoffApp) = Unit
        override fun remember() = Unit
        override fun close() = Unit
    }
}

/**
 * 5.5 Road ahead: the day-by-day plan, «заменить» (D-6), save/share, the Waybill footer. Fork camper-ui (mockup
 * screen 6 «Дорога впереди»): the header card (route, km badge, the trip chips), «Вести по картам», the notes card,
 * then the days' stops in one craft card along a dashed road line — each stop an icon tile of its kind and a paper
 * row; the car rides the dashed line with the scroll. The app header and the tab bar are MainActivity's.
 */
@Composable
fun RoadScreen(ui: RoadUi, a: RoadActions) {
    val trip = ui.trip
    // S3-R1 focus restore: the scroll position and the rows' offsets in the scrolled content.
    val scroll = rememberScrollState()
    val rows = remember(trip) { mutableStateMapOf<String, Pair<Int, Int>>() }
    var content by remember { mutableStateOf<LayoutCoordinates?>(null) }
    var viewportH by remember { mutableStateOf(0) }
    var highlight by remember { mutableStateOf<String?>(null) }
    var section by remember { mutableStateOf(0 to 0) }
    // 5.9 §5: TalkBack focus moves to the returned row (input focus → TYPE_VIEW_FOCUSED, TalkBack follows it).
    val requesters = remember(trip) { mutableMapOf<String, FocusRequester>() }
    val density = LocalDensity.current
    LaunchedEffect(ui.focus.seq) {
        // motion.returnToItem (5.9 §5): jump (no animation) back to the same viewport offset, the focus row in view.
        val f = ui.focus
        val id = f.focusId ?: f.topId ?: return@LaunchedEffect
        val (y, h) = withTimeoutOrNull(2_000) { snapshotFlow { rows[id] }.filterNotNull().first() } ?: return@LaunchedEffect
        withFrameNanos { } // the content height (scroll.maxValue) of this frame
        val margin = with(density) { 16.dp.roundToPx() }
        val saved = f.scrollY
        var target = saved ?: if (f.focusId != null) y - (viewportH - h).coerceAtLeast(0) / 2 else y
        if (f.focusId != null && (y < target || y + h > target + viewportH)) {
            // the saved offset does not show the row (it moved): bring it into view
            target = if (h >= viewportH) y - margin else if (y < target) y - margin else y + h - viewportH + margin
        }
        scroll.scrollTo(target.coerceIn(0, scroll.maxValue))
        if (f.focusId != null) {
            withFrameNanos { }
            runCatching { requesters[f.focusId]?.requestFocus() }
            // motion.returnToItem (S3-QA P1-07): `overlay.returnFlash` held 400 ms, then an 800 ms fade
            // (reduced motion: shown static for 400 ms, removed without a fade)
            val m = DesignTokens.motion.returnToItem
            highlight = f.focusId
            delay(m.holdMs.toLong())
            highlight = null
            delay((m.highlightMs - m.holdMs).toLong())
            a.focusShown()
        }
    }
    // The top visible row, reported after scrolling settles (restored after Waybill / process death).
    LaunchedEffect(trip) {
        snapshotFlow { scroll.value }.collectLatest { v ->
            delay(250)
            val top = rows.entries.filter { (_, yh) -> yh.first + yh.second > v }.minByOrNull { it.value.first }?.key
            a.topRow(top, v)
        }
    }
    ScreenRoot(C.camper.page) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val windowH = maxHeight
            Column(Modifier.fillMaxSize()) {
                // The screen's own row under the app header: back (OI-27: «К лобовому» when opened from «Мои
                // поездки»), save, share.
                Row(Modifier.fillMaxWidth().padding(start = 6.dp, end = 6.dp, top = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                    val back = stringResource(if (ui.fromSaved) R.string.common_back_to_windshield else R.string.common_back_instruments)
                    BackLink(back, C.camper.ink, stringResource(R.string.cd_back, back), a::back, Modifier.testTag("road.back"))
                    Spacer(Modifier.weight(1f))
                    IconButton44(
                        Glyph.BOOKMARK, if (ui.saved) C.camper.orangeText else C.camper.ink,
                        stringResource(if (ui.saved) R.string.cd_road_saved else R.string.cd_road_save), "road.save", filled = ui.saved, onClick = a::save,
                    )
                    IconButton44(Glyph.SHARE, C.camper.ink, stringResource(R.string.cd_road_share), "road.share", onClick = a::share)
                }
                Box(Modifier.weight(1f).fillMaxWidth().onSizeChanged { viewportH = it.height }) {
                    // S-20: one scrolled column; the stops card draws a single dashed road line behind its rows.
                    // A trip has tens of rows, not thousands.
                    Column(
                        Modifier.fillMaxSize().verticalScroll(scroll).testTag("road.list")
                            .onGloballyPositioned { content = it }
                            .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 4.dp, bottom = 28.dp),
                        verticalArrangement = Arrangement.spacedBy(CraftDefaults.Gap),
                    ) {
                        HeaderCard(trip, ui.bearing8)
                        // 5.5 §10.1 / CEO 29.10: «Вести по картам» — today's day in the preferred maps app, every point
                        HandoffCta(ui.handoffDay, { a.handoff(ui.handoffDay) }, { a.handoffSheet(ui.handoffDay) }, maps = ui.maps, target = ui.carTarget)
                        Intro(trip, a)
                        val parkingOn = parkingAware(trip)
                        CraftCard(Modifier.fillMaxWidth().padding(end = CraftDefaults.ShadowX), padding = PaddingValues(start = StopsPadStart, end = 10.dp, top = 12.dp, bottom = 4.dp), spacing = 0.dp) {
                            Column(
                                Modifier.fillMaxWidth().roadLine()
                                    .onGloballyPositioned { c -> content?.let { root -> if (root.isAttached && c.isAttached) section = root.localPositionOf(c, Offset.Zero).y.roundToInt() to c.size.height } },
                            ) {
                                trip.daysList.forEachIndexed { di, d ->
                                    DayHeader(d, trip.roundTrip && di == trip.daysList.lastIndex && trip.days > 1, first = di == 0, parkingOn, { a.handoffSheet(d.day) }) { a.handoffSheet(d.day) }
                                    d.stops.forEachIndexed { si, st ->
                                        StopRow(
                                            st, di == 0 && si == 0, st.id in ui.booked, ui.townPrep[st.townId] ?: st.name,
                                            showParking = parkingOn && showsParking(st),
                                            onParking = { a.parking(st) },
                                            highlighted = st.id == highlight,
                                            focusRequester = requesters.getOrPut(st.id) { FocusRequester() },
                                            onPlaced = { y, h -> if (rows[st.id] != y to h) rows[st.id] = y to h },
                                            content = { content },
                                            onLongPress = { a.stopMenu(st) },
                                            onReport = { a.reportStop(st) },
                                            onTap = if (ui.tappable(st)) ({ a.card(st) }) else null,
                                            onHotel = { a.hotel(st.id) },
                                        ) { a.replace(st) }
                                    }
                                }
                            }
                        }
                    }
                    // components §26.3: the car rides the visible part of the dashed road line with the scroll
                    val (secY, secH) = section
                    if (secH > 0 && viewportH > 0) {
                        val top = with(density) { (secY - scroll.value).coerceAtLeast(0).toDp().value }
                        val bottom = with(density) { (secY + secH - scroll.value).coerceAtMost(viewportH).toDp().value }
                        CarMarker(
                            top, bottom, if (scroll.maxValue > 0) scroll.value.toFloat() / scroll.maxValue else 0f,
                            x = CraftDefaults.ScreenGutter + StopsPadStart + TileCol / 2 - DesignTokens.size.carMarkerW / 2,
                        )
                    }
                    Box(
                        Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(20.dp)
                            .background(Brush.verticalGradient(listOf(C.camper.page.copy(alpha = 0f), C.camper.page))),
                    )
                }
                Footer(trip, ui.minimum, parkingAware(trip), a::waybill)
            }
            val t = ui.toast
            if (t != null) {
                PlateToast(
                    toastText(t), bottom = FooterBottom + DesignTokens.size.ctaWaybillH + 16.dp,
                    action = if (ui.canUndo) stringResource(R.string.common_undo) else null, onAction = a::undo,
                )
            }
            val r = ui.replace
            if (r != null) ReplaceSheet(r, windowH, a)
            val m = ui.stopMenu
            if (m != null) StopMenuSheet(m, ui.stopHandoff, ui.carTarget, ui.maps, windowH, a)
            val dm = ui.dayMenu
            if (dm != null) DayMenuSheet(dm, ui.dayHandoff, ui.carTarget, ui.maps, windowH, a)
            val c = ui.card
            if (c != null) CardSheet(c, windowH, a.card())
            if (ui.aboutData) AboutDataSheet(windowH, a::closeAboutData)
            val pk = ui.parking
            if (pk != null) ParkingSheet(pk, windowH, a::closeParking)
            val bd = ui.border
            if (bd != null) BorderSheet(bd, windowH, a::closeBorder)
            val hs = ui.handoff
            if (hs != null) HandoffSheetView(trip, hs, windowH, a.handoffSheet())
        }
    }
}

/** The stop column of the stops card: the icon tiles (32) sit on the dashed road line at its centre. */
private val TileCol = CraftDefaults.TileSize

/** The stops card's start padding (the car's x follows it). */
private val StopsPadStart = 10.dp

/** The footer's distance to the tab bar (its hard shadow fits in it). */
private val FooterBottom = 12.dp

/** D-6: «Заменить: <name>» with the current stop and the engine's alternatives (Δ min / Δ ₽). */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.ReplaceSheet(r: ReplaceUi, windowH: androidx.compose.ui.unit.Dp, a: RoadActions) {
    val s = r.stop
    BottomSheet(stringResource(R.string.replace_title, stopName(s)), a::closeReplace, "replace", windowH) {
        Txt(stringResource(R.string.replace_subtitle), T.body.sm, C.camper.inkSoft, Modifier.padding(bottom = 10.dp))
        Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            // Sub-line: the engine's own sentence for the place (copy has no per-tag labels for food/rest yet).
            OptionRow(s, s.name, s.note ?: s.reason, stringResource(R.string.replace_current), r.picked == null, "replace.current") { a.pick(null) }
            s.alternatives.forEachIndexed { i, alt ->
                OptionRow(alt.stop ?: s, alt.name, alt.stop?.note ?: alt.stop?.reason, deltaText(alt), r.picked == alt.id, "replace.alt.$i", breaks = alt.breaksBudget) { a.pick(alt.id) }
            }
        }
        val note = s.alternativesNote
        if (note != null) Txt(note, T.body.md, C.camper.inkSoft, Modifier.padding(top = 10.dp))
        Spacer(Modifier.height(14.dp))
        if (s.alternatives.isNotEmpty()) {
            // N-13 / fork camper-ui: the orange craft button, sentence case, no arrow; disabled until another row is
            // picked (the end / bottom padding keep its hard shadow inside the sheet)
            val enabled = r.picked != null && !r.busy
            CraftButton(
                stringResource(R.string.replace_confirm), a::confirmReplace,
                Modifier.padding(end = CraftDefaults.ShadowX, bottom = CraftDefaults.ShadowY).fillMaxWidth().testTag("replace.confirm"),
                enabled = enabled,
            )
        }
        Box(
            Modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = a::closeReplace)
                .testTag("replace.keep"),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.replace_keep), T.body.mdStrong, C.camper.inkSoft) }
    }
}

/**
 * D-5 stop menu (5.13): the first item `handoff_from_stop` (target line below, the truncated note when the engine
 * kept only 8 vias), then «Заменить», then «Сообщить об ошибке» (D-7).
 */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.StopMenuSheet(
    s: StopDto,
    handoff: HandoffDto?,
    target: HandoffTarget,
    maps: app.verst.nav.HandoffApp,
    windowH: androidx.compose.ui.unit.Dp,
    a: RoadActions,
) {
    BottomSheet(stopName(s), a::closeStopMenu, "stopmenu", windowH) {
        // components §22 (S3-QA): items with 1 dp `dash.control` dividers, no gap. (1) the hand-off — not for
        // fuel / rest stops or a stop without coordinates; (2) «Заменить» where the row has it; (3) D-7.
        val items = mutableListOf<@Composable () -> Unit>()
        // CEO 29.10: not a border crossing either — its point is approximate (a town near it, not the checkpoint)
        val handoffRow = s.kind != "fuel" && s.kind != "rest" && s.kind != "border" && s.lat != null && s.lon != null
        if (handoffRow) {
            items += { HandoffItem(stringResource(R.string.handoff_from_stop), target, handoff?.truncated == true, enabled = handoff != null, tag = "stopmenu.navigator", maps = maps, onClick = a::navigatorFromStop) }
        }
        val canReplace = s.replaceable && (s.alternatives.isNotEmpty() || s.alternativesNote != null)
        if (canReplace) items += { ActionItem(stringResource(R.string.stopmenu_swap), "stopmenu.swap", a::stopMenuReplace) }
        items += { ActionItem(stringResource(R.string.stopmenu_report), "stopmenu.report", a::stopMenuReport) }
        items.forEachIndexed { i, item ->
            if (i > 0) DashedDivider(thickness = 1.5.dp)
            item()
        }
    }
}

/** 5.13 day menu: «День N» and one item «По картам: день N». */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.DayMenuSheet(
    day: Int,
    handoff: HandoffDto?,
    target: HandoffTarget,
    maps: app.verst.nav.HandoffApp,
    windowH: androidx.compose.ui.unit.Dp,
    a: RoadActions,
) {
    BottomSheet(stringResource(R.string.road_day, day), a::closeDayMenu, "daymenu", windowH) {
        HandoffItem(stringResource(R.string.handoff_day, day), target, handoff?.truncated == true, enabled = handoff != null, tag = "daymenu.go", maps = maps, onClick = a::dayMenuGo)
    }
}

/**
 * components §22 `HandoffItem`: navigator glyph, title, the target line, the truncated note, ↗ (it leaves the app).
 * The line names where it opens: [maps] (Яндекс / Google Карты) or that app's site in the browser.
 */
@Composable
internal fun HandoffItem(
    title: String,
    target: HandoffTarget,
    truncated: Boolean,
    enabled: Boolean,
    tag: String,
    maps: app.verst.nav.HandoffApp = app.verst.nav.HandoffApp.MAPS,
    onClick: () -> Unit,
) {
    val google = maps == app.verst.nav.HandoffApp.GOOGLE
    val line = when (target) {
        HandoffTarget.Navigator, HandoffTarget.NavigatorDryRun -> stringResource(R.string.handoff_navigator)
        HandoffTarget.Maps, HandoffTarget.MapsDryRun -> stringResource(R.string.handoff_maps_car)
        HandoffTarget.Google, HandoffTarget.GoogleDryRun -> stringResource(R.string.handoff_google_car)
        else -> stringResource(if (google) R.string.handoff_google_web else R.string.handoff_web)
    }
    val cd = when (target) {
        HandoffTarget.Navigator, HandoffTarget.NavigatorDryRun -> stringResource(R.string.handoff_cd_navigator)
        HandoffTarget.Maps, HandoffTarget.MapsDryRun, HandoffTarget.Google, HandoffTarget.GoogleDryRun -> line
        else -> stringResource(R.string.handoff_cd_web)
    }
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 64.dp)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = "$title. $cd" }
            .testTag(tag).padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CraftIconTile(R.drawable.ic_ui_location_arrow, active = enabled)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Txt(title, T.list.title, if (enabled) C.camper.ink else C.text.disabled, maxLines = 1)
            Txt(line, T.body.sm, C.camper.inkMuted, maxLines = 1, modifier = Modifier.testTag("$tag.target"))
            if (truncated) Txt(stringResource(R.string.handoff_truncated), T.body.sm, C.camper.orangeText, Modifier.testTag("$tag.truncated"))
        }
        GlyphIcon(Glyph.UP_RIGHT, C.camper.inkSoft, 16.dp)
    }
}

/**
 * The ODbL package (CEO D-IR-07, docs/legal/risk-register.md R-01): where the catalogue's free copy, the ODbL text
 * and the OpenStreetMap copyright page live, and the notice file the APK ships. The URIs are the ones in
 * `backend/planner/tools/data/build_catalogue.py` (`meta.licence`) and in the notice; `test_data_licence.py` keeps
 * the three in step.
 */
internal object DataLicence {
    /** core-ui `src/main/assets/licenses/` (the folder of the font NOTICE; ADR-0012 spelled it `licences`). */
    const val NOTICE_ASSET = "licenses/data.txt"
    const val CATALOGUE_COPY = "https://github.com/pazzia/Verst/tree/main/data/catalogue"
    const val ODBL = "https://opendatacommons.org/licenses/odbl/1-0/"
    const val OSM_COPYRIGHT = "https://www.openstreetmap.org/copyright"
}

/**
 * 5.12 §3 «О данных»: the sources and licences, then the links (the free catalogue copy, ODbL 1.0, OpenStreetMap
 * copyright; each leaves the app, ↗) and the full notice `assets/licenses/data.txt`, shown in place. The body
 * scrolls inside the sheet once the notice is open.
 */
@Composable
internal fun androidx.compose.foundation.layout.BoxScope.AboutDataSheet(windowH: androidx.compose.ui.unit.Dp, onClose: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val uri = androidx.compose.ui.platform.LocalUriHandler.current
    val notice = remember {
        runCatching { context.assets.open(DataLicence.NOTICE_ASSET).bufferedReader(Charsets.UTF_8).use { it.readText() } }.getOrNull()
    }
    var full by remember { mutableStateOf(false) }
    val open: (String) -> Unit = { url -> runCatching { uri.openUri(url) } }
    // BottomSheet already scrolls its content (a weighted verticalScroll column); a second weighted scroll column
    // here measured at 0 height inside it and hid the whole body (CI run 125).
    BottomSheet(stringResource(R.string.about_data_title), onClose, "aboutdata", windowH) {
        Txt(stringResource(R.string.about_data_body), T.body.md, C.camper.inkSoft, Modifier.padding(bottom = 8.dp))
        DataLink(stringResource(R.string.about_data_copy), "aboutdata.copy") { open(DataLicence.CATALOGUE_COPY) }
        DataLink(stringResource(R.string.about_data_odbl), "aboutdata.odbl") { open(DataLicence.ODBL) }
        DataLink(stringResource(R.string.about_data_osm), "aboutdata.osm") { open(DataLicence.OSM_COPYRIGHT) }
        if (notice != null) {
            DataLink(stringResource(if (full) R.string.about_data_notice_hide else R.string.about_data_notice), "aboutdata.notice", external = false) { full = !full }
            if (full) Txt(notice, T.body.sm, C.camper.inkSoft, Modifier.padding(top = 4.dp).testTag("aboutdata.notice.text"))
        }
    }
}

/** A link row of «О данных»: `type.body.mdStrong` orange text like `route_approx_more`, touch 44; ↗ when it leaves the app. */
@Composable
private fun DataLink(title: String, tag: String, external: Boolean = true, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .clickable(role = Role.Button, onClick = onClick).testTag(tag),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Txt(title, T.body.mdStrong, C.camper.orangeText, Modifier.weight(1f))
        if (external) GlyphIcon(Glyph.UP_RIGHT, C.camper.inkSoft, 16.dp)
    }
}

/** components §22 `ActionItem`: min-h 52, `type.list.title`, left-aligned, no icon; pressed `camper.header`. */
@Composable
private fun ActionItem(title: String, tag: String, onClick: () -> Unit) {
    val source = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    Box(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 52.dp)
            .background(if (pressed) C.camper.header else Color.Transparent)
            .clickable(source, indication = null, role = Role.Button, onClick = onClick).testTag(tag),
        contentAlignment = Alignment.CenterStart,
    ) { Txt(title, T.list.title, C.camper.ink, maxLines = 2) }
}

/** D-6 row (N-08), fork camper-ui: min-h 64, a white-paper field (orange 2 dp frame when picked); radio, the kind's mini sign at 0.7. */
@Composable
private fun OptionRow(kind: StopDto, name: String, sub: String?, delta: String, selected: Boolean, tag: String, breaks: Boolean = false, onClick: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 64.dp)
            .craftField(focused = selected)
            .selectable(selected, role = Role.RadioButton, onClick = onClick)
            .testTag(tag)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(Modifier.size(18.dp).border(2.dp, if (selected) C.camper.orange else C.camper.border, RoundedCornerShape(9.dp)), contentAlignment = Alignment.Center) {
            if (selected) Box(Modifier.size(8.dp).clip(RoundedCornerShape(4.dp)).background(C.camper.orange))
        }
        RoadSign(kind.sign, kind.name, app.verst.feature.common.signTags(kind.poiKind, kind.tags), Modifier.scaled(0.7f))
        Column(Modifier.weight(1f)) {
            Txt(name, T.title.sm, C.camper.ink, maxLines = 1)
            if (!sub.isNullOrBlank()) Txt(sub, T.body.sm, C.camper.inkSoft, maxLines = 2)
        }
        // 5.8 §3: a `breaksBudget` row — a red dot before the delta and «не в бюджете» (still selectable)
        Column(horizontalAlignment = Alignment.End) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (breaks) Box(Modifier.padding(end = 6.dp).size(6.dp).clip(RoundedCornerShape(3.dp)).background(C.accent.red).testTag("$tag.breaks"))
                Txt(delta, T.body.mdStrong, C.camper.ink, maxLines = 1)
            }
            if (breaks) Txt(stringResource(R.string.budget_alt_breaks), T.body.sm, C.accent.redText, maxLines = 1)
        }
    }
}

/** N-14: `replace_delta` with independent signs; a zero part is dropped (`_min` / `_rub` / `_none`). */
@Composable
private fun deltaText(alt: AlternativeDto): String {
    fun sign(n: Int) = if (n > 0) "+" else "−"
    val min = kotlin.math.abs(alt.deltaMin)
    val rub = app.verst.settings.AppPrefs.money(kotlin.math.abs(alt.deltaRub))
    return when {
        alt.deltaMin != 0 && alt.deltaRub != 0 -> stringResource(R.string.replace_delta, sign(alt.deltaMin), min, sign(alt.deltaRub), rub)
        alt.deltaMin != 0 -> stringResource(R.string.replace_delta_min, sign(alt.deltaMin), min)
        alt.deltaRub != 0 -> stringResource(R.string.replace_delta_rub, sign(alt.deltaRub), rub)
        else -> stringResource(R.string.replace_delta_none)
    }
}

/**
 * Fork camper-ui (mockup screen 6): the header card — «Дорога впереди» (orange overline), the bearing arrow and the
 * route, the km badge; under them the trip chips (days · nights, crew, pace). The title block is one heading.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun HeaderCard(trip: TripDto, bearing8: String) {
    CraftCard(Modifier.fillMaxWidth().padding(end = CraftDefaults.ShadowX), padding = PaddingValues(horizontal = 12.dp, vertical = 10.dp)) {
        Row(Modifier.fillMaxWidth().semantics(mergeDescendants = true) { heading() }, verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Txt(stringResource(R.string.road_title), CraftType.overline, C.camper.orangeText, maxLines = 1)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(arrowFor(bearing8), C.camper.ink, 16.dp)
                    Spacer(Modifier.width(6.dp))
                    Txt(trip.title, CraftType.cardTitle, C.camper.ink, Modifier.weight(1f, fill = false), maxLines = 2)
                }
            }
            Spacer(Modifier.width(8.dp))
            // `.craft-badge` with the km on the tagged text itself (e2e reads `road.km`'s text)
            Box(
                Modifier.clip(RoundedCornerShape(CraftDefaults.BadgeRadius)).background(C.camper.amber)
                    .border(CraftDefaults.BadgeBorder, C.camper.border, RoundedCornerShape(CraftDefaults.BadgeRadius))
                    .padding(horizontal = 8.dp, vertical = 2.dp),
                contentAlignment = Alignment.Center,
            ) { Txt(stringResource(R.string.road_odometer, RuFormat.thousands(trip.km)), CraftType.badge, C.camper.onAmber, Modifier.testTag("road.km"), maxLines = 1) }
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            // S-01: the deck's `road_chip_days` («3 дня · 2 ночи»), now with a string 4th argument.
            TripPill(
                if (trip.nights > 0) {
                    stringResource(
                        R.string.road_chip_days, trip.days, pluralStringResource(R.plurals.plural_day, trip.days),
                        trip.nights, pluralStringResource(R.plurals.plural_night, trip.nights),
                    )
                } else days(trip.days),
            )
            TripPill(crewShort(trip.input.crew.adults, trip.input.crew.children, trip.input.crew.dog))
            TripPill(stringResource(R.string.road_chip_pace, RuFormat.thousands(trip.input.dailyKm)))
        }
    }
}

/** A trip chip of the header card: white paper, 1.5 dp brown border, radius 10, ink text. */
@Composable
private fun TripPill(text: String) {
    val shape = RoundedCornerShape(CraftDefaults.BadgeRadius)
    Box(
        Modifier.clip(shape).background(C.camper.field).border(CraftDefaults.BadgeBorder, C.camper.border, shape)
            .padding(horizontal = 8.dp, vertical = 3.dp),
        contentAlignment = Alignment.Center,
    ) { Txt(text, T.body.smStrong, C.camper.ink, maxLines = 1) }
}

/** The amber tint of the warnings card (opaque: the card's hard shadow must not show through). */
private val WarnTint = lerp(C.camper.paper, C.camper.amber, 0.22f)

@Composable
private fun Intro(trip: TripDto, a: RoadActions) {
    val onAbout = a::aboutData
    CraftCard(Modifier.fillMaxWidth().padding(end = CraftDefaults.ShadowX), spacing = 6.dp) {
        Txt(stringResource(R.string.road_intro), T.body.mdTight, C.camper.inkSoft)
        // 5.5 §9 (S3-FINAL P1-02): the open-data notice is a muted info line, not a warning plate; with a synthetic
        // route both notes share one line (`route_approx_open_data`)
        // 5.5 §10.2: rows mark open data with the dotted ring; the legend is said once here (with «О данных»)
        val ringRows = trip.daysList.any { d -> d.stops.any { !it.verified } }
        // CEO 29.10: the trip-abroad notice has its own line below (it is not about open data)
        val openData = trip.warnings.firstOrNull { it.code == "UNVERIFIED_PLACES" || (it.level == "info" && it.code != ABROAD_WARNING) }
        val infoText = when {
            trip.approxDistances && openData != null && !ringRows -> stringResource(R.string.route_approx_open_data)
            trip.approxDistances -> stringResource(R.string.route_approx)
            openData != null && !ringRows -> openData.message
            else -> null
        }
        val posts = trip.daysList.any { d -> d.stops.any { it.kmDriven != null } }
        val abroad = trip.warnings.firstOrNull { it.code == ABROAD_WARNING }?.message
        if (infoText != null || abroad != null || ringRows || posts) DashedDivider()
        if (infoText != null) {
            Row(Modifier.fillMaxWidth().testTag(if (trip.approxDistances) "road.approx" else "road.opendata"), verticalAlignment = Alignment.CenterVertically) {
                GlyphIcon(Glyph.INFO, C.camper.inkMuted, 14.dp)
                Spacer(Modifier.width(6.dp))
                Txt(infoText, T.body.sm, C.camper.inkMuted, Modifier.weight(1f, fill = false))
                Box(
                    Modifier.padding(start = 8.dp).defaultMinSize(minHeight = DesignTokens.size.touchMin)
                        .clickable(role = Role.Button, onClick = onAbout).testTag("road.approx.more"),
                    contentAlignment = Alignment.Center,
                ) { Txt(stringResource(R.string.route_approx_more), T.body.mdStrong, C.camper.orangeText) }
            }
        }
        // CEO 29.10 (trips abroad): «цены, сборы и правила там … не проверены» — a muted info line too
        abroad?.let { m ->
            Row(Modifier.fillMaxWidth().testTag("road.abroad"), verticalAlignment = Alignment.CenterVertically) {
                GlyphIcon(Glyph.INFO, C.camper.inkMuted, 14.dp)
                Spacer(Modifier.width(6.dp))
                Txt(m, T.body.sm, C.camper.inkMuted, Modifier.weight(1f, fill = false))
            }
        }
        Legends(ringRows && !trip.approxDistances, posts = posts, onAbout)
        if (ringRows && trip.approxDistances) Legends(true, posts = false, onAbout = {}, about = false) // «О данных» is on the line above
    }
    // S3-QA P1-06: one plate per night — the engine sentence, then the night's «Ближайшая подходящая: …» note
    val seen = mutableSetOf<String>()
    // S3-QA2: with more than one night plate each one says which night («Ночь 2: не нашли …»)
    val nightPlates = trip.warnings.count { it.code == "NO_LODGING" && it.message != null }
    val nightPrefix = stringResource(R.string.road_night_prefix)
    for (w in trip.warnings) {
        if (w.code == "UNVERIFIED_PLACES" || w.level == "info") continue // the info line above
        val raw = w.message ?: continue
        if (!seen.add("${w.code}|${w.day}|$raw")) continue
        val night = w.day
        val msg = if (w.code == "NO_LODGING" && nightPlates > 1 && night != null) {
            String.format(nightPrefix, night, raw.replaceFirstChar { it.lowercase() })
        } else raw
        val second = if (w.code == "NO_LODGING" && w.day != null) {
            trip.daysList.firstOrNull { it.day == w.day }?.stops?.lastOrNull { it.kind == "overnight" }?.note?.takeIf { it.isNotBlank() && it != raw }
        } else null
        // fork camper-ui: an amber-tinted craft card with the amber «!» key
        Row(
            Modifier.fillMaxWidth().padding(end = CraftDefaults.ShadowX).craftSurface(fill = WarnTint)
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Box(
                Modifier.size(22.dp).clip(RoundedCornerShape(11.dp)).background(C.camper.amber)
                    .border(CraftDefaults.BadgeBorder, C.camper.border, RoundedCornerShape(11.dp)),
                contentAlignment = Alignment.Center,
            ) { Txt("!", T.caption.bold, C.camper.onAmber) }
            Column(Modifier.weight(1f)) {
                Txt(msg, T.body.md, C.camper.ink)
                if (second != null) Txt(second, T.body.sm, C.camper.inkSoft, Modifier.padding(top = 2.dp).testTag("road.warning.nearest"))
            }
        }
    }
}

/**
 * Mockup `.road-line`: the dashed brown road (3 dp, 6 on / 6 off, one phase for the whole trip) down the centre of
 * the stop column, behind the tiles.
 */
private fun Modifier.roadLine(): Modifier = drawBehind {
    val x = TileCol.toPx() / 2
    drawLine(
        C.camper.border, Offset(x, 0f), Offset(x, size.height), strokeWidth = 3.dp.toPx(),
        pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 6.dp.toPx())),
    )
}

@Composable
private fun DayHeader(day: DayDto, home: Boolean, first: Boolean, parkingOn: Boolean, onGo: () -> Unit, onSheet: () -> Unit) {
    val hours = (day.driveMin / 60.0).roundToInt()
    val meta = if (home) stringResource(R.string.road_day_meta_home, RuFormat.thousands(day.km))
    else stringResource(R.string.road_day_meta, RuFormat.thousands(day.km), hours)
    val cd = stringResource(R.string.cd_road_day, day.day, day.km.toString(), hours, pluralStringResource(R.plurals.plural_hour, hours)) +
        if (parkingOn) ". " + dayParkingCd(day) else ""
    Row(
        // the day's road tile on the dashed line, «День N» + meta, the day's «вести»
        Modifier.fillMaxWidth().padding(top = if (first) 0.dp else 8.dp, bottom = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(Modifier.width(TileCol), contentAlignment = Alignment.Center) {
            CraftIconTile(R.drawable.ic_ui_road, active = false, size = 28.dp, fill = C.camper.header)
        }
        Column(
            Modifier.weight(1f).semantics(mergeDescendants = true) { heading(); contentDescription = cd },
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            Txt(stringResource(R.string.road_day, day.day), CraftType.cardTitle, C.camper.orangeText, maxLines = 1)
            Txt(meta, T.body.sm, C.camper.inkSoft, maxLines = 1)
            // 5.5 §10.6: the day's parking under the meta («≈ 500 ₽ + ?»)
            if (parkingOn) DayParking(day)
        }
        // 5.5 §10.1: «вести» replaces «в навигатор ↗» → the hand-off sheet on this day
        DayGoButton(day.day, onGo, onSheet)
    }
}

/** The icon tile of a stop: the kind's icon, fill and tint (orange sights, amber nights, blue border, green rest). */
private class StopTile(val icon: Int, val fill: Color, val tint: Color)

private fun stopTile(s: StopDto, start: Boolean): StopTile = when {
    s.kind == "sight" -> StopTile(R.drawable.ic_ui_camera, C.camper.orange, C.camper.onOrange)
    s.kind == "overnight" -> StopTile(R.drawable.ic_ui_tent, C.camper.amber, C.camper.onAmber)
    s.kind == "border" -> StopTile(R.drawable.ic_ui_passport, C.camper.blue, C.camper.onOrange)
    s.kind == "rest" -> StopTile(R.drawable.ic_service_rest, C.camper.green, C.camper.onOrange)
    s.kind == "food" -> StopTile(R.drawable.ic_service_food, C.camper.paper, C.camper.border)
    s.kind == "fuel" -> StopTile(R.drawable.ic_service_fuel, C.camper.paper, C.camper.border)
    start || s.kind == "start" -> StopTile(R.drawable.ic_ui_van, C.camper.header, C.camper.border)
    else -> StopTile(R.drawable.ic_ui_route, C.camper.header, C.camper.border)
}

/** The overline colour of a stop row (orange sights, green nights, blue border; on paper, AA). */
private fun stopAccent(s: StopDto): Color = when (s.kind) {
    "sight" -> C.camper.orangeText
    "overnight" -> C.camper.greenText
    "border" -> C.camper.blue
    else -> C.camper.inkSoft
}

@Composable
private fun StopRow(
    s: StopDto,
    first: Boolean,
    booked: Boolean,
    townPrep: String,
    highlighted: Boolean,
    focusRequester: FocusRequester,
    onPlaced: (y: Int, h: Int) -> Unit,
    content: () -> LayoutCoordinates?,
    onLongPress: () -> Unit,
    onReport: () -> Unit,
    onTap: (() -> Unit)?,
    onHotel: () -> Unit,
    showParking: Boolean = false,
    onParking: () -> Unit = {},
    onReplace: () -> Unit,
) {
    val start = first || s.kind == "start"
    val line1 = if (start) stringResource(R.string.road_start)
    else stringResource(R.string.road_ahead_km, RuFormat.thousands(s.kmFromPrev))
    val time = RuFormat.clock(s.arriveAt ?: s.departAt) ?: ""
    val name = stopName(s)
    val note = noteWithAmenities(s)
    val kmPost = if (start) null else s.kmDriven
    val openDataCd = if (!s.verified) stringResource(R.string.cd_open_data) else null
    val kmCd = kmPost?.let { stringResource(R.string.cd_road_km_post, RuFormat.thousands(it)) }
    val cost: String? = when (s.kind) {
        // ADR-0019 E-2: 0 ₽ of an unknown price is not «вход свободный»
        "sight" -> if ("ticket" in s.unknownFacts) stringResource(R.string.road_ticket_unknown) else if (s.costRub == 0) stringResource(R.string.road_free) else rub(s.costRub)
        // CEO 29.10: a night or a meal abroad has no known price — «цена не указана», never 0 ₽ (the walk's rule)
        "food", "overnight" -> if (s.priceUnknown) stringResource(R.string.walk_stop_price_unknown) else rub(s.costRub)
        "rest" -> stringResource(R.string.common_rub, app.verst.settings.AppPrefs.money(0))
        "fuel" -> if (s.costRub > 0) rub(s.costRub) else null
        else -> null
    }
    val kindCd = (s.poiKindRu ?: app.verst.feature.common.kindWord(s.poiKind))?.lowercase()
    val parkingCd = if (showParking) stringResource(R.string.cd_road_parking_inline, parkingInline(s.parking)).substringBefore(". ") else null
    val crossing = s.kind == "border"
    val cd = listOfNotNull(line1, kmCd, time, name, kindCd, openDataCd, note, s.localTimeRu, s.unknownRu, cost, parkingCd).joinToString(", ")
    val canReplace = s.replaceable && (s.alternatives.isNotEmpty() || s.alternativesNote != null)
    // S3-R1: the restored row flashes `overlay.returnFlash` and fades (reduced motion: on, then off).
    val reduced = LocalReducedMotion.current
    val glow by animateFloatAsState(
        if (highlighted) 1f else 0f,
        if (reduced || highlighted) snap() else tween(DesignTokens.motion.returnToItem.highlightMs - DesignTokens.motion.returnToItem.holdMs, easing = DesignTokens.motion.returnToItem.easing),
        label = "focus",
    )
    val haptic = LocalHapticFeedback.current
    val longPress by rememberUpdatedState(onLongPress)
    val tap by rememberUpdatedState(onTap)
    val openLabel = stringResource(R.string.cd_card, s.name)
    val naviLabel = stringResource(R.string.cd_road_action_navigator)
    val swapLabel = stringResource(R.string.stopmenu_swap)
    val reportLabel = stringResource(R.string.cd_road_action_report)
    val tile = stopTile(s, start)
    val accent = stopAccent(s)
    Row(
        Modifier.fillMaxWidth()
            .onGloballyPositioned { c -> content()?.let { root -> if (root.isAttached && c.isAttached) onPlaced(root.localPositionOf(c, Offset.Zero).y.roundToInt(), c.size.height) } }
            // D-5: a long-press opens the stop menu (children's buttons keep their taps).
            .pointerInput(s.id, onTap != null) {
                // M§15.5: sights / hotel nights open the card; other rows have no tap at all (no click semantics)
                detectTapGestures(
                    onTap = if (onTap != null) ({ tap?.invoke() }) else null,
                    onLongPress = {
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        longPress()
                    },
                )
            }
            .padding(bottom = 12.dp)
            .semantics(mergeDescendants = true) {
                contentDescription = cd
                if (onTap != null) onClick(openLabel) { onTap(); true }
                customActions = listOfNotNull(
                    CustomAccessibilityAction(naviLabel) { onLongPress(); true },
                    if (canReplace) CustomAccessibilityAction(swapLabel) { onReplace(); true } else null,
                    CustomAccessibilityAction(reportLabel) { onReport(); true },
                )
            }
            .focusRequester(focusRequester)
            .focusable()
            .testTag("road.stop.${s.id}"),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        // the stop column on the dashed road line: the kind's tile, under it the km post (5.5 §10.8 decision B)
        Column(Modifier.width(TileCol), horizontalAlignment = Alignment.CenterHorizontally) {
            CraftIconTile(tile.icon, active = s.kind == "sight", fill = tile.fill, tint = tile.tint)
            if (kmPost != null) KmPost(kmPost, Modifier.padding(top = 8.dp))
        }
        // the paper row (mockup: white paper, 2 dp brown border, radius 12); the restored row glows inside it
        Column(
            Modifier.weight(1f)
                .craftSurface(fill = C.camper.field, radius = 12.dp, border = CraftDefaults.BorderThin, shadow = null)
                .drawBehind { if (glow > 0f) drawRect(C.overlay.returnFlash.copy(alpha = C.overlay.returnFlash.alpha * glow)) } // motion.returnToItem
                .padding(start = 10.dp, end = 2.dp, top = 4.dp, bottom = 6.dp),
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Txt(line1, CraftType.overline, accent, Modifier.weight(1f), maxLines = 1)
                Txt(time, CraftType.overline, accent, align = TextAlign.End)
                MoreButton(stringResource(R.string.cd_road_stop_more, s.name), "road.stop.${s.id}.more", onLongPress)
            }
            Row(Modifier.fillMaxWidth().padding(end = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Txt(name, CraftType.cardTitle, C.camper.ink, Modifier.weight(1f), maxLines = 2)
                // CEO 29.10: a crossing keeps the «граница» sign (the engine sends `city`)
                if (crossing) RoadSign(app.verst.core.ui.components.BORDER_SIGN, s.name, emptyList(), Modifier.padding(start = 6.dp).scaled(0.55f))
            }
            Column(Modifier.padding(end = 8.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                // 5.5 §10.7 part 3: one tag row (StretchTag before the KindTag, then the open-data ring); sights only
                app.verst.feature.common.TagRow(
                    if (s.kind == "sight") s.poiKind else null,
                    if (s.stretch) s.dwellMin.takeIf { it > 0 } ?: 30 else null,
                    openData = !s.verified || s.border?.unverified == true, // a crossing's facts: nobody checked them
                    modifier = Modifier.padding(vertical = 1.dp).testTag("road.tags.${s.id}"),
                    label = if (s.kind == "sight") s.poiKindRu else null,
                )
                if (!note.isNullOrBlank()) Txt(note, T.body.md, C.camper.inkSoft, maxLines = 2)
                // ADR-0019: what nobody checked for this stop («Часы не известны — уточните»), under the reason
                s.unknownRu?.let { Txt(it, T.body.sm, C.camper.inkMuted, Modifier.testTag("road.unknown.${s.id}"), maxLines = 2) }
                // block 1 / CEO 29.10: a stop on another clock (after the border) says its local time
                s.localTimeRu?.let { Txt(it, T.body.sm, C.camper.inkMuted, Modifier.testTag("road.localtime.${s.id}"), maxLines = 1) }
                val hotel = s.kind == "overnight" && s.hotelOptions.isNotEmpty()
                val borderSheet = crossing && s.border != null && onTap != null
                if (cost != null || canReplace || hotel || showParking || borderSheet) {
                    CostsLine(cost, s.parking, showParking, "road.stop.${s.id}", onParking) {
                        if (borderSheet) QuietAction(stringResource(R.string.road_border_open), stringResource(R.string.road_border_open), "road.border.${s.id}", C.camper.blue, { onTap?.invoke() })
                        else if (hotel) HotelAction(booked, if (booked) stringResource(R.string.cd_road_booked) else stringResource(R.string.cd_road_hotel, townPrep), "road.hotel.${s.id}", onHotel)
                        // designer В-5: «заменить» is a visible button (components §2.6), not quiet text
                        else if (canReplace) SwapButton(stringResource(R.string.cd_road_swap, s.name), "road.swap.${s.id}", onReplace)
                    }
                }
            }
        }
    }
}

/** 5.5 §10.4 / §10.7: rest amenities live inside the description («… Есть: туалет · столы · навес»). */
@Composable
private fun noteWithAmenities(s: StopDto): String? {
    // 5.5 §10.2: the dotted ring replaces every «не проверено» on rows (the engine's reason may still say it)
    val note = (s.note ?: s.reason)?.split(" · ")?.filterNot { it.trim().trimEnd('.').equals("не проверено", ignoreCase = true) }
        ?.joinToString(" · ")?.takeIf { it.isNotBlank() }
    if (s.amenities.isEmpty()) return note
    val words = s.amenities.mapNotNull {
        when (it) {
            "wc", "toilets", "toilet" -> stringResource(R.string.road_amenity_toilet)
            "tables", "picnic_table" -> stringResource(R.string.road_amenity_tables)
            "shelter" -> stringResource(R.string.road_amenity_shelter)
            "cafe", "cafe_at_fuel" -> stringResource(R.string.road_amenity_cafe)
            "playground" -> stringResource(R.string.road_amenity_playground)
            "walk" -> stringResource(R.string.road_amenity_walk)
            "view" -> stringResource(R.string.road_amenity_view)
            "ev_charger" -> stringResource(R.string.road_amenity_ev)
            "24h" -> stringResource(R.string.road_amenity_24h)
            else -> null // `parking` is the P part
        }
    }
    if (words.isEmpty()) return note
    val line = stringResource(R.string.road_rest_amenities, words.joinToString(" · ")).replaceFirstChar { it.uppercase() }
    return if (note.isNullOrBlank()) line else "${note.trimEnd()} $line"
}

/** components §26.2: hotels «выбрать отель →» 12/600 orange; booked «Забронировано ✓». */
@Composable
private fun HotelAction(booked: Boolean, cd: String, tag: String, onClick: () -> Unit) {
    QuietAction(
        stringResource(if (booked) R.string.road_booked else R.string.road_pick_hotel), cd, tag, C.camper.orangeText, onClick,
    ) { if (booked) GlyphIcon(Glyph.CHECK, C.camper.orangeText, 14.dp, Modifier.padding(start = 4.dp)) }
}

/** components §2.6 `SwapButton` «заменить», fork camper-ui: a small paper key (h 30, 2 dp border, tile shadow), touch 44. */
@Composable
private fun SwapButton(cd: String, tag: String, onClick: () -> Unit) {
    Box(
        Modifier.touch36().clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = cd }.testTag(tag).padding(start = 6.dp, end = 4.dp),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier.height(30.dp)
                .craftSurface(
                    fill = C.camper.paper, radius = 10.dp, border = CraftDefaults.BorderThin, shadow = C.camper.border,
                    shadowX = CraftDefaults.TileShadow, shadowY = CraftDefaults.TileShadow,
                )
                .padding(horizontal = 10.dp),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.road_swap), T.body.smStrong, C.camper.ink, maxLines = 1) }
    }
}

/** Designer В-6: «⋯» opens the stop menu (navigator from here, swap, report) — the long press stays as a shortcut. */
@Composable
private fun MoreButton(cd: String, tag: String, onClick: () -> Unit) {
    Box(
        Modifier.width(DesignTokens.size.touchMin).touchAt(18.dp).clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = cd }.testTag(tag),
        contentAlignment = Alignment.Center,
    ) { GlyphIcon(Glyph.MORE, C.camper.inkSoft, 20.dp) }
}

@Composable
private fun stopName(s: StopDto): String = when {
    s.kind == "overnight" -> stringResource(R.string.road_name_night, s.name)
    // 5.5 §10.4: a fun stop reads «Разминка · …» (unless the engine already said so)
    s.stretch && !s.name.startsWith(StretchPrefix) -> stringResource(R.string.road_stretch_name, s.name)
    else -> s.name
}

private const val StretchPrefix = "Разминка"

/**
 * The footer «ПУТЕВОЙ ЛИСТ · СКОЛЬКО СТОИТ», fork camper-ui: a craft card pinned above the tab bar — the receipt
 * tile, the label (budget badge / overrun / abroad), the total, per person or «из них парковки», the chevron.
 */
@Composable
private fun Footer(trip: TripDto, minimum: Boolean, parkingOn: Boolean, onClick: () -> Unit) {
    val c = trip.cost
    val fit = trip.budgetFit
    val budget = c.budgetRub
    // 5.8 §3: small overrun = fitted ≤ allowed but over the budget; over = the shown minimum / a plain overrun
    val tight = fit?.smallOverrun == true && budget != null && c.totalRub > budget
    val over = budget != null && (minimum || (c.overBudget && !tight))
    val fits = budget != null && !over && !tight
    // CEO 29.10 (trips abroad): the rouble total leaves the costs abroad out — the label says so
    val incomplete = trip.abroad?.roubleTotalIncomplete == true
    val label = when {
        over -> stringResource(R.string.road_waybill_over, app.verst.settings.AppPrefs.money((c.totalRub - budget!!).coerceAtLeast(0)))
        incomplete -> stringResource(R.string.road_total_abroad_incomplete)
        else -> stringResource(R.string.road_waybill_label)
    }
    val total = rub(c.totalRub)
    val perPerson = stringResource(R.string.road_waybill_per_person, app.verst.settings.AppPrefs.money(c.perPersonRub))
    val parkingSum = parkingOf(trip)
    val parkingRub = if (parkingOn) c.lines.firstOrNull { it.key == "parking" }?.rub ?: parkingSum.rub else null
    val parkingText = parkingRub?.let { parkingTotalText(parkingSum, it) }
    val cd = stringResource(R.string.cd_road_waybill, app.verst.settings.AppPrefs.money(c.totalRub)) + ". " + perPerson +
        (if (incomplete) ". " + stringResource(R.string.road_total_abroad_incomplete) else "") +
        (parkingText?.let { ". " + stringResource(R.string.road_footer_parking) + " " + it } ?: "")
    Row(
        Modifier
            .fillMaxWidth()
            .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter + CraftDefaults.ShadowX, top = 6.dp, bottom = FooterBottom)
            .defaultMinSize(minHeight = DesignTokens.size.ctaWaybillH)
            .craftSurface()
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("road.total")
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        CraftIconTile(R.drawable.ic_ui_receipt, active = true)
        // The label spans the row; the per-person line (F3) sits on the amount line, right of it (S-22).
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if ((fits || tight) && !incomplete) {
                    // «ПУТЕВОЙ ЛИСТ ·» + the badge (components §20)
                    Txt(label.substringBefore(" · ") + " · ", T.body.smStrong, C.camper.inkSoft, maxLines = 1)
                    if (fits) {
                        GlyphIcon(Glyph.CHECK, C.camper.greenText, 12.dp, Modifier.padding(end = 4.dp))
                        Txt(stringResource(R.string.budget_fit_badge), T.body.smStrong, C.camper.greenText, Modifier.testTag("road.fit"), maxLines = 1)
                    } else {
                        Box(Modifier.padding(end = 5.dp).size(8.dp).clip(RoundedCornerShape(4.dp)).background(C.budget.tight))
                        Txt(stringResource(R.string.budget_tight_badge, app.verst.settings.AppPrefs.money(c.totalRub - budget!!)), T.body.smStrong, C.camper.inkSoft, Modifier.testTag("road.tight"), maxLines = 1)
                    }
                } else {
                    val tag = when {
                        over -> "road.over"
                        incomplete -> "road.abroad.incomplete"
                        else -> "road.label"
                    }
                    Txt(label, T.body.smStrong, if (over) C.accent.redText else C.camper.inkSoft, Modifier.testTag(tag), maxLines = 1)
                }
            }
            Row(verticalAlignment = Alignment.Bottom) {
                Txt(total, T.amount, C.camper.ink, Modifier.testTag("road.total.amount"), maxLines = 1)
                Spacer(Modifier.weight(1f))
                // 5.5 §10.6: with parking the right block (under the label line) says «из них парковки»;
                // the per-person line yields to it
                if (parkingRub != null) FooterParking(parkingRub, parkingSum)
                else Txt(perPerson, T.body.smStrong, C.camper.inkSoft, Modifier.padding(start = 8.dp), maxLines = 1, align = TextAlign.End)
            }
        }
        Icon(R.drawable.ic_ui_chevron_right, C.camper.border, 18.dp)
    }
}

/** CEO 29.10: the engine's info warning of a trip abroad («цены, сборы и правила там … не проверены»). */
private const val ABROAD_WARNING = "ABROAD"
