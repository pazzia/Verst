package app.verst.core.ui

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * G-01 / M§10.1: `:core-ui` DesignTokens.kt equals design/DesignTokens.kt. Until DES-100 bundles the fonts, the
 * `font` object (and the `R` import it needs) may differ — `tools/sync_design_tokens.py` writes system fallbacks.
 */
class DesignTokensInSyncTest {
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")

    private fun withoutFonts(text: String): List<String> {
        val lines = text.lines().filterNot { it == "import app.verst.core.ui.R" || it == "import androidx.compose.ui.text.font.DeviceFontFamilyName" }
        val start = lines.indexOf("    object font {")
        val end = (start + 1 until lines.size).first { lines[it] == "    }" }
        return lines.subList(0, start) + lines.subList(end + 1, lines.size)
    }

    @Test
    fun tokensMatchDesign() {
        val design = root.resolve("design/DesignTokens.kt").readText()
        val copy = root.resolve("android/core-ui/src/main/kotlin/app/verst/core/ui/theme/DesignTokens.kt").readText()
        val fonts = root.resolve("android/core-ui/src/main/res/font/ibm_plex_sans_condensed_regular.ttf").exists()
        if (fonts) {
            assertEquals("verbatim copy once the fonts are bundled", design, copy)
        } else {
            assertTrue(copy.contains("DeviceFontFamilyName(\"sans-serif-condensed\")"))
            assertEquals(withoutFonts(design), withoutFonts(copy))
        }
    }
}
