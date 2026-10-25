package app.verst.core.model

import app.verst.core.model.contract.Contracts
import app.verst.core.model.cost.CostCalculator
import app.verst.core.model.cost.CostCrew
import app.verst.core.model.cost.CostUnitsDto
import app.verst.core.model.cost.HotelPriceDto
import app.verst.core.model.cost.NightUnitDto
import app.verst.core.model.dto.PlanOutcome
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Sprint 3: every `docs/contracts/v2` response decodes into the app's DTOs (M§5.4, ARCH-305). */
class V2ContractsTest {
    private fun envelope(name: String): String =
        (Json.parseToJsonElement(Contracts.repoRoot.resolve("docs/contracts/v2/$name").readText()).jsonObject["response"] as JsonObject).toString()

    private fun request(name: String): JsonObject =
        Json.parseToJsonElement(Contracts.repoRoot.resolve("docs/contracts/v2/$name").readText()).jsonObject["request"] as JsonObject

    private fun <T> ok(r: EngineResult<T>): T = (r as? EngineResult.Ok)?.value ?: error("not ok: $r")

    @Test
    fun geoCalls() {
        val near = ok(EngineJson.geoNearest(envelope("geo_nearest.json")))
        assertEquals("Ярославль", near.town!!.name)
        assertEquals("Ярославля", near.town!!.nameGenRu)
        assertTrue(near.insideRussia)
        val out = ok(EngineJson.geoNearest(envelope("geo_nearest-outside.json")))
        assertFalse(out.insideRussia)
        val hits = ok(EngineJson.suggestions(envelope("geo_search-city.json")))
        assertEquals("Санкт-Петербург", hits.first().name)
        assertEquals("Санкт-Петербурга", hits.first().nameGenRu)
        assertTrue(ok(EngineJson.suggestions(envelope("geo_search-poi.json"))).isNotEmpty())
    }

    @Test
    fun planAndEstimateV2() {
        val o = ok(EngineJson.planOutcome(envelope("plan-synthetic.json")))
        val plan = (o as PlanOutcome.Plan).result
        assertTrue("synthetic route", plan.trip.approxDistances)
        assertNull(plan.trip.budgetFit)
        assertTrue(plan.tripJson.contains("engineState"))
        val e = ok(EngineJson.estimate(envelope("estimate-synthetic.json")))
        assertEquals("plan", e.outcome)
        assertTrue("an estimate total (data-dependent: ${e.totalRub})", e.totalRub > 0)
        // The v1 decoder still reads a v2 plan (additive fields only).
        assertEquals(plan.trip.km, ok(EngineJson.planResult(envelope("plan-synthetic.json"))).trip.km)
    }

    @Test
    fun noFitOutcomeOfAdr0011() {
        // ADR-0011 «Doesn't fit» envelope (the engine's ARCH-301 contract file replaces this sample when it lands).
        val trip = (Json.parseToJsonElement(envelope("plan-synthetic.json")).jsonObject["result"] as JsonObject)["trip"].toString()
        val env = """{"ok": true, "result": {"outcome": "no_fit", "budgetRub": 30000, "allowedRub": 31500,
            "minimum": {"totalRub": 41200, "levers": [{"code": "lodging_cheap", "savedRub": 6000}], "trip": $trip, "shareText": "s"},
            "options": [{"kind": "shorten", "days": 2, "totalRub": 29700, "readyRouteId": "rr_golden_ring_short", "titleRu": "Золотое кольцо · коротко"},
              {"kind": "cheaper_route", "totalRub": 24300, "readyRouteId": "rr_yaroslavl", "titleRu": "Ярославль"},
              {"kind": "raise_budget", "budgetRub": 42000}],
            "textRu": "В 30 000 ₽ эта поездка не помещается"}, "ms": 1}"""
        val nf = (ok(EngineJson.planOutcome(env)) as PlanOutcome.NoFit).noFit
        assertEquals(30000, nf.budgetRub)
        assertEquals(41200, nf.minimumTotalRub)
        assertEquals(listOf("shorten", "cheaper_route", "raise_budget"), nf.options.map { it.kind })
        assertEquals(42000, nf.options.last().budgetRub)
        assertNotNull(nf.minimum)
        assertEquals("lodging_cheap", nf.minimumLevers.single().code)
    }

    @Test
    fun cardsHandoffAndCity() {
        val sight = ok(EngineJson.poiDetails(envelope("poi_details-sight.json")))
        assertEquals("museum", sight.poiKind)
        assertNotNull(sight.image!!.card)
        // the licence is the file's own (the data run decides which); it is always named
        assertTrue(sight.image!!.credit!!.licence.orEmpty().startsWith("CC") || sight.image!!.credit!!.licence == "Public domain")
        val hotel = ok(EngineJson.poiDetails(envelope("poi_details-hotel.json")))
        assertTrue(hotel.isFictional)
        // release-s3: only single photographs may be area photos — when there is one, it is labelled as such
        hotel.image?.let { assertTrue(it.isArea); assertTrue(it.labelRu!!.startsWith("Фото района")) }
        val bar = ok(EngineJson.poiDetails(envelope("poi_details-bar.json")))
        assertEquals("bar", bar.kind)
        assertTrue(bar.attributionRu.isNotEmpty())
        val nf = EngineJson.poiDetails(envelope("poi_details-not-found.json"))
        assertEquals("NOT_FOUND", (nf as EngineResult.Err).error.code)

        val day = ok(EngineJson.handoff(envelope("handoff-car-day.json")))
        assertEquals("car", day.mode)
        assertTrue(day.parts.isNotEmpty() && day.parts.all { it.links.navigator!!.startsWith("yandexnavi://build_route_on_map?") })
        val walk = ok(EngineJson.handoff(envelope("handoff-walk.json")))
        // a long walk is split into parts (real catalogue): every part is a pedestrian web link, no navigator
        assertTrue(walk.parts.isNotEmpty())
        walk.parts.forEach { assertNull(it.links.navigator); assertTrue(it.links.web!!.endsWith("&rtt=pd")) }

        val presets = ok(EngineJson.cityPresets(envelope("city_presets.json")))
        assertEquals("Ярославль", presets.town!!.name)
        // availability comes from the data; the shape is fixed: the six presets (M4 adds «Прогулка с собакой»), custom always available
        assertEquals(setOf("overview", "museums", "dog_walk", "ryumochnye", "beer", "custom"), presets.presets.map { it.preset }.toSet())
        assertTrue(presets.presets.first { it.preset == "custom" }.available)
        assertTrue(presets.presets.first { it.preset == "ryumochnye" }.adultOnly)
        for (f in listOf("city_route-overview.json", "city_route-custom.json", "city_route-museums-spb.json", "city_route-ryumochnye.json")) {
            val w = ok(EngineJson.walkRoute(envelope(f)))
            assertTrue(f, w.stops.isNotEmpty())
            assertTrue(f, w.json.contains("\"stops\""))
        }
        val ry = ok(EngineJson.walkRoute(envelope("city_route-ryumochnye.json")))
        assertTrue(ry.adultOnly)
        assertTrue(ry.stops.all { it.isBar })
        assertEquals("NOT_ENOUGH_POIS", (EngineJson.walkRoute(envelope("city_route-error-not-enough.json")) as EngineResult.Err).error.code)
        assertEquals("NO_CITY", (EngineJson.walkRoute(envelope("city_route-error-no-city.json")) as EngineResult.Err).error.code)
        assertEquals("adultConfirmed", (EngineJson.walkRoute(envelope("city_route-error-adult.json")) as EngineResult.Err).error.field)
    }

    @Test
    fun walkRequestMatchesTheContractInput() {
        val input = (request("city_route-custom.json")["args"] as JsonObject)["input_json"] as JsonObject
        val mine = Json.parseToJsonElement(
            WalkRequest(GeoPoint("Ярославль, Советская площадь", 57.6261, 39.8845), "custom", 240, listOf("parks", "views", "food"), "slow").toInputJson(),
        ).jsonObject
        for (k in listOf("start", "preset", "interests", "durationMin", "pace")) assertEquals(k, input[k], mine[k])
    }

    @Test
    fun explicitRoomsInTheCalculator() {
        // ADR-0011: rooms × price with the engine's room count; null = ceil(adults / 2) (old cases unchanged).
        fun units(rooms: Int?, optRooms: Int?) = CostUnitsDto(
            fuel = app.verst.core.model.cost.FuelUnitsDto(consumption = 8.0),
            nights = listOf(
                NightUnitDto("d1s05", 1, "Ярославль", "h1", 6000, listOf(HotelPriceDto("h1", 6000, rooms = rooms), HotelPriceDto("h2", 8400, rooms = optRooms)), rooms = rooms),
            ),
        )
        val crew = CostCrew(adults = 4, children = 1, dog = true)
        val legacy = CostCalculator.recompute(units(null, null), crew, false, null)
        val family = CostCalculator.recompute(units(1, 1), crew, false, null)
        assertEquals(2 * 6000, legacy.lines.getValue("lodging"))
        assertEquals(1 * 6000, family.lines.getValue("lodging"))
        val picked = CostCalculator.recompute(units(2, 1), crew, false, null, app.verst.core.model.cost.CostOverridesDto(hotelByStop = mapOf("d1s05" to "h2")))
        assertEquals(1 * 8400, picked.lines.getValue("lodging"))
    }
}
