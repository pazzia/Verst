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
import app.verst.core.model.dto.BudgetFitDto
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
    /** 5.8: the minimum of a no-fit is over budget everywhere. */
    val minimum: Boolean = false,
)

interface WaybillActions {
    fun back()
    fun toggleLine(key: String)
    fun toggleReserve()
    fun save()
    fun share()
    /** 5.8 §3: over budget «Подогнать под бюджет» (re-plan → Drive). */
    fun refit() = Unit
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
                Spacer(Modifier.height(12.dp)) // N-11: sheet top 64 (back link 8 + 44), clip at 50
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
                    if (line.key == "parking") ParkingLine(line, trip, ui.expanded == line.key) { a.toggleLine(line.key) }
                    else CostLine(line, ui.expanded == line.key) { a.toggleLine(line.key) }
                }
                cost.lines.firstOrNull { it.key == "reserve" }?.let { ReserveRow(it, cost.reserveOn, ui.busy, a::toggleReserve) }
                TotalRow(cost.totalRub)
            }
            // ADR-0019 E-2: the total says what it leaves out («Без билетов в 1 место — цена неизвестна»)
            cost.totalNoteRu?.let { Txt(it, T.paper.label, C.paper.text, Modifier.padding(top = 4.dp, end = 100.dp).testTag("waybill.total.note")) }
            // 5.8 §3: «Подогнали под бюджет» + one line per lever (the savings sum to initial − total)
            val fit = trip.budgetFit
            if (fit != null && fit.levers.isNotEmpty()) LeverLines(fit)
            val tight = fit?.smallOverrun == true && cost.budgetRub != null && cost.totalRub > cost.budgetRub!!
            IssuedLeft(cost.budgetRub, cost.remainingRub, (cost.overBudget || ui.minimum) && !tight, tight, cost.totalRub)
            if ((cost.overBudget || ui.minimum) && !tight && cost.budgetRub != null) {
                Txt(stringResource(R.string.waybill_over_hint), T.paper.label, C.paper.text, Modifier.padding(top = 4.dp, end = 100.dp))
                Box(
                    Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = a::refit).testTag("waybill.refit"),
                    contentAlignment = Alignment.CenterStart,
                ) { Txt(stringResource(R.string.budget_refit) + " →", T.body.mdStrong, C.paper.ink) }
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
    // 5.12 §3: a synthetic route → «≈» in front of the km
    val mileage = (if (trip.approxDistances) "≈ " else "") +
        stringResource(R.string.waybill_mileage_value, RuFormat.thousands(trip.km), trip.days, pluralStringResource(R.plurals.plural_day, trip.days))
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
    }, right = { Txt(app.verst.settings.AppPrefs.symbol(), T.paper.tableHead, C.paper.label) }) // D-IR-20: the column's currency
}

/** components §11 `CostLine`: name + chevron, the engine formula in hand, the sum; expands to the breakdown. */
@Composable
private fun CostLine(line: CostLineDto, expanded: Boolean, onClick: () -> Unit) {
    val sum = app.verst.settings.AppPrefs.amount(line.rub)
    val state = stringResource(if (expanded) R.string.cd_waybill_collapse else R.string.cd_waybill_expand)
    val cd = stringResource(R.string.cd_waybill_line, line.title, app.verst.settings.AppPrefs.money(line.rub), line.formula, state)
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
                }, right = { Txt(app.verst.settings.AppPrefs.amount(b.rub), T.hand.sm, C.paper.ink, align = TextAlign.End, maxLines = 1) })
            }
        }
    }
}

/**
 * 5.6 §9 (S4) «Парковки»: P 15 + title + chevron; the formula (engine, else from the stops) with «+ ещё N без
 * данных»; expanded: one row per paid stop, the free ones collapsed into one 0 row, the unknown ones with «?»,
 * then the note. Amount = Σ known stays (= the Road-ahead footer).
 */
@Composable
private fun ParkingLine(line: CostLineDto, trip: TripDto, expanded: Boolean, onClick: () -> Unit) {
    val stops = trip.daysList.flatMap { it.stops }.filter { app.verst.feature.road.showsParking(it) }
    val paid = stops.filter { it.parking?.known == true && (it.parking?.rub ?: 0) > 0 }
    val free = stops.count { it.parking?.free == true }
    val unknownStops = stops.filter { it.parking?.known != true }
    // S4-QA P1-01: the same count as the Road ahead rows and day headers (every left-the-car stop without a tariff)
    val unknown = unknownStops.size
    // S4-RELEASE: the same rule as the Road footer and day headers — no exact or zero sum while a stop is unknown.
    // The column is numeric (70 dp, like «Платные дороги 0»), so «бесплатно + ?» reads «0 + ?» here.
    val sum = app.verst.settings.AppPrefs.amount(line.rub) + if (unknown > 0) " + ?" else ""
    val hoursOf = { s: app.verst.core.model.dto.StopDto -> kotlin.math.ceil(s.parking?.hours ?: (s.dwellMin / 60.0)).toInt().coerceAtLeast(1) }
    val formula = line.formula.replace(Regex("""\s*[+·]?\s*(\+\s*)?ещё \d+ без данных"""), "").trim().ifBlank {
        val h = paid.sumOf(hoursOf)
        val towns = paid.mapNotNull { it.townId }.distinct().size.coerceAtLeast(if (paid.isEmpty()) 0 else 1)
        stringResource(R.string.waybill_parking_formula, paid.size, stringResource(R.string.common_hours_short, h), "$towns ${pluralStringResource(R.plurals.plural_town, towns)}")
    }
    val unknownLine = if (unknown > 0) stringResource(R.string.waybill_parking_unknown, unknown) else null
    val state = stringResource(if (expanded) R.string.cd_waybill_collapse else R.string.cd_waybill_expand)
    val cd = stringResource(R.string.cd_waybill_line, line.title, app.verst.settings.AppPrefs.money(line.rub) + if (unknown > 0) " + ?" else "", listOfNotNull(formula, unknownLine).joinToString(" "), state)
    Column(
        Modifier.fillMaxWidth().animateContentSize()
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("waybill.line.parking"),
    ) {
        TableRow(1.dp, SumCol, Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin), left = {
            Column(Modifier.padding(horizontal = 6.dp, vertical = 3.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    app.verst.feature.road.PGlyph(15.dp, Modifier.padding(end = 6.dp))
                    Txt(line.title.ifBlank { stringResource(R.string.waybill_parking) }, T.paper.body, C.paper.text, maxLines = 1)
                    Spacer(Modifier.width(6.dp))
                    GlyphIcon(Glyph.CHEVRON_DOWN, C.paper.label, 12.dp, Modifier.rotate(if (expanded) 180f else 0f), strokeWidth = 2.5f)
                }
                Txt(formula, T.hand.sm, C.paper.ink, Modifier.testTag("waybill.formula.parking"))
                if (unknownLine != null) Txt(unknownLine, T.hand.sm, C.paper.ink, Modifier.testTag("waybill.parking.unknown"))
            }
        }, right = { Txt(sum, T.hand.md, C.paper.ink, Modifier.testTag("waybill.sum.parking"), align = TextAlign.End, maxLines = 2) })
        if (expanded) {
            val rows = buildList<Pair<String, String>> {
                if (line.breakdown.isNotEmpty()) {
                    line.breakdown.forEach { b -> add((if (b.formula.isBlank()) b.label else b.label + ", " + b.formula.substringBefore(" = ")) to app.verst.settings.AppPrefs.amount(b.rub)) }
                    // every unknown stop is listed (S4-QA P1-01), also when the engine's breakdown has only the known ones
                    val listed = line.breakdown.map { it.label }.toSet()
                    unknownStops.filter { it.name !in listed }.forEach { st -> add(st.name to "?") }
                } else {
                    paid.forEach { s ->
                        add(stringResource(R.string.waybill_parking_row, s.name, hoursOf(s), app.verst.settings.AppPrefs.amount(s.parking?.rubPerHour ?: 0)) to app.verst.settings.AppPrefs.amount(s.parking?.rub ?: 0))
                    }
                    if (free > 0) add("${stringResource(R.string.road_parking_inline_free).replaceFirstChar { it.uppercase() }} · $free" to "0")
                    unknownStops.forEach { s -> add(s.name to "?") }
                }
            }
            rows.forEachIndexed { i, (text, rub) ->
                TableRow(0.dp, SumCol, Modifier.defaultMinSize(minHeight = 22.dp).testTag("waybill.breakdown.parking.$i"), left = {
                    Txt(text, T.paper.label, C.paper.text, Modifier.padding(start = 18.dp, end = 6.dp, top = 2.dp, bottom = 2.dp))
                }, right = { Txt(rub, T.hand.sm, C.paper.ink, align = TextAlign.End, maxLines = 1) })
            }
            TableRow(1.dp, SumCol, Modifier.defaultMinSize(minHeight = 22.dp), left = {
                Txt(stringResource(R.string.waybill_parking_note), T.paper.label, C.paper.label, Modifier.padding(start = 18.dp, end = 6.dp, top = 2.dp, bottom = 4.dp))
            }, right = {})
        }
    }
}

/** components §11 `ReserveSwitch`: checkbox (hand check), «Резерв 10%», sub, sum or «—»; a Switch for TalkBack. */
@Composable
private fun ReserveRow(line: CostLineDto, on: Boolean, busy: Boolean, onToggle: () -> Unit) {
    val sum = if (on) app.verst.settings.AppPrefs.amount(line.rub) else NONE
    val cd = stringResource(R.string.cd_waybill_reserve, app.verst.settings.AppPrefs.money(if (on) line.rub else 0))
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
    val value = stringResource(R.string.common_estimate_rub, app.verst.settings.AppPrefs.money(total))
    val cd = stringResource(R.string.cd_waybill_total, app.verst.settings.AppPrefs.money(total))
    TableRow(0.dp, TotalCol, Modifier.semantics(mergeDescendants = true) { heading(); contentDescription = cd }, left = {
        Txt(stringResource(R.string.waybill_total), T.paper.total, C.paper.text, Modifier.padding(6.dp))
    }, right = { Fade(value) { Txt(it, T.hand.xl, C.paper.ink, Modifier.padding(vertical = 4.dp).testTag("waybill.total"), align = TextAlign.End, maxLines = 1) } })
}

@Composable
private fun LeverLines(fit: BudgetFitDto) {
    Column(Modifier.fillMaxWidth().padding(top = 8.dp).testTag("waybill.levers")) {
        Txt(stringResource(R.string.budget_fitted_title), T.paper.body, C.paper.text)
        fit.levers.forEach { l ->
            Row(Modifier.fillMaxWidth().defaultMinSize(minHeight = 22.dp), verticalAlignment = Alignment.CenterVertically) {
                Txt(leverName(l.code), T.paper.label, C.paper.text, Modifier.weight(1f))
                Txt("−" + app.verst.settings.AppPrefs.money(l.savedRub), T.hand.sm, C.paper.ink, Modifier.width(TotalCol), align = TextAlign.End, maxLines = 1)
            }
        }
    }
}

@Composable
internal fun leverName(code: String): String = when (code) {
    "lodging_cheap" -> stringResource(R.string.budget_lever_lodging_cheap)
    "family_rooms" -> stringResource(R.string.budget_lever_family_rooms)
    "food_economy" -> stringResource(R.string.budget_lever_food_economy)
    "sights_free" -> stringResource(R.string.budget_lever_sights_free)
    "parking_free" -> stringResource(R.string.budget_lever_parking_free)
    "fewer_nights" -> stringResource(R.string.budget_lever_fewer_nights)
    "variant" -> stringResource(R.string.budget_lever_variant)
    else -> code
}

@Composable
private fun IssuedLeft(budget: Int?, remaining: Int?, over: Boolean, tight: Boolean = false, total: Int = 0) {
    Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Column(Modifier.weight(1f).semantics(mergeDescendants = true) {}) {
            Txt(stringResource(R.string.waybill_issued), T.paper.label, C.paper.label)
            Txt(budget?.let { app.verst.settings.AppPrefs.amount(it) } ?: NONE, T.hand.md, C.paper.ink, Modifier.fillMaxWidth().underline(C.paper.lines).testTag("waybill.issued"))
        }
        Column(Modifier.weight(1f).semantics(mergeDescendants = true) {}) {
            val isOver = over && budget != null
            Txt(
                stringResource(if (tight) R.string.waybill_tight_label else if (isOver) R.string.waybill_over else R.string.waybill_left),
                T.paper.label, C.paper.label,
            )
            val value = when {
                tight && budget != null -> app.verst.settings.AppPrefs.amount(total - budget)
                budget == null || remaining == null -> NONE
                isOver -> app.verst.settings.AppPrefs.amount(kotlin.math.abs(remaining))
                else -> stringResource(R.string.common_estimate_rub, app.verst.settings.AppPrefs.money(remaining))
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
        Row(verticalAlignment = Alignment.CenterVertically) {
            Txt(
                stringResource(if (saved) R.string.waybill_saved else R.string.waybill_save), T.button.md,
                if (saved) C.text.secondary else C.text.primary, maxLines = 1, align = TextAlign.Center,
            )
            // N-09: the check is drawn after «Сохранено» (the font has no «✓»).
            if (saved) GlyphIcon(Glyph.CHECK, C.text.secondary, 16.dp, Modifier.padding(start = 6.dp))
        }
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
