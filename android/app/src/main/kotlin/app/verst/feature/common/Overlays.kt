package app.verst.feature.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.paneTitle
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.ui.R
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/**
 * components §16 `BottomSheet`, static (no drag; the enter/exit motion is DEV-131 polish): scrim, top radius 16,
 * 2 dp rim, handle, title row with a 44 dp «Закрыть», content padding 8 20 24, ≤ 88 % of the window.
 */
@Composable
fun BoxScope.BottomSheet(title: String, onClose: () -> Unit, tag: String, maxHeight: Dp, content: @Composable ColumnScope.() -> Unit) {
    val close = stringResource(R.string.common_close)
    Box(
        Modifier.matchParentSize().background(C.overlay.scrim)
            .clickable(remember { MutableInteractionSource() }, indication = null, onClick = onClose),
    )
    val shape = RoundedCornerShape(topStart = DesignTokens.radius.r16, topEnd = DesignTokens.radius.r16)
    Column(
        Modifier
            .align(Alignment.BottomCenter)
            .fillMaxWidth()
            .heightIn(max = maxHeight * 0.88f)
            .clip(shape)
            .background(C.dash.control)
            .padding(top = 2.dp)
            .clip(shape)
            .background(C.dash.raised)
            // Swallow taps so they do not reach the scrim.
            .clickable(remember { MutableInteractionSource() }, indication = null) {}
            .semantics { paneTitle = title }
            .testTag(tag)
            .padding(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 24.dp),
    ) {
        Box(
            Modifier.align(Alignment.CenterHorizontally).size(DesignTokens.size.sheetHandleW, DesignTokens.size.sheetHandleH)
                .clip(RoundedCornerShape(2.dp)).background(C.dash.outline),
        )
        Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Txt(title, T.title.lg, C.text.primary, Modifier.weight(1f), maxLines = 2)
            Box(
                Modifier.size(DesignTokens.size.touchMin).clip(RoundedCornerShape(DesignTokens.radius.r8))
                    .clickable(role = Role.Button, onClick = onClose).semantics { contentDescription = close }.testTag("$tag.close"),
                contentAlignment = Alignment.Center,
            ) { GlyphIcon(Glyph.CLOSE, C.text.secondary, 20.dp) }
        }
        Column(Modifier.fillMaxWidth().weight(1f, fill = false).verticalScroll(rememberScrollState()), content = content)
    }
}

/** components §16 `PlateToast`: bottom-centred above [bottom], text + optional yellow action, polite live region. */
@Composable
fun BoxScope.PlateToast(text: String, bottom: Dp, action: String? = null, onAction: () -> Unit = {}) {
    Row(
        Modifier
            .align(Alignment.BottomCenter)
            .padding(start = 16.dp, end = 16.dp, bottom = bottom)
            .defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .clip(RoundedCornerShape(DesignTokens.radius.r10))
            .background(C.dash.control)
            .border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(DesignTokens.radius.r10))
            .semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite }
            .testTag("toast")
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Txt(text, T.body.mdTight, C.text.primary, Modifier.weight(1f, fill = false))
        if (action != null) {
            Box(
                Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = onAction).testTag("toast.action"),
                contentAlignment = Alignment.Center,
            ) { Txt(action, T.body.mdStrong, C.accent.yellow, maxLines = 1) }
        }
    }
}

/** A 44 × 44 icon button of a top bar (5.5 T1/T2). */
@Composable
fun IconButton44(glyph: Glyph, tint: androidx.compose.ui.graphics.Color, cd: String, tag: String, filled: Boolean = false, onClick: () -> Unit) {
    Box(
        Modifier.size(DesignTokens.size.touchMin).clip(RoundedCornerShape(DesignTokens.radius.r8))
            .clickable(role = Role.Button, onClick = onClick).semantics { contentDescription = cd }.testTag(tag),
        contentAlignment = Alignment.Center,
    ) { GlyphIcon(glyph, tint, 22.dp, filled = filled) }
}

/** Fill helper so callers can lay an overlay over the whole screen. */
@Composable
fun FullOverlay(content: @Composable BoxScope.() -> Unit) {
    Box(Modifier.fillMaxSize(), content = content)
}
