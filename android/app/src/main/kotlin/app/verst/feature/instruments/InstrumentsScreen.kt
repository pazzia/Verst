package app.verst.feature.instruments

import androidx.compose.foundation.Canvas
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.offset
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.layout
import androidx.compose.ui.unit.IntOffset
import app.verst.core.ui.components.LocalReducedMotion
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.unit.Dp
import app.verst.core.ui.components.Band
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
    ScreenRoot(C.dash.raised, statusBar = C.sky.band1) {
        Column(Modifier.fillMaxSize()) {
            Box(Modifier.fillMaxWidth().height(232.dp)) {
                SkyStrip(120.dp, bands = InstrumentsSky)
                Box(Modifier.fillMaxSize().padding(top = 104.dp).dashboardSurface(curve = 30.dp, rim = false))
                // M1: the mirror stem (30 × 58 from the top edge), under the body.
                Box(Modifier.align(Alignment.TopCenter).size(30.dp, 58.dp).background(C.dash.controlAlt))
                BigMirror(ui, a, Modifier.padding(start = 20.dp, end = 20.dp, top = 54.dp).fillMaxWidth().height(174.dp))
                BackLink(ui.title, C.mirror.label, stringResource(R.string.cd_back, ui.title), a::back, Modifier.padding(start = 12.dp, top = 4.dp))
            }
            Box(Modifier.weight(1f).fillMaxWidth()) {
                Column(
                    Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
                ) {
                    // N-04 / 5.3 §2.2 rhythm: chip at 232, summary 282, wells 322 (175 × 197 at L14/R14), mood 535.
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Txt(stringResource(R.string.instruments_hint), T.body.mdTight, C.text.secondary, Modifier.weight(1f).padding(end = 8.dp))
                        ToggleChip(
                            stringResource(if (ui.frontAdult) R.string.instruments_front_adult else R.string.instruments_front_none),
                            ui.frontAdult, a::front, role = Role.Switch,
                        )
                    }
                    Txt(summary(ui), T.title.lgNum, C.text.primary, Modifier.padding(top = 6.dp), maxLines = 2)
                    // The wells sit 6 dp wider on each side than the 20 dp text column (L14 / R14).
                    Row(
                        Modifier.padding(top = 14.dp).layout { m, c ->
                            val extra = 12.dp.roundToPx()
                            val p = m.measure(c.copy(minWidth = c.maxWidth + extra, maxWidth = c.maxWidth + extra))
                            layout(c.maxWidth, p.height) { p.place(-extra / 2, 0) }
                        }.height(197.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        KmWell(ui, a, Modifier.weight(1f).fillMaxHeight())
                        BudgetWell(ui, a, Modifier.weight(1f).fillMaxHeight())
                    }
                    Txt(stringResource(R.string.instruments_mood_label), T.label.md, C.text.muted, Modifier.padding(top = 16.dp))
                    // 5.3 §9: three radio cards in the radiogroup «Как едем», always one selected
                    Column(
                        Modifier.padding(top = 8.dp).selectableGroup().testTag("instruments.moods"),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        MoodCard(Mood.CALM, ui.mood == Mood.CALM, null, a)
                        MoodCard(Mood.FUN, ui.mood == Mood.FUN, funCrew(ui.children, ui.dog), a)
                        MoodCard(Mood.JUST_DRIVE, ui.mood == Mood.JUST_DRIVE, null, a)
                    }
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
                    Txt(metaLine, T.body.mdTight, C.text.secondary, Modifier.padding(top = 2.dp).testTag("instruments.meta"), maxLines = 2)
                    if (suffix != null) {
                        Txt(
                            suffix, T.body.mdTight, if (ui.budgetOutcome == "no_fit") C.accent.redText else C.text.secondary,
                            Modifier.testTag("instruments.budget"), maxLines = 1,
                        )
                    }
                }
                val go = stringResource(R.string.common_go)
                StartButton(StartSize.L, go, enabled = true, cd = go, onClick = a::go, modifier = Modifier.testTag("instruments.start"))
            }
        }
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

/** 5.3 §9: the selected fun card's line from the crew in the mirror (child → dog → adults only). */
@Composable
private fun funCrew(children: Int, dog: Boolean): String {
    val parts = buildList {
        if (children > 0) add(stringResource(R.string.instruments_mood_fun_child))
        if (dog) add(stringResource(R.string.instruments_mood_fun_dog))
        if (isEmpty()) add(stringResource(R.string.instruments_mood_fun_adults))
    }
    return stringResource(R.string.instruments_mood_fun_crew, parts.joinToString("; "))
}

/** components §25 `MoodCard`: a radio card (min-h 56, padding 10 12, radius 12, gap 12). */
@Composable
private fun MoodCard(m: Mood, selected: Boolean, crewLine: String?, a: InstrumentsActions) {
    val shape = RoundedCornerShape(12.dp)
    val sub = stringResource(
        when (m) {
            Mood.CALM -> R.string.instruments_mood_calm_sub
            Mood.FUN -> R.string.instruments_mood_fun_sub
            Mood.JUST_DRIVE -> R.string.instruments_mood_drive_sub
        },
    )
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 56.dp).clip(shape)
            // the on fill #1F1F17 has no token yet (dev-notes S4): dash.face + the 2 dp yellow border
            .background(C.dash.face)
            .border(if (selected) DesignTokens.stroke.w2 else DesignTokens.stroke.w1, if (selected) C.accent.yellowText else C.dash.controlAlt, shape)
            .selectable(selected, role = Role.RadioButton, onClick = { a.mood(m) })
            .testTag("instruments.mood.${m.wire}")
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(
            Modifier.size(20.dp).drawBehind {
                val r = size.minDimension / 2
                if (selected) {
                    val w = 6.dp.toPx()
                    drawCircle(C.accent.yellowText, r - w / 2, style = Stroke(w))
                } else {
                    val w = 2.dp.toPx()
                    drawCircle(C.dash.outlineDashed, r - w / 2, style = Stroke(w))
                }
            },
        )
        Column(Modifier.weight(1f)) {
            Txt(moodTitle(m), MoodTitle, C.text.primary, maxLines = 1)
            Txt(sub, T.body.smRelaxed, C.text.secondary, Modifier.padding(top = 2.dp))
            if (selected && crewLine != null) {
                Txt(crewLine, T.body.smStrong, C.accent.yellowText, Modifier.padding(top = 4.dp).testTag("instruments.mood.crew"))
            }
        }
    }
}

private val MoodTitle = T.field.md.copy(fontWeight = androidx.compose.ui.text.font.FontWeight.W700)

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
            // M4/M5: reflected ground with the road trapezoid (top x 188…202, bottom 160…230 on screen).
            Box(
                Modifier.fillMaxWidth().height(22.dp).background(C.scene.groundDay).drawBehind {
                    val cx = size.width / 2
                    val d = 1.dp.toPx()
                    drawPath(
                        Path().apply {
                            moveTo(cx - 7 * d, 0f); lineTo(cx + 7 * d, 0f); lineTo(cx + 35 * d, size.height); lineTo(cx - 35 * d, size.height); close()
                        },
                        C.scene.road,
                    )
                },
            )
            Spacer(Modifier.fillMaxWidth().height(4.dp).background(C.mirror.glass))
            Row(
                Modifier.fillMaxSize().background(C.dash.bench).padding(start = 16.dp, end = 16.dp, top = 6.dp, bottom = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                val names = listOf("Левое", "Среднее", "Правое")
                ui.back.forEachIndexed { i, seat -> SeatButton(seat, names[i], { a.seat(i) }, Modifier.weight(1f).testTag("instruments.seat.$i")) }
            }
        }
        DogToggle(ui.dog, a::dog, Modifier.align(Alignment.TopStart).padding(start = 258.dp, top = 26.dp))
    }
}

/** components §3.4 `DogToggle`: 56 × 52, body 32 × 26 + ears when on; dashed body, «+ пёс» when off. */
@Composable
private fun DogToggle(on: Boolean, onClick: () -> Unit, modifier: Modifier) {
    val cd = stringResource(if (on) R.string.cd_instruments_dog_on else R.string.cd_instruments_dog_off)
    Box(
        modifier
            .size(56.dp, 52.dp)
            .toggleable(on, role = Role.Switch) { onClick() }
            .semantics { contentDescription = cd }
            .testTag("instruments.dog"),
    ) {
        // motion.dogWag: ±6° about the body's bottom centre, 600 ms each way, while the dog is on.
        val reduced = LocalReducedMotion.current
        val wag = if (on && !reduced) {
            rememberInfiniteTransition(label = "wag").animateFloat(
                DesignTokens.motion.dogWag.fromDeg, DesignTokens.motion.dogWag.toDeg,
                infiniteRepeatable(tween(DesignTokens.motion.dogWag.durationMs / 2, easing = DesignTokens.motion.dogWag.easing), RepeatMode.Reverse),
                label = "wagDeg",
            ).value
        } else 0f
        Canvas(Modifier.matchParentSize().graphicsLayer { rotationZ = wag; transformOrigin = TransformOrigin(28f / 56f, 40f / 52f) }) {
            val d = 1.dp.toPx()
            val body = Path().apply {
                addRoundRect(
                    RoundRect(
                        12 * d, 14 * d, 44 * d, 40 * d,
                        topLeftCornerRadius = CornerRadius(14 * d), topRightCornerRadius = CornerRadius(14 * d),
                        bottomRightCornerRadius = CornerRadius(10 * d), bottomLeftCornerRadius = CornerRadius(10 * d),
                    ),
                )
            }
            if (on) {
                // N-05: ears relative to the body: (+6, −6) at −18° and (+17, −6) at +18°.
                for ((x, deg) in listOf(18f to -18f, 29f to 18f)) {
                    rotate(deg, Offset((x + 4.5f) * d, 15 * d)) {
                        drawRoundRect(C.crew.dog, Offset(x * d, 8 * d), Size(9 * d, 14 * d), CornerRadius(5 * d))
                    }
                }
                drawPath(body, C.crew.dog)
            } else {
                drawPath(body, C.text.muted, style = Stroke(2 * d, pathEffect = PathEffect.dashPathEffect(floatArrayOf(4 * d, 3 * d))))
            }
        }
        Txt(
            stringResource(if (on) R.string.instruments_dog_on else R.string.instruments_dog_off), T.caption.bold,
            if (on) C.text.primary else C.text.secondary, Modifier.align(Alignment.BottomCenter), maxLines = 1,
        )
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
    val shape = RoundedCornerShape(topStart = DesignTokens.radius.r14, topEnd = DesignTokens.radius.r14, bottomEnd = DesignTokens.radius.r6, bottomStart = DesignTokens.radius.r6)
    Column(
        modifier
            .fillMaxSize()
            .clip(shape)
            .then(
                // components §3.3: empty = dashed 2 dp (6 / 4) `color.dash.outlineDashed`, transparent.
                if (seat == Seat.EMPTY) Modifier.drawBehind {
                    val w = 2.dp.toPx()
                    drawRoundRect(
                        C.dash.outlineDashed, Offset(w / 2, w / 2), Size(size.width - w, size.height - w), CornerRadius(12.dp.toPx()),
                        style = Stroke(w, pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 4.dp.toPx()))),
                    )
                } else Modifier.background(C.dash.outline),
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
    Box(Modifier.padding(top = 2.dp).size(body, head).clip(RoundedCornerShape(topStart = head, topEnd = head)).background(color))
}

@Composable
private fun Well(label: String, modifier: Modifier, gap: Dp = 8.dp, content: @Composable () -> Unit) {
    Column(
        modifier
            .clip(RoundedCornerShape(DesignTokens.radius.r24))
            .background(C.dash.well)
            .border(DesignTokens.stroke.w4, C.dash.control, RoundedCornerShape(DesignTokens.radius.r24))
            .padding(horizontal = 10.dp, vertical = 12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(gap, Alignment.CenterVertically),
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
    val days = ui.days
    Well(stringResource(R.string.instruments_km_label), modifier) {
        // components §4: frame 113 × 42, four drums «0300», the last one white.
        val digits = ui.dailyKm.toString().padStart(4, '0')
        Row(
            Modifier.clip(RoundedCornerShape(DesignTokens.radius.r6)).background(C.dash.odometerFrame).padding(4.dp).testTag("instruments.odometer"),
            horizontalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            digits.forEachIndexed { i, d ->
                val last = i == digits.lastIndex
                Box(
                    Modifier.size(DesignTokens.size.drumW, DesignTokens.size.drumH).clip(RoundedCornerShape(DesignTokens.radius.r3))
                        .background(if (last) C.sign.white else C.dash.odometerDrum),
                    contentAlignment = Alignment.Center,
                ) {
                    // motion.odometerRoll: only changed drums roll (300 ms decelerate); instant under reduced motion.
                    val reduced = LocalReducedMotion.current
                    AnimatedContent(
                        d,
                        transitionSpec = {
                            if (reduced) EnterTransition.None togetherWith ExitTransition.None else {
                                val up = targetState > initialState
                                val spec = tween<IntOffset>(DesignTokens.motion.odometerRoll.durationMs, easing = DesignTokens.motion.odometerRoll.easing)
                                slideInVertically(spec) { h -> if (up) h else -h } togetherWith slideOutVertically(spec) { h -> if (up) -h else h }
                            }
                        },
                        label = "drum$i",
                    ) { digit -> Txt(digit.toString(), T.odometer, if (last) C.text.onLight else C.sign.white) }
                }
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Txt(
                if (m == 0) stringResource(R.string.instruments_drive_time_h, h) else stringResource(R.string.instruments_drive_time, h, m),
                T.body.smRelaxed, C.text.secondary, align = TextAlign.Center,
            )
            Txt(
                if (days == null) " " else stringResource(
                    if (ui.roundTrip) R.string.instruments_days_ring else R.string.instruments_days_oneway,
                    days, pluralStringResource(R.plurals.plural_day, days),
                ),
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
    Well(stringResource(R.string.instruments_budget_label), modifier, gap = 6.dp) {
        val reduced = LocalReducedMotion.current
        // a custom budget («до 42 000 ₽») puts the needle between the neighbouring presets
        val pos = ui.budgetCustom?.let { c ->
            val vals = BudgetPresets.dropLast(1).filterNotNull()
            val i = vals.indexOfLast { it <= c }
            when {
                i < 0 -> 0f
                i >= vals.lastIndex -> vals.lastIndex.toFloat()
                else -> i + (c - vals[i]).toFloat() / (vals[i + 1] - vals[i])
            }
        } ?: ui.budgetIndex.toFloat()
        val angle by animateFloatAsState(
            -90f + 36f * pos,
            if (reduced) snap() else spring(DesignTokens.motion.needle.dampingRatio, DesignTokens.motion.needle.stiffness),
            label = "needle",
        )
        Box(Modifier.size(DesignTokens.size.gaugeW, DesignTokens.size.gaugeH)) {
            Gauge(angle, Modifier.matchParentSize())
            // N-06: E (red text) and F, baseline-left at (8, 46) / (114, 46) of the gauge box.
            Txt(stringResource(R.string.instruments_gauge_empty), T.caption.bold, C.accent.redText, Modifier.offset(x = 8.dp, y = 34.dp))
            Txt(stringResource(R.string.instruments_gauge_full), T.caption.bold, C.text.primary, Modifier.offset(x = 114.dp, y = 34.dp))
        }
        val shown = ui.budgetCustom ?: preset
        Txt(
            if (shown == null) stringResource(R.string.instruments_budget_any) else stringResource(R.string.instruments_budget_value, app.verst.settings.AppPrefs.money(shown)),
            T.title.lgNum, C.text.primary, Modifier.testTag("instruments.budget.value"), maxLines = 1,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StepperKey("−", ui.budgetIndex > 0, stringResource(R.string.cd_instruments_budget_less), { a.budget(-1) })
            StepperKey("+", ui.budgetIndex < BudgetPresets.lastIndex, stringResource(R.string.cd_instruments_budget_more), { a.budget(1) })
        }
    }
}

/**
 * components §6 FuelGauge (S-14): 130 × 62, arc centre (65, 58) r 53, track and E zone stroke 8 butt, needle
 * 4 × 48 (radius 2) rotated −90° + 36° · preset, hub d 16 at (65, 60).
 */
@Composable
private fun Gauge(angle: Float, modifier: Modifier) {
    Canvas(modifier) {
        val d = size.width / 130f
        val c = Offset(65 * d, 58 * d)
        val r = 53 * d
        val tl = Offset(c.x - r, c.y - r)
        val box = Size(2 * r, 2 * r)
        drawArc(C.dash.controlAlt, 180f, 180f, false, tl, box, style = Stroke(8 * d, cap = StrokeCap.Butt))
        drawArc(C.accent.red, 180f, 48.8f, false, tl, box, style = Stroke(8 * d, cap = StrokeCap.Butt))
        rotate(angle, c) {
            drawRoundRect(C.accent.yellowText, Offset(c.x - 2 * d, c.y - 48 * d), Size(4 * d, 48 * d), CornerRadius(2 * d))
        }
        drawCircle(C.sign.white, 8 * d, Offset(65 * d, 60 * d))
    }
}

/** Sky of the 5.3 strip (S1–S3): band 1 0–60, band 3 60–90, band 4 90–120. */
private val InstrumentsSky: List<Band> get() = listOf(Band(0f, 60f, C.sky.band1), Band(60f, 30f, C.sky.band3), Band(90f, 30f, C.sky.band4))
