package app.verst.core.model

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class EngineJsonTest {
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")

    @Test
    fun everyGoldenSnapshotDecodes() {
        val files = root.resolve("backend/planner/tests/golden/snapshots").listFiles { f -> f.extension == "json" }!!.sorted()
        assertTrue("snapshots found", files.size >= 10)
        for (f in files) {
            val trip = EngineJson.trip(f.readText())
            assertEquals(f.name, trip.days, trip.daysList.size)
            assertTrue(f.name, trip.cost.totalRub > 0)
            assertTrue(f.name, trip.daysList.all { d -> d.stops.isNotEmpty() })
        }
    }

    @Test
    fun envelopeOkAndError() {
        val ok = EngineJson.readyRoutes(
            """{"ok":true,"result":[{"id":"rr","title":"Ярославль","subtitle":"2 дня","kmTotal":526,"kmSign":263,""" +
                """"ring":"weekend","roundTrip":true,"daysMin":2,"daysMax":2,"tags":[],"hubTownId":"t","bearing8":"NE","coverKey":"y"}],"ms":0}""",
        )
        assertEquals(263, (ok as EngineResult.Ok).value.single().kmSign)
        val err = EngineJson.planResult("""{"ok":false,"error":{"code":"TOO_SHORT","message":"x","roadKm":3.2},"ms":1}""")
        assertEquals("TOO_SHORT", (err as EngineResult.Err).error.code)
        val garbage = EngineJson.planResult("not json")
        assertEquals("INTERNAL", (garbage as EngineResult.Err).error.code)
    }

    @Test
    fun planEventsDecode() {
        val stage = EngineJson.event("""{"event": "stage", "key": "split", "text": "Прокладываем дорогу", "progress": 0.05}""")!!
        assertEquals("split", stage.key)
        val stop = EngineJson.event("""{"event":"stop","day":1,"stop":{"id":"d1s02","kind":"sight","sign":"tourist","name":"Лавра","kmAt":73,"provisional":false}}""")!!
        assertEquals("tourist", stop.stop!!.sign)
        assertNull(EngineJson.event("{"))
    }

    @Test
    fun requestJson() {
        val free = PlanRequest(DefaultOrigin, GeoPoint("Ярославль", 57.6261, 39.8845), adults = 2, children = 1, dailyKm = 300)
        val body = Json.parseToJsonElement(free.toInputJson()).jsonObject
        assertEquals(300, body["dailyKm"]!!.jsonPrimitive.int)
        assertEquals("Ярославль", body["destination"]!!.jsonObject["label"]!!.jsonPrimitive.content)
        assertTrue(body.containsKey("budget"))
        val ready = PlanRequest(DefaultOrigin, readyRouteId = "rr_golden_ring", budgetRub = 40_000, mood = Mood.CALM)
        val r = Json.parseToJsonElement(ready.toInputJson()).jsonObject
        assertEquals("rr_golden_ring", r["readyRouteId"]!!.jsonPrimitive.content)
        assertEquals("calm", r["mood"]!!.jsonPrimitive.content)
        assertTrue(!r.containsKey("destination"))
    }

    @Test
    fun formatting() {
        assertEquals("34 500", RuFormat.thousands(34500))
        assertEquals("900", RuFormat.thousands(900))
        assertEquals("1 000 000", RuFormat.thousands(1_000_000))
        assertEquals("09:05", RuFormat.clock("2026-11-07T09:05"))
        assertNull(RuFormat.clock(null))
        assertEquals(260, TripMath.driveMinutes(300))
        assertEquals(3, TripMath.days(745, 300))
        val km = TripMath.roadKmEstimate(DefaultOrigin, GeoPoint("Ярославль", 57.6261, 39.8845))
        assertTrue("$km", km in 300..340)
    }
}
