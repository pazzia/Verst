package app.verst

import android.app.Application
import app.verst.data.FileTripStore
import app.verst.engine.ChaquopyPlannerGateway
import app.verst.engine.EngineHost
import app.verst.nav.VerstFlow
import app.verst.platform.AndroidLocator
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

/** Process entry: starts the on-device engine in the background (ADR-0010, M§5.2) and holds the app flow. */
class VerstApp : Application(), coil.ImageLoaderFactory {
    lateinit var engine: EngineHost
        private set

    /** D-IR-20: saved trips in the app, mirrored into the folder the user picked (settings «Где хранить поездки»). */
    val tripStore: app.verst.settings.MirroringTripStore by lazy { app.verst.settings.MirroringTripStore(FileTripStore(this), this) }

    /** SRV-01: the test backend of this build (ADR-0020); the phone engine stays the fallback. */
    val server: app.verst.data.net.ServerClient by lazy {
        app.verst.data.net.ServerClient(
            { app.verst.settings.AppPrefs.serverUrl }, app.verst.settings.AppPrefs.serverAuth,
            BuildConfig.VERSION_NAME, { app.verst.settings.AppPrefs.settings.language.tag },
        )
    }

    val gateway: app.verst.engine.ServerPlannerGateway by lazy {
        app.verst.engine.ServerPlannerGateway(
            ChaquopyPlannerGateway(engine), server,
            enabled = { app.verst.settings.AppPrefs.settings.planOnServer }, online = { flow.connectivity.online },
            // CEO 29.10: a trip abroad goes to the server whatever the setting, but only with the tester's consent
            consent = { app.verst.settings.AppPrefs.settings.serverConsent },
        )
    }

    /** App-scoped (survives activity recreation); created on first use from the main thread. */
    val flow: VerstFlow by lazy {
        VerstFlow(
            gateway,
            CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate),
            tripStore,
        ) { engine.restart() }.also {
            it.locator = AndroidLocator(this)
            it.addressFallback = app.verst.platform.AndroidGeocoder(this)
            it.countrySource = app.verst.platform.TelephonyCountrySource(this) // CEO 29.10: the maps app by country
        }
    }

    /** DEV-300: Coil with the app's OkHttp (User-Agent) and the 64 MB `cacheDir/images` disk cache. */
    override fun newImageLoader(): coil.ImageLoader = app.verst.data.net.Net.imageLoader(this)

    override fun onCreate() {
        super.onCreate()
        // D-IR-20: settings first — the activity reads the language, the tokens read the theme
        app.verst.settings.AppPrefs.init(this)
        app.verst.core.ui.theme.Palette.day = app.verst.settings.Themes.isDay(this, app.verst.settings.AppPrefs.settings.theme)
        engine = EngineHost(this)
        engine.start()
    }

    private var network: app.verst.data.net.NetworkConnectivity? = null

    /** DEV-300: the real network state under the debug override (started by the activity, once). */
    fun startNetwork() {
        if (network != null) return
        network = app.verst.data.net.NetworkConnectivity(this, flow.connectivity).also { it.start() }
    }
}
