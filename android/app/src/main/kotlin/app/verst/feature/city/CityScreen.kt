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
import app.verst.core.model.RuFormat
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
import app.verst.nav.WalkDurations
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** 5.10 state (stateless; `VerstRoot` maps `VerstFlow` into it). */
data class CityUi(
    val town: String?,
    /** «Советская пл., 1» / «Ярославль» — what the start line names. */
    val startLabel: String,
    val fromGps: Boolean,
    val presets: List<CityPresetDto>,
    val loading: Boolean,
    val error: String?,
    val selected: String,
    val durationMin: Int,
    val interests: List<String>,
    val pace: String,
    val budget: Int?,
    val returnToStart: Boolean,
    val customSheet: Boolean,
    val ageGate: Boolean,
    val building: Boolean,
    val children: Boolean,
    val startTime: String,
    /** S3-QA P0-01: the start is the next day's window opening. */
    val startTomorrow: Boolean = false,
)

interface CityActions {
    fun back()
    fun changeStart()
    fun preset(p: String)
    fun go()
    fun duration(min: Int)
    fun interest(i: String)
    fun pace(p: String)
    fun budget(rub: Int?)
    fun toggleReturn()
    fun closeCustom()
    fun buildCustom()
    fun age(yes: Boolean)
    fun longer()
    fun otherPreset()
}

private val PresetOrder = listOf("overview", "museums", "ryumochnye", "beer", "custom")

/** 5.10 «По городу»: stepping out of the car — the evening street, the street plate, the brown preset plates. */
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
                    Spacer(Modifier.height(15.dp))
                    Txt(stringResource(R.string.city_title), T.display, C.text.primary, Modifier.semantics { heading() })
                    Row(Modifier.fillMaxWidth().padding(top = 6.dp).defaultMinSize(minHeight = 44.dp), verticalAlignment = Alignment.CenterVertically) {
                        Txt(stringResource(R.string.city_start, ui.startLabel), T.body.mdTight, C.text.secondary, Modifier.weight(1f).testTag("city.start"), maxLines = 2)
                        Box(
                            Modifier.height(44.dp).clickable(role = Role.Button, onClick = a::changeStart).testTag("city.change"),
                            contentAlignment = Alignment.Center,
                        ) {
                            Box(
                                Modifier.height(36.dp).border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r8)).padding(horizontal = 10.dp),
                                contentAlignment = Alignment.Center,
                            ) { Txt(stringResource(R.string.city_start_change), T.body.smStrong, C.text.secondary) }
                        }
                    }
                    Spacer(Modifier.height(12.dp))
                    when {
                        ui.error == "NO_CITY" -> StatePlate(
                            stringResource(R.string.city_no_city_title), stringResource(R.string.city_no_city_body),
                            listOf(stringResource(R.string.city_no_city_action) to a::changeStart), "city.nocity",
                        )
                        ui.error == "NOT_ENOUGH_POIS" -> StatePlate(
                            stringResource(R.string.city_not_enough_title), stringResource(R.string.city_not_enough_body),
                            listOf(
                                stringResource(R.string.city_not_enough_longer, ((WalkDurations.firstOrNull { it > ui.durationMin } ?: WalkDurations.last()) / 60)) to a::longer,
                                stringResource(R.string.city_not_enough_other) to a::otherPreset,
                            ),
                            "city.notenough",
                        )
                        else -> {
                            Txt(stringResource(R.string.city_presets_label), T.label.md, C.text.muted)
                            Spacer(Modifier.height(8.dp))
                            if (ui.loading && ui.presets.isEmpty()) {
                                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                    PlaceholderPlate(170.dp, DesignTokens.size.presetH, C.dash.controlAlt)
                                    PlaceholderPlate(170.dp, DesignTokens.size.presetH, C.dash.controlAlt)
                                }
                            } else {
                                PresetGrid(ui, a)
                            }
                        }
                    }
                    Spacer(Modifier.height(16.dp))
                }
                Caption(ui, a)
            }
            if (ui.customSheet) CustomSheet(ui, windowH, a)
            if (ui.ageGate) {
                NaviDialog(
                    stringResource(R.string.age_gate_title), stringResource(R.string.age_gate_body),
                    stringResource(R.string.age_gate_yes), stringResource(R.string.age_gate_no), "agegate",
                    { a.age(true) }, { a.age(false) },
                )
            }
        }
    }
}

@Composable
private fun PresetGrid(ui: CityUi, a: CityActions) {
    // only the presets the city supports (`available`); «Свой маршрут» always last
    val shown = ui.presets.filter { it.available }.sortedBy { PresetOrder.indexOf(it.preset).let { i -> if (i < 0) 99 else i } }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        shown.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { p -> PresetPlate(p, p.preset == ui.selected, ui.children, Modifier.weight(1f)) { a.preset(p.preset) } }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
internal fun presetName(p: String, fallback: String = ""): String = when (p) {
    "overview" -> stringResource(R.string.city_preset_overview)
    "museums" -> stringResource(R.string.city_preset_museums)
    "ryumochnye" -> stringResource(R.string.city_preset_ryumochnye)
    "beer" -> stringResource(R.string.city_preset_beer)
    "custom" -> stringResource(R.string.city_preset_custom)
    else -> fallback
}

@Composable
private fun presetSub(p: CityPresetDto, kidsBlocked: Boolean): String {
    val h = p.defaultDurationMin / 60
    if (p.adultOnly && kidsBlocked) return stringResource(R.string.city_kids_blocked)
    return when (p.preset) {
        "overview" -> stringResource(R.string.city_preset_overview_sub, h)
        "museums" -> stringResource(R.string.city_preset_museums_sub, h)
        "ryumochnye" -> stringResource(R.string.city_preset_ryumochnye_sub, h)
        "beer" -> stringResource(R.string.city_preset_beer_sub, h)
        else -> stringResource(R.string.city_preset_custom_sub)
    }
}

/** components §21 `PresetPlate`: the brown tourist plate, pictogram, name, sub; 18+ badge; selected outline + check. */
@Composable
private fun PresetPlate(p: CityPresetDto, selected: Boolean, children: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val custom = p.preset == "custom"
    val disabled = p.adultOnly && children
    val name = presetName(p.preset, p.titleRu)
    val sub = presetSub(p, children)
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
            .padding(horizontal = 12.dp, vertical = 6.dp) // 10 in the spec; the 3 dp inner border leaves no room for 24 + 2 lines
            .alpha(if (disabled) 0.45f else 1f),
    ) {
        val icon = when (p.preset) {
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
            if (ui.building) {
                // 5.10 §7: the caption shimmers with «Собираем прогулку…»
                Txt(stringResource(R.string.city_caption_label), T.label.md, C.text.muted)
                Txt(stringResource(R.string.city_building), T.title.lg, C.text.primary, Modifier.testTag("city.building"), maxLines = 1)
                PlaceholderPlate(140.dp, 12.dp, C.dash.controlAlt, Modifier.padding(top = 4.dp))
            } else {
                Txt(stringResource(R.string.city_caption_label), T.label.md, C.text.muted)
                Txt(
                    stringResource(R.string.city_caption_title, presetName(ui.selected, ui.selected), ui.durationMin / 60),
                    T.title.lg, C.text.primary, Modifier.testTag("city.caption"), maxLines = 1,
                )
                if (ui.town != null) {
                    Txt(
                        stringResource(if (ui.startTomorrow) R.string.city_caption_meta_tomorrow else R.string.city_caption_meta, ui.town, ui.startTime),
                        T.body.mdTight, C.text.secondary, Modifier.testTag("city.caption.meta"), maxLines = 1,
                    )
                }
            }
        }
        val label = stringResource(R.string.city_go)
        StartButton(
            StartSize.M, label, enabled = ui.error != "NO_CITY" && ui.presets.any { it.available } && !ui.building, cd = label,
            onClick = a::go, modifier = Modifier.testTag("city.go"), walker = true, loading = ui.building,
        )
    }
}

/** 5.10 §5 «Свой маршрут». */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun BoxScope.CustomSheet(ui: CityUi, windowH: Dp, a: CityActions) {
    BottomSheet(stringResource(R.string.city_custom_title), a::closeCustom, "city.custom", windowH) {
        Label(stringResource(R.string.city_duration_label))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            WalkDurations.forEach { m -> ParamChip(stringResource(R.string.city_duration, m / 60), ui.durationMin == m, "city.duration.$m") { a.duration(m) } }
        }
        Label(stringResource(R.string.city_interests_label))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Interests.forEach { (key, res) -> ParamChip(stringResource(res), key in ui.interests, "city.interest.$key", multi = true) { a.interest(key) } }
        }
        Label(stringResource(R.string.city_pace_label))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("slow" to R.string.city_pace_slow, "normal" to R.string.city_pace_normal, "fast" to R.string.city_pace_fast).forEach { (k, res) ->
                ParamChip(stringResource(res), ui.pace == k, "city.pace.$k") { a.pace(k) }
            }
        }
        Label(stringResource(R.string.city_budget_label))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(2_000, 5_000, 10_000).forEach { v -> ParamChip(stringResource(R.string.city_budget_value, RuFormat.thousands(v)), ui.budget == v, "city.budget.$v") { a.budget(v) } }
            ParamChip(stringResource(R.string.instruments_budget_any), ui.budget == null, "city.budget.any") { a.budget(null) }
        }
        Row(
            Modifier.fillMaxWidth().padding(top = 16.dp).defaultMinSize(minHeight = 44.dp)
                .toggleable(ui.returnToStart, role = Role.Switch, onValueChange = { a.toggleReturn() }).testTag("city.return"),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Txt(stringResource(R.string.city_return_label), T.body.mdStrong, C.text.primary, Modifier.weight(1f))
            Box(
                Modifier.size(44.dp, 26.dp).clip(RoundedCornerShape(13.dp)).background(if (ui.returnToStart) C.accent.yellow else C.dash.control),
                contentAlignment = if (ui.returnToStart) Alignment.CenterEnd else Alignment.CenterStart,
            ) { Box(Modifier.padding(3.dp).size(20.dp).clip(CircleShape).background(if (ui.returnToStart) C.text.onLight else C.text.secondary)) }
        }
        Spacer(Modifier.height(14.dp))
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

/** components §21 `ParamChips` (the `MoodChip` look): h 44, radius 22. */
@Composable
private fun ParamChip(text: String, on: Boolean, tag: String, multi: Boolean = false, onClick: () -> Unit) {
    val shape = RoundedCornerShape(22.dp)
    Box(
        Modifier.height(44.dp).clip(shape).background(if (on) C.accent.yellow else C.dash.control)
            .border(DesignTokens.stroke.w1, if (on) C.accent.yellow else C.dash.outline, shape)
            .then(if (multi) Modifier.toggleable(on, role = Role.Checkbox, onValueChange = { onClick() }) else Modifier.selectable(on, role = Role.RadioButton, onClick = onClick))
            .testTag(tag).padding(horizontal = 14.dp),
        contentAlignment = Alignment.Center,
    ) { Txt(text, T.body.mdStrong, if (on) C.text.onLight else C.text.secondary, maxLines = 1) }
}

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

