package app.verst.data

import android.content.Context
import android.util.AtomicFile
import android.util.Log
import app.verst.core.model.DefaultsDto
import app.verst.core.model.LastTripDto
import app.verst.core.model.ReportDto
import app.verst.core.model.Reports
import app.verst.core.model.SavedTripDto
import app.verst.core.model.SavedTrips
import java.io.File

/** What reading the saved-trips file found (release review P1-1). */
sealed interface TripsLoad {
    data class Ok(val trips: List<SavedTripDto>) : TripsLoad

    /** The file could not be read (corrupt or an unknown schema). It was moved aside, never overwritten. */
    data class Unreadable(val keptAs: String) : TripsLoad
}

/**
 * Saved trips (M§6.1, DEV-SLICE-2/3 subset): the whole list in one JSON file, plus the unsaved current trip
 * (`last.json`, P1-2). Called off the main thread by one serialized writer (`VerstFlow`).
 */
interface TripStore {
    fun load(): TripsLoad
    fun save(trips: List<SavedTripDto>)
    fun loadLast(): LastTripDto?
    fun saveLast(last: LastTripDto?)
    fun loadDefaults(): DefaultsDto?
    fun saveDefaults(d: DefaultsDto)

    /** D-7: the local report queue (`files/reports/queue.json`). */
    fun appendReport(r: ReportDto) = Unit
    fun loadReports(): List<ReportDto> = emptyList()
}

/**
 * `files/trips/saved.json` and `files/trips/last.json`, each written through [AtomicFile] (temp `.new` + rename),
 * so a crash mid-write leaves the previous file readable. A file that does not decode is renamed to
 * `saved.json.bad-<ts>` and kept: the next save then starts a new file instead of destroying the old trips.
 */
class FileTripStore(context: Context, private val now: () -> Long = System::currentTimeMillis) : TripStore {
    private val dir = File(context.filesDir, "trips").apply { mkdirs() }
    private val file = AtomicFile(File(dir, "saved.json"))
    private val last = AtomicFile(File(dir, "last.json"))
    private val defaults = AtomicFile(File(dir, "defaults.json"))
    private val reports = AtomicFile(File(File(context.filesDir, "reports").apply { mkdirs() }, "queue.json"))

    override fun loadReports(): List<ReportDto> = try {
        Reports.decode(reports.readFully().toString(Charsets.UTF_8))
    } catch (_: java.io.FileNotFoundException) {
        emptyList()
    }

    override fun appendReport(r: ReportDto) = write(reports, Reports.encode(loadReports() + r))

    override fun load(): TripsLoad {
        val bytes = try {
            file.readFully()
        } catch (_: java.io.FileNotFoundException) {
            return TripsLoad.Ok(emptyList())
        }
        val trips = SavedTrips.decodeOrNull(bytes.toString(Charsets.UTF_8))
        if (trips != null) return TripsLoad.Ok(trips)
        val aside = File(dir, "saved.json.bad-${now()}")
        file.baseFile.renameTo(aside)
        Log.w(TAG, "saved trips unreadable, kept as ${aside.name}")
        return TripsLoad.Unreadable(aside.name)
    }

    override fun save(trips: List<SavedTripDto>) = write(file, SavedTrips.encode(trips))

    override fun loadLast(): LastTripDto? = try {
        SavedTrips.decodeLast(last.readFully().toString(Charsets.UTF_8))
    } catch (_: java.io.FileNotFoundException) {
        null
    }

    override fun saveLast(last: LastTripDto?) {
        if (last == null) this.last.delete() else write(this.last, SavedTrips.encodeLast(last))
    }

    override fun loadDefaults(): DefaultsDto? = try {
        SavedTrips.decodeDefaults(defaults.readFully().toString(Charsets.UTF_8))
    } catch (_: java.io.FileNotFoundException) {
        null
    }

    override fun saveDefaults(d: DefaultsDto) = write(defaults, SavedTrips.encodeDefaults(d))

    private fun write(f: AtomicFile, text: String) {
        val out = f.startWrite()
        try {
            out.write(text.toByteArray(Charsets.UTF_8))
            f.finishWrite(out)
        } catch (e: Exception) {
            f.failWrite(out)
            throw e
        }
    }

    companion object {
        const val TAG = "VerstTrips"
    }
}

/** In-memory store (Robolectric screenshots and unit tests); [failWrites] simulates a full disk. */
class MemoryTripStore(initial: List<SavedTripDto> = emptyList()) : TripStore {
    @Volatile var trips = initial
        private set
    @Volatile var last: LastTripDto? = null
        private set
    @Volatile var failWrites = false
    val writes = java.util.concurrent.atomic.AtomicInteger()

    override fun load(): TripsLoad = TripsLoad.Ok(trips)
    override fun save(trips: List<SavedTripDto>) {
        writes.incrementAndGet()
        if (failWrites) throw java.io.IOException("disk full (test)")
        this.trips = trips
    }

    override fun loadLast() = last
    override fun saveLast(last: LastTripDto?) {
        if (failWrites) throw java.io.IOException("disk full (test)")
        this.last = last
    }

    fun seedLast(l: LastTripDto?) {
        last = l
    }

    @Volatile var reports: List<ReportDto> = emptyList()
        private set
    override fun appendReport(r: ReportDto) {
        reports = Reports.decode(Reports.encode(reports + r))
    }
    override fun loadReports() = reports

    @Volatile var defaults: DefaultsDto? = null
    override fun loadDefaults() = defaults
    override fun saveDefaults(d: DefaultsDto) {
        defaults = d
    }
}
