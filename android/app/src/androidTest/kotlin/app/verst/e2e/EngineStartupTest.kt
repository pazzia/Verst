package app.verst.e2e

import android.os.SystemClock
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
        assertTrue("catalogue loaded", catalogue != null)
        // Two more loads on the engine thread, timed like EngineHost (load_catalogue + selfcheck): one sample on the
        // shared CI emulator swings with host load (2 539 ms on 26.10, 2 817 ms on 27.10 on code that passed before
        // and after). The budget below applies to the median of three, so one stall does not fail the build and a
        // real regression (every load slower) still does.
        val samples = listOf(catalogue!!) + List(2) { reloadCatalogueMs() }
        val median = samples.sorted()[1]
        json.put("catalogueMs", catalogue).put("readyPlusCatalogueMs", t.totalMs + catalogue)
            .put("catalogueSamplesMs", org.json.JSONArray(samples)).put("catalogueMedianMs", median)
        File(E2e.dir(), "timings.json").writeText(json.toString(2))
        assertTrue("readyMs ${t.totalMs} > 8000 (hard limit)", t.totalMs <= 8000)
        // M§15.2 / DEV-309: the app is usable ≤ 5 000 ms after start on the emulator. The catalogue loads in the
        // background after «ready» (S3-R4); S4 r7.3 doubled it (822 KB POIs, 1.8–3.3 s cold on the CI emulator):
        // M9 slimmed the load (run 117: 454–1 033 ms over five cold starts, target ≤ 1 500 ms): the budget is
        // 2 000 ms — the target plus emulator jitter (dev-notes S4-RELEASE)
        assertTrue("readyMs ${t.totalMs} > 5000 (Sprint 3 budget)", t.totalMs <= 5000)
        assertTrue("catalogue median $median ms > 2000 (samples $samples)", median <= 2000)
    }

    private fun reloadCatalogueMs(): Long {
        val r0 = SystemClock.elapsedRealtime()
        for (fn in listOf("load_catalogue", "selfcheck")) {
            val body = JSONObject(E2e.engine.call(fn))
            assertTrue("$fn failed: $body", body.getBoolean("ok"))
        }
        return SystemClock.elapsedRealtime() - r0
    }
}
