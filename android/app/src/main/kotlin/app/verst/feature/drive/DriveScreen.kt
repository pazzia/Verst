package app.verst.feature.drive

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.offset
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.clearAndSetSemantics
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.RoadSign
import kotlinx.coroutines.delay
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.PrimaryCta
import app.verst.core.ui.components.ProgressBar
import app.verst.core.ui.components.StepLine
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.DrivePosts
import app.verst.core.ui.components.DriveRoad
import app.verst.core.ui.components.DriveSky
import app.verst.core.ui.components.WindshieldScene
import app.verst.core.ui.components.dashboardSurface
import app.verst.core.ui.components.naviPanel
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.ScreenRoot
import app.verst.nav.DriveAction
import app.verst.nav.DriveUi
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

private val DashHeight = 304.dp

/** User-facing message for an engine error code (5.4 §4.4, M§9). */
fun errorMessageRes(code: String): Int = when (code) {
    "INVALID_INPUT" -> R.string.error_invalid_input
    "UNREACHABLE" -> R.string.error_unreachable
    "TOO_SHORT" -> R.string.error_too_short
    // CEO 29.10: a trip abroad is planned only on the server
    app.verst.engine.ServerPlannerGateway.ABROAD_OFFLINE -> R.string.abroad_server_line
    app.verst.engine.ServerPlannerGateway.ABROAD_NO_SERVER -> R.string.abroad_error_no_server
    app.verst.engine.ServerPlannerGateway.ABROAD_NO_CONSENT -> R.string.abroad_error_no_consent
    else -> R.string.error_upstream // UPSTREAM, INTERNAL, NO_WORLD, TZDATA_MISSING, engine start failures
}

/**
 * The error's text: CEO 29.10 — the engine's own sentence about a point abroad («Граница закрыта для легковых до
 * 2 января 2027: …»), else our copy for the code.
 */
@Composable
fun errorMessage(e: EngineErrorDto): String = e.abroadText ?: stringResource(errorMessageRes(e.code))

fun actionLabelRes(action: DriveAction): Int = when (action) {
    DriveAction.RETRY -> R.string.common_try_again
    DriveAction.TO_INSTRUMENTS -> R.string.drive_to_instruments
    DriveAction.CHANGE_ROUTE -> R.string.drive_change_route
}

/** 5.4 Drive, simplified: the plan's progress on the navigator panel; errors as a screen with an action. */
@Composable
fun DriveScreen(
    ui: DriveUi,
    kmLabel: String,
    action: (EngineErrorDto) -> DriveAction,
    onCancel: () -> Unit,
    onDone: () -> Unit,
    onErrorAction: (DriveAction, String) -> Unit,
) {
    ScreenRoot(C.dash.base, statusBar = C.interior.liner) {
        BoxWithConstraints(Modifier.matchParentSize()) {
            WindshieldScene(maxHeight - DashHeight + 20.dp, hills = false, sunX = 161f, refHeight = 560f, sky = DriveSky, road = DriveRoad, sunCenterY = 304f,
                laneCycleMs = DesignTokens.motion.lane.drive.durationMs, posts = DrivePosts)
            if (ui.error == null) FlyingSigns(ui.signs, maxWidth)
            val back = stringResource(if (ui.error != null) R.string.common_back_instruments else R.string.common_cancel)
            BackLink(
                back, C.mirror.label,
                if (ui.error != null) stringResource(R.string.cd_back, back) else stringResource(R.string.cd_drive_cancel),
                onCancel, Modifier.padding(start = 12.dp, top = 14.dp).testTag("drive.back"),
            )
            Column(
                Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(DashHeight).dashboardSurface()
                    .padding(start = 18.dp, end = 18.dp, top = 22.dp, bottom = 26.dp),
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                Panel(ui, kmLabel)
                val err = ui.error
                when {
                    err != null -> {
                        val act = action(err)
                        val msg = errorMessage(err)
                        PrimaryCta(stringResource(actionLabelRes(act)), { onErrorAction(act, msg) }, Modifier.testTag("drive.error.cta"))
                    }
                    ui.done && ui.noFit -> PrimaryCta(stringResource(R.string.budget_nofit_cta), onDone, Modifier.testTag("drive.nofit"))
                    ui.done -> PrimaryCta(stringResource(R.string.drive_done), onDone, Modifier.testTag("drive.cta"))
                    else -> Box(Modifier.height(DesignTokens.size.ctaH))
                }
            }
        }
    }
}

@Composable
private fun Panel(ui: DriveUi, kmLabel: String) {
    Column(
        Modifier.fillMaxWidth().height(186.dp).naviPanel().padding(horizontal = 20.dp, vertical = 18.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        val err = ui.error
        if (err != null) {
            Txt(stringResource(R.string.drive_failed), T.label.md, C.navi.label, Modifier.testTag("drive.failed"))
            val abroad = err.abroadText
            Txt(
                abroad ?: stringResource(errorMessageRes(err.code)), T.body.step, C.text.primary,
                Modifier.semantics { liveRegion = LiveRegionMode.Polite }.testTag("drive.error.message"), maxLines = if (abroad != null) 4 else Int.MAX_VALUE,
            )
            // a verdict about the place is not fixed by trying again
            if (abroad == null) Txt(stringResource(R.string.drive_error_sub), T.body.md, C.navi.text)
            return@Column
        }
        Row(Modifier.fillMaxWidth()) {
            Txt(stringResource(R.string.drive_header, kmLabel), T.label.md, C.navi.label, Modifier.weight(1f), maxLines = 1)
            if (ui.days > 0) Txt(stringResource(R.string.drive_header_days, ui.days, pluralStringResource(R.plurals.plural_day_upper, ui.days)), T.label.md, C.navi.label)
        }
        // motion.progress: 400 ms easeInOut toward the revealed stage.
        val reduced = LocalReducedMotion.current
        val progress by animateFloatAsState(
            ui.progress, if (reduced) snap() else tween(DesignTokens.motion.progress.durationMs, easing = DesignTokens.motion.progress.easing), label = "progress",
        )
        ProgressBar(progress, Modifier.fillMaxWidth().height(4.dp))
        Column(Modifier.semantics { liveRegion = LiveRegionMode.Polite }, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            val shown = ui.lines.takeLast(4)
            shown.forEachIndexed { i, line ->
                val isLast = i == shown.lastIndex
                key(line) { AppearLine(line, done = !isLast || ui.done) }
            }
        }
    }
}


/** motion.stepAppear: fade in + 6 dp from the left, 350 ms easeOut (instant under reduced motion). */
@Composable
private fun AppearLine(text: String, done: Boolean) {
    val reduced = LocalReducedMotion.current
    val p = remember { Animatable(if (reduced) 1f else 0f) }
    LaunchedEffect(Unit) { if (!reduced) p.animateTo(1f, tween(DesignTokens.motion.stepAppear.durationMs, easing = DesignTokens.motion.stepAppear.easing)) }
    StepLine(text, done, Modifier.graphicsLayer { alpha = p.value; translationX = DesignTokens.motion.stepAppear.fromDxDp.toPx() * (1 - p.value) })
}

/**
 * motion.flyingSign (5.4 S10): each engine `stop` becomes a sign that flies from (195, 250) toward the viewer,
 * left or right, scale 0.12 → 1.7, alpha in over the first 15 %, 3600 ms rushIn, ≥ 1200 ms apart, ≤ 3 in flight.
 * Reduced motion: the latest sign, static at the spawn point, scale 1.
 */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.FlyingSigns(signs: List<app.verst.core.model.dto.StopEventDto>, width: androidx.compose.ui.unit.Dp) {
    val m = DesignTokens.motion.flyingSign
    val reduced = LocalReducedMotion.current
    val k = width.value / 390f
    if (reduced) {
        val last = signs.lastOrNull() ?: return
        Box(Modifier.offset(x = (195 * k).dp - 34.dp, y = 250.dp - 31.dp).clearAndSetSemantics {}) { RoadSign(last.sign ?: "city", last.name ?: "", emptyList()) }
        return
    }
    signs.forEachIndexed { i, st ->
        key(st.id ?: "$i") {
            val p = remember { Animatable(0f) }
            var visible by remember { mutableStateOf(true) }
            LaunchedEffect(Unit) {
                delay((i * m.staggerMs).toLong())
                p.animateTo(1f, tween(m.durationMs, easing = m.easing))
                visible = false
            }
            if (visible && p.value > 0f) {
                val dir = if (i % 2 == 0) 1f else -1f
                Box(
                    Modifier.offset(x = (195 * k).dp - 34.dp, y = 250.dp - 31.dp)
                        .graphicsLayer {
                            val e = p.value
                            val s = m.fromScale + (m.toScale - m.fromScale) * e
                            scaleX = s
                            scaleY = s
                            translationX = dir * m.dxDp.toPx() * e
                            translationY = m.dyDp.toPx() * e
                            alpha = minOf(1f, e / m.fadeInFraction)
                        }
                        .clearAndSetSemantics {},
                ) { RoadSign(st.sign ?: "city", st.name ?: "", emptyList()) }
            }
        }
    }
}
