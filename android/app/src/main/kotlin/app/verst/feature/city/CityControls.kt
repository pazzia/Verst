package app.verst.feature.city

import androidx.annotation.DrawableRes
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
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.dto.CityPresetDto
import app.verst.core.model.dto.WalkSuggestion
import app.verst.core.ui.R
import app.verst.core.ui.components.CraftBadge
import app.verst.core.ui.components.CraftBadgeColor
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftSecondaryButton
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.StepperKey
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.nav.CityPicker
import app.verst.nav.DOG_WALK
import app.verst.nav.WalkDurations
import app.verst.nav.WalkFew
import app.verst.core.ui.theme.DesignTokens.color as C

/*
 * Fork camper-ui (CEO 31.10): the city controls in the «Кемпер-гид» craft look (mockup screen 10) — preset tiles
 * in a 2-column grid (orange when selected), craft chips, crew rows with craft keys, paper plates.
 */

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

/** A field caption inside a craft card («СТАРТ ПРОГУЛКИ», «КТО ИДЁТ»; uppercase copy). */
@Composable
internal fun SectionLabel(text: String, modifier: Modifier = Modifier) =
    Txt(text, CraftType.sectionTitle, C.camper.inkSoft, modifier.padding(top = 2.dp))

/**
 * The head of a craft card (mockup `h3` with the thin rule): an optional overline (green «ПЕШКОМ · ЯРОСЛАВЛЬ»),
 * the title, the 20 % brown rule under them.
 */
@Composable
internal fun CardHeading(title: String, overline: String? = null, overlineTag: String? = null, overlineColor: Color = C.camper.greenText) {
    Column(Modifier.fillMaxWidth().semantics(mergeDescendants = true) { heading() }, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        if (overline != null) {
            Txt(overline, CraftType.overline, overlineColor, if (overlineTag != null) Modifier.testTag(overlineTag) else Modifier, maxLines = 1)
        }
        Txt(title, CraftType.cardTitle, C.camper.ink, maxLines = 2)
        Box(Modifier.fillMaxWidth().padding(top = 4.dp).height(1.dp).background(C.camper.divider))
    }
}

/** components §27 `CrewCell` × 3 as craft rows: Взрослые 1–9, Дети 0–9 (− value +), Собака (switch). */
@Composable
internal fun CrewCells(adults: Int, children: Int, dog: Boolean, onAdults: (Int) -> Unit, onChildren: (Int) -> Unit, onDog: (Boolean) -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        StepperRow(stringResource(R.string.city_crew_adults), R.drawable.ic_crew_adult, adults, 1, 9, "city.crew.adults", onAdults)
        StepperRow(stringResource(R.string.city_crew_kids), R.drawable.ic_crew_child, children, 0, 9, "city.crew.kids", onChildren)
        DogRow(dog, onDog)
    }
}

/** A crew row: icon, label, the craft keys − / + around the value (each key 52 × 44). */
@Composable
private fun StepperRow(label: String, @DrawableRes icon: Int, value: Int, min: Int, max: Int, tag: String, onChange: (Int) -> Unit) {
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp).semantics(mergeDescendants = false) { stateDescription = "$label: $value" },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, C.camper.border, 20.dp)
        Spacer(Modifier.width(10.dp))
        Txt(label, CraftType.chip, C.camper.ink, Modifier.weight(1f), maxLines = 1)
        StepperKey("−", value > min, "$label −", { onChange(value - 1) }, Modifier.testTag("$tag.minus"))
        Txt(value.toString(), CraftType.fieldMono, C.camper.ink, Modifier.widthIn(min = 36.dp).testTag("$tag.value"), maxLines = 1, align = TextAlign.Center)
        StepperKey("+", value < max, "$label +", { onChange(value + 1) }, Modifier.padding(end = CraftDefaults.TileShadow).testTag("$tag.plus"))
    }
}

/** The dog row: a switch row («с нами» / «нет»), the whole row is the target. */
@Composable
private fun DogRow(on: Boolean, onDog: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp).clip(RoundedCornerShape(CraftDefaults.FieldRadius))
            .toggleable(on, role = Role.Switch, onValueChange = onDog).testTag("city.crew.dog"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(R.drawable.ic_ui_dog, if (on) C.camper.greenText else C.camper.border, 20.dp)
        Spacer(Modifier.width(10.dp))
        Txt(stringResource(R.string.city_crew_dog), CraftType.chip, C.camper.ink, Modifier.weight(1f), maxLines = 1)
        Txt(
            stringResource(if (on) R.string.city_crew_dog_on else R.string.city_crew_dog_off), CraftType.caption,
            if (on) C.camper.greenText else C.camper.inkMuted, Modifier.padding(end = 10.dp), maxLines = 1,
        )
        CraftSwitch(on)
    }
}

/** The craft switch look (the row carries the semantics): brown-rimmed track, orange when on, paper knob. */
@Composable
internal fun CraftSwitch(on: Boolean) {
    val track = RoundedCornerShape(14.dp)
    Box(
        Modifier.size(48.dp, 28.dp).clip(track).background(if (on) C.camper.orange else C.camper.header)
            .border(CraftDefaults.BorderThin, C.camper.border, track),
        contentAlignment = if (on) Alignment.CenterEnd else Alignment.CenterStart,
    ) {
        Box(
            Modifier.padding(4.dp).size(20.dp).clip(CircleShape).background(C.camper.field)
                .border(CraftDefaults.BorderThin, C.camper.border, CircleShape),
        )
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
            CraftType.caption, C.camper.inkSoft, Modifier.padding(top = 8.dp).testTag("city.duration.hint"),
        )
    }
}

/** The craft choice chip (CraftChip look: orange + white when on, white paper else), h 44, radio or checkbox. */
@Composable
internal fun ParamChip(text: String, on: Boolean, tag: String, multi: Boolean = false, onClick: () -> Unit) {
    val shape = RoundedCornerShape(CraftDefaults.ChipRadius)
    Box(
        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clip(shape).background(if (on) C.camper.orange else C.camper.field)
            .border(CraftDefaults.BorderThin, C.camper.border, shape)
            .then(if (multi) Modifier.toggleable(on, role = Role.Checkbox, onValueChange = { onClick() }) else Modifier.selectable(on, role = Role.RadioButton, onClick = onClick))
            .testTag(tag).padding(horizontal = 14.dp),
        contentAlignment = Alignment.Center,
    ) { Txt(text, CraftType.chip, if (on) C.camper.onOrange else C.camper.ink, maxLines = 1) }
}

/** The preset tiles, two per row (mockup «Выберите пресет»); children never disable one (S4). */
@Composable
internal fun PresetGrid(presets: List<CityPresetDto>, selected: String, onPick: (String) -> Unit) {
    Column(Modifier.padding(end = CraftDefaults.TileShadow, bottom = CraftDefaults.TileShadow), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        presets.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { p -> PresetPlate(p, p.preset == selected, Modifier.weight(1f)) { onPick(p.preset) } }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

/** A craft preset tile: the icon, the 18+ badge, name and sub; selected = orange fill, white text. */
@Composable
private fun PresetPlate(p: CityPresetDto, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val name = presetName(p.preset, p.titleRu)
    val sub = presetSub(p)
    val cd = if (p.adultOnly) stringResource(R.string.cd_city_preset_18, name, sub) else stringResource(R.string.cd_city_preset, name, sub)
    Column(
        modifier.defaultMinSize(minHeight = DesignTokens.size.presetH)
            .craftSurface(
                if (selected) C.camper.orange else C.camper.field, radius = CraftDefaults.ChipRadius, border = CraftDefaults.BorderThin,
                shadow = C.camper.border, shadowX = CraftDefaults.TileShadow, shadowY = CraftDefaults.TileShadow,
            )
            .selectable(selected, role = Role.RadioButton, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("city.preset.${p.preset}")
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Icon(presetIcon(p.preset), if (selected) C.camper.onOrange else presetTint(p.preset), 20.dp)
            Spacer(Modifier.weight(1f))
            if (p.adultOnly) CraftBadge(stringResource(R.string.city_badge_18), color = CraftBadgeColor.AMBER)
        }
        Txt(name, CraftType.chip, if (selected) C.camper.onOrange else C.camper.ink, maxLines = 1)
        Txt(sub, CraftType.caption, if (selected) C.camper.onOrange else C.camper.inkSoft, maxLines = 1)
    }
}

/** The mockup's preset icons (camera, dog, beer, sliders) and the museum pictogram. */
@DrawableRes
private fun presetIcon(preset: String): Int = when (preset) {
    DOG_WALK -> R.drawable.ic_ui_dog
    "overview" -> R.drawable.ic_ui_camera
    "museums" -> R.drawable.ic_tourist_museum
    "ryumochnye", "beer" -> R.drawable.ic_ui_beer
    "custom" -> R.drawable.ic_ui_sliders
    else -> R.drawable.ic_tourist_walk
}

/** The icon tints of an idle tile (mockup: the dog green, the mug amber — here its text-safe orange). */
private fun presetTint(preset: String): Color = when (preset) {
    DOG_WALK -> C.camper.greenText
    "ryumochnye", "beer" -> C.camper.orangeText
    else -> C.camper.border
}

/**
 * CEO 29.10: a preset the engine could not offer because our catalogue has no such places in this town
 * (`noData`): shown disabled under the tiles with the engine's reason (`noDataRu`) — a gap of our base, not of
 * the town. Other unavailable presets stay hidden.
 */
@Composable
internal fun NoDataPresets(presets: List<CityPresetDto>) {
    Column(Modifier.fillMaxWidth().padding(top = 10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        presets.forEach { p ->
            val name = presetName(p.preset, p.titleRu)
            val title = name + stringResource(R.string.common_join_dot) + stringResource(R.string.city_preset_nodata)
            val reason = p.noDataRu ?: stringResource(R.string.walk_few_no_data_fallback)
            val cd = stringResource(R.string.cd_city_preset_nodata, name, reason)
            Row(
                Modifier.fillMaxWidth()
                    .craftSurface(
                        C.camper.header, radius = CraftDefaults.ChipRadius, border = CraftDefaults.BorderThin,
                        borderColor = C.camper.border.copy(alpha = 0.4f), shadow = null,
                    )
                    .semantics(mergeDescendants = true) { contentDescription = cd; disabled() }
                    .testTag("city.preset.nodata.${p.preset}").padding(horizontal = 12.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Icon(presetIcon(p.preset), C.camper.inkMuted, 20.dp)
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Txt(title, CraftType.chip, C.camper.inkMuted, maxLines = 1)
                    Txt(reason, CraftType.caption, C.camper.inkMuted, Modifier.testTag("city.preset.nodata.${p.preset}.reason"))
                }
            }
        }
    }
}

/** components §28 `WalkWarningPlate`, craft: paper plate, amber «!» disc, optional actions (informative: ПОШЛИ stays on). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun WalkWarningPlate(text: String, tag: String, actions: List<Pair<String, () -> Unit>> = emptyList()) {
    PlateFrame(tag) {
        Box(
            Modifier.size(22.dp).clip(CircleShape).background(C.camper.amber).border(CraftDefaults.BadgeBorder, C.camper.border, CircleShape),
            contentAlignment = Alignment.Center,
        ) { Txt("!", CraftType.badge, C.camper.onAmber) }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Txt(text, CraftType.body, C.camper.ink)
            if (actions.isNotEmpty()) {
                FlowRow(
                    Modifier.padding(end = CraftDefaults.TileShadow, bottom = CraftDefaults.TileShadow),
                    horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    actions.forEachIndexed { i, (label, onClick) ->
                        Box(
                            Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin)
                                .craftSurface(
                                    C.camper.paper, radius = CraftDefaults.FieldRadius, border = CraftDefaults.BorderThin,
                                    shadow = C.camper.border, shadowX = CraftDefaults.TileShadow, shadowY = CraftDefaults.TileShadow,
                                )
                                .clickable(role = Role.Button, onClick = onClick).testTag("$tag.action.$i").padding(horizontal = 12.dp),
                            contentAlignment = Alignment.Center,
                        ) { Txt(label, DesignTokens.type.body.smStrong, C.camper.ink, maxLines = 1) }
                    }
                }
            }
        }
    }
}

/** components §28 `WalkInfoPlate`, craft: how the walk was adapted (green check disc). */
@Composable
internal fun WalkInfoPlate(text: String, tag: String) {
    PlateFrame(tag) {
        Box(
            Modifier.size(22.dp).clip(CircleShape).background(C.camper.green).border(CraftDefaults.BadgeBorder, C.camper.border, CircleShape),
            contentAlignment = Alignment.Center,
        ) { GlyphIcon(Glyph.CHECK, C.camper.onOrange, 12.dp) }
        Txt(text, CraftType.body, C.camper.ink, Modifier.weight(1f))
    }
}

/** The plate of the warnings and notes: white paper, 2 dp brown border, radius 14, no shadow. */
@Composable
internal fun PlateFrame(tag: String, content: @Composable RowScope.() -> Unit) {
    Row(
        Modifier.fillMaxWidth()
            .craftSurface(C.camper.field, radius = 14.dp, border = CraftDefaults.BorderThin, shadow = null)
            .padding(horizontal = 12.dp, vertical = 10.dp).testTag(tag),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) { content() }
}

/**
 * 5.10 / 5.11 §10.5 «Для 8 ч рядом мало мест»: a craft card, one tile per **engine** suggestion (each verified to
 * work); the app never invents one. Without suggestions (an older engine) the plate only says what to change.
 */
@Composable
internal fun FewPlate(few: WalkFew, preset: String, excludedCount: Int, onSuggestion: (WalkSuggestion) -> Unit) {
    Column(
        Modifier.fillMaxWidth().craftSurface().testTag("walk.few").padding(CraftDefaults.CardPadding),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (few.noData) {
            // CEO 29.10: no data of this kind here is a gap of our base — the engine's sentence, not «мало мест»
            Txt(few.messageRu ?: stringResource(R.string.walk_few_no_data_fallback), CraftType.cardTitle, C.camper.ink, Modifier.testTag("walk.few.nodata"))
            if (few.suggestions.isEmpty()) Txt(stringResource(R.string.walk_few_no_data_none), CraftType.body, C.camper.inkSoft)
        } else {
            val what = if (few.unlimited) presetName(preset, preset) else durationLabel(few.durationMin)
            Txt(stringResource(R.string.walk_few_title, what), CraftType.cardTitle, C.camper.ink)
            if (few.suggestions.isEmpty()) {
                Txt(stringResource(R.string.walk_other_none_note), CraftType.body, C.camper.inkSoft)
            }
        }
        few.suggestions.forEachIndexed { i, sg ->
            val places = sg.count?.let { "$it ${pluralStringResource(R.plurals.plural_place, it)}" }
            val (title, sub) = when {
                sg.clearExclude -> stringResource(R.string.walk_few_clear) to
                    stringResource(R.string.walk_few_clear_sub, (sg.count ?: excludedCount).let { "$it ${pluralStringResource(R.plurals.plural_place, it)}" })
                sg.unlimited -> stringResource(R.string.walk_few_unlimited) to places?.let { stringResource(R.string.walk_few_unlimited_sub, it) }
                sg.durationMin != null -> stringResource(R.string.walk_few_duration, durationLabel(sg.durationMin)) to places?.let { stringResource(R.string.walk_few_duration_sub, it) }
                // «custom» with widened interests: the engine names it («История, архитектура, парки и виды»)
                sg.preset == "custom" && sg.titleRu != null -> sg.titleRu!! to places?.let { stringResource(R.string.walk_few_preset_sub, it) }
                else -> stringResource(R.string.walk_few_preset, presetName(sg.preset ?: "", sg.preset ?: "")) to places?.let { stringResource(R.string.walk_few_preset_sub, it) }
            }
            Row(
                Modifier.fillMaxWidth().padding(end = CraftDefaults.TileShadow, bottom = CraftDefaults.TileShadow).defaultMinSize(minHeight = 52.dp)
                    .craftSurface(
                        C.camper.field, radius = CraftDefaults.FieldRadius, border = CraftDefaults.BorderThin,
                        shadow = C.camper.border, shadowX = CraftDefaults.TileShadow, shadowY = CraftDefaults.TileShadow,
                    )
                    .clickable(role = Role.Button) { onSuggestion(sg) }.testTag("walk.few.$i").padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Txt(title, CraftType.chip, C.camper.ink, maxLines = 1)
                    if (sub != null) Txt(sub, CraftType.caption, C.camper.inkSoft, maxLines = 1)
                }
                Icon(R.drawable.ic_ui_chevron_right, C.camper.border, 16.dp)
            }
        }
    }
}

/** The picker sheets (5.10 prefs; 5.11 filter bar): duration, preset, crew, budget, pace; «Готово» below. */
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
        Spacer(Modifier.height(4.dp))
        when (picker) {
            CityPicker.DURATION -> DurationChips(ui.durationMin, { a.duration(it) })
            CityPicker.PRESET -> PresetGrid(ui.presets, ui.selected) { a.preset(it) }
            CityPicker.CREW -> CrewCells(ui.adults, ui.children, ui.dog, a::adults, a::children, a::dog)
            CityPicker.BUDGET -> BudgetChips(ui.budget) { a.budget(it) }
            CityPicker.PACE -> PaceChips(ui.pace) { a.pace(it) }
        }
        Spacer(Modifier.height(16.dp))
        CraftSecondaryButton(stringResource(R.string.settings_done), a::closePicker, Modifier.fillMaxWidth().testTag("city.picker.done"))
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun BudgetChips(budget: Int?, onPick: (Int?) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf(2_000, 5_000, 10_000).forEach { v -> ParamChip(stringResource(R.string.city_budget_value, app.verst.settings.AppPrefs.money(v)), budget == v, "city.budget.$v") { onPick(v) } }
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
    budget?.let { stringResource(R.string.city_budget_value, app.verst.settings.AppPrefs.money(it)) } ?: stringResource(R.string.instruments_budget_any)

@Composable
internal fun paceLabel(pace: String): String = stringResource(Paces.firstOrNull { it.first == pace }?.second ?: R.string.city_pace_normal)

/** A settings row «Бюджет на всех · до 5 000 ₽ ›» (5.10 §10 step 7): label left, the value in orange, chevron. */
@Composable
internal fun PrefRow(label: String, value: String, tag: String, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp).clickable(role = Role.Button, onClick = onClick).testTag(tag),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Txt(label, CraftType.chip, C.camper.ink, Modifier.weight(1f), maxLines = 1)
        Txt(value, DesignTokens.type.body.smStrong, C.camper.orangeText, maxLines = 1)
        Spacer(Modifier.width(6.dp))
        Icon(R.drawable.ic_ui_chevron_right, C.camper.border, 16.dp)
    }
}

/** The disabled look for a control the engine said is used up («Другие варианты нет»). */
internal fun Modifier.dimmed(on: Boolean): Modifier = if (on) this.alpha(0.35f) else this
