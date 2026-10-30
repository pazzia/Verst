package app.verst.feature.city

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.dto.CityPresetDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.PlaceholderPlate
import app.verst.core.ui.components.StartButton
import app.verst.core.ui.components.StartSize
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.WalkerIcon
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.NaviDialog
import app.verst.feature.common.ScreenRoot
import app.verst.nav.CityPicker
import app.verst.nav.DOG_WALK
import app.verst.nav.WalkFew
import app.verst.core.model.dto.WalkSuggestion
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T
import app.verst.nav.visibleCityPresets

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

/** 5.10 «По городу» (S4 §10): a fresh walk setup — start, who goes, which walk, how long, wishes. */
@Composable
fun CityScreen(ui: CityUi, a: CityActions) {
    ScreenRoot(C.city.sky, statusBar = C.city.sky) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val windowH = maxHeight
            Column(Modifier.fillMaxSize().background(C.dash.raised)) {
                Box(Modifier.fillMaxWidth().height(203.dp)) {
                    CityScene(Modifier.fillMaxWidth().height(200.dp), crop = 200.dp)
                    Box(Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(3.dp).background(C.city.curb))
                    val back = stringResource(R.string.common_back_to_windshield)
                    BackLink(back, C.mirror.label, stringResource(R.string.cd_back, back), a::back, Modifier.padding(start = 12.dp, top = 8.dp).testTag("city.back"))
                    StreetPlate(ui.town, ui.startLabel, Modifier.padding(start = 20.dp, top = 44.dp))
                }
                Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp)) {
                    // 2. СТАРТ ПРОГУЛКИ — one target → the 5.12 search
                    SectionLabel(stringResource(R.string.city_start_label))
                    StartField(ui, a::changeStart)
                    // 3. КТО ИДЁТ
                    SectionLabel(stringResource(R.string.city_crew_label))
                    CrewCells(ui.adults, ui.children, ui.dog, a::adults, a::children, a::dog)
                    // 4. КАКАЯ ПРОГУЛКА (+ the errors)
                    SectionLabel(stringResource(R.string.city_type_label))
                    when {
                        ui.error == "NO_CITY" -> StatePlate(
                            stringResource(R.string.city_no_city_title), stringResource(R.string.city_no_city_body),
                            listOf(stringResource(R.string.city_no_city_action) to a::changeStart), "city.nocity",
                        )
                        ui.loading && ui.presets.isEmpty() -> Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            PlaceholderPlate(170.dp, DesignTokens.size.presetH, C.dash.controlAlt)
                            PlaceholderPlate(170.dp, DesignTokens.size.presetH, C.dash.controlAlt)
                        }
                        else -> {
                            PresetGrid(ui.presets, ui.selected, a::preset)
                            if (ui.noDataPresets.isNotEmpty()) NoDataPresets(ui.noDataPresets)
                        }
                    }
                    // 5. warnings (informative: ПОШЛИ stays on)
                    CityWarnings(ui, a)
                    ui.few?.let { f ->
                        Spacer(Modifier.height(10.dp))
                        // the plate answers ПОШЛИ: bring it (with its suggestions) into view above the caption row
                        val bring = androidx.compose.runtime.remember { androidx.compose.foundation.relocation.BringIntoViewRequester() }
                        androidx.compose.runtime.LaunchedEffect(f) { runCatching { bring.bringIntoView() } }
                        Box(Modifier.bringIntoViewRequester(bring)) { FewPlate(f, ui.selected, ui.excludedCount, a::suggestion) }
                    }
                    // 6. СКОЛЬКО ГУЛЯЕМ
                    SectionLabel(stringResource(R.string.city_duration_label))
                    DurationChips(ui.durationMin, a::duration)
                    // 7. ПОЖЕЛАНИЯ И ОГРАНИЧЕНИЯ
                    SectionLabel(stringResource(R.string.city_prefs_label))
                    PrefsPlate(ui, a)
                    Spacer(Modifier.height(16.dp))
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

/** components §27 `StartField`: locate icon, the address, «Москва · вы здесь», «изменить» — one target. */
@Composable
private fun StartField(ui: CityUi, onClick: () -> Unit) {
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    val cd = stringResource(R.string.cd_city_start, ui.startLabel)
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 60.dp).clip(shape).background(C.navi.field)
            .border(2.dp, C.accent.yellowText, shape).clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }.testTag("city.start")
            .padding(start = 14.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        GlyphIcon(Glyph.LOCATE, C.accent.yellowText, 22.dp)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Txt(ui.startLabel, T.title.sm, C.text.primary, Modifier.testTag("city.start.label"), maxLines = 1)
            if (ui.fromGps && ui.town != null) Txt(stringResource(R.string.city_start_here, ui.town), T.body.sm, C.navi.labelSecondary, maxLines = 1)
            else if (ui.town != null && ui.town != ui.startLabel) Txt(ui.town, T.body.sm, C.navi.labelSecondary, maxLines = 1)
        }
        Row(
            Modifier.height(40.dp).clip(RoundedCornerShape(DesignTokens.radius.r8)).background(C.dash.control).padding(horizontal = 12.dp).testTag("city.change"),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            GlyphIcon(Glyph.PENCIL, C.text.secondary, 16.dp)
            Txt(stringResource(R.string.city_start_change), T.body.smStrong, C.text.secondary, maxLines = 1)
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
    Column(Modifier.padding(top = 10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (ui.children > 0 && drink) WalkWarningPlate(stringResource(R.string.walk_warn_child_bars), "city.warn.childbars")
        if (ui.dog && drink) WalkWarningPlate(stringResource(R.string.walk_warn_dog_bars), "city.warn.dogbars", dogActions)
        if (ui.dog && indoor) WalkWarningPlate(stringResource(R.string.walk_warn_dog_indoor), "city.warn.dogindoor", dogActions)
    }
}

/** 5.10 §10 step 7: «Бюджет на всех ›», «Темп ›», «Вернуться к старту» (switch). */
@Composable
private fun PrefsPlate(ui: CityUi, a: CityActions) {
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    Column(Modifier.fillMaxWidth().clip(shape).background(C.dash.control).border(DesignTokens.stroke.w1, C.dash.outline, shape)) {
        PrefRow(stringResource(R.string.city_pref_budget), budgetLabel(ui.budget), "city.pref.budget") { a.openPicker(CityPicker.BUDGET) }
        Box(Modifier.fillMaxWidth().height(1.dp).background(C.dash.outline))
        PrefRow(stringResource(R.string.city_pref_pace), paceLabel(ui.pace), "city.pref.pace") { a.openPicker(CityPicker.PACE) }
        Box(Modifier.fillMaxWidth().height(1.dp).background(C.dash.outline))
        Row(
            Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp)
                .toggleable(ui.returnToStart, role = Role.Switch, onValueChange = { a.toggleReturn() }).testTag("city.return").padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Txt(stringResource(R.string.city_pref_return), T.body.mdStrong, C.text.primary, Modifier.weight(1f))
            Box(
                Modifier.size(44.dp, 26.dp).clip(RoundedCornerShape(13.dp)).background(if (ui.returnToStart) C.accent.yellow else C.dash.controlAlt),
                contentAlignment = if (ui.returnToStart) Alignment.CenterEnd else Alignment.CenterStart,
            ) { Box(Modifier.padding(3.dp).size(20.dp).clip(CircleShape).background(if (ui.returnToStart) C.text.onLight else C.text.secondary)) }
        }
    }
}

@Composable
private fun StatePlate(title: String, body: String, actions: List<Pair<String, () -> Unit>>, tag: String) {
    Column(
        Modifier.fillMaxWidth().border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r10)).padding(12.dp).testTag(tag),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Txt(title, T.title.sm, C.text.primary)
        Txt(body, T.body.md, C.text.secondary)
        actions.forEachIndexed { i, (label, onClick) ->
            Box(
                Modifier.fillMaxWidth().height(48.dp).clip(RoundedCornerShape(DesignTokens.radius.r10)).background(C.dash.control)
                    .border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r10))
                    .clickable(role = Role.Button, onClick = onClick).testTag("$tag.$i"),
                contentAlignment = Alignment.Center,
            ) { Txt(label, T.button.md, C.text.primary, maxLines = 1) }
        }
    }
}

@Composable
private fun Caption(ui: CityUi, a: CityActions) {
    Row(
        Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, bottom = 24.dp, top = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f).padding(end = 14.dp).semantics(mergeDescendants = true) {}) {
            Txt(stringResource(R.string.city_caption_label), T.label.md, C.text.muted)
            if (ui.building) {
                Txt(stringResource(R.string.city_building), T.title.lg, C.text.primary, Modifier.testTag("city.building"), maxLines = 1)
                PlaceholderPlate(140.dp, 12.dp, C.dash.controlAlt, Modifier.padding(top = 4.dp))
            } else {
                val name = presetName(ui.selected, ui.selected)
                Txt(
                    if (ui.durationMin == null) "$name${stringResource(R.string.common_join_dot)}${stringResource(R.string.city_duration_unlimited)}"
                    else stringResource(R.string.city_caption_title, name, ui.durationMin / 60),
                    T.title.lg, C.text.primary, Modifier.testTag("city.caption"), maxLines = 2, // «Пивной · без ограничения»
                )
                val crew = crewLine(ui.adults, ui.children, ui.dog)
                Txt(
                    when {
                        ui.durationMin == null -> stringResource(R.string.city_caption_untimed, crew)
                        ui.startTomorrow -> stringResource(R.string.city_caption_meta_tomorrow, crew, ui.startTime)
                        else -> stringResource(R.string.city_caption_meta, crew, ui.startTime)
                    },
                    T.body.mdTight, C.text.secondary, Modifier.testTag("city.caption.meta"), maxLines = 1,
                )
            }
        }
        val label = stringResource(R.string.city_go)
        StartButton(
            StartSize.M, label, enabled = ui.error != "NO_CITY" && ui.presets.isNotEmpty() && !ui.building, cd = label,
            onClick = a::go, modifier = Modifier.testTag("city.go"), walker = true, loading = ui.building,
        )
    }
}

/** 5.10 §5 «Свой маршрут»: the interests (duration, pace, budget and the return live on 5.10 itself). */
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
        Box(
            Modifier.fillMaxWidth().height(56.dp).clip(RoundedCornerShape(DesignTokens.radius.r12)).background(C.accent.yellow)
                .clickable(role = Role.Button, onClick = a::buildCustom).testTag("city.build"),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.city_build), T.cta.sm, C.text.onLight, maxLines = 1) }
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
private fun Label(text: String) = Txt(text, T.label.md, C.text.muted, Modifier.padding(top = 16.dp, bottom = 6.dp))

/** components §21 `StreetPlate`: «пешком · Ярославль» / the street (+ the house square when there is a number). */
@Composable
private fun StreetPlate(town: String?, start: String, modifier: Modifier) {
    val street = start.substringBeforeLast(",").takeIf { start.contains(',') && start.substringAfterLast(",").trim().firstOrNull()?.isDigit() == true } ?: start
    val house = start.substringAfterLast(",").trim().takeIf { start.contains(',') && it.firstOrNull()?.isDigit() == true }
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        PlateBox(Modifier.widthIn(max = 280.dp)) {
            Column {
                Txt(
                    listOfNotNull(stringResource(R.string.city_plate_kind), town).joinToString(" · "),
                    T.street.kind, C.sign.blueText, maxLines = 1,
                )
                Txt(street.substringAfter(", ").ifBlank { street }, T.street.name, C.sign.white, Modifier.testTag("city.plate"), maxLines = 1)
            }
        }
        if (house != null) PlateBox(Modifier.size(DesignTokens.size.streetPlateH)) { Txt(house, T.street.name, C.sign.white, maxLines = 1) }
    }
}

@Composable
private fun PlateBox(modifier: Modifier, content: @Composable () -> Unit) {
    Box(
        modifier.height(DesignTokens.size.streetPlateH).clip(RoundedCornerShape(DesignTokens.radius.r6)).background(C.sign.blue).padding(4.dp)
            .border(DesignTokens.stroke.w2, C.sign.white, RoundedCornerShape(DesignTokens.radius.r4)).padding(horizontal = 12.dp, vertical = 6.dp),
        contentAlignment = Alignment.CenterStart,
    ) { content() }
}

/** components §21 `CityScene` (decorative): roofs, facades with lit windows, pavement, lamps; no roof liner. */
@Composable
fun CityScene(modifier: Modifier, crop: Dp) {
    Canvas(modifier.semantics { }) {
        val k = size.width / 390f
        val hScale = crop.toPx() / (200f * k)
        fun y(v: Float) = v * k * hScale
        fun x(v: Float) = v * k
        drawRect(C.city.sky)
        val roof = Path().apply {
            val pts = listOf(0 to 112, 34 to 112, 34 to 96, 80 to 96, 80 to 106, 128 to 106, 128 to 88, 150 to 80, 172 to 88, 172 to 104, 230 to 104, 230 to 92, 270 to 92, 270 to 108, 318 to 108, 318 to 94, 390 to 94)
            moveTo(x(pts[0].first.toFloat()), y(pts[0].second.toFloat()))
            pts.drop(1).forEach { (px, py) -> lineTo(x(px.toFloat()), y(py.toFloat())) }
            lineTo(x(390f), y(200f)); lineTo(0f, y(200f)); close()
        }
        drawPath(roof, C.city.facadeC)
        val blocks = listOf(0f to 70f, 70f to 150f, 150f to 236f, 236f to 318f, 318f to 390f)
        blocks.forEachIndexed { i, (a, b) -> drawRect(C.city.facadeB, Offset(x(a), y(if (i % 2 == 0) 124f else 132f)), Size(x(b - a), y(200f) - y(if (i % 2 == 0) 124f else 132f))) }
        drawRect(C.city.facadeA, Offset(0f, y(140f)), Size(size.width, y(186f) - y(140f)))
        var idx = 0
        for (row in listOf(150f, 172f)) {
            var wx = 8f
            while (wx < 382f) {
                val lit = (idx * 7 + (row.toInt() / 22)) % 5 < 3 // ≈ 60 % lit, a fixed index pattern
                drawRect(if (lit) C.city.window else C.city.windowOff, Offset(x(wx), y(row)), Size(x(10f), y(14f)))
                wx += 22f
                idx++
            }
        }
        drawRect(C.city.sidewalk, Offset(0f, y(186f)), Size(size.width, y(200f) - y(186f)))
        var jx = 0f
        while (jx < 390f) {
            drawLine(C.city.joint, Offset(x(jx), y(186f)), Offset(x(jx), y(200f)), 1.dp.toPx())
            jx += 24f
        }
        for (lx in listOf(56f, 196f, 336f)) {
            drawCircle(Brush.radialGradient(listOf(C.city.lampGlow, Color.Transparent), Offset(x(lx), y(137f)), x(18f)), x(18f), Offset(x(lx), y(137f)))
            drawRect(C.interior.pole, Offset(x(lx - 1.5f), y(134f)), Size(x(3f), y(52f)))
            drawRect(C.city.lamp, Offset(x(lx - 7f), y(131f)), Size(x(14f), y(6f)))
        }
    }
}

