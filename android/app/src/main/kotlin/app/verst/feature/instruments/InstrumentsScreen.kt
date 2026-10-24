package app.verst.feature.instruments

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.verst.core.model.BudgetPresets
import app.verst.core.model.Mood
import app.verst.core.model.RuFormat
import app.verst.core.model.TripMath
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.SkyStrip
import app.verst.core.ui.components.StartButton
import app.verst.core.ui.components.StartSize
import app.verst.core.ui.components.StepperKey
import app.verst.core.ui.components.ToggleChip
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.dashboardSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.genitive
import app.verst.nav.Seat
import kotlin.math.cos
import kotlin.math.sin
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

data class InstrumentsUi(
    val title: String,
    val origin: String,
    val roundTrip: Boolean,
    val tripKm: Int,
    val frontAdult: Boolean,
    val back: List<Seat>,
    val dog: Boolean,
    val adults: Int,
    val children: Int,
    val dailyKm: Int,
    val budgetIndex: Int,
    val mood: Mood?,
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

/** 5.3 Instruments, simplified: crew in the mirror, km per day, budget presets, mood; ПОЕХАЛИ. */
@Composable
fun InstrumentsScreen(ui: InstrumentsUi, a: InstrumentsActions) {
    ScreenRoot(C.dash.raised) {
        Column(Modifier.fillMaxSize()) {
            Box(Modifier.fillMaxWidth().height(232.dp)) {
                SkyStrip(120.dp)
                Box(Modifier.fillMaxSize().padding(top = 104.dp).dashboardSurface(curve = 30.dp))
                BigMirror(ui, a, Modifier.padding(start = 20.dp, end = 20.dp, top = 54.dp).fillMaxWidth().height(174.dp))
                BackLink(ui.title, C.mirror.label, stringResource(R.string.cd_back, ui.title), a::back, Modifier.padding(start = 12.dp, top = 4.dp))
            }
            Box(Modifier.weight(1f).fillMaxWidth()) {
                Column(
                    Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Row(Modifier.fillMaxWidth().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        Txt(stringResource(R.string.instruments_hint), T.body.mdTight, C.text.secondary, Modifier.weight(1f).padding(end = 8.dp))
                        ToggleChip(
                            stringResource(if (ui.frontAdult) R.string.instruments_front_adult else R.string.instruments_front_none),
                            ui.frontAdult, a::front, role = Role.Switch,
                        )
                    }
                    Txt(summary(ui), T.title.lgNum, C.text.primary, maxLines = 2)
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        KmWell(ui, a, Modifier.weight(1f))
                        BudgetWell(ui, a, Modifier.weight(1f))
                    }
                    Txt(stringResource(R.string.instruments_mood_label), T.label.md, C.text.muted)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ToggleChip(stringResource(R.string.instruments_mood_calm), ui.mood == Mood.CALM, { a.mood(Mood.CALM) })
                        ToggleChip(stringResource(R.string.instruments_mood_more), ui.mood == Mood.MORE_STOPS, { a.mood(Mood.MORE_STOPS) })
                    }
                    ToggleChip(stringResource(R.string.instruments_mood_drive), ui.mood == Mood.JUST_DRIVE, { a.mood(Mood.JUST_DRIVE) })
                    Spacer(Modifier.height(16.dp))
                }
                // 5.3 §1: content scrolls under a 16 dp fade above the caption row.
                Box(
                    Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(16.dp)
                        .background(Brush.verticalGradient(listOf(C.dash.raised.copy(alpha = 0f), C.dash.raised))),
                )
            }
            Row(
                Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, bottom = 24.dp, top = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f).padding(end = 14.dp).semantics(mergeDescendants = true) {}) {
                    Txt(stringResource(R.string.instruments_ready_label), T.label.md, C.text.muted)
                    Txt(ui.title, T.title.lg, C.text.primary, maxLines = 1)
                    val meta = if (ui.roundTrip) {
                        stringResource(R.string.instruments_ready_meta_ring, genitive(ui.origin), RuFormat.thousands(ui.tripKm))
                    } else {
                        stringResource(R.string.common_km_approx, RuFormat.thousands(ui.tripKm))
                    }
                    Txt(meta, T.body.mdTight, C.text.secondary, Modifier.padding(top = 2.dp), maxLines = 1)
                }
                val go = stringResource(R.string.common_go)
                StartButton(StartSize.L, go, enabled = true, cd = go, onClick = a::go, modifier = Modifier.testTag("instruments.start"))
            }
        }
    }
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

@Composable
private fun BigMirror(ui: InstrumentsUi, a: InstrumentsActions, modifier: Modifier) {
    Box(
        modifier
            .clip(RoundedCornerShape(40.dp))
            .background(C.dash.controlAlt)
            .padding(5.dp)
            .clip(RoundedCornerShape(35.dp))
            .background(C.sky.band2),
    ) {
        Column(Modifier.fillMaxSize()) {
            Spacer(Modifier.height(54.dp))
            Box(Modifier.fillMaxWidth().height(22.dp).background(C.scene.groundDay))
            Row(
                Modifier.fillMaxSize().background(C.dash.bench).padding(horizontal = 16.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                val names = listOf("Левое", "Среднее", "Правое")
                ui.back.forEachIndexed { i, seat -> SeatButton(seat, names[i], { a.seat(i) }, Modifier.weight(1f).testTag("instruments.seat.$i")) }
            }
        }
        val dogCd = stringResource(if (ui.dog) R.string.cd_instruments_dog_on else R.string.cd_instruments_dog_off)
        Box(
            Modifier
                .align(Alignment.TopEnd)
                .padding(top = 12.dp, end = 12.dp)
                .height(44.dp)
                .clip(RoundedCornerShape(22.dp))
                .background(if (ui.dog) C.crew.dog else C.mirror.glass.copy(alpha = 0.6f))
                .clickable(role = Role.Switch, onClick = a::dog)
                .semantics { contentDescription = dogCd }
                .padding(horizontal = 14.dp),
            contentAlignment = Alignment.Center,
        ) {
            Txt(stringResource(if (ui.dog) R.string.instruments_dog_on else R.string.instruments_dog_off), T.body.mdStrong, if (ui.dog) C.text.onLight else C.mirror.label)
        }
    }
}

@Composable
private fun SeatButton(seat: Seat, side: String, onClick: () -> Unit, modifier: Modifier) {
    val label = stringResource(
        when (seat) {
            Seat.EMPTY -> R.string.instruments_seat_empty
            Seat.ADULT -> R.string.instruments_seat_adult
            Seat.CHILD -> R.string.instruments_seat_child
        },
    )
    val cd = stringResource(R.string.cd_instruments_seat, side, label)
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    Column(
        modifier
            .fillMaxSize()
            .clip(shape)
            .then(
                if (seat == Seat.EMPTY) Modifier.border(DesignTokens.stroke.w1, C.dash.outlineDashed, shape)
                else Modifier.background(C.dash.outline),
            )
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Bottom,
    ) {
        when (seat) {
            Seat.ADULT -> Silhouette(22.dp, 44.dp, C.crew.adult)
            Seat.CHILD -> Silhouette(16.dp, 32.dp, C.crew.child)
            Seat.EMPTY -> Unit
        }
        Txt(label, T.caption.strong, if (seat == Seat.EMPTY) C.text.seatEmpty else C.text.primary, Modifier.padding(vertical = 3.dp), maxLines = 1)
    }
}

@Composable
private fun Silhouette(head: androidx.compose.ui.unit.Dp, body: androidx.compose.ui.unit.Dp, color: androidx.compose.ui.graphics.Color) {
    Box(Modifier.size(head).clip(CircleShape).background(color))
    Box(Modifier.padding(top = 2.dp).size(body, head).clip(RoundedCornerShape(topStart = 12.dp, topEnd = 12.dp)).background(color))
}

@Composable
private fun Well(label: String, modifier: Modifier, content: @Composable () -> Unit) {
    Column(
        modifier
            .clip(RoundedCornerShape(DesignTokens.radius.r24))
            .background(C.dash.well)
            .border(DesignTokens.stroke.w4, C.dash.control, RoundedCornerShape(DesignTokens.radius.r24))
            .padding(horizontal = 10.dp, vertical = 12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Txt(label, T.label.wide, C.text.muted)
        content()
    }
}

@Composable
private fun KmWell(ui: InstrumentsUi, a: InstrumentsActions, modifier: Modifier) {
    val minutes = TripMath.driveMinutes(ui.dailyKm)
    val h = minutes / 60
    val m = minutes % 60
    val days = TripMath.days(ui.tripKm, ui.dailyKm)
    val dayWord = pluralStringResource(R.plurals.plural_day, days)
    Well(stringResource(R.string.instruments_km_label), modifier) {
        Row(horizontalArrangement = Arrangement.spacedBy(3.dp)) {
            ui.dailyKm.toString().padStart(3, '0').forEach { d ->
                Box(
                    Modifier.size(DesignTokens.size.drumW, DesignTokens.size.drumH).clip(RoundedCornerShape(DesignTokens.radius.r4)).background(C.dash.face),
                    contentAlignment = Alignment.Center,
                ) { Txt(d.toString(), T.odometer, C.text.primary) }
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Txt(
                if (m == 0) stringResource(R.string.instruments_drive_time_h, h) else stringResource(R.string.instruments_drive_time, h, m),
                T.body.smRelaxed, C.text.secondary, align = TextAlign.Center,
            )
            Txt(
                stringResource(if (ui.roundTrip) R.string.instruments_days_ring else R.string.instruments_days_oneway, days, dayWord),
                T.body.smRelaxed, C.text.secondary, align = TextAlign.Center,
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StepperKey("−", ui.dailyKm > TripMath.KM_MIN, stringResource(R.string.cd_instruments_km_less), { a.km(-TripMath.KM_STEP) }, Modifier.testTag("instruments.km.less"))
            StepperKey("+", ui.dailyKm < TripMath.KM_MAX, stringResource(R.string.cd_instruments_km_more), { a.km(TripMath.KM_STEP) }, Modifier.testTag("instruments.km.more"))
        }
    }
}

@Composable
private fun BudgetWell(ui: InstrumentsUi, a: InstrumentsActions, modifier: Modifier) {
    val preset = BudgetPresets[ui.budgetIndex]
    Well(stringResource(R.string.instruments_budget_label), modifier) {
        Gauge(ui.budgetIndex.toFloat() / BudgetPresets.lastIndex, Modifier.size(DesignTokens.size.gaugeW * 0.85f, DesignTokens.size.gaugeH * 0.85f))
        Txt(
            if (preset == null) stringResource(R.string.instruments_budget_any) else stringResource(R.string.instruments_budget_value, RuFormat.thousands(preset)),
            T.title.lgNum, C.text.primary, maxLines = 1,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StepperKey("−", ui.budgetIndex > 0, stringResource(R.string.cd_instruments_budget_less), { a.budget(-1) })
            StepperKey("+", ui.budgetIndex < BudgetPresets.lastIndex, stringResource(R.string.cd_instruments_budget_more), { a.budget(1) })
        }
    }
}

/** components §6 FuelGauge, simplified: E…F arc and a needle at the preset fraction. */
@Composable
private fun Gauge(fraction: Float, modifier: Modifier) {
    Canvas(modifier) {
        val sw = 5.dp.toPx()
        val r = minOf(size.width / 2, size.height) - sw
        val c = Offset(size.width / 2, size.height - sw / 2)
        val box = Size(2 * r, 2 * r)
        val tl = Offset(c.x - r, c.y - r)
        drawArc(C.dash.controlAlt, 180f, 180f, false, tl, box, style = Stroke(sw, cap = StrokeCap.Round))
        drawArc(C.accent.red, 180f, 30f, false, tl, box, style = Stroke(sw, cap = StrokeCap.Round))
        val a = Math.toRadians((180.0 + 180.0 * fraction))
        val tip = Offset(c.x + (r - sw * 2) * cos(a).toFloat(), c.y + (r - sw * 2) * sin(a).toFloat())
        drawLine(C.accent.yellow, c, tip, 3.dp.toPx(), StrokeCap.Round)
        drawCircle(C.text.primary, 4.dp.toPx(), c)
    }
}
