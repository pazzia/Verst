package app.verst.feature.common

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.layout
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import app.verst.core.ui.components.LocalReducedMotion
import kotlinx.coroutines.launch
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
import app.verst.core.ui.components.CraftBadge
import app.verst.core.ui.components.CraftBadgeColor
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftSecondaryButton
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/**
 * components §16 `BottomSheet`; camper fork: a paper sheet with the brown 2.5 dp rim and the card radius on top
 * (no rim at the bottom edge), handle, title row (optional leading sign and overline) with a 44 dp «Закрыть» tile,
 * a thin rule, content padding 8 18 20, ≤ 88 % of the window. Scrim; slides in; drag down to dismiss.
 */
@Composable
fun BoxScope.BottomSheet(
    title: String,
    onClose: () -> Unit,
    tag: String,
    maxHeight: Dp,
    badge: String? = null,
    /** TalkBack pane title when it differs from the visible title (D-13 `cd_mock_partner`). */
    pane: String = title,
    /** 5.9 C2: the mini sign before the title (cards). */
    leading: (@Composable () -> Unit)? = null,
    /** Camper fork: a line above the title (the card's kind overline). */
    overline: (@Composable () -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val close = stringResource(R.string.common_close)
    val reduced = LocalReducedMotion.current
    val enter = remember { Animatable(if (reduced) 1f else 0f) }
    LaunchedEffect(Unit) {
        if (!reduced) enter.animateTo(1f, tween(DesignTokens.motion.bottomSheetIn.durationMs, easing = DesignTokens.motion.bottomSheetIn.easing))
    }
    val drag = remember { Animatable(0f) }
    var sheetH by remember { mutableStateOf(1) }
    val scope = rememberCoroutineScope()
    val density = LocalDensity.current
    Box(
        Modifier.matchParentSize().graphicsLayer { alpha = enter.value }.background(C.overlay.scrim)
            .clickable(remember { MutableInteractionSource() }, indication = null, onClick = onClose),
    )
    val shape = RoundedCornerShape(topStart = CraftDefaults.CardRadius, topEnd = CraftDefaults.CardRadius)
    Column(
        Modifier
            .align(Alignment.BottomCenter)
            .fillMaxWidth()
            .heightIn(max = maxHeight * 0.88f)
            .onSizeChanged { sheetH = it.height.coerceAtLeast(1) }
            // bottomSheetIn: slide from the bottom; drag down to dismiss (25 % or a fling > 1200 dp/s), else spring back.
            .graphicsLayer { translationY = (1 - enter.value) * sheetH + drag.value }
            .draggable(
                rememberDraggableState { d -> scope.launch { drag.snapTo((drag.value + d).coerceAtLeast(0f)) } },
                Orientation.Vertical,
                onDragStopped = { v ->
                    val fling = with(density) { v.toDp().value } > 1200f
                    if (drag.value > sheetH * 0.25f || fling) onClose() else drag.animateTo(0f, spring(stiffness = 400f))
                },
            )
            // the brown rim on the top and the sides, then the paper
            .clip(shape)
            .background(C.camper.border)
            .padding(start = CraftDefaults.Border, top = CraftDefaults.Border, end = CraftDefaults.Border)
            .clip(shape)
            .background(C.camper.paper)
            // Swallow taps so they do not reach the scrim (pointerInput, not clickable: no semantics merging).
            .pointerInput(Unit) { detectTapGestures { } }
            .semantics { paneTitle = pane }
            .testTag(tag)
            .padding(start = 18.dp, end = 18.dp, top = 8.dp, bottom = 20.dp),
    ) {
        Box(
            Modifier.align(Alignment.CenterHorizontally).size(DesignTokens.size.sheetHandleW, DesignTokens.size.sheetHandleH)
                .clip(RoundedCornerShape(2.dp)).background(C.camper.border.copy(alpha = 0.35f)),
        )
        Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            if (leading != null) {
                Box(Modifier.padding(end = 12.dp).testTag("$tag.sign")) { leading() }
            }
            // With a badge the title keeps its natural width (it is short) and the spacer takes the rest.
            Column(if (badge == null) Modifier.weight(1f) else Modifier, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                if (overline != null) overline()
                Txt(title, T.title.lg, C.camper.ink, maxLines = 2)
            }
            if (badge != null) {
                // D-13 «ДЕМО» badge: the amber craft badge.
                CraftBadge(badge, Modifier.padding(start = 8.dp).testTag("$tag.badge"), CraftBadgeColor.AMBER)
                Spacer(Modifier.weight(1f))
            }
            Box(
                Modifier.size(DesignTokens.size.touchMin).clip(RoundedCornerShape(DesignTokens.radius.r8))
                    .clickable(role = Role.Button, onClick = onClose).semantics { contentDescription = close }.testTag("$tag.close"),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    Modifier.size(32.dp).craftSurface(
                        C.camper.field, radius = 10.dp, border = CraftDefaults.BorderThin, shadow = C.camper.border,
                        shadowX = CraftDefaults.TileShadow, shadowY = CraftDefaults.TileShadow,
                    ),
                    contentAlignment = Alignment.Center,
                ) { GlyphIcon(Glyph.CLOSE, C.camper.ink, 16.dp) }
            }
        }
        Box(Modifier.fillMaxWidth().padding(top = 8.dp).height(1.dp).background(C.camper.divider))
        // bottom 4 dp: room for the hard shadow of a last craft button inside the scroll clip
        Column(
            Modifier.fillMaxWidth().weight(1f, fill = false).verticalScroll(rememberScrollState()).padding(top = 8.dp, bottom = 4.dp),
            content = content,
        )
    }
}

/** Lays the content out at [k] of its natural size (the 0.7 mini signs of D-6 and the 5.9 card title). */
fun Modifier.scaled(k: Float): Modifier = layout { m, _ ->
    val p = m.measure(androidx.compose.ui.unit.Constraints())
    val w = (p.width * k).toInt()
    val h = (p.height * k).toInt()
    layout(w, h) { p.placeWithLayer((w - p.width) / 2, (h - p.height) / 2) { scaleX = k; scaleY = k } }
}

/** components §16 `PlateToast`; camper fork: a paper craft plate, bottom-centred above [bottom], text + optional orange action, polite live region. */
@Composable
fun BoxScope.PlateToast(text: String, bottom: Dp, action: String? = null, onAction: () -> Unit = {}) {
    // Toast in: α 0 → 1, 8 dp → 0, 200 ms decelerate (motion.md §2.2), re-run for each new text.
    val reduced = LocalReducedMotion.current
    val p = remember(text) { Animatable(if (reduced) 1f else 0f) }
    LaunchedEffect(text) { if (!reduced) p.animateTo(1f, tween(200, easing = DesignTokens.motion.easing.decelerate)) }
    Row(
        Modifier
            .align(Alignment.BottomCenter)
            .graphicsLayer { alpha = p.value; translationY = 8.dp.toPx() * (1 - p.value) }
            .padding(start = 16.dp, end = 16.dp, bottom = bottom)
            .defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .craftSurface(C.camper.paper, radius = 14.dp, border = CraftDefaults.BorderThin)
            .semantics(mergeDescendants = true) { liveRegion = LiveRegionMode.Polite }
            .testTag("toast")
            .padding(horizontal = 16.dp), // F-02: one line + action = 44 dp (the action box is the 44 touch target)
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Txt(text, T.body.mdTight, C.camper.ink, Modifier.weight(1f, fill = false).padding(vertical = 10.dp))
        if (action != null) {
            Box(
                Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = onAction).testTag("toast.action"),
                contentAlignment = Alignment.Center,
            ) { Txt(action, T.body.mdStrong, C.camper.orangeText, maxLines = 1) }
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

/**
 * components §16 `NaviDialog`; camper fork: a centred craft card (window − 48), title, body, the orange
 * [CraftButton] (primary) and the paper [CraftSecondaryButton] (secondary).
 */
@Composable
fun BoxScope.NaviDialog(
    title: String,
    body: String,
    primary: String,
    secondary: String,
    tag: String,
    onPrimary: () -> Unit,
    onSecondary: () -> Unit,
    /** S4 `AgeGateDialog`: «Нет» / «Да» side by side, equal width («Да» orange, right). */
    sideBySide: Boolean = false,
) {
    Box(Modifier.matchParentSize().background(C.overlay.scrim).clickable(remember { MutableInteractionSource() }, indication = null, onClick = onSecondary))
    Column(
        Modifier.align(Alignment.Center).fillMaxWidth().padding(horizontal = 24.dp).craftSurface()
            .pointerInput(Unit) { detectTapGestures { } }
            .semantics { paneTitle = title }.testTag(tag)
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(if (sideBySide) 16.dp else 12.dp),
    ) {
        Txt(title, T.title.lg, C.camper.ink)
        if (body.isNotEmpty()) Txt(body, CraftType.body, C.camper.inkSoft)
        if (sideBySide) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                CraftSecondaryButton(secondary, onSecondary, Modifier.weight(1f).testTag("$tag.no"))
                CraftButton(primary, onPrimary, Modifier.weight(1f).testTag("$tag.yes"))
            }
        } else {
            CraftButton(primary, onPrimary, Modifier.fillMaxWidth().testTag("$tag.yes"))
            CraftSecondaryButton(secondary, onSecondary, Modifier.fillMaxWidth().testTag("$tag.no"))
        }
    }
}
