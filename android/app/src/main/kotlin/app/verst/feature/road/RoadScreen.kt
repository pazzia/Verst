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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.layout.layout
import app.verst.feature.common.scaled
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.focusable
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.style.LineHeightStyle
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
import app.verst.core.ui.components.InfoChip
import app.verst.core.ui.components.RoadSign
import app.verst.core.ui.components.SkyStrip
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.PrimaryCta
import app.verst.core.ui.components.arrowFor
import app.verst.core.ui.components.dashboardSurface
import app.verst.core.ui.components.overheadPlate
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
    /** 5.13 §2: what the car label names (Navigator / Maps / Browser). */
    val carTarget: HandoffTarget = HandoffTarget.Browser,
    /** S3-R1 focus restore. */
    val focus: RoadFocus = RoadFocus(),
    /** 5.9: an open card. */
    val card: CardUi? = null,
    /** 5.12 §3 «О данных» sheet. */
    val aboutData: Boolean = false,
    /** 5.8: the minimum of a no-fit, shown over budget everywhere. */
    val minimum: Boolean = false,
    /** M§15.5: which rows open a card (sights, nights with a hotel). */
    val tappable: (StopDto) -> Boolean = { it.kind == "sight" || (it.kind == "overnight" && it.hotelOptions.isNotEmpty()) },
    /** 5.5 §10.6: the stop whose ParkingSheet is open. */
    val parking: StopDto? = null,
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

    /** 5.5 §10.1: «Вести в навигаторе» / a day's «вести» → the hand-off sheet on that day; long-press = always the sheet. */
    fun handoff(day: Int) = dayNavigator(day)
    fun handoffSheet(day: Int) = handoff(day)

    /** 5.5 §10.6: the P part of a row → the ParkingSheet. */
    fun parking(stop: StopDto) = Unit
    fun closeParking() = Unit

    /** 5.13 §5 the hand-off sheet's actions. */
    fun handoffSheet(): HandoffSheetActions = object : HandoffSheetActions {
        override fun scope(day: Int?) = Unit
        override fun pick(which: app.verst.nav.HandoffApp) = Unit
        override fun install(which: app.verst.nav.HandoffApp) = Unit
        override fun remember() = Unit
        override fun close() = Unit
    }
}

/** 5.5 Road ahead: the day-by-day signs of the plan, «заменить» (D-6), save/share, the Waybill footer. */
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
    val reducedMotion = LocalReducedMotion.current
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
    ScreenRoot(C.dash.raised, statusBar = C.sky.band1) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val windowH = maxHeight
            Column(Modifier.fillMaxSize()) {
                Box(Modifier.fillMaxWidth().height(150.dp)) {
                    SkyStrip(132.dp)
                    Box(Modifier.fillMaxSize().padding(top = 110.dp).dashboardSurface(curve = 30.dp, rim = false))
                    // OI-27: «К лобовому» when the trip was opened from «Мои поездки».
                    val back = stringResource(if (ui.fromSaved) R.string.common_back_to_windshield else R.string.common_back_instruments)
                    BackLink(back, C.mirror.label, stringResource(R.string.cd_back, back), a::back, Modifier.padding(start = 12.dp, top = 10.dp).testTag("road.back"))
                    Row(Modifier.align(Alignment.TopEnd).padding(top = 6.dp, end = 12.dp)) {
                        IconButton44(
                            Glyph.BOOKMARK, if (ui.saved) C.accent.yellowText else C.mirror.label,
                            stringResource(if (ui.saved) R.string.cd_road_saved else R.string.cd_road_save), "road.save", filled = ui.saved, onClick = a::save,
                        )
                        IconButton44(Glyph.SHARE, C.mirror.label, stringResource(R.string.cd_road_share), "road.share", onClick = a::share)
                    }
                    TitleSign(trip, ui.bearing8, Modifier.padding(start = 20.dp, end = 20.dp, top = 56.dp).fillMaxWidth())
                }
                Box(Modifier.weight(1f).fillMaxWidth().onSizeChanged { viewportH = it.height }) {
                    // S-20: one scrolled column; the road section draws a single continuous road (one lane-dash
                    // phase), the rows draw only their connector stubs. A trip has tens of rows, not thousands.
                    Column(
                        Modifier.fillMaxSize().verticalScroll(scroll).testTag("road.list")
                            .onGloballyPositioned { content = it },
                    ) {
                        Intro(trip, ui.handoffDay, a)
                        val parkingOn = parkingAware(trip)
                        Column(
                            Modifier.fillMaxWidth().roadSection()
                                .onGloballyPositioned { c -> content?.let { root -> if (root.isAttached && c.isAttached) section = root.localPositionOf(c, Offset.Zero).y.roundToInt() to c.size.height } },
                        ) {
                            trip.daysList.forEachIndexed { di, d ->
                                DayHeader(d, trip.roundTrip && di == trip.daysList.lastIndex && trip.days > 1, first = di == 0, parkingOn, { a.handoff(d.day) }) { a.handoffSheet(d.day) }
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
                            Spacer(Modifier.height(24.dp))
                        }
                    }
                    // components §26.3: the car loops over the visible part of the road (z above the km posts)
                    val (secY, secH) = section
                    if (secH > 0 && viewportH > 0) {
                        val top = with(density) { (secY - scroll.value).coerceAtLeast(0).toDp().value }
                        val bottom = with(density) { (secY + secH - scroll.value).coerceAtMost(viewportH).toDp().value }
                        CarMarker(top, bottom)
                    }
                    Box(
                        Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(24.dp)
                            .background(Brush.verticalGradient(listOf(C.dash.raised.copy(alpha = 0f), C.dash.raised))),
                    )
                }
                Footer(trip, ui.minimum, parkingAware(trip), a::waybill)
            }
            val t = ui.toast
            if (t != null) {
                PlateToast(
                    toastText(t), bottom = 24.dp + DesignTokens.size.ctaWaybillH + 16.dp,
                    action = if (ui.canUndo) stringResource(R.string.common_undo) else null, onAction = a::undo,
                )
            }
            val r = ui.replace
            if (r != null) ReplaceSheet(r, windowH, a)
            val m = ui.stopMenu
            if (m != null) StopMenuSheet(m, ui.stopHandoff, ui.carTarget, windowH, a)
            val dm = ui.dayMenu
            if (dm != null) DayMenuSheet(dm, ui.dayHandoff, ui.carTarget, windowH, a)
            val c = ui.card
            if (c != null) CardSheet(c, windowH, a.card())
            if (ui.aboutData) AboutDataSheet(windowH, a::closeAboutData)
            val pk = ui.parking
            if (pk != null) ParkingSheet(pk, windowH, a::closeParking)
            val hs = ui.handoff
            if (hs != null) HandoffSheetView(trip, hs, windowH, a.handoffSheet())
        }
    }
}

/** D-6: «Заменить: <name>» with the current stop and the engine's alternatives (Δ min / Δ ₽). */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.ReplaceSheet(r: ReplaceUi, windowH: androidx.compose.ui.unit.Dp, a: RoadActions) {
    val s = r.stop
    BottomSheet(stringResource(R.string.replace_title, stopName(s)), a::closeReplace, "replace", windowH) {
        Txt(stringResource(R.string.replace_subtitle), T.body.sm, C.text.secondary, Modifier.padding(bottom = 10.dp))
        Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            // Sub-line: the engine's own sentence for the place (copy has no per-tag labels for food/rest yet).
            OptionRow(s, s.name, s.note ?: s.reason, stringResource(R.string.replace_current), r.picked == null, "replace.current") { a.pick(null) }
            s.alternatives.forEachIndexed { i, alt ->
                OptionRow(alt.stop ?: s, alt.name, alt.stop?.note ?: alt.stop?.reason, deltaText(alt), r.picked == alt.id, "replace.alt.$i", breaks = alt.breaksBudget) { a.pick(alt.id) }
            }
        }
        val note = s.alternativesNote
        if (note != null) Txt(note, T.body.md, C.text.note, Modifier.padding(top = 10.dp))
        Spacer(Modifier.height(14.dp))
        if (s.alternatives.isNotEmpty()) {
            // N-13: `YellowButton` h 56, sentence case, no arrow; disabled until another row is picked.
            val enabled = r.picked != null && !r.busy
            Box(
                Modifier.fillMaxWidth().height(DesignTokens.size.buttonH).clip(RoundedCornerShape(DesignTokens.radius.r12))
                    .background(if (enabled) C.accent.yellow else C.dash.control)
                    .clickable(enabled = enabled, role = Role.Button, onClick = a::confirmReplace)
                    .testTag("replace.confirm"),
                contentAlignment = Alignment.Center,
            ) { Txt(stringResource(R.string.replace_confirm), T.cta.sm, if (enabled) C.text.onLight else C.text.disabled, maxLines = 1) }
        }
        Box(
            Modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = a::closeReplace)
                .testTag("replace.keep"),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.replace_keep), T.body.mdStrong, C.text.secondary) }
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
    windowH: androidx.compose.ui.unit.Dp,
    a: RoadActions,
) {
    BottomSheet(stopName(s), a::closeStopMenu, "stopmenu", windowH) {
        // components §22 (S3-QA): items with 1 dp `dash.control` dividers, no gap. (1) the hand-off — not for
        // fuel / rest stops or a stop without coordinates; (2) «Заменить» where the row has it; (3) D-7.
        val items = mutableListOf<@Composable () -> Unit>()
        val handoffRow = s.kind != "fuel" && s.kind != "rest" && s.lat != null && s.lon != null
        if (handoffRow) {
            items += { HandoffItem(stringResource(R.string.handoff_from_stop), target, handoff?.truncated == true, enabled = handoff != null, tag = "stopmenu.navigator", onClick = a::navigatorFromStop) }
        }
        val canReplace = s.replaceable && (s.alternatives.isNotEmpty() || s.alternativesNote != null)
        if (canReplace) items += { ActionItem(stringResource(R.string.stopmenu_swap), "stopmenu.swap", a::stopMenuReplace) }
        items += { ActionItem(stringResource(R.string.stopmenu_report), "stopmenu.report", a::stopMenuReport) }
        items.forEachIndexed { i, item ->
            if (i > 0) Box(Modifier.fillMaxWidth().height(1.dp).background(C.dash.control))
            item()
        }
    }
}

/** 5.13 day menu: «День N» and one item «В навигатор: день N». */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.DayMenuSheet(
    day: Int,
    handoff: HandoffDto?,
    target: HandoffTarget,
    windowH: androidx.compose.ui.unit.Dp,
    a: RoadActions,
) {
    BottomSheet(stringResource(R.string.road_day, day), a::closeDayMenu, "daymenu", windowH) {
        HandoffItem(stringResource(R.string.handoff_day, day), target, handoff?.truncated == true, enabled = handoff != null, tag = "daymenu.go", onClick = a::dayMenuGo)
    }
}

/** components §22 `HandoffItem`: navigator glyph, title, the target line, the truncated note, ↗ (it leaves the app). */
@Composable
internal fun HandoffItem(title: String, target: HandoffTarget, truncated: Boolean, enabled: Boolean, tag: String, onClick: () -> Unit) {
    val line = when (target) {
        HandoffTarget.Navigator, HandoffTarget.NavigatorDryRun -> stringResource(R.string.handoff_navigator)
        HandoffTarget.Maps, HandoffTarget.MapsDryRun -> stringResource(R.string.handoff_maps_car)
        else -> stringResource(R.string.handoff_web)
    }
    val cd = when (target) {
        HandoffTarget.Navigator, HandoffTarget.NavigatorDryRun -> stringResource(R.string.handoff_cd_navigator)
        else -> stringResource(R.string.handoff_cd_web)
    }
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 64.dp)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = "$title. $cd" }
            .testTag(tag).padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        GlyphIcon(Glyph.NAVIGATOR, C.accent.yellowText, 22.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Txt(title, T.list.title, if (enabled) C.text.primary else C.text.disabled, maxLines = 1)
            Txt(line, T.body.sm, C.text.muted, maxLines = 1, modifier = Modifier.testTag("$tag.target"))
            if (truncated) Txt(stringResource(R.string.handoff_truncated), T.body.sm, C.accent.yellowText, Modifier.testTag("$tag.truncated"))
        }
        GlyphIcon(Glyph.UP_RIGHT, C.text.secondary, 16.dp)
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
        Txt(stringResource(R.string.about_data_body), T.body.md, C.text.secondary, Modifier.padding(bottom = 8.dp))
        DataLink(stringResource(R.string.about_data_copy), "aboutdata.copy") { open(DataLicence.CATALOGUE_COPY) }
        DataLink(stringResource(R.string.about_data_odbl), "aboutdata.odbl") { open(DataLicence.ODBL) }
        DataLink(stringResource(R.string.about_data_osm), "aboutdata.osm") { open(DataLicence.OSM_COPYRIGHT) }
        if (notice != null) {
            DataLink(stringResource(if (full) R.string.about_data_notice_hide else R.string.about_data_notice), "aboutdata.notice", external = false) { full = !full }
            if (full) Txt(notice, T.body.sm, C.text.secondary, Modifier.padding(top = 4.dp).testTag("aboutdata.notice.text"))
        }
    }
}

/** A link row of «О данных»: `type.body.mdStrong` `color.navi.label` like `route_approx_more`, touch 44; ↗ when it leaves the app. */
@Composable
private fun DataLink(title: String, tag: String, external: Boolean = true, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .clickable(role = Role.Button, onClick = onClick).testTag(tag),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Txt(title, T.body.mdStrong, C.navi.label, Modifier.weight(1f))
        if (external) GlyphIcon(Glyph.UP_RIGHT, C.text.secondary, 16.dp)
    }
}

/** components §22 `ActionItem`: min-h 52, `type.list.title`, left-aligned, no icon; pressed `dash.pressed`. */
@Composable
private fun ActionItem(title: String, tag: String, onClick: () -> Unit) {
    val source = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    Box(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 52.dp)
            .background(if (pressed) C.dash.pressed else androidx.compose.ui.graphics.Color.Transparent)
            .clickable(source, indication = null, role = Role.Button, onClick = onClick).testTag(tag),
        contentAlignment = Alignment.CenterStart,
    ) { Txt(title, T.list.title, C.text.primary, maxLines = 2) }
}

/** D-6 row (N-08): min-h 64, `dash.controlAlt`, radius 10, padding 10 12; radio, the kind's mini sign at 0.7. */
@Composable
private fun OptionRow(kind: StopDto, name: String, sub: String?, delta: String, selected: Boolean, tag: String, breaks: Boolean = false, onClick: () -> Unit) {
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 64.dp)
            .clip(shape)
            .background(C.dash.controlAlt)
            .then(if (selected) Modifier.border(DesignTokens.stroke.w1, C.accent.yellowText, shape) else Modifier)
            .selectable(selected, role = Role.RadioButton, onClick = onClick)
            .testTag(tag)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(Modifier.size(18.dp).border(2.dp, if (selected) C.accent.yellowText else C.text.secondary, RoundedCornerShape(9.dp)), contentAlignment = Alignment.Center) {
            if (selected) Box(Modifier.size(6.dp).clip(RoundedCornerShape(3.dp)).background(C.accent.yellow))
        }
        RoadSign(kind.sign, kind.name, app.verst.feature.common.signTags(kind.poiKind, kind.tags), Modifier.scaled(0.7f))
        Column(Modifier.weight(1f)) {
            Txt(name, T.title.sm, C.text.primary, maxLines = 1)
            if (!sub.isNullOrBlank()) Txt(sub, T.body.sm, C.text.secondary, maxLines = 2)
        }
        // 5.8 §3: a `breaksBudget` row — a red dot before the delta and «не в бюджете» (still selectable)
        Column(horizontalAlignment = Alignment.End) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (breaks) Box(Modifier.padding(end = 6.dp).size(6.dp).clip(RoundedCornerShape(3.dp)).background(C.accent.red).testTag("$tag.breaks"))
                Txt(delta, T.body.mdStrong, C.text.primary, maxLines = 1)
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

@Composable
private fun TitleSign(trip: TripDto, bearing8: String, modifier: Modifier) {
    val cd = "${trip.title}, ${trip.km}"
    Row(
        modifier
            .height(49.dp)
            .overheadPlate(outer = 3.dp, radius = 7.dp, innerRadius = 5.dp)
            .semantics(mergeDescendants = true) { heading(); contentDescription = cd }
            .padding(horizontal = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(arrowFor(bearing8), C.sign.white, 20.dp)
        Spacer(Modifier.width(8.dp))
        Txt(trip.title, T.sign.xl, C.sign.white, Modifier.weight(1f), maxLines = 1)
        Txt(RuFormat.thousands(trip.km), T.sign.xl, C.sign.white, Modifier.testTag("road.km"))
    }
}

@Composable
private fun Intro(trip: TripDto, handoffDay: Int, a: RoadActions) {
    val onAbout = a::aboutData
    // S-21 / 5.5 §2.2: L1 at the list top, L2 +6, L3 +8, road column 18 below L3 (padding 4 + margin 14).
    Column(Modifier.padding(start = 20.dp, end = 20.dp, top = 0.dp, bottom = 18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        // N-07: the 29.4 line box exactly (no font padding, trimmed line height), so the chips land at +6.
        Txt(stringResource(R.string.road_title), T.display.copy(lineHeightStyle = TightLines), C.text.primary, Modifier.semantics { heading() })
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            // S-01: the deck's `road_chip_days` («3 дня · 2 ночи»), now with a string 4th argument.
            InfoChip(
                if (trip.nights > 0) {
                    stringResource(
                        R.string.road_chip_days, trip.days, pluralStringResource(R.plurals.plural_day, trip.days),
                        trip.nights, pluralStringResource(R.plurals.plural_night, trip.nights),
                    )
                } else days(trip.days),
            )
            InfoChip(crewShort(trip.input.crew.adults, trip.input.crew.children, trip.input.crew.dog))
            InfoChip(stringResource(R.string.road_chip_pace, RuFormat.thousands(trip.input.dailyKm)))
        }
        // 5.5 §10.1: «Вести в навигаторе» under the chips (a link carries one day → the sheet on today's day)
        HandoffCta(handoffDay, { a.handoff(handoffDay) }, { a.handoffSheet(handoffDay) }, Modifier.padding(top = 6.dp))
        Txt(stringResource(R.string.road_intro), T.body.mdTight, C.text.secondary, Modifier.padding(top = 4.dp))
        // 5.5 §9 (S3-FINAL P1-02): the open-data notice is a muted info line, not a warning plate; with a synthetic
        // route both notes share one line (`route_approx_open_data`)
        // 5.5 §10.2: rows mark open data with the dotted ring; the legend is said once here (with «О данных»)
        val ringRows = trip.daysList.any { d -> d.stops.any { !it.verified } }
        val openData = trip.warnings.firstOrNull { it.code == "UNVERIFIED_PLACES" || it.level == "info" }
        val infoText = when {
            trip.approxDistances && openData != null && !ringRows -> stringResource(R.string.route_approx_open_data)
            trip.approxDistances -> stringResource(R.string.route_approx)
            openData != null && !ringRows -> openData.message
            else -> null
        }
        if (infoText != null) {
            Row(Modifier.fillMaxWidth().testTag(if (trip.approxDistances) "road.approx" else "road.opendata"), verticalAlignment = Alignment.CenterVertically) {
                GlyphIcon(Glyph.INFO, C.text.muted, 14.dp)
                Spacer(Modifier.width(6.dp))
                Txt(infoText, T.body.sm, C.text.muted, Modifier.weight(1f, fill = false))
                Box(
                    Modifier.padding(start = 8.dp).defaultMinSize(minHeight = DesignTokens.size.touchMin)
                        .clickable(role = Role.Button, onClick = onAbout).testTag("road.approx.more"),
                    contentAlignment = Alignment.Center,
                ) { Txt(stringResource(R.string.route_approx_more), T.body.mdStrong, C.navi.label) }
            }
        }
        Legends(ringRows && !trip.approxDistances, posts = trip.daysList.any { d -> d.stops.any { it.kmDriven != null } }, onAbout)
        if (ringRows && trip.approxDistances) Legends(true, posts = false, onAbout = {}, about = false) // «О данных» is on the line above
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
            Row(
                Modifier.fillMaxWidth().padding(top = 4.dp)
                    .border(DesignTokens.stroke.w1, C.accent.yellowText, RoundedCornerShape(DesignTokens.radius.r10))
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(Modifier.width(14.dp).height(14.dp).clip(RoundedCornerShape(7.dp)).background(C.accent.yellow), contentAlignment = Alignment.Center) {
                    Txt("!", T.caption.bold, C.text.onLight)
                }
                Column(Modifier.weight(1f)) {
                    Txt(msg, T.body.md, C.text.primary)
                    if (second != null) Txt(second, T.body.sm, C.text.secondary, Modifier.padding(top = 2.dp).testTag("road.warning.nearest"))
                }
            }
        }
    }
}

/**
 * 5.5 §10.8: the road column x 10…62 (3 dp white edges), centre dashes at x 36 (32 / 64, one global phase);
 * the car lane is x 13–31, the km posts x 37–59.
 */
private fun Modifier.roadSection(): Modifier = drawBehind {
    val dp = 1.dp.toPx()
    drawRect(C.scene.road, Offset(10 * dp, 0f), Size(52 * dp, size.height))
    drawRect(C.scene.roadEdge, Offset(10 * dp, 0f), Size(3 * dp, size.height))
    drawRect(C.scene.roadEdge, Offset(59 * dp, 0f), Size(3 * dp, size.height))
    var y = 0f
    while (y < size.height) {
        drawRect(C.scene.roadEdge, Offset(34.5f * dp, y), Size(3 * dp, minOf(32 * dp, size.height - y)))
        y += 64 * dp
    }
}

/** Per row: the 8 × 3 connector stub at x 60, row top + 30 (`color.interior.pole`), from the road to the sign. */
private fun Modifier.connector(): Modifier = drawBehind {
    val dp = 1.dp.toPx()
    drawRect(C.interior.pole, Offset(60 * dp, 30 * dp), Size(8 * dp, 3 * dp))
}

@Composable
private fun DayHeader(day: DayDto, home: Boolean, first: Boolean, parkingOn: Boolean, onGo: () -> Unit, onSheet: () -> Unit) {
    val hours = (day.driveMin / 60.0).roundToInt()
    val meta = if (home) stringResource(R.string.road_day_meta_home, RuFormat.thousands(day.km))
    else stringResource(R.string.road_day_meta, RuFormat.thousands(day.km), hours)
    val cd = stringResource(R.string.cd_road_day, day.day, day.km.toString(), hours, pluralStringResource(R.plurals.plural_hour, hours)) +
        if (parkingOn) ". " + dayParkingCd(day) else ""
    Row(
        // S-21 / 5.5 §10.7: day 1 starts at the road top, later days 6 below the previous row; 10 to row 1.
        Modifier.fillMaxWidth().padding(start = 66.dp, end = 12.dp, top = if (first) 0.dp else 6.dp, bottom = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(
            Modifier.weight(1f).semantics(mergeDescendants = true) { heading(); contentDescription = cd },
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Txt(stringResource(R.string.road_day, day.day), T.title.sm, C.accent.yellowText, maxLines = 1)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Txt(meta, T.body.sm, C.text.muted, maxLines = 1)
                // 5.5 §10.6: the day's parking under the meta («≈ 500 ₽ + ?»)
                if (parkingOn) DayParking(day)
            }
        }
        // 5.5 §10.1: «вести» replaces «в навигатор ↗» → the hand-off sheet on this day
        DayGoButton(day.day, onGo, onSheet)
    }
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
        "food", "overnight" -> rub(s.costRub)
        "rest" -> stringResource(R.string.common_rub, app.verst.settings.AppPrefs.money(0))
        "fuel" -> if (s.costRub > 0) rub(s.costRub) else null
        else -> null
    }
    val kindCd = (s.poiKindRu ?: app.verst.feature.common.kindWord(s.poiKind))?.lowercase()
    val parkingCd = if (showParking) stringResource(R.string.cd_road_parking_inline, parkingInline(s.parking)).substringBefore(". ") else null
    val cd = listOfNotNull(line1, kmCd, time, name, kindCd, openDataCd, note, s.unknownRu, cost, parkingCd).joinToString(", ")
    val canReplace = s.replaceable && (s.alternatives.isNotEmpty() || s.alternativesNote != null)
    // S3-R1: the restored row flashes `accent.yellow` at 14 % and fades (reduced motion: on, then off).
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
    Row(
        Modifier.fillMaxWidth()
            .onGloballyPositioned { c -> content()?.let { root -> if (root.isAttached && c.isAttached) onPlaced(root.localPositionOf(c, Offset.Zero).y.roundToInt(), c.size.height) } }
            .drawBehind { if (glow > 0f) drawRect(C.overlay.returnFlash.copy(alpha = C.overlay.returnFlash.alpha * glow)) } // motion.returnToItem
            .connector()
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
            .padding(top = 8.dp, bottom = 12.dp, end = 4.dp)
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
    ) {
        // 5.5 §10.8 decision B: the km post in the post zone x 37–59, row top + 4 (the row's top padding is 8)
        Box(Modifier.width(66.dp)) {
            if (kmPost != null) KmPost(kmPost, Modifier.padding(start = 37.dp).offset(y = (-4).dp))
        }
        // the sign column 66–132 (city signs with their 2 dp outline may overflow it by a dp each side)
        Box(Modifier.widthIn(min = 66.dp), contentAlignment = Alignment.TopCenter) {
            RoadSign(s.sign, s.name, app.verst.feature.common.signTags(s.poiKind, s.tags))
        }
        Column(Modifier.weight(1f).padding(start = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Txt(line1, T.body.sm, C.text.muted, Modifier.weight(1f), maxLines = 1)
                Txt(time, T.body.sm, C.text.muted, align = TextAlign.End)
                MoreButton(stringResource(R.string.cd_road_stop_more, s.name), "road.stop.${s.id}.more", onLongPress)
            }
            Txt(name, T.title.md, C.text.primary, maxLines = 2)
            // 5.5 §10.7 part 3: one tag row (StretchTag before the KindTag, then the open-data ring); sights only
            app.verst.feature.common.TagRow(
                if (s.kind == "sight") s.poiKind else null,
                if (s.stretch) s.dwellMin.takeIf { it > 0 } ?: 30 else null,
                openData = !s.verified,
                modifier = Modifier.padding(vertical = 1.dp).testTag("road.tags.${s.id}"),
                label = if (s.kind == "sight") s.poiKindRu else null,
            )
            if (!note.isNullOrBlank()) Txt(note, T.body.md, C.text.note, maxLines = 2)
            // ADR-0019: what nobody checked for this stop («Часы не известны — уточните»), under the reason
            s.unknownRu?.let { Txt(it, T.body.sm, C.text.muted, Modifier.testTag("road.unknown.${s.id}"), maxLines = 2) }
            val hotel = s.kind == "overnight" && s.hotelOptions.isNotEmpty()
            if (cost != null || canReplace || hotel || showParking) {
                CostsLine(cost, s.parking, showParking, "road.stop.${s.id}", onParking) {
                    if (hotel) HotelAction(booked, if (booked) stringResource(R.string.cd_road_booked) else stringResource(R.string.cd_road_hotel, townPrep), "road.hotel.${s.id}", onHotel)
                    // designer В-5: «заменить» is a visible outline button (components §2.6), not quiet text
                    else if (canReplace) SwapButton(stringResource(R.string.cd_road_swap, s.name), "road.swap.${s.id}", onReplace)
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

/** components §26.2: hotels «выбрать отель →» 12/600 `navi.label`; booked «Забронировано ✓». */
@Composable
private fun HotelAction(booked: Boolean, cd: String, tag: String, onClick: () -> Unit) {
    QuietAction(
        stringResource(if (booked) R.string.road_booked else R.string.road_pick_hotel), cd, tag, C.navi.label, onClick,
    ) { if (booked) GlyphIcon(Glyph.CHECK, C.navi.label, 14.dp, Modifier.padding(start = 4.dp)) }
}

/** components §2.6 `SwapButton` «заменить»: h 32 in the 36 costs line (touch 44), outline, `type.body.smStrong`. */
@Composable
private fun SwapButton(cd: String, tag: String, onClick: () -> Unit) {
    Box(
        Modifier.touch36().clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = cd }.testTag(tag).padding(start = 6.dp),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier.height(32.dp).border(DesignTokens.stroke.w1, C.text.secondary, RoundedCornerShape(DesignTokens.radius.r8)).padding(horizontal = 10.dp),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.road_swap), T.body.smStrong, C.text.primary, maxLines = 1) }
    }
}

/** Designer В-6: «⋯» opens the stop menu (navigator from here, swap, report) — the long press stays as a shortcut. */
@Composable
private fun MoreButton(cd: String, tag: String, onClick: () -> Unit) {
    Box(
        Modifier.width(DesignTokens.size.touchMin).touchAt(18.dp).clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = cd }.testTag(tag),
        contentAlignment = Alignment.Center,
    ) { GlyphIcon(Glyph.MORE, C.text.secondary, 20.dp) }
}

/** components §2.6 `HotelButton` «Выбрать отель →» (blue), booked «Забронировано ✓». */
@Composable
private fun HotelButton(booked: Boolean, cd: String, tag: String, onClick: () -> Unit) {
    Box(
        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = cd }.testTag(tag),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier.height(36.dp).clip(RoundedCornerShape(DesignTokens.radius.r8)).background(C.sign.blue).padding(horizontal = 12.dp),
            contentAlignment = Alignment.Center,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Txt(stringResource(if (booked) R.string.road_booked else R.string.road_pick_hotel), T.body.mdStrong, C.sign.white, maxLines = 1)
                // N-09: the check is drawn (the font has no «✓»).
                if (booked) GlyphIcon(Glyph.CHECK, C.sign.white, 16.dp, Modifier.padding(start = 6.dp))
            }
        }
    }
}

@Composable
private fun stopName(s: StopDto): String = when {
    s.kind == "overnight" -> stringResource(R.string.road_name_night, s.name)
    // 5.5 §10.4: a fun stop reads «Разминка · …» (unless the engine already said so)
    s.stretch && !s.name.startsWith(StretchPrefix) -> stringResource(R.string.road_stretch_name, s.name)
    else -> s.name
}

private const val StretchPrefix = "Разминка"

@Composable
private fun Footer(trip: TripDto, minimum: Boolean, parkingOn: Boolean, onClick: () -> Unit) {
    val c = trip.cost
    val fit = trip.budgetFit
    val budget = c.budgetRub
    // 5.8 §3: small overrun = fitted ≤ allowed but over the budget; over = the shown minimum / a plain overrun
    val tight = fit?.smallOverrun == true && budget != null && c.totalRub > budget
    val over = budget != null && (minimum || (c.overBudget && !tight))
    val fits = budget != null && !over && !tight
    val label = when {
        over -> stringResource(R.string.road_waybill_over, app.verst.settings.AppPrefs.money((c.totalRub - budget!!).coerceAtLeast(0)))
        else -> stringResource(R.string.road_waybill_label)
    }
    val total = rub(c.totalRub)
    val perPerson = stringResource(R.string.road_waybill_per_person, app.verst.settings.AppPrefs.money(c.perPersonRub))
    val parkingSum = parkingOf(trip)
    val parkingRub = if (parkingOn) c.lines.firstOrNull { it.key == "parking" }?.rub ?: parkingSum.rub else null
    val parkingText = parkingRub?.let { parkingTotalText(parkingSum, it) }
    val cd = stringResource(R.string.cd_road_waybill, app.verst.settings.AppPrefs.money(c.totalRub)) + ". " + perPerson +
        (parkingText?.let { ". " + stringResource(R.string.road_footer_parking) + " " + it } ?: "")
    Row(
        Modifier
            .fillMaxWidth()
            .padding(start = 16.dp, end = 16.dp, bottom = 24.dp)
            .height(DesignTokens.size.ctaWaybillH)
            .clip(RoundedCornerShape(DesignTokens.radius.r12))
            .background(C.sign.white)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("road.total")
            .padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // The label spans the row; the per-person line (F3) sits on the amount line, right of it (S-22).
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (fits || tight) {
                    // «ПУТЕВОЙ ЛИСТ ·» + the badge (components §20)
                    Txt(label.substringBefore(" · ") + " · ", T.body.smStrong, C.text.onLightMuted, maxLines = 1)
                    if (fits) {
                        GlyphIcon(Glyph.CHECK, C.text.onLightMuted, 12.dp, Modifier.padding(end = 4.dp))
                        Txt(stringResource(R.string.budget_fit_badge), T.body.smStrong, C.text.onLightMuted, Modifier.testTag("road.fit"), maxLines = 1)
                    } else {
                        Box(Modifier.padding(end = 5.dp).size(8.dp).clip(RoundedCornerShape(4.dp)).background(C.budget.tight))
                        Txt(stringResource(R.string.budget_tight_badge, app.verst.settings.AppPrefs.money(c.totalRub - budget!!)), T.body.smStrong, C.text.onLightMuted, Modifier.testTag("road.tight"), maxLines = 1)
                    }
                } else {
                    Txt(label, T.body.smStrong, if (over) C.paper.inkRed else C.text.onLightMuted, Modifier.testTag(if (over) "road.over" else "road.label"), maxLines = 1)
                }
            }
            Row(verticalAlignment = Alignment.Bottom) {
                Txt(total, T.amount, C.text.onLight, Modifier.testTag("road.total.amount"), maxLines = 1)
                Spacer(Modifier.weight(1f))
                // 5.5 §10.6: with parking the right block (under the label line) says «из них парковки»;
                // the per-person line yields to it
                if (parkingRub != null) FooterParking(parkingRub, parkingSum)
                else Txt(perPerson, T.body.smStrong, C.text.onLightMuted, Modifier.padding(start = 8.dp), maxLines = 1, align = TextAlign.End)
            }
        }
        Spacer(Modifier.width(12.dp))
        Icon(R.drawable.ic_arrow_right, C.text.onLight, 22.dp)
    }
}


private val TightLines = LineHeightStyle(LineHeightStyle.Alignment.Center, LineHeightStyle.Trim.Both)
