package app.verst.core.model

import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.LocalMoney
import app.verst.core.model.dto.PlanOutcome
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * CEO 29.10 (trips abroad, wave 1, server only): the server's answers decode. The samples in
 * `src/test/resources/abroad/` are real engine output — `mobile.plan` on `world_v1` with the CI fixture catalogues
 * (`backend/planner/tests/abroad_fixture.py`, golden clock 2026-10-23): Владикавказ → Тбилиси (the `done` body the
 * server streams) and Москва → Баку mapped to the API's error body (`verst_api.errors.from_envelope`).
 */
class AbroadDtoTest {
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")

    private fun resource(name: String): String = AbroadDtoTest::class.java.getResource("/abroad/$name")!!.readText()

    private fun plan() = (EngineJson.planOutcome("""{"ok":true,"result":${resource("plan-vladikavkaz-tbilisi.json")}}""") as EngineResult.Ok)
        .value.let { it as PlanOutcome.Plan }.result

    @Test
    fun theBorderStopDecodesWithItsFacts() {
        val trip = plan().trip
        assertTrue("distances abroad are the road model", trip.approxDistances)
        val stops = trip.daysList.flatMap { it.stops }
        val border = stops.single { it.kind == "border" }
        assertEquals("city", border.sign) // the engine's sign; the app draws its own «граница»
        assertEquals(120, border.dwellMin)
        assertFalse(border.replaceable)
        val b = border.border!!
        assertEquals("verkhny_lars", b.crossingId)
        assertEquals("RU" to "GE", b.from to b.to)
        assertEquals("Россия" to "Грузия", b.fromRu to b.toRu)
        assertFalse(b.marker)
        assertTrue(b.coordsApprox && b.coordsNoteRu!!.contains("Владикавказ"))
        assertFalse(b.waitKnown)
        assertTrue(b.waitRu!!.contains("неизвестно"))
        assertEquals(120, b.bufferMin)
        assertTrue(b.unverified)
        assertTrue("Загранпаспорт" in b.documents.map { it.textRu })
        assertEquals(4, b.facts.size)
        assertTrue(b.facts.all { f -> f.sources.isNotEmpty() && f.sources.all { it.url.startsWith("https://") && it.typeRu != null } })
        assertEquals(listOf(false), b.risks.map { it.appliesOnTripDate }) // October: the Nov–Mar risk does not apply
        val tpl = b.fees.first { it.key == "tpl" }
        assertTrue(tpl.mandatory)
        assertFalse(tpl.counted)
        assertEquals("secondary_source", tpl.notCountedWhy)
        assertEquals("GEL", tpl.currency)
        assertNull(tpl.amount)
        assertTrue(tpl.ruleSources.isNotEmpty())
        assertEquals("no_amount", b.fees.first { it.key == "medical" }.notCountedWhy)
    }

    @Test
    fun stopsAbroadHaveLocalTimeAndUnknownPrices() {
        val stops = plan().trip.daysList.flatMap { it.stops }
        val after = stops.drop(stops.indexOfFirst { it.kind == "border" } + 1)
        assertEquals(listOf("rest", "food", "finish"), after.map { it.kind })
        assertTrue(after.all { it.localTz == "Asia/Tbilisi" && it.localTimeRu!!.startsWith("По местному времени") })
        assertNull(stops.first().localTimeRu) // Владикавказ: the trip's own clock
        val food = stops.single { it.kind == "food" }
        assertTrue(food.priceUnknown)
        assertEquals(listOf("hours", "price"), food.unknownFacts)
        assertEquals(0, food.costRub)
        assertEquals("Цена за границей неизвестна — в рублёвый итог не входит", food.unknownRu)
    }

    @Test
    fun theAbroadBlockSaysWhatTheRoubleTotalLeavesOut() {
        val r = plan()
        val trip = r.trip
        val a = trip.abroad!!
        assertTrue(a.unverified)
        assertTrue(a.roubleTotalIncomplete)
        assertEquals(4, a.notInRoubleTotalRu.size)
        assertTrue(a.notInRoubleTotalRu.first().startsWith("Грузия: топливо"))
        assertNull(a.rates) // no Bank of Russia rates on the server: the lari stay lari
        val ge = a.countries.single()
        assertEquals("GE", ge.code)
        assertEquals("Грузия", ge.nameRu)
        assertEquals("GEL", ge.currency)
        assertTrue(ge.km > 0)
        val fuel = ge.fuel!!
        assertEquals("ai95", fuel.fuelType)
        assertEquals("4.29", fuel.pricePerLitre)
        assertEquals(listOf("4.16", "4.29"), fuel.priceRange)
        assertEquals("39.90", fuel.amount)
        assertNull(fuel.rub)
        assertFalse(fuel.inRoubleTotal)
        assertEquals("unknown", ge.tolls!!.status)
        assertEquals(1, ge.mealsUnpriced)
        assertEquals("≈ 40 GEL", LocalMoney.approx(a.localTotals.single().amount, a.localTotals.single().currency))
        assertTrue(trip.cost.totalNoteRu!!.contains("За границей посчитано не всё"))
        assertTrue(trip.warnings.any { it.code == "ABROAD" && it.level == "info" })
        // the private trip JSON keeps the block for the next engine call and for saving
        assertTrue(r.tripJson.contains("\"roubleTotalIncomplete\""))
    }

    @Test
    fun aTripInRussiaHasNoAbroadParts() {
        val trip = EngineJson.trip(root.resolve("backend/planner/tests/golden/snapshots/G02_golden_ring.json").readText())
        assertNull(trip.abroad)
        val stops = trip.daysList.flatMap { it.stops }
        assertTrue(stops.none { it.border != null || it.priceUnknown || it.localTimeRu != null })
    }

    @Test
    fun theClosedBorderIsAFinalVerdictWithTheServersSentence() {
        // the API body, flattened like ServerClient does (`details` into the error object)
        val body = Json.parseToJsonElement(resource("error-border-closed.json")).jsonObject["error"]!!.jsonObject
        val flat = JsonObject(body.filterKeys { it != "details" } + body["details"]!!.jsonObject)
        val e = EngineJson.json.decodeFromJsonElement(EngineErrorDto.serializer(), flat)
        assertEquals("INVALID_INPUT", e.code)
        assertEquals("border_closed", e.reason)
        assertEquals("AZ", e.country)
        assertEquals("2027-01-02T06:00:00+04:00", e.until)
        assertTrue(e.abroadVerdict)
        assertTrue(e.abroadText!!.startsWith("Граница закрыта для легковых до 2 января 2027"))
        // the phone bridge's shape: a diagnostic `message`, the sentence in `messageRu`
        val bridge = EngineJson.planOutcome(
            """{"ok":false,"error":{"code":"INVALID_INPUT","message":"destination: no_crossing","field":"destination","reason":"no_crossing","messageRu":"Нет перехода"}}""",
        ) as EngineResult.Err
        assertEquals("Нет перехода", bridge.error.abroadText)
        // a request the server's schema rejected is not a verdict about the place
        val schema = EngineErrorDto("INVALID_INPUT", "Проверьте параметры поездки", field = "mood")
        assertFalse(schema.abroadVerdict)
        assertNull(schema.abroadText)
    }

    @Test
    fun localMoneyShareTextAndTheRequest() {
        assertEquals("≈ 37 GEL", LocalMoney.approx("36.89", "GEL"))
        assertEquals("≈ 10${RuFormat.THIN}000 AMD", LocalMoney.approx("10000", "AMD"))
        assertNull(LocalMoney.approx(null, "GEL"))
        assertNull(LocalMoney.approx("12", null))
        assertNull(LocalMoney.approx("n/a", "GEL"))

        val share = plan().shareText
        val note = "без расходов за границей"
        val shared = ShareText.withAbroad(share, incomplete = true, note = note)
        assertEquals("Итого ≈ 300 ₽ на 2 чел. — без расходов за границей", shared.lines().last())
        assertEquals(share.lines().dropLast(1), shared.lines().dropLast(1))
        assertEquals(shared, ShareText.withAbroad(shared, incomplete = true, note = note)) // said once
        assertEquals(share, ShareText.withAbroad(share, incomplete = false, note = note))

        // routing only: the flag never reaches the engine
        val tbilisi = PlanRequest(DefaultOrigin, GeoPoint("Тбилиси", 41.7151, 44.8271), abroad = true)
        assertFalse("abroad" in Json.parseToJsonElement(tbilisi.toInputJson()).jsonObject)
        assertFalse(PlanRequest(DefaultOrigin, GeoPoint("Тбилиси", 41.7151, 44.8271)).abroad)
    }
}
