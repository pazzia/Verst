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
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.graphicsLayer
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
    "monastery" in tags || "church" in tags || "cathedral" in tags -> R.drawable.ic_tourist_monastery
    "museum" in tags || "theatre" in tags || "theater" in tags || "gallery" in tags -> R.drawable.ic_tourist_museum
    "view" in tags -> R.drawable.ic_tourist_view
    "walk" in tags -> R.drawable.ic_tourist_walk
    else -> R.drawable.ic_tourist_generic
}

/** CEO 29.10 (trips abroad): the `sign` the app gives a `kind: "border"` stop (the engine sends `city`). */
const val BORDER_SIGN = "border"

/** components §2.1 RoadSign (Road ahead size). Decorative: the row speaks for it. */
@Composable
fun RoadSign(sign: String, cityName: String, tags: List<String>, modifier: Modifier = Modifier) {
    when (sign) {
        "city" -> CityPlate(cityName, modifier)
        BORDER_SIGN -> BorderSign(modifier)
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
 * CEO 29.10 (trips abroad): the «граница» sign in the city plate's chrome (white outline, white face, black border;
 * the same minimum width), a barrier pictogram — black post, a bar striped `accent.red` / `sign.white` — over
 * «ГРАНИЦА» in the city-sign type. Colours, strokes and type are the sign tokens only.
 */
@Composable
private fun BorderSign(modifier: Modifier) {
    val label = androidx.compose.ui.res.stringResource(R.string.sign_border)
    Column(
        modifier
            .width(CITY_MIN_W)
            .border(DesignTokens.stroke.w2, C.sign.white, RoundedCornerShape(DesignTokens.radius.r6))
            .padding(DesignTokens.stroke.w2)
            .clip(RoundedCornerShape(DesignTokens.radius.r4))
            .background(C.sign.white)
            .border(DesignTokens.stroke.w3, C.sign.black, RoundedCornerShape(DesignTokens.radius.r4))
            .padding(horizontal = 5.dp, vertical = 7.dp)
            .clearAndSetSemantics {},
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Canvas(Modifier.size(44.dp, 20.dp)) {
            val d = 1.dp.toPx()
            // the post and its foot
            drawRect(C.sign.black, Offset(3 * d, 4 * d), Size(4 * d, 15 * d))
            drawRect(C.sign.black, Offset(0f, 18 * d), Size(10 * d, 2 * d))
            // the bar: red and white stripes in a black outline, hinged on the post
            val top = 5 * d
            val h = 5 * d
            val x0 = 7 * d
            val x1 = size.width - d
            var x = x0
            var i = 0
            while (x < x1) {
                val w = minOf(6 * d, x1 - x)
                drawRect(if (i % 2 == 0) C.accent.red else C.sign.white, Offset(x, top), Size(w, h))
                x += 6 * d
                i++
            }
            drawRect(C.sign.black, Offset(x0, top), Size(x1 - x0, h), style = Stroke(d))
            drawCircle(C.sign.black, 2.5f * d, Offset(5 * d, top + h / 2))
        }
        BasicText(
            text = label,
            style = T.sign.city.copy(color = C.text.onLight, textAlign = TextAlign.Center),
            maxLines = 1,
        )
    }
}

/** Chrome around the city text: outline 2 + border padding 2 (each side) + text padding 5 (each side). */
private val CITY_CHROME = 14.dp
private val CITY_MIN_W = 68.dp
private val CITY_MAX_W = 120.dp
private const val CITY_MIN_SCALE = 0.8f

/**
 * components §2.1 city plate (S3-QA P1-04): the town name in uppercase, up to 3 lines, broken **only** at a space
 * or after a hyphen (the hyphen stays at the line end: «САНКТ-» / «ПЕТЕРБУРГ»), never inside a word. If the
 * longest word does not fit the 68 dp plate, the plate grows up to 120 dp, then the text scales down to 80 %.
 */
@Composable
private fun CityPlate(cityName: String, modifier: Modifier) {
    val text = cityName.uppercase()
    val base = T.sign.city
    val measurer = androidx.compose.ui.text.rememberTextMeasurer()
    val density = androidx.compose.ui.platform.LocalDensity.current
    // the unbreakable pieces: split at spaces, and after each hyphen (the hyphen belongs to the left piece)
    val words = remember(text) { text.split(' ').flatMap { w -> Regex("[^-]+-?|-").findAll(w).map { it.value }.toList() }.filter { it.isNotBlank() } }
    val longest = remember(text, base) {
        words.maxOfOrNull { measurer.measure(it, base, maxLines = 1, softWrap = false).size.width } ?: 0
    }
    val longestDp = with(density) { longest.toDp() }
    val plateW = (longestDp + CITY_CHROME + 1.dp).coerceIn(CITY_MIN_W, CITY_MAX_W)
    val scale = if (longestDp + CITY_CHROME + 1.dp <= CITY_MAX_W) 1f
    else ((CITY_MAX_W - CITY_CHROME - 1.dp) / longestDp).coerceAtLeast(CITY_MIN_SCALE)
    // explicit break opportunities after hyphens (zero-width space); no hyphenation inside words
    val shown = text.replace("-", "-\u200B")
    Box(
        modifier
            .width(plateW)
            .border(DesignTokens.stroke.w2, C.sign.white, RoundedCornerShape(6.dp))
            .padding(DesignTokens.stroke.w2)
            .clip(RoundedCornerShape(DesignTokens.radius.r4))
            .background(C.sign.white)
            .border(DesignTokens.stroke.w3, C.sign.black, RoundedCornerShape(DesignTokens.radius.r4))
            .padding(horizontal = 5.dp, vertical = 8.dp)
            .clearAndSetSemantics {},
        contentAlignment = Alignment.Center,
    ) {
        BasicText(
            text = shown,
            style = base.copy(
                color = C.text.onLight, textAlign = TextAlign.Center,
                fontSize = base.fontSize * scale, lineHeight = base.lineHeight * scale,
                lineBreak = androidx.compose.ui.text.style.LineBreak.Heading,
                hyphens = androidx.compose.ui.text.style.Hyphens.None,
            ),
            maxLines = 3,
        )
    }
}

/** The pieces a city name may break into (tests): «САНКТ-ПЕТЕРБУРГ» → «САНКТ-», «ПЕТЕРБУРГ». */
fun cityBreakPieces(name: String): List<String> =
    name.uppercase().split(' ').flatMap { w -> Regex("[^-]+-?|-").findAll(w).map { it.value }.toList() }.filter { it.isNotBlank() }


enum class StartSize(val outer: Dp, val face: Dp, val icon: Dp) {
    L(DesignTokens.size.startLOuter, DesignTokens.size.startLFace, DesignTokens.size.startLIcon),
    M(DesignTokens.size.startMOuter, DesignTokens.size.startMFace, DesignTokens.size.startMIcon),
    S(DesignTokens.size.startSOuter, DesignTokens.size.startSFace, DesignTokens.size.startSIcon),
}

/** components §7 StartButton (no pulse in the slice): bezel, face, red ring, power icon, «ПОЕХАЛИ». */
@Composable
fun StartButton(size: StartSize, label: String, enabled: Boolean, cd: String, onClick: () -> Unit, modifier: Modifier = Modifier, walker: Boolean = false, loading: Boolean = false) {
    val fg = if (enabled) C.text.primary else C.text.disabled
    // motion.startPulse (enabled only): a red ring spreading 0 → 16 dp (14 on S), α 0.55 → 0, 1800 ms easeOut;
    // motion.startPress: face + label 0.96 while pressed.
    val pulseClock = sceneClock(overlay = !enabled)
    val interaction = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val press by animateFloatAsState(if (pressed) DesignTokens.motion.startPress.toScale else 1f, tween(DesignTokens.motion.startPress.durationMs), label = "press")
    val pm = DesignTokens.motion.startPulse
    Box(
        modifier
            .size(size.outer)
            .drawBehind {
                if (!enabled) return@drawBehind
                val t = pulseClock.value
                if (t == 0L) return@drawBehind
                val p = pm.easing.transform(Phases.cycle(t, pm.durationMs))
                val spread = (if (size == StartSize.S) pm.toSpreadSmDp else pm.toSpreadDp).toPx() * p
                drawCircle(C.accent.redPulse.copy(alpha = pm.fromAlpha * (1 - p)), this.size.minDimension / 2 + spread)
            }
            .clip(CircleShape)
            .background(C.dash.control)
            .clickable(interaction, indication = null, enabled = enabled, role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) {
                contentDescription = cd
                if (!enabled) disabled()
            },
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier
                .graphicsLayer { scaleX = press; scaleY = press }
                .size(size.face)
                .clip(CircleShape)
                .background(C.dash.face)
                .border(DesignTokens.size.startRing, if (enabled) C.accent.red else C.dash.outlineDashed, CircleShape)
                .drawBehind {
                    if (loading) {
                        val w = DesignTokens.size.startRing.toPx()
                        drawArc(C.accent.yellowText, -90f, 100f, false, topLeft = Offset(w / 2, w / 2), size = Size(this.size.width - w, this.size.height - w), style = Stroke(w, cap = StrokeCap.Round))
                    }
                },
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                // 5.10 C2: the walk variant carries `walker` and «ПОШЛИ»; while building, a static loading arc
                if (walker) {
                    WalkerIcon(fg, size.icon)
                } else {
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
                drawLine(C.accent.yellowText, Offset(size.width * 0.1f, size.height * 0.55f), Offset(size.width * 0.4f, size.height * 0.85f), sw, StrokeCap.Round)
                drawLine(C.accent.yellowText, Offset(size.width * 0.4f, size.height * 0.85f), Offset(size.width * 0.95f, size.height * 0.15f), sw, StrokeCap.Round)
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
            drawRoundRect(C.accent.yellowText, size = Size(size.width * fraction.coerceIn(0f, 1f), size.height), cornerRadius = r)
        },
    )
}
