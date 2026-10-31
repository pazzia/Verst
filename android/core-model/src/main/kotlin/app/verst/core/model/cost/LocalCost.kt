package app.verst.core.model.cost

import app.verst.core.model.EngineJson
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * [CostCalculator] over an engine trip JSON (the private trip of `plan`/`replace_stop`/`patch_cost`): the
 * instant local numbers of a reserve toggle, a hotel choice or a replace, before the engine answers.
 */
object LocalCost {
    private fun units(trip: JsonObject): CostUnitsDto =
        EngineJson.json.decodeFromJsonElement(CostUnitsDto.serializer(), trip.getValue("cost").jsonObject.getValue("units"))

    fun crew(trip: JsonObject): CostCrew =
        EngineJson.json.decodeFromJsonElement(CostCrew.serializer(), trip.getValue("input").jsonObject.getValue("crew"))

    fun reserveOn(trip: JsonObject): Boolean = trip.getValue("cost").jsonObject["reserveOn"]?.jsonPrimitive?.booleanOrNull ?: true

    fun budget(trip: JsonObject): Int? = (trip.getValue("input").jsonObject["budget"] as? JsonPrimitive)?.takeIf { it !is JsonNull }?.intOrNull

    /** The units of alternative [altId] of stop [stopId], or null. */
    fun altUnits(trip: JsonObject, stopId: String, altId: String): AltUnitsDto? {
        for (d in trip.getValue("daysList").jsonArray) for (s in d.jsonObject.getValue("stops").jsonArray) {
            val so = s.jsonObject
            if ((so["id"] as? JsonPrimitive)?.content != stopId) continue
            val alt = so["alternatives"]?.jsonArray?.map { it.jsonObject }?.firstOrNull { (it["id"] as? JsonPrimitive)?.content == altId } ?: return null
            return EngineJson.json.decodeFromJsonElement(AltUnitsDto.serializer(), alt.getValue("units"))
        }
        return null
    }

    fun now(trip: JsonObject, reserveOn: Boolean = reserveOn(trip), budget: Int? = budget(trip), ov: CostOverridesDto = CostOverridesDto()): CostNumbers =
        CostCalculator.recompute(units(trip), crew(trip), reserveOn, budget, ov)

    fun reserve(trip: JsonObject, on: Boolean) = now(trip, reserveOn = on)
    fun hotel(trip: JsonObject, stopId: String, placeId: String) = now(trip, ov = CostOverridesDto(hotelByStop = mapOf(stopId to placeId)))
    fun replace(trip: JsonObject, stopId: String, altId: String): CostNumbers? =
        altUnits(trip, stopId, altId)?.let { now(trip, ov = CostOverridesDto(replaced = mapOf(stopId to it))) }

    fun parse(tripJson: String): JsonObject = EngineJson.json.parseToJsonElement(tripJson).jsonObject
}
