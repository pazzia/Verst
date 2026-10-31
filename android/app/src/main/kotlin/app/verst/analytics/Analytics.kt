package app.verst.analytics

/**
 * ENG-05 product analytics (SPEC §15, `docs/traction/tracking-plan.md` §2). The app reports typed
 * [AnalyticsEvent]s; where they go is the implementation's business:
 *  - [NoopAnalytics]: the default — unit tests, and every build without an AppMetrica key (the public demo APK);
 *  - [GuardedAnalytics] over AppMetrica ([VerstAnalytics]): only when the build carries a key.
 */
interface Analytics {
    /** False for [NoopAnalytics]: callers skip building an event (no engine call is made only to fill a property). */
    val enabled: Boolean get() = true

    fun track(event: AnalyticsEvent)
}

/** Sends nothing. */
object NoopAnalytics : Analytics {
    override val enabled: Boolean get() = false

    override fun track(event: AnalyticsEvent) = Unit
}

/** Where a checked event goes (AppMetrica `reportEvent` in the app, a list in tests). */
fun interface EventSink {
    fun send(name: String, params: Map<String, Any>)
}

/**
 * Every event passes [PrivacyGuard] before it reaches [sink]. An event with a suspicious property (coordinates,
 * e-mail, phone, free text, a key outside the snake_case form) is dropped whole and [onDropped] gets its name and the
 * rule names — never the values.
 */
class GuardedAnalytics(
    private val sink: EventSink,
    private val onDropped: (event: String, rules: List<String>) -> Unit = { _, _ -> },
) : Analytics {
    override fun track(event: AnalyticsEvent) {
        val params = event.params()
        val problems = PrivacyGuard.violations(params)
        if (problems.isEmpty()) sink.send(event.name, params) else onDropped(event.name, problems)
    }
}
