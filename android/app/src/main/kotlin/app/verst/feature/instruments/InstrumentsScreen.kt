package app.verst.feature.instruments

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import app.verst.core.model.BudgetPresets
import app.verst.core.model.Mood
import app.verst.core.model.RuFormat
import app.verst.core.model.TripMath
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftChip
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftIconTile
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.DashedDivider
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.StepperKey
import app.verst.core.ui.components.ToggleChip
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.ScreenRoot
import app.verst.nav.Seat
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

data class InstrumentsUi(
    val title: String,
    val origin: String,
    val roundTrip: Boolean,
    /** The engine's km of this trip (`estimate` = the plan); null while it is computed. */
    val tripKm: Int?,
    val frontAdult: Boolean,
    val back: List<Seat>,
    val dog: Boolean,
    val adults: Int,
    val children: Int,
    val dailyKm: Int,
    val budgetIndex: Int,
    val mood: Mood?,
    /** The engine's days of this trip; null while it is computed. */
    val days: Int? = null,
    /** OI-39: the origin in the genitive from the engine. */
    val originGen: String = origin,
    /** 5.8: a no-fit «Поднять бюджет до …» value shown exactly («до 42 000 ₽»). */
    val budgetCustom: Int? = null,
    /** 5.8 §3: `estimate.outcome` + `totalRub` + `budgetStatus` (caption meta suffix). */
    val budgetOutcome: String? = null,
    val budgetTotal: Int? = null,
    val budgetStatus: String? = null,
    /** CEO 29.10 (trips abroad): КУДА is abroad — the server plans it; the caption says so in one line. */
    val abroad: Boolean = false,
    /** ПОЕХАЛИ can plan (false: a trip abroad offline or without a server). */
    val goEnabled: Boolean = true,
)

interface InstrumentsActions {
    fun back()
    fun seat(i: Int)
    fun front()
    fun dog()
    fun km(delta: Int)
    fun budget(delta: Int)
    fun mood(m: Mood)
    fun go()
}

/**
 * 5.3 Instruments, camper-ui fork (mockup screen 3 «Приборы»): a paper page — the crew card (seats, the front seat,
 * the dog), the «приборная панель» card (km per day, budget), «Как едем» chips — and, pinned below, the trip
 * summary with the engine's verdict and the full-width ПОЕХАЛИ.
 */
@Composable
fun InstrumentsScreen(ui: InstrumentsUi, a: InstrumentsActions) {
    ScreenRoot(C.camper.page) {
        Column(Modifier.fillMaxSize()) {
            Column(
                Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, bottom = CraftDefaults.Gap),
                verticalArrangement = Arrangement.spacedBy(CraftDefaults.Gap),
            ) {
                BackLink(ui.title, C.camper.inkSoft, stringResource(R.string.cd_back, ui.title), a::back, Modifier.padding(top = 4.dp))
                CrewCard(ui, a)
                DialsCard(ui, a)
                MoodCard(ui, a)
            }
            Caption(ui, a)
        }
    }
}

/** The crew: the summary, «Рядом с вами», the three back seats and the dog (tap cycles a seat, toggles the dog). */
@Composable
private fun CrewCard(ui: InstrumentsUi, a: InstrumentsActions) {
    CraftCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            CraftIconTile(R.drawable.ic_ui_van, active = false, fill = C.camper.amber, tint = C.camper.border)
            Txt(summary(ui), CraftType.cardTitle, C.camper.ink, Modifier.weight(1f), maxLines = 2)
        }
        ToggleChip(
            stringResource(if (ui.frontAdult) R.string.instruments_front_adult else R.string.instruments_front_none),
            ui.frontAdult, a::front, role = Role.Switch,
        )
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            val names = listOf("Левое", "Среднее", "Правое")
            ui.back.forEachIndexed { i, seat -> SeatTile(seat, names.getOrElse(i) { "" }, { a.seat(i) }, Modifier.weight(1f).testTag("instruments.seat.$i")) }
            DogTile(ui.dog, a::dog, Modifier.weight(1f))
        }
    }
}

private val TileShape = RoundedCornerShape(CraftDefaults.FieldRadius)

/** An empty place: white paper with a dashed brown frame (components §3.3). */
private fun Modifier.dashedTile(): Modifier = clip(TileShape).background(C.camper.field).drawBehind {
    val w = CraftDefaults.BorderThin.toPx()
    drawRoundRect(
        C.camper.inkMuted, Offset(w / 2, w / 2), Size(size.width - w, size.height - w), CornerRadius(CraftDefaults.FieldRadius.toPx() - w / 2),
        style = Stroke(w, pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 4.dp.toPx()))),
    )
}

/** A back seat: adult amber, child orange, empty dashed; the label under the pictogram. */
@Composable
private fun SeatTile(seat: Seat, side: String, onClick: () -> Unit, modifier: Modifier) {
    val label = stringResource(
        when (seat) {
            Seat.EMPTY -> R.string.instruments_seat_empty
            Seat.ADULT -> R.string.instruments_seat_adult
            Seat.CHILD -> R.string.instruments_seat_child
        },
    )
    val cd = stringResource(R.string.cd_instruments_seat, side, label)
    val (fill, fg) = when (seat) {
        Seat.ADULT -> C.camper.amber to C.camper.onAmber
        Seat.CHILD -> C.camper.orange to C.camper.onOrange
        Seat.EMPTY -> C.camper.field to C.camper.inkMuted
    }
    Column(
        modifier
            .height(68.dp)
            .then(if (seat == Seat.EMPTY) Modifier.dashedTile() else Modifier.craftField(fill = fill))
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp, Alignment.CenterVertically),
    ) {
        when (seat) {
            Seat.ADULT -> Icon(R.drawable.ic_crew_adult, fg, 24.dp)
            Seat.CHILD -> Icon(R.drawable.ic_crew_child, fg, 20.dp)
            Seat.EMPTY -> Spacer(Modifier.height(20.dp))
        }
        Txt(label, T.caption.strong, fg, maxLines = 1)
    }
}

/** components §3.4 `DogToggle` as a tile: green with the dog when on; dashed «+ пёс» when off. */
@Composable
private fun DogTile(on: Boolean, onClick: () -> Unit, modifier: Modifier) {
    val cd = stringResource(if (on) R.string.cd_instruments_dog_on else R.string.cd_instruments_dog_off)
    val fg = if (on) C.camper.onOrange else C.camper.inkMuted
    Column(
        modifier
            .height(68.dp)
            .then(if (on) Modifier.craftField(fill = C.camper.green) else Modifier.dashedTile())
            .toggleable(on, role = Role.Switch) { onClick() }
            .semantics { contentDescription = cd }
            .testTag("instruments.dog"),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp, Alignment.CenterVertically),
    ) {
        Icon(R.drawable.ic_ui_dog, fg, 22.dp)
        Txt(stringResource(if (on) R.string.instruments_dog_on else R.string.instruments_dog_off), T.caption.strong, fg, maxLines = 1)
    }
}

/** The mockup's «Приборная панель»: km per day (stepper + drive time + days) and the budget (stepper). */
@Composable
private fun DialsCard(ui: InstrumentsUi, a: InstrumentsActions) {
    val minutes = TripMath.driveMinutes(ui.dailyKm)
    val h = minutes / 60
    val m = minutes % 60
    val days = ui.days
    CraftCard(Modifier.fillMaxWidth()) {
        StepperRow(
            label = stringResource(R.string.instruments_km_label),
            value = RuFormat.thousands(ui.dailyKm),
            valueCd = stringResource(R.string.cd_instruments_km, RuFormat.thousands(ui.dailyKm)),
            valueTag = "instruments.odometer",
            canLess = ui.dailyKm > TripMath.KM_MIN, canMore = ui.dailyKm < TripMath.KM_MAX,
            lessCd = stringResource(R.string.cd_instruments_km_less), moreCd = stringResource(R.string.cd_instruments_km_more),
            onLess = { a.km(-TripMath.KM_STEP) }, onMore = { a.km(TripMath.KM_STEP) },
            lessModifier = Modifier.testTag("instruments.km.less"), moreModifier = Modifier.testTag("instruments.km.more"),
        )
        val time = if (m == 0) stringResource(R.string.instruments_drive_time_h, h) else stringResource(R.string.instruments_drive_time, h, m)
        val daysText = if (days == null) null else stringResource(
            if (ui.roundTrip) R.string.instruments_days_ring else R.string.instruments_days_oneway,
            days, pluralStringResource(R.plurals.plural_day, days),
        )
        Txt(listOfNotNull(time, daysText).joinToString(stringResource(R.string.common_join_dot)), CraftType.caption, C.camper.inkSoft)
        DashedDivider()
        val shown = ui.budgetCustom ?: BudgetPresets[ui.budgetIndex]
        val budgetText = if (shown == null) stringResource(R.string.instruments_budget_any) else stringResource(R.string.instruments_budget_value, app.verst.settings.AppPrefs.money(shown))
        StepperRow(
            label = stringResource(R.string.instruments_budget_label),
            value = budgetText,
            valueCd = if (shown == null) stringResource(R.string.cd_instruments_budget_any) else stringResource(R.string.cd_instruments_budget_value, app.verst.settings.AppPrefs.money(shown)),
            valueTag = null,
            valueTextTag = "instruments.budget.value",
            canLess = ui.budgetIndex > 0, canMore = ui.budgetIndex < BudgetPresets.lastIndex,
            lessCd = stringResource(R.string.cd_instruments_budget_less), moreCd = stringResource(R.string.cd_instruments_budget_more),
            onLess = { a.budget(-1) }, onMore = { a.budget(1) },
        )
    }
}

/** Label above; «−», the value in a white field (mono), «+». */
@Composable
private fun StepperRow(
    label: String,
    value: String,
    valueCd: String,
    valueTag: String?,
    canLess: Boolean,
    canMore: Boolean,
    lessCd: String,
    moreCd: String,
    onLess: () -> Unit,
    onMore: () -> Unit,
    valueTextTag: String? = null,
    lessModifier: Modifier = Modifier,
    moreModifier: Modifier = Modifier,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Txt(label, CraftType.fieldLabel, C.camper.inkSoft, maxLines = 1)
        Row(Modifier.fillMaxWidth().padding(end = 2.dp, bottom = 2.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StepperKey("−", canLess, lessCd, onLess, lessModifier)
            Box(
                Modifier
                    .weight(1f)
                    .defaultMinSize(minHeight = DesignTokens.size.touchMin)
                    .craftField()
                    .semantics(mergeDescendants = true) { contentDescription = valueCd }
                    .then(if (valueTag != null) Modifier.testTag(valueTag) else Modifier)
                    .padding(horizontal = 10.dp),
                contentAlignment = Alignment.Center,
            ) {
                Txt(value, CraftType.fieldMono, C.camper.ink, if (valueTextTag != null) Modifier.testTag(valueTextTag) else Modifier, maxLines = 1)
            }
            StepperKey("+", canMore, moreCd, onMore, moreModifier)
        }
    }
}

/** «Как едем»: the three presets as chips (radiogroup, always one selected), the preset's line, the crew line. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MoodCard(ui: InstrumentsUi, a: InstrumentsActions) {
    CraftCard(Modifier.fillMaxWidth()) {
        Txt(stringResource(R.string.instruments_mood_label), CraftType.sectionTitle, C.camper.ink, maxLines = 1)
        // 5.3 §9: three radio chips in the radiogroup «Как едем»
        FlowRow(
            Modifier.fillMaxWidth().selectableGroup().testTag("instruments.moods"),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            for (m in listOf(Mood.CALM, Mood.FUN, Mood.JUST_DRIVE)) {
                val on = ui.mood == m
                CraftChip(
                    moodTitle(m), on, { a.mood(m) },
                    Modifier.semantics { selected = on }.testTag("instruments.mood.${m.wire}"),
                )
            }
        }
        val mood = ui.mood
        if (mood != null) {
            val sub = stringResource(
                when (mood) {
                    Mood.CALM -> R.string.instruments_mood_calm_sub
                    Mood.FUN -> R.string.instruments_mood_fun_sub
                    Mood.JUST_DRIVE -> R.string.instruments_mood_drive_sub
                },
            )
            Txt(sub, CraftType.caption, C.camper.inkSoft)
            if (mood == Mood.FUN) {
                Txt(funCrew(ui.children, ui.dog), T.body.smStrong, C.camper.orangeText, Modifier.testTag("instruments.mood.crew"))
            }
        }
    }
}

/** Pinned: ВСЁ ГОТОВО К ВЫЕЗДУ · the trip · the engine's km (+ the budget verdict, the mood) and ПОЕХАЛИ. */
@Composable
private fun Caption(ui: InstrumentsUi, a: InstrumentsActions) {
    Column(
        Modifier.fillMaxWidth().padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 4.dp, bottom = CraftDefaults.ScreenGutter),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        CraftCard(
            Modifier.fillMaxWidth().semantics(mergeDescendants = true) {},
            padding = PaddingValues(horizontal = 12.dp, vertical = 10.dp),
            spacing = 2.dp,
        ) {
            Txt(stringResource(R.string.instruments_ready_label), CraftType.overline, C.camper.orangeText, maxLines = 1)
            Txt(ui.title, CraftType.cardTitle, C.camper.ink, maxLines = 1)
            val km = ui.tripKm
            val meta = when {
                km == null -> " " // the engine's number arrives within a moment; never a guessed one
                ui.roundTrip -> stringResource(R.string.instruments_ready_meta_ring, ui.originGen, RuFormat.thousands(km))
                else -> stringResource(R.string.common_km, RuFormat.thousands(km))
            }
            // 5.8 §3: the engine's budget verdict after the km («· ≈ 33 800 ₽ — в бюджете»)
            val total = ui.budgetTotal
            val suffix = when {
                km == null || ui.budgetOutcome == null -> null
                ui.budgetOutcome == "no_fit" -> stringResource(R.string.budget_instruments_nofit)
                total == null -> null
                // an engine without the fitter (API v2 M1) answers `plan` even over budget: say nothing then
                ui.budgetStatus == null && total > (ui.budgetCustom ?: BudgetPresets[ui.budgetIndex] ?: Int.MAX_VALUE) -> null
                ui.budgetStatus == null -> stringResource(R.string.budget_instruments_fits, app.verst.settings.AppPrefs.money(total))
                else -> stringResource(R.string.budget_instruments_fitted, app.verst.settings.AppPrefs.money(total))
            }
            // 5.3 §9: the meta ends with the preset name in lower case («… · весело и познавательно»)
            val moodWord = ui.mood?.let { moodTitle(it).lowercase() }
            val metaLine = if (km != null && moodWord != null) meta + stringResource(R.string.common_join_dot) + moodWord else meta
            if (ui.abroad && km == null) {
                // CEO 29.10: no estimate abroad (the server plans it at ПОЕХАЛИ) — the line says who plans and what it needs
                Txt(stringResource(R.string.abroad_server_line), CraftType.caption, C.camper.inkSoft, Modifier.testTag("instruments.abroad"), maxLines = 2)
            } else {
                Txt(metaLine, CraftType.caption, C.camper.inkSoft, Modifier.testTag("instruments.meta"), maxLines = 2)
            }
            if (suffix != null) {
                Txt(
                    suffix, CraftType.caption, if (ui.budgetOutcome == "no_fit") C.accent.redText else C.camper.inkSoft,
                    Modifier.testTag("instruments.budget"), maxLines = 1,
                )
            }
        }
        val go = stringResource(R.string.common_go)
        CraftButton(
            go, a::go,
            Modifier.fillMaxWidth().semantics { contentDescription = go }.testTag("instruments.start"),
            icon = R.drawable.ic_ui_compass,
            enabled = ui.goEnabled,
        )
    }
}

@Composable
private fun moodTitle(m: Mood): String = stringResource(
    when (m) {
        Mood.CALM -> R.string.instruments_mood_calm
        Mood.FUN -> R.string.instruments_mood_more
        Mood.JUST_DRIVE -> R.string.instruments_mood_drive
    },
)

/** 5.3 §9: the fun preset's line from the crew (child → dog → adults only). */
@Composable
private fun funCrew(children: Int, dog: Boolean): String {
    val parts = buildList {
        if (children > 0) add(stringResource(R.string.instruments_mood_fun_child))
        if (dog) add(stringResource(R.string.instruments_mood_fun_dog))
        if (isEmpty()) add(stringResource(R.string.instruments_mood_fun_adults))
    }
    return stringResource(R.string.instruments_mood_fun_crew, parts.joinToString("; "))
}

@Composable
private fun summary(ui: InstrumentsUi): String {
    val parts = mutableListOf(
        stringResource(R.string.instruments_summary_adults, ui.adults, pluralStringResource(R.plurals.plural_adult, ui.adults)),
    )
    if (ui.children > 0) {
        parts += stringResource(R.string.instruments_summary_children, ui.children, pluralStringResource(R.plurals.plural_child, ui.children))
    }
    if (ui.dog) parts += stringResource(R.string.instruments_summary_dog)
    return parts.joinToString(stringResource(R.string.common_join_dot))
}
