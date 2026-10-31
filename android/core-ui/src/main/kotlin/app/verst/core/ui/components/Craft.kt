package app.verst.core.ui.components

import androidx.annotation.DrawableRes
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import app.verst.core.ui.theme.DesignTokens
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/*
 * Fork camper-ui (CEO 31.10): the «Кемпер-гид» craft components (design/camper/mockup-13-screens.html).
 *
 * Look: paper surfaces (`color.camper.paper`), a 2–2.5 dp brown border (`color.camper.border`), large radii and a
 * HARD offset shadow (no blur) down-right. Colours come from `DesignTokens.color.camper.*` only; sizes from
 * [CraftDefaults]; text styles from [CraftType] (the app fonts, no new font files).
 *
 * The hard shadow is drawn outside the component bounds (3 × 4 dp for cards and buttons, 2 × 2 dp for tiles):
 * leave at least 4 dp to the right and below inside a clipping parent.
 */

/** Sizes of the craft look (the mockup's CSS in dp). */
object CraftDefaults {
    /** Card and button border (mockup 2.5 px). */
    val Border: Dp = 2.5.dp
    /** Field, chip, key and icon-tile border. */
    val BorderThin: Dp = 2.dp
    /** Badge border. */
    val BadgeBorder: Dp = 1.5.dp
    val CardRadius: Dp = 20.dp
    val ButtonRadius: Dp = 16.dp
    val FieldRadius: Dp = 12.dp
    val ChipRadius: Dp = 12.dp
    val BadgeRadius: Dp = 10.dp
    /** Hard shadow offset of cards and buttons. */
    val ShadowX: Dp = 3.dp
    val ShadowY: Dp = 4.dp
    /** A pressed button moves by this much right and down (its shadow stays: it looks pushed in). */
    val PressShift: Dp = 2.dp
    /** Hard shadow offset of icon tiles, keys and the header's buttons. */
    val TileShadow: Dp = 2.dp
    val TileSize: Dp = 32.dp
    /** CraftButton / CraftSecondaryButton minimum height. */
    val ButtonHeight: Dp = 52.dp
    /** Screen side gutter and the gap between cards (mockup p-3.5, space-y-3). */
    val ScreenGutter: Dp = 14.dp
    val Gap: Dp = 12.dp
    /** Inner padding of a CraftCard. */
    val CardPadding: PaddingValues = PaddingValues(12.dp)
}

/** Text styles of the craft components, derived from the type tokens (Verst Sans Narrow / Plex Mono). */
object CraftType {
    /** CraftButton label, 15 sp bold, slightly tracked (pass uppercase copy for the mockup look). */
    val button: TextStyle = T.cta.sm.copy(letterSpacing = 0.04.em)
    /** CraftSecondaryButton / SecondaryButton label. */
    val buttonSecondary: TextStyle = T.button.md
    /** Title inside a card («Мой кемпер / Экипаж», a stop name). */
    val cardTitle: TextStyle = T.title.sm
    /** Section title above cards (uppercase copy). */
    val sectionTitle: TextStyle = T.label.md.copy(fontWeight = FontWeight.W700, fontSize = 12.sp, lineHeight = 15.6.sp)
    /** Small orange / green overline above a card title («ДЕНЬ 1 ИЗ 2», uppercase copy). */
    val overline: TextStyle = T.label.md.copy(fontWeight = FontWeight.W700)
    /** CraftBadge text. */
    val badge: TextStyle = T.tag.kind
    /** CraftChip / ToggleChip text. */
    val chip: TextStyle = T.body.mdStrong
    /** CraftField value. */
    val field: TextStyle = T.field.md
    /** CraftField value in mono (amounts, km per day). */
    val fieldMono: TextStyle = T.tag.odometer.copy(fontSize = 15.sp, lineHeight = 20.sp)
    /** Field label above a CraftField. */
    val fieldLabel: TextStyle = T.label.md
    /** Body copy inside cards. */
    val body: TextStyle = T.body.md
    /** Secondary lines («Москва → Владимир → Суздаль»). */
    val caption: TextStyle = T.body.sm
    /** Tab bar labels. */
    val tab: TextStyle = T.caption.bold
    /** «ВЕРСТА» in the header. */
    val wordmark: TextStyle = T.title.md.copy(letterSpacing = 0.12.em)
}

enum class CraftBadgeColor { AMBER, ORANGE, GREEN, BLUE }

/** The hard (unblurred) offset shadow of the craft look, drawn behind the rest of the chain. */
fun Modifier.craftShadow(
    radius: Dp,
    dx: Dp = CraftDefaults.ShadowX,
    dy: Dp = CraftDefaults.ShadowY,
    color: Color = C.camper.shadow,
): Modifier = drawBehind {
    drawRoundRect(color, topLeft = Offset(dx.toPx(), dy.toPx()), size = size, cornerRadius = CornerRadius(radius.toPx()))
}

/**
 * A craft surface: hard shadow (null = none), rounded clip, fill and brown border. Use it for your own containers
 * (rows inside a card, a sheet header); CraftCard uses it with the defaults.
 */
fun Modifier.craftSurface(
    fill: Color = C.camper.paper,
    radius: Dp = CraftDefaults.CardRadius,
    border: Dp = CraftDefaults.Border,
    borderColor: Color = C.camper.border,
    shadow: Color? = C.camper.shadow,
    shadowX: Dp = CraftDefaults.ShadowX,
    shadowY: Dp = CraftDefaults.ShadowY,
): Modifier {
    val shape = RoundedCornerShape(radius)
    val withShadow = if (shadow != null) craftShadow(radius, shadowX, shadowY, shadow) else this
    return withShadow.clip(shape).background(fill).border(border, borderColor, shape)
}

/** The frame of an input field (white paper, 2 dp brown border, radius 12); orange border while [focused]. */
fun Modifier.craftField(fill: Color = C.camper.field, focused: Boolean = false): Modifier {
    val shape = RoundedCornerShape(CraftDefaults.FieldRadius)
    return clip(shape).background(fill).border(CraftDefaults.BorderThin, if (focused) C.camper.orange else C.camper.border, shape)
}

/** `.craft-card`: paper, 2.5 dp brown border, radius 20, hard shadow 3 × 4 dp (brown 25 %); a column of [content]. */
@Composable
fun CraftCard(
    modifier: Modifier = Modifier,
    padding: PaddingValues = CraftDefaults.CardPadding,
    onClick: (() -> Unit)? = null,
    fill: Color = C.camper.paper,
    spacing: Dp = 10.dp,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier
            .craftSurface(fill)
            .then(if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier)
            .padding(padding),
        verticalArrangement = Arrangement.spacedBy(spacing),
        content = content,
    )
}

/**
 * The pressable craft plate shared by the buttons: a full-brown hard shadow that stays put while the face moves
 * [CraftDefaults.PressShift] right and down on press (mockup `.craft-btn:active`), so the shadow shrinks to 1 × 2.
 */
@Composable
internal fun CraftPressable(
    fill: Color,
    pressedFill: Color,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier,
    minHeight: Dp,
    horizontalPadding: Dp,
    arrangement: Arrangement.Horizontal,
    content: @Composable RowScope.() -> Unit,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val reduced = LocalReducedMotion.current
    val shift by animateFloatAsState(
        targetValue = if (pressed && enabled) 1f else 0f,
        animationSpec = tween(durationMillis = if (reduced) 0 else 120),
        label = "craftPress",
    )
    val radius = CraftDefaults.ButtonRadius
    val shape = RoundedCornerShape(radius)
    Row(
        modifier
            .defaultMinSize(minHeight = minHeight)
            .then(if (enabled) Modifier.craftShadow(radius, color = C.camper.border) else Modifier)
            .graphicsLayer {
                translationX = shift * CraftDefaults.PressShift.toPx()
                translationY = shift * CraftDefaults.PressShift.toPx()
            }
            .clip(shape)
            .background(if (pressed && enabled) pressedFill else fill)
            .border(CraftDefaults.Border, if (enabled) C.camper.border else C.camper.border.copy(alpha = 0.4f), shape)
            .clickable(interaction, indication = null, enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(horizontal = horizontalPadding),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = arrangement,
        content = content,
    )
}

/** `.craft-btn`: the primary button — orange, white bold label, optional leading icon (a DES-102 / ic_ui_* drawable). */
@Composable
fun CraftButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    @DrawableRes icon: Int? = null,
    enabled: Boolean = true,
) {
    val fg = if (enabled) C.camper.onOrange else C.camper.inkMuted
    CraftPressable(
        fill = if (enabled) C.camper.orange else C.camper.header,
        pressedFill = C.camper.orangePressed,
        enabled = enabled,
        onClick = onClick,
        modifier = modifier,
        minHeight = CraftDefaults.ButtonHeight,
        horizontalPadding = DesignTokens.space.s16,
        arrangement = Arrangement.spacedBy(DesignTokens.space.s8, Alignment.CenterHorizontally),
    ) {
        if (icon != null) Icon(icon, fg, 18.dp)
        Txt(text, CraftType.button, fg, maxLines = 1)
    }
}

/** The paper twin of [CraftButton] («Заменить», «Сохранить офлайн»): paper fill, brown text, same border and shadow. */
@Composable
fun CraftSecondaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    @DrawableRes icon: Int? = null,
    enabled: Boolean = true,
) {
    val fg = if (enabled) C.camper.ink else C.camper.inkMuted
    CraftPressable(
        fill = if (enabled) C.camper.paper else C.camper.header,
        pressedFill = C.camper.header,
        enabled = enabled,
        onClick = onClick,
        modifier = modifier,
        minHeight = CraftDefaults.ButtonHeight,
        horizontalPadding = DesignTokens.space.s16,
        arrangement = Arrangement.spacedBy(DesignTokens.space.s8, Alignment.CenterHorizontally),
    ) {
        if (icon != null) Icon(icon, fg, 18.dp)
        Txt(text, CraftType.buttonSecondary, fg, maxLines = 1)
    }
}

/** `.craft-badge`: a small filled label with a 1.5 dp brown border, radius 10 («4 гостя», «220 км», «Включён»). */
@Composable
fun CraftBadge(text: String, modifier: Modifier = Modifier, color: CraftBadgeColor = CraftBadgeColor.AMBER) {
    val (fill, fg) = when (color) {
        CraftBadgeColor.AMBER -> C.camper.amber to C.camper.onAmber
        CraftBadgeColor.ORANGE -> C.camper.orange to C.camper.onOrange
        CraftBadgeColor.GREEN -> C.camper.green to C.camper.onOrange
        CraftBadgeColor.BLUE -> C.camper.blue to C.camper.onOrange
    }
    val shape = RoundedCornerShape(CraftDefaults.BadgeRadius)
    Box(
        modifier
            .clip(shape)
            .background(fill)
            .border(CraftDefaults.BadgeBorder, C.camper.border, shape)
            .padding(horizontal = DesignTokens.space.s8, vertical = DesignTokens.space.s2),
        contentAlignment = Alignment.Center,
    ) { Txt(text, CraftType.badge, fg, maxLines = 1) }
}

/** A choice chip (mood «Спокойно / Весело», presets): orange with white text when [selected], else white paper. */
@Composable
fun CraftChip(
    text: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    role: Role = Role.RadioButton,
    @DrawableRes icon: Int? = null,
) {
    val shape = RoundedCornerShape(CraftDefaults.ChipRadius)
    val fg = if (selected) C.camper.onOrange else C.camper.ink
    Row(
        modifier
            .defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .clip(shape)
            .background(if (selected) C.camper.orange else C.camper.field)
            .border(CraftDefaults.BorderThin, C.camper.border, shape)
            .clickable(role = role, onClick = onClick)
            .padding(horizontal = DesignTokens.space.s14),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(DesignTokens.space.s6, Alignment.CenterHorizontally),
    ) {
        if (icon != null) Icon(icon, fg, 16.dp)
        Txt(text, CraftType.chip, fg, maxLines = 1)
    }
}

/**
 * A rounded-square icon tile (tab bar, stop markers, the header gear): 2 dp brown border, 2 × 2 dp hard shadow;
 * [active] = orange with a white icon, else paper with a brown icon. [fill] / [tint] override both (the amber logo
 * tile). With [onClick] the tile sits in a 44 dp touch target; [cd] is its TalkBack label.
 */
@Composable
fun CraftIconTile(
    @DrawableRes iconRes: Int,
    active: Boolean,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    size: Dp = CraftDefaults.TileSize,
    cd: String? = null,
    fill: Color? = null,
    tint: Color? = null,
) {
    val radius = if (size >= 30.dp) 10.dp else 8.dp
    val shape = RoundedCornerShape(radius)
    val bg = fill ?: if (active) C.camper.orange else C.camper.paper
    val fg = tint ?: if (active) C.camper.onOrange else C.camper.border
    val tile = Modifier
        .size(size)
        .craftShadow(radius, CraftDefaults.TileShadow, CraftDefaults.TileShadow, C.camper.border)
        .clip(shape)
        .background(bg)
        .border(CraftDefaults.BorderThin, C.camper.border, shape)
    val described = if (cd != null) Modifier.semantics { contentDescription = cd } else Modifier
    if (onClick == null) {
        Box(modifier.then(tile).then(described), contentAlignment = Alignment.Center) { Icon(iconRes, fg, size * 0.55f) }
    } else {
        Box(
            modifier
                .sizeIn(minWidth = DesignTokens.size.touchMin, minHeight = DesignTokens.size.touchMin)
                .clip(RoundedCornerShape(DesignTokens.radius.r8))
                .clickable(role = Role.Button, onClick = onClick)
                .then(described),
            contentAlignment = Alignment.Center,
        ) {
            Box(tile, contentAlignment = Alignment.Center) { Icon(iconRes, fg, size * 0.55f) }
        }
    }
}

/**
 * A read-only (optionally clickable) field: optional [label] above, white paper frame ([craftField]), the value
 * or the [placeholder] when [text] is empty, optional leading / trailing icons. For typing, put a BasicTextField
 * in `Modifier.craftField(focused = …)` yourself.
 */
@Composable
fun CraftField(
    text: String,
    modifier: Modifier = Modifier,
    label: String? = null,
    placeholder: String? = null,
    @DrawableRes leadingIcon: Int? = null,
    @DrawableRes trailingIcon: Int? = null,
    onClick: (() -> Unit)? = null,
    mono: Boolean = false,
    fill: Color = C.camper.field,
) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(DesignTokens.space.s4)) {
        if (label != null) Txt(label, CraftType.fieldLabel, C.camper.inkSoft, maxLines = 1)
        Row(
            Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = DesignTokens.size.touchMin)
                .craftField(fill)
                .then(if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier)
                .padding(horizontal = DesignTokens.space.s12, vertical = DesignTokens.space.s8),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(DesignTokens.space.s8),
        ) {
            if (leadingIcon != null) Icon(leadingIcon, C.camper.orangeText, 16.dp)
            val empty = text.isEmpty()
            Txt(
                if (empty) placeholder.orEmpty() else text,
                if (mono && !empty) CraftType.fieldMono else CraftType.field,
                if (empty) C.camper.inkMuted else C.camper.ink,
                Modifier.weight(1f),
                maxLines = 1,
            )
            if (trailingIcon != null) Icon(trailingIcon, C.camper.border, 16.dp)
        }
    }
}

/** A section title above cards (uppercase copy, ink, heading for TalkBack) with an optional orange link at the end. */
@Composable
fun CraftSectionTitle(text: String, modifier: Modifier = Modifier, action: String? = null, onAction: (() -> Unit)? = null) {
    Row(
        modifier.fillMaxWidth().padding(horizontal = DesignTokens.space.s4),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Txt(text, CraftType.sectionTitle, C.camper.ink, Modifier.weight(1f).semantics { heading() }, maxLines = 2)
        if (action != null) {
            Box(
                Modifier
                    .defaultMinSize(minHeight = DesignTokens.size.touchMin)
                    .then(if (onAction != null) Modifier.clickable(role = Role.Button, onClick = onAction) else Modifier)
                    .padding(start = DesignTokens.space.s8),
                contentAlignment = Alignment.CenterEnd,
            ) { Txt(action, T.body.smStrong, C.camper.orangeText, maxLines = 1) }
        }
    }
}

/** The dashed rule inside cards (mockup `border-dashed border-[#4A3525]/20`). */
@Composable
fun DashedDivider(modifier: Modifier = Modifier, color: Color = C.camper.divider, thickness: Dp = 2.dp) {
    Box(
        modifier
            .fillMaxWidth()
            .height(thickness)
            .drawBehind {
                val y = size.height / 2
                drawLine(
                    color, Offset(0f, y), Offset(size.width, y), strokeWidth = size.height,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 4.dp.toPx())),
                )
            },
    )
}
