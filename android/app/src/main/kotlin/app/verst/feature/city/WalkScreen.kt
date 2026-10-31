package app.verst.feature.city

import androidx.compose.animation.core.animateFloat
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
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
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.HandoffDto
import app.verst.core.model.dto.WalkRouteDto
import app.verst.core.model.dto.WalkStopDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.CraftBadge
import app.verst.core.ui.components.CraftBadgeColor
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftIconTile
import app.verst.core.ui.components.CraftSecondaryButton
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.InfoChip
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.WalkerIcon
import app.verst.core.ui.components.craftShadow
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.card.CardActions
import app.verst.feature.card.CardSheet
import app.verst.feature.card.CardUi
import app.verst.feature.common.HoursPill
import app.verst.feature.common.HoursState
import app.verst.feature.common.IconButton44
import app.verst.feature.common.KindTag
import app.verst.feature.common.PlateToast
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.crewShort
import app.verst.feature.common.cuisineWords
import app.verst.feature.common.kindWord
import app.verst.feature.common.toastText
import app.verst.nav.CityPicker
import app.verst.nav.DOG_WALK
import app.verst.nav.HandoffTarget
import app.verst.nav.Toast
import app.verst.nav.WalkFew
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
    /** S4 5.11 §10: the filter bar's values (duration, preset, crew) and the open picker. */
    val filters: PickerUi? = null,
    val picker: CityPicker? = null,
    /** «Другой вариант» found nothing new (disabled + note). */
    val otherNone: Boolean = false,
    /** `NOT_ENOUGH_POIS` after a filter change: the plate replaces the column. */
    val few: WalkFew? = null,
    val excludedCount: Int = 0,
    /** CEO 29.10: the maps app the walk opens in (the same preference as the car: Яндекс Карты or Google Карты). */
    val maps: app.verst.nav.HandoffApp = app.verst.nav.HandoffApp.MAPS,
)

interface WalkActions : PickerActions {
    fun back()
    fun save()
    fun share()
    fun stop(s: WalkStopDto)
    fun handoff(part: Int)
    fun other()
    fun card(): CardActions
    fun focusShown() = Unit
    fun openPicker(p: CityPicker) = Unit
    fun suggestion(s: app.verst.core.model.dto.WalkSuggestion) = Unit
    fun dogWalk() = Unit
    override fun duration(min: Int?) = Unit
    override fun preset(p: String) = Unit
    override fun adults(n: Int) = Unit
    override fun children(n: Int) = Unit
    override fun dog(on: Boolean) = Unit
    override fun pace(p: String) = Unit
    override fun budget(rub: Int?) = Unit
    override fun closePicker() = Unit
}

/** The walker's lane inside the stops card: its width and the lane's centre from the card's left edge. */
private val LaneW = 34.dp
private val LaneX = 17.dp

/** The walker disc (no generated token yet; the car's is `size.carMarkerW/H`). */
private val WalkerSize = 26.dp

/** The numbered stop discs: 1 orange, 2 amber, 3 green, then again (mockup screen 11). */
private val StopDisc = 28.dp

/**
 * 5.11 «Прогулка», camper fork (mockup screen 11): the header card (green «ПЕШКОМ · город», the engine's title,
 * a green badge), the filter chips and the hand-off, then the stops as numbered discs in one craft card — the
 * walker rides the card's lane with the scroll — «Другой вариант» and the cost card below. The app header and the
 * tab bar are drawn around the screen by `VerstRoot`.
 */
@Composable
fun WalkScreen(ui: WalkUi, a: WalkActions) {
    val w = ui.walk
    val scroll = rememberScrollState()
    val rows = remember(w.id) { mutableStateMapOf<String, Int>() }
    var content by remember { mutableStateOf<LayoutCoordinates?>(null) }
    // CEO 29.10: the walker rides the walk column like the car on Road ahead — the column's place in the list
    var viewportH by remember { mutableStateOf(0) }
    var section by remember { mutableStateOf(0 to 0) }
    val density = LocalDensity.current
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
    val gutter = CraftDefaults.ScreenGutter
    ScreenRoot(C.camper.page) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val windowH = maxHeight
            Column(Modifier.fillMaxSize()) {
                Box(Modifier.weight(1f).fillMaxWidth().onSizeChanged { viewportH = it.height }) {
                    Column(
                        Modifier.fillMaxSize().verticalScroll(scroll).testTag("walk.list").onGloballyPositioned { content = it },
                    ) {
                        TopBar(ui, a)
                        Column(Modifier.fillMaxWidth().padding(horizontal = gutter), verticalArrangement = Arrangement.spacedBy(CraftDefaults.Gap)) {
                            HeaderCard(w)
                            Intro(ui, a)
                        }
                        Spacer(Modifier.height(CraftDefaults.Gap))
                        // S3-FINAL P2-02: every stop has default hours → the top line says it once, rows stay quiet
                        val allDefaultHours = w.stops.filter { it.poiId != null }.let { st -> st.isNotEmpty() && st.all { !it.hoursVerified } }
                        val few = ui.few
                        if (few != null) {
                            // 5.11 §10.5: the plate replaces the column; no cost footer, no «Другой вариант»
                            Box(Modifier.padding(horizontal = gutter)) { FewPlate(few, ui.filters?.selected ?: w.preset, ui.excludedCount, a::suggestion) }
                            Spacer(Modifier.height(24.dp))
                        } else {
                            Box {
                                // 5.11 §10.2: while rebuilding the previous walk stays, dimmed to 35 %, under the pill
                                Column(Modifier.fillMaxWidth().dimmed(ui.building)) {
                                    Column(
                                        Modifier.padding(horizontal = gutter).fillMaxWidth().craftSurface().walkLane()
                                            .onGloballyPositioned { c -> content?.let { root -> if (root.isAttached && c.isAttached) section = root.localPositionOf(c, Offset.Zero).y.roundToInt() to c.size.height } }
                                            .padding(top = 12.dp, bottom = 12.dp, end = 12.dp),
                                    ) {
                                        val start = RuFormat.clock(w.startAt) ?: ""
                                        val finish = RuFormat.clock(w.endAt) ?: ""
                                        Txt(
                                            when {
                                                w.untimed -> stringResource(R.string.walk_untimed_header)
                                                w.startsTomorrow() -> stringResource(R.string.walk_header_tomorrow, start, finish)
                                                else -> stringResource(R.string.walk_header, start, finish)
                                            },
                                            CraftType.overline, C.camper.orangeText,
                                            Modifier.padding(start = LaneW, bottom = 6.dp).semantics { heading() }.testTag("walk.header"),
                                        )
                                        EndRow(stringResource(R.string.walk_start_row), w.start.label ?: w.townName ?: "", if (w.untimed) "" else start, R.drawable.ic_ui_location_arrow)
                                        val dog = ui.filters?.dog == true
                                        w.stops.forEachIndexed { i, s ->
                                            WalkStopRow(
                                                s, i, s.id == highlight, allDefaultHours, w.untimed, dog,
                                                requesters.getOrPut(s.id) { FocusRequester() }, { content }, { y -> if (rows[s.id] != y) rows[s.id] = y },
                                            ) { a.stop(s) }
                                        }
                                        val fin = w.finish
                                        if (fin != null) EndRow(stringResource(R.string.walk_finish_row), fin.label ?: "", if (w.untimed) "" else finish, R.drawable.ic_ui_tent)
                                    }
                                    Spacer(Modifier.height(CraftDefaults.Gap))
                                    Box(Modifier.padding(horizontal = gutter)) {
                                        if (ui.otherNone) {
                                            OtherNone()
                                        } else {
                                            CraftSecondaryButton(
                                                stringResource(R.string.walk_other), a::other, Modifier.fillMaxWidth().testTag("walk.other"),
                                                icon = R.drawable.ic_ui_route, enabled = !ui.building,
                                            )
                                        }
                                    }
                                    Spacer(Modifier.height(24.dp))
                                }
                                if (ui.building) RebuildPill(Modifier.align(Alignment.TopStart).padding(start = gutter + LaneW, end = gutter + 12.dp, top = 30.dp))
                            }
                        }
                    }
                    // CEO 29.10: the walker rides the visible part of the stops card's lane with the scroll
                    val (secY, secH) = section
                    if (ui.few == null && secH > 0 && viewportH > 0) {
                        val top = with(density) { (secY - scroll.value).coerceAtLeast(0).toDp().value }
                        val bottom = with(density) { (secY + secH - scroll.value).coerceAtMost(viewportH).toDp().value }
                        WalkerMarker(top, bottom, if (scroll.maxValue > 0) scroll.value.toFloat() / scroll.maxValue else 0f)
                    }
                }
                if (ui.few == null) Footer(w)
            }
            val t = ui.toast
            if (t != null) PlateToast(toastText(t), bottom = 24.dp + DesignTokens.size.ctaWaybillH + 16.dp)
            val c = ui.card
            if (c != null) CardSheet(c, windowH, a.card())
            val pk = ui.picker
            val f = ui.filters
            if (pk != null && f != null) CityPickerSheet(pk, f, windowH, a)
        }
    }
}

/** Back to «По городу», save and share (44 dp targets). */
@Composable
private fun TopBar(ui: WalkUi, a: WalkActions) {
    Row(Modifier.fillMaxWidth().padding(start = 6.dp, end = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        val back = stringResource(R.string.city_title)
        BackLink(back, C.camper.inkSoft, stringResource(R.string.cd_back, back), a::back, Modifier.testTag("walk.back"))
        Spacer(Modifier.weight(1f))
        IconButton44(
            Glyph.BOOKMARK, if (ui.saved) C.camper.orangeText else C.camper.border,
            stringResource(if (ui.saved) R.string.cd_road_saved else R.string.cd_road_save), "walk.save", filled = ui.saved, onClick = a::save,
        )
        IconButton44(Glyph.SHARE, C.camper.border, stringResource(R.string.cd_road_share), "walk.share", onClick = a::share)
    }
}

/**
 * The header card (mockup «Пешеходный режим»): the green walker tile, «ПЕШКОМ · ЯРОСЛАВЛЬ», the engine's title up
 * to 2 lines and the green badge (the duration of a timed walk, else the number of places); TalkBack: «title, ≈ km».
 */
@Composable
private fun HeaderCard(w: WalkRouteDto) {
    val kmText = stringResource(R.string.common_km_approx, km(w.walkKm))
    val overline = listOfNotNull(stringResource(R.string.city_plate_kind), w.townName).joinToString(" · ").uppercase()
    val badge = if (w.untimed) "${w.stops.size} ${pluralStringResource(R.plurals.plural_place, w.stops.size)}"
    else stringResource(R.string.walk_chip_duration_text, hours(w.durationMin))
    CraftCard(Modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth().semantics(mergeDescendants = true) { heading(); contentDescription = "${w.titleRu}, $kmText" },
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CraftIconTile(R.drawable.ic_tourist_walk, active = false, size = 36.dp, fill = C.camper.green, tint = C.camper.onOrange)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Txt(overline, CraftType.overline, C.camper.greenText, maxLines = 1)
                Txt(w.titleRu, CraftType.cardTitle, C.camper.ink, Modifier.testTag("walk.title"), maxLines = 2)
            }
            Spacer(Modifier.width(8.dp))
            CraftBadge(badge, color = CraftBadgeColor.GREEN)
        }
    }
}

/** components §29 rebuild pill, craft: orange pulsing dot + «Пересобираем прогулку…» over the dimmed column. */
@Composable
private fun RebuildPill(modifier: Modifier) {
    val reduced = LocalReducedMotion.current
    val m = DesignTokens.motion.rebuildPulse
    val pulse = if (reduced) m.toAlpha else {
        val t = androidx.compose.animation.core.rememberInfiniteTransition(label = "rebuild")
        val v by t.animateFloat(
            m.fromAlpha, m.toAlpha,
            androidx.compose.animation.core.infiniteRepeatable(androidx.compose.animation.core.tween(m.durationMs / 2, easing = m.easing), androidx.compose.animation.core.RepeatMode.Reverse),
            label = "dot",
        )
        v
    }
    Row(
        modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .craftSurface(C.camper.field, radius = 22.dp, border = CraftDefaults.BorderThin)
            .padding(horizontal = 16.dp).testTag("walk.rebuilding"),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(Modifier.size(10.dp).clip(CircleShape).background(C.camper.orange.copy(alpha = pulse / m.toAlpha)))
        Txt(stringResource(R.string.walk_rebuilding), DesignTokens.type.body.mdStrong, C.camper.ink, maxLines = 1)
    }
}

/** «Другой вариант» used up: a dashed, disabled craft button with the note (components §29). */
@Composable
private fun OtherNone() {
    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(
            Modifier.fillMaxWidth().height(CraftDefaults.ButtonHeight).clip(RoundedCornerShape(CraftDefaults.ButtonRadius)).drawBehind {
                val sw = CraftDefaults.BorderThin.toPx()
                drawRoundRect(
                    C.camper.border.copy(alpha = 0.5f), Offset(sw / 2, sw / 2), Size(size.width - sw, size.height - sw),
                    CornerRadius(CraftDefaults.ButtonRadius.toPx()),
                    style = Stroke(sw, pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 4.dp.toPx()))),
                )
            }.semantics { disabled() }.testTag("walk.other.none"),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.walk_other_none), CraftType.buttonSecondary, C.camper.inkMuted, maxLines = 1) }
        Txt(stringResource(R.string.walk_other_none_note), CraftType.caption, C.camper.inkMuted, align = TextAlign.Center)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Intro(ui: WalkUi, a: WalkActions) {
    val w = ui.walk
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        val f = ui.filters
        if (f != null) {
            // 5.11 §10.1: the filter bar (duration, preset, crew); a change rebuilds the walk on this screen
            Row(
                Modifier.horizontalScroll(rememberScrollState()).semantics { contentDescription = "" },
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(durationLabel(f.durationMin), "walk.filter.duration") { a.openPicker(CityPicker.DURATION) }
                FilterChip(presetName(f.selected, w.titleRu), "walk.filter.preset") { a.openPicker(CityPicker.PRESET) }
                FilterChip(crewShort(f.adults, f.children, f.dog), "walk.filter.crew") { a.openPicker(CityPicker.CREW) }
            }
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            // S3-QA2: half hours with the decimal comma («5,5 ч»), whole hours without «,0» (the header badge)
            InfoChip(stringResource(R.string.walk_chip_km, km(w.walkKm)))
            if (w.returnToStart) InfoChip(stringResource(R.string.walk_chip_back))
            if (w.adultOnly) CraftBadge(stringResource(R.string.city_badge_18), Modifier.align(Alignment.CenterVertically), CraftBadgeColor.AMBER)
        }
        Txt(stringResource(R.string.walk_approx), CraftType.caption, C.camper.inkMuted)
        if (w.shorterThanAsked) {
            // «places» → the deck sentence; another reason (budget) → the engine's own sentence
            val sh = w.shorter
            val engineText = sh?.messageRu?.takeIf { sh.reason != "places" }
            val text = engineText
                ?: stringResource(R.string.walk_shorter, hours(sh?.actualMin ?: w.durationMin), hours(sh?.requestedMin ?: w.requestedMin ?: 0))
            Txt(text, CraftType.caption, C.camper.inkMuted, Modifier.testTag("walk.shorter"))
        }
        if (w.untimed) {
            Txt(stringResource(R.string.walk_untimed_facts, "${w.stops.size} ${pluralStringResource(R.plurals.plural_place, w.stops.size)}", km(w.walkKm)), CraftType.caption, C.camper.inkMuted, Modifier.testTag("walk.untimed.facts"))
        }
        // L3a: the walk hand-off, one button per part when the engine split the walk
        val parts = ui.handoff?.parts.orEmpty()
        val label = when (ui.target) {
            HandoffTarget.Maps, HandoffTarget.MapsDryRun -> stringResource(R.string.handoff_walk_cta)
            HandoffTarget.Google, HandoffTarget.GoogleDryRun -> stringResource(R.string.handoff_walk_cta_google)
            else -> stringResource(if (ui.maps == app.verst.nav.HandoffApp.GOOGLE) R.string.handoff_google_web else R.string.handoff_web)
        }
        if (parts.size > 1) {
            parts.forEach { p ->
                // the part on its own line: «Открыть Яндекс Карты в браузере» / «Часть 1 из 2 · до …» (never clipped);
                // CEO 31.10: the part names where it ends, the last one of a round walk «обратно к старту»
                val end = p.points.lastOrNull()
                val sub = when {
                    end?.role == "destination" && w.returnToStart -> stringResource(R.string.handoff_part_back, p.index, parts.size)
                    !end?.nameRu.isNullOrBlank() -> stringResource(R.string.handoff_part_to, p.index, parts.size, end?.nameRu.orEmpty())
                    else -> stringResource(R.string.handoff_part, p.index, parts.size)
                }
                WalkCta(label, "walk.handoff.${p.index}", sub) { a.handoff(p.index) }
            }
        } else {
            WalkCta(label, "walk.handoff") { a.handoff(1) }
        }
        val note = w.responsibleNoteRu
        if (note != null) {
            // L4: the responsible plate, first and not dismissible (fixed copy)
            Row(
                Modifier.fillMaxWidth()
                    .craftSurface(C.camper.field, radius = 14.dp, border = CraftDefaults.BorderThin, borderColor = C.camper.orangeText, shadow = null)
                    .padding(horizontal = 12.dp, vertical = 10.dp).testTag("walk.responsible"),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                CraftBadge(stringResource(R.string.city_badge_18), color = CraftBadgeColor.AMBER)
                // S3-FINAL P2-01: «За руль — только трезвым» never breaks before the dash
                Txt(stringResource(R.string.walk_responsible).replace(" —", " —"), CraftType.body, C.camper.ink)
            }
        }
        CrewPlates(ui, a)
        for (warn in w.warnings) {
            if (warn.code == "PRICE_UNKNOWN") {
                // CEO 29.10: OSM gives no prices for cafés and restaurants — our copy (RU / EN), the same plate
                WarningBox(stringResource(R.string.walk_warn_price_unknown), "walk.warn.price")
                continue
            }
            val m = warn.messageRu ?: continue
            if (warn.code in CrewWarningCodes) continue // the crew plates above
            if (warn.code == "SHORTER_THAN_ASKED") continue // said once, by the note under the ±15 % line (5.11 §9)
            if (warn.code == "HOURS_UNVERIFIED") {
                // S3-QA P2-08: only when a stop really has default hours, as a muted line (not a plate)
                if (w.stops.any { !it.hoursVerified && it.poiId != null }) Txt(m, CraftType.caption, C.camper.inkMuted, Modifier.testTag("walk.hours"))
                continue
            }
            WarningBox(m)
        }
    }
}

/** An engine walk warning: a paper plate with the sentence. */
@Composable
private fun WarningBox(text: String, tag: String? = null) {
    Box(
        Modifier.fillMaxWidth().craftSurface(C.camper.field, radius = 14.dp, border = CraftDefaults.BorderThin, shadow = null)
            .then(if (tag != null) Modifier.testTag(tag) else Modifier).padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Txt(text, CraftType.body, C.camper.inkSoft)
    }
}

private val CrewWarningCodes = setOf("CHILD_BARS", "DOG_INDOOR", "CHILD_ADAPTED", "CHILD_MUSEUMS", "DOG_ADAPTED")

/**
 * 5.11 §10.4: yellow plates for what may get in the way, green ones for how the walk was adapted. The engine's
 * v3 codes decide; with an older engine the same facts are read off the stops (the dog and indoor places).
 */
@Composable
private fun CrewPlates(ui: WalkUi, a: WalkActions) {
    val w = ui.walk
    val f = ui.filters ?: return
    val codes = w.warnings.map { it.code }.toSet()
    val indoor = w.stops.count { it.indoor }
    if (f.children > 0 && ("CHILD_BARS" in codes || w.adultOnly)) WalkWarningPlate(stringResource(R.string.walk_warn_child_bars), "walk.warn.childbars")
    val dogPlate = f.dog && ("DOG_INDOOR" in codes || indoor > 0) && indoor > 0
    if (dogPlate) {
        val actions = buildList {
            if (f.presets.any { it.preset == DOG_WALK }) add(stringResource(R.string.walk_action_dog_walk) to { a.preset(DOG_WALK) })
            add(stringResource(R.string.walk_action_dog_home) to { a.dog(false) })
        }
        WalkWarningPlate(stringResource(R.string.walk_warn_dog_count, indoor), "walk.warn.dog", actions)
    }
    if ("CHILD_ADAPTED" in codes) WalkInfoPlate(stringResource(R.string.walk_info_child), "walk.info.child")
    if ("CHILD_MUSEUMS" in codes) WalkInfoPlate(stringResource(R.string.walk_info_child_museums), "walk.info.childmuseums")
    val dogInfo = "DOG_ADAPTED" in codes || w.preset == DOG_WALK
    if (dogInfo) WalkInfoPlate(stringResource(R.string.walk_info_dog), "walk.info.dog")
    // M4 crew notes; the dog one only when no dog plate above already speaks about the dog
    w.crewNotesRu.filterNot { (dogPlate || dogInfo) && it.contains("собак", ignoreCase = true) }.forEachIndexed { i, n -> WalkInfoPlate(n, "walk.crew.note.$i") }
}

/** components §29 `WalkFilterChip`, craft: white paper chip (h 44, brown border), the value and a chevron-down. */
@Composable
private fun FilterChip(text: String, tag: String, onClick: () -> Unit) {
    val shape = RoundedCornerShape(CraftDefaults.ChipRadius)
    Row(
        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clip(shape).background(C.camper.field)
            .border(CraftDefaults.BorderThin, C.camper.border, shape)
            .clickable(role = Role.Button, onClick = onClick).testTag(tag).padding(start = 12.dp, end = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Txt(text, DesignTokens.type.body.smStrong, C.camper.ink, maxLines = 1)
        GlyphIcon(Glyph.CHEVRON_DOWN, C.camper.border, 12.dp)
    }
}

/**
 * The walk hand-off as the orange craft button (the walker, the label up to 2 lines; a part's «Часть 1 из 2 · до …»
 * on its own line under the label).
 */
@Composable
private fun WalkCta(text: String, tag: String, sub: String? = null, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = if (sub == null) CraftDefaults.ButtonHeight else 60.dp)
            .craftSurface(C.camper.orange, radius = CraftDefaults.ButtonRadius, shadow = C.camper.border)
            .clickable(role = Role.Button, onClick = onClick).testTag(tag).padding(horizontal = 16.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        WalkerIcon(C.camper.onOrange, 18.dp)
        Spacer(Modifier.width(8.dp))
        if (sub == null) {
            Txt(text, CraftType.button, C.camper.onOrange, maxLines = 2, align = TextAlign.Center)
        } else {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Txt(text, CraftType.button, C.camper.onOrange, maxLines = 1)
                Txt(sub, CraftType.caption, C.camper.onOrange, maxLines = 1)
            }
        }
    }
}

/**
 * CEO 29.10: the walker on the stops card's lane, as the car on Road ahead (components §26.3 `CarMarker`): a 26 dp
 * orange craft disc with the pedestrian glyph (`walker`, §17.5) centred on the lane. It does not walk by itself —
 * it stands still and moves only with the scroll, at [progress] (0 = the list top, 1 = its end) of the visible
 * card between [top] and [bottom] (dp in the list's viewport), so it is where the reader is in the walk. No time
 * animation, so nothing changes with reduced motion.
 */
@Composable
private fun WalkerMarker(top: Float, bottom: Float, progress: Float) {
    val len = bottom - top - WalkerSize.value
    if (len <= 0f) return
    val y = progress.coerceIn(0f, 1f) * len
    Box(
        Modifier.offset(x = CraftDefaults.ScreenGutter + LaneX - WalkerSize / 2, y = (top + y).dp).size(WalkerSize)
            .drawBehind {
                val r = size.minDimension / 2
                // the hard 2 × 2 dp shadow, the orange disc, its brown rim
                drawCircle(C.camper.border, r, center + Offset(2f * density, 2f * density))
                drawCircle(C.camper.orange, r)
                drawCircle(C.camper.border, r - 1f * density, style = Stroke(2f * density))
            }
            .testTag("walk.walker").clearAndSetSemantics {},
        contentAlignment = Alignment.Center,
    ) { WalkerIcon(C.camper.onOrange, 16.dp) }
}

/** The walker's lane: a dashed footpath down the left of the stops card. */
private fun Modifier.walkLane(): Modifier = drawBehind {
    val x = LaneX.toPx()
    val top = 14.dp.toPx()
    val bottom = size.height - 14.dp.toPx()
    if (bottom > top) {
        drawLine(
            C.camper.border.copy(alpha = 0.35f), Offset(x, top), Offset(x, bottom), strokeWidth = 2.dp.toPx(), cap = StrokeCap.Round,
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(4.dp.toPx(), 5.dp.toPx())),
        )
    }
}

/** A numbered stop disc (mockup: 1 orange, 2 amber, 3 green). */
@Composable
private fun StopNumber(n: Int) {
    val (fill, fg) = when ((n - 1) % 3) {
        0 -> C.camper.orange to C.camper.onOrange
        1 -> C.camper.amber to C.camper.onAmber
        else -> C.camper.green to C.camper.onOrange
    }
    Box(
        Modifier.size(StopDisc).craftShadow(StopDisc / 2, CraftDefaults.TileShadow, CraftDefaults.TileShadow, C.camper.border)
            .clip(CircleShape).background(fill).border(CraftDefaults.BorderThin, C.camper.border, CircleShape),
        contentAlignment = Alignment.Center,
    ) { Txt(n.toString(), CraftType.badge, fg, maxLines = 1) }
}

/** The start / finish row: a paper icon tile in the disc column, «старт · 11:00», the place. */
@Composable
private fun EndRow(kind: String, name: String, time: String, @androidx.annotation.DrawableRes icon: Int) {
    Row(
        Modifier.fillMaxWidth().padding(start = LaneW, top = 6.dp, bottom = 6.dp).semantics(mergeDescendants = true) {},
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(StopDisc), contentAlignment = Alignment.Center) { CraftIconTile(icon, active = false, size = 26.dp) }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Row(Modifier.fillMaxWidth()) {
                Txt(kind, CraftType.caption, C.camper.inkMuted, Modifier.weight(1f))
                Txt(time, CraftType.caption, C.camper.inkMuted, align = TextAlign.End)
            }
            Txt(name, CraftType.cardTitle, C.camper.ink, maxLines = 2)
        }
    }
}

@Composable
private fun WalkStopRow(
    s: WalkStopDto, index: Int, focused: Boolean, hideHoursNote: Boolean, untimed: Boolean, dog: Boolean,
    focusRequester: FocusRequester, content: () -> LayoutCoordinates?, onPlaced: (Int) -> Unit, onTap: () -> Unit,
) {
    val line = stringResource(R.string.walk_next, distance(s.walkKmFromPrev), s.walkMinFromPrev)
    val time = if (untimed) "" else RuFormat.clock(s.arriveAt) ?: ""
    // CEO 29.10: an unknown price (OSM cafés, restaurants) is «цена не указана» — never 0 ₽ or nothing at all
    val cost = if (s.costRub > 0 && !s.priceUnknown) stringResource(R.string.walk_footer_total, app.verst.settings.AppPrefs.money(s.costRub)) else null
    val priceUnknown = if (s.priceUnknown) stringResource(R.string.walk_stop_price_unknown) else null
    val kindText = s.poiKindRu?.uppercase() ?: kindWord(s.poiKind ?: s.kind)
    val cuisine = if (s.isFood) cuisineWords(s.cuisine) else null
    val cd = listOfNotNull(line, time, s.nameRu, cuisine, s.noteRu, cost, priceUnknown).joinToString(", ")
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
            .padding(start = LaneW, top = 8.dp, bottom = 10.dp)
            .semantics(mergeDescendants = true) {
                contentDescription = cd
                if (s.tappable) onClick { onTap(); true }
            }
            .focusRequester(focusRequester)
            .focusable()
            .testTag("walk.stop.${s.id}"),
    ) {
        StopNumber(index + 1)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Txt(line, CraftType.caption, C.camper.inkMuted, Modifier.weight(1f), maxLines = 1)
                Txt(time, DesignTokens.type.body.smStrong, C.camper.orangeText, align = TextAlign.End)
            }
            Txt(s.nameRu, CraftType.cardTitle, C.camper.ink, maxLines = 2)
            // S4 5.11 §10.3: the category tag; timed rows «открыто до 20:00», untimed rows the hours pill
            val hours = s.hours
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                kindText?.let { KindTag(it) }
                // CEO 29.10: «КАФЕ · грузинская кухня» — the cuisine words beside the tag while there is room
                if (cuisine != null) Txt(cuisine, CraftType.caption, C.camper.inkMuted, Modifier.weight(1f, fill = false).testTag("walk.stop.cuisine"), maxLines = 1)
                if (!untimed && hours != null && hours.source != "default") TimedHours(hours)
            }
            if (untimed) UntimedHours(hours)
            // M4 notes join parts with « · » («С собакой внутрь обычно нельзя · Часы работы уточняйте»)
            // S4-QA P2-02: no «уточняйте» next to known hours; parts read as sentences («…нельзя. Часы…»)
            val knownHours = hours != null && hours.source != "default" && (hours.todayRu != null || hours.allDay)
            val parts = s.noteRu?.split(" · ").orEmpty().map { it.trim().trimEnd('.') }
                .filterNot { it.isBlank() || ((hideHoursNote || knownHours) && it == HOURS_NOTE) }
            val dogNo = if (dog && s.indoor && parts.none { it.contains("собак", ignoreCase = true) }) stringResource(R.string.walk_stop_dog_no).trimEnd('.') else null
            (parts + listOfNotNull(dogNo)).takeIf { it.isNotEmpty() }?.joinToString(". ", postfix = ".")
                ?.let { Txt(it, CraftType.body, C.camper.inkSoft, Modifier.testTag("walk.stop.note")) }
            if (cost != null) Txt(cost, DesignTokens.type.body.mdStrong, C.camper.orangeText)
            if (priceUnknown != null) Txt(priceUnknown, CraftType.caption, C.camper.inkMuted, Modifier.testTag("walk.stop.price.unknown"))
        }
    }
}

/** Timed rows: «открыто до 20:00» (green) / «сегодня закрыто» (red), no pill (`type.tag.hours`). */
@Composable
private fun TimedHours(h: app.verst.core.model.dto.WalkHoursDto) {
    val until = h.todayRu?.substringAfterLast('–', "")?.substringAfterLast('-', "")?.trim()?.takeIf { it.isNotEmpty() }
    when {
        h.openNow == false -> Txt(stringResource(R.string.hours_closed), T.tag.hours, C.hours.closed, maxLines = 1)
        h.allDay -> Txt(stringResource(R.string.hours_24), T.tag.hours, C.hours.open, maxLines = 1)
        until != null -> Txt(stringResource(R.string.hours_open_until, until), T.tag.hours, C.hours.open, maxLines = 1)
    }
}

/** Untimed rows: the `HoursPill` — open / closed (with the day) / round the clock / not given. */
@Composable
private fun UntimedHours(h: app.verst.core.model.dto.WalkHoursDto?) {
    when {
        h == null || (h.todayRu == null && !h.allDay && h.openNow == null) -> HoursPill(HoursState.UNKNOWN, stringResource(R.string.hours_unknown))
        // M6: default hours are a guess — no «открыто» claim, just the hours (the note says «уточняйте»)
        h.source == "default" && h.openNow != false -> HoursPill(HoursState.UNKNOWN, h.todayRu ?: stringResource(R.string.hours_unknown))
        h.allDay -> HoursPill(HoursState.ALLDAY, stringResource(R.string.hours_24))
        h.openNow == false -> HoursPill(HoursState.CLOSED, h.closedDayRu?.let { stringResource(R.string.hours_closed_day, it) } ?: stringResource(R.string.hours_closed))
        h.todayRu != null -> HoursPill(if (h.openNow == true) HoursState.OPEN else HoursState.UNKNOWN, if (h.openNow == true) stringResource(R.string.hours_today_open, h.todayRu!!) else h.todayRu!!)
        else -> HoursPill(HoursState.UNKNOWN, stringResource(R.string.hours_unknown))
    }
}

/** The engine's per-stop default-hours note (`walk.note.hours`). */
private const val HOURS_NOTE = "Часы работы уточняйте"

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

/** The §21 bar-sign pictogram of a walk stop kind. */
internal fun walkSignGlyph(kind: String): Glyph = when (kind) {
    "pub", "craft", "beer" -> Glyph.MUG
    "cafe" -> Glyph.CUP
    "restaurant", "fast_food", "food_court" -> Glyph.CUTLERY
    else -> Glyph.GLASS
}

/** 5.11 footer: a craft summary card (not a button) «СКОЛЬКО СТОИТ ПРОГУЛКА · ≈ 2 400 ₽ на всех». */
@Composable
private fun Footer(w: WalkRouteDto) {
    val total = w.cost.totalRub
    val per = (total.toDouble() / w.people).roundToInt().let { ((it + 50) / 100) * 100 }
    CraftCard(
        Modifier.fillMaxWidth().padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 8.dp, bottom = 12.dp)
            .semantics(mergeDescendants = true) {}.testTag("walk.total"),
        padding = PaddingValues(horizontal = 16.dp, vertical = 10.dp),
        spacing = 2.dp,
    ) {
        Txt(stringResource(R.string.walk_footer_label), CraftType.overline, C.camper.orangeText, maxLines = 1)
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (total <= 0 && w.priceUnknown) {
                // CEO 29.10: the prices of the cafés are unknown — never «Бесплатно» for them
                Txt(stringResource(R.string.walk_footer_price_unknown), T.amount, C.camper.ink, Modifier.testTag("walk.price.unknown"), maxLines = 1)
                Spacer(Modifier.weight(1f))
                Txt(stringResource(R.string.walk_footer_price_unknown_sub), DesignTokens.type.body.smStrong, C.camper.inkSoft, maxLines = 1)
            } else if (total <= 0) {
                // 5.11 §9 (S3-QA P1-03): never «≈ 0 ₽»; no per-person line
                Txt(stringResource(R.string.walk_footer_free), T.amount, C.camper.greenText, Modifier.testTag("walk.free"), maxLines = 1)
                Spacer(Modifier.weight(1f))
                Txt(stringResource(R.string.walk_footer_free_sub), DesignTokens.type.body.smStrong, C.camper.inkSoft, maxLines = 1)
            } else {
                Txt(stringResource(R.string.walk_footer_total, app.verst.settings.AppPrefs.money(total)), T.amount, C.camper.ink, maxLines = 1)
                Spacer(Modifier.weight(1f))
                // CEO 29.10: with unknown café prices the sum leaves them out — say so instead of a per-person sum
                val sub = if (w.priceUnknown) stringResource(R.string.walk_footer_without_food)
                else stringResource(R.string.walk_footer_per_person, app.verst.settings.AppPrefs.money(per))
                Txt(sub, DesignTokens.type.body.smStrong, C.camper.inkSoft, maxLines = 1)
            }
        }
    }
}
