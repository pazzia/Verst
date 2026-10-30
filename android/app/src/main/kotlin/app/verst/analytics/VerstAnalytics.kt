package app.verst.analytics

import android.app.Application
import android.util.Log
import app.verst.BuildConfig
import io.appmetrica.analytics.AppMetrica
import io.appmetrica.analytics.AppMetricaConfig

/**
 * The process's analytics (ENG-05): AppMetrica when the build carries an API key (`BuildConfig.APPMETRICA_API_KEY`,
 * see `app/build.gradle.kts`), else [NoopAnalytics] — a build without a key never activates the SDK and sends nothing.
 *
 * AppMetrica is an external processor (R-07): location collection and advertising identifiers are switched off
 * explicitly, no user profile id is ever set, and every event passes [PrivacyGuard]. Its own pseudonymous device id
 * is the only identifier (SPEC §15, §16).
 */
object VerstAnalytics {
    private const val TAG = "VerstAnalytics"

    @Volatile private var instance: Analytics? = null

    /** `app_open` cold / warm, kept for the process. */
    val appOpen = AppOpenTracker()

    /** Activates once per process and returns the same [Analytics] on every call (activity recreation included). */
    fun install(app: Application, key: String = BuildConfig.APPMETRICA_API_KEY): Analytics =
        instance ?: synchronized(this) { instance ?: create(app, key).also { instance = it } }

    /** A key that is not usable never touches the SDK (unit-tested); [install] keeps the result for the process. */
    internal fun create(app: Application, key: String): Analytics {
        if (!AnalyticsKey.usable(key)) return NoopAnalytics
        return runCatching {
            AppMetrica.activate(app, config(key))
            AppMetrica.setLocationTracking(false) // belt and braces: the config already says so
            AppMetrica.enableActivityAutoTracking(app) // sessions; activation happens in the activity, not Application
            GuardedAnalytics(
                sink = { name, params -> AppMetrica.reportEvent(name, params) },
                onDropped = { name, rules -> Log.w(TAG, "dropped $name: $rules") },
            )
        }.getOrElse {
            Log.w(TAG, "AppMetrica not activated: ${it.javaClass.simpleName}")
            NoopAnalytics
        }
    }

    /**
     * The SDK configuration (unit-tested): no location, no advertising ids, no automatic revenue or deeplink
     * («app open») events; crash reporting on (ENG-05 «analytics funnel and crash reporting»).
     */
    fun config(key: String): AppMetricaConfig = AppMetricaConfig.newConfigBuilder(key)
        .withLocationTracking(false)
        .withAdvIdentifiersTracking(false)
        .withRevenueAutoTrackingEnabled(false)
        .withAppOpenTrackingEnabled(false)
        .withCrashReporting(true)
        .build()
}

/** An AppMetrica API key is a UUID; an empty or malformed key means «analytics off». */
object AnalyticsKey {
    private val FORM = Regex("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

    fun usable(key: String?): Boolean = key != null && FORM.matches(key)
}
