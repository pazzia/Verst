package app.verst.core.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.ui.R
import app.verst.core.ui.theme.DesignTokens
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** Direction arrow vector for an engine `bearing8` (components §17.1). */
fun arrowFor(bearing8: String): Int = when (bearing8) {
    "N" -> R.drawable.ic_arrow_up
    "NE" -> R.drawable.ic_arrow_up_right
    "E" -> R.drawable.ic_arrow_right
    "SE" -> R.drawable.ic_arrow_down_right
    "S" -> R.drawable.ic_arrow_down
    "SW" -> R.drawable.ic_arrow_down_left
    "W" -> R.drawable.ic_arrow_left
    else -> R.drawable.ic_arrow_up_left
}

/** Service pictogram by engine `sign` (signs.md: fuel 7.3, food 7.7, rest 7.11, hotel 7.12). */
fun servicePictogram(sign: String): Int = when (sign) {
    "fuel" -> R.drawable.ic_service_fuel
    "food" -> R.drawable.ic_service_food
    "hotel" -> R.drawable.ic_service_hotel
    else -> R.drawable.ic_service_rest
}

/** Tourist pictogram from the place tags. */
fun touristPictogram(tags: List<String>): Int = when {
    "kremlin" in tags -> R.drawable.ic_tourist_kremlin
    "monastery" in tags -> R.drawable.ic_tourist_monastery
    "museum" in tags -> R.drawable.ic_tourist_museum
    "view" in tags -> R.drawable.ic_tourist_view
    "walk" in tags -> R.drawable.ic_tourist_walk
    else -> R.drawable.ic_tourist_generic
}

/** components §2.1 RoadSign (Road ahead size). Decorative: the row speaks for it. */
@Composable
fun RoadSign(sign: String, cityName: String, tags: List<String>, modifier: Modifier = Modifier) {
    when (sign) {
        "city" -> Box(
            modifier
                .widthIn(min = 68.dp)
                .width(68.dp)
                .border(DesignTokens.stroke.w2, C.sign.white, RoundedCornerShape(6.dp))
                .padding(DesignTokens.stroke.w2)
                .clip(RoundedCornerShape(DesignTokens.radius.r4))
                .background(C.sign.white)
                .border(DesignTokens.stroke.w3, C.sign.black, RoundedCornerShape(DesignTokens.radius.r4))
                .padding(horizontal = 5.dp, vertical = 8.dp)
                .clearAndSetSemantics {},
            contentAlignment = Alignment.Center,
        ) { CitySignText(cityName.uppercase()) }
        "tourist" -> Box(
            modifier
                .size(DesignTokens.size.touristSign)
                .clip(RoundedCornerShape(DesignTokens.radius.r5))
                .background(C.sign.brown)
                .padding(3.dp)
                .border(DesignTokens.stroke.w2, C.sign.white, RoundedCornerShape(DesignTokens.radius.r3))
                .clearAndSetSemantics {},
            contentAlignment = Alignment.Center,
        ) { Icon(touristPictogram(tags), C.sign.white, 30.dp) }
        else -> Column(
            modifier
                .size(DesignTokens.size.serviceSignW, DesignTokens.size.serviceSignH)
                .clip(RoundedCornerShape(DesignTokens.radius.r4))
                .background(C.sign.blue)
                .padding(5.dp)
                .clearAndSetSemantics {},
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Box(
                Modifier.size(DesignTokens.size.pictogramPlate).clip(RoundedCornerShape(DesignTokens.radius.r2)).background(C.sign.white),
                contentAlignment = Alignment.Center,
            ) { Icon(servicePictogram(sign), C.sign.black, 28.dp) }
            Box(Modifier.size(22.dp, 3.dp).clip(RoundedCornerShape(DesignTokens.radius.r2)).background(C.sign.white))
        }
    }
}

/**
 * Town name on the white city plate: up to 3 lines, never broken inside a word (components §2.1). A word that
 * does not fit the plate width shrinks the text in steps (needed with the fallback font until DES-100).
 */
@Composable
private fun CitySignText(text: String) {
    var scale by remember(text) { mutableFloatStateOf(1f) }
    val base = T.sign.city
    BasicText(
        text = text,
        style = base.copy(color = C.text.onLight, textAlign = TextAlign.Center, fontSize = base.fontSize * scale, lineHeight = base.lineHeight * scale),
        maxLines = 3,
        onTextLayout = { layout ->
            val brokenWord = (0 until layout.lineCount - 1).any { i ->
                val end = layout.getLineEnd(i)
                end in 1 until text.length && !text[end - 1].isWhitespace() && !text[end].isWhitespace()
            }
            if ((brokenWord || layout.hasVisualOverflow) && scale > MIN_CITY_SCALE) scale *= 0.92f
        },
    )
}

private const val MIN_CITY_SCALE = 0.7f

enum class StartSize(val outer: Dp, val face: Dp, val icon: Dp) {
    L(DesignTokens.size.startLOuter, DesignTokens.size.startLFace, DesignTokens.size.startLIcon),
    M(DesignTokens.size.startMOuter, DesignTokens.size.startMFace, DesignTokens.size.startMIcon),
    S(DesignTokens.size.startSOuter, DesignTokens.size.startSFace, DesignTokens.size.startSIcon),
}

/** components §7 StartButton (no pulse in the slice): bezel, face, red ring, power icon, «ПОЕХАЛИ». */
@Composable
fun StartButton(size: StartSize, label: String, enabled: Boolean, cd: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val fg = if (enabled) C.text.primary else C.text.disabled
    Box(
        modifier
            .size(size.outer)
            .clip(CircleShape)
            .background(C.dash.control)
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) {
                contentDescription = cd
                if (!enabled) disabled()
            },
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier
                .size(size.face)
                .clip(CircleShape)
                .background(C.dash.face)
                .border(DesignTokens.size.startRing, if (enabled) C.accent.red else C.dash.outlineDashed, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Canvas(Modifier.size(size.icon)) {
                    val sw = DesignTokens.stroke.icon.ui.toPx()
                    val r = this.size.minDimension / 2 - sw
                    drawArc(
                        fg, startAngle = -50f, sweepAngle = 280f, useCenter = false,
                        topLeft = Offset(center.x - r, center.y - r), size = Size(2 * r, 2 * r),
                        style = Stroke(sw, cap = StrokeCap.Round),
                    )
                    drawLine(fg, Offset(center.x, 0f + sw / 2), Offset(center.x, center.y), sw, StrokeCap.Round)
                }
                Txt(label, if (size == StartSize.S) T.button.startLabelSm else T.button.startLabel, fg, maxLines = 1)
            }
        }
    }
}

/** A step line of the Drive panel (components §8 `StepLine`). */
@Composable
fun StepLine(text: String, done: Boolean, modifier: Modifier = Modifier) {
    androidx.compose.foundation.layout.Row(modifier, verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Canvas(Modifier.padding(top = 4.dp).size(10.dp)) {
            val sw = 2.dp.toPx()
            if (done) {
                drawLine(C.accent.yellow, Offset(size.width * 0.1f, size.height * 0.55f), Offset(size.width * 0.4f, size.height * 0.85f), sw, StrokeCap.Round)
                drawLine(C.accent.yellow, Offset(size.width * 0.4f, size.height * 0.85f), Offset(size.width * 0.95f, size.height * 0.15f), sw, StrokeCap.Round)
            } else {
                drawCircle(C.navi.label, radius = size.minDimension / 2 - sw / 2, style = Stroke(sw))
            }
        }
        Txt(if (done) text else "$text…", T.body.step, if (done) C.text.primary else C.text.secondary)
    }
}

/** Progress bar (components §8). */
@Composable
fun ProgressBar(fraction: Float, modifier: Modifier = Modifier) {
    Box(
        modifier.drawBehind {
            val r = androidx.compose.ui.geometry.CornerRadius(size.height / 2)
            drawRoundRect(C.navi.divider, cornerRadius = r)
            drawRoundRect(C.accent.yellow, size = Size(size.width * fraction.coerceIn(0f, 1f), size.height), cornerRadius = r)
        },
    )
}
