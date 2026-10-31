package app.verst.core.ui.components

import androidx.annotation.DrawableRes
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.ui.R
import app.verst.core.ui.theme.DesignTokens
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** `BasicText` with a token style and colour (there is no Material in this app). */
@Composable
fun Txt(
    text: String,
    style: TextStyle,
    color: Color,
    modifier: Modifier = Modifier,
    maxLines: Int = Int.MAX_VALUE,
    align: TextAlign? = null,
) {
    BasicText(
        text = text,
        modifier = modifier,
        style = if (align != null) style.copy(color = color, textAlign = align) else style.copy(color = color),
        maxLines = maxLines,
        overflow = if (maxLines == Int.MAX_VALUE) TextOverflow.Clip else TextOverflow.Ellipsis,
    )
}

/** A DES-102 vector drawable tinted at use (they are drawn in `color.sign.black`). */
@Composable
fun Icon(@DrawableRes id: Int, tint: Color, size: Dp, modifier: Modifier = Modifier) {
    Image(
        painter = painterResource(id),
        contentDescription = null,
        colorFilter = ColorFilter.tint(tint),
        modifier = modifier.size(size),
    )
}

/** components §14: back arrow + label, 44 dp touch, «Назад: <label>» for TalkBack. */
@Composable
fun BackLink(label: String, color: Color, cd: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier
            .defaultMinSize(minWidth = DesignTokens.size.touchMin, minHeight = DesignTokens.size.touchMin)
            .clip(RoundedCornerShape(DesignTokens.radius.r8))
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .padding(horizontal = DesignTokens.space.s4),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(DesignTokens.space.s6),
    ) {
        Icon(R.drawable.ic_arrow_left, color, 14.dp)
        Txt(label, T.body.mdTight, color, maxLines = 1, modifier = Modifier.widthIn(max = BackLabelMax))
    }
}

private val BackLabelMax = 150.dp

/** components §13 `InfoChip`; camper fork: a white-paper craft pill with a 1.5 dp brown border. */
@Composable
fun InfoChip(text: String, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(CraftDefaults.BadgeRadius)
    Box(
        modifier
            .clip(shape)
            .background(C.camper.field)
            .border(CraftDefaults.BadgeBorder, C.camper.border, shape)
            .padding(horizontal = 9.dp, vertical = DesignTokens.space.s4),
    ) { Txt(text, T.body.smStrong, C.camper.ink, maxLines = 1) }
}

/** components §13 `MoodChip` / `FrontSeatChip`; camper fork: [CraftChip] (orange when on, white paper when off). */
@Composable
fun ToggleChip(text: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier, role: Role = Role.RadioButton) {
    CraftChip(text, selected, onClick, modifier, role)
}

/** components §5 `StepperKey` (− / +); camper fork: a header-tan key, 2 dp brown border, 2 × 2 dp hard shadow. */
@Composable
fun StepperKey(glyph: String, enabled: Boolean, cd: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val radius = CraftDefaults.FieldRadius
    val shape = RoundedCornerShape(radius)
    Box(
        modifier
            .size(DesignTokens.size.keyW, DesignTokens.size.keyH)
            // the hard shadow replaces S-28 `shadow.key` (none when disabled)
            .then(if (enabled) Modifier.craftShadow(radius, CraftDefaults.TileShadow, CraftDefaults.TileShadow, C.camper.border) else Modifier)
            .clip(shape)
            .background(C.camper.header)
            .border(CraftDefaults.BorderThin, if (enabled) C.camper.border else C.camper.border.copy(alpha = 0.4f), shape)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics { contentDescription = cd },
        contentAlignment = Alignment.Center,
    ) { Txt(glyph, T.button.glyph.copy(fontWeight = FontWeight.W700), if (enabled) C.camper.ink else C.text.disabled) }
}

/** components §15 `PrimaryCta`; camper fork: the orange craft button (white label + arrow), 58 high, full width. */
@Composable
fun PrimaryCta(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    CraftPressable(
        fill = C.camper.orange,
        pressedFill = C.camper.orangePressed,
        enabled = true,
        onClick = onClick,
        modifier = modifier.fillMaxWidth().height(DesignTokens.size.ctaH),
        minHeight = DesignTokens.size.ctaH,
        horizontalPadding = DesignTokens.space.s18,
        arrangement = Arrangement.Start,
    ) {
        Txt(text, T.cta.md, C.camper.onOrange, maxLines = 1, modifier = Modifier.weight(1f))
        Icon(R.drawable.ic_arrow_right, C.camper.onOrange, 22.dp)
    }
}

/** components §15 `SecondaryButton`; camper fork: the paper craft button ([CraftSecondaryButton] look, 56 high). */
@Composable
fun SecondaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    CraftPressable(
        fill = C.camper.paper,
        pressedFill = C.camper.header,
        enabled = true,
        onClick = onClick,
        modifier = modifier.height(DesignTokens.size.buttonH),
        minHeight = DesignTokens.size.buttonH,
        horizontalPadding = DesignTokens.space.s12,
        arrangement = Arrangement.Center,
    ) { Txt(text, T.button.md, C.camper.ink, maxLines = 1, align = TextAlign.Center) }
}

/** A placeholder plate for loading rows (components §16 `Shimmer`, static: no infinite animation). */
@Composable
fun PlaceholderPlate(width: Dp, height: Dp, color: Color, modifier: Modifier = Modifier) {
    Box(modifier.size(width, height).clip(RoundedCornerShape(DesignTokens.radius.r4)).background(color))
}
