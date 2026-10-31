package app.verst.analytics

/** The fake [Analytics] of the tests: records every event in order (names + the exact properties sent). */
class RecordingAnalytics : Analytics {
    val events = mutableListOf<AnalyticsEvent>()

    /** Every event since the start, including those [clear] removed from [events]. */
    val all = mutableListOf<AnalyticsEvent>()

    override fun track(event: AnalyticsEvent) {
        events += event
        all += event
    }

    /** `name` + properties, the way AppMetrica would receive them. */
    val sent: List<Pair<String, Map<String, Any>>> get() = events.map { it.name to it.params() }

    val names: List<String> get() = events.map { it.name }

    fun clear() = events.clear()
}
