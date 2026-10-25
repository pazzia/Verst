package app.verst.feature.road

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.layout.layout
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.DayDto
import app.verst.core.model.dto.ParkingDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.dto.TripDto
import app.verst.core.ui.R
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.SecondaryButton
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.OpenDataRing
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/*
 * 5.5 §10 (Sprint 4) parts of Road ahead: the «Вести в навигаторе» CTA and the day «вести», the km posts and the
 * car marker of decision B (§10.8), the one costs line with the inline P part (§10.7) and the ParkingSheet (§10.6).
 */

/** Stops where the car is left (5.5 §10.6): not fuel, not the start, not the finish. */
internal fun parkingStop(s: StopDto): Boolean = s.kind in setOf("sight", "food", "rest", "overnight")

/**
 * A trip with parking data (M6: the «Парковки» line exists only in `russia_v1`; fixture worlds have none, and then
 * no P part is drawn at all).
 */
internal fun parkingAware(trip: TripDto): Boolean =
    trip.cost.lines.any { it.key == "parking" } || trip.daysList.any { d -> d.stops.any { it.parking != null } }

/**
 * 5.5 §10.10 (S4-QA P1-01): in a parking-aware trip every left-the-car stop (sight, food, rest area, night) has a
 * P part, «P ?» when the engine has no tariff; fuel is the only row without it.
 */
internal fun showsParking(s: StopDto): Boolean = parkingStop(s)

/** Σ known stays of a day and the count of stops without data. */
internal data class ParkingSum(val rub: Int, val unknown: Int)

internal fun parkingOf(day: DayDto): ParkingSum {
    val stops = day.stops.filter(::showsParking)
    return ParkingSum(stops.sumOf { it.parking?.takeIf(ParkingDto::known)?.rub ?: 0 }, stops.count { it.parking?.known != true })
}

/** components §26 `HandoffCta`: yellow, full width, min-h 60: navigator arrow 26, title 18/700, sub 12/600, chevron. */
@Composable
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
internal fun HandoffCta(day: Int, onClick: () -> Unit, onLongClick: () -> Unit, modifier: Modifier = Modifier) {
    val source = remember { MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    val cd = stringResource(R.string.road_handoff_cta) + ". " + stringResource(R.string.road_handoff_cta_sub, day)
    Row(
        modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.handoffCtaH).clip(shape)
            // pressed #E6BD38 has no token: the yellow at 90 % over the dashboard reads the same (dev-notes S4)
            .background(if (pressed) C.accent.yellow.copy(alpha = 0.9f) else C.accent.yellow)
            .combinedClickable(source, indication = null, role = Role.Button, onLongClick = onLongClick, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("road.handoff")
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        GlyphIcon(Glyph.NAVIGATOR, C.text.onLight, 26.dp, filled = true)
        Column(Modifier.weight(1f)) {
            Txt(stringResource(R.string.road_handoff_cta), T.cta.lg, C.text.onLight, maxLines = 1)
            Txt(stringResource(R.string.road_handoff_cta_sub, day), T.body.smStrong, C.text.onLightMuted, maxLines = 1)
        }
        GlyphIcon(Glyph.RIGHT, C.text.onLight, 18.dp)
    }
}

/** components §26 day «вести»: min-h 36, padding 0 10, radius 18, 1 dp yellow, 12/600 + arrow 12 (touch 44). */
@Composable
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
internal fun DayGoButton(day: Int, onClick: () -> Unit, onLongClick: () -> Unit) {
    val cd = stringResource(R.string.cd_road_handoff_day, day)
    Box(
        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .combinedClickable(role = Role.Button, onLongClick = onLongClick, onClick = onClick)
            .semantics { contentDescription = cd }.testTag("road.day.$day.navigator"),
        contentAlignment = Alignment.Center,
    ) {
        Row(
            Modifier.height(36.dp).border(DesignTokens.stroke.w1, C.accent.yellow, RoundedCornerShape(18.dp)).padding(horizontal = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            GlyphIcon(Glyph.NAVIGATOR, C.accent.yellow, 12.dp, filled = true)
            Txt(stringResource(R.string.road_handoff_day), T.body.smStrong, C.accent.yellow, maxLines = 1)
        }
    }
}

/** The small blue «P» (radius 3, white bold): the inline P part 15, the day line 16, the footer 14. */
@Composable
internal fun PGlyph(size: Dp, modifier: Modifier = Modifier) {
    val fs = when {
        size >= 32.dp -> 20.sp
        size >= 15.dp -> 11.sp
        else -> 10.sp
    }
    Box(
        modifier.size(size).clip(RoundedCornerShape(if (size >= 32.dp) 4.dp else 3.dp)).background(C.sign.blue).clearAndSetSemantics {},
        contentAlignment = Alignment.Center,
    ) { Txt("P", PLetter.copy(fontSize = fs, lineHeight = fs), C.sign.white, maxLines = 1) }
}

private val PLetter = TextStyle(fontWeight = FontWeight.W700, fontSize = 11.sp, lineHeight = 11.sp)

/** The P part text: «≈ 300 ₽» / «бесплатно» / «?» (null parking with a parking-aware engine = unknown). */
@Composable
internal fun parkingInline(p: ParkingDto?): String = when {
    p == null || !p.known -> stringResource(R.string.road_parking_inline_unknown)
    p.free -> stringResource(R.string.road_parking_inline_free)
    else -> stringResource(R.string.road_parking_inline_paid, RuFormat.thousands(p.rub ?: 0))
}

@Composable
private fun parkingCd(p: ParkingDto?): String {
    val v = when {
        p == null || !p.known -> stringResource(R.string.road_parking_unknown)
        p.free -> stringResource(R.string.road_parking_inline_free)
        else -> stringResource(R.string.road_parking_inline_paid, RuFormat.thousands(p.rub ?: 0))
    }
    return stringResource(R.string.cd_road_parking_inline, v)
}

/**
 * components §26.2 `CostsLine`: price (yellow) · P part (a button → ParkingSheet), and the quiet action on the right.
 * Fuel has the price only. The P part keeps a 36 × 44 touch box.
 */
/**
 * components §26.2 `CostsLine` with 5.5 §10.10 (S4-QA P1-03): the quiet action is pinned right on the **first**
 * line and never wraps; price · P part share the rest, and when they don't fit the P part moves under the price
 * (left-aligned, no separator), still a button.
 */
@Composable
internal fun CostsLine(price: String?, parking: ParkingDto?, showParking: Boolean, tag: String, onParking: () -> Unit, action: @Composable () -> Unit) {
    val pPart: @Composable () -> Unit = {
        val unknown = parking?.known != true
        val cd = parkingCd(parking)
        Row(
            Modifier.touch36().defaultMinSize(minWidth = 36.dp)
                .clickable(role = Role.Button, onClick = onParking)
                .semantics(mergeDescendants = true) { contentDescription = cd }
                .testTag("$tag.parking")
                .padding(horizontal = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            PGlyph(15.dp)
            Txt(parkingInline(parking), T.body.mdStrong, if (unknown) C.text.muted else C.navi.text, maxLines = 1)
        }
    }
    Row(Modifier.fillMaxWidth().defaultMinSize(minHeight = 36.dp), verticalAlignment = Alignment.Top) {
        androidx.compose.ui.layout.Layout(
            content = {
                Box(Modifier.height(36.dp), contentAlignment = Alignment.CenterStart) { if (price != null) Txt(price, T.body.mdStrong, C.accent.yellow, maxLines = 1) }
                Box(Modifier.height(36.dp).padding(horizontal = 5.dp), contentAlignment = Alignment.Center) { Txt("·", T.body.mdStrong, C.interior.pole, maxLines = 1) }
                Box(Modifier.height(36.dp), contentAlignment = Alignment.CenterStart) { if (showParking) pPart() }
            },
            modifier = Modifier.weight(1f),
        ) { ms, c ->
            val loose = c.copy(minWidth = 0)
            val pr = ms[0].measure(loose)
            val dot = ms[1].measure(loose)
            val pp = ms[2].measure(loose)
            val hasPrice = price != null
            val oneLine = !showParking || !hasPrice || pr.width + dot.width + pp.width <= c.maxWidth
            val h = if (oneLine) maxOf(pr.height, pp.height) else pr.height + pp.height
            layout(c.maxWidth, h) {
                if (hasPrice) pr.place(0, 0)
                if (showParking) {
                    if (oneLine) {
                        if (hasPrice) dot.place(pr.width, 0)
                        pp.place(if (hasPrice) pr.width + dot.width else 0, 0)
                    } else {
                        pp.place(0, pr.height) // under the price, no separator
                    }
                }
            }
        }
        Box(Modifier.height(36.dp), contentAlignment = Alignment.Center) { action() }
    }
}

/** A 44 dp touch box that lays out 36 high (the costs line is min-h 36; the touch target keeps 44). */
internal fun Modifier.touch36(): Modifier = this.layout { m, c ->
    val t = DesignTokens.size.touchMin.roundToPx()
    val p = m.measure(c.copy(minHeight = t, maxHeight = if (c.hasBoundedHeight) maxOf(t, c.maxHeight) else t))
    val h = 36.dp.roundToPx()
    layout(p.width, h) { p.place(0, (h - p.height) / 2) }
}

/** components §26.2 quiet action «заменить» (12/600 muted, no border, min-h 36, touch 44). */
@Composable
internal fun QuietAction(text: String, cd: String, tag: String, color: androidx.compose.ui.graphics.Color = C.text.muted, onClick: () -> Unit, trailing: @Composable () -> Unit = {}) {
    Row(
        Modifier.touch36().clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }.testTag(tag).padding(start = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Txt(text, T.body.smStrong, color, maxLines = 1)
        trailing()
    }
}

/** The day header's parking line: P 16 + «≈ 500 ₽» / «≈ 500 ₽ + ?» (12/600 `navi.text`). */
@Composable
internal fun DayParking(day: DayDto) {
    val p = parkingOf(day)
    val text = when {
        p.rub == 0 && p.unknown == 0 -> stringResource(R.string.road_parking_inline_free) // not «≈ 0 ₽»
        p.rub == 0 -> stringResource(R.string.road_parking_inline_unknown)
        p.unknown > 0 -> stringResource(R.string.road_parking_day_unknown, RuFormat.thousands(p.rub))
        else -> stringResource(R.string.road_parking_day, RuFormat.thousands(p.rub))
    }
    Row(Modifier.testTag("road.day.${day.day}.parking"), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        PGlyph(16.dp)
        Txt(text, T.body.smStrong, C.navi.text, maxLines = 1)
    }
}

/** TalkBack of the day parking line (merged into the day header). */
@Composable
internal fun dayParkingCd(day: DayDto): String {
    val p = parkingOf(day)
    val base = stringResource(R.string.cd_road_parking_day, RuFormat.thousands(p.rub))
    return if (p.unknown > 0) base + " " + stringResource(R.string.cd_road_parking_day_unknown, p.unknown) else base
}

/** The footer block «P из них парковки / ≈ 1 620 ₽» (components §26). */
@Composable
internal fun FooterParking(rub: Int) {
    Column(Modifier.padding(start = 10.dp).testTag("road.total.parking"), horizontalAlignment = Alignment.End) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            PGlyph(14.dp)
            Txt(stringResource(R.string.road_footer_parking), T.body.smStrong, C.text.onLightMuted, maxLines = 1)
        }
        Txt(
            if (rub == 0) stringResource(R.string.road_parking_inline_free) else stringResource(R.string.common_estimate_rub, RuFormat.thousands(rub)),
            T.paper.total, C.text.onLight, maxLines = 1, align = TextAlign.End,
        )
    }
}

private val KmNumber = TextStyle(
    fontFamily = DesignTokens.font.plexMono, fontWeight = FontWeight.W600, fontSize = 10.sp, lineHeight = 11.sp, letterSpacing = (-0.02).em,
)
private val KmUnit = TextStyle(fontWeight = FontWeight.W700, fontSize = 8.sp, lineHeight = 9.sp)

/** components §26.2 `KmPost`: plate 22 × 26 white, 1.5 dp black, radius 2; Plex Mono number + «км»; post 4 × 10. */
@Composable
internal fun KmPost(km: Int, modifier: Modifier = Modifier) {
    Column(modifier.testTag("road.kmpost"), horizontalAlignment = Alignment.CenterHorizontally) {
        Column(
            Modifier.size(22.dp, 26.dp).clip(RoundedCornerShape(2.dp)).background(C.sign.white)
                .border(1.5.dp, C.sign.black, RoundedCornerShape(2.dp)),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Txt(km.toString(), KmNumber, C.text.onLight, maxLines = 1)
            Txt(stringResource(R.string.common_km_unit), KmUnit, C.text.onLight, maxLines = 1)
        }
        Box(Modifier.size(4.dp, 10.dp).background(C.sign.black).padding(horizontal = 1.dp).background(C.sign.white))
    }
}

/** The legends under the chips: the open-data ring (with «О данных») and the mini km post (5.5 §10.2, §10.8). */
@Composable
internal fun Legends(openData: Boolean, posts: Boolean, onAbout: () -> Unit, about: Boolean = true) {
    if (openData) {
        Row(Modifier.fillMaxWidth().testTag("road.legend.opendata"), verticalAlignment = Alignment.CenterVertically) {
            OpenDataRing(Modifier.padding(end = 6.dp))
            Txt(stringResource(R.string.road_open_data_legend), T.body.sm, C.text.muted, Modifier.weight(1f, fill = false))
            if (about) Box(
                Modifier.padding(start = 4.dp).defaultMinSize(minHeight = DesignTokens.size.touchMin)
                    .clickable(role = Role.Button, onClick = onAbout).testTag("road.approx.more"),
                contentAlignment = Alignment.Center,
            ) { Txt("· " + stringResource(R.string.route_approx_more), T.body.smStrong, C.navi.label, maxLines = 1) }
        }
    }
    if (posts) {
        Row(Modifier.fillMaxWidth().testTag("road.legend.kmpost"), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.padding(end = 6.dp).size(18.dp, 16.dp).clip(RoundedCornerShape(2.dp)).background(C.sign.white)
                    .border(DesignTokens.stroke.w1, C.sign.black, RoundedCornerShape(2.dp)).clearAndSetSemantics {},
                contentAlignment = Alignment.Center,
            ) { Txt("73", KmNumber.copy(fontSize = 8.sp, lineHeight = 9.sp), C.text.onLight, maxLines = 1) }
            Txt(stringResource(R.string.road_km_post_legend), T.body.sm, C.text.muted, Modifier.weight(1f))
        }
    }
}

/**
 * components §26.3 `CarMarker`: an 18 × 32 top-down car, front at the bottom (it drives down the list), in the car
 * lane x 13–31, looping over the visible road at `motion.carMarker` speed; parked at the top with reduced motion.
 */
@Composable
internal fun BoxScope.CarMarker(top: Float, bottom: Float) {
    val len = bottom - top - DesignTokens.size.carMarkerH.value
    if (len <= 0f) return
    val reduced = LocalReducedMotion.current
    val y = if (reduced) 0f else {
        val ms = (len / DesignTokens.motion.carMarker.speedDpPerS * 1000).toInt().coerceAtLeast(1000)
        val t = rememberInfiniteTransition(label = "car")
        val v by t.animateFloat(0f, 1f, infiniteRepeatable(tween(ms, easing = LinearEasing), RepeatMode.Restart), label = "carY")
        v * len
    }
    Canvas(
        Modifier.offset(x = 13.dp, y = (top + y).dp).size(DesignTokens.size.carMarkerW, DesignTokens.size.carMarkerH)
            .testTag("road.car").clearAndSetSemantics {},
    ) {
        val d = 1.dp.toPx()
        // halo: a soft drop shadow, then the 1 dp light outline
        drawRoundRect(C.sign.black.copy(alpha = 0.6f), Offset(1.75f * d, 4f * d), Size(14.5f * d, 30f * d), CornerRadius(5 * d))
        drawRoundRect(C.text.primary, Offset(0.75f * d, 0f), Size(16.5f * d, 32f * d), CornerRadius(6 * d))
        for ((x, yy) in listOf(0f to 6f, 15f to 6f, 0f to 20f, 15f to 20f)) {
            drawRoundRect(C.text.onLight, Offset(x * d, yy * d), Size(3 * d, 6 * d), CornerRadius(d))
        }
        drawRoundRect(C.accent.yellow, Offset(1.75f * d, 1f * d), Size(14.5f * d, 30f * d), CornerRadius(5 * d))
        drawRoundRect(C.text.onLight, Offset(1.75f * d, 1f * d), Size(14.5f * d, 30f * d), CornerRadius(5 * d), style = Stroke(1.5f * d))
        drawRoundRect(C.text.onLight.copy(alpha = 0.85f), Offset(4.5f * d, 4.5f * d), Size(9 * d, 3.5f * d), CornerRadius(1.5f * d))
        // the roof (#FFE27A has no token: the yellow lightened over white)
        drawRoundRect(C.sign.white.copy(alpha = 0.35f), Offset(5 * d, 10 * d), Size(8 * d, 8 * d), CornerRadius(2 * d))
        drawPath(
            Path().apply { moveTo(4f * d, 26f * d); lineTo(14f * d, 26f * d); lineTo(12.5f * d, 21.5f * d); lineTo(5.5f * d, 21.5f * d); close() },
            C.text.onLight.copy(alpha = 0.85f),
        )
        drawRoundRect(C.text.primary, Offset(3.5f * d, 28f * d), Size(3 * d, 1.6f * d), CornerRadius(0.8f * d))
        drawRoundRect(C.text.primary, Offset(11.5f * d, 28f * d), Size(3 * d, 1.6f * d), CornerRadius(0.8f * d))
    }
}

/**
 * components §26 `ParkingSheet`: the big sign + plate, «ПАРКОВКА», the stop's detail, the rows Тариф / Стоим /
 * Воскресенье / Где (what we know), the note and «Понятно». Unknown: the rows say what we don't know.
 */
@Composable
internal fun BoxScope.ParkingSheet(s: StopDto, windowH: Dp, onClose: () -> Unit) {
    val p = s.parking
    val known = p?.known == true
    val hours = p?.hours ?: (s.dwellMin / 60.0)
    val h = kotlin.math.ceil(hours).toInt().coerceAtLeast(1)
    val detail = when {
        !known -> stringResource(R.string.road_parking_unknown)
        p!!.free -> p.freeRu ?: stringResource(R.string.road_parking_free)
        // M6: `zoneRu` is the engine's whole sentence («Москва: платная зона …, 380 ₽/ч с 08:00 до 21:00»)
        p.zoneRu != null -> p.zoneRu!!
        else -> stringResource(R.string.road_parking_zone, stringResource(R.string.road_parking_zone_default), RuFormat.thousands(p.rubPerHour ?: 0), h)
    }
    BottomSheet(s.name, onClose, "parking", windowH) {
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Box(
                    Modifier.size(52.dp).clip(RoundedCornerShape(6.dp)).background(C.sign.blue).padding(3.dp)
                        .border(DesignTokens.stroke.w2, C.sign.white, RoundedCornerShape(4.dp)),
                    contentAlignment = Alignment.Center,
                ) { Txt("P", PLetter.copy(fontSize = 32.sp, lineHeight = 32.sp), C.sign.white, maxLines = 1) }
                Box(
                    Modifier.offset(y = (-1).dp).defaultMinSize(minWidth = 64.dp).height(24.dp).clip(RoundedCornerShape(3.dp)).background(C.sign.white)
                        .border(DesignTokens.stroke.w2, C.sign.black, RoundedCornerShape(3.dp)).padding(horizontal = 6.dp),
                    contentAlignment = Alignment.Center,
                ) { Txt(parkingInline(p), T.paper.total, if (known) C.text.onLight else C.text.onLightMuted, maxLines = 1) }
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Txt(stringResource(R.string.road_parking_sheet_label), T.label.md, C.text.muted, maxLines = 1)
                Txt(detail, T.body.md, C.navi.text, Modifier.testTag("parking.detail"))
            }
        }
        val rows = buildList {
            add(stringResource(R.string.road_parking_row_rate) to when {
                !known -> stringResource(R.string.road_parking_unknown)
                p!!.free -> stringResource(R.string.road_parking_inline_free)
                else -> stringResource(R.string.road_parking_paid, RuFormat.thousands(p.rubPerHour ?: 0), RuFormat.thousands(p.rub ?: 0))
            })
            add(stringResource(R.string.road_parking_row_stay) to stringResource(R.string.common_hours_approx, h))
            p?.sundayRu?.let { add(stringResource(R.string.road_parking_row_sunday) to it) }
            p?.whereRu?.let { add(stringResource(R.string.road_parking_row_where) to it) }
        }
        Column(
            Modifier.padding(top = 14.dp).fillMaxWidth().clip(RoundedCornerShape(DesignTokens.radius.r12)).background(C.dash.face)
                .border(DesignTokens.stroke.w1, C.dash.controlAlt, RoundedCornerShape(DesignTokens.radius.r12)),
        ) {
            rows.forEachIndexed { i, (k, v) ->
                if (i > 0) Box(Modifier.fillMaxWidth().height(1.dp).background(C.dash.controlAlt))
                Row(
                    Modifier.fillMaxWidth().defaultMinSize(minHeight = 44.dp).semantics(mergeDescendants = true) {}.padding(horizontal = 14.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Txt(k, T.body.step, C.text.secondary, maxLines = 1)
                    Spacer(Modifier.width(12.dp))
                    Txt(v, T.body.step.copy(fontWeight = FontWeight.W600), C.text.primary, Modifier.weight(1f), align = TextAlign.End)
                }
            }
        }
        // S4-QA P1-04: an unknown tariff is not «уже в сумме»
        Txt(
            p?.noteRu ?: stringResource(if (known) R.string.road_parking_note else R.string.road_parking_note_unknown),
            T.body.smRelaxed, C.text.muted, Modifier.padding(top = 10.dp).testTag("parking.note"),
        )
        SecondaryButton(stringResource(R.string.road_parking_ok), onClose, Modifier.padding(top = 14.dp).fillMaxWidth().testTag("parking.ok"))
    }
}
