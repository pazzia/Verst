package app.verst.analytics

/**
 * The app events of SPEC §15 + ENG-05 (`docs/traction/tracking-plan.md` §2.2–2.4), one class per event, with
 * typed properties. [params] is what is sent: `snake_case` keys, values Int / Long / Boolean or a short token
 * from a fixed list (buckets, enums, ids). No coordinates, addresses or text the user typed; the only free word is
 * `start_city`, which is the engine's catalogue town of the start (never the address picked or the GPS point).
 *
 * `trip_id` is a random UUID made on the phone for each ПОЕХАЛИ (kept through replace, re-cost and «Подогнать под
 * бюджет»); once the trip is saved it is also the trip's key in «Мои поездки». It is omitted where there is no trip.
 * `device_id` and the app version are added by AppMetrica itself and are not repeated here.
 */
sealed class AnalyticsEvent(val name: String) {
    abstract fun params(): Map<String, Any>

    /** Builds a property map, dropping null values. */
    protected fun props(vararg pairs: Pair<String, Any?>): Map<String, Any> =
        linkedMapOf<String, Any>().apply { for ((k, v) in pairs) if (v != null) put(k, v) }

    /** The app came to the foreground (§2.2): a new process ([StartType.COLD]) or back from the background. */
    data class AppOpen(val start: StartType, val offline: Boolean) : AnalyticsEvent("app_open") {
        override fun params() = props("start_type" to start.wire, "offline" to offline)
    }

    /** The Windshield list was shown, once per showing; [count] = ready routes the engine has for this start (0 too). */
    data class ReadyRouteShown(val count: Int, val startCity: String) : AnalyticsEvent("ready_route_shown") {
        override fun params() = props("count" to count, "start_city" to startCity)
    }

    /** A ready-route row was tapped; [rank] = its row from 1. */
    data class ReadyRouteSelected(val routeId: String, val rank: Int) : AnalyticsEvent("ready_route_selected") {
        override fun params() = props("route_id" to Buckets.token(routeId), "rank" to rank)
    }

    /** The first suggestion request of one Navigator visit; only the query's length is sent. */
    data class SearchStarted(val queryLen: Int) : AnalyticsEvent("search_started") {
        override fun params() = props("query_len" to queryLen)
    }

    /** A suggestion was picked; [rank] = its row from 1 (0 = not from a shown list). */
    data class SearchSelected(val queryLen: Int, val resultType: SearchResultType, val rank: Int) : AnalyticsEvent("search_selected") {
        override fun params() = props("query_len" to queryLen, "result_type" to resultType.wire, "rank" to rank)
    }

    /** One Instruments value changed; [valueBucket] per §2.4 (see [Buckets]). */
    data class ParamsChanged(val field: ParamField, val valueBucket: String) : AnalyticsEvent("params_changed") {
        override fun params() = props("field" to field.wire, "value_bucket" to valueBucket)
    }

    /**
     * ПОЕХАЛИ on Instruments; [days] = the engine's estimate, null when it had not answered yet; [readyRouteId] = the
     * ready-route template (`rr_golden_ring`) or [NO_READY_ROUTE] for a free A → B trip (regional pilot report).
     */
    data class PlanRequested(
        val kmBucket: String,
        val days: Int?,
        val dog: Boolean,
        val children: String,
        val mood: String?,
        val readyRouteId: String,
    ) : AnalyticsEvent("plan_requested") {
        override fun params() = props(
            "km_bucket" to kmBucket, "days" to days, "dog" to dog, "children" to children, "mood" to mood,
            "ready_route_id" to Buckets.token(readyRouteId),
        )
    }

    /** The plan came back with a trip; [latencyMs] = engine time from the start of the plan to its result. */
    data class PlanSucceeded(
        val tripId: String,
        val latencyMs: Long,
        val routingSource: RoutingSource,
        val readyRouteId: String,
    ) : AnalyticsEvent("plan_succeeded") {
        override fun params() = props(
            "trip_id" to tripId, "latency_ms" to latencyMs, "routing_source" to routingSource.wire,
            "ready_route_id" to Buckets.token(readyRouteId),
        )
    }

    /** The plan failed or timed out ([errorCode] = the engine code; `NO_FIT` = no trip within the budget). */
    data class PlanFailed(val latencyMs: Long, val errorCode: String) : AnalyticsEvent("plan_failed") {
        override fun params() = props("latency_ms" to latencyMs, "error_code" to Buckets.token(errorCode))
    }

    /** An alternative replaced a stop; [kind] = the stop kind, [altRank] = the alternative's row from 1. */
    data class StopReplaced(val tripId: String?, val kind: String, val altRank: Int) : AnalyticsEvent("stop_replaced") {
        override fun params() = props("trip_id" to tripId, "kind" to Buckets.token(kind), "alt_rank" to altRank)
    }

    data class WaybillOpened(val tripId: String?, val totalBucket: String, val overBudget: Boolean) : AnalyticsEvent("waybill_opened") {
        override fun params() = props("trip_id" to tripId, "total_bucket" to totalBucket, "over_budget" to overBudget)
    }

    data class ReserveToggled(val tripId: String?, val on: Boolean) : AnalyticsEvent("reserve_toggled") {
        override fun params() = props("trip_id" to tripId, "state" to if (on) "on" else "off")
    }

    /** «Забронировать ночь» for overnight stop [stopId] (the engine's stop id, e.g. `d1s06`). */
    data class HotelLinkClicked(val tripId: String?, val stopId: String, val priceBucket: String) : AnalyticsEvent("hotel_link_clicked") {
        override fun params() = props("trip_id" to tripId, "stop_id" to Buckets.token(stopId), "price_bucket" to priceBucket)
    }

    /** An excursion link was opened (SPEC §14). Defined for the schema; the app has no excursion link yet. */
    data class ExcursionLinkClicked(val tripId: String?, val placeId: String) : AnalyticsEvent("excursion_link_clicked") {
        override fun params() = props("trip_id" to tripId, "place_id" to Buckets.token(placeId))
    }

    /** The route went to a navigator / maps app (or the web maps); [day] = the trip day handed off. */
    data class NavigatorOpened(val tripId: String?, val app: NaviApp, val day: Int?) : AnalyticsEvent("navigator_opened") {
        override fun params() = props("trip_id" to tripId, "app" to app.wire, "day" to day)
    }

    /** The trip was saved on the phone; [startDate] `yyyy-mm-dd` of day 1, [days] the trip's days. */
    data class TripSaved(val tripId: String, val startDate: String?, val days: Int, val readyRouteId: String) : AnalyticsEvent("trip_saved") {
        override fun params() = props("trip_id" to tripId, "start_date" to startDate, "days" to days, "ready_route_id" to Buckets.token(readyRouteId))
    }

    data class TripShared(val tripId: String?, val channel: ShareChannel) : AnalyticsEvent("trip_shared") {
        override fun params() = props("trip_id" to tripId, "channel" to channel.wire)
    }

    /** «Хочу Pro» sent (BIZ-06). Defined for the schema; the app has no Pro form yet. */
    data class ProWaitlistJoined(val source: String) : AnalyticsEvent("pro_waitlist_joined") {
        override fun params() = props("source" to Buckets.token(source))
    }

    /** D-7 report sent; [kind] = the reason (`closed`, `tags`, `price`, `other`). The comment is never sent. */
    data class FeedbackSent(val tripId: String?, val kind: String) : AnalyticsEvent("feedback_sent") {
        override fun params() = props("trip_id" to tripId, "kind" to Buckets.token(kind))
    }

    /** ENG-05 (§2.3): the user confirmed driving the saved trip, fully or in part. */
    data class TripDrivenConfirmed(
        val tripId: String,
        val completion: Completion,
        val daysSinceEnd: Int,
        val kmBucket: String,
        val dog: Boolean,
        val children: String,
        val source: DrivenSource = DrivenSource.IN_APP_PROMPT,
    ) : AnalyticsEvent("trip_driven_confirmed") {
        override fun params() = props(
            "trip_id" to tripId, "completion" to completion.wire, "days_since_end" to daysSinceEnd,
            "km_bucket" to kmBucket, "dog" to dog, "children" to children, "source" to source.wire,
        )
    }

    enum class StartType(val wire: String) { COLD("cold"), WARM("warm") }

    enum class SearchResultType(val wire: String) {
        CITY("city"), ADDRESS("address"), PLACE("place"), PIN("pin");

        companion object {
            /** Suggestion kinds: `city`, `address` (Nominatim), `place` / `poi` (catalogue / OSM-only place). */
            fun of(kind: String): SearchResultType = when (kind) {
                "city" -> CITY
                "address" -> ADDRESS
                "pin" -> PIN
                else -> PLACE
            }
        }
    }

    /** `params_changed.field`: the Instruments values that exist today (fuel and date have no control yet). */
    enum class ParamField(val wire: String) { ADULTS("adults"), CHILDREN("children"), DOG("dog"), PACE("pace"), BUDGET("budget") }

    /** `road` = the engine's road graph; `fallback` = the synthetic route (`approxDistances`). */
    enum class RoutingSource(val wire: String) { ROAD("road"), FALLBACK("fallback") }

    /** `web` = the maps site in the browser (no maps app on the phone). */
    enum class NaviApp(val wire: String) { YANDEX_NAVIGATOR("yandex_navigator"), YANDEX_MAPS("yandex_maps"), TWO_GIS("2gis"), WEB("web") }

    /** `unknown`: the system share sheet does not tell the app which app was chosen. */
    enum class ShareChannel(val wire: String) { MESSENGER("messenger"), SOCIAL("social"), OTHER("other"), UNKNOWN("unknown") }

    enum class Completion(val wire: String) { FULL("full"), PARTIAL("partial") }

    enum class DrivenSource(val wire: String) { IN_APP_PROMPT("in_app_prompt") }

    companion object {
        /** `start_city` when the start is not within 30 km of a catalogue town. */
        const val OTHER = "other"

        /** `ready_route_id` of a free A → B trip. */
        const val NO_READY_ROUTE = "none"
    }
}
