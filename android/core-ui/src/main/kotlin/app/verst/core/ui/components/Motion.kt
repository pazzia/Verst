package app.verst.core.ui.components

import android.content.Context
import android.provider.Settings
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.animation.core.withInfiniteAnimationFrameMillis
import app.verst.core.ui.theme.DesignTokens

/**
 * motion.md §4.4: true when the system «Remove animations» switch is on (transition or animator scale 0). All
 * loops then show their static frames and one-shots jump to their end state.
 */
val LocalReducedMotion = staticCompositionLocalOf { false }

fun reducedMotion(context: Context): Boolean {
    val r = context.contentResolver
    fun scale(name: String) = runCatching { Settings.Global.getFloat(r, name, 1f) }.getOrDefault(1f)
    return scale(Settings.Global.ANIMATOR_DURATION_SCALE) == 0f || scale(Settings.Global.TRANSITION_ANIMATION_SCALE) == 0f
}

/**
 * motion.md §5: one clock per screen, in ms, advanced by frames while [running]. Uses the *infinite* frame
 * API so tests are not kept busy by the loops (Compose's InfiniteAnimationPolicy). Read it inside draw lambdas
 * only, so a frame redraws without recomposing.
 */
@Composable
fun rememberSceneClock(running: Boolean): State<Long> {
    val time = remember { mutableLongStateOf(0L) }
    LaunchedEffect(running) {
        if (!running) return@LaunchedEffect
        var last = withInfiniteAnimationFrameMillis { it }
        while (true) {
            withInfiniteAnimationFrameMillis { now ->
                time.longValue += (now - last).coerceIn(0, 100)
                last = now
            }
        }
    }
    return time
}

/** Scene clock that runs unless reduced motion is on or an overlay covers the scene (motion.md §4.3). */
@Composable
fun sceneClock(overlay: Boolean = false): State<Long> = rememberSceneClock(!LocalReducedMotion.current && !overlay)

object Phases {
    /** Lane dash phase in road-plane dp (0 → period per cycle). */
    fun lane(t: Long, cycleMs: Int, periodDp: Float = 160f): Float = (t % cycleMs).toFloat() / cycleMs * periodDp

    /** `turnSignal`: alpha 1 for 0–495 ms, 0.15 to 900 ms. */
    fun turnSignal(t: Long): Float =
        if (t % DesignTokens.motion.turnSignal.durationMs < DesignTokens.motion.turnSignal.onMs) 1f else DesignTokens.motion.turnSignal.offAlpha

    /** `twinkle`: 0.3 ↔ 1 over 2400 ms with the star's delay; easeInOut per half. */
    fun twinkle(t: Long, delayMs: Int): Float {
        val d = DesignTokens.motion.twinkle.durationMs
        val p = ((t + d - delayMs) % d).toFloat() / d
        val half = if (p < 0.5f) p * 2 else (1 - p) * 2
        val e = DesignTokens.motion.easing.easeInOut.transform(half)
        return DesignTokens.motion.twinkle.fromAlpha + (1 - DesignTokens.motion.twinkle.fromAlpha) * e
    }

    /** Progress 0…1 of a repeating post / sign cycle with an offset. */
    fun cycle(t: Long, durationMs: Int, offsetMs: Int = 0): Float = ((t + offsetMs) % durationMs).toFloat() / durationMs
}
