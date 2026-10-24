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
class VerstApp : Application() {
    lateinit var engine: EngineHost
        private set

    /** App-scoped (survives activity recreation); created on first use from the main thread. */
    val flow: VerstFlow by lazy {
        VerstFlow(
            ChaquopyPlannerGateway(engine),
            CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate),
            FileTripStore(this),
        ) { engine.restart() }.also { it.locator = AndroidLocator(this) }
    }

    override fun onCreate() {
        super.onCreate()
        engine = EngineHost(this)
        engine.start()
    }
}
