package app.verst.core.model

import kotlinx.serialization.Serializable

/**
 * D-7 «Сообщить об ошибке» (S3-R3, local): one report about a place. There is no feedback endpoint yet, so the
 * reports wait in `files/reports/queue.json` with `sent = false` (the queue a later sender drains).
 */
@Serializable
data class ReportDto(
    val id: String,
    /** Unix ms. */
    val at: Long,
    /** `closed` | `tags` | `price` | `other` (D-7 rows, in order). */
    val reason: String,
    val comment: String = "",
    val name: String,
    val placeId: String? = null,
    val stopId: String? = null,
    /** `road` (Road ahead row / stop menu), `card` (5.9), `walk` (a walk stop card). */
    val source: String,
    val world: String? = null,
    val online: Boolean = true,
    val sent: Boolean = false,
)

@Serializable
data class ReportsFile(val schema: Int = Reports.SCHEMA, val reports: List<ReportDto> = emptyList())

object Reports {
    const val SCHEMA = 1
    /** The oldest reports drop out beyond this (a local queue, not an archive). */
    const val LIMIT = 200
    const val COMMENT_MAX = 280
    val REASONS = listOf("closed", "tags", "price", "other")

    fun decode(text: String?): List<ReportDto> = try {
        if (text.isNullOrBlank()) emptyList()
        else EngineJson.json.decodeFromString(ReportsFile.serializer(), text).takeIf { it.schema == SCHEMA }?.reports ?: emptyList()
    } catch (_: Exception) {
        emptyList()
    }

    fun encode(reports: List<ReportDto>): String =
        EngineJson.json.encodeToString(ReportsFile.serializer(), ReportsFile(reports = reports.takeLast(LIMIT)))

    /** Appends [r] to the queue text (an unreadable queue starts over: reports are not worth a crash). */
    fun append(text: String?, r: ReportDto): String = encode(decode(text) + r)
}
