package app.verst.e2e

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * M§5.3: every golden case with a snapshot, planned on the device by `golden_snapshot`, equals the snapshot
 * byte for byte; the edge cases without one fail with their error codes. Writes `files/e2e/parity.json`.
 */
@RunWith(AndroidJUnit4::class)
class EngineParityTest {
    private val assets = InstrumentationRegistry.getInstrumentation().context.assets

    private fun asset(path: String): String = assets.open(path).bufferedReader(Charsets.UTF_8).use { it.readText() }

    @Test
    fun goldenSnapshotsMatch() {
        E2e.awaitReady(15_000)
        val cases = assets.list("cases").orEmpty().filter { it.endsWith(".json") }.sorted()
        val snapshots = assets.list("snapshots").orEmpty().toSet()
        val report = JSONObject()
        val mismatches = mutableListOf<String>()
        var snapshotCases = 0
        for (file in cases) {
            val name = file.removeSuffix(".json")
            val body = JSONObject(E2e.engine.call("golden_snapshot", asset("cases/$file")))
            val entry = JSONObject().put("ms", body.optLong("ms"))
            if (file in snapshots) {
                snapshotCases++
                val equal = body.getBoolean("ok") && body.getString("result") == asset("snapshots/$file")
                entry.put("equal", equal)
                if (!body.getBoolean("ok")) entry.put("error", body.getJSONObject("error").getString("code"))
                if (!equal) mismatches += name
            } else {
                entry.put("error", if (body.getBoolean("ok")) "NONE" else body.getJSONObject("error").getString("code"))
            }
            report.put(name, entry)
        }
        File(E2e.dir(), "parity.json").writeText(report.toString(2))
        assertEquals("snapshot cases", 11, snapshotCases) // G01–G08, G11–G13
        assertTrue("snapshot mismatch: $mismatches", mismatches.isEmpty())
        assertEquals("UNREACHABLE", report.getJSONObject("G09_edge_unreachable").getString("error"))
        assertEquals("TOO_SHORT", report.getJSONObject("G10_edge_too_short").getString("error"))
    }
}
