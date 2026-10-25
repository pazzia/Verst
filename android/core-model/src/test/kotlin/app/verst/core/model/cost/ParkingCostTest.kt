package app.verst.core.model.cost

import app.verst.core.model.EngineJson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * ADR-0015 §4 parking parity (S4): the «Парковки» line is Σ `units.parking[].rub` (already rounded per stop), part
 * of the subtotal (so of the reserve and the total); unknown stays add nothing; no units → no line at all (v2 trips).
 * The Python `cost_recompute_cases.json` parking cases will run through [CostCalculatorContractTest] once the engine
 * milestone lands; these pin the Kotlin side meanwhile.
 */
class ParkingCostTest {
    private val fuel = FuelUnitsDto(consumption = 8.0, regions = listOf(FuelRegionUnitDto("76", "Ярославская", 100.0, "60.00")))
    private val crew = CostCrew(adults = 2)

    private fun units(parking: List<ParkingUnitDto>) = CostUnitsDto(fuel = fuel, parking = parking)

    @Test
    fun noUnitsNoLine() {
        val n = CostCalculator.recompute(units(emptyList()), crew, reserveOn = true, budgetRub = null)
        assertFalse("parking" in n.lines)
    }

    @Test
    fun sumOfKnownStaysAndUnknownsAddNothing() {
        val n = CostCalculator.recompute(
            units(
                listOf(
                    ParkingUnitDto("d1s2", 150, 2.0, 300, "zone"),
                    ParkingUnitDto("d1s4", 100, 2.0, 200, "zone"),
                    ParkingUnitDto("d1s5", null, null, 0, "free"),
                    ParkingUnitDto("d1s6", null, 1.0, null, "unknown"),
                ),
            ),
            crew, reserveOn = true, budgetRub = null,
        )
        assertEquals(500, n.lines["parking"])
        // fuel 100 km × 8 l / 100 × 60 ₽ = 480; parking 500 → subtotal 980, reserve 10 % = 100 (round 10)
        assertEquals(980, n.subtotalRub)
        assertEquals(100, n.lines["reserve"])
        assertEquals(1100, n.totalRub)
        val keys = n.lines.keys.toList()
        assertTrue("parking before reserve: $keys", keys.indexOf("parking") < keys.indexOf("reserve"))
    }

    @Test
    fun replacedStopTakesTheAlternativesStay() {
        val u = units(listOf(ParkingUnitDto("d1s2", 150, 2.0, 300, "zone")))
        val ov = CostOverridesDto(replaced = mapOf("d1s2" to AltUnitsDto(parkingRub = 80, parkingSource = "zone")))
        assertEquals(80, CostCalculator.recompute(u, crew, reserveOn = false, budgetRub = null, ov = ov).lines["parking"])
        // M6 rule 5: without `parkingSource` the replaced stop loses its parking
        val none = CostOverridesDto(replaced = mapOf("d1s2" to AltUnitsDto(parkingRub = 80)))
        assertEquals(0, CostCalculator.recompute(u, crew, reserveOn = false, budgetRub = null, ov = none).lines["parking"])
    }

    @Test
    fun v3StopParkingParses() {
        val s = EngineJson.json.decodeFromString(
            app.verst.core.model.dto.StopDto.serializer(),
            """{"id":"d1s2","kind":"sight","sign":"brown","name":"Лавра","kmDriven":73,"kmLeft":752,"poiKind":"monastery",
               "funFor":["child"],"parking":{"rubPerHour":150,"rub":300,"source":"zone","extra":1},"amenities":["toilets"]}""",
        )
        assertEquals(73, s.kmDriven)
        assertEquals(300, s.parking?.rub)
        assertTrue(s.parking!!.known)
        assertTrue(s.stretch)
        val free = EngineJson.json.decodeFromString(app.verst.core.model.dto.ParkingDto.serializer(), """{"rub":0,"source":"free"}""")
        assertTrue(free.free && free.known)
        val unknown = EngineJson.json.decodeFromString(app.verst.core.model.dto.ParkingDto.serializer(), """{"rubPerHour":null,"rub":null,"source":"unknown"}""")
        assertFalse(unknown.known)
    }
}
