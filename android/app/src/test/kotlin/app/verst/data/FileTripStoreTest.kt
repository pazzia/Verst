package app.verst.data

import androidx.test.core.app.ApplicationProvider
import app.verst.core.model.DefaultsDto
import app.verst.core.model.EngineJson
import app.verst.core.model.LastTripDto
import app.verst.core.model.SavedTrips
import app.verst.core.model.dto.PlanResultDto
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** Release review P1-1 / P1-2 on the real file store. */
@RunWith(RobolectricTestRunner::class)
class FileTripStoreTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")
    private val text = root.resolve("backend/planner/tests/golden/snapshots/G01_msk_yar_round.json").readText()
    private val result = PlanResultDto(EngineJson.trip(text), "share", "октябрь", "2026", tripJson = text)
    private val dir = File(context.filesDir, "trips")

    @Test
    fun roundTripLastAndDefaults() {
        val store = FileTripStore(context)
        val e = SavedTrips.entry("a", 1, result, "NE")
        store.save(listOf(e, e.copy(id = "b")))
        assertEquals(listOf("a", "b"), (store.load() as TripsLoad.Ok).trips.map { it.id })
        store.saveLast(LastTripDto(trip = e, savedId = "a", screen = "road"))
        assertEquals("road", store.loadLast()!!.screen)
        store.saveLast(null)
        assertNull(store.loadLast())
        store.saveDefaults(DefaultsDto(dog = true, dailyKm = 450))
        assertEquals(450, store.loadDefaults()!!.dailyKm)
    }

    @Test
    fun unreadableFileIsKeptAsideAndNeverOverwritten() {
        dir.mkdirs()
        File(dir, "saved.json").writeText("{\"schema\": 1, \"trips\": [ broken")
        val store = FileTripStore(context) { 42 }
        val load = store.load()
        assertEquals(TripsLoad.Unreadable("saved.json.bad-42"), load)
        val aside = File(dir, "saved.json.bad-42")
        assertTrue(aside.exists())
        store.save(listOf(SavedTrips.entry("new", 1, result, "N")))
        assertTrue("the unreadable file survives the next save", aside.readText().contains("broken"))
        assertEquals(listOf("new"), (store.load() as TripsLoad.Ok).trips.map { it.id })
    }

    @Test
    fun unknownSchemaIsUnreadableToo() {
        dir.mkdirs()
        File(dir, "saved.json").writeText("""{"schema": 2, "trips": []}""")
        assertTrue(FileTripStore(context) { 7 }.load() is TripsLoad.Unreadable)
    }
}
