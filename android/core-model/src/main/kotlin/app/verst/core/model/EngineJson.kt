package app.verst.core.model

import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.EstimateDto
import app.verst.core.model.dto.PlaceNameDto
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.SuggestionDto
import app.verst.core.model.dto.TripDto
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.nullable
import kotlinx.serialization.builtins.serializer
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
    /** `plan`/`replace_stop`/`patch_cost`: the DTO plus the private trip JSON verbatim ([PlanResultDto.tripJson]). */
    fun planResult(envelope: String): EngineResult<PlanResultDto> =
        when (val r = decode(envelope, JsonObject.serializer())) {
            is EngineResult.Err -> r
            is EngineResult.Ok -> try {
                val raw = r.value["trip"] as? JsonObject ?: throw IllegalArgumentException("result without trip")
                EngineResult.Ok(json.decodeFromJsonElement(PlanResultDto.serializer(), r.value).copy(tripJson = raw.toString()))
            } catch (e: Exception) {
                EngineResult.Err(EngineErrorDto("INTERNAL", "undecodable trip: $e"))
            }
        }

    /**
     * v2 `plan` (ADR-0011): `outcome = plan` → the trip (as [planResult]); `outcome = no_fit` → the minimum (its
     * trip decoded like a plan result, shown only on request) and the options.
     */
    fun planOutcome(envelope: String): EngineResult<app.verst.core.model.dto.PlanOutcome> =
        when (val r = decode(envelope, JsonObject.serializer())) {
            is EngineResult.Err -> r
            is EngineResult.Ok -> try {
                val body = r.value
                if ((body["outcome"] as? JsonPrimitive)?.content == "no_fit") {
                    val nf = json.decodeFromJsonElement(app.verst.core.model.dto.NoFitDto.serializer(), body)
                    val min = body["minimum"] as? JsonObject
                    val minTrip = (min?.get("trip") as? JsonObject)?.let { raw ->
                        json.decodeFromJsonElement(PlanResultDto.serializer(), min).copy(tripJson = raw.toString())
                    }
                    val levers = (min?.get("levers"))?.let { json.decodeFromJsonElement(ListSerializer(app.verst.core.model.dto.BudgetLeverDto.serializer()), it) }.orEmpty()
                    val total = (min?.get("totalRub") as? JsonPrimitive)?.content?.toIntOrNull() ?: minTrip?.trip?.cost?.totalRub ?: 0
                    EngineResult.Ok(app.verst.core.model.dto.PlanOutcome.NoFit(nf.copy(minimum = minTrip, minimumLevers = levers, minimumTotalRub = total)))
                } else {
                    val raw = body["trip"] as? JsonObject ?: throw IllegalArgumentException("result without trip")
                    EngineResult.Ok(app.verst.core.model.dto.PlanOutcome.Plan(json.decodeFromJsonElement(PlanResultDto.serializer(), body).copy(tripJson = raw.toString())))
                }
            } catch (e: Exception) {
                EngineResult.Err(EngineErrorDto("INTERNAL", "undecodable plan: $e"))
            }
        }

    fun geoNearest(envelope: String) = decode(envelope, app.verst.core.model.dto.GeoNearestDto.serializer())
    fun poiDetails(envelope: String) = decode(envelope, app.verst.core.model.dto.PoiDetailsDto.serializer())
    fun handoff(envelope: String) = decode(envelope, app.verst.core.model.dto.HandoffDto.serializer())
    fun cityPresets(envelope: String) = decode(envelope, app.verst.core.model.dto.CityPresetsDto.serializer())

    /** `city_route`: the walk plus its JSON verbatim (the `handoff` input and what is saved). */
    fun walkRoute(envelope: String): EngineResult<app.verst.core.model.dto.WalkRouteDto> =
        when (val r = decode(envelope, JsonObject.serializer())) {
            is EngineResult.Err -> r
            is EngineResult.Ok -> try {
                EngineResult.Ok(json.decodeFromJsonElement(app.verst.core.model.dto.WalkRouteDto.serializer(), r.value).copy(json = r.value.toString()))
            } catch (e: Exception) {
                EngineResult.Err(EngineErrorDto("INTERNAL", "undecodable walk: $e"))
            }
        }

    fun walk(text: String): app.verst.core.model.dto.WalkRouteDto =
        json.decodeFromString(app.verst.core.model.dto.WalkRouteDto.serializer(), text).copy(json = text)

    fun estimate(envelope: String) = decode(envelope, EstimateDto.serializer())
    fun placeName(envelope: String) = decode(envelope, PlaceNameDto.serializer().nullable)
    fun kmList(envelope: String) = decode(envelope, ListSerializer(Int.serializer().nullable))

    fun trip(text: String): TripDto = json.decodeFromString(TripDto.serializer(), text)

    fun event(text: String): PlanEventDto? = try {
        json.decodeFromString(PlanEventDto.serializer(), text)
    } catch (_: Exception) {
        null
    }
}

data class GeoPoint(val label: String, val lat: Double, val lon: Double)

/** `city_route` input (ADR-0013 "Input"). */
data class WalkRequest(
    val start: GeoPoint,
    val preset: String,
    val durationMin: Int? = null,
    val interests: List<String> = emptyList(),
    val pace: String? = null,
    val budgetRub: Int? = null,
    val returnToStart: Boolean = true,
    val adults: Int = 2,
    val children: Int = 0,
    val adultConfirmed: Boolean = false,
    val exclude: List<String> = emptyList(),
    /** API v3: the dog in the walk's own crew (ADR-0015 §6). */
    val dog: Boolean = false,
    /** API v3: «без ограничения» — sent as `"durationMin": null`. */
    val unlimited: Boolean = false,
) {
    fun toInputJson(): String = buildJsonObject {
        put("start", buildJsonObject {
            put("lat", start.lat)
            put("lon", start.lon)
            put("label", start.label)
        })
        put("preset", preset)
        if (unlimited) put("durationMin", kotlinx.serialization.json.JsonNull) else durationMin?.let { put("durationMin", it) }
        if (interests.isNotEmpty()) put("interests", kotlinx.serialization.json.JsonArray(interests.map { JsonPrimitive(it) }))
        pace?.let { put("pace", it) }
        budgetRub?.let { put("budgetRub", it) }
        put("returnToStart", returnToStart)
        put("crew", buildJsonObject {
            put("adults", adults)
            put("children", children)
            if (dog) put("dog", true)
        })
        if (adultConfirmed) put("adultConfirmed", true)
        if (exclude.isNotEmpty()) put("exclude", kotlinx.serialization.json.JsonArray(exclude.map { JsonPrimitive(it) }))
    }.toString()
}

/** `handoff` options (ADR-0014): car day / from a stop / from here, or walk. */
object HandoffArgs {
    fun day(day: Int): String = buildJsonObject {
        put("mode", "car")
        put("day", day)
        put("fromHere", true)
    }.toString()

    fun fromStop(stopId: String): String = buildJsonObject {
        put("mode", "car")
        put("fromStopId", stopId)
    }.toString()

    fun walk(): String = buildJsonObject {
        put("mode", "walk")
        put("fromHere", false)
    }.toString()
}

/** Bodies of `patch_cost` (A§16.9) and `estimate_points`. */
object EngineArgs {
    fun reservePatch(on: Boolean): String = buildJsonObject { put("reserveOn", on) }.toString()

    fun hotelPatch(stopId: String, placeId: String): String =
        buildJsonObject { put("hotelChoice", buildJsonObject { put("stopId", stopId); put("placeId", placeId) }) }.toString()

    fun points(points: List<GeoPoint>): String =
        kotlinx.serialization.json.JsonArray(points.map { p -> buildJsonObject { put("lat", p.lat); put("lon", p.lon) } }).toString()
}

/** The default mock origin (D-16 «старт — Москва»; the most populous town of `central_russia_v1`). */
val DefaultOrigin = GeoPoint("Москва", 55.7558, 37.6173)

/** Sprint 3: the app's default world = the fixture world + the catalogue (M§5.4, ADR-0012 §4). */
const val DefaultWorld = "russia_v1"

/** The golden-test world (G01–G12) and the e2e parity world. */
const val GoldenWorld = "central_russia_v1"

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
