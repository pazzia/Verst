package app.verst.feature.exit

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.HotelOptionDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.dto.TripDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.CraftBadge
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.NaviDialog
import app.verst.feature.common.PlateToast
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.toastText
import app.verst.feature.road.CraftPlate
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

/** Fork camper-ui (mockup screen 9): the night card is the dark-brown craft card with amber accents. */
private val NightFill = C.camper.ink
private val NightText = C.camper.paper
private val NightSoft = C.camper.paper.copy(alpha = 0.8f)

/**
 * 5.7 «Съезд к ночёвке», fork camper-ui (mockup screen 9): the dark-brown night card — «НОЧЁВКА N ИЗ M» and the km /
 * time badge in amber, the town, the blue exit sign (its real distance), the night's hotels as amber-framed rows —
 * and the amber booking button through the demo partner (D-13), «Забронировали?» on return (D-10).
 */
@Composable
fun ExitScreen(ui: ExitUi, a: ExitActions) {
    ScreenRoot(C.camper.page) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            Column(Modifier.fillMaxSize()) {
                val back = stringResource(R.string.common_back_road)
                BackLink(back, C.camper.ink, stringResource(R.string.cd_back, back), a::back, Modifier.padding(start = 6.dp, top = 2.dp).testTag("exit.back"))
                Panel(ui, a, Modifier.weight(1f).fillMaxWidth())
                BookCta(
                    ui, a,
                    Modifier.padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter + CraftDefaults.ShadowX, top = 8.dp, bottom = 14.dp),
                )
            }
            val t = ui.toast
            if (t != null) {
                val text = if (t is Toast.Booked) stringResource(R.string.exit_booked_toast, ui.townPrep) else toastText(t)
                PlateToast(
                    text, bottom = 14.dp + DesignTokens.size.ctaBookH + 16.dp,
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

@Composable
internal fun tagLine(o: HotelOptionDto): String {
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
    Box(modifier) {
        Column(Modifier.fillMaxWidth().verticalScroll(scroll).padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 4.dp, bottom = 12.dp)) {
            // the dark-brown craft card with the amber border (mockup `bg-[#261C14] border-[#F4A261]`)
            Column(
                Modifier.fillMaxWidth().padding(end = CraftDefaults.ShadowX, bottom = CraftDefaults.ShadowY)
                    .craftSurface(fill = NightFill, borderColor = C.camper.amber)
                    .testTag("exit.panel")
                    .padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    if (ui.offline) {
                        Txt(headerLeft + stringResource(R.string.common_join_dot) + headerRight, CraftType.overline, C.camper.amber, Modifier.weight(1f), maxLines = 1)
                        CraftBadge(stringResource(R.string.common_offline), Modifier.padding(start = 8.dp).testTag("exit.offline"))
                    } else {
                        Txt(headerLeft, CraftType.overline, C.camper.amber, Modifier.weight(1f), maxLines = 1)
                        CraftBadge(headerRight, Modifier.padding(start = 8.dp))
                    }
                }
                Txt(s.name, T.title.xl, NightText, Modifier.semantics { heading(); contentDescription = headingCd }, maxLines = 1)
                // the blue exit sign in place of the mockup's photo: the real distance to the selected hotel
                ExitSign(ui, Modifier.align(Alignment.CenterHorizontally))
                val reason = s.reason ?: s.note
                if (ui.trip.warnings.any { it.code == "NO_LODGING" && (it.day == null || it.day == s.day) }) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(18.dp).clip(RoundedCornerShape(9.dp)).background(C.camper.amber), contentAlignment = Alignment.Center) {
                            Txt("!", T.caption.bold, C.camper.onAmber)
                        }
                        Txt(stringResource(R.string.error_no_lodging), T.body.sm, NightText)
                    }
                }
                if (!reason.isNullOrBlank()) Txt(reason, T.body.md, NightSoft)
                val group = stringResource(R.string.cd_exit_group)
                Column(Modifier.selectableGroup().semantics { contentDescription = group }, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    s.hotelOptions.forEachIndexed { i, o ->
                        HotelOption(o, selected = o.placeId == ui.selectedId, booked = o.placeId == ui.bookedPlaceId, index = i) { a.select(o.placeId) }
                    }
                }
            }
        }
        // F-04: on overflow a 16 dp page-colour fade at the bottom edge (the next option peeks under it).
        if (scroll.canScrollForward) {
            Box(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(16.dp)
                    .background(Brush.verticalGradient(listOf(C.camper.page.copy(alpha = 0f), C.camper.page))),
            )
        }
    }
}

/**
 * components §12.2 HotelOption, fork camper-ui: a row of the night card — amber radio, name, tags, the crew's price per
 * night in amber mono (booked → «забронировано»); the picked row has the 2 dp amber frame on brown.
 */
@Composable
private fun HotelOption(o: HotelOptionDto, selected: Boolean, booked: Boolean, index: Int, onClick: () -> Unit) {
    val tags = tagLine(o)
    val price = app.verst.settings.AppPrefs.money(o.priceCrewRub)
    val cd = stringResource(R.string.cd_exit_option, o.name, tags, price)
    val shape = RoundedCornerShape(12.dp)
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = DesignTokens.size.hotelRowMinH)
            .clip(shape)
            .background(if (selected) C.camper.border else NightFill)
            .border(if (selected) CraftDefaults.BorderThin else 1.5.dp, if (selected) C.camper.amber else C.camper.amber.copy(alpha = 0.4f), shape)
            .selectable(selected, role = Role.RadioButton, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("exit.option.$index")
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(Modifier.size(18.dp).border(2.dp, if (selected) C.camper.amber else NightSoft, RoundedCornerShape(9.dp)), contentAlignment = Alignment.Center) {
            if (selected) Box(Modifier.size(8.dp).clip(RoundedCornerShape(4.dp)).background(C.camper.amber))
        }
        Column(Modifier.weight(1f)) {
            Txt(o.name, T.title.sm, NightText, maxLines = 1)
            if (tags.isNotEmpty()) Txt(tags, T.body.sm, NightSoft, maxLines = 2)
        }
        if (booked) {
            Txt(stringResource(R.string.exit_booked_badge), T.body.smStrong, C.camper.amber, maxLines = 1)
        } else {
            Txt(stringResource(R.string.common_estimate_rub, price), CraftType.fieldMono.copy(fontWeight = FontWeight.W700), C.camper.amber, maxLines = 1)
        }
    }
}

/**
 * components §15 `BookCta` (online / offline), fork camper-ui: an amber craft plate (the night's accent; brown text
 * keeps both lines readable) or, once booked, the paper plate «Открыть бронирование». Offline and «нет вариантов»
 * are the flat, dimmed plate.
 */
@Composable
private fun BookCta(ui: ExitUi, a: ExitActions, modifier: Modifier) {
    val source = remember { MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    if (ui.booked) {
        // 5.7 §4 Booked: the secondary look, «Открыть бронирование», arrow upRight.
        CraftPlate(
            modifier.fillMaxWidth().height(DesignTokens.size.ctaBookH)
                .clickable(source, indication = null, role = Role.Button, onClick = a::book)
                .testTag("exit.book"),
            pressed = pressed, fill = C.camper.paper, pressedFill = C.camper.header, minHeight = DesignTokens.size.ctaBookH,
            horizontalPadding = 18.dp, arrangement = Arrangement.Start,
        ) {
            Txt(stringResource(R.string.exit_book_open), T.cta.lg, C.camper.ink, Modifier.weight(1f), maxLines = 1)
            Icon(R.drawable.ic_arrow_up_right, C.camper.inkSoft, 22.dp)
        }
        return
    }
    // Mock build: no real brand anywhere (OI-40) — «демо-партнёр, без оплаты».
    val cd = stringResource(R.string.cd_exit_book_mock)
    // F-03: no hotel options → nothing to book: the offline look, «нет вариантов с вашими условиями», not pressable.
    val none = ui.stop.hotelOptions.isEmpty()
    if (none) {
        CraftPlate(
            modifier.fillMaxWidth().height(DesignTokens.size.ctaBookH).testTag("exit.book"),
            fill = C.camper.header, raised = false, minHeight = DesignTokens.size.ctaBookH, horizontalPadding = 18.dp, arrangement = Arrangement.Start,
        ) {
            Column(Modifier.weight(1f)) {
                Txt(stringResource(R.string.exit_book), T.cta.lg, C.camper.inkSoft, maxLines = 1)
                Txt(stringResource(R.string.exit_book_none), T.body.smMedium, C.camper.inkSoft, maxLines = 1)
            }
        }
        return
    }
    CraftPlate(
        modifier
            .fillMaxWidth()
            .height(DesignTokens.size.ctaBookH)
            .clickable(source, indication = null, role = Role.Button) { if (ui.offline) a.needInternet() else a.book() }
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("exit.book"),
        pressed = pressed,
        fill = if (ui.offline) C.camper.header else C.camper.amber,
        pressedFill = C.accent.yellowPressed,
        raised = !ui.offline,
        minHeight = DesignTokens.size.ctaBookH,
        horizontalPadding = 18.dp,
        arrangement = Arrangement.Start,
    ) {
        Column(Modifier.weight(1f)) {
            Txt(stringResource(R.string.exit_book), T.cta.lg, if (ui.offline) C.camper.inkSoft else C.camper.onAmber, maxLines = 1)
            if (ui.offline) {
                Txt(stringResource(R.string.common_need_internet), T.body.smMedium, C.accent.redText, maxLines = 1)
            } else {
                Txt(stringResource(R.string.exit_book_partner_mock), T.body.smMedium, C.camper.onAmber, maxLines = 1)
            }
        }
        if (!ui.offline) Icon(R.drawable.ic_arrow_up_right, C.camper.onAmber, 22.dp)
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
    val total = app.verst.settings.AppPrefs.money(o.priceCrewRub * nights)
    val pane = stringResource(R.string.cd_mock_partner, o.name, inDate, outDate, total)
    BottomSheet(stringResource(R.string.mock_partner_title), a::closePartner, "partner", windowH, badge = stringResource(R.string.mock_partner_badge), pane = pane) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Txt(stringResource(R.string.mock_partner_line), T.body.sm, C.camper.orangeText, Modifier.padding(top = 4.dp).testTag("partner.line"))
            // fork camper-ui: the booking's facts on a white-paper field (craftField)
            Column(Modifier.fillMaxWidth().craftField().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Txt(stringResource(R.string.mock_partner_hotel, o.name, s.name), T.title.sm, C.camper.ink)
                Txt(stringResource(R.string.mock_partner_dates, inDate, outDate, nights, nightsWord), T.body.md, C.camper.ink)
                Txt(stringResource(R.string.mock_partner_guests, guests), T.body.md, C.camper.ink)
                Txt(stringResource(R.string.mock_partner_price, total, nights, nightsWord), T.title.sm, C.camper.orangeText)
            }
            Txt(stringResource(R.string.mock_partner_note), T.body.md, C.camper.inkSoft)
            // the end / bottom padding keep the button's hard shadow inside the sheet
            CraftButton(
                stringResource(R.string.mock_partner_back), a::closePartner,
                Modifier.padding(end = CraftDefaults.ShadowX, bottom = CraftDefaults.ShadowY).fillMaxWidth().testTag("partner.back"),
            )
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
