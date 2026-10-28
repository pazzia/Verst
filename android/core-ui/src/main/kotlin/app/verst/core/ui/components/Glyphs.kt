package app.verst.core.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.size

/**
 * UI icons of components §17.4 that DES-102 has not generated as drawables yet (24 × 24 grid, round caps and
 * joins). Drawn from the spec's path data so they match the vectors once they land.
 */
enum class Glyph(val path: String, val strokeWidth: Float = 2f, val filled: Boolean = false) {
    BOOKMARK("M6 3h12v18l-6-4-6 4z"),
    SHARE("M12 15V3M7 8l5-5 5 5M5 13v7h14v-7"),
    CHEVRON_DOWN("M6 9l6 6 6-6"),
    CLOSE("M6 6l12 12M18 6L6 18"),
    CHECK("M5 12.5l4.5 4.5L19 7", 2.4f),
    CHECK_HAND("M5 13c1.5 1 3 2.6 4 4.5 2.5-5 6-9.5 10-12.5"),

    // components §17.5 (Sprint 3)
    WALKER_BODY("M9.5 21l2.5-6.5 2.5 2V21M12 14.5l1-5-3.5 1.5L8 14M13 9.5l2.5 3 3 1"),
    WALKER_HEAD("M15 4.5a2 2 0 1 1-4 0a2 2 0 1 1 4 0z", filled = true),
    MUSEUM("M3 9l9-5 9 5M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"),
    GLASS("M7 4h10l-1.2 9.5a3.8 3.8 0 0 1-7.6 0zM12 17v3M8.5 20h7"),
    MUG("M6 7h9v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1zM15 10h2.5a2 2 0 0 1 0 4H15M8 4c.5 1 1.5 1 2 0s1.5-1 2 0"),
    BINOCULARS("M10.5 15a3.5 3.5 0 1 1-7 0a3.5 3.5 0 1 1 7 0zM20.5 15a3.5 3.5 0 1 1-7 0a3.5 3.5 0 1 1 7 0zM9 7l-2 4.5M15 7l2 4.5M10.5 14h3"),
    LOCATE("M19 12a7 7 0 1 1-14 0a7 7 0 1 1 14 0zM12 2v3M12 19v3M2 12h3M19 12h3"),
    LOCATE_DOT("M14 12a2 2 0 1 1-4 0a2 2 0 1 1 4 0z", filled = true),
    INFO("M21 12a9 9 0 1 1-18 0a9 9 0 1 1 18 0zM12 11v6M12 7.5h.01"),
    GEAR("M12 8.5a3.5 3.5 0 1 1 0 7a3.5 3.5 0 1 1 0-7zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"),
    /** Designer В-6: the stop row «⋯» (the stop menu without a long press). */
    MORE("M7.8 12a1.8 1.8 0 1 1-3.6 0a1.8 1.8 0 1 1 3.6 0zM13.8 12a1.8 1.8 0 1 1-3.6 0a1.8 1.8 0 1 1 3.6 0zM19.8 12a1.8 1.8 0 1 1-3.6 0a1.8 1.8 0 1 1 3.6 0z", filled = true),
    UP_RIGHT("M7 17L17 7M9 7h8v8"),
    RIGHT("M9 6l6 6-6 6", 2.5f),
    SEARCH("M17 10.5a6.5 6.5 0 1 1-13 0a6.5 6.5 0 1 1 13 0zM15.5 15.5L20 20", 2.4f),
    NAVIGATOR("M12 3l7 18-7-4-7 4z"),
    /** S4: the dog cell (filled), the start field «изменить», Яндекс Карты card, hours pills. */
    PAW("M5.8 10a1.7 2.1 0 1 0 3.4 0a1.7 2.1 0 1 0-3.4 0zM14.8 10a1.7 2.1 0 1 0 3.4 0a1.7 2.1 0 1 0-3.4 0zM8.7 6.6a1.6 2 0 1 0 3.2 0a1.6 2 0 1 0-3.2 0zM12.1 6.6a1.6 2 0 1 0 3.2 0a1.6 2 0 1 0-3.2 0zM12 12c-3 0-5 3.2-5 5.2c0 1.6 1.4 2.3 2.7 2c1-.2 1.5-.6 2.3-.6s1.3.4 2.3.6c1.3.3 2.7-.4 2.7-2c0-2-2-5.2-5-5.2z", 1.5f, true),
    PENCIL("M4 20h4L19 9l-4-4L4 16zM14 6l4 4"),
    PIN("M12 21s-6-6.2-6-11a6 6 0 1 1 12 0c0 4.8-6 11-6 11zM14 10a2 2 0 1 1-4 0a2 2 0 1 1 4 0z"),
    CLOCK("M21 12a9 9 0 1 1-18 0a9 9 0 1 1 18 0zM12 7v5l3 2"),
    MINUS("M6 12h12", 2.4f),
    PLUS("M12 6v12M6 12h12", 2.4f),
    PHOTO_NONE("M4 6h16v12H4zM4 15l4-4 4 4 3-3 5 5M3 3l18 18"),
}

/** components §17.5 `walker` (pedestrian zone 5.33): the filled head + the stroked body. */
@Composable
fun WalkerIcon(tint: Color, size: Dp, modifier: Modifier = Modifier) {
    androidx.compose.foundation.layout.Box(modifier.size(size)) {
        GlyphIcon(Glyph.WALKER_BODY, tint, size)
        GlyphIcon(Glyph.WALKER_HEAD, tint, size)
    }
}

/** components §17.5 `locateCross`: the ring and ticks + the filled centre. */
@Composable
fun LocateIcon(tint: Color, size: Dp, modifier: Modifier = Modifier) {
    androidx.compose.foundation.layout.Box(modifier.size(size)) {
        GlyphIcon(Glyph.LOCATE, tint, size)
        GlyphIcon(Glyph.LOCATE_DOT, tint, size)
    }
}

@Composable
fun GlyphIcon(glyph: Glyph, tint: Color, size: Dp, modifier: Modifier = Modifier, filled: Boolean = glyph.filled, strokeWidth: Float = glyph.strokeWidth) {
    val path = remember(glyph) { PathParser().parsePathString(glyph.path).toPath() }
    Canvas(modifier.size(size)) {
        val k = this.size.width / 24f
        scale(k, k, pivot = androidx.compose.ui.geometry.Offset.Zero) {
            if (filled) drawPath(path, tint, style = Fill)
            drawPath(path, tint, style = Stroke(width = strokeWidth, cap = StrokeCap.Round, join = StrokeJoin.Round))
        }
    }
}

/** Default glyph box (the 24 grid at 1:1). */
val GlyphDefault: Dp = 24.dp
