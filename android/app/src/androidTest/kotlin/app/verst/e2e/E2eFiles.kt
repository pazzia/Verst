package app.verst.e2e

import androidx.test.platform.app.InstrumentationRegistry
import app.verst.VerstApp
import app.verst.engine.EngineHost
import app.verst.engine.EngineStatus
import java.io.File
import org.junit.Assert.fail

/** Shared helpers of the emulator tests: the app's engine and the pulled `files/e2e/` directory. */
object E2e {
    val engine: EngineHost
        get() = (InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as VerstApp).engine

    fun dir(): File =
        File(InstrumentationRegistry.getInstrumentation().targetContext.getExternalFilesDir(null), "e2e").apply { mkdirs() }

    /** Waits for the engine; returns the Ready status and the wall time waited. */
    fun awaitReady(timeoutMs: Long): Pair<EngineStatus.Ready, Long> {
        val t0 = System.nanoTime()
        while (true) {
            val waited = (System.nanoTime() - t0) / 1_000_000
            when (val s = engine.status.value) {
                is EngineStatus.Ready -> return s to waited
                is EngineStatus.Failed -> fail("engine failed: ${s.code} ${s.detail}")
                is EngineStatus.Starting -> if (waited > timeoutMs) fail("engine not ready after $timeoutMs ms (${s.phase})")
            }
            Thread.sleep(20)
        }
    }
}
