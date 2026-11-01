// Camper design (CEO 31.10 «Кемпер-гид», selectable in Settings since 01.11): the restyled twin of Basics.kt;
// the shared state and action types stay in that file.
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

private val BackLabelMax = 150.dp

/** components §13 `InfoChipCamper`; camper fork: a white-paper craft pill with a 1.5 dp brown border. */
@Composable
fun InfoChipCamper(text: String, modifier: Modifier = Modifier) {
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
fun ToggleChipCamper(text: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier, role: Role = Role.RadioButton) {
    CraftChip(text, selected, onClick, modifier, role)
}

/** components §5 `StepperKeyCamper` (− / +); camper fork: a header-tan key, 2 dp brown border, 2 × 2 dp hard shadow. */
@Composable
fun StepperKeyCamper(glyph: String, enabled: Boolean, cd: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
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

/** components §15 `PrimaryCtaCamper`; camper fork: the orange craft button (dark ink label + arrow), 58 high, full width. */
@Composable
fun PrimaryCtaCamper(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
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

/** components §15 `SecondaryButtonCamper`; camper fork: the paper craft button ([CraftSecondaryButton] look, 56 high). */
@Composable
fun SecondaryButtonCamper(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
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

