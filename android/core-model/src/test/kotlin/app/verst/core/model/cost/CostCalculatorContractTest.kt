package app.verst.core.model.cost

import app.verst.core.model.EngineJson
import app.verst.core.model.contract.Contracts
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.int
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.Parameterized

/** DEV-104: every case of `tests/contract/cost_recompute_cases.json`, one test name per case. */
@RunWith(Parameterized::class)
class CostCalculatorContractTest(private val name: String, private val case: JsonObject) {
    companion object {
        @JvmStatic
        @Parameterized.Parameters(name = "case_{0}")
        fun cases(): List<Array<Any>> {
            val text = Contracts.repoRoot.resolve("backend/planner/tests/contract/cost_recompute_cases.json").readText()
            val cases = EngineJson.json.parseToJsonElement(text).jsonObject.getValue("cases").jsonArray
            return cases.map { c -> arrayOf(c.jsonObject.getValue("name").jsonPrimitive.content, c.jsonObject) }
        }
    }

    @Test
    fun matchesTheEngine() {
        val j = EngineJson.json
        val units = j.decodeFromJsonElement(CostUnitsDto.serializer(), case.getValue("units"))
        val crew = j.decodeFromJsonElement(CostCrew.serializer(), case.getValue("crew"))
        val ov = j.decodeFromJsonElement(CostOverridesDto.serializer(), case.getValue("overrides"))
        val budget = case["budget"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.int
        val r = CostCalculator.recompute(units, crew, case.getValue("reserveOn").jsonPrimitive.boolean, budget, ov)
        val e = case.getValue("expected").jsonObject
        val lines = e.getValue("lines").jsonObject.mapValues { it.value.jsonPrimitive.int }
        assertEquals("$name lines", lines, r.lines)
        assertEquals("$name subtotal", e.getValue("subtotalRub").jsonPrimitive.int, r.subtotalRub)
        assertEquals("$name total", e.getValue("totalRub").jsonPrimitive.int, r.totalRub)
        assertEquals("$name per person", e.getValue("perPersonRub").jsonPrimitive.int, r.perPersonRub)
        assertEquals("$name remaining", e["remainingRub"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.int, r.remainingRub)
        assertEquals("$name over", e.getValue("overBudget").jsonPrimitive.boolean, r.overBudget)
        assertEquals("$name hints", e.getValue("hintKeys").jsonArray.map { it.jsonPrimitive.content }, r.hintKeys)
        e["fuelFormulaKm"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.intOrNull?.let { assertEquals("$name fuel km", it, r.fuelFormulaKm) }
    }
}

/** Local total == engine total for every replace and patch item of the DEV-112 bundles. */
class LocalCostBundleTest {
    private fun assertCost(what: String, after: JsonObject, local: CostNumbers) {
        assertEquals("$what total", after.getValue("totalRub").jsonPrimitive.int, local.totalRub)
        for (l in after.getValue("lines").jsonArray) {
            val o = l.jsonObject
            val key = o.getValue("key").jsonPrimitive.content
            assertEquals("$what line $key", o.getValue("rub").jsonPrimitive.int, local.lines[key])
        }
        assertEquals("$what over", after.getValue("overBudget").jsonPrimitive.boolean, local.overBudget)
    }

    @Test
    fun replaceItems() {
        var n = 0
        for (b in Contracts.load("replace")) for (item in b.items) {
            val sid = item.getValue("stopId").jsonPrimitive.content
            val aid = item.getValue("altId").jsonPrimitive.content
            val local = LocalCost.replace(b.before, sid, aid) ?: error("${b.case} $sid/$aid: no alternative units")
            assertCost("${b.case} $sid/$aid", item.getValue("afterCost").jsonObject, local)
            n++
        }
        assertEquals(143, n) // G01–G13 (G13 = ARCH-301 CEO case)
    }

    @Test
    fun patchItems() {
        var n = 0
        for (b in Contracts.load("patch")) for (item in b.items) {
            val patch = item.getValue("patch").jsonObject
            val local = when {
                "reserveOn" in patch -> LocalCost.reserve(b.before, patch.getValue("reserveOn").jsonPrimitive.boolean)
                "budget" in patch -> LocalCost.now(b.before, budget = patch["budget"]?.takeIf { it !is JsonNull }?.jsonPrimitive?.int)
                else -> patch.getValue("hotelChoice").jsonObject.let {
                    LocalCost.hotel(b.before, it.getValue("stopId").jsonPrimitive.content, it.getValue("placeId").jsonPrimitive.content)
                }
            }
            assertCost("${b.case} ${item.getValue("kind").jsonPrimitive.content}", item.getValue("afterCost").jsonObject, local)
            n++
        }
        assertEquals(28, n) // G01–G13
    }

    @Test
    fun perf10kRecomputes() {
        val b = Contracts.load("patch").first { it.case.startsWith("G06") }
        val t0 = System.nanoTime()
        repeat(10_000) { LocalCost.reserve(b.before, it % 2 == 0) }
        val perMs = (System.nanoTime() - t0) / 1e6 / 10_000
        assertTrue("median-ish $perMs ms per recompute (incl. JSON decode)", perMs < 5.0)
    }
}
