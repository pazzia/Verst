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
import app.verst.feature.common.HoursPill
import app.verst.feature.common.HoursState
import app.verst.feature.common.KindTag
import app.verst.feature.common.kindWord
import app.verst.feature.common.cuisineWords
import app.verst.feature.common.crewShort
import app.verst.nav.CityPicker
import app.verst.nav.DOG_WALK
import app.verst.nav.WalkFew
import androidx.compose.foundation.horizontalScroll
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.semantics.disabled
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import androidx.compose.animation.core.animateFloat
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
    /** S4 5.11 §10: the filter bar's values (duration, preset, crew) and the open picker. */
    val filters: PickerUi? = null,
    val picker: CityPicker? = null,
    /** «Другой вариант» found nothing new (disabled + note). */
    val otherNone: Boolean = false,
    /** `NOT_ENOUGH_POIS` after a filter change: the plate replaces the column. */
    val few: WalkFew? = null,
    val excludedCount: Int = 0,
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
                            Glyph.BOOKMARK, if (ui.saved) C.accent.yellowText else C.mirror.label,
                            stringResource(if (ui.saved) R.string.cd_road_saved else R.string.cd_road_save), "walk.save", filled = ui.saved, onClick = a::save,
                        )
                        IconButton44(Glyph.SHARE, C.mirror.label, stringResource(R.string.cd_road_share), "walk.share", onClick = a::share)
                    }
                    WalkTitleSign(w, Modifier.padding(start = 20.dp, end = 20.dp, top = 56.dp).fillMaxWidth())
                }
                Column(
                    Modifier.weight(1f).fillMaxWidth().verticalScroll(scroll).testTag("walk.list").onGloballyPositioned { content = it },
                ) {
                    // S3-FINAL P2-02: every stop has default hours → the top line says it once, rows stay quiet
                    val allDefaultHours = w.stops.filter { it.poiId != null }.let { st -> st.isNotEmpty() && st.all { !it.hoursVerified } }
                    Intro(ui, a)
                    val few = ui.few
                    if (few != null) {
                        // 5.11 §10.5: the plate replaces the column; no cost footer, no «Другой вариант»
                        Box(Modifier.padding(horizontal = 20.dp)) { FewPlate(few, ui.filters?.selected ?: w.preset, ui.excludedCount, a::suggestion) }
                        Spacer(Modifier.height(24.dp))
                    } else {
                        Box {
                            // 5.11 §10.2: while rebuilding the previous walk stays, dimmed to 35 %, under the pill
                            Column(Modifier.fillMaxWidth().dimmed(ui.building)) {
                                Column(Modifier.fillMaxWidth().walkColumn()) {
                                    val start = RuFormat.clock(w.startAt) ?: ""
                                    val finish = RuFormat.clock(w.endAt) ?: ""
                                    Txt(
                                        when {
                                            w.untimed -> stringResource(R.string.walk_untimed_header)
                                            w.startsTomorrow() -> stringResource(R.string.walk_header_tomorrow, start, finish)
                                            else -> stringResource(R.string.walk_header, start, finish)
                                        },
                                        T.title.sm, C.accent.yellowText,
                                        Modifier.padding(start = 72.dp, end = 16.dp, bottom = 10.dp).semantics { heading() }.testTag("walk.header"),
                                    )
                                    EndRow(stringResource(R.string.walk_start_row), w.start.label ?: w.townName ?: "", if (w.untimed) "" else start)
                                    val dog = ui.filters?.dog == true
                                    w.stops.forEach { s ->
                                        WalkStopRow(
                                            s, w.people, s.id == highlight, allDefaultHours, w.untimed, dog,
                                            requesters.getOrPut(s.id) { FocusRequester() }, { content }, { y -> if (rows[s.id] != y) rows[s.id] = y },
                                        ) { a.stop(s) }
                                    }
                                    val fin = w.finish
                                    if (fin != null) EndRow(stringResource(R.string.walk_finish_row), fin.label ?: "", if (w.untimed) "" else finish)
                                    Spacer(Modifier.height(16.dp))
                                }
                                Box(Modifier.padding(horizontal = 20.dp)) {
                                    if (ui.otherNone) {
                                        OtherNone()
                                    } else {
                                        WideButton(stringResource(R.string.walk_other), "walk.other", enabled = !ui.building, onClick = a::other, height = 56.dp)
                                    }
                                }
                                Spacer(Modifier.height(24.dp))
                            }
                            if (ui.building) RebuildPill(Modifier.align(Alignment.TopStart).padding(start = 72.dp, end = 16.dp, top = 30.dp))
                        }
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

/** components §29 rebuild pill: yellow pulsing dot + «Пересобираем прогулку…» over the dimmed column. */
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
        modifier.fillMaxWidth().height(44.dp).clip(RoundedCornerShape(22.dp)).background(C.dash.control)
            .border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(22.dp)).padding(horizontal = 16.dp).testTag("walk.rebuilding"),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(Modifier.size(10.dp).clip(CircleShape).background(C.accent.yellow.copy(alpha = pulse / m.toAlpha)))
        Txt(stringResource(R.string.walk_rebuilding), T.body.mdStrong, C.text.primary, maxLines = 1)
    }
}

/** «Другой вариант» used up: dashed, disabled, with the note (components §29). */
@Composable
private fun OtherNone() {
    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(
            Modifier.fillMaxWidth().height(56.dp).clip(RoundedCornerShape(DesignTokens.radius.r12)).drawBehind {
                val w = DesignTokens.stroke.w1.toPx()
                drawRoundRect(
                    C.dash.outline, Offset(w / 2, w / 2), Size(size.width - w, size.height - w),
                    androidx.compose.ui.geometry.CornerRadius(DesignTokens.radius.r12.toPx()),
                    style = androidx.compose.ui.graphics.drawscope.Stroke(w, pathEffect = androidx.compose.ui.graphics.PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 4.dp.toPx()))),
                )
            }.semantics { disabled() }.testTag("walk.other.none"),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.walk_other_none), T.button.md, C.text.disabled, maxLines = 1) }
        Txt(stringResource(R.string.walk_other_none_note), T.body.sm, C.text.muted, align = TextAlign.Center)
    }
}

@Composable
private fun Intro(ui: WalkUi, a: WalkActions) {
    val w = ui.walk
    Column(Modifier.padding(start = 20.dp, end = 20.dp, bottom = 18.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Txt(stringResource(R.string.walk_heading), T.display, C.text.primary, Modifier.semantics { heading() })
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
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            // S3-QA2: half hours with the decimal comma («5,5 ч»), whole hours without «,0»
            if (f == null && !w.untimed) InfoChip(stringResource(R.string.walk_chip_duration_text, hours(w.durationMin)))
            InfoChip(stringResource(R.string.walk_chip_km, km(w.walkKm)))
            if (w.returnToStart) InfoChip(stringResource(R.string.walk_chip_back))
            if (w.adultOnly) {
                Box(
                    Modifier.clip(RoundedCornerShape(DesignTokens.radius.r12)).border(DesignTokens.stroke.w1, C.accent.yellowText, RoundedCornerShape(DesignTokens.radius.r12))
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
        if (w.untimed) {
            Txt(stringResource(R.string.walk_untimed_facts, "${w.stops.size} ${pluralStringResource(R.plurals.plural_place, w.stops.size)}", km(w.walkKm)), T.body.sm, C.text.muted, Modifier.testTag("walk.untimed.facts"))
        }
        // L3a: the walk hand-off, one button per part when the engine split the walk
        val parts = ui.handoff?.parts.orEmpty()
        val label = if (ui.target == HandoffTarget.Maps || ui.target == HandoffTarget.MapsDryRun) stringResource(R.string.handoff_walk_cta) else stringResource(R.string.handoff_web)
        if (parts.size > 1) {
            parts.forEach { p ->
                // the part on its own line: «Открыть Яндекс Карты в браузере» / «Часть 1 из 2» (never clipped)
                WideButton(label, "walk.handoff.${p.index}", walker = true, height = 60.dp, sub = stringResource(R.string.handoff_part, p.index, parts.size), onClick = { a.handoff(p.index) })
            }
        } else {
            WideButton(label, "walk.handoff", walker = true, enabled = true, onClick = { a.handoff(1) })
        }
        val note = w.responsibleNoteRu
        if (note != null) {
            // L4: the responsible plate, first and not dismissible (fixed copy)
            Row(
                Modifier.fillMaxWidth().border(DesignTokens.stroke.w1, C.accent.yellowText, RoundedCornerShape(DesignTokens.radius.r10))
                    .padding(horizontal = 12.dp, vertical = 10.dp).testTag("walk.responsible"),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(Modifier.size(22.dp).clip(CircleShape).background(C.sign.white), contentAlignment = Alignment.Center) {
                    Txt(stringResource(R.string.city_badge_18), T.caption.bold, C.text.onLight)
                }
                // S3-FINAL P2-01: «За руль — только трезвым» never breaks before the dash
                Txt(stringResource(R.string.walk_responsible).replace(" —", "\u00A0—"), T.body.md, C.text.primary)
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
                if (w.stops.any { !it.hoursVerified && it.poiId != null }) Txt(m, T.body.sm, C.text.muted, Modifier.testTag("walk.hours"))
                continue
            }
            WarningBox(m)
        }
    }
}

/** An engine walk warning: an outlined plate with the sentence. */
@Composable
private fun WarningBox(text: String, tag: String? = null) {
    Box(
        Modifier.fillMaxWidth().border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r10))
            .then(if (tag != null) Modifier.testTag(tag) else Modifier).padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Txt(text, T.body.md, C.text.secondary)
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

/** components §29 `WalkFilterChip`: h 36, radius 18, dashed-outline look, chevron-down. */
@Composable
private fun FilterChip(text: String, tag: String, onClick: () -> Unit) {
    val shape = RoundedCornerShape(18.dp)
    Row(
        Modifier.height(36.dp).clip(shape).background(C.dash.face).border(DesignTokens.stroke.w1, C.dash.outlineDashed, shape)
            .clickable(role = Role.Button, onClick = onClick).testTag(tag).padding(start = 12.dp, end = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Txt(text, T.body.smStrong, C.text.primary, maxLines = 1)
        GlyphIcon(Glyph.CHEVRON_DOWN, C.text.muted, 12.dp)
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

/** components §22 walk button / §2 `SecondaryButton`. */
@Composable
private fun WideButton(text: String, tag: String, walker: Boolean = false, enabled: Boolean = true, height: Dp = 48.dp, sub: String? = null, onClick: () -> Unit) {
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    Row(
        Modifier.fillMaxWidth().height(height).clip(shape).background(C.dash.control).border(DesignTokens.stroke.w1, C.dash.outline, shape)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick).testTag(tag).padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        if (walker) {
            WalkerIcon(C.accent.yellowText, 18.dp)
            Spacer(Modifier.width(8.dp))
        }
        if (sub == null) {
            Txt(text, T.button.md, if (enabled) C.text.primary else C.text.disabled, maxLines = 1)
        } else {
            androidx.compose.foundation.layout.Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Txt(text, T.button.md, if (enabled) C.text.primary else C.text.disabled, maxLines = 1)
                Txt(sub, T.body.sm, C.text.secondary, maxLines = 1)
            }
        }
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
private fun WalkStopRow(
    s: WalkStopDto, people: Int, focused: Boolean, hideHoursNote: Boolean, untimed: Boolean, dog: Boolean,
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
            if (s.isBar || s.isFood) BarSign(s.kind) else RoadSign("tourist", s.nameRu, app.verst.feature.common.signTags(s.poiKind ?: s.kind, listOf(s.kind)))
        }
        Column(Modifier.weight(1f).padding(start = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Txt(line, T.body.sm, C.text.muted, Modifier.weight(1f), maxLines = 1)
                Txt(time, T.body.sm, C.text.muted, align = TextAlign.End)
            }
            Txt(s.nameRu, T.title.md, C.text.primary, maxLines = 2)
            // S4 5.11 §10.3: the category tag; timed rows «открыто до 20:00», untimed rows the hours pill
            val hours = s.hours
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                kindText?.let { KindTag(it) }
                // CEO 29.10: «КАФЕ · грузинская кухня» — the cuisine words beside the tag while there is room
                if (cuisine != null) Txt(cuisine, T.body.sm, C.text.muted, Modifier.weight(1f, fill = false).testTag("walk.stop.cuisine"), maxLines = 1)
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
                ?.let { Txt(it, T.body.md, C.text.note, Modifier.testTag("walk.stop.note")) }
            if (cost != null) Txt(cost, T.body.mdStrong, C.accent.yellowText)
            if (priceUnknown != null) Txt(priceUnknown, T.body.sm, C.text.muted, Modifier.testTag("walk.stop.price.unknown"))
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

/**
 * components §21 bar sign: the `service` look with `glass` (bar, рюмочная) or `mug` (pub, craft); CEO 29.10: the
 * walk food places in the same look — `cup` (café), `cutlery` (restaurant, fast food, food court).
 */
@Composable
internal fun BarSign(kind: String) {
    Box(
        Modifier.size(35.dp, 43.dp).clip(RoundedCornerShape(4.dp)).background(C.sign.blue).padding(3.dp)
            .clip(RoundedCornerShape(3.dp)).background(C.sign.white),
        contentAlignment = Alignment.Center,
    ) {
        app.verst.core.ui.components.GlyphIcon(walkSignGlyph(kind), C.text.onLight, 22.dp)
    }
}

/** The §21 bar-sign pictogram of a walk stop kind. */
internal fun walkSignGlyph(kind: String): Glyph = when (kind) {
    "pub", "craft", "beer" -> Glyph.MUG
    "cafe" -> Glyph.CUP
    "restaurant", "fast_food", "food_court" -> Glyph.CUTLERY
    else -> Glyph.GLASS
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
                if (total <= 0 && w.priceUnknown) {
                    // CEO 29.10: the prices of the cafés are unknown — never «Бесплатно» for them
                    Txt(stringResource(R.string.walk_footer_price_unknown), T.amount, C.text.onLight, Modifier.testTag("walk.price.unknown"), maxLines = 1)
                    Spacer(Modifier.weight(1f))
                    Txt(stringResource(R.string.walk_footer_price_unknown_sub), T.body.smStrong, C.text.onLightMuted, maxLines = 1)
                } else if (total <= 0) {
                    // 5.11 §9 (S3-QA P1-03): never «≈ 0 ₽»; no per-person line
                    Txt(stringResource(R.string.walk_footer_free), T.amount, C.text.onLight, Modifier.testTag("walk.free"), maxLines = 1)
                    Spacer(Modifier.weight(1f))
                    Txt(stringResource(R.string.walk_footer_free_sub), T.body.smStrong, C.text.onLightMuted, maxLines = 1)
                } else {
                    Txt(stringResource(R.string.walk_footer_total, app.verst.settings.AppPrefs.money(total)), T.amount, C.text.onLight, maxLines = 1)
                    Spacer(Modifier.weight(1f))
                    // CEO 29.10: with unknown café prices the sum leaves them out — say so instead of a per-person sum
                    val sub = if (w.priceUnknown) stringResource(R.string.walk_footer_without_food)
                    else stringResource(R.string.walk_footer_per_person, app.verst.settings.AppPrefs.money(per))
                    Txt(sub, T.body.smStrong, C.text.onLightMuted, maxLines = 1)
                }
            }
        }
    }
}
