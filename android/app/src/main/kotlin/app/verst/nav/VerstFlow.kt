package app.verst.nav

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import app.verst.core.model.BudgetPresets
import app.verst.core.model.DefaultOrigin
import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.core.model.Mood
import app.verst.core.model.PlanRequest
import app.verst.core.model.TripMath
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.SuggestionDto
import app.verst.engine.PlannerGateway
import java.util.UUID
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** The 5 routes of the slice (M§7 subset). */
enum class Route { Windshield, Navigator, Instruments, Drive, Road }

sealed interface WindshieldData {
    data object Loading : WindshieldData
    data class Routes(val routes: List<ReadyRouteDto>) : WindshieldData
    data object NoRoutes : WindshieldData
    data class Failed(val engineFailed: Boolean) : WindshieldData
}

enum class Seat { EMPTY, ADULT, CHILD }

/** Error → copy and action (5.4 §4.4, M§9). */
enum class DriveAction { RETRY, TO_INSTRUMENTS, CHANGE_ROUTE }

data class DriveUi(
    val lines: List<String> = emptyList(),
    val progress: Float = 0f,
    /** Trip days once the engine has placed stops (0 = not known yet). */
    val days: Int = 0,
    val done: Boolean = false,
    val error: EngineErrorDto? = null,
)

/**
 * The app's state for the thin vertical slice: back stack, plan draft (origin, destination or ready route),
 * instrument values, the running plan and the planned trip. Lives in `VerstApp`, so it survives activity
 * recreation. All mutation happens on the main thread.
 */
class VerstFlow(private val gateway: PlannerGateway, private val scope: CoroutineScope, private val retryEngine: () -> Unit) {
    val stack = mutableStateListOf(Route.Windshield)
    val top: Route get() = stack.last()

    // ---- Windshield
    var origin: GeoPoint by mutableStateOf(DefaultOrigin)
        private set
    var windshield: WindshieldData by mutableStateOf(WindshieldData.Loading)
        private set
    var selectedRoute by mutableStateOf(0)

    // ---- Navigator
    var query by mutableStateOf("")
        private set
    var suggestions: List<SuggestionDto> by mutableStateOf(emptyList())
        private set
    var popular: List<SuggestionDto> by mutableStateOf(emptyList())
        private set
    var suggestFailed by mutableStateOf(false)
        private set
    var searching by mutableStateOf(false)
        private set
    var destination: SuggestionDto? by mutableStateOf(null)
        private set
    var editingFrom by mutableStateOf(false)
        private set

    /** TOO_SHORT / UNREACHABLE from the last plan, shown in the Navigator caption (5.2 §4.4). */
    var routeError: String? by mutableStateOf(null)
        private set
    private var suggestJob: Job? = null

    // ---- Instruments
    var readyRoute: ReadyRouteDto? by mutableStateOf(null)
        private set
    var frontAdult by mutableStateOf(true)
    val seats = mutableStateListOf(Seat.EMPTY, Seat.EMPTY, Seat.EMPTY)
    var dog by mutableStateOf(false)
    var dailyKm by mutableStateOf(300)
    var budgetIndex by mutableStateOf(BudgetPresets.indexOf(40_000))
    var mood: Mood? by mutableStateOf(null)
    private var moodTouched = false

    // ---- Drive / Road
    var drive by mutableStateOf(DriveUi())
        private set
    var result: PlanResultDto? by mutableStateOf(null)
        private set
    private var planJob: Job? = null

    val adults: Int get() = 1 + (if (frontAdult) 1 else 0) + seats.count { it == Seat.ADULT }
    val children: Int get() = seats.count { it == Seat.CHILD }

    init {
        loadRoutes()
    }

    // ------------------------------------------------------------------------------------------ navigation

    fun push(route: Route) {
        stack.add(route)
    }

    /** System back and every back link. Returns false on the root (the activity then finishes). */
    fun back(): Boolean {
        if (stack.size <= 1) return false
        when (top) {
            Route.Drive -> cancelPlan()
            Route.Navigator -> if (editingFrom) {
                editingFrom = false
                updateQuery("")
                return true
            }
            else -> Unit
        }
        stack.removeAt(stack.lastIndex)
        return true
    }

    // ------------------------------------------------------------------------------------------ windshield

    fun loadRoutes() {
        windshield = WindshieldData.Loading
        scope.launch {
            windshield = when (val r = gateway.readyRoutes(origin)) {
                is EngineResult.Ok -> if (r.value.isEmpty()) WindshieldData.NoRoutes else WindshieldData.Routes(r.value)
                is EngineResult.Err -> WindshieldData.Failed(r.error.code in ENGINE_START_CODES)
            }
            selectedRoute = 0
        }
    }

    fun retryWindshield() {
        retryEngine()
        loadRoutes()
    }

    val selected: ReadyRouteDto?
        get() = (windshield as? WindshieldData.Routes)?.routes?.getOrNull(selectedRoute)

    /** ПОЕХАЛИ / mirror on 5.1 → Instruments with the selected ready route. */
    fun openReadyRoute() {
        val r = selected ?: return
        readyRoute = r
        destination = null
        dailyKm = TripMath.defaultDailyKm(r.kmTotal)
        push(Route.Instruments)
    }

    /** Navi panel on 5.1 → Navigator, КУДА focused. */
    fun openNavigator() {
        editingFrom = false
        routeError = null
        updateQuery("")
        push(Route.Navigator)
    }

    // ------------------------------------------------------------------------------------------ navigator

    fun updateQuery(q: String) {
        query = q
        suggestJob?.cancel()
        suggestFailed = false
        if (q.trim().length < 2) {
            suggestions = emptyList()
            searching = false
            if (popular.isEmpty()) loadPopular()
            return
        }
        searching = true
        suggestJob = scope.launch {
            delay(250) // 5.2 debounce
            when (val r = gateway.suggest(q.trim(), origin)) {
                is EngineResult.Ok -> suggestions = r.value
                is EngineResult.Err -> {
                    suggestions = emptyList()
                    suggestFailed = true
                }
            }
            searching = false
        }
    }

    private fun loadPopular() {
        scope.launch {
            val r = gateway.popular()
            if (r is EngineResult.Ok) popular = r.value
        }
    }

    fun startEditFrom() {
        editingFrom = true
        updateQuery("")
    }

    fun pick(s: SuggestionDto) {
        if (editingFrom) {
            origin = GeoPoint(s.name, s.lat, s.lon)
            editingFrom = false
            loadRoutes()
            routeError = null
            updateQuery("")
        } else {
            destination = s
            routeError = null
            suggestJob?.cancel()
            searching = false
            suggestions = emptyList()
            query = s.name
        }
    }

    val destinationPoint: GeoPoint? get() = destination?.let { GeoPoint(it.name, it.lat, it.lon) }

    fun straightKm(): Int? = destinationPoint?.let { TripMath.haversineKm(origin, it).toInt() }

    /** ПОЕХАЛИ on 5.2 → Instruments with A → B. */
    fun openInstrumentsFree() {
        val d = destinationPoint ?: return
        readyRoute = null
        dailyKm = TripMath.defaultDailyKm(TripMath.roadKmEstimate(origin, d))
        push(Route.Instruments)
    }

    // ------------------------------------------------------------------------------------------ instruments

    /** Trip km for the estimates: the ready route km or straight line × 1.25 (A§11.11). */
    val tripKm: Int
        get() = readyRoute?.kmTotal ?: destinationPoint?.let { TripMath.roadKmEstimate(origin, it) } ?: 0

    val tripTitle: String
        get() = readyRoute?.title ?: "${origin.label} → ${destination?.name ?: "?"}"

    /** Seat cycle empty → adult → child → empty; ≤ 8 people incl. the driver (OI-07). */
    fun cycleSeat(i: Int) {
        seats[i] = when (seats[i]) {
            Seat.EMPTY -> Seat.ADULT
            Seat.ADULT -> Seat.CHILD
            Seat.CHILD -> Seat.EMPTY
        }
        if (!moodTouched) mood = if (children > 0) Mood.CALM else null
    }

    fun pickMood(m: Mood) {
        moodTouched = true
        mood = if (mood == m) null else m
    }

    fun stepKm(delta: Int) {
        dailyKm = (dailyKm + delta).coerceIn(TripMath.KM_MIN, TripMath.KM_MAX)
    }

    fun stepBudget(delta: Int) {
        budgetIndex = (budgetIndex + delta).coerceIn(0, BudgetPresets.lastIndex)
    }

    fun request(): PlanRequest = PlanRequest(
        origin = origin,
        destination = if (readyRoute == null) destinationPoint else null,
        readyRouteId = readyRoute?.id,
        adults = adults,
        children = children,
        dog = dog,
        dailyKm = dailyKm,
        budgetRub = BudgetPresets[budgetIndex],
        mood = mood,
    )

    // ------------------------------------------------------------------------------------------ drive

    /** ПОЕХАЛИ on 5.3 → Drive; the plan runs on `verst-python`, the steps are paced ≥ 400 ms (5.4 §6). */
    fun go() {
        if (top != Route.Drive) push(Route.Drive)
        startPlan()
    }

    fun retryPlan() = startPlan()

    private fun startPlan() {
        planJob?.cancel()
        drive = DriveUi()
        result = null
        val request = request()
        val id = UUID.randomUUID().toString()
        planJob = scope.launch {
            val pending = ArrayDeque<Pair<String, Float>>() // stage text, engine progress at that stage
            var days = 0
            var finished: EngineResult<PlanResultDto>? = null
            val engine = launch {
                finished = gateway.plan(id, request) { ev ->
                    when (ev.event) {
                        "stage" -> ev.text?.let { t ->
                            if (pending.none { it.first == t } && t !in drive.lines) pending.addLast(t to (ev.progress ?: 0.0).toFloat())
                        }
                        "stop" -> days = maxOf(days, ev.day ?: 0) // days as the engine splits them, not the estimate
                    }
                    Unit
                }
            }
            // Pacer: reveal one step per 400 ms while the engine works (or until the queue is empty); the bar
            // follows the revealed step, so it never runs ahead of the text.
            while (engine.isActive || pending.isNotEmpty()) {
                if (pending.isNotEmpty()) {
                    val (text, progress) = pending.removeFirst()
                    drive = drive.copy(lines = drive.lines + text, progress = maxOf(drive.progress, progress), days = days)
                } else {
                    drive = drive.copy(days = days)
                }
                delay(STEP_GAP_MS)
            }
            when (val r = finished) {
                is EngineResult.Ok -> {
                    result = r.value
                    drive = drive.copy(progress = 1f, done = true, days = r.value.trip.days)
                    delay(AUTO_ADVANCE_MS)
                    if (top == Route.Drive) openRoad()
                }
                is EngineResult.Err -> if (r.error.code == "CANCELLED") {
                    if (top == Route.Drive) stack.removeAt(stack.lastIndex)
                } else {
                    drive = drive.copy(error = r.error)
                }
                null -> drive = drive.copy(error = EngineErrorDto("INTERNAL", "no result"))
            }
        }
    }

    private fun cancelPlan() {
        planJob?.cancel()
        planJob = null
    }

    /** CTA «Дорога готова — смотреть знаки» / auto-advance: Drive is replaced by Road (popUpTo Drive inclusive). */
    fun openRoad() {
        if (result == null) return
        if (top == Route.Drive) stack[stack.lastIndex] = Route.Road else push(Route.Road)
    }

    fun driveAction(code: String): DriveAction = when (code) {
        "INVALID_INPUT" -> DriveAction.TO_INSTRUMENTS
        "UNREACHABLE", "TOO_SHORT" -> DriveAction.CHANGE_ROUTE
        else -> DriveAction.RETRY
    }

    /** Error CTA: retry, back to Instruments, or back to the Navigator with the error in its caption. */
    fun onDriveError(action: DriveAction, message: String) {
        when (action) {
            DriveAction.RETRY -> retryPlan()
            DriveAction.TO_INSTRUMENTS -> back()
            DriveAction.CHANGE_ROUTE -> {
                cancelPlan()
                val nav = stack.lastIndexOf(Route.Navigator)
                if (nav >= 0) {
                    while (stack.size > nav + 1) stack.removeAt(stack.lastIndex)
                    routeError = message
                } else {
                    back()
                }
            }
        }
    }

    companion object {
        const val STEP_GAP_MS = 400L
        const val AUTO_ADVANCE_MS = 1000L
        val ENGINE_START_CODES = setOf("NO_ENGINE", "ENGINE_START", "NO_WORLD", "TZDATA_MISSING")
    }
}
