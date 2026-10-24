package app.verst.engine

import app.verst.core.model.DefaultWorld
import app.verst.core.model.EngineJson
import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.core.model.PlanRequest
import app.verst.core.model.EngineArgs
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.EstimateDto
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.SuggestionDto
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/** Feature-facing engine API (M§5.2 `PlannerGateway`, DEV-SLICE subset). Every result is an `EngineResult`. */
interface PlannerGateway {
    suspend fun readyRoutes(origin: GeoPoint): EngineResult<List<ReadyRouteDto>>
    suspend fun suggest(query: String, near: GeoPoint?): EngineResult<List<SuggestionDto>>
    suspend fun popular(): EngineResult<List<SuggestionDto>>
    suspend fun plan(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanResultDto>

    /** The engine's km/days of [request] before Road ahead (= its plan); cancelling the caller cancels it. */
    suspend fun estimate(requestId: String, request: PlanRequest): EngineResult<EstimateDto>

    /** Base-route km from [origin] to each point (suggestion rows); null where unreachable. */
    suspend fun estimatePoints(origin: GeoPoint, points: List<GeoPoint>): EngineResult<List<Int?>>

    /** D-6: swap in an alternative on the engine (A§6.11); returns the whole new trip. */
    suspend fun replaceStop(tripJson: String, stopId: String, altId: String): EngineResult<PlanResultDto>

    /** Waybill reserve toggle etc. (A§16.9 `patch_cost`); cost-only, returns the whole trip. */
    suspend fun patchCost(tripJson: String, patchJson: String): EngineResult<PlanResultDto>
}

class ChaquopyPlannerGateway(private val host: EngineHost, private val world: String = DefaultWorld) : PlannerGateway {

    /** Waits for the engine; `Failed` (or > 30 s starting) becomes an engine error so the screen can show it. */
    private suspend fun ready(): EngineErrorDto? {
        val s = withTimeoutOrNull(30_000) { host.status.first { it !is EngineStatus.Starting } }
        return when (s) {
            is EngineStatus.Ready -> null
            is EngineStatus.Failed -> EngineErrorDto(s.code, s.detail)
            else -> EngineErrorDto("ENGINE_START", "engine not ready after 30 s")
        }
    }

    private suspend fun <T> run(decode: (String) -> EngineResult<T>, function: String, vararg args: Any?): EngineResult<T> {
        ready()?.let { return EngineResult.Err(it) }
        val envelope = withContext(host.dispatcher) { host.callHere(function, *args) }
        return decode(envelope)
    }

    override suspend fun readyRoutes(origin: GeoPoint) =
        run(EngineJson::readyRoutes, "ready_routes", world, origin.lat, origin.lon, 50.0, 20)

    override suspend fun suggest(query: String, near: GeoPoint?) =
        run(EngineJson::suggestions, "suggest", world, query, near?.lat, near?.lon, 6)

    override suspend fun popular() = run(EngineJson::suggestions, "popular", world, 6)

    override suspend fun estimatePoints(origin: GeoPoint, points: List<GeoPoint>) =
        run(EngineJson::kmList, "estimate_points", world, origin.lat, origin.lon, EngineArgs.points(points))

    override suspend fun replaceStop(tripJson: String, stopId: String, altId: String) =
        run(EngineJson::planResult, "replace_stop", world, tripJson, stopId, altId)

    override suspend fun patchCost(tripJson: String, patchJson: String) =
        run(EngineJson::planResult, "patch_cost", world, tripJson, patchJson)

    override suspend fun estimate(requestId: String, request: PlanRequest): EngineResult<EstimateDto> {
        ready()?.let { return EngineResult.Err(it) }
        return EngineJson.estimate(cancellable(requestId) { host.callHere("estimate", world, requestId, request.toInputJson()) })
    }

    /**
     * `mobile.plan` on `verst-python`; events are delivered on the main thread. Cancelling the calling coroutine
     * calls `mobile.cancel(requestId)` (D-13), which makes the running plan return `CANCELLED`.
     */
    override suspend fun plan(
        requestId: String,
        request: PlanRequest,
        onEvent: (PlanEventDto) -> Unit,
    ): EngineResult<PlanResultDto> = coroutineScope {
        ready()?.let { return@coroutineScope EngineResult.Err(it) }
        val listener = PlanEventListener { json ->
            EngineJson.event(json)?.let { ev -> launch(Dispatchers.Main) { onEvent(ev) } }
        }
        EngineJson.planResult(cancellable(requestId) { host.callHere("plan", world, requestId, request.toInputJson(), listener) })
    }

    /**
     * Runs a blocking engine call on `verst-python`; while it runs a sibling watches for the caller's
     * cancellation and then tells the engine (`mobile.cancel`, the one call allowed from another thread), which
     * makes the call return `CANCELLED` at its next check.
     */
    private suspend fun cancellable(requestId: String, call: () -> String): String = coroutineScope {
        val finished = AtomicBoolean(false)
        val watcher = launch {
            try {
                awaitCancellation()
            } finally {
                if (!finished.get()) withContext(NonCancellable + Dispatchers.Default) { host.cancel(requestId) }
            }
        }
        val envelope = withContext(host.dispatcher) { call() }
        finished.set(true)
        watcher.cancel()
        envelope
    }
}
