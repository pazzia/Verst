package app.verst.feature.road

import androidx.compose.foundation.background
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
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
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
)

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
}

/** 5.5 Road ahead: the day-by-day signs of the plan, «заменить» (D-6), save/share, the Waybill footer. */
@Composable
fun RoadScreen(ui: RoadUi, a: RoadActions) {
    val trip = ui.trip
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
                            Glyph.BOOKMARK, if (ui.saved) C.accent.yellow else C.mirror.label,
                            stringResource(if (ui.saved) R.string.cd_road_saved else R.string.cd_road_save), "road.save", filled = ui.saved, onClick = a::save,
                        )
                        IconButton44(Glyph.SHARE, C.mirror.label, stringResource(R.string.cd_road_share), "road.share", onClick = a::share)
                    }
                    TitleSign(trip, ui.bearing8, Modifier.padding(start = 20.dp, end = 20.dp, top = 56.dp).fillMaxWidth())
                }
                Box(Modifier.weight(1f).fillMaxWidth()) {
                    // S-20: one scrolled column; the road section draws a single continuous road (one lane-dash
                    // phase), the rows draw only their connector stubs. A trip has tens of rows, not thousands.
                    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).testTag("road.list")) {
                        Intro(trip)
                        Column(Modifier.fillMaxWidth().roadSection()) {
                            trip.daysList.forEachIndexed { di, d ->
                                DayHeader(d, trip.roundTrip && di == trip.daysList.lastIndex && trip.days > 1, first = di == 0)
                                d.stops.forEachIndexed { si, st -> StopRow(st, di == 0 && si == 0) { a.replace(st) } }
                            }
                            Spacer(Modifier.height(24.dp))
                        }
                    }
                    Box(
                        Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(24.dp)
                            .background(Brush.verticalGradient(listOf(C.dash.raised.copy(alpha = 0f), C.dash.raised))),
                    )
                }
                Footer(trip, a::waybill)
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
            OptionRow(s.name, s.note ?: s.reason, stringResource(R.string.replace_current), r.picked == null, "replace.current") { a.pick(null) }
            s.alternatives.forEachIndexed { i, alt ->
                OptionRow(alt.name, alt.stop?.note ?: alt.stop?.reason, deltaText(alt), r.picked == alt.id, "replace.alt.$i") { a.pick(alt.id) }
            }
        }
        val note = s.alternativesNote
        if (note != null) Txt(note, T.body.md, C.text.note, Modifier.padding(top = 10.dp))
        Spacer(Modifier.height(14.dp))
        if (s.alternatives.isNotEmpty()) {
            val enabled = r.picked != null && !r.busy
            Box(Modifier.fillMaxWidth().testTag("replace.confirm")) {
                if (enabled) {
                    PrimaryCta(stringResource(R.string.replace_confirm).uppercase(), a::confirmReplace)
                } else {
                    Box(
                        Modifier.fillMaxWidth().height(DesignTokens.size.ctaH).clip(RoundedCornerShape(DesignTokens.radius.r12)).background(C.dash.control)
                            .padding(horizontal = 18.dp),
                        contentAlignment = Alignment.CenterStart,
                    ) { Txt(stringResource(R.string.replace_confirm).uppercase(), T.cta.md, C.text.disabled, maxLines = 1) }
                }
            }
        }
        Box(
            Modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = a::closeReplace)
                .testTag("replace.keep"),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.replace_keep), T.body.mdStrong, C.text.secondary) }
    }
}

/** HotelOption-style radio row (components §12.2, D-6). */
@Composable
private fun OptionRow(name: String, sub: String?, delta: String, selected: Boolean, tag: String, onClick: () -> Unit) {
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = DesignTokens.size.hotelRowMinH)
            .clip(shape)
            .background(if (selected) C.dash.controlAlt else C.dash.raised)
            .border(DesignTokens.stroke.w1, if (selected) C.accent.yellow else C.dash.outline, shape)
            .selectable(selected, role = Role.RadioButton, onClick = onClick)
            .testTag(tag)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(Modifier.size(18.dp).border(2.dp, if (selected) C.accent.yellow else C.text.secondary, RoundedCornerShape(9.dp)), contentAlignment = Alignment.Center) {
            if (selected) Box(Modifier.size(6.dp).clip(RoundedCornerShape(3.dp)).background(C.accent.yellow))
        }
        Column(Modifier.weight(1f)) {
            Txt(name, T.title.sm, C.text.primary, maxLines = 1)
            if (!sub.isNullOrBlank()) Txt(sub, T.body.sm, C.text.secondary, maxLines = 2)
        }
        Txt(delta, T.body.mdStrong, C.text.primary, maxLines = 1)
    }
}

/** «+4 мин · −150 ₽» from `replace_delta` («{sign}{min} мин · {sign}{amount} ₽», copy-ru D-6), one sign per part. */
@Composable
private fun deltaText(alt: AlternativeDto): String {
    fun sign(n: Int) = when {
        n > 0 -> "+"
        n < 0 -> "−"
        else -> ""
    }
    val minutes = stringResource(R.string.replace_delta, sign(alt.deltaMin), kotlin.math.abs(alt.deltaMin), RuFormat.thousands(kotlin.math.abs(alt.deltaRub)))
    if (sign(alt.deltaMin) == sign(alt.deltaRub)) return minutes
    // Mixed signs: the template uses one sign for both parts, so each part comes from its own rendering.
    val rub = stringResource(R.string.replace_delta, sign(alt.deltaRub), kotlin.math.abs(alt.deltaMin), RuFormat.thousands(kotlin.math.abs(alt.deltaRub)))
    val sep = stringResource(R.string.common_join_dot)
    return minutes.substringBefore(sep) + sep + rub.substringAfter(sep)
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
private fun Intro(trip: TripDto) {
    // S-21 / 5.5 §2.2: L1 at the list top, L2 +6, L3 +8, road column 18 below L3 (padding 4 + margin 14).
    Column(Modifier.padding(start = 20.dp, end = 20.dp, top = 0.dp, bottom = 18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Txt(stringResource(R.string.road_title), T.display, C.text.primary, Modifier.semantics { heading() })
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
        Txt(stringResource(R.string.road_intro), T.body.mdTight, C.text.secondary, Modifier.padding(top = 2.dp))
        for (w in trip.warnings) {
            val msg = w.message ?: continue
            Row(
                Modifier.fillMaxWidth().padding(top = 4.dp)
                    .border(DesignTokens.stroke.w1, C.accent.yellow, RoundedCornerShape(DesignTokens.radius.r10))
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(Modifier.width(14.dp).height(14.dp).clip(RoundedCornerShape(7.dp)).background(C.accent.yellow), contentAlignment = Alignment.Center) {
                    Txt("!", T.caption.bold, C.text.onLight)
                }
                Txt(msg, T.body.md, C.text.primary)
            }
        }
    }
}

/** 5.5 §2.4: asphalt x 14…60, 3 dp edges, lane dashes 32 / 64 from the section top (one global phase). */
private fun Modifier.roadSection(): Modifier = drawBehind {
    val dp = 1.dp.toPx()
    drawRect(C.scene.road, Offset(14 * dp, 0f), Size(46 * dp, size.height))
    drawRect(C.scene.roadEdge, Offset(14 * dp, 0f), Size(3 * dp, size.height))
    drawRect(C.scene.roadEdge, Offset(57 * dp, 0f), Size(3 * dp, size.height))
    var y = 0f
    while (y < size.height) {
        drawRect(C.scene.roadEdge, Offset(35.5f * dp, y), Size(3 * dp, minOf(32 * dp, size.height - y)))
        y += 64 * dp
    }
}

/** Per row: the 14 × 3 connector stub at x 60, row top + 38 (`color.interior.pole`). */
private fun Modifier.connector(): Modifier = drawBehind {
    val dp = 1.dp.toPx()
    drawRect(C.interior.pole, Offset(60 * dp, 38 * dp), Size(14 * dp, 3 * dp))
}

@Composable
private fun DayHeader(day: DayDto, home: Boolean, first: Boolean) {
    val hours = (day.driveMin / 60.0).roundToInt()
    val meta = if (home) stringResource(R.string.road_day_meta_home, RuFormat.thousands(day.km))
    else stringResource(R.string.road_day_meta, RuFormat.thousands(day.km), hours)
    val cd = stringResource(R.string.cd_road_day, day.day, day.km.toString(), hours, pluralStringResource(R.plurals.plural_hour, hours))
    Row(
        // S-21: day 1 starts at the road top (margin 0), later days 6 below the previous row; 10 to row 1.
        Modifier.fillMaxWidth().padding(start = 72.dp, end = 16.dp, top = if (first) 0.dp else 6.dp, bottom = 10.dp)
            .semantics(mergeDescendants = true) { heading(); contentDescription = cd },
        verticalAlignment = Alignment.Bottom,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Txt(stringResource(R.string.road_day, day.day), T.title.sm, C.accent.yellow)
        Txt(meta, T.body.sm, C.text.muted, maxLines = 1)
    }
}

@Composable
private fun StopRow(s: StopDto, first: Boolean, onReplace: () -> Unit) {
    val line1 = if (first || s.kind == "start") stringResource(R.string.road_start)
    else stringResource(R.string.road_ahead_km, RuFormat.thousands(s.kmFromPrev))
    val unverified = if (!s.verified) stringResource(R.string.common_join_dot) + stringResource(R.string.common_unverified) else ""
    val time = RuFormat.clock(s.arriveAt ?: s.departAt) ?: ""
    val name = stopName(s)
    val note = s.note ?: s.reason
    val cost: String? = when (s.kind) {
        "sight" -> if (s.costRub == 0) stringResource(R.string.road_free) else rub(s.costRub)
        "food", "overnight" -> rub(s.costRub)
        "rest" -> stringResource(R.string.common_rub, "0")
        "fuel" -> if (s.costRub > 0) rub(s.costRub) else null
        else -> null
    }
    val cd = listOfNotNull(line1 + unverified, time, name, note, cost).joinToString(", ")
    Row(
        Modifier.fillMaxWidth().connector().padding(top = 8.dp, bottom = 12.dp, end = 16.dp)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("road.stop.${s.id}"),
    ) {
        Box(Modifier.padding(start = 72.dp).width(68.dp), contentAlignment = Alignment.TopCenter) {
            RoadSign(s.sign, s.name, s.tags)
        }
        Column(Modifier.weight(1f).padding(start = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Txt(line1 + unverified, T.body.sm, C.text.muted, Modifier.weight(1f), maxLines = 1)
                Txt(time, T.body.sm, C.text.muted, align = TextAlign.End)
            }
            Txt(name, T.title.md, C.text.primary, maxLines = 2)
            if (!note.isNullOrBlank()) Txt(note, T.body.md, C.text.note)
            val canReplace = s.replaceable && (s.alternatives.isNotEmpty() || s.alternativesNote != null)
            if (cost != null || canReplace) {
                Row(Modifier.fillMaxWidth().padding(top = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                    Txt(cost ?: "", T.body.mdStrong, C.accent.yellow, Modifier.weight(1f))
                    if (canReplace) SwapButton(stringResource(R.string.cd_road_swap, s.name), "road.swap.${s.id}", onReplace)
                }
            }
        }
    }
}

/** components §2.6 `SwapButton` «заменить»: h 36 (touch 44), outline, `type.body.smStrong`. */
@Composable
private fun SwapButton(cd: String, tag: String, onClick: () -> Unit) {
    Box(
        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = cd }.testTag(tag),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier.height(36.dp).border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r8)).padding(horizontal = 10.dp),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.road_swap), T.body.smStrong, C.text.secondary, maxLines = 1) }
    }
}

@Composable
private fun stopName(s: StopDto): String = when (s.kind) {
    "overnight" -> stringResource(R.string.road_name_night, s.name)
    else -> s.name
}

@Composable
private fun Footer(trip: TripDto, onClick: () -> Unit) {
    val c = trip.cost
    val over = c.overBudget && c.budgetRub != null
    val label = if (over) stringResource(R.string.road_waybill_over, RuFormat.thousands(c.totalRub - (c.budgetRub ?: 0)))
    else stringResource(R.string.road_waybill_label)
    val total = rub(c.totalRub)
    val perPerson = stringResource(R.string.road_waybill_per_person, RuFormat.thousands(c.perPersonRub))
    val cd = stringResource(R.string.cd_road_waybill, RuFormat.thousands(c.totalRub)) + ". " + perPerson
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
            Txt(label, T.body.smStrong, if (over) C.paper.inkRed else C.text.onLightMuted, maxLines = 1)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Txt(total, T.amount, C.text.onLight, Modifier.testTag("road.total.amount"), maxLines = 1)
                Spacer(Modifier.weight(1f))
                Txt(perPerson, T.body.smStrong, C.text.onLightMuted, Modifier.padding(start = 8.dp), maxLines = 1, align = TextAlign.End)
            }
        }
        Spacer(Modifier.width(12.dp))
        Icon(R.drawable.ic_arrow_right, C.text.onLight, 22.dp)
    }
}
