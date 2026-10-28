package app.verst.engine

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import app.verst.core.model.EngineResult
import app.verst.core.model.PlanRequest
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlanOutcome
import app.verst.data.net.ServerClient
import app.verst.data.net.ServerUnavailable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch

/** Where the last plan was built, for the settings screen. */
data class PlanSource(val server: Boolean, val ms: Long, val fallbackReason: String? = null)

/**
 * SRV-01: the plan goes to the server when the setting says so and the phone is online; everything else, and
 * the plan whenever the server cannot give one, is the phone engine ([phone]). Only the engine's verdict about the
 * trip itself (`ServerClient.FINAL`: unreachable, too short) is final; any other server failure falls back.
 */
class ServerPlannerGateway(
    private val phone: PlannerGateway,
    private val server: ServerClient,
    private val enabled: () -> Boolean,
    private val online: () -> Boolean,
    private val now: () -> Long = System::currentTimeMillis,
) : PlannerGateway by phone {
    var lastPlan: PlanSource? by mutableStateOf(null)
        private set

    override suspend fun planOutcome(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanOutcome> {
        if (!enabled() || !server.configured) return phone.planOutcome(requestId, request, onEvent)
        if (!online()) return fallback(requestId, request, onEvent, "offline")
        val t0 = now()
        return try {
            coroutineScope {
                val r = server.plan(request.toInputJson()) { ev -> launch(Dispatchers.Main) { onEvent(ev) } }
                lastPlan = PlanSource(server = true, ms = now() - t0)
                r
            }
        } catch (e: ServerUnavailable) {
            currentCoroutineContext().ensureActive() // a cancelled plan is not retried on the phone
            fallback(requestId, request, onEvent, e.message ?: "unavailable")
        }
    }

    private suspend fun fallback(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit, reason: String): EngineResult<PlanOutcome> {
        val t0 = now()
        val r = phone.planOutcome(requestId, request, onEvent)
        lastPlan = PlanSource(server = false, ms = now() - t0, fallbackReason = reason)
        return r
    }
}
