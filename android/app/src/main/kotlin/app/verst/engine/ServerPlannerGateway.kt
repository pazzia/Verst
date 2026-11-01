package app.verst.engine

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import app.verst.core.model.EngineResult
import app.verst.core.model.PlanRequest
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.PlanEventDto
import app.verst.core.model.dto.PlanOutcome
import app.verst.data.net.PlanServer
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
 * trip itself (`ServerClient.isFinal`: unreachable, too short, a point abroad it cannot plan) is final; any other
 * server failure falls back.
 *
 * CEO 29.10 (trips abroad, wave 1): a request with [PlanRequest.abroad] goes to the server whatever [enabled] says
 * (the phone engine knows only Russia), and never falls back to the phone: without a server, consent or network, or
 * when the server fails, the answer is an error the Drive screen shows ([ABROAD_NO_SERVER], [ABROAD_NO_CONSENT],
 * [ABROAD_OFFLINE], `UPSTREAM`).
 */
class ServerPlannerGateway(
    private val phone: PlannerGateway,
    private val server: PlanServer,
    private val enabled: () -> Boolean,
    private val online: () -> Boolean,
    private val now: () -> Long = System::currentTimeMillis,
    /** Security review В-1: the tester agreed to plan on the server (the app asks before the first trip abroad). */
    private val consent: () -> Boolean = { true },
) : PlannerGateway by phone {
    var lastPlan: PlanSource? by mutableStateOf(null)
        private set

    /** This build has a server: a trip abroad can be planned (online). */
    val serverConfigured: Boolean get() = server.configured

    override suspend fun planOutcome(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanOutcome> {
        if (request.abroad) return abroad(request, onEvent)
        if (!enabled() || !server.configured) return phone.planOutcome(requestId, request, onEvent)
        if (!online()) return fallback(requestId, request, onEvent, "offline")
        val t0 = now()
        return try {
            onServer(request, onEvent).also { lastPlan = PlanSource(server = true, ms = now() - t0) }
        } catch (e: ServerUnavailable) {
            currentCoroutineContext().ensureActive() // a cancelled plan is not retried on the phone
            fallback(requestId, request, onEvent, e.message ?: "unavailable")
        }
    }

    /** A trip abroad: the server or an error — the phone engine would only reject it (`outside_russia`). */
    private suspend fun abroad(request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanOutcome> {
        if (!server.configured) return EngineResult.Err(EngineErrorDto(ABROAD_NO_SERVER, "no server in this build"))
        if (!consent()) return EngineResult.Err(EngineErrorDto(ABROAD_NO_CONSENT, "no consent to plan on the server"))
        if (!online()) return EngineResult.Err(EngineErrorDto(ABROAD_OFFLINE, "offline"))
        val t0 = now()
        return try {
            onServer(request, onEvent).also { lastPlan = PlanSource(server = true, ms = now() - t0) }
        } catch (e: ServerUnavailable) {
            currentCoroutineContext().ensureActive()
            EngineResult.Err(EngineErrorDto("UPSTREAM", "server: ${e.message ?: "unavailable"}"))
        }
    }

    private suspend fun onServer(request: PlanRequest, onEvent: (PlanEventDto) -> Unit): EngineResult<PlanOutcome> = coroutineScope {
        server.plan(request.toInputJson()) { ev -> launch(Dispatchers.Main) { onEvent(ev) } }
    }

    private suspend fun fallback(requestId: String, request: PlanRequest, onEvent: (PlanEventDto) -> Unit, reason: String): EngineResult<PlanOutcome> {
        val t0 = now()
        val r = phone.planOutcome(requestId, request, onEvent)
        lastPlan = PlanSource(server = false, ms = now() - t0, fallbackReason = reason)
        return r
    }

    companion object {
        /** A trip abroad in a build without a server. */
        const val ABROAD_NO_SERVER = "ABROAD_NO_SERVER"

        /** A trip abroad before the tester agreed to plan on the server. */
        const val ABROAD_NO_CONSENT = "ABROAD_NO_CONSENT"

        /** A trip abroad without the network. */
        const val ABROAD_OFFLINE = "ABROAD_OFFLINE"
    }
}
