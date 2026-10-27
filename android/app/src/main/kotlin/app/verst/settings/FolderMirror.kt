package app.verst.settings

import android.content.Context
import android.net.Uri
import android.provider.DocumentsContract
import android.util.Log
import app.verst.core.model.SavedTripDto
import app.verst.core.model.SavedTrips
import app.verst.core.model.TripStorage
import app.verst.data.TripStore
import app.verst.data.TripsLoad

/**
 * D-IR-20 «Где хранить поездки → в папке»: the saved trips stay in the app (the source of truth) and every save is
 * also written to one JSON file in the folder the user picked (Storage Access Framework, no storage permission).
 * A failed folder write never loses the trip: it is reported on the settings screen.
 */
class MirroringTripStore(private val inner: TripStore, private val context: Context) : TripStore by inner {
    override fun save(trips: List<SavedTripDto>) {
        inner.save(trips)
        if (AppPrefs.settings.storage == TripStorage.FOLDER) mirror(trips)
    }

    /** Writes [trips] now (also used right after the folder is picked). */
    fun mirror(trips: List<SavedTripDto>) {
        val uri = AppPrefs.settings.folderUri ?: return
        val now = System.currentTimeMillis()
        AppPrefs.folderStatus = try {
            FolderFiles.write(context, Uri.parse(uri), FILE, "application/json", SavedTrips.encode(trips).toByteArray(Charsets.UTF_8))
            FolderStatus.Written(now, trips.size)
        } catch (e: Exception) {
            Log.w("VerstFolder", "cannot write the trips file", e)
            FolderStatus.Failed(now, e.javaClass.simpleName)
        }
    }

    fun mirrorCurrent() {
        val l = inner.load()
        if (l is TripsLoad.Ok) mirror(l.trips)
    }

    companion object {
        const val FILE = "verst-saved-trips.json"
    }
}

/** Create-or-replace of one file in a SAF tree. */
object FolderFiles {
    fun write(context: Context, tree: Uri, name: String, mime: String, bytes: ByteArray) {
        val cr = context.contentResolver
        val rootId = DocumentsContract.getTreeDocumentId(tree)
        val children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, rootId)
        var existing: Uri? = null
        cr.query(
            children,
            arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME),
            null, null, null,
        )?.use { c ->
            while (c.moveToNext()) {
                if (c.getString(1) == name) {
                    existing = DocumentsContract.buildDocumentUriUsingTree(tree, c.getString(0))
                    break
                }
            }
        }
        val target = existing
            ?: DocumentsContract.createDocument(cr, DocumentsContract.buildDocumentUriUsingTree(tree, rootId), mime, name)
            ?: error("createDocument returned null")
        (cr.openOutputStream(target, "wt") ?: error("no output stream")).use { it.write(bytes) }
    }

    /** The folder's display name for the settings row. */
    fun displayName(context: Context, tree: Uri): String? = runCatching {
        val doc = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree))
        context.contentResolver.query(doc, arrayOf(DocumentsContract.Document.COLUMN_DISPLAY_NAME), null, null, null)
            ?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
    }.getOrNull()
}
