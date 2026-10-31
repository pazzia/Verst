package app.verst.feature.city

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.dto.CityPresetDto
import app.verst.core.model.dto.WalkSuggestion
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftSecondaryButton
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.DashedDivider
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.PlaceholderPlate
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.NaviDialog
import app.verst.feature.common.ScreenRoot
import app.verst.nav.CityPicker
import app.verst.nav.DOG_WALK
import app.verst.nav.WalkFew
import app.verst.core.ui.theme.DesignTokens.color as C

/** 5.10 state (stateless; `VerstRoot` maps `VerstFlow` into it). */
data class CityUi(
    val town: String?,
    /** «Советская пл., 1» / «Ярославль» — what the start field names. */
    val startLabel: String,
    val fromGps: Boolean,
    /** The visible presets in display order (`VerstFlow.visibleCityPresets`). */
    val presets: List<CityPresetDto>,
    val loading: Boolean,
    val error: String?,
    val selected: String,
    /** null = «без ограничения». */
    val durationMin: Int?,
    val interests: List<String>,
    val pace: String,
    val budget: Int?,
    val returnToStart: Boolean,
    val customSheet: Boolean,
    val ageGate: Boolean,
    val building: Boolean,
    val adults: Int = 2,
    val children: Int = 0,
    val dog: Boolean = false,
    val startTime: String,
    /** S3-QA P0-01: the start is the next day's window opening. */
    val startTomorrow: Boolean = false,
    /** `NOT_ENOUGH_POIS` with the engine's suggestions. */
    val few: WalkFew? = null,
    val picker: CityPicker? = null,
    val excludedCount: Int = 0,
    /** CEO 29.10: presets our catalogue has no places for here (`noData`), shown disabled with `noDataRu`. */
    val noDataPresets: List<CityPresetDto> = emptyList(),
) {
    val pickerUi: PickerUi get() = PickerUi(durationMin, presets, selected, adults, children, dog, pace, budget)
}

interface CityActions : PickerActions {
    fun back()
    fun changeStart()
    fun go()
    fun interest(i: String)
    fun toggleReturn()
    fun closeCustom()
    fun buildCustom()
    fun age(yes: Boolean)
    fun suggestion(s: WalkSuggestion)
    fun openPicker(p: CityPicker)
    override fun duration(min: Int?) = Unit
    override fun adults(n: Int) = Unit
    override fun children(n: Int) = Unit
    override fun dog(on: Boolean) = Unit
    override fun pace(p: String) = Unit
    override fun budget(rub: Int?) = Unit
    override fun closePicker() = Unit
}

/**
 * 5.10 «По городу» (S4 §10), camper fork (mockup screen 10 «По городу пешком»): craft cards on the paper page —
 * «Прогулка по городу» (start, who goes), the preset tiles, how long, wishes; the caption and «ПОШЛИ» below.
 * The app header and the tab bar are drawn around the screen by `VerstRoot`.
 */
@Composable
fun CityScreen(ui: CityUi, a: CityActions) {
    ScreenRoot(C.camper.page) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val windowH = maxHeight
            Column(Modifier.fillMaxSize()) {
                Column(
                    Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                        .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 4.dp, bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(CraftDefaults.Gap),
                ) {
                    val back = stringResource(R.string.common_back_to_windshield)
                    BackLink(back, C.camper.inkSoft, stringResource(R.string.cd_back, back), a::back, Modifier.testTag("city.back"))
                    // 1–3. «Прогулка по городу»: where it starts and who goes
                    CraftCard(Modifier.fillMaxWidth()) {
                        CardHeading(
                            stringResource(R.string.windshield_city_title),
                            overline = listOfNotNull(stringResource(R.string.city_plate_kind), ui.town).joinToString(" · ").uppercase(),
                            overlineTag = "city.plate",
                        )
                        // 2. СТАРТ ПРОГУЛКИ — one target → the 5.12 search
                        SectionLabel(stringResource(R.string.city_start_label))
                        StartField(ui, a::changeStart)
                        // 3. КТО ИДЁТ
                        SectionLabel(stringResource(R.string.city_crew_label))
                        CrewCells(ui.adults, ui.children, ui.dog, a::adults, a::children, a::dog)
                    }
                    // 4. КАКАЯ ПРОГУЛКА (+ the errors)
                    CraftCard(Modifier.fillMaxWidth()) {
                        SectionLabel(stringResource(R.string.city_type_label))
                        when {
                            ui.error == "NO_CITY" -> StatePlate(
                                stringResource(R.string.city_no_city_title), stringResource(R.string.city_no_city_body),
                                listOf(stringResource(R.string.city_no_city_action) to a::changeStart), "city.nocity",
                            )
                            ui.loading && ui.presets.isEmpty() -> Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                PlaceholderPlate(150.dp, DesignTokens.size.presetH, C.camper.header)
                                PlaceholderPlate(150.dp, DesignTokens.size.presetH, C.camper.header)
                            }
                            else -> {
                                PresetGrid(ui.presets, ui.selected, a::preset)
                                if (ui.noDataPresets.isNotEmpty()) NoDataPresets(ui.noDataPresets)
                            }
                        }
                    }
                    // 5. warnings (informative: ПОШЛИ stays on)
                    CityWarnings(ui, a)
                    ui.few?.let { f ->
                        // the plate answers ПОШЛИ: bring it (with its suggestions) into view above the caption row
                        val bring = remember { BringIntoViewRequester() }
                        LaunchedEffect(f) { runCatching { bring.bringIntoView() } }
                        Box(Modifier.bringIntoViewRequester(bring)) { FewPlate(f, ui.selected, ui.excludedCount, a::suggestion) }
                    }
                    // 6. СКОЛЬКО ГУЛЯЕМ
                    CraftCard(Modifier.fillMaxWidth()) {
                        SectionLabel(stringResource(R.string.city_duration_label))
                        DurationChips(ui.durationMin, a::duration)
                    }
                    // 7. ПОЖЕЛАНИЯ И ОГРАНИЧЕНИЯ
                    CraftCard(Modifier.fillMaxWidth(), spacing = 4.dp) {
                        SectionLabel(stringResource(R.string.city_prefs_label))
                        PrefsRows(ui, a)
                    }
                }
                Caption(ui, a)
            }
            if (ui.customSheet) CustomSheet(ui, windowH, a)
            ui.picker?.let { CityPickerSheet(it, ui.pickerUi, windowH, a) }
            if (ui.ageGate) {
                // S4: only the question, «Нет» / «Да» of equal width
                NaviDialog(
                    stringResource(R.string.age_gate_question), "",
                    stringResource(R.string.age_gate_yes_short), stringResource(R.string.age_gate_no), "agegate",
                    { a.age(true) }, { a.age(false) }, sideBySide = true,
                )
            }
        }
    }
}

/** components §27 `StartField`, craft: location arrow, the address, «Москва · вы здесь», «изменить» — one target. */
@Composable
private fun StartField(ui: CityUi, onClick: () -> Unit) {
    val cd = stringResource(R.string.cd_city_start, ui.startLabel)
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 56.dp).craftField()
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }.testTag("city.start")
            .padding(start = 12.dp, end = 6.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(R.drawable.ic_ui_location_arrow, C.camper.orangeText, 20.dp)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Txt(ui.startLabel, CraftType.cardTitle, C.camper.ink, Modifier.testTag("city.start.label"), maxLines = 1)
            if (ui.fromGps && ui.town != null) Txt(stringResource(R.string.city_start_here, ui.town), CraftType.caption, C.camper.inkSoft, maxLines = 1)
            else if (ui.town != null && ui.town != ui.startLabel) Txt(ui.town, CraftType.caption, C.camper.inkSoft, maxLines = 1)
        }
        Box(Modifier.defaultMinSize(minHeight = 40.dp).padding(horizontal = 8.dp).testTag("city.change"), contentAlignment = Alignment.Center) {
            Txt(stringResource(R.string.city_start_change), DesignTokens.type.body.smStrong, C.camper.orangeText, maxLines = 1)
        }
    }
}

/** 5.10 §10 step 5: what may get in the way, from the walk's crew and the chosen preset. */
@Composable
private fun CityWarnings(ui: CityUi, a: CityActions) {
    val drink = ui.selected in setOf("ryumochnye", "beer") || (ui.selected == "custom" && "bars" in ui.interests)
    val indoor = ui.selected == "museums"
    val dogWalk = ui.presets.any { it.preset == DOG_WALK }
    val dogActions = buildList {
        if (dogWalk) add(stringResource(R.string.walk_action_dog_walk) to { a.preset(DOG_WALK) })
        add(stringResource(R.string.walk_action_dog_home) to { a.dog(false) })
    }
    val child = ui.children > 0 && drink
    val dogBars = ui.dog && drink
    val dogIndoor = ui.dog && indoor
    if (!child && !dogBars && !dogIndoor) return
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (child) WalkWarningPlate(stringResource(R.string.walk_warn_child_bars), "city.warn.childbars")
        if (dogBars) WalkWarningPlate(stringResource(R.string.walk_warn_dog_bars), "city.warn.dogbars", dogActions)
        if (dogIndoor) WalkWarningPlate(stringResource(R.string.walk_warn_dog_indoor), "city.warn.dogindoor", dogActions)
    }
}

/** 5.10 §10 step 7: «Бюджет на всех ›», «Темп ›», «Вернуться к старту» (switch), dashed rules between. */
@Composable
private fun PrefsRows(ui: CityUi, a: CityActions) {
    PrefRow(stringResource(R.string.city_pref_budget), budgetLabel(ui.budget), "city.pref.budget") { a.openPicker(CityPicker.BUDGET) }
    DashedDivider()
    PrefRow(stringResource(R.string.city_pref_pace), paceLabel(ui.pace), "city.pref.pace") { a.openPicker(CityPicker.PACE) }
    DashedDivider()
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp)
            .toggleable(ui.returnToStart, role = Role.Switch, onValueChange = { a.toggleReturn() }).testTag("city.return"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Txt(stringResource(R.string.city_pref_return), CraftType.chip, C.camper.ink, Modifier.weight(1f))
        CraftSwitch(ui.returnToStart)
    }
}

/** «Рядом нет города»: the sentence and the way out as paper craft buttons. */
@Composable
private fun StatePlate(title: String, body: String, actions: List<Pair<String, () -> Unit>>, tag: String) {
    Column(
        Modifier.fillMaxWidth().testTag(tag),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Txt(title, CraftType.cardTitle, C.camper.ink)
        Txt(body, CraftType.body, C.camper.inkSoft)
        actions.forEachIndexed { i, (label, onClick) ->
            CraftSecondaryButton(label, onClick, Modifier.fillMaxWidth().padding(bottom = CraftDefaults.ShadowY).testTag("$tag.$i"))
        }
    }
}

/** The caption under the cards: «ПРОГУЛКА», what is chosen, who and when — and the orange «ПОШЛИ». */
@Composable
private fun Caption(ui: CityUi, a: CityActions) {
    Column(Modifier.fillMaxWidth()) {
        DashedDivider()
        Row(
            Modifier.fillMaxWidth().padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 10.dp, bottom = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f).padding(end = 12.dp).semantics(mergeDescendants = true) {}) {
                Txt(stringResource(R.string.city_caption_label), CraftType.overline, C.camper.orangeText)
                if (ui.building) {
                    Txt(stringResource(R.string.city_building), CraftType.cardTitle, C.camper.ink, Modifier.testTag("city.building"), maxLines = 1)
                    PlaceholderPlate(140.dp, 12.dp, C.camper.header, Modifier.padding(top = 4.dp))
                } else {
                    val name = presetName(ui.selected, ui.selected)
                    Txt(
                        if (ui.durationMin == null) "$name${stringResource(R.string.common_join_dot)}${stringResource(R.string.city_duration_unlimited)}"
                        else stringResource(R.string.city_caption_title, name, ui.durationMin / 60),
                        CraftType.cardTitle, C.camper.ink, Modifier.testTag("city.caption"), maxLines = 2, // «Пивной · без ограничения»
                    )
                    val crew = crewLine(ui.adults, ui.children, ui.dog)
                    Txt(
                        when {
                            ui.durationMin == null -> stringResource(R.string.city_caption_untimed, crew)
                            ui.startTomorrow -> stringResource(R.string.city_caption_meta_tomorrow, crew, ui.startTime)
                            else -> stringResource(R.string.city_caption_meta, crew, ui.startTime)
                        },
                        CraftType.caption, C.camper.inkSoft, Modifier.testTag("city.caption.meta"), maxLines = 1,
                    )
                }
            }
            CraftButton(
                stringResource(R.string.city_go), a::go, Modifier.testTag("city.go"),
                icon = R.drawable.ic_tourist_walk, enabled = ui.error != "NO_CITY" && ui.presets.isNotEmpty() && !ui.building,
            )
        }
    }
}

/** 5.10 §5 «Свой маршрут»: the interests and the duration (pace, budget and the return live on 5.10 itself). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun BoxScope.CustomSheet(ui: CityUi, windowH: Dp, a: CityActions) {
    BottomSheet(stringResource(R.string.city_custom_title), a::closeCustom, "city.custom", windowH) {
        Label(stringResource(R.string.city_interests_label))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Interests.forEach { (key, res) -> ParamChip(stringResource(res), key in ui.interests, "city.interest.$key", multi = true) { a.interest(key) } }
        }
        Label(stringResource(R.string.city_duration_label))
        DurationChips(ui.durationMin, a::duration, hint = false)
        Spacer(Modifier.height(18.dp))
        CraftButton(
            stringResource(R.string.city_build).uppercase(), a::buildCustom, Modifier.fillMaxWidth().testTag("city.build"),
            icon = R.drawable.ic_tourist_walk,
        )
    }
}

private val Interests = listOf(
    "history" to R.string.city_interest_history,
    "architecture" to R.string.city_interest_architecture,
    "museums" to R.string.city_interest_museums,
    "parks" to R.string.city_interest_parks,
    "food" to R.string.city_interest_food,
    "bars" to R.string.city_interest_bars,
    "views" to R.string.city_interest_views,
)

@Composable
private fun Label(text: String) = SectionLabel(text, Modifier.padding(top = 14.dp, bottom = 6.dp))
