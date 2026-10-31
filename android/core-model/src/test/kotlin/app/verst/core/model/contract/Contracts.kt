package app.verst.core.model.contract

import java.io.File
import java.util.zip.GZIPInputStream
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * Loader of the engine contract bundles written by `backend/planner/tools/gen_mobile_contracts.py` (DEV-112):
 * `docs/contracts/{replace,patch}/<case>.json.gz` = `{"case", "before", "items": [...]}`, the trip before the
 * edit stored once per case. Replace items: `stopId`, `altId`, `afterDay`, `afterCost`, `afterKm`. Patch items:
 * `kind`, `patch`, `afterCost`, `afterInput`, `afterHotel` (null or the changed fields of one overnight stop).
 */
object Contracts {
    val repoRoot: File = File(System.getProperty("verst.repoRoot") ?: error("system property verst.repoRoot"))
    private val dir = repoRoot.resolve("docs/contracts")

    data class Bundle(val case: String, val before: JsonObject, val items: List<JsonObject>)

    fun files(kind: String): List<File> =
        dir.resolve(kind).listFiles { f -> f.name.endsWith(".json.gz") }.orEmpty().sortedBy { it.name }

    fun gunzip(file: File): String =
        GZIPInputStream(file.inputStream()).bufferedReader(Charsets.UTF_8).use { it.readText() }

    fun load(kind: String): List<Bundle> = files(kind).map { f ->
        val doc = Json.parseToJsonElement(gunzip(f)).jsonObject
        Bundle(
            doc.getValue("case").jsonPrimitive.content,
            doc.getValue("before").jsonObject,
            doc.getValue("items").jsonArray.map { it.jsonObject },
        )
    }
}
