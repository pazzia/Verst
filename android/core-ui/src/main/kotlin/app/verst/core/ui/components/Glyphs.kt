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
