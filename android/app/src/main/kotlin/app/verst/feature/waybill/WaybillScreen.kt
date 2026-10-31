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
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.BudgetFitDto
import app.verst.core.model.dto.CostLineDto
import app.verst.core.model.dto.LocalMoney
import app.verst.core.model.dto.TripDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftSecondaryButton
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.DashedDivider
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
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

/** Mockup `.stamp-box`: the stamp is turned −4° (the craft look), not the round stamp's −14°. */
private const val StampRotation = -4f

/** The waybill's amounts: Plex Mono, 15 sp bold (mockup `font-mono font-bold`). */
private val SumMono = CraftType.fieldMono.copy(fontWeight = FontWeight.W700)

/** The total: Plex Mono 22 sp bold (mockup `text-base font-black font-mono`). */
private val TotalMono = CraftType.fieldMono.copy(fontSize = 22.sp, lineHeight = 26.sp, fontWeight = FontWeight.W700)

/**
 * 5.6 Waybill, simplified (DEV-SLICE-2): the sheet with the engine's cost lines and formulas, one line expanded at a
 * time, the reserve switch re-costed by the engine (`patch_cost`), issued / left against the budget, the stamp (once
 * per trip), the entry slide and value cross-fades. Fork camper-ui (mockup screen 8 «Путевой лист»): a paper craft
 * card «ПУТЕВОЙ ЛИСТ» with its number, a dashed rule, the lines with mono amounts, the 2 dp rule over «ИТОГО», the
 * stamp as a dashed red box turned −4° (its own words: «ВЕРСТА / В ПУТЬ / ГОТОВЫ»), and craft buttons.
 */
@Composable
fun WaybillScreen(ui: WaybillUi, a: WaybillActions) {
    ScreenRoot(C.camper.page) {
        Column(Modifier.fillMaxSize()) {
            Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = CraftDefaults.ScreenGutter)) {
                val back = stringResource(R.string.common_back_road)
                BackLink(back, C.camper.ink, stringResource(R.string.cd_back, back), a::back, Modifier.padding(top = 2.dp).testTag("waybill.back"))
                Spacer(Modifier.height(4.dp))
                // motion.sheetSlide: 40 dp up + fade in over 600 ms on entry (at rest under reduced motion).
                val reduced = LocalReducedMotion.current
                val slide = remember { Animatable(if (reduced) 1f else 0f) }
                LaunchedEffect(Unit) { if (!reduced) slide.animateTo(1f, tween(DesignTokens.motion.sheetSlide.durationMs, easing = DesignTokens.motion.sheetSlide.easing)) }
                Box(Modifier.graphicsLayer { translationY = DesignTokens.motion.sheetSlide.fromDyDp.toPx() * (1 - slide.value); alpha = slide.value }) {
                    Sheet(ui, a)
                }
                Spacer(Modifier.height(16.dp))
            }
            // the end / bottom padding keep the buttons' hard shadows above the tab bar
            Row(
                Modifier.fillMaxWidth().padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter + CraftDefaults.ShadowX, bottom = 14.dp, top = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                CraftSecondaryButton(
                    stringResource(if (ui.saved) R.string.waybill_saved else R.string.waybill_save), a::save,
                    Modifier.weight(1f).testTag("waybill.save"), enabled = !ui.saved,
                )
                CraftButton(stringResource(R.string.waybill_share), a::share, Modifier.weight(1f).testTag("waybill.share"))
            }
        }
        val t = ui.toast
        if (t != null) PlateToast(toastText(t), bottom = 14.dp + CraftDefaults.ButtonHeight + 16.dp)
    }
}

@Composable
private fun Sheet(ui: WaybillUi, a: WaybillActions) {
    val trip = ui.trip
    val cost = trip.cost
    Box(Modifier.fillMaxWidth().padding(end = CraftDefaults.ShadowX, bottom = CraftDefaults.ShadowY)) {
        CraftCard(Modifier.fillMaxWidth().testTag("waybill.sheet"), padding = PaddingValues(14.dp), spacing = 0.dp) {
            Header(ui.number)
            DashedDivider(Modifier.padding(top = 10.dp, bottom = 4.dp), color = C.camper.border.copy(alpha = 0.3f))
            FormGrid(trip)
            Spacer(Modifier.height(12.dp))
            TableHeader()
            cost.lines.filter { it.key != "reserve" }.forEach { line ->
                if (line.key == "parking") ParkingLine(line, trip, ui.expanded == line.key) { a.toggleLine(line.key) }
                else CostLine(line, ui.expanded == line.key) { a.toggleLine(line.key) }
            }
            cost.lines.firstOrNull { it.key == "reserve" }?.let { ReserveRow(it, cost.reserveOn, ui.busy, a::toggleReserve) }
            TotalRow(cost.totalRub)
            // ADR-0019 E-2: the total says what it leaves out («Без билетов в 1 место — цена неизвестна»)
            cost.totalNoteRu?.let { Txt(it, T.body.sm, C.camper.inkSoft, Modifier.padding(top = 4.dp).testTag("waybill.total.note")) }
            // CEO 29.10 (trips abroad): «За границей» — what the rouble total leaves out, fuel in the local currency
            trip.abroad?.let { AbroadBlock(it) }
            // 5.8 §3: «Подогнали под бюджет» + one line per lever (the savings sum to initial − total)
            val fit = trip.budgetFit
            if (fit != null && fit.levers.isNotEmpty()) LeverLines(fit)
            val tight = fit?.smallOverrun == true && cost.budgetRub != null && cost.totalRub > cost.budgetRub!!
            IssuedLeft(cost.budgetRub, cost.remainingRub, (cost.overBudget || ui.minimum) && !tight, tight, cost.totalRub)
            if ((cost.overBudget || ui.minimum) && !tight && cost.budgetRub != null) {
                Txt(stringResource(R.string.waybill_over_hint), T.body.sm, C.camper.inkSoft, Modifier.padding(top = 8.dp))
                // mockup: «Подогнать под бюджет» is the orange craft button (its shadow stays inside the card's padding)
                CraftButton(
                    stringResource(R.string.budget_refit), a::refit,
                    Modifier.padding(top = 10.dp).fillMaxWidth().testTag("waybill.refit"),
                )
            }
            if (ui.monthRu != null && ui.year != null) {
                Txt(
                    stringResource(R.string.waybill_footnote_real, ui.monthRu, ui.year), T.body.sm, C.camper.inkMuted,
                    Modifier.padding(top = 10.dp),
                )
            }
        }
        // mockup `.stamp-box`: top right of the card, over the header's free end
        Stamp(ui.stamp, Modifier.align(Alignment.TopEnd).padding(top = 14.dp, end = 12.dp))
    }
}

@Composable
private fun Header(number: Int) {
    val no = number.toString().padStart(3, '0')
    Column(
        // the stamp sits at the top end: the header keeps clear of it
        Modifier.fillMaxWidth().padding(end = 96.dp).semantics(mergeDescendants = true) { heading() },
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Txt(stringResource(R.string.waybill_form), CraftType.overline, C.camper.orangeText, maxLines = 1)
        Txt(stringResource(R.string.waybill_title), CraftType.wordmark, C.camper.ink, maxLines = 1)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Txt(stringResource(R.string.waybill_subtitle), T.body.sm, C.camper.inkSoft, Modifier.weight(1f, fill = false), maxLines = 1)
            Txt(" · " + stringResource(R.string.waybill_number) + " ", T.body.sm, C.camper.inkSoft, maxLines = 1)
            Txt(no, SumMono, C.camper.ink, Modifier.testTag("waybill.number"), maxLines = 1)
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
    Column(Modifier.fillMaxWidth().padding(top = 6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        FormRow(stringResource(R.string.waybill_route), trip.title, "waybill.route")
        FormRow(stringResource(R.string.waybill_crew), crewParts, "waybill.crew")
        FormRow(stringResource(R.string.waybill_mileage), mileage, "waybill.mileage")
    }
}

@Composable
private fun FormRow(label: String, value: String, tag: String) {
    Row(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {}, verticalAlignment = Alignment.Top) {
        Txt(label, CraftType.fieldLabel, C.camper.inkSoft, Modifier.width(92.dp).padding(top = 2.dp), maxLines = 1)
        Txt(value, T.body.mdStrong, C.camper.ink, Modifier.weight(1f).testTag(tag))
    }
}

/** The column heads: «СТАТЬЯ И РАСЧЁТ» and the currency (D-IR-20), muted overlines. */
@Composable
private fun TableHeader() {
    Row(Modifier.fillMaxWidth().padding(bottom = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        Txt(stringResource(R.string.waybill_table_item), CraftType.sectionTitle, C.camper.inkMuted, Modifier.weight(1f), maxLines = 1)
        Txt(app.verst.settings.AppPrefs.symbol(), CraftType.sectionTitle, C.camper.inkMuted, maxLines = 1)
    }
    DashedDivider(thickness = 1.5.dp)
}

/** A line of the sheet: the left part (title, formula), the amount right (mono), a dashed rule under it. */
@Composable
private fun SheetRow(modifier: Modifier = Modifier, left: @Composable () -> Unit, right: @Composable () -> Unit) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.weight(1f), contentAlignment = Alignment.CenterStart) { left() }
        Box(Modifier.widthIn(min = SumCol).padding(start = 8.dp), contentAlignment = Alignment.CenterEnd) { right() }
    }
}

/** A breakdown row under an expanded line: indented label, the amount in small mono. */
@Composable
private fun BreakdownRow(text: String, amount: String, tag: String?, muted: Boolean = false) {
    SheetRow(
        Modifier.defaultMinSize(minHeight = 24.dp).then(if (tag != null) Modifier.testTag(tag) else Modifier),
        left = { Txt(text, T.body.sm, if (muted) C.camper.inkMuted else C.camper.inkSoft, Modifier.padding(start = 14.dp, top = 2.dp, bottom = 2.dp)) },
        right = { Txt(amount, T.body.smStrong, C.camper.inkSoft, align = TextAlign.End, maxLines = 1) },
    )
}

/** components §11 `CostLine`: name + chevron, the engine formula, the sum; expands to the breakdown. */
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
        SheetRow(Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).padding(vertical = 6.dp), left = {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Txt(line.title, T.body.mdStrong, C.camper.ink, maxLines = 1)
                    if (line.breakdown.isNotEmpty()) {
                        Spacer(Modifier.width(6.dp))
                        GlyphIcon(Glyph.CHEVRON_DOWN, C.camper.inkSoft, 12.dp, Modifier.rotate(if (expanded) 180f else 0f), strokeWidth = 2.5f)
                    }
                }
                Txt(line.formula, T.body.sm, C.camper.inkSoft, Modifier.testTag("waybill.formula.${line.key}"))
            }
        }, right = { Txt(sum, SumMono, C.camper.ink, align = TextAlign.End, maxLines = 1) })
        if (expanded) {
            val sep = stringResource(R.string.common_join_dot)
            line.breakdown.forEachIndexed { i, b ->
                // The engine's breakdown formula ends with «= N ₽», which the ₽ column already shows.
                val text = if (b.formula.isBlank()) b.label else b.label + sep + b.formula.substringBefore(" = ")
                BreakdownRow(text, app.verst.settings.AppPrefs.amount(b.rub), "waybill.breakdown.${line.key}.$i")
            }
            Spacer(Modifier.height(4.dp))
        }
        DashedDivider(thickness = 1.5.dp)
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
    // The column is numeric (like «Платные дороги 0»), so «бесплатно + ?» reads «0 + ?» here.
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
        SheetRow(Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).padding(vertical = 6.dp), left = {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    app.verst.feature.road.PGlyph(15.dp, Modifier.padding(end = 6.dp))
                    Txt(line.title.ifBlank { stringResource(R.string.waybill_parking) }, T.body.mdStrong, C.camper.ink, maxLines = 1)
                    Spacer(Modifier.width(6.dp))
                    GlyphIcon(Glyph.CHEVRON_DOWN, C.camper.inkSoft, 12.dp, Modifier.rotate(if (expanded) 180f else 0f), strokeWidth = 2.5f)
                }
                Txt(formula, T.body.sm, C.camper.inkSoft, Modifier.testTag("waybill.formula.parking"))
                if (unknownLine != null) Txt(unknownLine, T.body.sm, C.camper.inkSoft, Modifier.testTag("waybill.parking.unknown"))
            }
        }, right = { Txt(sum, SumMono, C.camper.ink, Modifier.testTag("waybill.sum.parking"), align = TextAlign.End, maxLines = 2) })
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
            rows.forEachIndexed { i, (text, rub) -> BreakdownRow(text, rub, "waybill.breakdown.parking.$i") }
            BreakdownRow(stringResource(R.string.waybill_parking_note), "", null, muted = true)
            Spacer(Modifier.height(4.dp))
        }
        DashedDivider(thickness = 1.5.dp)
    }
}

/** components §11 `ReserveSwitch`: a craft check (green when on), «Резерв 10%» in green, sub, sum or «—»; a Switch for TalkBack. */
@Composable
private fun ReserveRow(line: CostLineDto, on: Boolean, busy: Boolean, onToggle: () -> Unit) {
    val sum = if (on) app.verst.settings.AppPrefs.amount(line.rub) else NONE
    val cd = stringResource(R.string.cd_waybill_reserve, app.verst.settings.AppPrefs.money(if (on) line.rub else 0))
    val box = RoundedCornerShape(6.dp)
    SheetRow(
        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .toggleable(on, enabled = !busy, role = Role.Switch) { onToggle() }
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("waybill.reserve")
            .padding(vertical = 6.dp),
        left = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.size(22.dp).clip(box).background(if (on) C.camper.green else C.camper.field).border(CraftDefaults.BorderThin, C.camper.border, box),
                    contentAlignment = Alignment.Center,
                ) {
                    if (on) GlyphIcon(Glyph.CHECK, C.camper.onOrange, 16.dp, Modifier.testTag("waybill.reserve.check"))
                }
                Spacer(Modifier.width(10.dp))
                Column {
                    Txt(line.title, T.body.mdStrong, C.camper.greenText, maxLines = 1)
                    Txt(line.formula, T.body.sm, C.camper.inkSoft, maxLines = 2)
                }
            }
        },
        right = { Fade(sum) { Txt(it, SumMono, if (on) C.camper.greenText else C.camper.inkMuted, align = TextAlign.End, maxLines = 1, modifier = Modifier.testTag("waybill.reserve.sum")) } },
    )
}

/** «ИТОГО» under the mockup's 2 dp brown rule, the total in big mono. */
@Composable
private fun TotalRow(total: Int) {
    val value = stringResource(R.string.common_estimate_rub, app.verst.settings.AppPrefs.money(total))
    val cd = stringResource(R.string.cd_waybill_total, app.verst.settings.AppPrefs.money(total))
    Box(Modifier.padding(top = 6.dp).fillMaxWidth().height(2.dp).background(C.camper.border))
    Row(
        Modifier.fillMaxWidth().padding(top = 8.dp).semantics(mergeDescendants = true) { heading(); contentDescription = cd },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Txt(stringResource(R.string.waybill_total), CraftType.sectionTitle, C.camper.ink, Modifier.weight(1f), maxLines = 1)
        Fade(value) { Txt(it, TotalMono, C.camper.ink, Modifier.widthIn(min = SumCol).testTag("waybill.total"), align = TextAlign.End, maxLines = 1) }
    }
}

/**
 * CEO 29.10 (trips abroad): the block the engine's total note points to («смотрите блок «За границей»»): «Итог без
 * расходов за границей» with the engine's list of what is left out, then per country the km and the fuel — in roubles
 * only with the server's Bank of Russia rate, else as is in the local currency («≈ 37 GEL»), then the counted sums.
 */
@Composable
private fun AbroadBlock(abroad: app.verst.core.model.dto.AbroadDto) {
    Column(Modifier.fillMaxWidth().padding(top = 10.dp).testTag("waybill.abroad"), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(Modifier.semantics(mergeDescendants = true) { heading() }, verticalAlignment = Alignment.CenterVertically) {
            Txt(stringResource(R.string.waybill_abroad_title), T.body.mdStrong, C.camper.ink)
            if (abroad.unverified) Txt(" · " + stringResource(R.string.common_unverified), T.body.sm, C.camper.inkMuted)
        }
        if (abroad.roubleTotalIncomplete) {
            Txt(stringResource(R.string.road_total_abroad_incomplete), T.body.sm, C.camper.ink, Modifier.testTag("waybill.abroad.incomplete"))
            abroad.notInRoubleTotalRu.forEachIndexed { i, m ->
                Txt("— $m", T.body.sm, C.camper.inkSoft, Modifier.padding(start = 8.dp).testTag("waybill.abroad.missing.$i"))
            }
        }
        abroad.countries.forEach { c ->
            val km = RuFormat.thousands(kotlin.math.round(c.km).toInt())
            Txt(stringResource(R.string.waybill_abroad_country, c.nameRu.ifBlank { c.code }, km), T.body.sm, C.camper.ink, Modifier.padding(top = 4.dp))
            val f = c.fuel
            val local = LocalMoney.approx(f?.amount, f?.currency ?: c.currency)
            val rub = if (f != null && f.inRoubleTotal) f.rub else null
            val fuel = when {
                f == null -> null
                rub != null -> stringResource(R.string.waybill_abroad_fuel, app.verst.settings.AppPrefs.money(rub) + (local?.let { " ($it)" } ?: ""))
                local != null -> stringResource(R.string.waybill_abroad_fuel_local, local)
                else -> stringResource(R.string.waybill_abroad_fuel_unknown)
            }
            if (fuel != null) Txt(fuel, T.body.smStrong, C.camper.inkSoft, Modifier.padding(start = 8.dp).testTag("waybill.abroad.fuel.${c.code}"))
        }
        val totals = abroad.localTotals.mapNotNull { LocalMoney.approx(it.amount, it.currency) }
        if (totals.isNotEmpty()) {
            Txt(stringResource(R.string.waybill_abroad_counted, totals.joinToString(", ")), T.body.sm, C.camper.ink, Modifier.padding(top = 4.dp).testTag("waybill.abroad.counted"))
        }
    }
}

@Composable
private fun LeverLines(fit: BudgetFitDto) {
    Column(Modifier.fillMaxWidth().padding(top = 10.dp).testTag("waybill.levers")) {
        Txt(stringResource(R.string.budget_fitted_title), T.body.mdStrong, C.camper.greenText)
        fit.levers.forEach { l ->
            Row(Modifier.fillMaxWidth().defaultMinSize(minHeight = 24.dp), verticalAlignment = Alignment.CenterVertically) {
                Txt(leverName(l.code), T.body.sm, C.camper.ink, Modifier.weight(1f))
                Txt("−" + app.verst.settings.AppPrefs.money(l.savedRub), T.body.smStrong, C.camper.greenText, Modifier.width(TotalCol), align = TextAlign.End, maxLines = 1)
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

/** «Выдано» / «Остаток» (or «Перерасход», «Сверх бюджета»): two white-paper fields with mono values. */
@Composable
private fun IssuedLeft(budget: Int?, remaining: Int?, over: Boolean, tight: Boolean = false, total: Int = 0) {
    Row(Modifier.fillMaxWidth().padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Column(Modifier.weight(1f).semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Txt(stringResource(R.string.waybill_issued), CraftType.fieldLabel, C.camper.inkSoft)
            Box(Modifier.fillMaxWidth().craftField().padding(horizontal = 10.dp, vertical = 8.dp)) {
                Txt(budget?.let { app.verst.settings.AppPrefs.amount(it) } ?: NONE, SumMono, C.camper.ink, Modifier.testTag("waybill.issued"), maxLines = 1)
            }
        }
        Column(Modifier.weight(1f).semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            val isOver = over && budget != null
            Txt(
                stringResource(if (tight) R.string.waybill_tight_label else if (isOver) R.string.waybill_over else R.string.waybill_left),
                CraftType.fieldLabel, if (isOver) C.accent.redText else C.camper.inkSoft,
            )
            val value = when {
                tight && budget != null -> app.verst.settings.AppPrefs.amount(total - budget)
                budget == null || remaining == null -> NONE
                isOver -> app.verst.settings.AppPrefs.amount(kotlin.math.abs(remaining))
                else -> stringResource(R.string.common_estimate_rub, app.verst.settings.AppPrefs.money(remaining))
            }
            Box(Modifier.fillMaxWidth().craftField().padding(horizontal = 10.dp, vertical = 8.dp)) {
                Fade(value) { Txt(it, SumMono, if (isOver) C.accent.redText else C.camper.ink, Modifier.testTag("waybill.left"), maxLines = 1) }
            }
        }
    }
}

/** 5.6 §3: changed values cross-fade 200 ms (instant under reduced motion). */
@Composable
private fun Fade(value: String, content: @Composable (String) -> Unit) {
    if (LocalReducedMotion.current) content(value) else Crossfade(value, animationSpec = tween(200, easing = DesignTokens.motion.easing.standard), label = "value") { content(it) }
}

/**
 * components §11.1 stamp, fork camper-ui (mockup `.stamp-box`): a 2 dp dashed red box turned −4°, «ВЕРСТА / В ПУТЬ /
 * ГОТОВЫ» in the stamp type (the stamp's own words). `motion.stamp` once per trip: after 1000 ms, scale 2.4 → 0.92
 * (300 ms) → 1 (500 ms), α 0 → 0.9 → 0.85.
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
            .graphicsLayer {
                val v = p.value
                val scale = if (v <= m.midFraction) m.fromScale + (m.midScale - m.fromScale) * (v / m.midFraction)
                else m.midScale + (m.toScale - m.midScale) * ((v - m.midFraction) / (1 - m.midFraction))
                scaleX = scale
                scaleY = scale
                alpha = if (v <= m.midFraction) m.midAlpha * (v / m.midFraction) else m.midAlpha + (m.toAlpha - m.midAlpha) * ((v - m.midFraction) / (1 - m.midFraction))
                rotationZ = StampRotation
            }
            .clearAndSetSemantics {}
            .drawBehind {
                val w = 2.dp.toPx()
                drawRoundRect(
                    C.camper.stamp, topLeft = Offset(w / 2, w / 2), size = Size(size.width - w, size.height - w),
                    cornerRadius = CornerRadius(4.dp.toPx()),
                    style = Stroke(width = w, pathEffect = PathEffect.dashPathEffect(floatArrayOf(5.dp.toPx(), 3.dp.toPx()))),
                )
            }
            .testTag("waybill.stamp")
            .padding(horizontal = 8.dp, vertical = 4.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Txt(stringResource(R.string.waybill_stamp_top), T.stamp.sm, C.camper.stamp, maxLines = 1)
            Txt(stringResource(R.string.waybill_stamp_mid), T.stamp.lg, C.camper.stamp, maxLines = 1)
            Txt(stringResource(R.string.waybill_stamp_bottom), T.stamp.sm, C.camper.stamp, maxLines = 1)
        }
    }
}
