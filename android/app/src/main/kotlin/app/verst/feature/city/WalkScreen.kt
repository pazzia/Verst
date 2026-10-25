package app.verst.feature.city

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.HandoffDto
import app.verst.core.model.dto.WalkRouteDto
import app.verst.core.model.dto.WalkStopDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.InfoChip
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.RoadSign
import androidx.compose.foundation.focusable
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.WalkerIcon
import app.verst.core.ui.components.overheadPlate
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.card.CardActions
import app.verst.feature.card.CardSheet
import app.verst.feature.card.CardUi
import app.verst.feature.common.IconButton44
import app.verst.feature.common.PlateToast
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.toastText
import app.verst.nav.HandoffTarget
import app.verst.nav.Toast
import kotlin.math.roundToInt
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeoutOrNull
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

data class WalkUi(
    val walk: WalkRouteDto,
    val handoff: HandoffDto?,
    val target: HandoffTarget,
    val saved: Boolean,
    val building: Boolean,
    val card: CardUi? = null,
    val toast: Toast? = null,
    val focusId: String? = null,
    val focusSeq: Int = 0,
)

interface WalkActions {
    fun back()
    fun save()
    fun share()
    fun stop(s: WalkStopDto)
    fun handoff(part: Int)
    fun other()
    fun card(): CardActions
    fun focusShown() = Unit
}

/** 5.11 «Прогулка»: 5.5 with the city strip, the walking column, the walk hand-off and the cost plate. */
@Composable
fun WalkScreen(ui: WalkUi, a: WalkActions) {
    val w = ui.walk
    val scroll = rememberScrollState()
    val rows = remember(w.id) { mutableStateMapOf<String, Int>() }
    var content by remember { mutableStateOf<LayoutCoordinates?>(null) }
    val requesters = remember(w.id) { mutableMapOf<String, FocusRequester>() }
    var highlight by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(ui.focusSeq) {
        val id = ui.focusId ?: return@LaunchedEffect
        val y = withTimeoutOrNull(2_000) { snapshotFlow { rows[id] }.filterNotNull().first() } ?: return@LaunchedEffect
        if (y < scroll.value || y > scroll.value + 400) scroll.scrollTo((y - 120).coerceAtLeast(0))
        // 5.9 §5: TalkBack focus back to the row; returnFlash held 400 ms, then an 800 ms fade (S3-QA P1-07)
        androidx.compose.runtime.withFrameNanos { }
        runCatching { requesters[id]?.requestFocus() }
        val m = DesignTokens.motion.returnToItem
        highlight = id
        delay(m.holdMs.toLong())
        highlight = null
        delay((m.highlightMs - m.holdMs).toLong())
        a.focusShown()
    }
    ScreenRoot(C.dash.raised, statusBar = C.city.sky) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val windowH = maxHeight
            Column(Modifier.fillMaxSize()) {
                Box(Modifier.fillMaxWidth().height(150.dp)) {
                    CityScene(Modifier.fillMaxWidth().height(132.dp), crop = 132.dp)
                    Box(Modifier.fillMaxWidth().padding(top = 130.dp).height(2.dp).background(C.city.curb))
                    val back = stringResource(R.string.city_title)
                    BackLink(back, C.mirror.label, stringResource(R.string.cd_back, back), a::back, Modifier.padding(start = 12.dp, top = 10.dp).testTag("walk.back"))
                    Row(Modifier.align(Alignment.TopEnd).padding(top = 6.dp, end = 12.dp)) {
                        IconButton44(
                            Glyph.BOOKMARK, if (ui.saved) C.accent.yellow else C.mirror.label,
                            stringResource(if (ui.saved) R.string.cd_road_saved else R.string.cd_road_save), "walk.save", filled = ui.saved, onClick = a::save,
                        )
                        IconButton44(Glyph.SHARE, C.mirror.label, stringResource(R.string.cd_road_share), "walk.share", onClick = a::share)
                    }
                    WalkTitleSign(w, Modifier.padding(start = 20.dp, end = 20.dp, top = 56.dp).fillMaxWidth())
                }
                Column(
                    Modifier.weight(1f).fillMaxWidth().verticalScroll(scroll).testTag("walk.list").onGloballyPositioned { content = it },
                ) {
                    Intro(ui, a)
                    Column(Modifier.fillMaxWidth().walkColumn()) {
                        val start = RuFormat.clock(w.startAt) ?: ""
                        val finish = RuFormat.clock(w.endAt) ?: ""
                        Txt(
                            stringResource(if (w.startsTomorrow()) R.string.walk_header_tomorrow else R.string.walk_header, start, finish), T.title.sm, C.accent.yellow,
                            Modifier.padding(start = 72.dp, end = 16.dp, bottom = 10.dp).semantics { heading() },
                        )
                        EndRow(stringResource(R.string.walk_start_row), w.start.label ?: w.townName ?: "", start)
                        w.stops.forEach { s ->
                            WalkStopRow(s, w.people, s.id == highlight, requesters.getOrPut(s.id) { FocusRequester() }, { content }, { y -> if (rows[s.id] != y) rows[s.id] = y }) { a.stop(s) }
                        }
                        val fin = w.finish
                        if (fin != null) EndRow(stringResource(R.string.walk_finish_row), fin.label ?: "", finish)
                        Spacer(Modifier.height(16.dp))
                    }
                    Box(Modifier.padding(horizontal = 20.dp)) {
                        WideButton(stringResource(R.string.walk_other), "walk.other", enabled = !ui.building, onClick = a::other, height = 56.dp)
                    }
                    Spacer(Modifier.height(24.dp))
                }
                Footer(w)
            }
            val t = ui.toast
            if (t != null) PlateToast(toastText(t), bottom = 24.dp + DesignTokens.size.ctaWaybillH + 16.dp)
            val c = ui.card
            if (c != null) CardSheet(c, windowH, a.card())
        }
    }
}

@Composable
private fun Intro(ui: WalkUi, a: WalkActions) {
    val w = ui.walk
    Column(Modifier.padding(start = 20.dp, end = 20.dp, bottom = 18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Txt(stringResource(R.string.walk_heading), T.display, C.text.primary, Modifier.semantics { heading() })
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            // S3-QA2: half hours with the decimal comma («5,5 ч»), whole hours without «,0»
            InfoChip(stringResource(R.string.walk_chip_duration_text, hours(w.durationMin)))
            InfoChip(stringResource(R.string.walk_chip_km, km(w.walkKm)))
            if (w.returnToStart) InfoChip(stringResource(R.string.walk_chip_back))
            if (w.adultOnly) {
                Box(
                    Modifier.clip(RoundedCornerShape(DesignTokens.radius.r12)).border(DesignTokens.stroke.w1, C.accent.yellow, RoundedCornerShape(DesignTokens.radius.r12))
                        .padding(horizontal = 10.dp, vertical = 4.dp),
                ) { Txt(stringResource(R.string.city_badge_18), T.body.smStrong, C.text.primary) }
            }
        }
        Txt(stringResource(R.string.walk_approx), T.body.sm, C.text.muted)
        if (w.shorterThanAsked) {
            // «places» → the deck sentence; another reason (budget) → the engine's own sentence
            val sh = w.shorter
            val engineText = sh?.messageRu?.takeIf { sh.reason != "places" }
            val text = engineText
                ?: stringResource(R.string.walk_shorter, hours(sh?.actualMin ?: w.durationMin), hours(sh?.requestedMin ?: w.requestedMin ?: 0))
            Txt(text, T.body.sm, C.text.muted, Modifier.testTag("walk.shorter"))
        }
        // L3a: the walk hand-off, one button per part when the engine split the walk
        val parts = ui.handoff?.parts.orEmpty()
        val label = if (ui.target == HandoffTarget.Maps || ui.target == HandoffTarget.MapsDryRun) stringResource(R.string.handoff_maps_walk) else stringResource(R.string.handoff_web)
        if (parts.size > 1) {
            parts.forEach { p ->
                WideButton("$label · " + stringResource(R.string.handoff_part, p.index, parts.size), "walk.handoff.${p.index}", walker = true, onClick = { a.handoff(p.index) })
            }
        } else {
            WideButton(label, "walk.handoff", walker = true, enabled = true, onClick = { a.handoff(1) })
        }
        val note = w.responsibleNoteRu
        if (note != null) {
            // L4: the responsible plate, first and not dismissible (fixed copy)
            Row(
                Modifier.fillMaxWidth().border(DesignTokens.stroke.w1, C.accent.yellow, RoundedCornerShape(DesignTokens.radius.r10))
                    .padding(horizontal = 12.dp, vertical = 10.dp).testTag("walk.responsible"),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(Modifier.size(22.dp).clip(CircleShape).background(C.sign.white), contentAlignment = Alignment.Center) {
                    Txt(stringResource(R.string.city_badge_18), T.caption.bold, C.text.onLight)
                }
                Txt(stringResource(R.string.walk_responsible), T.body.md, C.text.primary)
            }
        }
        for (warn in w.warnings) {
            val m = warn.messageRu ?: continue
            if (warn.code == "SHORTER_THAN_ASKED") continue // said once, by the note under the ±15 % line (5.11 §9)
            if (warn.code == "HOURS_UNVERIFIED") {
                // S3-QA P2-08: only when a stop really has default hours, as a muted line (not a plate)
                if (w.stops.any { !it.hoursVerified && it.poiId != null }) Txt(m, T.body.sm, C.text.muted, Modifier.testTag("walk.hours"))
                continue
            }
            Box(Modifier.fillMaxWidth().border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r10)).padding(horizontal = 12.dp, vertical = 10.dp)) {
                Txt(m, T.body.md, C.text.secondary)
            }
        }
    }
}

/** Hours to the nearest half: «4», «5,5» (the chip `walk_chip_duration_text` and the `walk_shorter` note agree). */
private fun hours(min: Int): String {
    val halves = (min / 30.0).roundToInt()
    return if (halves % 2 == 0) (halves / 2).toString() else "${halves / 2},5"
}

/** One decimal below 10 km without a trailing zero («6», «5,8»); whole km from 10 (S3-QA P2-01). */
private fun km(v: Double): String {
    if (v >= 10) return v.roundToInt().toString()
    val tenths = (v * 10).roundToInt()
    return if (tenths % 10 == 0) (tenths / 10).toString() else "${tenths / 10},${tenths % 10}"
}

@Composable
private fun distance(km: Double): String =
    if (km < 1.0) stringResource(R.string.walk_distance_m, (km * 1000 / 50).roundToInt() * 50) else stringResource(R.string.common_km, km(km))

/** components §22 walk button / §2 `SecondaryButton`. */
@Composable
private fun WideButton(text: String, tag: String, walker: Boolean = false, enabled: Boolean = true, height: Dp = 48.dp, onClick: () -> Unit) {
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    Row(
        Modifier.fillMaxWidth().height(height).clip(shape).background(C.dash.control).border(DesignTokens.stroke.w1, C.dash.outline, shape)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick).testTag(tag).padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        if (walker) {
            WalkerIcon(C.accent.yellow, 18.dp)
            Spacer(Modifier.width(8.dp))
        }
        Txt(text, T.button.md, if (enabled) C.text.primary else C.text.disabled, maxLines = 1)
    }
}

/** components §21 `WalkTitleSign`: the pedestrian-zone pictogram, the engine title up to 2 lines, «≈ 5,8 км». */
@Composable
private fun WalkTitleSign(w: WalkRouteDto, modifier: Modifier) {
    val km = km(w.walkKm)
    val kmText = stringResource(R.string.common_km_approx, km)
    Row(
        modifier.heightIn(min = 49.dp).overheadPlate(outer = 3.dp, radius = 7.dp, innerRadius = 5.dp)
            .semantics(mergeDescendants = true) { heading(); contentDescription = "${w.titleRu}, $kmText" }
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(28.dp).clip(RoundedCornerShape(3.dp)).background(C.sign.white), contentAlignment = Alignment.Center) {
            WalkerIcon(C.text.onLight, 22.dp)
        }
        Spacer(Modifier.width(8.dp))
        Txt(w.titleRu, T.sign.xlTight, C.sign.white, Modifier.weight(1f).testTag("walk.title"), maxLines = 2)
        Txt(kmText, T.sign.xlTight, C.sign.white, Modifier.padding(start = 8.dp), maxLines = 1)
    }
}

/** components §21 `WalkColumn`: pavement x 14–60, kerbs, joints every 24 dp, a centre joint. */
private fun Modifier.walkColumn(): Modifier = drawBehind {
    val dp = 1.dp.toPx()
    drawRect(C.city.sidewalk, Offset(14 * dp, 0f), Size(46 * dp, size.height))
    drawRect(C.city.curb, Offset(14 * dp, 0f), Size(2 * dp, size.height))
    drawRect(C.city.curb, Offset(58 * dp, 0f), Size(2 * dp, size.height))
    drawRect(C.city.joint, Offset(36.5f * dp, 0f), Size(1 * dp, size.height))
    var y = 0f
    while (y < size.height) {
        drawRect(C.city.joint, Offset(16 * dp, y), Size(42 * dp, 1 * dp))
        y += 24 * dp
    }
}

@Composable
private fun EndRow(kind: String, name: String, time: String) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 12.dp, end = 16.dp).semantics(mergeDescendants = true) {}) {
        Box(Modifier.padding(start = 72.dp).widthIn(min = 68.dp), contentAlignment = Alignment.TopCenter) { RoadSign("city", name.substringBefore(","), emptyList()) }
        Column(Modifier.weight(1f).padding(start = 4.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Txt(kind, T.body.sm, C.text.muted, Modifier.weight(1f))
                Txt(time, T.body.sm, C.text.muted, align = TextAlign.End)
            }
            Txt(name, T.title.md, C.text.primary, maxLines = 2)
        }
    }
}

@Composable
private fun WalkStopRow(s: WalkStopDto, people: Int, focused: Boolean, focusRequester: FocusRequester, content: () -> LayoutCoordinates?, onPlaced: (Int) -> Unit, onTap: () -> Unit) {
    val line = stringResource(R.string.walk_next, distance(s.walkKmFromPrev), s.walkMinFromPrev)
    val time = RuFormat.clock(s.arriveAt) ?: ""
    val cost = if (s.costRub > 0) stringResource(R.string.walk_footer_total, RuFormat.thousands(s.costRub)) else null
    val cd = listOfNotNull(line, time, s.nameRu, s.noteRu, cost).joinToString(", ")
    val tap by rememberUpdatedState(onTap)
    val reduced = LocalReducedMotion.current
    val m = DesignTokens.motion.returnToItem
    val glow by androidx.compose.animation.core.animateFloatAsState(
        if (focused) 1f else 0f,
        if (reduced || focused) androidx.compose.animation.core.snap() else androidx.compose.animation.core.tween(m.highlightMs - m.holdMs, easing = m.easing),
        label = "focus",
    )
    Row(
        Modifier.fillMaxWidth()
            .onGloballyPositioned { c -> content()?.let { root -> if (root.isAttached && c.isAttached) onPlaced(root.localPositionOf(c, Offset.Zero).y.roundToInt()) } }
            .drawBehind { if (glow > 0f) drawRect(C.overlay.returnFlash.copy(alpha = C.overlay.returnFlash.alpha * glow)) }
            .then(if (s.tappable) Modifier.pointerInput(s.id) { detectTapGestures(onTap = { tap() }) } else Modifier)
            .padding(top = 8.dp, bottom = 12.dp, end = 16.dp)
            .semantics(mergeDescendants = true) {
                contentDescription = cd
                if (s.tappable) onClick { onTap(); true }
            }
            .focusRequester(focusRequester)
            .focusable()
            .testTag("walk.stop.${s.id}"),
    ) {
        Box(Modifier.padding(start = 72.dp).widthIn(min = 68.dp), contentAlignment = Alignment.TopCenter) {
            if (s.isBar) BarSign(s.kind) else RoadSign("tourist", s.nameRu, listOf(s.kind))
        }
        Column(Modifier.weight(1f).padding(start = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Txt(line, T.body.sm, C.text.muted, Modifier.weight(1f), maxLines = 1)
                Txt(time, T.body.sm, C.text.muted, align = TextAlign.End)
            }
            Txt(s.nameRu, T.title.md, C.text.primary, maxLines = 2)
            s.noteRu?.takeIf { it.isNotBlank() }?.let { Txt(it, T.body.md, C.text.note) }
            if (cost != null) Txt(cost, T.body.mdStrong, C.accent.yellow)
        }
    }
}

/** components §21 bar sign: the `service` look with `glass` (bar, рюмочная) or `mug` (pub, craft). */
@Composable
internal fun BarSign(kind: String) {
    Box(
        Modifier.size(35.dp, 43.dp).clip(RoundedCornerShape(4.dp)).background(C.sign.blue).padding(3.dp)
            .clip(RoundedCornerShape(3.dp)).background(C.sign.white),
        contentAlignment = Alignment.Center,
    ) {
        app.verst.core.ui.components.GlyphIcon(if (kind == "pub" || kind == "craft" || kind == "beer") Glyph.MUG else Glyph.GLASS, C.text.onLight, 22.dp)
    }
}

/** 5.11 footer: a summary plate (not a button) «СКОЛЬКО СТОИТ ПРОГУЛКА · ≈ 2 400 ₽ на всех». */
@Composable
private fun Footer(w: WalkRouteDto) {
    val total = w.cost.totalRub
    val per = (total.toDouble() / w.people).roundToInt().let { ((it + 50) / 100) * 100 }
    Row(
        Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 24.dp).height(DesignTokens.size.ctaWaybillH)
            .clip(RoundedCornerShape(DesignTokens.radius.r12)).background(C.sign.white)
            .semantics(mergeDescendants = true) {}.testTag("walk.total").padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Txt(stringResource(R.string.walk_footer_label), T.body.smStrong, C.text.onLightMuted, maxLines = 1)
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (total <= 0) {
                    // 5.11 §9 (S3-QA P1-03): never «≈ 0 ₽»; no per-person line
                    Txt(stringResource(R.string.walk_footer_free), T.amount, C.text.onLight, Modifier.testTag("walk.free"), maxLines = 1)
                    Spacer(Modifier.weight(1f))
                    Txt(stringResource(R.string.walk_footer_free_sub), T.body.smStrong, C.text.onLightMuted, maxLines = 1)
                } else {
                    Txt(stringResource(R.string.walk_footer_total, RuFormat.thousands(total)), T.amount, C.text.onLight, maxLines = 1)
                    Spacer(Modifier.weight(1f))
                    Txt(stringResource(R.string.walk_footer_per_person, RuFormat.thousands(per)), T.body.smStrong, C.text.onLightMuted, maxLines = 1)
                }
            }
        }
    }
}
