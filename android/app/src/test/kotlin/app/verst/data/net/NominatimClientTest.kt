package app.verst.data.net

import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** DEV-302 acceptance on MockWebServer: one request per submit, the UA header, the 1 req/s bucket, offline, the cache. */
class NominatimClientTest {
    private val server = MockWebServer()
    private var online = true
    private lateinit var client: NominatimClient
    private val body = """[{"place_id": 7, "lat": "57.6266", "lon": "39.8938", "display_name": "1, Советская улица, Ярославль",
        "address": {"house_number": "1", "road": "Советская улица", "city": "Ярославль"}}]"""

    @Before
    fun start() {
        server.start()
        val http = OkHttpClient.Builder().addInterceptor(Net.userAgent).build()
        client = NominatimClient({ http }, server.url("/").toString(), { online })
    }

    @After
    fun stop() = server.shutdown()

    @Test
    fun oneRequestWithTheUserAgentAndTheRussianParameters() = runBlocking {
        server.enqueue(MockResponse().setBody(body))
        val r = client.search("Ярославль Советская 1") as AddressResult.Ok
        assertEquals("Советская улица, 1", r.value.single().name)
        assertEquals("Ярославль", r.value.single().subtitle)
        assertEquals(1, server.requestCount)
        val rq = server.takeRequest()
        assertEquals(Net.USER_AGENT, rq.getHeader("User-Agent"))
        val url = rq.requestUrl!!
        // CEO 29.10: the whole world — no country filter (the viewbox near the user still ranks local streets first)
        assertNull("no country restriction", url.queryParameter("countrycodes"))
        assertEquals("ru", url.queryParameter("accept-language"))
        assertEquals("10", url.queryParameter("limit"))
        assertEquals("Ярославль Советская 1", url.queryParameter("q"))
        assertNull("no place, no box", url.queryParameter("viewbox"))
        // the 24 h cache: the same query sends nothing
        client.search("Ярославль Советская 1")
        assertEquals(1, server.requestCount)
    }

    /** CEO 29.10: «Ленина 5» near Фрязино ranks Фрязино's street first (a preferred box, not a limit). */
    @Test
    fun theUsersPlaceBiasesTheSearch() = runBlocking {
        server.enqueue(MockResponse().setBody(body))
        client.search("Ленина 5", app.verst.core.model.GeoPoint("Фрязино", 55.96, 38.05))
        val url = server.takeRequest().requestUrl!!
        assertEquals("37.6500,56.3600,38.4500,55.5600", url.queryParameter("viewbox"))
        assertEquals("0", url.queryParameter("bounded"))
    }

    /** CEO 29.10: a foreign row names its country and carries the code; a Russian row stays the city alone. */
    @Test
    fun aForeignRowCarriesItsCountry() {
        val rows = NominatimClient.parseSearch(
            """[{"place_id": 9, "lat": "50.0874", "lon": "14.4213", "name": "Прага", "display_name": "Прага, Чехия",
                "address": {"city": "Прага", "country": "Чехия", "country_code": "cz"}},
               {"place_id": 10, "lat": "50.0870", "lon": "14.4200", "display_name": "5, Карлова, Прага, Чехия",
                "address": {"road": "Карлова", "house_number": "5", "city": "Прага", "country": "Чехия", "country_code": "cz"}},
               {"place_id": 7, "lat": "57.6266", "lon": "39.8938", "display_name": "1, Советская улица, Ярославль, Россия",
                "address": {"house_number": "1", "road": "Советская улица", "city": "Ярославль", "country": "Россия", "country_code": "ru"}}]""",
        )
        assertEquals(listOf("Прага", "Карлова, 5", "Советская улица, 1"), rows.map { it.name })
        assertEquals(listOf("Прага · Чехия", "Прага · Чехия", "Ярославль"), rows.map { it.subtitle })
        assertEquals(listOf("cz", "cz", "ru"), rows.map { it.countryCode })
        assertEquals(listOf(true, true, false), rows.map { it.abroad })
        // an old row without a country code is Russia (the engine's rows never carry one)
        assertFalse(NominatimClient.parseSearch(body).single().abroad)
        assertEquals("Чехия", NominatimClient.subtitle(null, "Чехия", "cz"))
    }

    @Test
    fun twoSubmitsWithinASecondAreSpacedByTheBucket() = runBlocking {
        server.enqueue(MockResponse().setBody(body))
        server.enqueue(MockResponse().setBody("[]"))
        val t0 = System.nanoTime()
        client.search("Советская 1")
        client.search("Тверская 2")
        val ms = (System.nanoTime() - t0) / 1_000_000
        assertEquals(2, server.requestCount)
        assertTrue("the second request waited for the bucket: $ms ms", ms >= 950)
    }

    @Test
    fun offlineSendsNothing() = runBlocking {
        online = false
        assertEquals(AddressResult.Offline, client.search("Советская 1"))
        assertEquals(0, server.requestCount)
    }

    @Test
    fun reverseGivesTheStreetLabel() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"address": {"road": "Советская площадь", "house_number": "1"}, "display_name": "x"}"""))
        assertEquals("Советская площадь, 1", (client.reverse(57.6261, 39.8845) as AddressResult.Ok).value)
        assertEquals("57.626100", server.takeRequest().requestUrl!!.queryParameter("lat"))
    }

    @Test
    fun anHttpErrorIsAFailureNotACrash() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(503))
        assertTrue(client.search("Советская 1") is AddressResult.Failed)
    }

    /** Designer В-2: nothing to connect to (airplane mode the system has not noticed yet) is offline, not «try again». */
    @Test
    fun noConnectionIsOffline() = runBlocking {
        server.shutdown()
        assertEquals(AddressResult.Offline, client.search("Советская 1"))
    }
}
