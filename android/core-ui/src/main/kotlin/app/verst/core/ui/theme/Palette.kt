package app.verst.core.ui.theme

/**
 * D-IR-20: which palette the colour tokens return. Set once per process in `VerstApp.onCreate` from the settings,
 * before anything reads a token; a theme or design change restarts the app (top-level brushes and cached colours
 * would otherwise keep the old palette).
 */
object Palette {
    @Volatile
    var day: Boolean = false

    /**
     * CEO 01.11: the «Кемпер-гид» design (paper palette, Craft components, header and tab bar) instead of the
     * classic dashboard. Every colour token returns its camper value, and the restyled screens draw their camper twin.
     */
    @Volatile
    var camper: Boolean = false
}
