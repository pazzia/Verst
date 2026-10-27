package app.verst.core.ui.theme

/**
 * D-IR-20: which palette the colour tokens return. Set once per process in `VerstApp.onCreate` from the settings,
 * before anything reads a token; a theme change restarts the app (top-level brushes and cached colours would
 * otherwise keep the old palette).
 */
object Palette {
    @Volatile
    var day: Boolean = false
}
