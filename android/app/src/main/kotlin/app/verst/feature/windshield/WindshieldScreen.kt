package app.verst.feature.windshield

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import kotlinx.coroutines.withTimeoutOrNull
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import app.verst.core.ui.components.LocalReducedMotion
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInParent
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.foundation.combinedClickable
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.SavedTripDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.ui.R
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.PlaceholderPlate
import app.verst.core.ui.components.StartButton
import app.verst.core.ui.components.StartSize
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.WindshieldScene
import app.verst.core.ui.components.arrowFor
import app.verst.core.ui.components.dashboardSurface
import app.verst.core.ui.components.naviPanel
import app.verst.core.ui.components.overheadPlate
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.crewShort
import app.verst.nav.WindshieldData
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

private val DashHeight = 324.dp
private const val SavedTripsWarn = app.verst.core.model.SavedTrips.WARN_FROM

/** Everything the Windshield draws (stateless; the caller maps `VerstFlow` into it). */
data class WindshieldUi(
    val origin: String,
    val data: WindshieldData,
    val selected: Int,
    val adults: Int,
    val children: Int,
    val dog: Boolean,
    /** Saved trips in D-1 order; the «Мои поездки» plate shows only when non-empty (W-27). */
    val trips: List<SavedTripDto> = emptyList(),
    val tripsSheet: Boolean = false,
    /** OI-39: the origin in the genitive from the engine («Москвы»); the nominative until it arrives. */
    val originGen: String = origin,
)

/** «Мои поездки» plate and the D-1 sheet. */
interface TripsActions {
    fun open()
    fun close()
    fun pick(id: String)
    fun delete(id: String)
}

private val NoTrips = object : TripsActions {
    override fun open() {}
    override fun close() {}
    override fun pick(id: String) {}
    override fun delete(id: String) {}
}

/** 5.1 Windshield, simplified: ready routes on the overhead sign, the navigator entry, the start button. */
@Composable
fun WindshieldScreen(
    ui: WindshieldUi,
    onSelect: (Int) -> Unit,
    onStart: () -> Unit,
    onNavigator: () -> Unit,
    onRetry: () -> Unit,
    trips: TripsActions = NoTrips,
    onDebug: () -> Unit = {},
) {
    ScreenRoot(C.dash.base, statusBar = C.interior.liner) {
        BoxWithConstraints(Modifier.matchParentSize()) {
            val sceneH = maxHeight - DashHeight + 20.dp
            var signBottom by remember { mutableStateOf(290f) }
            WindshieldScene(sceneH, gantry = true, gantryTop = minOf(286f, signBottom - 4f), overlay = ui.tripsSheet)
            Mirror(crewShort(ui.adults, ui.children, ui.dog), ui.adults, ui.children, ui.dog, Modifier.align(Alignment.TopCenter).padding(top = 8.dp))
            val density = androidx.compose.ui.platform.LocalDensity.current
            Sign(
                ui, onSelect, onRetry,
                Modifier.padding(start = 20.dp, end = 20.dp, top = 84.dp).fillMaxWidth()
                    .onGloballyPositioned { c -> signBottom = with(density) { (c.positionInParent().y + c.size.height).toDp().value } },
            )
            Dashboard(ui, onStart, onNavigator, trips::open, onDebug, Modifier.align(Alignment.BottomCenter))
            if (ui.tripsSheet && ui.trips.isNotEmpty()) TripsSheet(ui.trips, maxHeight, trips)
        }
    }
}

/** D-1 «Мои поездки»: rows with the trip arrow, name, total and meta; tap → Road ahead. */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.TripsSheet(trips: List<SavedTripDto>, windowH: androidx.compose.ui.unit.Dp, a: TripsActions) {
    BottomSheet(stringResource(R.string.trips_title), a::close, "trips", windowH) {
        val n = trips.size
        Txt(
            stringResource(R.string.trips_subtitle, n, pluralStringResource(R.plurals.plural_saved, n)),
            T.body.sm, C.text.secondary, Modifier.padding(bottom = if (n >= SavedTripsWarn) 4.dp else 10.dp),
        )
        if (n >= SavedTripsWarn) Txt(stringResource(R.string.trips_near_limit, n), T.body.sm, C.accent.redText, Modifier.padding(bottom = 10.dp))
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            trips.forEachIndexed { i, t -> TripRow(t, i, { a.delete(t.id) }) { a.pick(t.id) } }
        }
    }
}

@Composable
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
private fun TripRow(t: SavedTripDto, index: Int, onDelete: () -> Unit, onClick: () -> Unit) {
    val deleteLabel = stringResource(R.string.trips_delete_yes)
    val daysWord = pluralStringResource(R.plurals.plural_day, t.days)
    val date = tripDates(t.startAt, t.days)
    val meta = stringResource(R.string.trips_row_meta, date, t.days, daysWord, crewShort(t.adults, t.children, t.dog))
    val total = RuFormat.thousands(t.totalRub)
    val cd = stringResource(R.string.cd_trips_row, t.title, date, t.days, daysWord, total)
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 64.dp)
            .clip(RoundedCornerShape(DesignTokens.radius.r10))
            .background(C.dash.controlAlt)
            // D-1: tap opens, long-press (or the TalkBack action «Удалить») asks to delete.
            .combinedClickable(role = Role.Button, onLongClick = onDelete, onClick = onClick)
            .semantics(mergeDescendants = true) {
                contentDescription = cd
                customActions = listOf(CustomAccessibilityAction(deleteLabel) { onDelete(); true })
            }
            .testTag("trips.row.$index")
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(32.dp).clip(RoundedCornerShape(DesignTokens.radius.r4)).background(C.sign.blue), contentAlignment = Alignment.Center) {
            Icon(arrowFor(t.bearing8), C.sign.white, 18.dp)
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Txt(t.title, T.title.sm, C.text.primary, Modifier.weight(1f), maxLines = 1)
                Txt(stringResource(R.string.common_estimate_rub, total), T.body.mdStrong, C.accent.yellow, Modifier.padding(start = 8.dp), maxLines = 1)
            }
            Txt(meta, T.body.sm, C.text.secondary, maxLines = 1)
        }
    }
}

/** 5.1 §4.4 «Мои поездки · N» plate (bookmark 16, outline, 36 high, 44 touch). */
@Composable
private fun TripsPlate(count: Int, onClick: () -> Unit) {
    val cd = stringResource(R.string.cd_windshield_my_trips, count, pluralStringResource(R.plurals.plural_saved, count))
    Box(
        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = cd }.testTag("windshield.trips"),
        contentAlignment = Alignment.CenterStart,
    ) {
        Row(
            Modifier.height(36.dp).border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r8)).padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            GlyphIcon(Glyph.BOOKMARK, C.text.secondary, 16.dp)
            Txt(stringResource(R.string.windshield_my_trips, count), T.body.mdStrong, C.text.secondary, maxLines = 1)
        }
    }
}

/**
 * components §3.1 `Mirror.Small` (S-07, S-08): stem + body as one Canvas 150 × 56 (origin = screen (120, 8)),
 * glass reflecting sky (`sky.band2`) and ground, crew silhouettes as cut-outs in `mirror.glass` at the slot
 * centres 154 / 193 / 230 (adults from the outer slots inward, children in the rest), the dog at the right,
 * glare; the crew caption below.
 */
@Composable
private fun Mirror(caption: String, adults: Int, children: Int, dog: Boolean, modifier: Modifier) {
    // motion.mirrorSway: ±1.5° about the stem top, 2000 ms each way (0° under reduced motion).
    val sway = if (LocalReducedMotion.current) 0f else rememberInfiniteTransition(label = "sway").animateFloat(
        DesignTokens.motion.mirrorSway.fromDeg, DesignTokens.motion.mirrorSway.toDeg,
        infiniteRepeatable(tween(DesignTokens.motion.mirrorSway.durationMs / 2, easing = DesignTokens.motion.mirrorSway.easing), RepeatMode.Reverse),
        label = "swayDeg",
    ).value
    Column(
        modifier.graphicsLayer { rotationZ = sway; transformOrigin = TransformOrigin(0.5f, 0f) }.semantics(mergeDescendants = true) {},
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Canvas(Modifier.size(150.dp, 54.dp)) {
            val d = 1.dp.toPx()
            drawRect(C.dash.controlAlt, Offset(71 * d, 0f), Size(8 * d, 10 * d))
            drawRoundRect(C.dash.controlAlt, Offset(0f, 10 * d), Size(150 * d, 44 * d), CornerRadius(22 * d))
            val glass = Path().apply { addRoundRect(RoundRect(3 * d, 13 * d, 147 * d, 51 * d, CornerRadius(19 * d))) }
            clipPath(glass) {
                drawRect(C.mirror.glass, Offset(3 * d, 13 * d), Size(144 * d, 38 * d))
                drawRect(C.sky.band2, Offset(3 * d, 13 * d), Size(144 * d, 20 * d))
                drawRect(C.scene.groundDay, Offset(3 * d, 33 * d), Size(144 * d, 18 * d))
                val slotsX = listOf(34f, 73f, 110f)
                val nA = (adults - 1).coerceIn(0, 3)
                val adultSlots = listOf(0, 2, 1).take(nA)
                val childSlots = (0..2).filter { it !in adultSlots }.take(children.coerceAtMost(3 - nA))
                for (i in adultSlots) {
                    val cx = slotsX[i]
                    drawCircle(C.mirror.glass, 6 * d, Offset(cx * d, 31 * d))
                    drawRoundRectTop(C.mirror.glass, (cx - 12) * d, 38 * d, 24 * d, 12 * d, 10 * d)
                }
                for (i in childSlots) {
                    val cx = slotsX[i]
                    drawCircle(C.mirror.glass, 4.5f * d, Offset(cx * d, 35.5f * d))
                    drawRoundRectTop(C.mirror.glass, (cx - 9) * d, 41 * d, 18 * d, 10 * d, 8 * d)
                }
                if (dog) {
                    for ((x, deg) in listOf(126f to 20f, 134f to -20f)) {
                        rotate(deg, Offset((x + 2) * d, 33 * d)) { drawRoundRect(C.mirror.glass, Offset(x * d, 30 * d), Size(4 * d, 6 * d), CornerRadius(2 * d)) }
                    }
                    drawPath(
                        Path().apply {
                            addRoundRect(
                                RoundRect(
                                    125 * d, 33 * d, 139 * d, 45 * d, topLeftCornerRadius = CornerRadius(6 * d), topRightCornerRadius = CornerRadius(6 * d),
                                    bottomRightCornerRadius = CornerRadius(4 * d), bottomLeftCornerRadius = CornerRadius(4 * d),
                                ),
                            )
                        },
                        C.mirror.glass,
                    )
                }
                rotate(25f, Offset(13 * d, 38 * d)) { drawRect(C.mirror.glare, Offset(-17 * d, 3 * d), Size(60 * d, 70 * d)) }
            }
        }
        Txt(caption, T.caption.strong, C.mirror.label, Modifier.padding(top = 3.dp), maxLines = 1)
    }
}

/** A rect with rounded top corners only (silhouette bodies). */
private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawRoundRectTop(color: androidx.compose.ui.graphics.Color, x: Float, y: Float, w: Float, h: Float, r: Float) {
    drawPath(
        Path().apply { addRoundRect(RoundRect(x, y, x + w, y + h, topLeftCornerRadius = CornerRadius(r), topRightCornerRadius = CornerRadius(r))) },
        color,
    )
}

@Composable
private fun Sign(ui: WindshieldUi, onSelect: (Int) -> Unit, onRetry: () -> Unit, modifier: Modifier) {
    val loadingCd = stringResource(R.string.windshield_loading_cd)
    Column(modifier.overheadPlate().padding(start = 12.dp, end = 12.dp, top = 12.dp, bottom = 10.dp)) {
        Row(Modifier.fillMaxWidth().padding(start = 6.dp, end = 6.dp, bottom = 4.dp)) {
            Txt(
                stringResource(R.string.windshield_sign_header, ui.originGen.uppercase()),
                T.label.md, C.sign.blueText, Modifier.weight(1f).semantics { heading() }, maxLines = 1,
            )
            if (ui.data is WindshieldData.Routes) Txt(stringResource(R.string.windshield_sign_km), T.label.md, C.sign.blueText)
        }
        when (val d = ui.data) {
            is WindshieldData.Loading -> Column(Modifier.semantics(mergeDescendants = true) { contentDescription = loadingCd }) {
                repeat(4) {
                    Row(Modifier.fillMaxWidth().height(44.dp).padding(horizontal = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        PlaceholderPlate(22.dp, 22.dp, C.sign.plate)
                        Spacer(Modifier.width(10.dp))
                        PlaceholderPlate(150.dp, 14.dp, C.sign.plate)
                        Spacer(Modifier.weight(1f))
                        PlaceholderPlate(30.dp, 14.dp, C.sign.plate)
                    }
                }
            }
            is WindshieldData.Routes -> {
                d.routes.take(4).forEachIndexed { i, r -> RouteRow(r, i == ui.selected, i) { onSelect(i) } }
                val more = d.routes.size - 4
                if (more > 0) {
                    Txt(
                        stringResource(R.string.windshield_sign_more, more, pluralStringResource(R.plurals.plural_route, more)),
                        T.caption.md, C.sign.blueText, Modifier.padding(start = 6.dp, top = 3.dp),
                    )
                }
            }
            is WindshieldData.NoRoutes -> Column(Modifier.padding(horizontal = 6.dp, vertical = 10.dp)) {
                Txt(stringResource(R.string.windshield_no_routes_sign), T.sign.lg, C.sign.white)
                Txt(stringResource(R.string.windshield_no_routes_footer), T.caption.md, C.sign.blueText, Modifier.padding(top = 8.dp))
            }
            is WindshieldData.Failed -> Column(Modifier.padding(horizontal = 6.dp, vertical = 6.dp)) {
                if (d.engineFailed) {
                    Txt(stringResource(R.string.engine_failed_title), T.sign.lg, C.sign.white)
                    Txt(stringResource(R.string.engine_failed_text), T.caption.md, C.sign.blueText, Modifier.padding(top = 4.dp))
                } else {
                    Txt(stringResource(R.string.windshield_error_sign), T.sign.lg, C.sign.white)
                }
                Row(
                    Modifier
                        .padding(top = 6.dp)
                        .height(44.dp)
                        .clip(RoundedCornerShape(DesignTokens.radius.r4))
                        .clickable(role = Role.Button, onClick = onRetry)
                        .testTag("windshield.retry")
                        .padding(end = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Icon(R.drawable.ic_arrow_right, C.accent.yellow, 22.dp)
                    Txt(stringResource(R.string.common_retry), T.sign.lg, C.accent.yellow)
                }
            }
        }
    }
}

@Composable
private fun RouteRow(r: ReadyRouteDto, selected: Boolean, index: Int, onClick: () -> Unit) {
    val fg = if (selected) C.accent.yellow else C.sign.white
    Row(
        Modifier
            .fillMaxWidth()
            .height(44.dp)
            .clip(RoundedCornerShape(DesignTokens.radius.r4))
            .background(if (selected) C.sign.blueSelected else C.sign.blue.copy(alpha = 0f))
            .clickable(role = Role.Button, onClick = onClick)
            .testTag("windshield.route.$index")
            .padding(horizontal = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(arrowFor(r.bearing8), fg, 22.dp)
        Spacer(Modifier.width(10.dp))
        Txt(r.title, T.sign.lg, fg, Modifier.weight(1f), maxLines = 1)
        Txt(r.kmSign.toString(), T.sign.lg, fg, align = TextAlign.End)
    }
}

@Composable
private fun Dashboard(ui: WindshieldUi, onStart: () -> Unit, onNavigator: () -> Unit, onTrips: () -> Unit, onDebug: () -> Unit, modifier: Modifier) {
    val routes = (ui.data as? WindshieldData.Routes)?.routes
    val selected = routes?.getOrNull(ui.selected)
    Box(modifier.fillMaxWidth().height(DashHeight).dashboardSurface()) {
        NaviEntry(ui.origin, ui.data is WindshieldData.NoRoutes, onNavigator, onDebug, Modifier.padding(start = 18.dp, end = 18.dp, top = 22.dp).fillMaxWidth())
        Row(
            Modifier.align(Alignment.BottomStart).fillMaxWidth().padding(start = 22.dp, end = 20.dp, bottom = 56.dp)
                .height(DesignTokens.size.startMOuter),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // N-02: the column (label / title / meta / 8 / plate) is centred on the start button, even when taller.
            Column(Modifier.weight(1f).padding(end = 14.dp).wrapContentHeight(unbounded = true).semantics(mergeDescendants = true) {}) {
                val (label, title, meta) = when {
                    selected != null -> Triple(stringResource(R.string.windshield_selected_label), selected.title, selected.subtitle)
                    ui.data is WindshieldData.Loading -> Triple(stringResource(R.string.windshield_selected_label), null, null)
                    else -> Triple(
                        stringResource(R.string.windshield_no_routes_label),
                        stringResource(R.string.windshield_no_routes_title),
                        stringResource(R.string.windshield_no_routes_meta),
                    )
                }
                Txt(label, T.label.md, C.text.muted, maxLines = 1)
                if (title != null) Txt(title, T.title.xl, C.text.primary, maxLines = 1) else PlaceholderPlate(160.dp, 20.dp, C.dash.controlAlt, Modifier.padding(vertical = 4.dp))
                if (meta != null) Txt(meta, T.body.mdTight, C.text.secondary, Modifier.padding(top = 2.dp), maxLines = 1) else PlaceholderPlate(120.dp, 12.dp, C.dash.controlAlt)
                if (ui.trips.isNotEmpty()) {
                    Spacer(Modifier.height(4.dp)) // 8 dp to the plate box (the 44 dp touch box adds 4)
                    TripsPlate(ui.trips.size, onTrips)
                }
            }
            StartButton(
                StartSize.M, stringResource(R.string.common_go), enabled = selected != null,
                cd = if (selected != null) stringResource(R.string.cd_start_route, selected.title) else stringResource(R.string.cd_start_disabled_destination),
                onClick = onStart, modifier = Modifier.testTag("windshield.start"),
            )
        }
    }
}

@Composable
private fun NaviEntry(origin: String, highlight: Boolean, onClick: () -> Unit, onDebug: () -> Unit, modifier: Modifier) {
    val cd = stringResource(R.string.cd_windshield_navi)
    Column(
        modifier
            .naviPanel()
            .clip(RoundedCornerShape(16.dp))
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("windshield.navi")
            .padding(start = 18.dp, end = 18.dp, top = 16.dp, bottom = 14.dp),
    ) {
        Row(Modifier.fillMaxWidth()) {
            // DEV-127 hidden entry: a 2 s long-press on «НАВИГАТОР» opens the debug panel.
            Txt(
                stringResource(R.string.windshield_navi_label), T.label.md, C.navi.label,
                Modifier.weight(1f).testTag("windshield.debug").pointerInput(Unit) {
                    detectTapGestures(onPress = {
                        val released = withTimeoutOrNull(2_000) { tryAwaitRelease() }
                        if (released == null) onDebug()
                    })
                },
            )
            Txt(stringResource(R.string.windshield_you_are, origin.uppercase()), T.label.md, C.navi.label)
        }
        Row(
            Modifier
                .padding(top = 12.dp)
                .fillMaxWidth()
                .height(48.dp)
                .clip(RoundedCornerShape(DesignTokens.radius.r10))
                .background(C.navi.field)
                // 5.1 §4.7 (S-09): no routes nearby → the field is the way on, yellow 2 dp border (static frame).
                .border(
                    if (highlight) DesignTokens.stroke.w2 else DesignTokens.stroke.w1,
                    if (highlight) C.accent.yellow else C.navi.fieldBorder,
                    RoundedCornerShape(DesignTokens.radius.r10),
                )
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            SearchGlyph()
            Spacer(Modifier.width(10.dp))
            Column {
                Txt(stringResource(R.string.windshield_field_title), T.field.md, C.text.primary, maxLines = 1)
                Txt(stringResource(R.string.windshield_field_sub), T.body.sm, C.navi.labelSecondary, maxLines = 1)
            }
        }
        Txt(stringResource(R.string.windshield_hint), T.body.sm, C.navi.labelSecondary, Modifier.padding(top = 8.dp), maxLines = 1)
    }
}

/** Search icon (components §17.3): circle + handle, `stroke.icon.ui`, yellow. */
@Composable
fun SearchGlyph(modifier: Modifier = Modifier) {
    Box(
        modifier.size(18.dp).drawBehind {
            val sw = DesignTokens.stroke.icon.ui.toPx()
            val r = size.width * 0.32f
            val c = Offset(size.width * 0.42f, size.height * 0.42f)
            drawCircle(C.accent.yellow, r, c, style = Stroke(sw))
            drawLine(C.accent.yellow, Offset(c.x + r * 0.75f, c.y + r * 0.75f), Offset(size.width * 0.92f, size.height * 0.92f), sw)
        },
    )
}


/** N-03 / D-1 dates: «31 октября», «7–9 ноября», «30 октября – 2 ноября» (+ year when not this year). */
@Composable
fun tripDates(startAt: String?, days: Int): String {
    val start = startAt?.takeIf { it.length >= 10 }?.let { runCatching { java.time.LocalDate.parse(it.substring(0, 10)) }.getOrNull() } ?: return ""
    val end = start.plusDays((days - 1).coerceAtLeast(0).toLong())
    val text = when {
        end == start -> stringResource(R.string.common_date_day, start.dayOfMonth.toString(), monthGen(start.monthValue))
        end.monthValue == start.monthValue -> stringResource(R.string.common_date_range_month, start.dayOfMonth.toString(), end.dayOfMonth.toString(), monthGen(end.monthValue))
        else -> stringResource(R.string.common_date_range, start.dayOfMonth.toString(), monthGen(start.monthValue), end.dayOfMonth.toString(), monthGen(end.monthValue))
    }
    return if (end.year != java.time.LocalDate.now().year) stringResource(R.string.common_date_with_year, text, end.year.toString()) else text
}

@Composable
private fun monthGen(m: Int): String = stringResource(
    when (m) {
        1 -> R.string.common_month_gen_01
        2 -> R.string.common_month_gen_02
        3 -> R.string.common_month_gen_03
        4 -> R.string.common_month_gen_04
        5 -> R.string.common_month_gen_05
        6 -> R.string.common_month_gen_06
        7 -> R.string.common_month_gen_07
        8 -> R.string.common_month_gen_08
        9 -> R.string.common_month_gen_09
        10 -> R.string.common_month_gen_10
        11 -> R.string.common_month_gen_11
        else -> R.string.common_month_gen_12
    },
)
