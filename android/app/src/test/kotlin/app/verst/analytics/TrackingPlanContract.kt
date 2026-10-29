package app.verst.analytics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue

/**
 * `docs/traction/tracking-plan.md` §2.2–2.4 as data: each event's properties and each property's allowed values.
 * An event the app sends with a key or a value outside this contract fails the tests, so a new property cannot
 * slip in without the plan (§0.1, §2.5) and the dev-notes being changed with it.
 */
object TrackingPlanContract {
    /** Event → its properties (all optional on the wire; `trip_id` is omitted where there is no trip). */
    val EVENTS: Map<String, Set<String>> = mapOf(
        "app_open" to setOf("start_type", "offline"),
        "ready_route_shown" to setOf("count", "start_city"),
        "ready_route_selected" to setOf("route_id", "rank"),
        "search_started" to setOf("query_len"),
        "search_selected" to setOf("query_len", "result_type", "rank"),
        "params_changed" to setOf("field", "value_bucket"),
        "plan_requested" to setOf("km_bucket", "days", "dog", "children", "mood", "ready_route_id"),
        "plan_succeeded" to setOf("trip_id", "latency_ms", "routing_source", "ready_route_id"),
        "plan_failed" to setOf("latency_ms", "error_code"),
        "stop_replaced" to setOf("trip_id", "kind", "alt_rank"),
        "waybill_opened" to setOf("trip_id", "total_bucket", "over_budget"),
        "reserve_toggled" to setOf("trip_id", "state"),
        "hotel_link_clicked" to setOf("trip_id", "stop_id", "price_bucket"),
        "excursion_link_clicked" to setOf("trip_id", "place_id"),
        "navigator_opened" to setOf("trip_id", "app", "day"),
        "trip_saved" to setOf("trip_id", "start_date", "days", "ready_route_id"),
        "trip_shared" to setOf("trip_id", "channel"),
        "pro_waitlist_joined" to setOf("source"),
        "feedback_sent" to setOf("trip_id", "kind"),
        "trip_driven_confirmed" to setOf("trip_id", "completion", "days_since_end", "km_bucket", "dog", "children", "source"),
    )

    private val TOKEN = Regex("[A-Za-z0-9_]{1,32}")
    private val UUID = Regex("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    private val DATE = Regex("\\d{4}-\\d{2}-\\d{2}")

    /** A town name: letters, spaces and hyphens (no digits, no punctuation an address would need). */
    private val TOWN = Regex("[\\p{L}][\\p{L} \\-]{0,39}")

    /** `params_changed.value_bucket`: adults 1–7, pace 150–900, budget `20k`…`80k` / `none`, dog `yes` / `no`. */
    private val BUCKET = Regex("[1-7]|[1-9]\\d0|yes|no|\\d{2}k|none")

    private fun oneOf(vararg allowed: String): (Any) -> Boolean = { v: Any -> v is String && v in allowed }
    private val count: (Any) -> Boolean = { v: Any -> (v is Int && v >= 0) || (v is Long && v >= 0) }
    private val bool: (Any) -> Boolean = { v: Any -> v is Boolean }
    private val token: (Any) -> Boolean = { v: Any -> v is String && TOKEN.matches(v) }

    private val KM = arrayOf("<150", "150-300", "300-500", "500-800", "800-1200", ">1200", "unknown")
    private val CHILDREN = arrayOf("0", "1", "2", "3+")

    /** Property → its allowed values (§2.4). */
    val VALUES: Map<String, (Any) -> Boolean> = mapOf(
        "start_type" to oneOf("cold", "warm"),
        "offline" to bool,
        "count" to count,
        "start_city" to { v: Any -> v is String && TOWN.matches(v) },
        "route_id" to token,
        // Manager (regional pilot report): the template id, or `none` for a free A → B trip
        "ready_route_id" to { v: Any -> v is String && (v == "none" || Regex("rr_[a-z0-9_]{1,29}").matches(v)) },
        "rank" to count,
        "query_len" to count,
        "result_type" to oneOf("city", "address", "place", "pin"),
        "field" to oneOf("adults", "children", "dog", "pace", "budget"),
        "value_bucket" to { v: Any -> v is String && (v in CHILDREN || BUCKET.matches(v)) },
        "km_bucket" to oneOf(*KM),
        "days" to count,
        "dog" to bool,
        "children" to oneOf(*CHILDREN),
        "mood" to oneOf("calm", "fun", "just_drive"),
        "trip_id" to { v: Any -> v is String && UUID.matches(v) },
        "latency_ms" to count,
        "routing_source" to oneOf("road", "fallback"),
        "error_code" to token,
        "kind" to token,
        "alt_rank" to count,
        "total_bucket" to oneOf("<10k", "10-20k", "20-40k", "40-80k", ">80k"),
        "over_budget" to bool,
        "state" to oneOf("on", "off"),
        "stop_id" to token,
        "price_bucket" to oneOf("<3k", "3-5k", "5-8k", "8-12k", ">12k", "unknown"),
        "place_id" to token,
        "app" to oneOf("yandex_navigator", "yandex_maps", "google_maps", "2gis", "web"),
        "day" to count,
        "start_date" to { v: Any -> v is String && DATE.matches(v) },
        "channel" to oneOf("messenger", "social", "other", "unknown"),
        "source" to token,
        "completion" to oneOf("full", "partial"),
        "days_since_end" to count,
    )

    /** Every event passes [PrivacyGuard] and stays inside the contract. */
    fun assertClean(events: List<AnalyticsEvent>) {
        for (e in events) {
            val params = e.params()
            assertEquals("${e.name}: privacy", emptyList<String>(), PrivacyGuard.violations(params))
            val keys = EVENTS[e.name] ?: error("${e.name} is not in the tracking plan")
            assertTrue("${e.name}: keys ${params.keys} outside $keys", keys.containsAll(params.keys))
            for ((k, v) in params) assertTrue("${e.name}.$k = $v", VALUES.getValue(k)(v))
        }
    }
}
