package app.verst.analytics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Tracking plan §2.4 boundaries: a bucket holds its lower bound. */
class BucketsTest {
    @Test
    fun km() {
        val cases = mapOf(
            0 to "<150", 149 to "<150", 150 to "150-300", 299 to "150-300", 300 to "300-500", 500 to "500-800",
            542 to "500-800", 799 to "500-800", 800 to "800-1200", 1_199 to "800-1200", 1_200 to ">1200", 3_000 to ">1200",
        )
        for ((km, b) in cases) assertEquals("$km", b, Buckets.km(km))
        assertEquals("unknown", Buckets.km(null))
    }

    @Test
    fun totalAndPrice() {
        assertEquals("<10k", Buckets.total(9_999))
        assertEquals("10-20k", Buckets.total(10_000))
        assertEquals("10-20k", Buckets.total(16_500))
        assertEquals("20-40k", Buckets.total(39_999))
        assertEquals("40-80k", Buckets.total(40_000))
        assertEquals(">80k", Buckets.total(80_000))
        assertEquals("<3k", Buckets.price(2_999))
        assertEquals("3-5k", Buckets.price(3_000))
        assertEquals("5-8k", Buckets.price(6_000))
        assertEquals("8-12k", Buckets.price(8_000))
        assertEquals(">12k", Buckets.price(12_000))
        assertEquals("unknown", Buckets.price(0))
        assertEquals("unknown", Buckets.price(null))
    }

    @Test
    fun crewPaceBudgetDateToken() {
        assertEquals(listOf("0", "1", "2", "3+", "3+"), listOf(0, 1, 2, 3, 5).map(Buckets::children))
        assertEquals(listOf("1", "5", "7"), listOf(1, 5, 9).map(Buckets::adults))
        assertEquals(listOf("150", "350", "900"), listOf(150, 350, 900).map(Buckets::pace))
        assertEquals(listOf("20k", "60k", "42k", "none"), listOf(20_000, 60_000, 42_000, null).map(Buckets::budget))
        assertEquals("2026-10-24", Buckets.date("2026-10-24T08:00"))
        assertEquals("2026-10-24", Buckets.date("2026-10-24"))
        assertNull(Buckets.date("24.10.2026"))
        assertNull(Buckets.date(null))
        assertEquals("UNREACHABLE", Buckets.token("UNREACHABLE"))
        assertEquals("OTHER", Buckets.token("Не найден маршрут"))
        assertEquals("OTHER", Buckets.token(""))
        assertEquals("OTHER", Buckets.token(null))
    }
}
