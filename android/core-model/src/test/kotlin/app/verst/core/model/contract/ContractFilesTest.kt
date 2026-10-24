package app.verst.core.model.contract

import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** The gzipped contract bundles load; the full `TripEditor` / `CostCalculator` checks come with DEV-104. */
class ContractFilesTest {
    @Test
    fun replaceBundlesLoad() {
        val bundles = Contracts.load("replace")
        assertEquals("replace bundles", 10, bundles.size)
        assertTrue("replace items", bundles.sumOf { it.items.size } >= 40)
        for (b in bundles) {
            val stopIds = b.before.getValue("daysList").jsonArray
                .flatMap { it.jsonObject.getValue("stops").jsonArray }
                .map { it.jsonObject.getValue("id").jsonPrimitive.content }
                .toSet()
            for (item in b.items) {
                val stopId = item.getValue("stopId").jsonPrimitive.content
                assertTrue("${b.case}: stop $stopId in before", stopId in stopIds)
                assertTrue(b.case, item.getValue("afterDay").jsonObject.containsKey("stops"))
                assertTrue(b.case, item.getValue("afterCost").jsonObject.containsKey("totalRub"))
            }
            val perStop = b.items.groupingBy { it.getValue("stopId").jsonPrimitive.content }.eachCount()
            assertTrue("${b.case}: ≤ 3 alternatives per stop", perStop.values.all { it <= 3 })
        }
    }

    @Test
    fun patchBundlesLoad() {
        val bundles = Contracts.load("patch")
        assertEquals("patch bundles", 10, bundles.size)
        assertTrue("patch items", bundles.sumOf { it.items.size } >= 12)
        val kinds = bundles.flatMap { b -> b.items.map { it.getValue("kind").jsonPrimitive.content.substringBefore("_") } }
        assertEquals(setOf("reserve", "budget", "hotel"), kinds.toSet())
    }
}
