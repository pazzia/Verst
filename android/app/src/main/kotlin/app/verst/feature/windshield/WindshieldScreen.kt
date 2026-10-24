package app.verst.feature.windshield

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.ui.R
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.PlaceholderPlate
import app.verst.core.ui.components.StartButton
import app.verst.core.ui.components.StartSize
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.WindshieldScene
import app.verst.core.ui.components.arrowFor
import app.verst.core.ui.components.dashboardSurface
import app.verst.core.ui.components.naviPanel
import app.verst.core.ui.components.overheadPlate
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.crewShort
import app.verst.feature.common.genitive
import app.verst.nav.WindshieldData

private val C = DesignTokens.color
private val T = DesignTokens.type
private val DashHeight = 324.dp

/** Everything the Windshield draws (stateless; the caller maps `VerstFlow` into it). */
data class WindshieldUi(
    val origin: String,
    val data: WindshieldData,
    val selected: Int,
    val adults: Int,
    val children: Int,
    val dog: Boolean,
)

/** 5.1 Windshield, simplified: ready routes on the overhead sign, the navigator entry, the start button. */
@Composable
fun WindshieldScreen(
    ui: WindshieldUi,
    onSelect: (Int) -> Unit,
    onStart: () -> Unit,
    onNavigator: () -> Unit,
    onRetry: () -> Unit,
) {
    ScreenRoot(C.dash.base) {
        BoxWithConstraints(Modifier.matchParentSize()) {
            val sceneH = maxHeight - DashHeight + 20.dp
            WindshieldScene(sceneH)
            Mirror(crewShort(ui.adults, ui.children, ui.dog), Modifier.align(Alignment.TopCenter).padding(top = 8.dp))
            Sign(ui, onSelect, onRetry, Modifier.padding(start = 20.dp, end = 20.dp, top = 84.dp).fillMaxWidth())
            Dashboard(ui, onStart, onNavigator, Modifier.align(Alignment.BottomCenter))
        }
    }
}

@Composable
private fun Mirror(caption: String, modifier: Modifier) {
    Column(modifier.semantics(mergeDescendants = true) {}, horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.size(8.dp, 10.dp).background(C.dash.controlAlt))
        Box(
            Modifier
                .size(DesignTokens.size.mirrorSW, DesignTokens.size.mirrorSH)
                .clip(RoundedCornerShape(22.dp))
                .background(C.dash.controlAlt)
                .padding(3.dp)
                .clip(RoundedCornerShape(19.dp))
                .background(C.mirror.glass),
            contentAlignment = Alignment.Center,
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(13.dp), verticalAlignment = Alignment.Bottom) {
                repeat(3) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(Modifier.size(12.dp).clip(CircleShape).background(C.mirror.label.copy(alpha = 0.5f)))
                        Box(Modifier.padding(top = 2.dp).size(22.dp, 10.dp).clip(RoundedCornerShape(topStart = 8.dp, topEnd = 8.dp)).background(C.mirror.label.copy(alpha = 0.5f)))
                    }
                }
            }
        }
        Txt(caption, T.caption.strong, C.mirror.label, Modifier.padding(top = 3.dp), maxLines = 1)
    }
}

@Composable
private fun Sign(ui: WindshieldUi, onSelect: (Int) -> Unit, onRetry: () -> Unit, modifier: Modifier) {
    val loadingCd = stringResource(R.string.windshield_loading_cd)
    Column(modifier.overheadPlate().padding(start = 12.dp, end = 12.dp, top = 12.dp, bottom = 10.dp)) {
        Row(Modifier.fillMaxWidth().padding(start = 6.dp, end = 6.dp, bottom = 4.dp)) {
            Txt(
                stringResource(R.string.windshield_sign_header, genitive(ui.origin).uppercase()),
                T.label.md, C.sign.blueText, Modifier.weight(1f).semantics { heading() }, maxLines = 1,
            )
            if (ui.data is WindshieldData.Routes) Txt(stringResource(R.string.windshield_sign_km), T.label.md, C.sign.blueText)
        }
        when (val d = ui.data) {
            is WindshieldData.Loading -> Column(Modifier.semantics(mergeDescendants = true) { contentDescription = loadingCd }) {
                repeat(4) {
                    Row(Modifier.fillMaxWidth().height(44.dp).padding(horizontal = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        PlaceholderPlate(22.dp, 22.dp, C.sign.plate)
                        Spacer(Modifier.width(10.dp))
                        PlaceholderPlate(150.dp, 14.dp, C.sign.plate)
                        Spacer(Modifier.weight(1f))
                        PlaceholderPlate(30.dp, 14.dp, C.sign.plate)
                    }
                }
            }
            is WindshieldData.Routes -> {
                d.routes.take(4).forEachIndexed { i, r -> RouteRow(r, i == ui.selected, i) { onSelect(i) } }
                val more = d.routes.size - 4
                if (more > 0) {
                    Txt(
                        stringResource(R.string.windshield_sign_more, more, pluralStringResource(R.plurals.plural_route, more)),
                        T.caption.md, C.sign.blueText, Modifier.padding(start = 6.dp, top = 3.dp),
                    )
                }
            }
            is WindshieldData.NoRoutes -> Column(Modifier.padding(horizontal = 6.dp, vertical = 10.dp)) {
                Txt(stringResource(R.string.windshield_no_routes_sign), T.sign.lg, C.sign.white)
                Txt(stringResource(R.string.windshield_no_routes_footer), T.caption.md, C.sign.blueText, Modifier.padding(top = 8.dp))
            }
            is WindshieldData.Failed -> Column(Modifier.padding(horizontal = 6.dp, vertical = 6.dp)) {
                if (d.engineFailed) {
                    Txt(stringResource(R.string.engine_failed_title), T.sign.lg, C.sign.white)
                    Txt(stringResource(R.string.engine_failed_text), T.caption.md, C.sign.blueText, Modifier.padding(top = 4.dp))
                } else {
                    Txt(stringResource(R.string.windshield_error_sign), T.sign.lg, C.sign.white)
                }
                Row(
                    Modifier
                        .padding(top = 6.dp)
                        .height(44.dp)
                        .clip(RoundedCornerShape(DesignTokens.radius.r4))
                        .clickable(role = Role.Button, onClick = onRetry)
                        .testTag("windshield.retry")
                        .padding(end = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Icon(R.drawable.ic_arrow_right, C.accent.yellow, 22.dp)
                    Txt(stringResource(R.string.common_retry), T.sign.lg, C.accent.yellow)
                }
            }
        }
    }
}

@Composable
private fun RouteRow(r: ReadyRouteDto, selected: Boolean, index: Int, onClick: () -> Unit) {
    val fg = if (selected) C.accent.yellow else C.sign.white
    Row(
        Modifier
            .fillMaxWidth()
            .height(44.dp)
            .clip(RoundedCornerShape(DesignTokens.radius.r4))
            .background(if (selected) C.sign.blueSelected else C.sign.blue.copy(alpha = 0f))
            .clickable(role = Role.Button, onClick = onClick)
            .testTag("windshield.route.$index")
            .padding(horizontal = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(arrowFor(r.bearing8), fg, 22.dp)
        Spacer(Modifier.width(10.dp))
        Txt(r.title, T.sign.lg, fg, Modifier.weight(1f), maxLines = 1)
        Txt(r.kmSign.toString(), T.sign.lg, fg, align = TextAlign.End)
    }
}

@Composable
private fun Dashboard(ui: WindshieldUi, onStart: () -> Unit, onNavigator: () -> Unit, modifier: Modifier) {
    val routes = (ui.data as? WindshieldData.Routes)?.routes
    val selected = routes?.getOrNull(ui.selected)
    Box(modifier.fillMaxWidth().height(DashHeight).dashboardSurface()) {
        NaviEntry(ui.origin, onNavigator, Modifier.padding(start = 18.dp, end = 18.dp, top = 22.dp).fillMaxWidth())
        Row(
            Modifier.align(Alignment.BottomStart).fillMaxWidth().padding(start = 22.dp, end = 20.dp, bottom = 56.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f).padding(end = 14.dp).semantics(mergeDescendants = true) {}) {
                val (label, title, meta) = when {
                    selected != null -> Triple(stringResource(R.string.windshield_selected_label), selected.title, selected.subtitle)
                    ui.data is WindshieldData.Loading -> Triple(stringResource(R.string.windshield_selected_label), null, null)
                    else -> Triple(
                        stringResource(R.string.windshield_no_routes_label),
                        stringResource(R.string.windshield_no_routes_title),
                        stringResource(R.string.windshield_no_routes_meta),
                    )
                }
                Txt(label, T.label.md, C.text.muted, maxLines = 1)
                if (title != null) Txt(title, T.title.xl, C.text.primary, maxLines = 1) else PlaceholderPlate(160.dp, 20.dp, C.dash.controlAlt, Modifier.padding(vertical = 4.dp))
                if (meta != null) Txt(meta, T.body.mdTight, C.text.secondary, Modifier.padding(top = 2.dp), maxLines = 1) else PlaceholderPlate(120.dp, 12.dp, C.dash.controlAlt)
            }
            StartButton(
                StartSize.M, stringResource(R.string.common_go), enabled = selected != null,
                cd = if (selected != null) stringResource(R.string.cd_start_route, selected.title) else stringResource(R.string.cd_start_disabled_destination),
                onClick = onStart, modifier = Modifier.testTag("windshield.start"),
            )
        }
    }
}

@Composable
private fun NaviEntry(origin: String, onClick: () -> Unit, modifier: Modifier) {
    val cd = stringResource(R.string.cd_windshield_navi)
    Column(
        modifier
            .naviPanel()
            .clip(RoundedCornerShape(16.dp))
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("windshield.navi")
            .padding(start = 18.dp, end = 18.dp, top = 16.dp, bottom = 14.dp),
    ) {
        Row(Modifier.fillMaxWidth()) {
            Txt(stringResource(R.string.windshield_navi_label), T.label.md, C.navi.label, Modifier.weight(1f))
            Txt(stringResource(R.string.windshield_you_are, origin.uppercase()), T.label.md, C.navi.label)
        }
        Row(
            Modifier
                .padding(top = 12.dp)
                .fillMaxWidth()
                .height(48.dp)
                .clip(RoundedCornerShape(DesignTokens.radius.r10))
                .background(C.navi.field)
                .border(DesignTokens.stroke.w1, C.navi.fieldBorder, RoundedCornerShape(DesignTokens.radius.r10))
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            SearchGlyph()
            Spacer(Modifier.width(10.dp))
            Column {
                Txt(stringResource(R.string.windshield_field_title), T.field.md, C.text.primary, maxLines = 1)
                Txt(stringResource(R.string.windshield_field_sub), T.body.sm, C.navi.labelSecondary, maxLines = 1)
            }
        }
        Txt(stringResource(R.string.windshield_hint), T.body.sm, C.navi.labelSecondary, Modifier.padding(top = 8.dp), maxLines = 1)
    }
}

/** Search icon (components §17.3): circle + handle, `stroke.icon.ui`, yellow. */
@Composable
fun SearchGlyph(modifier: Modifier = Modifier) {
    Box(
        modifier.size(18.dp).drawBehind {
            val sw = DesignTokens.stroke.icon.ui.toPx()
            val r = size.width * 0.32f
            val c = Offset(size.width * 0.42f, size.height * 0.42f)
            drawCircle(C.accent.yellow, r, c, style = Stroke(sw))
            drawLine(C.accent.yellow, Offset(c.x + r * 0.75f, c.y + r * 0.75f), Offset(size.width * 0.92f, size.height * 0.92f), sw)
        },
    )
}
