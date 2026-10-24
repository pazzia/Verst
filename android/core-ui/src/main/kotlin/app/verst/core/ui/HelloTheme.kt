package app.verst.core.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color

/** DEV-100 only: the night background of v5, as a local constant (allow-listed until DesignTokens.kt, DEV-103). */
val HelloBackground = Color(0xFF141416)
val HelloText = Color(0xFFF2EFE6)

@Composable
fun HelloTheme(content: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize().background(HelloBackground)) { content() }
}
