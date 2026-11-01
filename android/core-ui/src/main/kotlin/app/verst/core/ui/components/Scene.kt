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
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.ui.theme.DesignTokens
import app.verst.core.ui.theme.DesignTokens.color as C

/**
 * Sky bands as (top dp, height dp, colour) in the 390-wide reference frame. The skies below are getters, not
 * stored lists: the colours come from the current palette, so a day/night switch repaints them (designer К-2).
 */
data class Band(val top: Float, val height: Float, val color: Color)

/** Sky of 5.1 (S1–S5). */
val FullSky: List<Band> get() = listOf(
    Band(0f, 110f, C.sky.band1), Band(110f, 70f, C.sky.band2), Band(180f, 55f, C.sky.band3),
    Band(235f, 40f, C.sky.band4), Band(275f, 25f, C.sky.band5),
)

/** Sky of 5.4 Drive (S1–S5, S-17): 0–120, 120–190, 190–240, 240–276, 276–300. */
val DriveSky: List<Band> get() = listOf(
    Band(0f, 120f, C.sky.band1), Band(120f, 70f, C.sky.band2), Band(190f, 50f, C.sky.band3),
    Band(240f, 36f, C.sky.band4), Band(276f, 24f, C.sky.band5),
)

/** Sky of the 5.5 strip (S1–S4, S-19): 0–50, 50–84, 84–110, 110–132 (band 2 skipped). */
val RoadSky: List<Band> get() = listOf(Band(0f, 50f, C.sky.band1), Band(50f, 34f, C.sky.band3), Band(84f, 26f, C.sky.band4), Band(110f, 22f, C.sky.band5))

/** Sky of the 5.2 strip (S1–S4): 0–46, 46–76, 76–94, 94–104; ground from 104. */
val NavigatorSky: List<Band> get() = listOf(Band(0f, 46f, C.sky.band1), Band(46f, 30f, C.sky.band3), Band(76f, 18f, C.sky.band4), Band(94f, 10f, C.sky.band5))

/**
 * One row of components §9.1: the road plane (W wide, L long) rotated θ about its near edge, seen with
 * perspective P from the top centre of its container (top, H). All values are dp of the 390-wide frame.
 */
data class RoadSpec(
    val top: Float, val h: Float, val p: Float, val thetaDeg: Float, val w: Float, val l: Float,
    val edge: Float, val lane: Float, val dash: Float = 70f, val period: Float = 160f,
)

val WindshieldRoad = RoadSpec(300f, 240f, 210f, 76f, 230f, 1000f, 6f, 8f)
val DriveRoad = RoadSpec(300f, 260f, 210f, 76f, 240f, 1000f, 6f, 8f)
val NavigatorRoad = RoadSpec(104f, 46f, 120f, 80f, 160f, 600f, 4f, 6f)
val ExitRoad = RoadSpec(240f, 190f, 200f, 76f, 230f, 900f, 6f, 8f)

/**
 * components §9.1 closed form: s = P / (P + d·sinθ), x' = cx + x·s, y' = top + (H − d·cosθ)·s; every element is
 * a quad of 4 projected corners (asphalt, both edge lines, lane dashes measured from the far end, phase 0),
 * clipped at the container top. [kx] / [ky] are px per reference dp horizontally / vertically.
 */
fun DrawScope.drawRoad3D(
    r: RoadSpec,
    kx: Float,
    ky: Float,
    phase: Float = 0f,
    asphalt: Color = C.scene.road,
    edges: Color = C.scene.roadEdge,
    laneColor: Color = C.scene.roadEdge,
) {
    val th = Math.toRadians(r.thetaDeg.toDouble())
    val sinT = kotlin.math.sin(th).toFloat()
    val cosT = kotlin.math.cos(th).toFloat()
    val cx = size.width / 2
    fun pt(x: Float, d: Float): Offset {
        val sc = r.p / (r.p + d * sinT)
        return Offset(cx + x * sc * kx, (r.top + (r.h - d * cosT) * sc) * ky)
    }
    fun quad(x0: Float, x1: Float, d0: Float, d1: Float, color: Color) {
        val a = pt(x0, d0)
        val b = pt(x1, d0)
        val c = pt(x1, d1)
        val e = pt(x0, d1)
        drawPath(Path().apply { moveTo(a.x, a.y); lineTo(b.x, b.y); lineTo(c.x, c.y); lineTo(e.x, e.y); close() }, color)
    }
    clipRect(top = r.top * ky, bottom = (r.top + r.h) * ky) {
        val hw = r.w / 2
        quad(-hw + r.edge, hw - r.edge, 0f, r.l, asphalt)
        quad(-hw, -hw + r.edge, 0f, r.l, edges)
        quad(hw - r.edge, hw, 0f, r.l, edges)
        // Dash k covers u ∈ [phase + k·period − period, …]: start one period early so the far end is never empty.
        var u = (phase % r.period) - r.period
        while (u < r.l) {
            val u0 = maxOf(u, 0f)
            val u1 = minOf(u + r.dash, r.l)
            if (u1 > u0) quad(-r.lane / 2, r.lane / 2, r.l - u0, r.l - u1, laneColor)
            u += r.period
        }
    }
}

/**
 * Static windshield scene (components §9, no lane motion yet): sky bands, sun, optional hills, ground, the
 * projected road (§9.1), optional gantry legs (§9.3), roof liner and A-pillars. Coordinates are dp of the
 * 390-wide frame; x scales with the width, y by k = min(1, height / `refHeight`) on short windows (5.1 §1).
 * Decorative: no semantics.
 */
@Composable
fun WindshieldScene(
    height: Dp,
    modifier: Modifier = Modifier,
    hills: Boolean = true,
    sunX: Float = 236f,
    refHeight: Float = 540f,
    sky: List<Band> = FullSky,
    road: RoadSpec = WindshieldRoad,
    sunCenterY: Float = 300f,
    gantry: Boolean = false,
    /** N-01: leg top in dp of the screen (min(286, sign plate bottom − 4)); legs end at y 386 of the frame. */
    gantryTop: Float = 286f,
    laneCycleMs: Int = DesignTokens.motion.lane.idle.durationMs,
    posts: PostSpec? = WindshieldPosts,
    overlay: Boolean = false,
) {
    val clock = sceneClock(overlay)
    val reduced = LocalReducedMotion.current
    Canvas(modifier.fillMaxWidth().height(height).clearAndSetSemantics {}) {
        val t = clock.value
        val k = size.width / 390.dp.toPx()
        val dp = 1.dp.toPx()
        val dy = dp * minOf(1f, size.height / (refHeight * dp))
        val horizon = road.top * dy
        for (b in sky) drawRect(b.color, Offset(0f, b.top * dy), Size(size.width, b.height * dy + 1f))
        drawCircle(C.scene.sun, radius = 34f * dy, center = Offset((sunX + 34f) * k * dp, sunCenterY * dy))
        if (hills) drawHills(k * dp, dy)
        drawRect(C.scene.groundDay, Offset(0f, horizon), Size(size.width, size.height - horizon))
        drawRoad3D(road, k * dp, dy, phase = Phases.lane(t, laneCycleMs))
        if (posts != null && !reduced) drawPosts(posts, t, k * dp, dy)
        if (gantry) {
            // §9.3: two legs 8 × 100 at x 34 and W − 42, y 286, under the sign.
            val top = minOf(gantryTop * dp, 286f * dy)
            val h = 386f * dy - top
            drawRect(C.interior.pole, Offset(34f * dp, top), Size(8f * dp, h))
            drawRect(C.interior.pole, Offset(size.width - 42f * dp, top), Size(8f * dp, h))
        }
        drawInterior(dp, k)
    }
}

/** §9.2 roadside posts: start boxes, travel, scale and timing (two posts, mirrored, offset by half a cycle). */
data class PostSpec(
    val rightX: Float, val leftX: Float, val y: Float, val dx: Float, val dy: Float,
    val fromScale: Float, val toScale: Float, val durationMs: Int, val offsetMs: Int, val easing: androidx.compose.animation.core.Easing,
)

val WindshieldPosts = DesignTokens.motion.post.idle.let {
    PostSpec(236f, 148f, 302f, it.dxDp.value, it.dyDp.value, it.fromScale, it.toScale, it.durationMs, it.offsetMs, it.easing)
}
val DrivePosts = DesignTokens.motion.post.drive.let {
    PostSpec(212f, 172f, 300f, it.dxDp.value, it.dyDp.value, it.fromScale, it.toScale, it.durationMs, it.offsetMs, it.easing)
}

private fun DrawScope.drawPosts(p: PostSpec, t: Long, kx: Float, ky: Float) {
    for ((x0, sign, off) in listOf(Triple(p.rightX, 1f, 0), Triple(p.leftX, -1f, p.offsetMs))) {
        val prog = Phases.cycle(t, p.durationMs, off)
        val e = p.easing.transform(prog)
        val alpha = p.easing.transform(minOf(1f, prog / 0.1f))
        val sc = p.fromScale + (p.toScale - p.fromScale) * e
        val cx = (x0 + 3f + sign * p.dx * e) * kx
        val cy = (p.y + 9f + p.dy * e) * ky
        val w = 6f * sc * kx
        val h = 18f * sc * ky
        drawRect(C.scene.roadEdge.copy(alpha = alpha), Offset(cx - w / 2, cy - h / 2), Size(w, h))
        drawRect(C.dash.base.copy(alpha = alpha), Offset(cx - w / 2, cy - h / 2), Size(w, 5f * sc * ky))
    }
}

/**
 * 5.7 night scene (§2.1): night sky and two bands, twinkling stars, crescent moon, town lights, night ground and
 * road (`lane.exit`), headlight, sign pole, liner and pillars. Reference frame 390 × 430, y scaled on short windows.
 */
@Composable
fun ExitScene(height: Dp, modifier: Modifier = Modifier, overlay: Boolean = false) {
    val clock = sceneClock(overlay)
    val reduced = LocalReducedMotion.current
    Canvas(modifier.fillMaxWidth().height(height).clearAndSetSemantics {}) {
        val t = clock.value
        val k = size.width / 390.dp.toPx()
        val dp = 1.dp.toPx()
        val dy = dp * minOf(1f, size.height / (430f * dp))
        val kx = k * dp
        drawRect(C.sky.night, Offset.Zero, Size(size.width, 150f * dy + 1f))
        drawRect(C.sky.band1, Offset(0f, 150f * dy), Size(size.width, 60f * dy + 1f))
        drawRect(C.sky.band2, Offset(0f, 210f * dy), Size(size.width, 30f * dy + 1f))
        for ((i, st) in listOf(Triple(60f, 40f, 3f), Triple(150f, 80f, 2f), Triple(300f, 30f, 3f)).withIndex()) {
            val a = if (reduced) 1f else Phases.twinkle(t, i * DesignTokens.motion.twinkle.staggerMs)
            drawCircle(C.scene.star.copy(alpha = a), st.third / 2 * dp, Offset((st.first + st.third / 2) * kx, (st.second + st.third / 2) * dy))
        }
        drawCircle(C.scene.moon, 20f * dp, Offset(90f * kx, 66f * dy))
        drawCircle(C.sky.night, 20f * dp, Offset(102f * kx, 60f * dy))
        for ((x, d) in listOf(210f to 3f, 223f to 2f, 235f to 3f, 248f to 2f, 260f to 3f)) {
            drawCircle(C.scene.sun, d / 2 * dp, Offset((x + d / 2) * kx, (232f + d / 2) * dy))
        }
        drawRect(C.scene.groundNight, Offset(0f, 240f * dy), Size(size.width, size.height - 240f * dy))
        drawRoad3D(ExitRoad, kx, dy, Phases.lane(t, DesignTokens.motion.lane.exit.durationMs), C.scene.roadNight, C.scene.roadEdgeNight, C.scene.roadEdge)
        drawPath(
            Path().apply { moveTo(175f * kx, 300f * dy); lineTo(215f * kx, 300f * dy); lineTo(320f * kx, 430f * dy); lineTo(70f * kx, 430f * dy); close() },
            C.scene.headlight,
        )
        drawRect(C.interior.pole, Offset(314f * kx, 196f * dy), Size(6f * dp, 100f * dy))
        drawInterior(dp, k)
    }
}

/** §9 item 3 (S-05): the hills polyline, translated to y 272, x scaled by width / 390. */
private fun DrawScope.drawHills(kx: Float, dy: Float) {
    val pts = listOf(0f to 28f, 40f to 18f, 80f to 24f, 130f to 12f, 170f to 22f, 200f to 16f, 250f to 26f, 300f to 14f, 350f to 24f, 390f to 18f)
    val p = Path().apply {
        moveTo(0f, (272f + 28f) * dy)
        for ((x, y) in pts) lineTo(x * kx, (272f + y) * dy)
        lineTo(390f * kx, (272f + 40f) * dy)
        lineTo(0f, (272f + 40f) * dy)
        close()
    }
    drawPath(p, C.sky.hills)
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

/**
 * A short sky strip with the roof liner (5.2, 5.3, 5.5 headers): the screen's [bands] (dp from the top), then
 * optional ground from [groundTop] with the projected [road].
 */
@Composable
fun SkyStrip(
    height: Dp,
    modifier: Modifier = Modifier,
    bands: List<Band> = RoadSky,
    groundTop: Float? = null,
    road: RoadSpec? = null,
    laneCycleMs: Int = DesignTokens.motion.lane.navi.durationMs,
    content: @Composable BoxScope.() -> Unit = {},
) {
    val clock = sceneClock()
    Box(
        modifier.fillMaxWidth().height(height).drawBehind {
            val dp = 1.dp.toPx()
            val t = clock.value
            for (b in bands) drawRect(b.color, Offset(0f, b.top * dp), Size(size.width, b.height * dp + 1f))
            if (groundTop != null) {
                drawRect(C.scene.groundDay, Offset(0f, groundTop * dp), Size(size.width, size.height - groundTop * dp))
                if (road != null) drawRoad3D(road, size.width / 390f, dp, Phases.lane(t, laneCycleMs))
            }
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

/**
 * components §10 (S-03): `M0 (T+R) A(W/2) R 0 0 1 (W/2) T A(W/2) R 0 0 1 W (T+R) V bottom H0 Z` — the top half of
 * an ellipse of half-width W/2 and half-height R, crest at T (the modifier's top). The rim is the same path 2 dp
 * higher in `color.dash.control`; caps (Instruments, Road ahead) have no rim (S-30).
 */
fun Modifier.dashboardSurface(curve: Dp = 34.dp, rim: Boolean = true): Modifier = drawBehind {
    val c = curve.toPx()
    fun shape(dy: Float) = Path().apply {
        moveTo(0f, c + dy)
        arcTo(Rect(0f, dy, size.width, dy + 2 * c), 180f, 180f, false)
        lineTo(size.width, size.height); lineTo(0f, size.height); close()
    }
    if (rim) drawPath(shape(-2.dp.toPx()), C.dash.control)
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
