package app.verst.feature.waybill

import androidx.compose.animation.Crossfade
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.keyframes
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.CostLineDto
import app.verst.core.model.dto.TripDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.PlateToast
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.toastText
import app.verst.nav.Toast
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** Everything the Waybill draws (stateless). */
data class WaybillUi(
    val trip: TripDto,
    /** «№ 001»: the saved-trip ordinal (1 when not saved). */
    val number: Int,
    val saved: Boolean,
    val expanded: String?,
    val busy: Boolean = false,
    val monthRu: String? = null,
    val year: String? = null,
    val toast: Toast? = null,
    /** Play the stamp (first opening of this trip); otherwise it shows its final frame (5.6 §3.1). */
    val stamp: Boolean = false,
)

interface WaybillActions {
    fun back()
    fun toggleLine(key: String)
    fun toggleReserve()
    fun save()
    fun share()
}

private val SumCol = 70.dp
private val TotalCol = 150.dp // 100 in the spec for «≈ 30 500»; our value carries «₽» (common_estimate_rub)
private const val NONE = "—"

/**
 * 5.6 Waybill, simplified (DEV-SLICE-2): the paper sheet with the engine's cost lines and formulas, one line
 * expanded at a time, the reserve switch re-costed by the engine (`patch_cost`), issued / left against the
 * budget, the stamp (once per trip), the entry slide and value cross-fades. Not in this slice: the Pro plate and sheet.
 */
@Composable
fun WaybillScreen(ui: WaybillUi, a: WaybillActions) {
    ScreenRoot(C.dash.raised) {
        Column(Modifier.fillMaxSize()) {
            Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 14.dp)) {
                val back = stringResource(R.string.common_back_road)
                BackLink(back, C.text.muted, stringResource(R.string.cd_back, back), a::back, Modifier.padding(top = 8.dp).testTag("waybill.back"))
                Spacer(Modifier.height(18.dp))
                // motion.sheetSlide: 40 dp up + fade in over 600 ms on entry (at rest under reduced motion).
                val reduced = LocalReducedMotion.current
                val slide = remember { Animatable(if (reduced) 1f else 0f) }
                LaunchedEffect(Unit) { if (!reduced) slide.animateTo(1f, tween(DesignTokens.motion.sheetSlide.durationMs, easing = DesignTokens.motion.sheetSlide.easing)) }
                Box(Modifier.graphicsLayer { translationY = DesignTokens.motion.sheetSlide.fromDyDp.toPx() * (1 - slide.value); alpha = slide.value }) {
                    Sheet(ui, a)
                }
                Spacer(Modifier.height(30.dp)) // the stamp hangs 30 dp below the sheet
                Spacer(Modifier.height(16.dp))
            }
            Row(Modifier.fillMaxWidth().padding(start = 14.dp, end = 14.dp, bottom = 20.dp, top = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SaveButton(ui.saved, a::save, Modifier.weight(1f))
                YellowButton(stringResource(R.string.waybill_share), a::share, Modifier.weight(1f).testTag("waybill.share"))
            }
        }
        val t = ui.toast
        if (t != null) PlateToast(toastText(t), bottom = 20.dp + DesignTokens.size.buttonH + 16.dp)
    }
}

@Composable
private fun Sheet(ui: WaybillUi, a: WaybillActions) {
    val trip = ui.trip
    val cost = trip.cost
    Box(Modifier.fillMaxWidth()) {
        Column(
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(DesignTokens.radius.r4))
                .background(C.paper.sheet)
                .testTag("waybill.sheet")
                .padding(start = 16.dp, end = 16.dp, top = 26.dp, bottom = 14.dp),
        ) {
            Header(ui.number)
            FormGrid(trip)
            Spacer(Modifier.height(10.dp))
            Column(Modifier.fillMaxWidth().border(1.5.dp, C.paper.text)) {
                TableHeader()
                cost.lines.filter { it.key != "reserve" }.forEach { line ->
                    CostLine(line, ui.expanded == line.key) { a.toggleLine(line.key) }
                }
                cost.lines.firstOrNull { it.key == "reserve" }?.let { ReserveRow(it, cost.reserveOn, ui.busy, a::toggleReserve) }
                TotalRow(cost.totalRub)
            }
            IssuedLeft(cost.budgetRub, cost.remainingRub, cost.overBudget)
            if (cost.overBudget && cost.budgetRub != null) {
                Txt(stringResource(R.string.waybill_over_hint), T.paper.label, C.paper.text, Modifier.padding(top = 4.dp, end = 100.dp))
            }
            if (ui.monthRu != null && ui.year != null) {
                Txt(
                    stringResource(R.string.waybill_footnote_real, ui.monthRu, ui.year), T.paper.label, C.paper.label,
                    Modifier.padding(top = 6.dp, end = 100.dp),
                )
            }
        }
        Stamp(ui.stamp, Modifier.align(Alignment.BottomEnd).offset(x = (-12).dp, y = 30.dp))
        // Clipboard clip (decorative), centred on the top edge.
        Box(
            Modifier.align(Alignment.TopCenter).offset(y = (-14).dp).size(120.dp, 30.dp)
                .clip(RoundedCornerShape(DesignTokens.radius.r8)).background(C.paper.clip)
                .drawBehind { drawRect(C.paper.clipShadow, Offset(0f, size.height - 3.dp.toPx()), androidx.compose.ui.geometry.Size(size.width, 3.dp.toPx())) }
                .clearAndSetSemantics {},
        )
    }
}

@Composable
private fun Header(number: Int) {
    val no = number.toString().padStart(3, '0')
    Row(
        Modifier.fillMaxWidth()
            .drawBehind { drawRect(C.paper.text, Offset(0f, size.height - 2.dp.toPx()), androidx.compose.ui.geometry.Size(size.width, 2.dp.toPx())) }
            .padding(bottom = 8.dp)
            .semantics(mergeDescendants = true) { heading() },
        verticalAlignment = Alignment.Bottom,
    ) {
        Column(Modifier.weight(1f)) {
            Txt(stringResource(R.string.waybill_form), T.paper.header, C.paper.label, maxLines = 1)
            Txt(stringResource(R.string.waybill_title), T.paper.title, C.paper.text, maxLines = 1)
            Txt(stringResource(R.string.waybill_subtitle), T.paper.sub, C.paper.text, maxLines = 1)
        }
        Row(verticalAlignment = Alignment.Bottom) {
            Txt(stringResource(R.string.waybill_number) + " ", T.paper.label, C.paper.label)
            Txt(no, T.hand.lg, C.paper.ink, Modifier.testTag("waybill.number"))
        }
    }
}

@Composable
private fun FormGrid(trip: TripDto) {
    val crew = trip.input.crew
    val crewParts = buildList {
        add(stringResource(R.string.waybill_crew_adults, crew.adults))
        if (crew.children > 0) add(stringResource(R.string.waybill_crew_children, crew.children))
        if (crew.dog) add(stringResource(R.string.waybill_crew_dog))
    }.joinToString(stringResource(R.string.common_join_comma))
    val mileage = stringResource(R.string.waybill_mileage_value, RuFormat.thousands(trip.km), trip.days, pluralStringResource(R.plurals.plural_day, trip.days))
    Column(Modifier.fillMaxWidth().padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        FormRow(stringResource(R.string.waybill_route), trip.title, "waybill.route")
        FormRow(stringResource(R.string.waybill_crew), crewParts, "waybill.crew")
        FormRow(stringResource(R.string.waybill_mileage), mileage, "waybill.mileage")
    }
}

@Composable
private fun FormRow(label: String, value: String, tag: String) {
    Row(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}, verticalAlignment = Alignment.Bottom) {
        Txt(label, T.paper.label, C.paper.label, Modifier.width(92.dp).padding(bottom = 3.dp), maxLines = 1)
        Txt(value, T.hand.md, C.paper.ink, Modifier.weight(1f).underline(C.paper.lines).testTag(tag))
    }
}

private fun Modifier.underline(color: Color): Modifier = drawBehind {
    drawRect(color, Offset(0f, size.height - 1.dp.toPx()), androidx.compose.ui.geometry.Size(size.width, 1.dp.toPx()))
}

/** A table row: wide cell | 1 dp rule | sum cell (components §11 Table), with a bottom rule. */
@Composable
private fun TableRow(rule: Dp, sumWidth: Dp, modifier: Modifier = Modifier, left: @Composable () -> Unit, right: @Composable () -> Unit) {
    Row(
        modifier.fillMaxWidth().height(IntrinsicSize.Min)
            .drawBehind { drawRect(C.paper.lines.takeIf { rule < 1.5.dp } ?: C.paper.text, Offset(0f, size.height - rule.toPx()), androidx.compose.ui.geometry.Size(size.width, rule.toPx())) },
    ) {
        Box(Modifier.weight(1f).fillMaxHeight(), contentAlignment = Alignment.CenterStart) { left() }
        Box(Modifier.width(1.dp).fillMaxHeight().background(C.paper.text))
        Box(Modifier.width(sumWidth).fillMaxHeight().padding(horizontal = 6.dp), contentAlignment = Alignment.CenterEnd) { right() }
    }
}

@Composable
private fun TableHeader() {
    TableRow(1.5.dp, SumCol, left = {
        Txt(stringResource(R.string.waybill_table_item), T.paper.tableHead, C.paper.label, Modifier.padding(horizontal = 6.dp, vertical = 3.dp))
    }, right = { Txt(stringResource(R.string.waybill_table_rub), T.paper.tableHead, C.paper.label) })
}

/** components §11 `CostLine`: name + chevron, the engine formula in hand, the sum; expands to the breakdown. */
@Composable
private fun CostLine(line: CostLineDto, expanded: Boolean, onClick: () -> Unit) {
    val sum = RuFormat.thousands(line.rub)
    val state = stringResource(if (expanded) R.string.cd_waybill_collapse else R.string.cd_waybill_expand)
    val cd = stringResource(R.string.cd_waybill_line, line.title, sum, line.formula, state)
    Column(
        Modifier.fillMaxWidth().animateContentSize()
            .clickable(enabled = line.breakdown.isNotEmpty(), role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("waybill.line.${line.key}"),
    ) {
        TableRow(1.dp, SumCol, Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin), left = {
            Column(Modifier.padding(horizontal = 6.dp, vertical = 3.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Txt(line.title, T.paper.body, C.paper.text, maxLines = 1)
                    if (line.breakdown.isNotEmpty()) {
                        Spacer(Modifier.width(6.dp))
                        GlyphIcon(Glyph.CHEVRON_DOWN, C.paper.label, 12.dp, Modifier.rotate(if (expanded) 180f else 0f), strokeWidth = 2.5f)
                    }
                }
                Txt(line.formula, T.hand.sm, C.paper.ink, Modifier.testTag("waybill.formula.${line.key}"))
            }
        }, right = { Txt(sum, T.hand.md, C.paper.ink, align = TextAlign.End, maxLines = 1) })
        if (expanded) {
            line.breakdown.forEachIndexed { i, b ->
                val sep = stringResource(R.string.common_join_dot)
                // The engine's breakdown formula ends with «= N ₽», which the ₽ column already shows.
                val text = if (b.formula.isBlank()) b.label else b.label + sep + b.formula.substringBefore(" = ")
                TableRow(if (i == line.breakdown.lastIndex) 1.dp else 0.dp, SumCol, Modifier.defaultMinSize(minHeight = 22.dp).testTag("waybill.breakdown.${line.key}.$i"), left = {
                    Txt(text, T.paper.label, C.paper.text, Modifier.padding(start = 18.dp, end = 6.dp, top = 2.dp, bottom = 2.dp))
                }, right = { Txt(RuFormat.thousands(b.rub), T.hand.sm, C.paper.ink, align = TextAlign.End, maxLines = 1) })
            }
        }
    }
}

/** components §11 `ReserveSwitch`: checkbox (hand check), «Резерв 10%», sub, sum or «—»; a Switch for TalkBack. */
@Composable
private fun ReserveRow(line: CostLineDto, on: Boolean, busy: Boolean, onToggle: () -> Unit) {
    val sum = if (on) RuFormat.thousands(line.rub) else NONE
    val cd = stringResource(R.string.cd_waybill_reserve, if (on) RuFormat.thousands(line.rub) else "0")
    TableRow(
        1.5.dp, SumCol,
        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .toggleable(on, enabled = !busy, role = Role.Switch) { onToggle() }
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("waybill.reserve"),
        left = {
            Row(Modifier.padding(horizontal = 6.dp, vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(18.dp).border(1.5.dp, C.paper.text), contentAlignment = Alignment.Center) {
                    if (on) GlyphIcon(Glyph.CHECK_HAND, C.paper.ink, 18.dp, Modifier.testTag("waybill.reserve.check"))
                }
                Spacer(Modifier.width(8.dp))
                Column {
                    Txt(line.title, T.paper.body, C.paper.text, maxLines = 1)
                    Txt(line.formula, T.paper.label, C.paper.label, maxLines = 2)
                }
            }
        },
        right = { Fade(sum) { Txt(it, T.hand.md, C.paper.ink, align = TextAlign.End, maxLines = 1, modifier = Modifier.testTag("waybill.reserve.sum")) } },
    )
}

@Composable
private fun TotalRow(total: Int) {
    val value = stringResource(R.string.common_estimate_rub, RuFormat.thousands(total))
    val cd = stringResource(R.string.cd_waybill_total, RuFormat.thousands(total))
    TableRow(0.dp, TotalCol, Modifier.semantics(mergeDescendants = true) { heading(); contentDescription = cd }, left = {
        Txt(stringResource(R.string.waybill_total), T.paper.total, C.paper.text, Modifier.padding(6.dp))
    }, right = { Fade(value) { Txt(it, T.hand.xl, C.paper.ink, Modifier.padding(vertical = 4.dp).testTag("waybill.total"), align = TextAlign.End, maxLines = 1) } })
}

@Composable
private fun IssuedLeft(budget: Int?, remaining: Int?, over: Boolean) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Column(Modifier.weight(1f).semantics(mergeDescendants = true) {}) {
            Txt(stringResource(R.string.waybill_issued), T.paper.label, C.paper.label)
            Txt(budget?.let { RuFormat.thousands(it) } ?: NONE, T.hand.md, C.paper.ink, Modifier.fillMaxWidth().underline(C.paper.lines).testTag("waybill.issued"))
        }
        Column(Modifier.weight(1f).semantics(mergeDescendants = true) {}) {
            val isOver = over && budget != null
            Txt(stringResource(if (isOver) R.string.waybill_over else R.string.waybill_left), T.paper.label, C.paper.label)
            val value = when {
                budget == null || remaining == null -> NONE
                isOver -> RuFormat.thousands(kotlin.math.abs(remaining))
                else -> stringResource(R.string.common_estimate_rub, RuFormat.thousands(remaining))
            }
            Fade(value) { Txt(it, T.hand.md, if (isOver) C.paper.inkRed else C.paper.ink, Modifier.fillMaxWidth().underline(C.paper.lines).testTag("waybill.left")) }
        }
    }
}

@Composable
private fun SaveButton(saved: Boolean, onClick: () -> Unit, modifier: Modifier) {
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    Box(
        modifier
            .height(DesignTokens.size.buttonH)
            .clip(shape)
            .background(C.dash.control)
            .border(DesignTokens.stroke.w1, C.dash.outline, shape)
            .clickable(enabled = !saved, role = Role.Button, onClick = onClick)
            .testTag("waybill.save"),
        contentAlignment = Alignment.Center,
    ) {
        Txt(
            stringResource(if (saved) R.string.waybill_saved else R.string.waybill_save), T.button.md,
            if (saved) C.text.secondary else C.text.primary, maxLines = 1, align = TextAlign.Center,
        )
    }
}

/** components §15 `YellowButton`. */
@Composable
private fun YellowButton(text: String, onClick: () -> Unit, modifier: Modifier) {
    Box(
        modifier.height(DesignTokens.size.buttonH).clip(RoundedCornerShape(DesignTokens.radius.r12)).background(C.accent.yellow)
            .clickable(role = Role.Button, onClick = onClick).padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) { Txt(text, T.cta.sm, C.text.onLight, maxLines = 1, align = TextAlign.Center) }
}


/** 5.6 §3: changed handwritten values cross-fade 200 ms (instant under reduced motion). */
@Composable
private fun Fade(value: String, content: @Composable (String) -> Unit) {
    if (LocalReducedMotion.current) content(value) else Crossfade(value, animationSpec = tween(200, easing = DesignTokens.motion.easing.standard), label = "value") { content(it) }
}

/**
 * components §11.1 stamp: 94 dp circle, ring 3 + inner ring 1, «ВЕРСТА / В ПУТЬ / ГОТОВЫ», rotated −14°, α 0.85.
 * `motion.stamp` once per trip: after 1000 ms, scale 2.4 → 0.92 (300 ms) → 1 (500 ms), α 0 → 0.9 → 0.85.
 */
@Composable
private fun Stamp(play: Boolean, modifier: Modifier) {
    val m = DesignTokens.motion.stamp
    val reduced = LocalReducedMotion.current
    val p = remember { Animatable(if (play && !reduced) 0f else 1f) }
    LaunchedEffect(play) {
        if (play && !reduced) {
            p.animateTo(1f, keyframes {
                durationMillis = m.durationMs
                delayMillis = m.delayMs
                0f at 0 using m.easing
                m.midFraction at (m.durationMs * m.midFraction).toInt() using m.easing
            })
        }
    }
    Box(
        modifier
            .size(94.dp)
            .graphicsLayer {
                val v = p.value
                val scale = if (v <= m.midFraction) m.fromScale + (m.midScale - m.fromScale) * (v / m.midFraction)
                else m.midScale + (m.toScale - m.midScale) * ((v - m.midFraction) / (1 - m.midFraction))
                scaleX = scale
                scaleY = scale
                alpha = if (v <= m.midFraction) m.midAlpha * (v / m.midFraction) else m.midAlpha + (m.toAlpha - m.midAlpha) * ((v - m.midFraction) / (1 - m.midFraction))
                rotationZ = m.rotationDeg
            }
            .clearAndSetSemantics {}
            .drawBehind {
                val d = 1.dp.toPx()
                drawCircle(C.paper.stamp, size.minDimension / 2 - 1.5f * d, style = androidx.compose.ui.graphics.drawscope.Stroke(3 * d))
                drawCircle(C.paper.stamp, size.minDimension / 2 - 6.5f * d, style = androidx.compose.ui.graphics.drawscope.Stroke(1 * d))
            }
            .testTag("waybill.stamp"),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Txt(stringResource(R.string.waybill_stamp_top), T.stamp.sm, C.paper.stamp, maxLines = 1)
            Txt(stringResource(R.string.waybill_stamp_mid), T.stamp.lg, C.paper.stamp, maxLines = 1)
            Txt(stringResource(R.string.waybill_stamp_bottom), T.stamp.sm, C.paper.stamp, maxLines = 1)
        }
    }
}
