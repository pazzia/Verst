package app.verst.core.model

import app.verst.core.model.dto.PlanResultDto
import java.io.File
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** DEV-SLICE-2: trip figures (one distance per trip), the raw trip JSON, Waybill/replace DTOs, saved trips. */
class SliceTwoModelTest {
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")
    private val yar = GeoPoint("Ярославль", 57.6261, 39.8845)
    private val req = PlanRequest(DefaultOrigin, yar, adults = 2, dailyKm = 300, budgetRub = 40_000)

    @Test
    fun figuresPreferTheExactRequestThenTheSameRoad() {
        val est = req to TripFigures(265, 1)
        assertEquals(TripFiguresPick.Picked(TripFigures(265, 1), stale = false), TripFiguresPick.pick(req, listOf(est)))
        // A child added: the new estimate is not back yet → the same road's last engine number, marked stale.
        val withChild = req.copy(children = 1)
        assertEquals(TripFiguresPick.Picked(TripFigures(265, 1), stale = true), TripFiguresPick.pick(withChild, listOf(est)))
        // The plan of the new request arrives later and wins over the older estimate.
        val planned = withChild to TripFigures(266, 1)
        assertEquals(TripFigures(266, 1), TripFiguresPick.pick(withChild, listOf(est, planned))!!.figures)
        // Another destination: no number at all (never a number of another trip).
        assertNull(TripFiguresPick.pick(req.copy(destination = GeoPoint("Тула", 54.19, 37.61)), listOf(est)))
        assertNull(TripFiguresPick.pick(null, listOf(est)))
    }

    @Test
    fun noStraightLineKmLeftInTheModel() {
        // P0 regression guard: the slice showed haversine (249) and haversine × 1.25 (312) for Москва → Ярославль.
        val names = TripMath::class.java.declaredMethods.map { it.name }
        assertFalse(names.toString(), names.any { it.contains("haversine", true) || it.contains("roadKm", true) })
        assertEquals("NE", TripMath.bearing8(DefaultOrigin, yar))
        assertEquals("S", TripMath.bearing8(DefaultOrigin, GeoPoint("Тула", 54.1961, 37.6182)))
    }

    private fun envelope(trip: String) = """{"ok":true,"result":{"trip":$trip,"shareText":"Текст","pricesMonthRu":"октябрь","pricesYear":"2026"},"ms":3}"""

    @Test
    fun planResultKeepsTheEngineTripVerbatim() {
        val text = root.resolve("backend/planner/tests/golden/snapshots/G02_golden_ring.json").readText()
        val r = (EngineJson.planResult(envelope(text)) as EngineResult.Ok).value
        assertEquals("октябрь", r.pricesMonthRu)
        assertEquals(EngineJson.json.parseToJsonElement(text), EngineJson.json.parseToJsonElement(r.tripJson))
        val c = r.trip.cost
        assertEquals(listOf("fuel", "tolls", "lodging", "food", "tickets", "reserve"), c.lines.map { it.key })
        assertTrue(c.lines.first().formula.contains("км"))
        assertTrue(c.lines.first { it.key == "fuel" }.breakdown.isNotEmpty())
        val alts = r.trip.daysList.flatMap { it.stops }.flatMap { it.alternatives }
        assertTrue("G02 has alternatives", alts.isNotEmpty())
        assertTrue(alts.all { it.stop != null && it.id.isNotEmpty() })
        assertEquals("""{"reserveOn":false}""", EngineArgs.reservePatch(false))
        assertEquals("""[{"lat":57.6261,"lon":39.8845}]""", EngineArgs.points(listOf(yar)))
        assertEquals(listOf(263, null), (EngineJson.kmList("""{"ok":true,"result":[263,null],"ms":1}""") as EngineResult.Ok).value)
        assertEquals(TripFigures(265, 1).km, (EngineJson.estimate("""{"ok":true,"result":{"km":265,"days":1},"ms":9}""") as EngineResult.Ok).value.km)
    }

    @Test
    fun savedTripsRoundTripLimitAndSchema() {
        val text = root.resolve("backend/planner/tests/golden/snapshots/G01_msk_yar_round.json").readText()
        val r: PlanResultDto = (EngineJson.planResult(envelope(text)) as EngineResult.Ok).value
        val e = SavedTrips.entry("t1", 1000, r, "NE")
        val back = SavedTrips.result(SavedTrips.decode(SavedTrips.encode(listOf(e))).single())
        assertEquals(r.trip, back.trip)
        assertEquals(EngineJson.json.parseToJsonElement(r.tripJson), EngineJson.json.parseToJsonElement(back.tripJson))
        assertEquals("Текст", back.shareText)

        var list = emptyList<SavedTripDto>()
        repeat(SavedTrips.LIMIT) { i ->
            val up = SavedTrips.upsert(list, e.copy(id = "t$i")) as SavedTrips.Upsert.Saved
            assertEquals(i + 1 >= SavedTrips.WARN_FROM, up.nearLimit)
            list = up.trips
        }
        assertEquals(SavedTrips.Upsert.LimitReached, SavedTrips.upsert(list, e.copy(id = "new")))
        // Re-saving an existing trip (after a replace) updates it in place even at the limit.
        val again = SavedTrips.upsert(list, e.copy(id = "t3", totalRub = 1)) as SavedTrips.Upsert.Saved
        assertEquals(SavedTrips.LIMIT, again.count)
        assertEquals(1, again.trips[3].totalRub)

        assertTrue(SavedTrips.decode("""{"schema":3,"trips":[]}""").isEmpty())
        assertTrue(SavedTrips.decode("{broken").isEmpty())
        assertTrue(SavedTrips.decode(null).isEmpty())
        assertEquals("NE", SavedTrips.decode(SavedTrips.encode(listOf(e))).single().bearing8)
        assertTrue(e.trip.jsonObject.containsKey("daysList"))
    }
}
