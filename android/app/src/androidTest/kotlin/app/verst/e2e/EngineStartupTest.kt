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
            .put("selfcheckMs", t.selfcheckMs)
            .put("readyMs", t.totalMs)
            .put("waitedMs", waited)
        // S3-R4: the catalogue loads after «ready» on the engine thread (the first screen does not wait for it)
        val c0 = System.nanoTime()
        while (E2e.engine.catalogueMs.value == null && (System.nanoTime() - c0) / 1_000_000 < 15_000) Thread.sleep(20)
        val catalogue = E2e.engine.catalogueMs.value
        json.put("catalogueMs", catalogue ?: -1).put("readyPlusCatalogueMs", t.totalMs + (catalogue ?: 0))
        File(E2e.dir(), "timings.json").writeText(json.toString(2))
        assertTrue("catalogue loaded", catalogue != null)
        assertTrue("readyMs ${t.totalMs} > 8000 (hard limit)", t.totalMs <= 8000)
        // M§15.2 / DEV-309: the app is usable ≤ 5 000 ms after start on the emulator. The catalogue loads in the
        // background after «ready» (S3-R4); S4 r7.3 doubled it (822 KB POIs, 1.8–3.3 s cold on the CI emulator):
        // its budget is 4 000 ms until the Architect slims the load (dev-notes S4)
        assertTrue("readyMs ${t.totalMs} > 5000 (Sprint 3 budget)", t.totalMs <= 5000)
        assertTrue("catalogueMs $catalogue > 4000", (catalogue ?: 0) <= 4000)
    }
}
