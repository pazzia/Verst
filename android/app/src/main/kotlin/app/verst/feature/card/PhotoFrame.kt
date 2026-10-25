package app.verst.feature.card

import android.graphics.drawable.BitmapDrawable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.BiasAlignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.painter.Painter
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import coil.compose.AsyncImagePainter
import coil.compose.rememberAsyncImagePainter
import coil.request.ImageRequest
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** components §18.1: the 7 placeholder vignettes (engine `poiKind` → illustration). */
enum class Placeholder { MUSEUM, CHURCH, PARK, MONUMENT, VIEW, BAR, CITY }

fun placeholderFor(poiKind: String?, kind: String? = null): Placeholder = when (poiKind ?: kind) {
    "museum", "gallery" -> Placeholder.MUSEUM
    "church", "monastery", "kremlin", "cathedral" -> Placeholder.CHURCH
    "park", "garden" -> Placeholder.PARK
    "monument", "memorial", "square" -> Placeholder.MONUMENT
    "viewpoint", "view", "embankment" -> Placeholder.VIEW
    "bar", "ryumochnaya", "pub", "craft", "beer" -> Placeholder.BAR
    else -> Placeholder.CITY
}

/** What the frame shows (5.9 §4). The frame has the same size in every state. */
sealed interface PhotoState {
    data object Loading : PhotoState
    /** [contain] = tiny, extreme aspect or transparent: fit on the mat instead of the crop. */
    data class Loaded(val painter: Painter, val contain: Boolean, val portrait: Boolean) : PhotoState
    data object None : PhotoState
    data object Error : PhotoState
    data object Offline : PhotoState
}

/** components §18 decision, from the decoded size before the first draw. */
fun containFor(w: Int, h: Int, hasAlpha: Boolean): Boolean {
    if (w <= 0 || h <= 0) return true
    val aspect = w.toFloat() / h
    return w < 320 || h < 200 || aspect < 0.45f || aspect > 3.2f || hasAlpha
}

/** True when the bitmap really has see-through pixels: a 9 × 9 grid plus the edges is sampled (cheap). */
internal fun transparent(b: android.graphics.Bitmap): Boolean {
    if (!b.hasAlpha()) return false
    val w = b.width
    val h = b.height
    if (w <= 0 || h <= 0) return false
    for (i in 0..8) for (j in 0..8) {
        val x = ((w - 1) * i) / 8
        val y = ((h - 1) * j) / 8
        if (android.graphics.Color.alpha(b.getPixel(x, y)) < 250) return true
    }
    return false
}

/**
 * components §18 `PhotoFrame`: fixed 3 : 2, radius 12, mat fill, hairline over the image; crop (portrait keeps the
 * top, bias −0.35) or contain on the mat; the credit line on the scrim (crop) or under the frame (contain /
 * placeholder hidden); the «ФОТО РАЙОНА» plate for hotel areas. Coil loads [url] with the app's disk cache.
 */
@Composable
fun PhotoFrame(
    url: String?,
    placeholder: Placeholder,
    credit: String?,
    area: Boolean,
    offline: Boolean,
    contentDescription: String,
    modifier: Modifier = Modifier,
    onCredit: (() -> Unit)? = null,
    /** true once an image is on screen (S3-QA P1-05: the hotel note depends on it). */
    onShown: (Boolean) -> Unit = {},
) {
    if (url == null) {
        androidx.compose.runtime.LaunchedEffect(Unit) { onShown(false) }
        PhotoFrameContent(PhotoState.None, placeholder, credit, area, contentDescription, modifier, onCredit)
        return
    }
    val context = androidx.compose.ui.platform.LocalContext.current
    // offline: the 64 MB disk cache only (no network attempt), then «Фото загрузится, когда будет интернет»
    val painter = rememberAsyncImagePainter(
        ImageRequest.Builder(context).data(url).allowHardware(false)
            // explicit size: the painter is drawn only once loaded, so Coil must not wait for a draw size
            .size(1200, 800)
            .networkCachePolicy(if (offline) coil.request.CachePolicy.DISABLED else coil.request.CachePolicy.ENABLED)
            .build(),
    )
    val state = when (val s = painter.state) {
        is AsyncImagePainter.State.Success -> {
            val d = s.result.drawable
            val bmp = (d as? BitmapDrawable)?.bitmap
            val w = d.intrinsicWidth
            val h = d.intrinsicHeight
            // an alpha channel is not transparency: opaque PNG collages crop like photos (S3-R4, real catalogue)
            PhotoState.Loaded(painter, containFor(w, h, bmp?.let { transparent(it) } == true), h.toFloat() / w.coerceAtLeast(1) > 1.05f)
        }
        is AsyncImagePainter.State.Error -> if (offline) PhotoState.Offline else PhotoState.Error
        else -> PhotoState.Loading
    }
    val shown = state is PhotoState.Loaded
    androidx.compose.runtime.LaunchedEffect(shown) { onShown(shown) }
    PhotoFrameContent(state, placeholder, credit, area, contentDescription, modifier, onCredit)
}

/** The stateless frame (Robolectric screenshots pass a fake painter). */
@Composable
fun PhotoFrameContent(
    state: PhotoState,
    placeholder: Placeholder,
    credit: String?,
    area: Boolean,
    contentDescription: String,
    modifier: Modifier = Modifier,
    onCredit: (() -> Unit)? = null,
) {
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    val loaded = state as? PhotoState.Loaded
    val crop = loaded != null && !loaded.contain
    val reduced = LocalReducedMotion.current
    val fade by animateFloatAsState(
        if (loaded != null) 1f else 0f,
        if (reduced) snap() else tween(DesignTokens.motion.photoFadeIn.durationMs, easing = DesignTokens.motion.photoFadeIn.easing),
        label = "photoFadeIn",
    )
    Column(modifier.fillMaxWidth()) {
        Box(
            Modifier.fillMaxWidth().aspectRatio(3f / 2f).clip(shape).background(C.photo.mat)
                .semantics { this.contentDescription = contentDescription }
                .testTag(
                    when (state) {
                        is PhotoState.Loaded -> "photo.loaded"
                        PhotoState.Loading -> "photo.loading"
                        PhotoState.None -> "photo.none"
                        PhotoState.Error -> "photo.error"
                        PhotoState.Offline -> "photo.offline"
                    },
                ),
        ) {
            if (loaded == null || fade < 1f) PlaceholderVignette(placeholder, state)
            if (loaded != null) {
                if (loaded.contain) {
                    // contain on the mat: 12 dp inset, never upscaled above 2 × (the painter's intrinsic size)
                    Image(
                        loaded.painter, null,
                        Modifier.fillMaxSize().padding(12.dp).alpha(fade),
                        contentScale = ContentScale.Fit,
                    )
                } else {
                    Image(
                        loaded.painter, null, Modifier.fillMaxSize().alpha(fade),
                        alignment = if (loaded.portrait) BiasAlignment(0f, -0.35f) else Alignment.Center,
                        contentScale = ContentScale.Crop,
                    )
                    // scrim under the credit
                    Box(
                        Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(56.dp)
                            .background(Brush.verticalGradient(listOf(Color.Transparent, C.photo.scrim))),
                    )
                    if (credit != null) CreditLine(credit, C.photo.credit, Modifier.align(Alignment.BottomStart).padding(start = 12.dp, end = 12.dp, bottom = 8.dp), onCredit)
                }
                if (area) AreaPlate(Modifier.align(Alignment.TopStart).padding(10.dp))
            }
            // hairline over the image
            Box(Modifier.matchParentSize().border(DesignTokens.stroke.w1, C.photo.border, shape))
        }
        // contain mode: the line under the frame. A placeholder has no credit (S3-QA P1-05: it would name a photo
        // that is not on screen), hotel areas included.
        if (credit != null && !crop && loaded != null) {
            CreditLine(credit, C.text.muted, Modifier.padding(top = 4.dp), onCredit)
        }
    }
}

@Composable
private fun CreditLine(text: String, color: Color, modifier: Modifier, onClick: (() -> Unit)?) {
    Txt(
        text, T.photo.credit, color,
        modifier.fillMaxWidth().then(if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier).testTag("photo.credit"),
        maxLines = 1,
    )
}

@Composable
private fun AreaPlate(modifier: Modifier) {
    Box(
        modifier.height(22.dp).clip(RoundedCornerShape(DesignTokens.radius.r4)).background(C.photo.scrim).padding(horizontal = 8.dp),
        contentAlignment = Alignment.Center,
    ) { Txt(androidx.compose.ui.res.stringResource(app.verst.core.ui.R.string.card_area_plate), T.photo.label, C.photo.credit, maxLines = 1) }
}

/** §18.1: the illustration at 42 % of the frame height, the state text at 78 %. */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.PlaceholderVignette(kind: Placeholder, state: PhotoState) {
    val mat = when (kind) {
        Placeholder.MUSEUM -> C.photo.phMuseum
        Placeholder.CHURCH -> C.photo.phChurch
        Placeholder.PARK -> C.photo.phPark
        Placeholder.MONUMENT -> C.photo.phMonument
        Placeholder.VIEW -> C.photo.phView
        Placeholder.BAR -> C.photo.phBar
        Placeholder.CITY -> C.photo.phCity
    }
    val text = when (state) {
        PhotoState.None -> androidx.compose.ui.res.stringResource(app.verst.core.ui.R.string.card_photo_none)
        PhotoState.Error -> androidx.compose.ui.res.stringResource(app.verst.core.ui.R.string.card_photo_error)
        PhotoState.Offline -> androidx.compose.ui.res.stringResource(app.verst.core.ui.R.string.card_photo_offline)
        else -> null
    }
    BoxWithConstraints(Modifier.matchParentSize().background(mat)) {
        val h = maxHeight
        Canvas(Modifier.size(96.dp, 64.dp).align(Alignment.TopCenter).offset(y = h * 0.42f - 32.dp)) { vignette(kind) }
        if (state == PhotoState.Loading) {
            // shimmer stand-in (static; the loop pauses under sheets, motion §4.3)
            Box(Modifier.matchParentSize().background(C.photo.matHighlight.copy(alpha = 0.25f)))
        }
        if (text != null) {
            Txt(
                text, T.body.sm, C.text.muted,
                Modifier.align(Alignment.TopCenter).offset(y = h * 0.78f - 8.dp).padding(horizontal = 16.dp),
                align = TextAlign.Center, maxLines = 1,
            )
        }
    }
}

/** The vignettes in a 96 × 64 box, `photo.ink` strokes 3 dp, `photo.accent` fills. */
private fun DrawScope.vignette(kind: Placeholder) {
    val u = size.width / 96f
    val ink = C.photo.ink
    val acc = C.photo.accent
    val st = Stroke(width = 3f * u)
    fun line(x1: Float, y1: Float, x2: Float, y2: Float) = drawLine(ink, Offset(x1 * u, y1 * u), Offset(x2 * u, y2 * u), 3f * u)
    fun rect(x: Float, y: Float, w: Float, h: Float, fill: Boolean = false) =
        if (fill) drawRect(acc, Offset(x * u, y * u), Size(w * u, h * u)) else drawRect(ink, Offset(x * u, y * u), Size(w * u, h * u), style = st)
    fun circle(cx: Float, cy: Float, r: Float, fill: Boolean = false) =
        if (fill) drawCircle(acc, r * u, Offset(cx * u, cy * u)) else drawCircle(ink, r * u, Offset(cx * u, cy * u), style = st)
    when (kind) {
        Placeholder.MUSEUM -> {
            val p = Path().apply { moveTo(18 * u, 22 * u); lineTo(48 * u, 6 * u); lineTo(78 * u, 22 * u); close() }
            drawPath(p, acc)
            drawPath(p, ink, style = st)
            for (x in listOf(26f, 40f, 56f, 70f)) line(x, 26f, x, 52f)
            line(14f, 58f, 82f, 58f)
        }
        Placeholder.CHURCH -> {
            rect(30f, 30f, 36f, 28f)
            rect(40f, 18f, 16f, 12f)
            circle(48f, 13f, 7f, fill = true)
            line(48f, 2f, 48f, 6f)
            line(45f, 4f, 51f, 4f)
            line(10f, 58f, 86f, 58f)
        }
        Placeholder.PARK -> {
            circle(26f, 30f, 12f, fill = true)
            circle(52f, 24f, 16f, fill = true)
            circle(76f, 34f, 9f, fill = true)
            line(26f, 42f, 26f, 58f); line(52f, 40f, 52f, 58f); line(76f, 43f, 76f, 58f)
            line(8f, 58f, 88f, 58f)
            line(34f, 52f, 46f, 52f)
        }
        Placeholder.MONUMENT -> {
            rect(34f, 44f, 28f, 14f, fill = true)
            circle(48f, 14f, 5f)
            line(48f, 19f, 48f, 36f); line(48f, 24f, 40f, 30f); line(48f, 24f, 56f, 30f)
            line(48f, 36f, 43f, 44f); line(48f, 36f, 53f, 44f)
            line(16f, 58f, 80f, 58f)
        }
        Placeholder.VIEW -> {
            val hills = Path().apply { moveTo(4 * u, 40 * u); quadraticTo(28 * u, 10 * u, 50 * u, 40 * u); quadraticTo(70 * u, 18 * u, 92 * u, 40 * u); close() }
            drawPath(hills, acc)
            line(4f, 46f, 92f, 46f)
            line(4f, 58f, 92f, 58f)
            for (x in listOf(16f, 36f, 56f, 76f)) line(x, 52f, x, 58f)
        }
        Placeholder.BAR -> {
            line(6f, 52f, 90f, 52f)
            val glass = Path().apply { moveTo(26 * u, 20 * u); lineTo(42 * u, 20 * u); lineTo(39 * u, 38 * u); lineTo(29 * u, 38 * u); close() }
            drawPath(glass, ink, style = st)
            line(34f, 38f, 34f, 48f)
            rect(54f, 22f, 16f, 26f, fill = true)
            rect(54f, 22f, 16f, 26f)
            line(70f, 28f, 76f, 28f); line(76f, 28f, 76f, 40f); line(76f, 40f, 70f, 40f)
        }
        Placeholder.CITY -> {
            for ((i, x) in listOf(8f, 36f, 64f).withIndex()) {
                val top = if (i == 1) 10f else 18f
                rect(x, top, 24f, 58f - top, fill = i == 1)
                rect(x, top, 24f, 58f - top)
                for (wy in listOf(top + 8f, top + 22f)) {
                    rect(x + 5f, wy, 5f, 6f)
                    rect(x + 14f, wy, 5f, 6f)
                }
            }
        }
    }
}
