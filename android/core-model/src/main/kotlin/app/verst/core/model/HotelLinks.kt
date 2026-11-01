package app.verst.core.model

import app.verst.core.model.dto.CrewDto
import app.verst.core.model.dto.StopDto
import java.net.URLEncoder

/**
 * ENG-03 (CEO 01.11 «прикрутить настоящее»): «Забронировать ночь» opens a real hotel search for the overnight town,
 * the night and the crew. The plain URL is built here, the same as verst-api `links.hotel_search_url`; with the
 * tester's consent the app asks the server first (`GET /v1/links/hotel`), which wraps it into the partner link when
 * the Travelpayouts account is configured (docs/partners/hotel-affiliate.md).
 */
data class HotelLinkQuery(
    val placeId: String?,
    val town: String,
    /** ISO date of the check-in (the overnight's arrival day). */
    val checkin: String,
    val nights: Int,
    val adults: Int,
    val childrenAges: List<Int>,
    val tripId: String?,
    val stopId: String,
) {
    /** The Yandex Travel city search without any partner marker. */
    fun plainUrl(): String {
        val q = buildList {
            add("text" to town)
            add("checkinDate" to checkin)
            add("checkoutDate" to checkout())
            add("adults" to adults.toString())
            if (childrenAges.isNotEmpty()) add("childrenAges" to childrenAges.joinToString(","))
        }
        return HotelLinks.SEARCH + "?" + q.joinToString("&") { (k, v) -> "$k=" + URLEncoder.encode(v, "UTF-8") }
    }

    fun checkout(): String = java.time.LocalDate.parse(checkin).plusDays(nights.toLong()).toString()
}

object HotelLinks {
    const val SEARCH = "https://travel.yandex.ru/hotels/search/"

    /**
     * The engine's own assumption for a child of unknown age (planner_config.json `cost.assumed_child_age`); the
     * partner's form needs an age per child, and the traveller can change it there.
     */
    const val ASSUMED_CHILD_AGE = 8

    /** The query for an overnight [stop] (its town and arrival day), or null when the stop has no date. */
    fun forStop(stop: StopDto, crew: CrewDto, tripId: String?, placeId: String?): HotelLinkQuery? {
        val day = stop.arriveAt?.take(10)?.takeIf { it.length == 10 && runCatching { java.time.LocalDate.parse(it) }.isSuccess }
            ?: return null
        return HotelLinkQuery(
            placeId = placeId,
            town = stop.name,
            checkin = day,
            nights = 1,
            adults = crew.adults.coerceIn(1, 7),
            childrenAges = List(crew.children.coerceIn(0, 5)) { ASSUMED_CHILD_AGE },
            tripId = tripId,
            stopId = stop.id,
        )
    }
}
