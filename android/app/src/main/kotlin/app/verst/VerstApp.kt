package app.verst

import android.app.Application
import app.verst.engine.EngineHost

/** Process entry: starts the on-device engine in the background (ADR-0010, M§5.2). */
class VerstApp : Application() {
    lateinit var engine: EngineHost
        private set

    override fun onCreate() {
        super.onCreate()
        engine = EngineHost(this)
        engine.start()
    }
}
