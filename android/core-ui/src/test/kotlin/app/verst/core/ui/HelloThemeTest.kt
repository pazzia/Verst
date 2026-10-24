package app.verst.core.ui

import androidx.compose.ui.graphics.toArgb
import org.junit.Assert.assertEquals
import org.junit.Test

class HelloThemeTest {
    @Test
    fun backgroundIsNight() {
        assertEquals(0xFF141416.toInt(), HelloBackground.toArgb())
    }
}
