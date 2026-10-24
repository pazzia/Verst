package app.verst

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.Canvas
import java.io.File

/**
 * Robolectric screenshots (M§0, M§11): renders a view hierarchy into a software bitmap and writes
 * `<verst.screenshots.dir>/<screen>/<state>@<w>x<h>.png`. `capture` returns null when the drawing is blank
 * (a single colour), so callers can fall back to Compose's `captureToImage()`.
 */
object Screenshot {
    val dir: File = File(System.getProperty("verst.screenshots.dir") ?: "build/outputs/screenshots")

    fun drawDecorView(activity: Activity): Bitmap {
        val view = activity.window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        view.draw(Canvas(bitmap))
        return bitmap
    }

    fun isUniform(bitmap: Bitmap): Boolean {
        val first = bitmap.getPixel(0, 0)
        for (y in 0 until bitmap.height step 7) {
            for (x in 0 until bitmap.width step 7) {
                if (bitmap.getPixel(x, y) != first) return false
            }
        }
        return true
    }

    fun write(bitmap: Bitmap, screen: String, state: String, widthDp: Int, heightDp: Int): File {
        val out = File(dir, "$screen/$state@${widthDp}x$heightDp.png")
        out.parentFile?.mkdirs()
        out.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        return out
    }
}
