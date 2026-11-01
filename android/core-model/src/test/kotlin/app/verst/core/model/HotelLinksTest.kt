package app.verst.core.model

import app.verst.core.model.dto.CrewDto
import app.verst.core.model.dto.StopDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class HotelLinksTest {
    private val night = StopDto(id = "d1_night", kind = "overnight", sign = "hotel", name = "Ярославль", arriveAt = "2026-10-24T14:54")

    @Test
    fun theOvernightTownNightAndCrew() {
        val q = HotelLinks.forStop(night, CrewDto(adults = 2, children = 2), "trip7", "pl_yar_hotel_strelka")!!
        assertEquals("2026-10-24", q.checkin)
        assertEquals("2026-10-25", q.checkout())
        assertEquals(listOf(8, 8), q.childrenAges)
        // the same URL as verst-api links.hotel_search_url (Python urlencode: spaces as +, Cyrillic as UTF-8 %XX)
        assertEquals(
            "https://travel.yandex.ru/hotels/search/?text=%D0%AF%D1%80%D0%BE%D1%81%D0%BB%D0%B0%D0%B2%D0%BB%D1%8C" +
                "&checkinDate=2026-10-24&checkoutDate=2026-10-25&adults=2&childrenAges=8%2C8",
            q.plainUrl(),
        )
    }

    @Test
    fun noDateNoLink() {
        assertNull(HotelLinks.forStop(night.copy(arriveAt = null), CrewDto(), null, null))
        assertNull(HotelLinks.forStop(night.copy(arriveAt = "soon"), CrewDto(), null, null))
    }

    @Test
    fun adultsOnlyHasNoChildrenParameter() {
        val q = HotelLinks.forStop(night.copy(name = "Великий Новгород"), CrewDto(adults = 1), null, null)!!
        assertEquals(
            "https://travel.yandex.ru/hotels/search/?text=%D0%92%D0%B5%D0%BB%D0%B8%D0%BA%D0%B8%D0%B9+%D0%9D%D0%BE%D0%B2%D0%B3%D0%BE%D1%80%D0%BE%D0%B4" +
                "&checkinDate=2026-10-24&checkoutDate=2026-10-25&adults=1",
            q.plainUrl(),
        )
    }
}
