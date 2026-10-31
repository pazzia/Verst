package app.verst.feature.drive

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.CraftBadge
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftIconTile
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.StepLine
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.ScreenRoot
import app.verst.nav.DriveAction
import app.verst.nav.DriveUi
import app.verst.core.ui.theme.DesignTokens.color as C

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

/**
 * 5.4 Drive, camper-ui fork (mockup screen 4 «Строим дорогу»): a paper page with one progress card — the van tile,
 * the stage header, a craft progress bar, the engine's step lines and the latest stop — and the full-width action
 * at the bottom once the road is ready; errors in the same card with their action. No app chrome on this screen.
 */
@Composable
fun DriveScreen(
    ui: DriveUi,
    kmLabel: String,
    action: (EngineErrorDto) -> DriveAction,
    onCancel: () -> Unit,
    onDone: () -> Unit,
    onErrorAction: (DriveAction, String) -> Unit,
) {
    ScreenRoot(C.camper.page) {
        Column(Modifier.fillMaxSize()) {
            val back = stringResource(if (ui.error != null) R.string.common_back_instruments else R.string.common_cancel)
            BackLink(
                back, C.camper.inkSoft,
                if (ui.error != null) stringResource(R.string.cd_back, back) else stringResource(R.string.cd_drive_cancel),
                onCancel, Modifier.padding(start = 10.dp, top = 8.dp).testTag("drive.back"),
            )
            Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = CraftDefaults.ScreenGutter, vertical = CraftDefaults.Gap),
                ) {
                    ProgressCard(ui, kmLabel)
                }
            }
            Box(
                Modifier
                    .fillMaxWidth()
                    .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 4.dp, bottom = 20.dp)
                    .height(CraftDefaults.ButtonHeight),
            ) {
                val err = ui.error
                when {
                    err != null -> {
                        val act = action(err)
                        val msg = errorMessage(err)
                        CraftButton(stringResource(actionLabelRes(act)), { onErrorAction(act, msg) }, Modifier.fillMaxWidth().testTag("drive.error.cta"))
                    }
                    ui.done && ui.noFit -> CraftButton(stringResource(R.string.budget_nofit_cta), onDone, Modifier.fillMaxWidth().testTag("drive.nofit"))
                    ui.done -> CraftButton(stringResource(R.string.drive_done), onDone, Modifier.fillMaxWidth().testTag("drive.cta"), icon = R.drawable.ic_ui_route)
                    else -> Unit
                }
            }
        }
    }
}

@Composable
private fun ProgressCard(ui: DriveUi, kmLabel: String) {
    CraftCard(Modifier.fillMaxWidth(), padding = PaddingValues(16.dp), spacing = 12.dp) {
        val err = ui.error
        CraftIconTile(
            if (err != null) R.drawable.ic_ui_road else R.drawable.ic_ui_van, active = false, size = 56.dp,
            fill = if (err != null) C.camper.header else C.camper.amber, tint = C.camper.border,
            modifier = Modifier.align(Alignment.CenterHorizontally),
        )
        if (err != null) {
            Txt(stringResource(R.string.drive_failed), CraftType.overline, C.accent.redText, Modifier.testTag("drive.failed"))
            val abroad = err.abroadText
            Txt(
                abroad ?: stringResource(errorMessageRes(err.code)), CraftType.cardTitle, C.camper.ink,
                Modifier.semantics { liveRegion = LiveRegionMode.Polite }.testTag("drive.error.message"), maxLines = if (abroad != null) 4 else Int.MAX_VALUE,
            )
            // a verdict about the place is not fixed by trying again
            if (abroad == null) Txt(stringResource(R.string.drive_error_sub), CraftType.caption, C.camper.inkSoft)
            return@CraftCard
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Txt(stringResource(R.string.drive_header, kmLabel), CraftType.cardTitle, C.camper.ink, Modifier.weight(1f), maxLines = 1)
            if (ui.days > 0) CraftBadge(stringResource(R.string.drive_header_days, ui.days, pluralStringResource(R.plurals.plural_day_upper, ui.days)))
        }
        // motion.progress: 400 ms easeInOut toward the revealed stage.
        val reduced = LocalReducedMotion.current
        val progress by animateFloatAsState(
            ui.progress, if (reduced) snap() else tween(DesignTokens.motion.progress.durationMs, easing = DesignTokens.motion.progress.easing), label = "progress",
        )
        CraftProgress(progress)
        Column(Modifier.semantics { liveRegion = LiveRegionMode.Polite }, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            val shown = ui.lines.takeLast(4)
            shown.forEachIndexed { i, line ->
                val isLast = i == shown.lastIndex
                key(line) { AppearLine(line, done = !isLast || ui.done) }
            }
        }
        // 5.4: the engine's latest stop (was the flying road sign), decorative like the signs were
        val last = ui.signs.lastOrNull()?.name
        if (!last.isNullOrBlank()) CraftBadge(last, Modifier.clearAndSetSemantics {})
    }
}

/** The craft progress bar (mockup): a sunken tan track with the brown frame, the orange fill. */
@Composable
private fun CraftProgress(fraction: Float) {
    Box(
        Modifier
            .fillMaxWidth()
            .height(16.dp)
            .craftField(fill = C.camper.header)
            .padding(3.dp),
    ) {
        Box(
            Modifier
                .fillMaxHeight()
                .fillMaxWidth(fraction.coerceIn(0f, 1f))
                .clip(RoundedCornerShape(6.dp))
                .background(C.camper.orange),
        )
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
