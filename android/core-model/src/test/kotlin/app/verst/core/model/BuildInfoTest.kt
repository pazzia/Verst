package app.verst.core.model

import org.junit.Assert.assertEquals
import org.junit.Test

class BuildInfoTest {
    @Test
    fun labelUsesSevenCharacterSha() {
        val info = BuildInfo(42, "0123456789abcdef")
        assertEquals("0123456", info.sha7)
        assertEquals("Сборка 42 · 0123456", info.label)
    }
}
