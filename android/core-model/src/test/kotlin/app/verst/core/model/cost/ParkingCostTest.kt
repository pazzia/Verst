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
                    ParkingUnitDto("d1s2", rubPerHour = 150, hours = 2.0, rub = 300, source = "zone"),
                    ParkingUnitDto("d1s4", rubPerHour = 100, hours = 2.0, rub = 200, source = "zone"),
                    ParkingUnitDto("d1s5", rubPerHour = null, hours = null, rub = 0, source = "free"),
                    ParkingUnitDto("d1s6", rubPerHour = null, hours = 1.0, rub = null, source = "unknown"),
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
        val u = units(listOf(ParkingUnitDto("d1s2", rubPerHour = 150, hours = 2.0, rub = 300, source = "zone")))
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
        // the engine marks fun stops by their reason today (`rest.fun.*`), not by `funFor`
        val fun0 = EngineJson.json.decodeFromString(
            app.verst.core.model.dto.StopDto.serializer(),
            """{"id":"d1s3","kind":"sight","sign":"brown","name":"Парк","reason":"Весело и познавательно: 30 минут — ребёнку размяться и узнать новое."}""",
        )
        assertTrue(fun0.stretch)
        val free = EngineJson.json.decodeFromString(app.verst.core.model.dto.ParkingDto.serializer(), """{"rub":0,"source":"free"}""")
        assertTrue(free.free && free.known)
        val unknown = EngineJson.json.decodeFromString(app.verst.core.model.dto.ParkingDto.serializer(), """{"rubPerHour":null,"rub":null,"source":"unknown"}""")
        assertFalse(unknown.known)
    }
}
