package app.verst.e2e

import androidx.test.ext.junit.runners.AndroidJUnit4
import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** DEV-101: the engine reaches Ready within 15 s; its timings go to `files/e2e/timings.json`. */
@RunWith(AndroidJUnit4::class)
class EngineStartupTest {
    @Test
    fun engineBecomesReady() {
        val (ready, waited) = E2e.awaitReady(15_000)
        val t = ready.info.timings
        val json = JSONObject()
            .put("engineVersion", ready.info.engineVersion)
            .put("python", ready.info.python)
            .put("pythonStartMs", t.pythonStartMs)
            .put("importMs", t.importMs)
            .put("worldsMs", t.worldsMs)
            .put("catalogueMs", t.catalogueMs)
            .put("selfcheckMs", t.selfcheckMs)
            .put("totalMs", t.totalMs)
            .put("waitedMs", waited)
        File(E2e.dir(), "timings.json").writeText(json.toString(2))
        assertTrue("totalMs ${t.totalMs} > 8000 (hard limit)", t.totalMs <= 8000)
        // M§15.2 / backlog DEV-309: engine start incl. the catalogue ≤ 5 000 ms on the emulator.
        assertTrue("totalMs ${t.totalMs} > 5000 (Sprint 3 budget)", t.totalMs <= 5000)
    }
}
