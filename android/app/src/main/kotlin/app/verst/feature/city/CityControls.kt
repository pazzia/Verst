package app.verst.feature.city

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.CityPresetDto
import app.verst.core.model.dto.WalkSuggestion
import app.verst.core.ui.R
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.nav.CityPicker
import app.verst.nav.DOG_WALK
import app.verst.nav.WalkDurations
import app.verst.nav.WalkFew
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** What the city pickers show (5.10 prefs and the 5.11 filter bar share them). */
data class PickerUi(
    val durationMin: Int?,
    val presets: List<CityPresetDto>,
    val selected: String,
    val adults: Int,
    val children: Int,
    val dog: Boolean,
    val pace: String,
    val budget: Int?,
)

interface PickerActions {
    fun duration(min: Int?)
    fun preset(p: String)
    fun adults(n: Int)
    fun children(n: Int)
    fun dog(on: Boolean)
    fun pace(p: String)
    fun budget(rub: Int?)
    fun closePicker()
}

@Composable
internal fun durationLabel(min: Int?): String =
    if (min == null) stringResource(R.string.city_duration_unlimited) else stringResource(R.string.city_duration, min / 60)

/** «2 взрослых · 1 ребёнок · собака» (5.10 caption meta). */
@Composable
internal fun crewLine(adults: Int, children: Int, dog: Boolean): String {
    val parts = mutableListOf("$adults ${pluralStringResource(R.plurals.plural_adult, adults)}")
    if (children > 0) parts += "$children ${pluralStringResource(R.plurals.plural_child, children)}"
    if (dog) parts += stringResource(R.string.instruments_summary_dog)
    return parts.joinToString(stringResource(R.string.common_join_dot))
}

@Composable
internal fun presetName(p: String, fallback: String = ""): String = when (p) {
    DOG_WALK -> stringResource(R.string.city_preset_dog)
    "overview" -> stringResource(R.string.city_preset_overview)
    "museums" -> stringResource(R.string.city_preset_museums)
    "ryumochnye" -> stringResource(R.string.city_preset_ryumochnye)
    "beer" -> stringResource(R.string.city_preset_beer)
    "custom" -> stringResource(R.string.city_preset_custom)
    else -> fallback
}

@Composable
private fun presetSub(p: CityPresetDto): String {
    val h = p.defaultDurationMin / 60
    return when (p.preset) {
        DOG_WALK -> stringResource(R.string.city_preset_dog_sub)
        "overview" -> stringResource(R.string.city_preset_overview_sub, h)
        "museums" -> stringResource(R.string.city_preset_museums_sub, h)
        "ryumochnye" -> stringResource(R.string.city_preset_ryumochnye_sub, h)
        "beer" -> stringResource(R.string.city_preset_beer_sub, h)
        else -> stringResource(R.string.city_preset_custom_sub)
    }
}

@Composable
internal fun SectionLabel(text: String, modifier: Modifier = Modifier) =
    Txt(text, T.label.md, C.text.muted, modifier.padding(top = 18.dp, bottom = 8.dp))

/** components §27 `CrewCell` × 3: Взрослые 1–9, Дети 0–9, Собака (toggle). */
@Composable
internal fun CrewCells(adults: Int, children: Int, dog: Boolean, onAdults: (Int) -> Unit, onChildren: (Int) -> Unit, onDog: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        StepperCell(stringResource(R.string.city_crew_adults), adults, 1, 9, "city.crew.adults", Modifier.weight(1f), onAdults)
        StepperCell(stringResource(R.string.city_crew_kids), children, 0, 9, "city.crew.kids", Modifier.weight(1f), onChildren)
        DogCell(dog, Modifier.weight(1f), onDog)
    }
}

@Composable
private fun CellFrame(modifier: Modifier, on: Boolean = false, content: @Composable () -> Unit) {
    val shape = RoundedCornerShape(14.dp)
    Box(
        modifier.height(DesignTokens.size.crewCellH).clip(shape).background(C.dash.well)
            .border(3.dp, if (on) C.crew.dog else C.dash.control, shape).padding(horizontal = 6.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) { content() }
}

@Composable
private fun StepperCell(label: String, value: Int, min: Int, max: Int, tag: String, modifier: Modifier, onChange: (Int) -> Unit) {
    CellFrame(modifier.semantics(mergeDescendants = false) { stateDescription = "$label: $value" }) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Txt(label, T.label.md, C.text.secondary, maxLines = 1)
            Txt(value.toString(), T.title.xl, C.text.primary, Modifier.testTag("$tag.value"), maxLines = 1)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                StepButton(Glyph.MINUS, value > min, "$tag.minus", "$label −") { onChange(value - 1) }
                StepButton(Glyph.PLUS, value < max, "$tag.plus", "$label +") { onChange(value + 1) }
            }
        }
    }
}

@Composable
private fun StepButton(g: Glyph, enabled: Boolean, tag: String, cd: String, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp, 34.dp).clip(RoundedCornerShape(10.dp)).background(C.dash.controlAlt)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = cd }.testTag(tag),
        contentAlignment = Alignment.Center,
    ) { GlyphIcon(g, if (enabled) C.text.primary else C.text.disabled, 16.dp) }
}

@Composable
private fun DogCell(on: Boolean, modifier: Modifier, onDog: (Boolean) -> Unit) {
    val label = stringResource(R.string.city_crew_dog)
    CellFrame(
        modifier.toggleable(on, role = Role.Switch, onValueChange = onDog).testTag("city.crew.dog"),
        on = on,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Txt(label, T.label.md, C.text.secondary, maxLines = 1)
            GlyphIcon(Glyph.PAW, if (on) C.crew.dog else C.text.muted, 34.dp, filled = on)
            Txt(stringResource(if (on) R.string.city_crew_dog_on else R.string.city_crew_dog_off), T.body.smStrong, if (on) C.text.primary else C.text.muted, maxLines = 1)
        }
    }
}

/** «СКОЛЬКО ГУЛЯЕМ»: 2 / 4 / 6 / 8 ч / без ограничения + the timed/untimed hint. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun DurationChips(durationMin: Int?, onPick: (Int?) -> Unit, hint: Boolean = true) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        WalkDurations.forEach { m -> ParamChip(stringResource(R.string.city_duration, m / 60), durationMin == m, "city.duration.$m") { onPick(m) } }
        ParamChip(stringResource(R.string.city_duration_unlimited), durationMin == null, "city.duration.unlimited") { onPick(null) }
    }
    if (hint) {
        Txt(
            stringResource(if (durationMin == null) R.string.city_duration_hint_untimed else R.string.city_duration_hint_timed),
            T.body.sm, C.text.muted, Modifier.padding(top = 8.dp).testTag("city.duration.hint"),
        )
    }
}

/** components §21 `ParamChips` (the `MoodChip` look): h 44, radius 22. */
@Composable
internal fun ParamChip(text: String, on: Boolean, tag: String, multi: Boolean = false, onClick: () -> Unit) {
    val shape = RoundedCornerShape(22.dp)
    Box(
        Modifier.height(44.dp).clip(shape).background(if (on) C.accent.yellow else C.dash.control)
            .border(DesignTokens.stroke.w1, if (on) C.accent.yellow else C.dash.outline, shape)
            .then(if (multi) Modifier.toggleable(on, role = Role.Checkbox, onValueChange = { onClick() }) else Modifier.selectable(on, role = Role.RadioButton, onClick = onClick))
            .testTag(tag).padding(horizontal = 14.dp),
        contentAlignment = Alignment.Center,
    ) { Txt(text, T.body.mdStrong, if (on) C.text.onLight else C.text.secondary, maxLines = 1) }
}

/** The preset plates in rows of two; children never disable one (S4). */
@Composable
internal fun PresetGrid(presets: List<CityPresetDto>, selected: String, onPick: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        presets.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { p -> PresetPlate(p, p.preset == selected, Modifier.weight(1f)) { onPick(p.preset) } }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

/** components §21 `PresetPlate`: the brown tourist plate, pictogram, name, sub; 18+ badge; selected outline + check. */
@Composable
private fun PresetPlate(p: CityPresetDto, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val custom = p.preset == "custom"
    val name = presetName(p.preset, p.titleRu)
    val sub = presetSub(p)
    val cd = if (p.adultOnly) stringResource(R.string.cd_city_preset_18, name, sub) else stringResource(R.string.cd_city_preset, name, sub)
    val shape = RoundedCornerShape(DesignTokens.radius.r5)
    Box(
        modifier.height(DesignTokens.size.presetH)
            .then(if (selected) Modifier.border(2.dp, C.accent.yellow, RoundedCornerShape(DesignTokens.radius.r5 + 2.dp)).padding(2.dp) else Modifier)
            .clip(shape)
            .background(if (custom) Color.Transparent else C.sign.brown)
            .then(
                if (custom) {
                    Modifier.drawBehind {
                        drawRoundRect(
                            C.sign.white, style = Stroke(2.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 6f))),
                            cornerRadius = androidx.compose.ui.geometry.CornerRadius(DesignTokens.radius.r5.toPx()),
                        )
                    }
                } else {
                    Modifier.padding(3.dp).border(DesignTokens.stroke.w2, C.sign.white, RoundedCornerShape(DesignTokens.radius.r3))
                },
            )
            .selectable(selected, role = Role.RadioButton, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("city.preset.${p.preset}")
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        val icon = when (p.preset) {
            DOG_WALK -> Glyph.PAW
            "overview" -> Glyph.BINOCULARS
            "museums" -> Glyph.MUSEUM
            "ryumochnye" -> Glyph.GLASS
            "beer" -> Glyph.MUG
            else -> Glyph.GEAR
        }
        GlyphIcon(icon, C.sign.white, 24.dp, Modifier.align(Alignment.TopStart))
        Column(Modifier.align(Alignment.BottomStart)) {
            Txt(name, T.title.sm, C.sign.white, maxLines = 1)
            Txt(sub, T.body.sm, C.mirror.label, maxLines = 1)
        }
        Row(Modifier.align(Alignment.TopEnd), horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
            if (p.adultOnly) {
                Box(Modifier.size(22.dp).clip(CircleShape).background(C.sign.white), contentAlignment = Alignment.Center) {
                    Txt(stringResource(R.string.city_badge_18), T.caption.bold, C.text.onLight, maxLines = 1)
                }
            }
            if (selected) GlyphIcon(Glyph.CHECK, C.accent.yellow, 16.dp)
        }
    }
}

/** components §28 `WalkWarningPlate`: yellow outline, «!» disc, optional actions (informative: ПОШЛИ stays on). */
@Composable
internal fun WalkWarningPlate(text: String, tag: String, actions: List<Pair<String, () -> Unit>> = emptyList()) {
    PlateFrame(C.accent.yellow, Color.Transparent, tag) {
        Box(Modifier.size(18.dp).clip(CircleShape).background(C.accent.yellow), contentAlignment = Alignment.Center) {
            Txt("!", T.caption.bold, C.text.onLight)
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Txt(text, T.body.md, C.text.primary)
            if (actions.isNotEmpty()) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    actions.forEachIndexed { i, (label, onClick) ->
                        Box(
                            Modifier.height(36.dp).clip(RoundedCornerShape(8.dp)).background(C.dash.control)
                                .border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(8.dp))
                                .clickable(role = Role.Button, onClick = onClick).testTag("$tag.action.$i").padding(horizontal = 10.dp),
                            contentAlignment = Alignment.Center,
                        ) { Txt(label, T.body.smStrong, C.text.primary, maxLines = 1) }
                    }
                }
            }
        }
    }
}

/** components §28 `WalkInfoPlate`: how the walk was adapted (green check). */
@Composable
internal fun WalkInfoPlate(text: String, tag: String) {
    PlateFrame(C.info.border, C.info.fill, tag) {
        Box(Modifier.size(18.dp).clip(CircleShape).background(C.info.mark), contentAlignment = Alignment.Center) {
            GlyphIcon(Glyph.CHECK, C.text.onLight, 12.dp)
        }
        Txt(text, T.body.md, C.text.primary, Modifier.weight(1f))
    }
}

@Composable
private fun PlateFrame(border: Color, fill: Color, tag: String, content: @Composable androidx.compose.foundation.layout.RowScope.() -> Unit) {
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    Row(
        Modifier.fillMaxWidth().clip(shape).background(fill).border(DesignTokens.stroke.w1, border, shape)
            .padding(horizontal = 12.dp, vertical = 10.dp).testTag(tag),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) { content() }
}

/**
 * 5.10 / 5.11 §10.5 «Для 8 ч рядом мало мест»: one button per **engine** suggestion (each verified to work);
 * the app never invents one. Without suggestions (an older engine) the plate only says what to change.
 */
@Composable
internal fun FewPlate(few: WalkFew, preset: String, excludedCount: Int, onSuggestion: (WalkSuggestion) -> Unit) {
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    Column(
        Modifier.fillMaxWidth().border(DesignTokens.stroke.w1, C.dash.outline, shape).padding(12.dp).testTag("walk.few"),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        val what = if (few.unlimited) presetName(preset, preset) else durationLabel(few.durationMin)
        Txt(stringResource(R.string.walk_few_title, what), T.title.sm, C.text.primary)
        if (few.suggestions.isEmpty()) {
            Txt(stringResource(R.string.walk_other_none_note), T.body.md, C.text.secondary)
        }
        few.suggestions.forEachIndexed { i, sg ->
            val places = sg.count?.let { "$it ${pluralStringResource(R.plurals.plural_place, it)}" }
            val (title, sub) = when {
                sg.clearExclude -> stringResource(R.string.walk_few_clear) to
                    stringResource(R.string.walk_few_clear_sub, (sg.count ?: excludedCount).let { "$it ${pluralStringResource(R.plurals.plural_place, it)}" })
                sg.unlimited -> stringResource(R.string.walk_few_unlimited) to places?.let { stringResource(R.string.walk_few_unlimited_sub, it) }
                sg.durationMin != null -> stringResource(R.string.walk_few_duration, durationLabel(sg.durationMin)) to places?.let { stringResource(R.string.walk_few_duration_sub, it) }
                else -> stringResource(R.string.walk_few_preset, presetName(sg.preset ?: "", sg.preset ?: "")) to places?.let { stringResource(R.string.walk_few_preset_sub, it) }
            }
            Column(
                Modifier.fillMaxWidth().defaultMinSize(minHeight = 52.dp).clip(RoundedCornerShape(DesignTokens.radius.r10)).background(C.dash.control)
                    .border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r10))
                    .clickable(role = Role.Button) { onSuggestion(sg) }.testTag("walk.few.$i").padding(horizontal = 12.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.Center,
            ) {
                Txt(title, T.title.sm, C.text.primary, maxLines = 1)
                if (sub != null) Txt(sub, T.body.sm, C.text.muted, maxLines = 1)
            }
        }
    }
}

/** The picker sheets (5.10 prefs; 5.11 filter bar): duration, preset, crew, budget, pace. */
@Composable
internal fun BoxScope.CityPickerSheet(picker: CityPicker, ui: PickerUi, windowH: Dp, a: PickerActions) {
    val title = when (picker) {
        CityPicker.DURATION -> stringResource(R.string.city_duration_label)
        CityPicker.PRESET -> stringResource(R.string.city_type_label)
        CityPicker.CREW -> stringResource(R.string.city_crew_label)
        CityPicker.BUDGET -> stringResource(R.string.city_pref_budget)
        CityPicker.PACE -> stringResource(R.string.city_pref_pace)
    }
    BottomSheet(title.lowercase().replaceFirstChar { it.uppercase() }, a::closePicker, "city.picker", windowH) {
        Spacer(Modifier.height(8.dp))
        when (picker) {
            CityPicker.DURATION -> DurationChips(ui.durationMin, { a.duration(it) })
            CityPicker.PRESET -> PresetGrid(ui.presets, ui.selected) { a.preset(it) }
            CityPicker.CREW -> CrewCells(ui.adults, ui.children, ui.dog, a::adults, a::children, a::dog)
            CityPicker.BUDGET -> BudgetChips(ui.budget) { a.budget(it) }
            CityPicker.PACE -> PaceChips(ui.pace) { a.pace(it) }
        }
        Spacer(Modifier.height(16.dp))
        Box(
            Modifier.fillMaxWidth().height(52.dp).clip(RoundedCornerShape(DesignTokens.radius.r12)).background(C.dash.control)
                .border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r12))
                .clickable(role = Role.Button, onClick = a::closePicker).testTag("city.picker.done"),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.settings_done), T.button.md, C.text.primary, maxLines = 1, align = TextAlign.Center) }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun BudgetChips(budget: Int?, onPick: (Int?) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf(2_000, 5_000, 10_000).forEach { v -> ParamChip(stringResource(R.string.city_budget_value, RuFormat.thousands(v)), budget == v, "city.budget.$v") { onPick(v) } }
        ParamChip(stringResource(R.string.instruments_budget_any), budget == null, "city.budget.any") { onPick(null) }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun PaceChips(pace: String, onPick: (String) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Paces.forEach { (k, res) -> ParamChip(stringResource(res), pace == k, "city.pace.$k") { onPick(k) } }
    }
}

internal val Paces = listOf("slow" to R.string.city_pace_slow, "normal" to R.string.city_pace_normal, "fast" to R.string.city_pace_fast)

@Composable
internal fun budgetLabel(budget: Int?): String =
    budget?.let { stringResource(R.string.city_budget_value, RuFormat.thousands(it)) } ?: stringResource(R.string.instruments_budget_any)

@Composable
internal fun paceLabel(pace: String): String = stringResource(Paces.firstOrNull { it.first == pace }?.second ?: R.string.city_pace_normal)

/** A settings-plate row «Бюджет на всех · до 5 000 ₽ ›» (5.10 §10 step 7). */
@Composable
internal fun PrefRow(label: String, value: String, tag: String, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp).clickable(role = Role.Button, onClick = onClick).testTag(tag).padding(horizontal = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Txt(label, T.body.mdStrong, C.text.primary, Modifier.weight(1f), maxLines = 1)
        Txt(value, T.body.md, C.text.secondary, maxLines = 1)
        Spacer(Modifier.width(6.dp))
        GlyphIcon(Glyph.RIGHT, C.text.muted, 14.dp)
    }
}

/** The disabled look for a control the engine said is used up («Другие варианты нет»). */
internal fun Modifier.dimmed(on: Boolean): Modifier = if (on) this.alpha(0.35f) else this
