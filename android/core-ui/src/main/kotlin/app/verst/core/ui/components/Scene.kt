package app.verst.core.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.ui.theme.DesignTokens
import app.verst.core.ui.theme.DesignTokens.color as C

/** Sky bands as (top dp, height dp, colour) in the 390-wide reference frame. */
data class Band(val top: Float, val height: Float, val color: Color)

/** Sky of 5.1 / 5.4 (S1–S5). */
val FullSky = listOf(
    Band(0f, 110f, C.sky.band1), Band(110f, 70f, C.sky.band2), Band(180f, 55f, C.sky.band3),
    Band(235f, 40f, C.sky.band4), Band(275f, 25f, C.sky.band5),
)

/**
 * Static windshield scene (components §9, DEV-SLICE: no lane motion yet): sky bands, sun, optional hills,
 * ground, the perspective road with edge lines and lane dashes, roof liner and A-pillars. `horizon` and
 * `bottom` are in dp of the 390-wide frame; x scales with the width. Decorative: no semantics.
 */
@Composable
fun WindshieldScene(height: Dp, modifier: Modifier = Modifier, hills: Boolean = true, sunX: Float = 236f) {
    Canvas(modifier.fillMaxWidth().height(height).clearAndSetSemantics {}) {
        val k = size.width / 390.dp.toPx()
        val dp = 1.dp.toPx()
        val horizon = 300f * dp
        for (b in FullSky) drawRect(b.color, Offset(0f, b.top * dp), Size(size.width, b.height * dp))
        drawCircle(C.scene.sun, radius = 34f * dp, center = Offset((sunX + 34f) * k * dp, 300f * dp))
        if (hills) drawHills(k, dp)
        drawRect(C.scene.groundDay, Offset(0f, horizon), Size(size.width, size.height - horizon))
        drawRoad(horizon, size.height, nearHalf = 115f * dp * k, farHalf = 6f * dp * k, dp = dp)
        drawInterior(dp, k)
    }
}

private fun DrawScope.drawHills(k: Float, dp: Float) {
    val p = Path().apply {
        moveTo(0f, 300f * dp)
        lineTo(0f, 286f * dp)
        cubicTo(60f * k * dp, 272f * dp, 110f * k * dp, 280f * dp, 160f * k * dp, 288f * dp)
        cubicTo(220f * k * dp, 276f * dp, 300f * k * dp, 272f * dp, 390f * k * dp, 284f * dp)
        lineTo(size.width, 300f * dp)
        close()
    }
    drawPath(p, C.sky.hills)
}

private fun DrawScope.drawRoad(top: Float, bottom: Float, nearHalf: Float, farHalf: Float, dp: Float) {
    val cx = size.width / 2
    val road = Path().apply {
        moveTo(cx - farHalf, top)
        lineTo(cx + farHalf, top)
        lineTo(cx + nearHalf, bottom)
        lineTo(cx - nearHalf, bottom)
        close()
    }
    drawPath(road, C.scene.road)
    val edge = 4f * dp
    drawLine(C.scene.roadEdge, Offset(cx - farHalf + 1f, top), Offset(cx - nearHalf + edge, bottom), strokeWidth = edge * 0.8f)
    drawLine(C.scene.roadEdge, Offset(cx + farHalf - 1f, top), Offset(cx + nearHalf - edge, bottom), strokeWidth = edge * 0.8f)
    // Lane dashes: perspective-shortened toward the horizon.
    val h = bottom - top
    var t = 0.04f
    while (t < 1f) {
        val t2 = minOf(1f, t + 0.06f + 0.14f * t)
        val w1 = 1.5f * dp + 6f * dp * t
        val w2 = 1.5f * dp + 6f * dp * t2
        val y1 = top + h * t * t
        val y2 = top + h * t2 * t2
        val dash = Path().apply {
            moveTo(cx - w1 / 2, y1); lineTo(cx + w1 / 2, y1); lineTo(cx + w2 / 2, y2); lineTo(cx - w2 / 2, y2); close()
        }
        drawPath(dash, C.scene.roadEdge)
        t = t2 + 0.05f + 0.12f * t2
    }
}

private fun DrawScope.drawInterior(dp: Float, k: Float) {
    val liner = Path().apply {
        moveTo(0f, 0f); lineTo(size.width, 0f); lineTo(size.width, 16f * dp)
        quadraticTo(size.width / 2, 2f * dp, 0f, 16f * dp); close()
    }
    drawPath(liner, C.interior.liner)
    val h = size.height
    drawPath(Path().apply { moveTo(0f, 0f); lineTo(24f * dp * k, 0f); lineTo(9.6f * dp * k, h); lineTo(0f, h); close() }, C.interior.liner)
    drawPath(
        Path().apply {
            moveTo(size.width, 0f); lineTo(size.width - 24f * dp * k, 0f); lineTo(size.width - 9.6f * dp * k, h); lineTo(size.width, h); close()
        },
        C.interior.liner,
    )
}

/** A short sky strip with the roof liner (5.2, 5.3, 5.5 headers). */
@Composable
fun SkyStrip(height: Dp, modifier: Modifier = Modifier, ground: Boolean = false, content: @Composable BoxScope.() -> Unit = {}) {
    Box(
        modifier.fillMaxWidth().height(height).drawBehind {
            val n = if (ground) 4 else 3
            val skyH = if (ground) size.height * 0.7f else size.height
            val colors = listOf(C.sky.band1, C.sky.band3, C.sky.band4, C.sky.band5).take(n)
            val weights = if (ground) listOf(0.45f, 0.25f, 0.18f, 0.12f) else listOf(0.45f, 0.3f, 0.25f)
            var y = 0f
            for ((i, c) in colors.withIndex()) {
                val bh = skyH * weights[i]
                drawRect(c, Offset(0f, y), Size(size.width, bh + 1f))
                y += bh
            }
            if (ground) drawRect(C.scene.groundDay, Offset(0f, skyH), Size(size.width, size.height - skyH))
            val dp = 1.dp.toPx()
            drawPath(
                Path().apply {
                    moveTo(0f, 0f); lineTo(size.width, 0f); lineTo(size.width, 14f * dp)
                    quadraticTo(size.width / 2, 2f * dp, 0f, 14f * dp); close()
                },
                C.interior.liner,
            )
        },
        content = content,
    )
}

/** components §10: dashboard surface with its curved top edge and rim. */
fun Modifier.dashboardSurface(curve: Dp = 34.dp): Modifier = drawBehind {
    val c = curve.toPx()
    val rim = 2.dp.toPx()
    fun shape(dy: Float) = Path().apply {
        moveTo(0f, c + dy)
        quadraticTo(size.width / 2, -c * 0.15f + dy, size.width, c + dy)
        lineTo(size.width, size.height); lineTo(0f, size.height); close()
    }
    drawPath(shape(-rim), C.dash.control)
    drawPath(shape(0f), C.dash.raised)
}

/** components §1: the GOST-blue plate with the white inner border. */
fun Modifier.overheadPlate(outer: Dp = 4.dp, radius: Dp = 9.dp, innerRadius: Dp = 6.dp): Modifier = drawBehind {
    val o = outer.toPx()
    val sw = 2.dp.toPx()
    drawRoundRect(DesignTokens.shadow.signLg.color, Offset(0f, 6.dp.toPx()), size, CornerRadius(radius.toPx()))
    drawRoundRect(C.sign.blue, Offset.Zero, size, CornerRadius(radius.toPx()))
    drawRoundRect(
        C.sign.white, Offset(o + sw / 2, o + sw / 2), Size(size.width - 2 * o - sw, size.height - 2 * o - sw),
        CornerRadius(innerRadius.toPx()), style = Stroke(sw),
    )
}

/** components §8: navigator bezel + screen. */
fun Modifier.naviPanel(bezel: Dp = 6.dp, radius: Dp = 16.dp): Modifier = drawBehind {
    val b = bezel.toPx()
    drawRoundRect(C.dash.control, Offset.Zero, size, CornerRadius(radius.toPx()))
    drawRoundRect(C.navi.screen, Offset(b, b), Size(size.width - 2 * b, size.height - 2 * b), CornerRadius(radius.toPx() - b))
}
