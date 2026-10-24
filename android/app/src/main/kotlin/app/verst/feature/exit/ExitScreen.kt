package app.verst.feature.exit

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.paneTitle
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.HotelOptionDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.dto.TripDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.ExitScene
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.Phases
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.dashboardSurface
import app.verst.core.ui.components.naviPanel
import app.verst.core.ui.components.sceneClock
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.NaviDialog
import app.verst.feature.common.PlateToast
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.toastText
import app.verst.nav.Toast
import kotlin.math.roundToInt
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** Everything 5.7 draws (stateless). */
data class ExitUi(
    val trip: TripDto,
    val stop: StopDto,
    /** 1-based night number and the trip's night count («НОЧЁВКА 1 ИЗ 2»). */
    val night: Int,
    val nights: Int,
    /** The hotel marked as booked for this night (one per night), or null. */
    val bookedPlaceId: String?,
    val offline: Boolean,
    /** Prepositional town for «Отметим ночёвку в Ярославле…». */
    val townPrep: String,
    val partnerOpen: Boolean = false,
    val dialogOpen: Boolean = false,
    val toast: Toast? = null,
    val canUndo: Boolean = false,
) {
    val selectedId: String? get() = stop.selectedHotelId ?: stop.hotelOptions.firstOrNull()?.placeId

    /** The selected option is the booked one: the CTA re-opens the booking. */
    val booked: Boolean get() = bookedPlaceId != null && bookedPlaceId == selectedId
}

interface ExitActions {
    fun back()
    fun select(placeId: String)
    fun book()
    fun closePartner()
    fun answer(booked: Boolean)
    fun needInternet()
    fun undoBooking()
}

private val DashH = 434.dp
/** F-04: scene minimum 260 dp → dashboard top ≥ 240 dp, so two hotel options fit at 640. */
private val MinSceneTop = 240.dp

/** 5.7 «Съезд к ночёвке»: night scene with the exit sign, the night's hotels, booking through the mock partner. */
@Composable
fun ExitScreen(ui: ExitUi, a: ExitActions) {
    ScreenRoot(C.dash.base, statusBar = C.interior.liner) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val dashTop = maxOf(maxHeight - DashH, MinSceneTop)
            val overlay = ui.partnerOpen || ui.dialogOpen
            ExitScene(dashTop + 20.dp, overlay = overlay)
            val k = maxWidth.value / 390f
            val ky = minOf(1f, (dashTop + 20.dp).value / 430f)
            ExitSign(ui, Modifier.offset(x = (162 * k).dp, y = (92 * ky).dp))
            Box(Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(maxHeight - dashTop).dashboardSurface(34.dp)) {
                val back = stringResource(R.string.common_back_road)
                BackLink(back, C.text.muted, stringResource(R.string.cd_back, back), a::back, Modifier.padding(start = 16.dp, top = 8.dp).testTag("exit.back"))
                TurnSignal(overlay, Modifier.align(Alignment.TopEnd).padding(top = 20.dp, end = 24.dp))
                Panel(ui, a, Modifier.fillMaxWidth().padding(start = 14.dp, end = 14.dp, top = 54.dp, bottom = 98.dp))
                BookCta(ui, a, Modifier.align(Alignment.BottomCenter).padding(start = 14.dp, end = 14.dp, bottom = 24.dp))
            }
            val t = ui.toast
            if (t != null) {
                val text = if (t is Toast.Booked) stringResource(R.string.exit_booked_toast, ui.townPrep) else toastText(t)
                PlateToast(
                    text, bottom = 24.dp + DesignTokens.size.ctaBookH + 16.dp,
                    action = if (t is Toast.Booked && ui.canUndo) stringResource(R.string.common_undo) else null, onAction = a::undoBooking,
                )
            }
            if (ui.partnerOpen) MockPartnerSheet(ui, maxHeight, a)
            if (ui.dialogOpen) BookedDialog(ui, a)
        }
    }
}

private fun selectedOption(s: StopDto): HotelOptionDto? = s.hotelOptions.firstOrNull { it.placeId == s.selectedHotelId } ?: s.hotelOptions.firstOrNull()

/** components §12.1 distance (OI-41 `exitDistanceM`): to 100 m below 1 km («800 м»), to 0,1 km above («1,2 км»). */
@Composable
private fun distanceText(m: Int): String? = when {
    m <= 0 -> null
    m < 950 -> stringResource(R.string.exit_sign_distance_m, maxOf(100, (m / 100.0).roundToInt() * 100))
    else -> stringResource(R.string.exit_sign_distance_km, "%.1f".format(java.util.Locale.ROOT, m / 1000.0).replace('.', ','))
}

/** components §12.1 ExitSign with `motion.exitNear` (scale 0.7 → 1, (−21, −14) → 0, α 0.6 → 1, 2200 ms). */
@Composable
private fun ExitSign(ui: ExitUi, modifier: Modifier) {
    val reduced = LocalReducedMotion.current
    val near = remember { Animatable(if (reduced) 1f else 0f) }
    LaunchedEffect(Unit) {
        if (!reduced) near.animateTo(1f, tween(DesignTokens.motion.exitNear.durationMs, easing = DesignTokens.motion.exitNear.easing))
    }
    val m = DesignTokens.motion.exitNear
    val dist = distanceText(selectedOption(ui.stop)?.exitDistanceM ?: 0)
    // Unknown distance: «ночёвка» on the plate and TalkBack without «через …» (5.7 §8).
    val cd = stringResource(R.string.cd_exit_sign, ui.stop.name, dist ?: "").let { if (dist == null) it.substringBefore(" через") else it }
    Box(
        modifier
            .width(198.dp)
            .graphicsLayer {
                val p = near.value
                val s = m.fromScale + (1 - m.fromScale) * p
                scaleX = s
                scaleY = s
                translationX = m.fromDxDp.toPx() * (1 - p)
                translationY = m.fromDyDp.toPx() * (1 - p)
                alpha = m.fromAlpha + (1 - m.fromAlpha) * p
                transformOrigin = TransformOrigin(m.pivotX, m.pivotY)
            }
            .clip(RoundedCornerShape(DesignTokens.radius.r8))
            .background(C.sign.blue)
            .padding(4.dp)
            .border(DesignTokens.stroke.w2, C.sign.white, RoundedCornerShape(DesignTokens.radius.r5))
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("exit.sign")
            .padding(horizontal = 10.dp, vertical = 8.dp),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Txt(ui.stop.name, T.sign.xlTight, C.sign.white, maxLines = 1)
                    Txt(stringResource(R.string.exit_sign_centre), T.sign.mdSub, C.sign.white, maxLines = 1)
                }
                Icon(R.drawable.ic_arrow_down_right, C.sign.white, 30.dp)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(34.dp).clip(RoundedCornerShape(DesignTokens.radius.r2)).background(C.sign.white), contentAlignment = Alignment.Center) {
                    Icon(R.drawable.ic_service_hotel, C.sign.black, 24.dp)
                }
                Spacer(Modifier.width(8.dp))
                Txt(dist ?: stringResource(R.string.exit_sign_no_distance), T.sign.lgBold, C.sign.white, Modifier.testTag("exit.distance"), maxLines = 1)
            }
        }
    }
}

/** 5.7 D3: «поворотник», blinking 900 ms (on 495 ms), steady under reduced motion. Decorative. */
@Composable
private fun TurnSignal(overlay: Boolean, modifier: Modifier) {
    val clock = sceneClock(overlay)
    val reduced = LocalReducedMotion.current
    val turn = remember { PathParser().parsePathString("M14 5l7 7-7 7v-4H3V9h11z").toPath() }
    Row(
        modifier.clearAndSetSemantics {}.graphicsLayer { alpha = if (reduced) 1f else Phases.turnSignal(clock.value) },
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Canvas(Modifier.size(18.dp)) {
            val s = size.width / 24f
            scale(s, s, pivot = androidx.compose.ui.geometry.Offset.Zero) { drawPath(turn, C.signal.green) }
        }
        Txt(stringResource(R.string.exit_turn), T.body.smStrong, C.signal.green, maxLines = 1)
    }
}

@Composable
private fun tagLine(o: HotelOptionDto): String {
    val labels = o.tags.mapNotNull {
        when (it) {
            "dogs_allowed" -> stringResource(R.string.exit_tag_dogs)
            "family_room" -> stringResource(R.string.exit_tag_family)
            "parking" -> stringResource(R.string.exit_tag_parking)
            "parking_guarded" -> stringResource(R.string.exit_tag_parking_guarded)
            else -> null
        }
    }
    val all = (if (!o.verified) listOf(stringResource(R.string.common_unverified)) else emptyList()) + labels
    return all.joinToString(stringResource(R.string.common_join_dot))
}

@Composable
private fun Panel(ui: ExitUi, a: ExitActions, modifier: Modifier) {
    val s = ui.stop
    val time = RuFormat.clock(s.arriveAt) ?: ""
    val km = RuFormat.thousands(s.kmAt)
    val headerLeft = stringResource(R.string.exit_header, ui.night, ui.nights)
    val headerRight = stringResource(R.string.exit_header_km, km, time)
    val headingCd = stringResource(R.string.cd_exit_heading, ui.night, ui.nights, km, time, s.name)
    val scroll = rememberScrollState()
    Box(modifier.naviPanel().padding(6.dp)) {
    Column(
        Modifier.verticalScroll(scroll).padding(12.dp).testTag("exit.panel"),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(Modifier.fillMaxWidth()) {
            if (ui.offline) {
                Txt(headerLeft + stringResource(R.string.common_join_dot) + headerRight, T.label.md, C.navi.label, Modifier.weight(1f), maxLines = 1)
                Txt(stringResource(R.string.common_offline), T.label.md, C.accent.redText, Modifier.testTag("exit.offline"))
            } else {
                Txt(headerLeft, T.label.md, C.navi.label, Modifier.weight(1f), maxLines = 1)
                Txt(headerRight, T.label.md, C.navi.label)
            }
        }
        Txt(s.name, T.title.xl, C.text.primary, Modifier.semantics { heading(); contentDescription = headingCd }, maxLines = 1)
        val reason = s.reason ?: s.note
        if (ui.trip.warnings.any { it.code == "NO_LODGING" && (it.day == null || it.day == s.day) }) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(14.dp).clip(RoundedCornerShape(7.dp)).background(C.accent.yellow), contentAlignment = Alignment.Center) {
                    Txt("!", T.caption.bold, C.text.onLight)
                }
                Txt(stringResource(R.string.error_no_lodging), T.body.sm, C.text.primary)
            }
        }
        if (!reason.isNullOrBlank()) Txt(reason, T.body.md, C.navi.text)
        val group = stringResource(R.string.cd_exit_group)
        Column(Modifier.selectableGroup().semantics { contentDescription = group }, verticalArrangement = Arrangement.spacedBy(8.dp)) {
            s.hotelOptions.forEachIndexed { i, o ->
                HotelOption(o, selected = o.placeId == ui.selectedId, booked = o.placeId == ui.bookedPlaceId, index = i) { a.select(o.placeId) }
            }
        }
    }
    // F-04: on overflow a 16 dp `navi.screen` fade at the panel's bottom edge (the next option peeks under it).
    if (scroll.canScrollForward) {
        Box(
            Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(16.dp)
                .background(androidx.compose.ui.graphics.Brush.verticalGradient(listOf(C.navi.screen.copy(alpha = 0f), C.navi.screen))),
        )
    }
    }
}

/** components §12.2 HotelOption (radio, name, tags, crew price per night; booked → «забронировано»). */
@Composable
private fun HotelOption(o: HotelOptionDto, selected: Boolean, booked: Boolean, index: Int, onClick: () -> Unit) {
    val tags = tagLine(o)
    val price = RuFormat.thousands(o.priceCrewRub)
    val cd = stringResource(R.string.cd_exit_option, o.name, tags, price)
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = DesignTokens.size.hotelRowMinH)
            .clip(shape)
            .background(if (selected) C.navi.field else C.navi.screen)
            .border(DesignTokens.stroke.w1, if (selected) C.accent.yellow else C.navi.fieldBorder, shape)
            .selectable(selected, role = Role.RadioButton, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("exit.option.$index")
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(Modifier.size(18.dp).border(2.dp, if (selected) C.accent.yellow else C.navi.radio, RoundedCornerShape(9.dp)), contentAlignment = Alignment.Center) {
            if (selected) Box(Modifier.size(6.dp).clip(RoundedCornerShape(3.dp)).background(C.accent.yellow))
        }
        Column(Modifier.weight(1f)) {
            Txt(o.name, T.title.sm, C.text.primary, maxLines = 1)
            if (tags.isNotEmpty()) Txt(tags, T.body.sm, C.navi.labelSecondary, maxLines = 2)
        }
        if (booked) {
            Txt(stringResource(R.string.exit_booked_badge), T.body.smStrong, C.accent.yellow, maxLines = 1)
        } else {
            Txt(stringResource(R.string.common_estimate_rub, price), T.title.sm, C.accent.yellow, maxLines = 1)
        }
    }
}

/** components §15 `BookCta` (online / offline) or, once booked, a SecondaryButton «Открыть бронирование». */
@Composable
private fun BookCta(ui: ExitUi, a: ExitActions, modifier: Modifier) {
    if (ui.booked) {
        // 5.7 §4 Booked: the CTA box with the SecondaryButton look, «Открыть бронирование», arrow upRight.
        val shape = RoundedCornerShape(DesignTokens.radius.r12)
        Row(
            modifier.fillMaxWidth().height(DesignTokens.size.ctaBookH).clip(shape).background(C.dash.control)
                .border(DesignTokens.stroke.w1, C.dash.outline, shape).clickable(role = Role.Button, onClick = a::book)
                .testTag("exit.book").padding(horizontal = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Txt(stringResource(R.string.exit_book_open), T.cta.lg, C.text.primary, Modifier.weight(1f), maxLines = 1)
            Icon(R.drawable.ic_arrow_up_right, C.text.secondary, 22.dp)
        }
        return
    }
    // Mock build: no real brand anywhere (OI-40) — «демо-партнёр, без оплаты».
    val cd = stringResource(R.string.cd_exit_book_mock)
    // F-03: no hotel options → nothing to book: the offline look, «нет вариантов с вашими условиями», not pressable.
    val none = ui.stop.hotelOptions.isEmpty()
    if (none) {
        Row(
            modifier.fillMaxWidth().height(DesignTokens.size.ctaBookH).clip(RoundedCornerShape(DesignTokens.radius.r12)).background(C.dash.control)
                .testTag("exit.book").padding(horizontal = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Txt(stringResource(R.string.exit_book), T.cta.lg, C.text.secondary, maxLines = 1)
                Txt(stringResource(R.string.exit_book_none), T.body.smMedium, C.text.secondary, maxLines = 1)
            }
        }
        return
    }
    Row(
        modifier
            .fillMaxWidth()
            .height(DesignTokens.size.ctaBookH)
            .clip(RoundedCornerShape(DesignTokens.radius.r12))
            .background(if (ui.offline) C.dash.control else C.accent.yellow)
            .clickable(role = Role.Button) { if (ui.offline) a.needInternet() else a.book() }
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("exit.book")
            .padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Txt(stringResource(R.string.exit_book), T.cta.lg, if (ui.offline) C.text.secondary else C.text.onLight, maxLines = 1)
            if (ui.offline) {
                Txt(stringResource(R.string.common_need_internet), T.body.smMedium, C.accent.redText, maxLines = 1)
            } else {
                Txt(stringResource(R.string.exit_book_partner_mock), T.body.smMedium, C.text.onLight, maxLines = 1)
            }
        }
        if (!ui.offline) Icon(R.drawable.ic_arrow_up_right, C.text.onLight, 22.dp)
    }
}

/**
 * D-13 `MockPartnerSheet`: a plain demo sheet in Verst's own dashboard look — no partner logo, no partner
 * colours, no payment or personal-data fields; it says it is a demo. Values come from the trip.
 */
@Composable
private fun BoxScope.MockPartnerSheet(ui: ExitUi, windowH: Dp, a: ExitActions) {
    val s = ui.stop
    val o = selectedOption(s) ?: return
    val nights = 1
    val nightsWord = pluralStringResource(R.plurals.plural_night, nights)
    val date = s.arriveAt?.takeIf { it.length >= 10 }?.let { java.time.LocalDate.parse(it.substring(0, 10)) }
    val inDate = date?.let { shortDate(it) } ?: ""
    val outDate = date?.plusDays(1)?.let { shortDate(it) } ?: ""
    val crew = ui.trip.input.crew
    val guests = buildList {
        add(stringResource(R.string.waybill_crew_adults, crew.adults))
        if (crew.children > 0) add(stringResource(R.string.waybill_crew_children, crew.children))
        if (crew.dog) add(stringResource(R.string.waybill_crew_dog))
    }.joinToString(stringResource(R.string.common_join_comma))
    val total = RuFormat.thousands(o.priceCrewRub * nights)
    val pane = stringResource(R.string.cd_mock_partner, o.name, inDate, outDate, total)
    BottomSheet(stringResource(R.string.mock_partner_title), a::closePartner, "partner", windowH, badge = stringResource(R.string.mock_partner_badge), pane = pane) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Txt(stringResource(R.string.mock_partner_line), T.body.sm, C.navi.label, Modifier.padding(top = 4.dp).testTag("partner.line"))
            Column(Modifier.fillMaxWidth().naviPanel().padding(6.dp).padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Txt(stringResource(R.string.mock_partner_hotel, o.name, s.name), T.title.sm, C.text.primary)
                Txt(stringResource(R.string.mock_partner_dates, inDate, outDate, nights, nightsWord), T.body.md, C.navi.text)
                Txt(stringResource(R.string.mock_partner_guests, guests), T.body.md, C.navi.text)
                Txt(stringResource(R.string.mock_partner_price, total, nights, nightsWord), T.title.sm, C.accent.yellow)
            }
            Txt(stringResource(R.string.mock_partner_note), T.body.md, C.text.secondary)
            Box(
                Modifier.fillMaxWidth().height(DesignTokens.size.buttonH).clip(RoundedCornerShape(DesignTokens.radius.r12)).background(C.accent.yellow)
                    .clickable(role = Role.Button, onClick = a::closePartner).testTag("partner.back"),
                contentAlignment = Alignment.Center,
            ) { Txt(stringResource(R.string.mock_partner_back), T.cta.sm, C.text.onLight, align = TextAlign.Center) }
        }
    }
}

/** D-10 `NaviDialog` «Забронировали?». */
@Composable
private fun BoxScope.BookedDialog(ui: ExitUi, a: ExitActions) = NaviDialog(
    stringResource(R.string.exit_return_title),
    stringResource(R.string.exit_return_body, ui.townPrep),
    stringResource(R.string.exit_return_yes),
    stringResource(R.string.exit_return_no),
    "booked",
    { a.answer(true) },
    { a.answer(false) },
)


/** «7 нояб.» (`common_date_day` + `common_month_short_*`). */
@Composable
fun shortDate(d: java.time.LocalDate): String = stringResource(R.string.common_date_day, d.dayOfMonth.toString(), monthShort(d.monthValue))

@Composable
private fun monthShort(m: Int): String = stringResource(
    when (m) {
        1 -> R.string.common_month_short_01
        2 -> R.string.common_month_short_02
        3 -> R.string.common_month_short_03
        4 -> R.string.common_month_short_04
        5 -> R.string.common_month_short_05
        6 -> R.string.common_month_short_06
        7 -> R.string.common_month_short_07
        8 -> R.string.common_month_short_08
        9 -> R.string.common_month_short_09
        10 -> R.string.common_month_short_10
        11 -> R.string.common_month_short_11
        else -> R.string.common_month_short_12
    },
)
