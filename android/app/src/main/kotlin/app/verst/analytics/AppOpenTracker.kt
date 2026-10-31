package app.verst.analytics

/**
 * `app_open` start type (tracking plan §2.2): the first foreground of the process is [AnalyticsEvent.StartType.COLD],
 * each later return from the background is [AnalyticsEvent.StartType.WARM]. A rotation (stop + start while changing
 * configurations) is not a new open. Fed by the single activity's onStart / onStop; one instance per process.
 */
class AppOpenTracker {
    private var opened = false
    private var background = true

    /** The activity started: the start type to report, or null when the app never left the foreground. */
    fun onStart(): AnalyticsEvent.StartType? {
        if (!background) return null
        background = false
        val type = if (opened) AnalyticsEvent.StartType.WARM else AnalyticsEvent.StartType.COLD
        opened = true
        return type
    }

    /** The activity stopped; [changingConfigurations] = it is only being recreated (rotation, dark mode). */
    fun onStop(changingConfigurations: Boolean) {
        if (!changingConfigurations) background = true
    }
}
