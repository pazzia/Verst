package app.verst.core.model

import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.SuggestionDto
import app.verst.core.model.dto.TripDto
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

/** Result of one engine call: the decoded payload or the engine's error (never an exception). */
sealed interface EngineResult<out T> {
    data class Ok<T>(val value: T) : EngineResult<T>
    data class Err(val error: EngineErrorDto) : EngineResult<Nothing>
}

/** Decoding of the `mobile.py` envelope `{ok, result|error, ms}` (M§5.1). */
object EngineJson {
    val json = Json { ignoreUnknownKeys = true; explicitNulls = false; encodeDefaults = true; coerceInputValues = true }

    fun <T> decode(envelope: String, serializer: KSerializer<T>): EngineResult<T> = try {
        val body = json.parseToJsonElement(envelope).jsonObject
        val ok = (body["ok"] as? JsonPrimitive)?.booleanOrNull == true
        if (ok) {
            EngineResult.Ok(json.decodeFromJsonElement(serializer, body["result"] ?: JsonNull))
        } else {
            val err = body["error"]
            if (err is JsonObject) EngineResult.Err(json.decodeFromJsonElement(EngineErrorDto.serializer(), err))
            else EngineResult.Err(EngineErrorDto("INTERNAL", "envelope without error"))
        }
    } catch (e: Exception) {
        EngineResult.Err(EngineErrorDto("INTERNAL", "undecodable envelope: $e"))
    }

    fun readyRoutes(envelope: String) = decode(envelope, ListSerializer(ReadyRouteDto.serializer()))
    fun suggestions(envelope: String) = decode(envelope, ListSerializer(SuggestionDto.serializer()))
    fun planResult(envelope: String) = decode(envelope, PlanResultDto.serializer())

    fun trip(text: String): TripDto = json.decodeFromString(TripDto.serializer(), text)

    fun event(text: String): PlanEventDto? = try {
        json.decodeFromString(PlanEventDto.serializer(), text)
    } catch (_: Exception) {
        null
    }
}

data class GeoPoint(val label: String, val lat: Double, val lon: Double)

/** The default mock origin (D-16 «старт — Москва»; the most populous town of `central_russia_v1`). */
val DefaultOrigin = GeoPoint("Москва", 55.7558, 37.6173)

const val DefaultWorld = "central_russia_v1"

enum class Mood(val wire: String) { CALM("calm"), MORE_STOPS("more_stops"), JUST_DRIVE("just_drive") }

/** Budget presets of 5.3 §3 (`null` = «не важно»). */
val BudgetPresets: List<Int?> = listOf(20_000, 30_000, 40_000, 60_000, 80_000, null)

/** What the user asked for; `toInputJson()` is the `TripInputDTO` body of `mobile.plan`. */
data class PlanRequest(
    val origin: GeoPoint,
    val destination: GeoPoint? = null,
    val readyRouteId: String? = null,
    val adults: Int = 2,
    val children: Int = 0,
    val dog: Boolean = false,
    val dailyKm: Int = 300,
    val budgetRub: Int? = null,
    val mood: Mood? = null,
) {
    fun toInputJson(): String {
        fun point(p: GeoPoint): JsonElement = buildJsonObject {
            put("lat", p.lat)
            put("lon", p.lon)
            put("label", p.label)
        }
        val body = buildJsonObject {
            put("origin", point(origin))
            if (destination != null) put("destination", point(destination))
            if (readyRouteId != null) put("readyRouteId", readyRouteId)
            put("crew", buildJsonObject {
                put("adults", adults)
                put("children", children)
                put("dog", dog)
            })
            put("dailyKm", dailyKm)
            put("budget", budgetRub?.let { JsonPrimitive(it) } ?: JsonNull)
            if (mood != null) put("mood", mood.wire)
        }
        return body.toString()
    }
}
