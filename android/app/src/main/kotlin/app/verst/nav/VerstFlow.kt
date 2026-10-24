package app.verst.nav

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import app.verst.core.model.BudgetPresets
import app.verst.core.model.DefaultOrigin
import app.verst.core.model.EngineArgs
import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.core.model.Mood
import app.verst.core.model.PlanRequest
import app.verst.core.model.SavedTripDto
import app.verst.core.model.SavedTrips
import app.verst.core.model.TripFigures
import app.verst.core.model.TripFiguresPick
import app.verst.core.model.TripMath
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.dto.SuggestionDto
import app.verst.data.TripStore
import app.verst.engine.PlannerGateway
import java.util.UUID
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** The routes of the slice (M§7 subset). */
enum class Route { Windshield, Navigator, Instruments, Drive, Road, Waybill }

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

/** Plate toasts of 5.5/5.6/D-6 (components §16 `PlateToast`); the screen picks the copy by type. */
sealed interface Toast {
    data class Replaced(val totalRub: Int) : Toast
    data object Saved : Toast
    data class SavedNearLimit(val count: Int) : Toast
    data object StorageFull : Toast
    data object EngineFailed : Toast
}

/** The D-6 replace sheet: the stop, the picked alternative (null = keep), whether the engine call runs. */
data class ReplaceUi(val stop: StopDto, val picked: String? = null, val busy: Boolean = false)

/**
 * The app's state for the vertical slice: back stack, plan draft (origin, destination or ready route),
 * instrument values, the engine's figures of the draft, the running plan, the current trip (fresh or saved) and
 * the saved trips. Lives in `VerstApp`, so it survives activity recreation. All mutation happens on the main
 * thread.
 */
class VerstFlow(
    private val gateway: PlannerGateway,
    private val scope: CoroutineScope,
    private val store: TripStore,
    private val io: CoroutineDispatcher = Dispatchers.IO,
    private val now: () -> Long = System::currentTimeMillis,
    private val retryEngine: () -> Unit,
) {
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

    /** Base-route km from the origin to suggestion rows («lat,lon» → km; null = unreachable). */
    val rowKm = mutableStateMapOf<String, Int?>()

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

    // ---- engine figures (P0: one trip, one distance)
    /** Engine km/days per request: `estimate` results and plans (newest last, ≤ 24). */
    private val known = mutableStateListOf<Pair<PlanRequest, TripFigures>>()

    /** The estimate error of a request (TOO_SHORT / UNREACHABLE / INVALID_INPUT before the plan). */
    var estimateError: Pair<PlanRequest, EngineErrorDto>? by mutableStateOf(null)
        private set

    // ---- Drive / Road / Waybill
    var drive by mutableStateOf(DriveUi())
        private set

    /** The trip on Road ahead and the Waybill (fresh plan or reopened saved trip). */
    var result: PlanResultDto? by mutableStateOf(null)
        private set

    /** The request [result] was planned from (null for a reopened saved trip). */
    private var resultRequest: PlanRequest? = null
    var resultBearing by mutableStateOf("N")
        private set
    var openedFromSaved by mutableStateOf(false)
        private set
    private var planJob: Job? = null

    var expandedLine: String? by mutableStateOf(null)
        private set
    var costBusy by mutableStateOf(false)
        private set
    var replace: ReplaceUi? by mutableStateOf(null)
        private set
    var toast: Toast? by mutableStateOf(null)
        private set
    private var undoTrip: PlanResultDto? = null
    private var toastJob: Job? = null

    // ---- saved trips
    val saved = mutableStateListOf<SavedTripDto>()

    /** Id of [result] in [saved] (null = never saved); [savedCurrent] = the saved copy equals [result]. */
    var savedId: String? by mutableStateOf(null)
        private set
    var savedCurrent by mutableStateOf(false)
        private set
    var tripsSheet by mutableStateOf(false)
        private set

    val adults: Int get() = 1 + (if (frontAdult) 1 else 0) + seats.count { it == Seat.ADULT }
    val children: Int get() = seats.count { it == Seat.CHILD }

    init {
        loadRoutes()
        scope.launch {
            val trips = withContext(io) { runCatching { store.load() }.getOrDefault(emptyList()) }
            saved.clear()
            saved.addAll(trips)
        }
        // Navigator / Instruments: estimate the draft on the engine 300 ms after it settles; leaving the screens
        // (or a newer draft) cancels the running estimate in the engine too.
        scope.launch {
            snapshotFlow { estimateTarget() }.distinctUntilChanged().collectLatest { r ->
                if (r == null || known.any { it.first == r }) return@collectLatest
                delay(ESTIMATE_DEBOUNCE_MS)
                when (val e = gateway.estimate(UUID.randomUUID().toString(), r)) {
                    is EngineResult.Ok -> {
                        record(r, TripFigures(e.value.km, e.value.days))
                        if (estimateError?.first == r) estimateError = null
                    }
                    is EngineResult.Err -> if (e.error.code != "CANCELLED") estimateError = r to e.error
                }
            }
        }
    }

    // ------------------------------------------------------------------------------------------ navigation

    fun push(route: Route) {
        stack.add(route)
    }

    /** System back and every back link. Sheets close first. Returns false on the root (the activity finishes). */
    fun back(): Boolean {
        if (replace != null) {
            closeReplace()
            return true
        }
        if (tripsSheet) {
            tripsSheet = false
            return true
        }
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

    /** Navi panel on 5.1 → Navigator, КУДА focused. The draft becomes a free A → B trip. */
    fun openNavigator() {
        editingFrom = false
        routeError = null
        readyRoute = null
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
            if (popular.isEmpty()) loadPopular() else fetchRowKm(popular)
            return
        }
        searching = true
        suggestJob = scope.launch {
            delay(250) // 5.2 debounce
            when (val r = gateway.suggest(q.trim(), origin)) {
                is EngineResult.Ok -> {
                    suggestions = r.value
                    fetchRowKm(r.value)
                }
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
            if (r is EngineResult.Ok) {
                popular = r.value
                fetchRowKm(r.value)
            }
        }
    }

    private fun fetchRowKm(rows: List<SuggestionDto>) {
        val missing = rows.filter { it.pointKey !in rowKm }
        if (missing.isEmpty()) return
        val from = origin
        scope.launch {
            val r = gateway.estimatePoints(from, missing.map { GeoPoint(it.name, it.lat, it.lon) })
            if (r is EngineResult.Ok && from == origin) missing.zip(r.value).forEach { (s, km) -> rowKm[s.pointKey] = km }
        }
    }

    fun startEditFrom() {
        editingFrom = true
        updateQuery("")
    }

    fun pick(s: SuggestionDto) {
        if (editingFrom) {
            origin = GeoPoint(s.name, s.lat, s.lon)
            rowKm.clear()
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

    /** ПОЕХАЛИ on 5.2 → Instruments with A → B. */
    fun openInstrumentsFree() {
        val d = destination ?: return
        readyRoute = null
        dailyKm = TripMath.defaultDailyKm(rowKm[d.pointKey] ?: 0)
        push(Route.Instruments)
    }

    // ------------------------------------------------------------------------------------------ instruments

    /** The draft request when it has a target (destination or ready route), else null. */
    fun draft(): PlanRequest? = if (readyRoute != null || destinationPoint != null) request() else null

    private fun estimateTarget(): PlanRequest? =
        if ((top == Route.Navigator && !editingFrom) || top == Route.Instruments) draft() else null

    /** The engine's km/days of the draft: exact for this request, stale while a newer estimate runs, or null. */
    val figures: TripFiguresPick.Picked?
        get() = TripFiguresPick.pick(draft(), known)

    /** TOO_SHORT / UNREACHABLE of the current draft (before any plan). */
    val draftError: EngineErrorDto?
        get() = estimateError?.takeIf { it.first == draft() }?.second

    private fun record(r: PlanRequest, f: TripFigures) {
        known.removeAll { it.first == r }
        known.add(r to f)
        while (known.size > 24) known.removeAt(0)
    }

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
                    showTrip(r.value, request, readyRoute?.bearing8 ?: "N", savedId = null, fromSaved = false)
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

    private fun showTrip(r: PlanResultDto, request: PlanRequest?, bearing: String, savedId: String?, fromSaved: Boolean) {
        result = r
        resultRequest = request
        resultBearing = bearing
        this.savedId = savedId
        savedCurrent = savedId != null
        openedFromSaved = fromSaved
        expandedLine = null
        replace = null
        undoTrip = null
        if (request != null) record(request, TripFigures(r.trip.km, r.trip.days)) // after planning: the engine's number
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

    // ------------------------------------------------------------------------------------------ road / waybill

    /** Road footer «ПУТЕВОЙ ЛИСТ · СКОЛЬКО СТОИТ» → Waybill 5.6. */
    fun openWaybill() {
        if (result == null) return
        expandedLine = null
        push(Route.Waybill)
    }

    /** 5.6 P-09: one line expanded at a time. */
    fun toggleLine(key: String) {
        expandedLine = if (expandedLine == key) null else key
    }

    /** 5.6 reserve row: the engine's `patch_cost {reserveOn}` (local, on-device); total and remainder follow. */
    fun toggleReserve() {
        val r = result ?: return
        if (costBusy) return
        costBusy = true
        scope.launch {
            when (val p = gateway.patchCost(r.tripJson, EngineArgs.reservePatch(!r.trip.cost.reserveOn))) {
                is EngineResult.Ok -> updateTrip(p.value)
                is EngineResult.Err -> showToast(Toast.EngineFailed)
            }
            costBusy = false
        }
    }

    private fun updateTrip(r: PlanResultDto) {
        result = r
        savedCurrent = false
        resultRequest?.let { record(it, TripFigures(r.trip.km, r.trip.days)) }
    }

    /** «заменить» on a stop → D-6 sheet. */
    fun openReplace(stop: StopDto) {
        replace = ReplaceUi(stop)
    }

    fun pickAlternative(altId: String?) {
        replace = replace?.copy(picked = altId)
    }

    fun closeReplace() {
        if (replace?.busy != true) replace = null
    }

    /** «ЗАМЕНИТЬ»: the engine's `replace_stop`; the trip and the total update, toast with «Вернуть». */
    fun confirmReplace() {
        val ui = replace ?: return
        val alt = ui.picked ?: return
        val r = result ?: return
        replace = ui.copy(busy = true)
        scope.launch {
            when (val n = gateway.replaceStop(r.tripJson, ui.stop.id, alt)) {
                is EngineResult.Ok -> {
                    undoTrip = r
                    updateTrip(n.value)
                    replace = null
                    showToast(Toast.Replaced(n.value.trip.cost.totalRub))
                }
                is EngineResult.Err -> {
                    replace = null
                    showToast(Toast.EngineFailed)
                }
            }
        }
    }

    /** «Вернуть» on the replace toast: the trip before the replace. */
    fun undo() {
        val prev = undoTrip ?: return
        undoTrip = null
        updateTrip(prev)
        dismissToast()
    }

    val canUndo: Boolean get() = undoTrip != null && toast is Toast.Replaced

    private fun showToast(t: Toast) {
        toast = t
        toastJob?.cancel()
        toastJob = scope.launch {
            delay(if (t is Toast.Replaced) 6_000 else 3_000)
            toast = null
            if (t is Toast.Replaced) undoTrip = null
        }
    }

    fun dismissToast() {
        toastJob?.cancel()
        toast = null
    }

    // ------------------------------------------------------------------------------------------ saved trips

    /** Save (5.5 T1 / 5.6 K1): upsert into the saved list, then write the file. */
    fun save() {
        val r = result ?: return
        val id = savedId ?: UUID.randomUUID().toString()
        when (val up = SavedTrips.upsert(saved.toList(), SavedTrips.entry(id, now(), r, resultBearing))) {
            SavedTrips.Upsert.LimitReached -> showToast(Toast.StorageFull)
            is SavedTrips.Upsert.Saved -> {
                saved.clear()
                saved.addAll(up.trips)
                savedId = id
                savedCurrent = true
                showToast(if (up.nearLimit) Toast.SavedNearLimit(up.count) else Toast.Saved)
                val snapshot = up.trips
                scope.launch { withContext(io) { runCatching { store.save(snapshot) } } }
            }
        }
    }

    /** Waybill «№ 001»: the trip's ordinal among the saved trips (1 when not saved). */
    val waybillNumber: Int
        get() = savedId?.let { id -> SavedTrips.ordered(saved).indexOfFirst { it.id == id }.takeIf { it >= 0 }?.plus(1) } ?: 1

    fun openTrips() {
        if (saved.isNotEmpty()) tripsSheet = true
    }

    /** D-1 row → Road ahead of the saved trip; back goes to the Windshield («К лобовому», OI-27). */
    fun openSaved(id: String) {
        val s = saved.firstOrNull { it.id == id } ?: return
        tripsSheet = false
        showTrip(SavedTrips.result(s), request = null, bearing = s.bearing8, savedId = s.id, fromSaved = true)
        while (stack.size > 1) stack.removeAt(stack.lastIndex)
        push(Route.Road)
    }

    /** e2e: start from an empty list. */
    fun clearSaved() {
        saved.clear()
        savedId = null
        savedCurrent = false
        scope.launch { withContext(io) { runCatching { store.save(emptyList()) } } }
    }

    companion object {
        const val STEP_GAP_MS = 400L
        const val AUTO_ADVANCE_MS = 1000L
        const val ESTIMATE_DEBOUNCE_MS = 300L
        val ENGINE_START_CODES = setOf("NO_ENGINE", "ENGINE_START", "NO_WORLD", "TZDATA_MISSING")
    }
}
