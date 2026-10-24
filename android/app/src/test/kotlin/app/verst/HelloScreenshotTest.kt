package app.verst

import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.captureToImage
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(qualifiers = "w390dp-h844dp-port-xxhdpi")
class HelloScreenshotTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun helloDefault() {
        compose.onNodeWithText("Верста").assertExists()
        compose.onNodeWithText("Движок: NO_ENGINE").assertExists() // no CPython under Robolectric
        compose.waitForIdle()
        var bitmap = Screenshot.drawDecorView(compose.activity)
        var method = "View.draw"
        if (Screenshot.isUniform(bitmap)) {
            bitmap = compose.onRoot().captureToImage().asAndroidBitmap()
            method = "captureToImage"
        }
        println("HelloScreenshotTest: method=$method size=${bitmap.width}x${bitmap.height}")
        assertEquals(1170, bitmap.width)
        assertEquals(2532, bitmap.height)
        Screenshot.write(bitmap, "hello", "default", 390, 844)
    }
}
