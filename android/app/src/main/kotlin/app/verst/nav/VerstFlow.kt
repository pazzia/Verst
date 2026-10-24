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
import app.verst.core.model.cost.CostApply
import app.verst.core.model.cost.LocalCost
import app.verst.engine.Connectivity
import app.verst.core.model.dto.EngineErrorDto
import app.verst.core.model.dto.PlanResultDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.dto.SuggestionDto
import app.verst.core.model.DefaultsDto
import app.verst.core.model.LastTripDto
import app.verst.data.TripStore
import app.verst.data.TripsLoad
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
enum class Route { Windshield, Navigator, Instruments, Drive, Road, Waybill, Exit, Debug }

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
    /** 5.4 flying signs: the engine's `stop` events in arrival order. */
    val signs: List<app.verst.core.model.dto.StopEventDto> = emptyList(),
)

/** Plate toasts of 5.5/5.6/D-6 (components §16 `PlateToast`); the screen picks the copy by type. */
sealed interface Toast {
    data class Replaced(val totalRub: Int) : Toast
    data object Saved : Toast
    data class SavedNearLimit(val count: Int) : Toast
    data object StorageFull : Toast
    data object EngineFailed : Toast
    data object NeedInternet : Toast

    /** «Отметили: ночёвка в … забронирована» + «Вернуть» (stop id). */
    data class Booked(val stopId: String) : Toast
    data object TripDeleted : Toast
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
    /** E-08 / M§9: simulated connectivity (the mock needs no network; the debug panel switches it off). */
    val connectivity: Connectivity = Connectivity(),
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

    /** D-1 deletion: the trip awaiting confirmation (NaviDialog), the last deleted one for «Вернуть». */
    var deleteAsk: SavedTripDto? by mutableStateOf(null)
        private set
    private var lastDeleted: Pair<Int, SavedTripDto>? = null

    /** 5.5 §4 limit: the «Место для поездок закончилось» dialog. */
    var limitDialog by mutableStateOf(false)
        private set

    // ---- Exit 5.7 / D-10
    var exitStopId: String? by mutableStateOf(null)
        private set
    var partnerOpen by mutableStateOf(false)
        private set
    var bookedDialog by mutableStateOf(false)
        private set

    /** 5.7 §8: per overnight stop, the hotel marked «Забронировали» (persisted with a saved trip). */
    val booked = mutableStateMapOf<String, String>()
    private var undoBooked: String? = null

    /** OI-39: the origin's genitive from the engine («Москвы»), the nominative until known. */
    var originGen by mutableStateOf(DefaultOrigin.label)
        private set

    /** Trips whose Waybill stamp has played (motion.stamp once per trip version, 5.6 §3.1). */
    private val stampShown = mutableSetOf<String>()

    // ---- DEV-127 debug panel (plain list, not part of visual QA)
    var debugGolden by mutableStateOf(false)
        private set
    var debugSlowSec by mutableStateOf(0)
    /** null = no forced error; else the engine code the next plan returns. */
    var debugForceError: String? by mutableStateOf(null)
    val debugWorld: String get() = gateway.world

    fun openDebug() = push(Route.Debug)

    fun setWorld(id: String) {
        if (gateway.world == id) return
        gateway.world = id
        origin = if (id == app.verst.core.model.DefaultWorld) DefaultOrigin else GeoPoint("Тестовск", 58.0, 50.0)
        originGen = origin.label
        known.clear()
        rowKm.clear()
        popular = emptyList()
        destination = null
        loadRoutes()
        loadOriginForms()
    }

    fun setGoldenClock(on: Boolean) {
        debugGolden = on
        known.clear()
        scope.launch { gateway.setClock(if (on) "golden" else "system") }
    }

    fun setOffline(on: Boolean) {
        connectivity.online = !on
    }

    /** «Сбросить данные»: saved trips, the current trip and the draft. */
    var resetAsk by mutableStateOf(false)
        private set

    /** «Сбросить данные» asks first (release review P2-3). */
    fun askReset() {
        resetAsk = true
    }

    fun cancelReset() {
        resetAsk = false
    }

    fun resetData() {
        resetAsk = false
        clearSaved()
        result = null
        booked.clear()
        destination = null
        known.clear()
        dailyKmTouched = false
        moodTouched = false
        frontAdult = true
        for (i in seats.indices) seats[i] = Seat.EMPTY
        dog = false
        dailyKm = 300
        budgetIndex = BudgetPresets.indexOf(40_000)
        mood = null
        while (stack.size > 1) stack.removeAt(stack.lastIndex)
    }

    val adults: Int get() = 1 + (if (frontAdult) 1 else 0) + seats.count { it == Seat.ADULT }
    val children: Int get() = seats.count { it == Seat.CHILD }

    init {
        loadRoutes()
        loadOriginForms()
        // P1-1 / P1-2: load the saved trips and the last trip first; saves wait for this (no save may write an
        // in-memory list that lacks the stored trips), then one writer serializes every write.
        scope.launch {
            val load = withContext(io) { runCatching { store.load() }.getOrElse { TripsLoad.Unreadable("io: $it") } }
            saved.clear()
            if (load is TripsLoad.Ok) saved.addAll(load.trips)
            val last = withContext(io) { runCatching { store.loadLast() }.getOrNull() }
            val defaults = withContext(io) { runCatching { store.loadDefaults() }.getOrNull() }
            if (defaults != null) applyDefaults(defaults)
            tripsLoaded = true
            if (last != null && result == null && stack.size == 1) restoreLast(last)
            if (pendingSave) {
                pendingSave = false
                save()
            }
            writer()
        }
        // F-01: the Windshield sign rows show the engine estimate of each visible ready route for the current
        // crew and pace — the same request (so the same number) Instruments, Drive and Road ahead will show.
        scope.launch {
            snapshotFlow {
                if (top == Route.Windshield) {
                    val visible = (windshield as? WindshieldData.Routes)?.routes?.take(4).orEmpty()
                    // the selected row first, then the others top to bottom
                    (visible.getOrNull(selectedRoute)?.let { listOf(it) }.orEmpty() + visible).distinct().map { routeRequest(it) }
                } else {
                    null
                }
            }.distinctUntilChanged().collectLatest { reqs ->
                // Cached by the whole request (route id, crew, pace, budget, mood, origin); world / clock changes clear
                // `known`. A crew change makes new requests: the rows fall back to the placeholder and re-estimate.
                for (r in reqs.orEmpty()) {
                    if (known.any { it.first == r }) continue
                    val e = gateway.estimate(UUID.randomUUID().toString(), r)
                    if (e is EngineResult.Ok) record(r, TripFigures(e.value.km, e.value.days))
                }
            }
        }
        // P1-2: the current trip and its screen go to last.json after every change (debounced); P2-10: defaults.
        scope.launch {
            snapshotFlow { lastKey() }.distinctUntilChanged().collectLatest {
                delay(LAST_DEBOUNCE_MS)
                if (tripsLoaded) enqueueLast()
            }
        }
        scope.launch {
            snapshotFlow { defaultsNow() }.distinctUntilChanged().collectLatest { d ->
                delay(LAST_DEBOUNCE_MS)
                if (tripsLoaded) {
                    pendingDefaults = d
                    writes.trySend(Unit)
                }
            }
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
        if (bookedDialog) {
            answerBooked(false)
            return true
        }
        if (partnerOpen) {
            closePartner()
            return true
        }
        if (deleteAsk != null) {
            deleteAsk = null
            return true
        }
        if (resetAsk) {
            resetAsk = false
            return true
        }
        if (limitDialog) {
            limitDialog = false
            return true
        }
        if (tripsSheet) {
            tripsSheet = false
            return true
        }
        if (stack.size <= 1) return false
        dismissToast()
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

    /** The request Instruments will plan for ready route [r] (same pace rule as [openReadyRoute]). */
    fun routeRequest(r: ReadyRouteDto): PlanRequest = PlanRequest(
        origin = origin, destination = null, readyRouteId = r.id, adults = adults, children = children, dog = dog,
        dailyKm = if (dailyKmTouched) dailyKm else TripMath.defaultDailyKm(r.kmTotal), budgetRub = BudgetPresets[budgetIndex], mood = mood,
    )

    /** F-01: the engine km of each visible ready route (route id → km), when known. */
    val routeKm: Map<String, Int>
        get() = (windshield as? WindshieldData.Routes)?.routes?.take(4)?.mapNotNull { r ->
            known.lastOrNull { it.first == routeRequest(r) }?.let { r.id to it.second.km }
        }?.toMap().orEmpty()

    /** ПОЕХАЛИ / mirror on 5.1 → Instruments with the selected ready route. */
    fun openReadyRoute() {
        val r = selected ?: return
        readyRoute = r
        destination = null
        if (!dailyKmTouched) dailyKm = TripMath.defaultDailyKm(r.kmTotal) // P2-10: a chosen pace is kept
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
            originGen = s.nameGenRu ?: s.name
            if (s.nameGenRu == null) loadOriginForms()
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
        if (!dailyKmTouched) dailyKm = TripMath.defaultDailyKm(rowKm[d.pointKey] ?: 0)
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
        while (known.size > 48) known.removeAt(0)
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
        dailyKmTouched = true
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
            val forced = debugForceError
            val slowMs = debugSlowSec * 1000L
            val engine = launch {
                if (forced != null) {
                    delay(STEP_GAP_MS)
                    finished = EngineResult.Err(EngineErrorDto(forced, "debug: forced"))
                    return@launch
                }
                finished = gateway.plan(id, request) { ev ->
                    when (ev.event) {
                        "stage" -> ev.text?.let { t ->
                            if (pending.none { it.first == t } && t !in drive.lines) pending.addLast(t to (ev.progress ?: 0.0).toFloat())
                        }
                        "stop" -> {
                            days = maxOf(days, ev.day ?: 0) // days as the engine splits them, not the estimate
                            ev.stop?.let { st -> drive = drive.copy(signs = drive.signs + st) }
                        }
                    }
                    Unit
                }
                if (slowMs > 0) delay(slowMs) // debug «Задержать готовность плана»
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
                    val bearing = readyRoute?.bearing8 ?: request.destination?.let { TripMath.bearing8(request.origin, it) } ?: "N"
                    showTrip(r.value, request, bearing, savedId = null, fromSaved = false)
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

    private fun showTrip(
        r: PlanResultDto,
        request: PlanRequest?,
        bearing: String,
        savedId: String?,
        fromSaved: Boolean,
        bookedStops: Map<String, String> = emptyMap(),
    ) {
        result = r
        tripSession += 1
        booked.clear()
        booked.putAll(bookedStops)
        resultRequest = request
        resultBearing = bearing
        this.savedId = savedId
        savedCurrent = savedId != null
        openedFromSaved = fromSaved
        expandedLine = null
        replace = null
        undoTrip = null
        dismissToast() // a toast belongs to the screen it was raised on
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
        val on = !r.trip.cost.reserveOn
        val session = tripSession
        // Local first (DEV-104 CostCalculator), then the engine's answer overwrites the whole trip.
        localCost(r) { trip -> CostApply.apply(r.trip, LocalCost.reserve(trip, on), on) }
        scope.launch {
            val p = gateway.patchCost(r.tripJson, EngineArgs.reservePatch(on))
            costBusy = false
            if (session != tripSession) return@launch // P2-1: another trip is on screen now
            when (p) {
                is EngineResult.Ok -> updateTrip(p.value)
                is EngineResult.Err -> {
                    result = r
                    showToast(Toast.EngineFailed)
                }
            }
        }
    }

    /** Shows [f]'s local trip at once (the engine trip JSON stays the source for the next engine call). */
    private fun localCost(r: PlanResultDto, f: (kotlinx.serialization.json.JsonObject) -> app.verst.core.model.dto.TripDto) {
        runCatching { f(LocalCost.parse(r.tripJson)) }.onSuccess { result = r.copy(trip = it) }
    }

    /** Waybill stamp: true the first time it is asked for this trip version (then the final frame). */
    fun stampOnce(): Boolean = stampShown.add(tripSession.toString())

    /** Increments when a new trip is shown (plan or reopened saved trip); cost edits keep the session. */
    var tripSession by mutableStateOf(0)
        private set

    // ------------------------------------------------------------------------------------------ exit 5.7

    /** Road-ahead night row «Выбрать отель →» → 5.7 for that night. */
    fun openExit(stopId: String) {
        exitStopId = stopId
        partnerOpen = false
        bookedDialog = false
        push(Route.Exit)
    }

    /** A hotel option: local recompute + selection now, `patch_cost {hotelChoice}` overwrites. */
    fun selectHotel(stopId: String, placeId: String) {
        val r = result ?: return
        val stop = r.trip.daysList.flatMap { it.stops }.firstOrNull { it.id == stopId } ?: return
        if (stop.selectedHotelId == placeId || costBusy) return
        costBusy = true
        val session = tripSession
        localCost(r) { trip -> CostApply.apply(r.trip, LocalCost.hotel(trip, stopId, placeId), r.trip.cost.reserveOn, stopId to placeId) }
        scope.launch {
            val p = gateway.patchCost(r.tripJson, EngineArgs.hotelPatch(stopId, placeId))
            costBusy = false
            if (session != tripSession) return@launch // P2-1
            when (p) {
                is EngineResult.Ok -> updateTrip(p.value)
                is EngineResult.Err -> {
                    result = r
                    showToast(Toast.EngineFailed)
                }
            }
        }
    }

    /** «Забронировать ночь» / «Открыть бронирование» → the mock partner sheet (D-13); offline → toast. */
    fun book() {
        if (!connectivity.online) {
            showToast(Toast.NeedInternet)
            return
        }
        partnerOpen = true
    }

    fun needInternet() = showToast(Toast.NeedInternet)

    private fun selectedHotel(stopId: String): String? =
        result?.trip?.daysList?.flatMap { it.stops }?.firstOrNull { it.id == stopId }?.let { it.selectedHotelId ?: it.hotelOptions.firstOrNull()?.placeId }

    /** The selected hotel of [stopId] is the booked one (Road «Забронировано», 5.7 booked CTA). */
    fun isBooked(stopId: String): Boolean = booked[stopId] != null && booked[stopId] == selectedHotel(stopId)

    /** Sheet dismissed (button, ×, back) → «Забронировали?» unless the selected hotel is already booked. */
    fun closePartner() {
        partnerOpen = false
        val sid = exitStopId ?: return
        if (!isBooked(sid)) bookedDialog = true
    }

    /** «Да, забронировали» marks the selected hotel (moving the mark, one per night) + toast with «Вернуть». */
    fun answerBooked(yes: Boolean) {
        bookedDialog = false
        val sid = exitStopId ?: return
        val pid = selectedHotel(sid) ?: return
        if (yes) {
            undoBooked = booked[sid] ?: ""
            booked[sid] = pid
            persistBooking()
            showToast(Toast.Booked(sid))
        }
    }

    /** «Вернуть» on the booked toast: the previous mark (or none). */
    fun undoBooking() {
        val sid = exitStopId ?: return
        val prev = undoBooked ?: return
        undoBooked = null
        if (prev.isEmpty()) booked.remove(sid) else booked[sid] = prev
        persistBooking()
        dismissToast()
    }

    private fun persistBooking() {
        savedCurrent = false
        if (savedId != null) save(silent = true) // a saved trip keeps its booking at once
    }

    /** The origin's name forms from the engine (OI-39). */
    private fun loadOriginForms() {
        val o = origin
        scope.launch {
            val r = gateway.reverse(o)
            if (r is EngineResult.Ok && o == origin) r.value?.nameGenRu?.let { originGen = it }
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
        // Local total first (the row itself changes with the engine's answer a moment later).
        localCost(r) { trip -> CostApply.apply(r.trip, LocalCost.replace(trip, ui.stop.id, alt) ?: error("no units"), r.trip.cost.reserveOn) }
        val session = tripSession
        scope.launch {
            val n = gateway.replaceStop(r.tripJson, ui.stop.id, alt)
            if (session != tripSession) return@launch // P2-1
            when (n) {
                is EngineResult.Ok -> {
                    undoTrip = r
                    updateTrip(n.value)
                    replace = null
                    showToast(Toast.Replaced(n.value.trip.cost.totalRub))
                }
                is EngineResult.Err -> {
                    result = r
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
            delay(if (t is Toast.Replaced || t is Toast.TripDeleted || t is Toast.Booked) 6_000 else 3_000)
            toast = null
            if (t is Toast.Replaced) undoTrip = null
            if (t is Toast.TripDeleted) lastDeleted = null
        }
    }

    fun dismissToast() {
        toastJob?.cancel()
        toast = null
    }

    // ------------------------------------------------------------------------------------------ saved trips

    /** Save (5.5 T1 / 5.6 K1): upsert into the saved list, then write the file. */
    fun save(silent: Boolean = false) {
        val r = result ?: return
        if (!tripsLoaded) {
            pendingSave = true // P1-1: never write before the stored trips are in memory
            return
        }
        val id = savedId ?: UUID.randomUUID().toString()
        when (val up = SavedTrips.upsert(saved.toList(), SavedTrips.entry(id, now(), r, resultBearing, booked.toMap()))) {
            SavedTrips.Upsert.LimitReached -> limitDialog = true
            is SavedTrips.Upsert.Saved -> {
                saved.clear()
                saved.addAll(up.trips)
                savedId = id
                savedCurrent = true
                if (!silent) showToast(if (up.nearLimit) Toast.SavedNearLimit(up.count) else Toast.Saved)
                persist()
            }
        }
    }

    private fun persist() {
        pendingTrips = saved.toList()
        writes.trySend(Unit)
    }

    // ------------------------------------------------------------------------------------------ the one writer

    private val writes = kotlinx.coroutines.channels.Channel<Unit>(kotlinx.coroutines.channels.Channel.CONFLATED)
    private var pendingTrips: List<SavedTripDto>? = null
    private var pendingLast: LastTripDto? = null
    private var lastDirty = false
    private var pendingDefaults: DefaultsDto? = null
    private var tripsLoaded = false
    private var pendingSave = false

    /**
     * P1-1: one coroutine performs every write in order (latest snapshot wins: the pending fields are replaced,
     * the conflated channel only wakes the writer). A failed trips write shows the storage toast and leaves the
     * trip marked unsaved instead of «Сохранено».
     */
    private suspend fun writer() {
        for (u in writes) {
            pendingTrips?.let { t ->
                pendingTrips = null
                val ok = withContext(io) { runCatching { store.save(t) }.isSuccess }
                if (!ok) {
                    savedCurrent = false
                    showToast(Toast.StorageFull)
                }
            }
            if (lastDirty) {
                lastDirty = false
                val l = pendingLast
                withContext(io) { runCatching { store.saveLast(l) } }
            }
            pendingDefaults?.let { d ->
                pendingDefaults = null
                withContext(io) { runCatching { store.saveDefaults(d) } }
            }
        }
    }

    /** Changes whenever last.json must be rewritten: the trip (identity), booking, saved id and screen. */
    private fun lastKey(): Any? = listOf(result, booked.toMap(), savedId, lastScreen(), exitStopId)

    private fun lastScreen(): String? = when {
        Route.Exit in stack -> "exit"
        Route.Waybill in stack -> "waybill"
        Route.Road in stack -> "road"
        else -> null
    }

    private fun enqueueLast() {
        val r = result
        pendingLast = r?.let {
            runCatching {
                LastTripDto(
                    trip = SavedTrips.entry(savedId ?: "last", now(), it, resultBearing, booked.toMap()),
                    savedId = savedId, screen = lastScreen(), exitStopId = exitStopId,
                )
            }.getOrNull()
        }
        lastDirty = true
        writes.trySend(Unit)
    }

    /** P1-2: back to the trip and screen of last.json (process death, force-stop + relaunch). */
    private fun restoreLast(l: LastTripDto) {
        val screen = l.screen ?: return
        val r = runCatching { SavedTrips.result(l.trip) }.getOrNull() ?: return
        val stillSaved = l.savedId != null && saved.any { it.id == l.savedId }
        showTrip(r, request = null, bearing = l.trip.bearing8, savedId = if (stillSaved) l.savedId else null, fromSaved = true, bookedStops = l.trip.bookedHotels)
        savedCurrent = false
        stack.clear()
        stack.add(Route.Windshield)
        stack.add(Route.Road)
        when (screen) {
            "waybill" -> stack.add(Route.Waybill)
            "exit" -> if (l.exitStopId != null) {
                exitStopId = l.exitStopId
                stack.add(Route.Exit)
            }
        }
    }

    // ------------------------------------------------------------------------------------------ defaults (P2-10)

    private var dailyKmTouched = false

    private fun defaultsNow() = DefaultsDto(
        frontAdult = frontAdult, seats = seats.map { it.name }, dog = dog, dailyKm = if (dailyKmTouched) dailyKm else null,
        budgetIndex = budgetIndex, mood = mood?.name, moodTouched = moodTouched,
        originLabel = origin.label, originLat = origin.lat, originLon = origin.lon, originGen = originGen,
    )

    private fun applyDefaults(d: DefaultsDto) {
        frontAdult = d.frontAdult
        d.seats.take(seats.size).forEachIndexed { i, n -> seats[i] = runCatching { Seat.valueOf(n) }.getOrDefault(Seat.EMPTY) }
        dog = d.dog
        d.dailyKm?.let {
            dailyKm = it
            dailyKmTouched = true
        }
        budgetIndex = d.budgetIndex.coerceIn(0, BudgetPresets.lastIndex)
        mood = d.mood?.let { runCatching { Mood.valueOf(it) }.getOrNull() }
        moodTouched = d.moodTouched
        val o = GeoPoint(d.originLabel, d.originLat, d.originLon)
        if (o != origin) {
            origin = o
            originGen = d.originGen
            rowKm.clear()
            loadRoutes()
        }
    }

    /** Limit dialog «Мои поездки» → back to the Windshield with the trips sheet open. */
    fun limitToTrips() {
        limitDialog = false
        while (stack.size > 1) stack.removeAt(stack.lastIndex)
        tripsSheet = true
    }

    fun dismissLimit() {
        limitDialog = false
    }

    /** D-1 long-press / TalkBack «Удалить» → confirmation dialog. */
    fun askDelete(id: String) {
        deleteAsk = saved.firstOrNull { it.id == id }
    }

    fun cancelDelete() {
        deleteAsk = null
    }

    /** «Удалить»: removed at once, toast «Поездка удалена» + «Вернуть» (6 s). */
    fun confirmDelete() {
        val t = deleteAsk ?: return
        deleteAsk = null
        val (rest, removed) = SavedTrips.remove(saved.toList(), t.id)
        lastDeleted = removed
        saved.clear()
        saved.addAll(rest)
        if (savedId == t.id) {
            savedId = null
            savedCurrent = false
        }
        if (saved.isEmpty()) tripsSheet = false
        persist()
        showToast(Toast.TripDeleted)
    }

    fun undoDelete() {
        val removed = lastDeleted ?: return
        lastDeleted = null
        val back = SavedTrips.restore(saved.toList(), removed)
        saved.clear()
        saved.addAll(back)
        persist()
        dismissToast()
    }

    val canUndoDelete: Boolean get() = lastDeleted != null && toast == Toast.TripDeleted

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
        showTrip(SavedTrips.result(s), request = null, bearing = s.bearing8, savedId = s.id, fromSaved = true, bookedStops = s.bookedHotels)
        while (stack.size > 1) stack.removeAt(stack.lastIndex)
        push(Route.Road)
    }

    /** e2e: start from an empty list. */
    fun clearSaved() {
        saved.clear()
        savedId = null
        savedCurrent = false
        if (tripsLoaded) persist()
    }

    companion object {
        const val STEP_GAP_MS = 400L
        const val AUTO_ADVANCE_MS = 1000L
        const val ESTIMATE_DEBOUNCE_MS = 300L
        const val LAST_DEBOUNCE_MS = 300L
        val ENGINE_START_CODES = setOf("NO_ENGINE", "ENGINE_START", "NO_WORLD", "TZDATA_MISSING")
    }
}
