package app.verst.feature.drive

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
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
    else -> R.string.error_upstream // UPSTREAM, INTERNAL, NO_WORLD, TZDATA_MISSING, engine start failures
}

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
            WindshieldScene(maxHeight - DashHeight + 20.dp, hills = false, sunX = 161f, refHeight = 560f)
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
                        val msg = stringResource(errorMessageRes(err.code))
                        PrimaryCta(stringResource(actionLabelRes(act)), { onErrorAction(act, msg) }, Modifier.testTag("drive.error.cta"))
                    }
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
            Txt(stringResource(errorMessageRes(err.code)), T.body.step, C.text.primary, Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            Txt(stringResource(R.string.drive_error_sub), T.body.md, C.navi.text)
            return@Column
        }
        Row(Modifier.fillMaxWidth()) {
            Txt(stringResource(R.string.drive_header, kmLabel), T.label.md, C.navi.label, Modifier.weight(1f), maxLines = 1)
            if (ui.days > 0) Txt(stringResource(R.string.drive_header_days, ui.days, pluralStringResource(R.plurals.plural_day_upper, ui.days)), T.label.md, C.navi.label)
        }
        ProgressBar(ui.progress, Modifier.fillMaxWidth().height(4.dp))
        Column(Modifier.semantics { liveRegion = LiveRegionMode.Polite }, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            val shown = ui.lines.takeLast(4)
            shown.forEachIndexed { i, line ->
                val isLast = i == shown.lastIndex
                StepLine(line, done = !isLast || ui.done)
            }
        }
    }
}
