package app.verst.data

import android.content.Context
import android.util.AtomicFile
import app.verst.core.model.SavedTripDto
import app.verst.core.model.SavedTrips
import java.io.File

/** Saved trips (M§6.1, DEV-SLICE-2 subset): the whole list in one JSON file, no Room. */
interface TripStore {
    fun load(): List<SavedTripDto>
    fun save(trips: List<SavedTripDto>)
}

/**
 * `files/trips/saved.json` written through [AtomicFile]: a crash mid-write leaves the previous file readable
 * (the temp/backup file is ignored or restored on the next read). Called off the main thread.
 */
class FileTripStore(context: Context) : TripStore {
    private val file = AtomicFile(File(File(context.filesDir, "trips").apply { mkdirs() }, "saved.json"))

    override fun load(): List<SavedTripDto> = try {
        SavedTrips.decode(file.readFully().toString(Charsets.UTF_8))
    } catch (_: java.io.FileNotFoundException) {
        emptyList()
    }

    override fun save(trips: List<SavedTripDto>) {
        val out = file.startWrite()
        try {
            out.write(SavedTrips.encode(trips).toByteArray(Charsets.UTF_8))
            file.finishWrite(out)
        } catch (e: Exception) {
            file.failWrite(out)
            throw e
        }
    }
}

/** In-memory store (Robolectric screenshots and unit tests). */
class MemoryTripStore(initial: List<SavedTripDto> = emptyList()) : TripStore {
    private var trips = initial
    override fun load() = trips
    override fun save(trips: List<SavedTripDto>) {
        this.trips = trips
    }
}
