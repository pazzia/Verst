package app.verst.core.model

import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** S3-R3: Commons URLs (parity with `catalogue/photos.py`), the report queue, the 5.10 caption start rule. */
class S3R3ModelTest {
    @Test
    fun commonsUrlsMatchThePythonBuilder() {
        // expected strings printed by verst_planner.catalogue.photos.image_urls
        assertEquals(
            "https://commons.wikimedia.org/wiki/Special:FilePath/Mona_Lisa,_by_Leonardo_da_Vinci,_from_C2RMF_retouched.jpg?width=800",
            CommonsPhotos.thumbUrl("Mona Lisa, by Leonardo da Vinci, from C2RMF retouched.jpg", 800),
        )
        assertEquals(
            "https://commons.wikimedia.org/wiki/Special:FilePath/Saint_Basil%27s_Cathedral_(Moscow).jpg?width=800",
            CommonsPhotos.thumbUrl("Saint Basil's Cathedral (Moscow).jpg", 800),
        )
        assertEquals(
            "https://commons.wikimedia.org/wiki/Special:FilePath/%D0%A0%D0%BE%D1%81%D1%82%D0%BE%D0%B2%D1%81%D0%BA%D0%B8%D0%B9_%D0%BA%D1%80%D0%B5%D0%BC%D0%BB%D1%8C.jpg?width=800",
            CommonsPhotos.thumbUrl("Ростовский кремль.jpg", 800),
        )
        assertEquals("https://commons.wikimedia.org/wiki/File:Coat_of_Arms_of_the_Russian_Federation.svg", CommonsPhotos.pageUrl("Coat of Arms of the Russian Federation.svg"))
        val img = CommonsPhotos.debugImage(app.verst.core.model.dto.PoiImageDto(isArea = true, labelRu = "Фото района: Ярославль · Wikimedia Commons"), "Example.jpg")
        assertTrue(img.isArea)
        assertEquals("Фото района: Ярославль · Wikimedia Commons", img.labelRu)
        assertEquals(5, CommonsPhotos.DEBUG_FILES.size)
    }

    @Test
    fun reportQueueAppendsCapsAndSurvivesGarbage() {
        val r = ReportDto("a", 1L, "price", "Билет 600 ₽", "Ростовский кремль", "pl_k", "d1s04", "road")
        val one = Reports.append(null, r)
        assertEquals(listOf(r), Reports.decode(one))
        assertEquals(listOf(r, r.copy(id = "b")), Reports.decode(Reports.append(one, r.copy(id = "b"))))
        assertEquals(listOf(r), Reports.decode(Reports.append("{not json", r)))
        assertEquals(emptyList<ReportDto>(), Reports.decode("""{"schema": 9, "reports": []}"""))
        val many = (1..(Reports.LIMIT + 5)).map { r.copy(id = "$it") }
        val kept = Reports.decode(Reports.encode(many))
        assertEquals(Reports.LIMIT, kept.size)
        assertEquals("6", kept.first().id) // the oldest drop out
    }

    private fun at(h: Int, m: Int) = ZonedDateTime.of(2026, 10, 24, h, m, 0, 0, ZoneId.of("Europe/Moscow"))

    @Test
    fun captionStartFollowsTheEngineWindows() {
        // day walk: now rounded up to 15 min inside 09:00 … 22:00 − duration
        assertEquals(WalkStart.Start(LocalTime.of(11, 15), false), WalkStart.of("overview", emptyList(), 240, at(11, 2)))
        assertEquals(WalkStart.Start(LocalTime.of(9, 0), false), WalkStart.of("overview", emptyList(), 240, at(7, 40)))
        // 22:45 with a 4 h walk: too late → tomorrow 09:00 (S3-QA P0-01: never a night walk)
        assertEquals(WalkStart.Start(LocalTime.of(9, 0), true), WalkStart.of("overview", emptyList(), 240, at(22, 45)))
        assertEquals(WalkStart.Start(LocalTime.of(9, 0), true), WalkStart.of("overview", emptyList(), 240, at(18, 5)))
        // museums open at 10:00
        assertEquals(WalkStart.Start(LocalTime.of(10, 0), false), WalkStart.of("museums", emptyList(), 360, at(8, 0)))
        // drink walks: 18:00 … 23:00 − duration; bars in a custom walk count as drinks
        assertEquals(WalkStart.Start(LocalTime.of(18, 0), false), WalkStart.of("ryumochnye", emptyList(), 240, at(12, 0)))
        assertEquals(WalkStart.Start(LocalTime.of(18, 0), false), WalkStart.of("custom", listOf("bars"), 120, at(15, 0)))
        assertEquals(WalkStart.Start(LocalTime.of(18, 0), true), WalkStart.of("ryumochnye", emptyList(), 240, at(20, 0)))
        // 23:50 rounds into the next day → the window opening, tomorrow
        assertEquals(WalkStart.Start(LocalTime.of(9, 0), true), WalkStart.of("overview", emptyList(), 120, at(23, 50)))
        assertEquals("09:00", WalkStart.Start(LocalTime.of(9, 0), true).label)
    }

    @Test
    fun engineStartAtIsTomorrowAgainstTheTownZone() {
        val zone = WalkStart.zone("Asia/Yekaterinburg")
        val now = ZonedDateTime.of(2026, 10, 24, 20, 30, 0, 0, ZoneId.of("UTC")) // 01:30 on the 25th in Пермь
        assertFalse(WalkStart.fromEngine("2026-10-25T10:00", zone, now)!!.tomorrow)
        assertTrue(WalkStart.fromEngine("2026-10-26T10:00", zone, now)!!.tomorrow)
        assertEquals(ZoneId.of("Europe/Moscow"), WalkStart.zone(null))
        assertEquals(ZoneId.of("Europe/Moscow"), WalkStart.zone("Nowhere/Bad"))
    }
}
