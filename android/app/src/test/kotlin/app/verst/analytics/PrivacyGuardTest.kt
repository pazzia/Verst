package app.verst.analytics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** R-07 / SPEC §16: [PrivacyGuard] catches personal data, and [GuardedAnalytics] never sends an event that has it. */
class PrivacyGuardTest {
    private fun rules(v: Any) = PrivacyGuard.violations(mapOf("value" to v))

    @Test
    fun coordinatesEmailsPhonesAndFreeTextAreCaught() {
        assertEquals(listOf("coordinates"), rules("55.7558"))
        assertEquals(listOf("coordinates"), rules("55,7558 37,6173"))
        assertEquals(listOf("coordinates"), rules("lat=57.6261;lon=39.8845"))
        assertEquals(listOf("type"), rules(55.7558)) // a Double never goes out
        assertEquals(listOf("type"), rules(37.6f))
        assertEquals(listOf("email"), rules("ivan@example.ru"))
        assertEquals(listOf("email"), rules("ivan@mail"))
        assertEquals(listOf("phone"), rules("+7 (916) 123-45-67"))
        assertEquals(listOf("phone"), rules("89161234567"))
        assertEquals(listOf("phone"), rules("тел 8-916-123-45-67"))
        assertEquals(listOf("free_text"), rules("Мы заехали в кафе у дороги, было очень вкусно"))
        assertEquals(listOf("free_text"), rules("две\nстроки"))
        assertEquals(listOf("free_text"), rules("x".repeat(PrivacyGuard.MAX_TEXT + 1)))
        assertEquals(listOf("coordinates", "free_text"), rules("Москва, ул. Тверская, 7 (55.7646, 37.6050)"))
    }

    @Test
    fun personalDataKeysAreCaught() {
        for (k in listOf("lat", "lon", "address", "email", "phone", "name", "query", "comment", "Trip_Id", "trip id", "")) {
            assertEquals(k, listOf("key"), PrivacyGuard.violations(mapOf(k to 1)))
        }
    }

    @Test
    fun theValuesTheAppSendsPass() {
        val clean = listOf(
            "2026-10-24", "123e4567-e89b-42d3-a456-426614174000", "12345678-1234-4123-8123-123456789012",
            "150-300", "<150", ">1200", "8-12k", "3+", "Москва", "Нижний Новгород", "Петропавловск-Камчатский",
            "d1s06", "rr_golden_ring", "pl_yar_spaso", "Q1078595", "osm_123456789", "UNREACHABLE", "yandex_navigator",
            "2gis", "none", 0, 1_200L, true, "x".repeat(PrivacyGuard.MAX_TEXT),
        )
        for (v in clean) assertEquals("$v", emptyList<String>(), rules(v))
    }

    @Test
    fun aDirtyEventIsDroppedWholeAndOnlyItsRuleNamesAreReported() {
        val sent = mutableListOf<String>()
        val dropped = mutableListOf<Pair<String, List<String>>>()
        val a = GuardedAnalytics({ name, _ -> sent += name }, { name, rules -> dropped += name to rules })
        a.track(AnalyticsEvent.ReadyRouteShown(3, "Москва"))
        a.track(AnalyticsEvent.ReadyRouteShown(3, "ivan@example.ru")) // a start_city that is not a town
        a.track(AnalyticsEvent.ReadyRouteShown(3, "Тверская 7, 55.7646 37.6050"))
        a.track(AnalyticsEvent.ProWaitlistJoined("79161234567")) // a phone that looks like a token is still a phone
        assertEquals(listOf("ready_route_shown"), sent)
        assertEquals(
            listOf("ready_route_shown" to listOf("email"), "ready_route_shown" to listOf("coordinates"), "pro_waitlist_joined" to listOf("phone")),
            dropped,
        )
    }

    @Test
    fun eventsWithoutAUiYetAndExtremeValuesStayInsideThePlan() {
        val id = "123e4567-e89b-42d3-a456-426614174000"
        val events = listOf(
            AnalyticsEvent.ExcursionLinkClicked(id, "pl_yar_spaso"),
            AnalyticsEvent.ExcursionLinkClicked(null, "Q1078595"),
            AnalyticsEvent.ProWaitlistJoined("waybill"),
            AnalyticsEvent.PlanFailed(0, "some engine message, not a code"), // → OTHER
            AnalyticsEvent.HotelLinkClicked(null, "d9s99", Buckets.price(null)),
            AnalyticsEvent.ReadyRouteShown(0, AnalyticsEvent.OTHER),
            AnalyticsEvent.PlanRequested(Buckets.km(null), null, true, Buckets.children(7), null, AnalyticsEvent.NO_READY_ROUTE),
            AnalyticsEvent.TripSaved(id, null, 1, "rr_golden_ring"),
            AnalyticsEvent.NavigatorOpened(id, AnalyticsEvent.NaviApp.TWO_GIS, null),
            AnalyticsEvent.TripDrivenConfirmed(id, AnalyticsEvent.Completion.FULL, 14, Buckets.km(5_000), false, "3+"),
        )
        TrackingPlanContract.assertClean(events)
        assertEquals("OTHER", events[3].params()["error_code"])
        assertTrue(events.all { e -> e.params().values.none { it is Double || it is Float } })
    }
}
