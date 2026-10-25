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
import app.verst.core.model.NaviHandoff
import app.verst.core.model.NaviLinks
import app.verst.core.model.LatLon
import app.verst.core.model.HandoffArgs
import app.verst.core.model.WalkRequest
import app.verst.core.model.EngineJson
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.EstimateDto
import app.verst.core.model.dto.HandoffDto
import app.verst.core.model.dto.HandoffLinksDto
import app.verst.core.model.dto.HandoffPartDto
import app.verst.data.TripStore
import app.verst.data.TripsLoad
import app.verst.engine.PlannerGateway
import java.util.UUID
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import app.verst.core.ui.theme.DesignTokens
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** The routes of the slice (M§7 subset). */
enum class Route { Windshield, Navigator, Instruments, Drive, Road, Waybill, Exit, Debug, NoFit, City, Walk }

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
    /** 5.8: the plan came back `no_fit` — the CTA is «Смотреть варианты». */
    val noFit: Boolean = false,
)

/** Plate toasts of 5.5/5.6/D-6 (components §16 `PlateToast`); the screen picks the copy by type. */
sealed interface Toast {
    data class Replaced(val totalRub: Int) : Toast
    data object Saved : Toast
    data class SavedNearLimit(val count: Int) : Toast
    data object StorageFull : Toast
    data object EngineFailed : Toast
    data object NeedInternet : Toast

    /** 5.13 hand-off toasts. */
    data class HandoffWeb(val walk: Boolean) : Toast
    data object HandoffOffline : Toast
    data object HandoffFailed : Toast
    /** 5.13 §5: «Открываем Яндекс Карты / Навигатор» (1 s) before the app opens. */
    data class HandoffOpen(val navi: Boolean) : Toast

    /** 5.12 location toasts ([town] = the origin that stays). */
    data class LocationDenied(val town: String) : Toast
    data object LocationBlocked : Toast
    data class LocationTimeout(val town: String) : Toast
    data object LocationOff : Toast

    /** 5.12 address search. */
    data object AddressRate : Toast

    /** 5.10: an 18+ preset with children in the crew. */
    data object CityKids : Toast

    /** S4 5.11 §10.2: the rebuild failed — the previous walk stays; «Повторить». */
    data object WalkRebuildFailed : Toast

    /** D-7: «Спасибо, проверим» (online) / «Отправим, когда появится сеть» (offline, queued). */
    data object ReportThanks : Toast
    data object ReportQueued : Toast

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
    /** DEV-302: the address search (Nominatim; a fake in unit tests). */
    addressSearch: app.verst.data.net.AddressSearch? = null,
    private val retryEngine: () -> Unit,
) {
    /** DEV-302: Nominatim, explicit submit only, ≤ 1/s (the e2e points its base URL at MockWebServer). */
    val address: app.verst.data.net.AddressSearch = addressSearch ?: app.verst.data.net.NominatimClient(online = { connectivity.online })
    val stack = mutableStateListOf(Route.Windshield)
    val top: Route get() = stack.last()

    // ---- Windshield
    var origin: GeoPoint by mutableStateOf(DefaultOrigin)
        private set
    var windshield: WindshieldData by mutableStateOf(WindshieldData.Loading)
        private set
    var selectedRoute by mutableStateOf(0)

    // ---- GPS origin (S3-R1 → 5.12, DEV-301)
    /** Off (not used) / Waiting («Ищем вас…») / On (the origin is the fix's town) / Failed. */
    var gps by mutableStateOf(GpsState.Off)
        private set
    /** 5.12 rationale sheet «Откуда поедем?» (until answered once). */
    var locationSheet by mutableStateOf(false)
        private set
    private var locationAsked = false
    var originFromGps by mutableStateOf(false)
        private set
    /** The fix is coarse («примерно, по сети» + «Точнее»). */
    var gpsApprox by mutableStateOf(false)
        private set
    /** Online reverse geocoding of the fix: «ул. Советская, 1». */
    var originAddress: String? by mutableStateOf(null)
        private set
    /** 5.12: the fix is outside Russia (`insideRussia = false`); ПОЕХАЛИ stays disabled until a Russian start. */
    var outsideRussia by mutableStateOf(false)
        private set
    /** The phone's position; set by the app (LocationManager), null in tests without one. */
    var locator: Locator? = null
    /** Shows the system permission dialog (coarse, or fine for «Точнее»); the activity answers through [onLocationPermission]. */
    var askLocationPermission: ((precise: Boolean) -> Unit)? = null
    /** Opens the app's system settings (blocked permission) / the location settings (location off). */
    var openAppSettings: (() -> Unit)? = null
    var openLocationSettings: (() -> Unit)? = null
    /** DEV-127 / e2e: a fixed position instead of the phone's (no permission needed). */
    var debugMockLocation: GeoPoint? by mutableStateOf(null)

    // ---- navigator hand-off (5.13, ADR-0014)
    /** Opens hand-off links outside the app; set by the activity. */
    var handoffLauncher: HandoffLauncher? = null
    /** The last hand-off and where it went (debug panel, e2e). */
    var lastHandoff: Pair<HandoffLinksDto, HandoffTarget>? by mutableStateOf(null)
        private set
    /** e2e: record the hand-off without leaving the app. */
    var debugHandoffDryRun = false
    /** D-5 stop menu (long-press on a Road-ahead row) and its engine hand-off. */
    var stopMenu: StopDto? by mutableStateOf(null)
        private set
    var stopHandoff: HandoffDto? by mutableStateOf(null)
        private set
    /** 5.13 day menu «В навигатор: день N». */
    var dayMenu: Int? by mutableStateOf(null)
        private set
    var dayHandoff: HandoffDto? by mutableStateOf(null)
        private set
    /** 5.13 §5 (S4) the hand-off sheet, and «Запомнить выбор» (persisted with the defaults). */
    var handoffSheet: HandoffSheet? by mutableStateOf(null)
        private set
    var handoffRemember by mutableStateOf(false)
        private set
    var handoffRememberedApp: HandoffApp? by mutableStateOf(null)
        private set
    /** ADR-0015 §1: the signing key has not arrived; unsigned → Карты get the whole day, Навигатор the next point. */
    var handoffSigned = false

    // ---- 5.9 cards
    var card: CardState? by mutableStateOf(null)

    /** D-7 report sheet: the place, the reason (one of [app.verst.core.model.Reports.REASONS]), the comment. */
    var report: ReportTarget? by mutableStateOf(null)
    var reportReason: String? by mutableStateOf(null)
    var reportComment: String by mutableStateOf("")
        private set
    /** 5.12 §3 «О данных» sheet. */
    var aboutData by mutableStateOf(false)
    /** 5.5 §10.6: the stop whose ParkingSheet is open (Road ahead). */
    var roadParking: StopDto? by mutableStateOf(null)
        private set

    // ---- 5.8 budget fit
    var noFit: app.verst.core.model.dto.NoFitDto? by mutableStateOf(null)
        private set
    /** A no-fit «Поднять бюджет до …» value between the presets («до 42 000 ₽»); cleared by the stepper. */
    var budgetCustom: Int? by mutableStateOf(null)
        private set
    /** The minimum trip of a no-fit, opened by «Показать самый экономный вариант» (over budget everywhere). */
    var showingMinimum by mutableStateOf(false)
        private set
    /** `estimate` budget figures per request (Instruments caption meta). */
    private val estimates = mutableStateMapOf<PlanRequest, EstimateDto>()

    // ---- 5.12 address search
    var addressResults: List<SuggestionDto> by mutableStateOf(emptyList())
        private set
    var addressState by mutableStateOf(AddressState.Idle)
        private set
    private var addressJob: Job? = null

    // ---- 5.10 / 5.11 «По городу»
    var cityPresets: app.verst.core.model.dto.CityPresetsDto? by mutableStateOf(null)
        private set
    var cityLoading by mutableStateOf(false)
        private set
    /** `NO_CITY` / `NOT_ENOUGH_POIS` / another engine code of the last presets or walk call. */
    var cityError: String? by mutableStateOf(null)
        private set
    var cityPreset by mutableStateOf("overview")
        private set
    /** null = «без ограничения» (S4, ADR-0015 §6). */
    var cityDurationMin: Int? by mutableStateOf(240)
        private set
    /** S4: values the user chose are kept — a preset's defaults only fill what was never touched. */
    private var cityDurationTouched = false
    private var cityPaceTouched = false
    /** S4 5.10 §10: the walk's own crew (not the car's), remembered for walks only. */
    var cityAdults by mutableStateOf(2)
        private set
    var cityChildren by mutableStateOf(0)
        private set
    var cityDog by mutableStateOf(false)
        private set
    /** S4 5.11 §10.2: «Другой вариант» found nothing new — the button is disabled until the input changes. */
    var walkOtherNone by mutableStateOf(false)
        private set
    /** S4 5.11 §10.5 / 5.10: `NOT_ENOUGH_POIS` with the engine's verified suggestions (never guessed here). */
    var walkFew: WalkFew? by mutableStateOf(null)
    /** M6: request input → the engine's `requestKey` (stale answers and same-request rebuilds). */
    private val walkKeyByInput = HashMap<String, String>()
        private set
    /** S4: which picker sheet is open (5.10 prefs, 5.11 filter bar). */
    var cityPicker: CityPicker? by mutableStateOf(null)
        private set
    private var walkSeq = 0
    private var rebuildJob: Job? = null
    private var lastOtherAdded: List<String> = emptyList()
    val cityInterests = mutableStateListOf<String>()
    var cityPace by mutableStateOf("normal")
        private set
    var cityBudget: Int? by mutableStateOf(null)
        private set
    var cityReturn by mutableStateOf(true)
        private set
    var cityCustomSheet by mutableStateOf(false)
        private set
    /** 18+ dialog: what to apply on «Да, мне есть 18» (a preset, or the «бары» interest). */
    var ageGate: AgeGate? by mutableStateOf(null)
        private set
    private var adultConfirmed = false
    var walkBuilding by mutableStateOf(false)
        private set
    var walk: app.verst.core.model.dto.WalkRouteDto? by mutableStateOf(null)
        private set
    private val walkExclude = mutableListOf<String>()
    private var walkJob: Job? = null
    var walkHandoff: HandoffDto? by mutableStateOf(null)
        private set
    /** The walk start (the GPS origin or a picked point); null = the trip origin. */
    var cityStart: GeoPoint? by mutableStateOf(null)
        private set
    private var cityPickingStart = false

    // ---- Road-ahead focus restore (S3-R1, CEO 2.1)
    /** The row acted on (Exit, replace, stop menu): scrolled into view and highlighted on the way back. */
    var roadFocusId: String? by mutableStateOf(null)
        private set
    /** The top visible row while scrolling (restores the position after Waybill / process death). */
    var roadTopId: String? by mutableStateOf(null)
        private set
    /** Bumps on every return to Road ahead (back from a screen, a sheet closed, a restore). */
    var roadFocusSeq by mutableStateOf(0)
        private set
    /** 5.9 §5: the scroll offset of Road ahead, restored exactly on the way back (also after process death). */
    var roadScrollY: Int? by mutableStateOf(null)
        private set
    /** Walk result focus restore (as Road ahead). */
    var walkFocusId: String? by mutableStateOf(null)
        private set
    var walkFocusSeq by mutableStateOf(0)
        private set
    /** The saved id of the walk on screen (DEV-308). */
    var savedWalkId: String? by mutableStateOf(null)
        private set

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

    /** 5.12 §5 autofocus: КУДА takes focus after a hand-picked ОТКУДА, not after a GPS fix (S3-QA P1-01). */
    var focusToField by mutableStateOf(true)
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
    /** 5.3 §9: always one selected; `fun` for a new trip (children no longer pre-select «Спокойно»). */
    var mood: Mood by mutableStateOf(Mood.FUN)
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

    /** e2e: the location question counts as answered («Выберу сам»), so no rationale sheet covers the screens. */
    fun debugLocationAnswered() {
        locationAsked = true
        locationSheet = false
    }

    /** e2e / debug: back to the default origin (Москва) with the location question unanswered. */
    fun debugResetOrigin() {
        locateJob?.cancel()
        debugMockLocation = null
        locationAsked = false
        locationSheet = false
        originFromGps = false
        originAddress = null
        outsideRussia = false
        gps = GpsState.Off
        cityStart = null
        if (origin != DefaultOrigin) {
            origin = DefaultOrigin
            originGen = DefaultOrigin.label
            loadOriginForms()
            rowKm.clear()
            loadRoutes()
        }
    }

    fun setWorld(id: String) {
        if (gateway.world == id) return
        gateway.world = id
        origin = if (id == "edge_cases_v1") GeoPoint("Тестовск", 58.0, 50.0) else DefaultOrigin
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
        connectivity.simulatedOffline = on
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
        mood = Mood.FUN
        locationAsked = false
        originFromGps = false
        originAddress = null
        gps = GpsState.Off
        debugMockLocation = null
        budgetCustom = null
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
                        estimates[r] = e.value
                        if (estimateError?.first == r) estimateError = null
                    }
                    is EngineResult.Err -> if (e.error.code != "CANCELLED") estimateError = r to e.error
                }
            }
        }
    }

    // ------------------------------------------------------------------------------------------ navigation

    fun push(route: Route) {
        locationSheet = false // the rationale belongs to the screen that asked
        stack.add(route)
    }

    /** System back and every back link. Sheets close first. Returns false on the root (the activity finishes). */
    fun back(): Boolean {
        if (ageGate != null) {
            answerAge(false)
            return true
        }
        if (cityPicker != null) {
            cityPicker = null
            return true
        }
        if (cityCustomSheet) {
            cityCustomSheet = false
            return true
        }
        if (locationSheet && (top == Route.Navigator || top == Route.City)) {
            locationSheet = false
            return true
        }
        if (aboutData) {
            aboutData = false
            return true
        }
        if (roadParking != null) {
            roadParking = null
            return true
        }
        if (handoffSheet != null) {
            closeHandoffSheet()
            return true
        }
        if (report != null) {
            closeReport()
            return true
        }
        if (card != null) {
            closeCard()
            return true
        }
        if (dayMenu != null) {
            closeDayMenu()
            return true
        }
        if (stopMenu != null) {
            closeStopMenu()
            return true
        }
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
            Route.City, Route.Walk -> {
                rebuildJob?.cancel()
                walkJob?.cancel()
                walkBuilding = false
                cityPicker = null
            }
            Route.Navigator -> if (editingFrom) {
                editingFrom = false
                updateQuery("")
                return true
            }
            else -> Unit
        }
        stack.removeAt(stack.lastIndex)
        if (top == Route.Road) roadFocusSeq += 1 // S3-R1: back to the row we left from
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
        focusToField = true
        push(Route.Navigator)
        onNavigatorOpened()
    }

    // ------------------------------------------------------------------------------------------ navigator

    fun updateQuery(q: String) {
        if (q != query) clearAddresses()
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
            when (val r = gateway.geoSearch(q.trim(), origin)) {
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
        clearAddresses()
        if (editingFrom && cityPickingStart) {
            // 5.10 «изменить»: the walk start, back to «По городу»
            cityPickingStart = false
            editingFrom = false
            cityStart = GeoPoint(if (s.kind == "address" && s.subtitle.isNotBlank()) "${s.subtitle}, ${s.name}" else s.name, s.lat, s.lon)
            updateQuery("")
            while (stack.size > 1 && top != Route.City) stack.removeAt(stack.lastIndex)
            loadCityPresets()
            return
        }
        if (editingFrom) {
            originFromGps = false
            originAddress = null
            outsideRussia = false
            gps = GpsState.Off
            origin = GeoPoint(if (s.kind == "address" && s.subtitle.isNotBlank()) "${s.subtitle}, ${s.name}" else s.name, s.lat, s.lon)
            originGen = s.nameGenRu ?: s.name
            if (s.nameGenRu == null) loadOriginForms()
            rowKm.clear()
            focusToField = true
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
    }

    fun pickMood(m: Mood) {
        moodTouched = true
        mood = m
    }

    fun stepKm(delta: Int) {
        dailyKmTouched = true
        dailyKm = (dailyKm + delta).coerceIn(TripMath.KM_MIN, TripMath.KM_MAX)
    }

    fun stepBudget(delta: Int) {
        val custom = budgetCustom
        budgetCustom = null
        if (custom != null) {
            // from «до 42 000 ₽» the stepper moves to the neighbouring preset
            val above = BudgetPresets.indexOfFirst { it == null || it > custom }.let { if (it < 0) BudgetPresets.lastIndex else it }
            budgetIndex = if (delta > 0) above else (above - 1).coerceAtLeast(0)
            return
        }
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
        budgetRub = budgetCustom ?: BudgetPresets[budgetIndex],
        mood = mood,
    )

    /** The budget the gauge shows: a no-fit «Поднять бюджет до …» value, else the preset. */
    val budgetRub: Int? get() = budgetCustom ?: BudgetPresets[budgetIndex]

    // ------------------------------------------------------------------------------------------ drive

    /** ПОЕХАЛИ on 5.3 → Drive; the plan runs on `verst-python`, the steps are paced ≥ 400 ms (5.4 §6). */
    fun go() {
        if (top != Route.Drive) push(Route.Drive)
        startPlan()
    }

    fun retryPlan() = startPlan(lastPlanRequest ?: request())

    private var lastPlanRequest: PlanRequest? = null

    private fun startPlan(request: PlanRequest = request()) {
        planJob?.cancel()
        drive = DriveUi()
        lastPlanRequest = request
        val id = UUID.randomUUID().toString()
        planJob = scope.launch {
            val pending = ArrayDeque<Pair<String, Float>>() // stage text, engine progress at that stage
            var days = 0
            var finished: EngineResult<app.verst.core.model.dto.PlanOutcome>? = null
            val forced = debugForceError
            val slowMs = debugSlowSec * 1000L
            val engine = launch {
                if (forced != null) {
                    delay(STEP_GAP_MS)
                    finished = EngineResult.Err(EngineErrorDto(forced, "debug: forced"))
                    return@launch
                }
                finished = gateway.planOutcome(id, request) { ev ->
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
                is EngineResult.Ok -> when (val o = r.value) {
                    is app.verst.core.model.dto.PlanOutcome.Plan -> {
                        val bearing = readyRoute?.bearing8 ?: request.destination?.let { TripMath.bearing8(request.origin, it) } ?: "N"
                        noFit = null
                        showingMinimum = false
                        showTrip(o.result, request, bearing, savedId = null, fromSaved = false)
                        drive = drive.copy(progress = 1f, done = true, days = o.result.trip.days)
                        delay(AUTO_ADVANCE_MS)
                        if (top == Route.Drive) openRoad()
                    }
                    is app.verst.core.model.dto.PlanOutcome.NoFit -> {
                        // 5.8: «Смотреть варианты», auto-advance after 1 s as for a plan
                        noFit = o.noFit
                        drive = drive.copy(progress = 1f, done = true, noFit = true)
                        delay(AUTO_ADVANCE_MS)
                        if (top == Route.Drive) openNoFit()
                    }
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
        stopMenu = null
        stopHandoff = null
        dayMenu = null
        dayHandoff = null
        card = null
        undoTrip = null
        roadFocusId = null
        roadTopId = null
        roadScrollY = null
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

    // ------------------------------------------------------------------------------------------ focus restore

    /** Road ahead reports its top visible row while it is on top (debounced by the screen). */
    fun roadTop(id: String?, scrollY: Int? = null) {
        if (top == Route.Road && id != null) {
            roadTopId = id
            if (scrollY != null && card == null && stopMenu == null && dayMenu == null) roadScrollY = scrollY
        }
    }


    /** The highlight of the restored row has been shown. */
    fun roadFocusShown() {
        roadFocusId = null
    }

    // ------------------------------------------------------------------------------------------ hand-off (5.13)

    /** The day header link → the day menu «В навигатор: день N» (the engine's links resolved behind it). */
    fun openDayMenu(day: Int) {
        val r = result ?: return
        dayMenu = day
        dayHandoff = null
        val session = tripSession
        scope.launch {
            val h = engineHandoff(r.tripJson, HandoffArgs.day(day)) ?: r.trip.daysList.firstOrNull { it.day == day }?.let { NaviLinks.day(it) }?.toDto(day)
            if (session == tripSession && dayMenu == day) dayHandoff = h
        }
    }

    fun closeDayMenu() {
        dayMenu = null
        dayHandoff = null
    }

    /** «В навигатор: день N». */
    fun dayMenuGo() {
        val h = dayHandoff ?: return
        dayMenu = null
        launchHandoff(h.parts.firstOrNull()?.links ?: return, walk = false)
    }

    // ---- 5.13 §5 (S4) the hand-off sheet

    /** «Вести в навигаторе» / a day's «вести»: the remembered app directly, else the sheet on [day]. */
    fun handoff(day: Int) {
        val app = handoffRememberedApp
        if (handoffRemember && app != null) {
            val r = result ?: return
            val session = tripSession
            scope.launch {
                val h = dayHandoffOf(r, day) ?: return@launch
                if (session == tripSession) launchApp(app, h, next = false)
            }
        } else {
            openHandoffSheet(day)
        }
    }

    /** The sheet on [day] (a long-press always opens it, even with «Запомнить выбор»). */
    fun openHandoffSheet(day: Int) {
        val r = result ?: return
        handoffSheet = HandoffSheet(day, null, day)
        loadSheet(r, day)
    }

    private fun loadSheet(r: PlanResultDto, day: Int) {
        val session = tripSession
        scope.launch {
            val h = dayHandoffOf(r, day)
            val cur = handoffSheet
            if (session == tripSession && cur != null && cur.handoffDay == day) handoffSheet = cur.copy(handoff = h)
        }
    }

    private suspend fun dayHandoffOf(r: PlanResultDto, day: Int): HandoffDto? =
        engineHandoff(r.tripJson, HandoffArgs.day(day)) ?: r.trip.daysList.firstOrNull { it.day == day }?.let { NaviLinks.day(it) }?.toDto(day)

    /** A tab: «День N» or «До след.» ([day] = null, the next point of the sheet's day). */
    fun handoffScope(day: Int?) {
        val cur = handoffSheet ?: return
        val r = result ?: return
        if (day == null) {
            handoffSheet = cur.copy(day = null)
        } else if (day != cur.handoffDay) {
            handoffSheet = HandoffSheet(day, null, day)
            loadSheet(r, day)
        } else {
            handoffSheet = cur.copy(day = day)
        }
    }

    fun closeHandoffSheet() {
        handoffSheet = null
        roadFocusSeq += 1
    }

    fun toggleHandoffRemember() {
        handoffRemember = !handoffRemember
        if (!handoffRemember) handoffRememberedApp = null
    }

    /** A card of the sheet: open that app (and remember it when «Запомнить выбор» is on). */
    fun handoffPick(app: HandoffApp) {
        val cur = handoffSheet ?: return
        val h = cur.handoff ?: return
        if (handoffRemember) handoffRememberedApp = app
        handoffSheet = null
        launchApp(app, h, next = cur.day == null)
        roadFocusSeq += 1
    }

    fun handoffInstall(app: HandoffApp) {
        handoffLauncher?.openStore(app)
    }

    /** The Навигатор / Карты link of [h]: unsigned the Навигатор gets the next point only (ADR-0015 §1). */
    private fun launchApp(app: HandoffApp, h: HandoffDto, next: Boolean) {
        val part = h.parts.firstOrNull() ?: return
        val l = part.links
        val nextPt = part.next ?: part.points.firstOrNull { it.role != "origin" }
        // a pre-v3 / local hand-off has no `next`: the day's first stop after its start
        val nextMaps = nextPt?.let { runCatching { LatLon(it.lat, it.lon) }.getOrNull() }
            ?: h.day?.let { d -> result?.trip?.daysList?.firstOrNull { it.day == d } }?.stops?.drop(1)
                ?.firstOrNull { it.lat != null && it.lon != null }?.let { runCatching { LatLon(it.lat!!, it.lon!!) }.getOrNull() }
        val uri: String?
        val web: String?
        when (app) {
            HandoffApp.NAVI -> {
                uri = if (next || !handoffSigned) l.navigatorNext ?: nextMaps?.let { NaviLinks.naviRoute(null, it, emptyList()) } else l.navigator
                web = null
            }
            HandoffApp.MAPS -> {
                uri = if (next && nextMaps != null) NaviLinks.mapsAppRoute(listOf(nextMaps)) else l.maps
                web = if (next && nextMaps != null) NaviLinks.webRoute(listOf(nextMaps)) else l.web
            }
        }
        val mapsApp = handoffLauncher?.mapsInstalled() == true
        if (app == HandoffApp.MAPS && !mapsApp && !connectivity.online) {
            showToast(Toast.HandoffOffline)
            return
        }
        val target = if (debugHandoffDryRun) {
            when {
                app == HandoffApp.NAVI -> HandoffTarget.NavigatorDryRun
                mapsApp -> HandoffTarget.MapsDryRun
                else -> HandoffTarget.BrowserDryRun
            }
        } else {
            handoffLauncher?.openIn(app, uri, web) ?: HandoffTarget.None
        }
        lastHandoff = HandoffLinksDto(navigator = if (app == HandoffApp.NAVI) uri else null, maps = if (app == HandoffApp.MAPS) uri else null, web = web) to target
        when (target) {
            HandoffTarget.Navigator, HandoffTarget.NavigatorDryRun -> showToast(Toast.HandoffOpen(navi = true))
            HandoffTarget.Maps, HandoffTarget.MapsDryRun -> showToast(Toast.HandoffOpen(navi = false))
            HandoffTarget.Browser, HandoffTarget.BrowserDryRun -> showToast(Toast.HandoffWeb(false))
            HandoffTarget.None -> showToast(Toast.HandoffFailed)
        }
    }

    /** D-5 stop menu on a long-press of a row. */
    fun openStopMenu(stop: StopDto) {
        val r = result ?: return
        roadFocusId = stop.id
        stopMenu = stop
        stopHandoff = null
        val session = tripSession
        scope.launch {
            val h = engineHandoff(r.tripJson, HandoffArgs.fromStop(stop.id)) ?: NaviLinks.fromStop(r.trip, stop.id)?.toDto(null)
            if (session == tripSession && stopMenu?.id == stop.id) stopHandoff = h
        }
    }

    fun closeStopMenu() {
        stopMenu = null
        stopHandoff = null
        roadFocusSeq += 1
    }

    /** «Открыть в навигаторе отсюда»: from this stop to the end of its day. */
    fun navigatorFromStop() {
        val h = stopHandoff ?: return
        stopMenu = null
        stopHandoff = null
        launchHandoff(h.parts.firstOrNull()?.links ?: return, walk = false)
        roadFocusSeq += 1 // back from the app: the row (5.9 §5)
    }

    /** «Заменить» in the stop menu → the D-6 sheet. */
    fun stopMenuReplace() {
        val s = stopMenu ?: return
        stopMenu = null
        stopHandoff = null
        openReplace(s)
    }

    /** 5.13 §2: what the car label names (navigator → maps → web), resolved from the installed apps. */
    val carTarget: HandoffTarget
        get() = when {
            handoffLauncher?.navigatorInstalled() == true -> HandoffTarget.Navigator
            handoffLauncher?.mapsInstalled() == true -> HandoffTarget.Maps
            else -> HandoffTarget.Browser
        }

    /** Walk: maps → web. */
    val walkTarget: HandoffTarget
        get() = if (handoffLauncher?.mapsInstalled() == true) HandoffTarget.Maps else HandoffTarget.Browser

    /** Kept for the R1 callers: the navigator app is installed. */
    val navigatorInstalled: Boolean get() = handoffLauncher?.navigatorInstalled() ?: false

    private suspend fun engineHandoff(routeJson: String, options: String): HandoffDto? =
        (gateway.handoff(routeJson, options) as? EngineResult.Ok)?.value?.takeIf { h -> h.parts.isNotEmpty() }

    /** One tap opens the target (no chooser); a web fallback says so; offline without an app → «нужен интернет». */
    private fun launchHandoff(links: HandoffLinksDto, walk: Boolean) {
        val resolved = if (walk) walkTarget else carTarget
        if (resolved == HandoffTarget.Browser && !connectivity.online) {
            showToast(Toast.HandoffOffline)
            return
        }
        val target = if (debugHandoffDryRun) {
            when (resolved) {
                HandoffTarget.Navigator -> HandoffTarget.NavigatorDryRun
                HandoffTarget.Maps -> HandoffTarget.MapsDryRun
                else -> HandoffTarget.BrowserDryRun
            }
        } else {
            handoffLauncher?.open(links, walk) ?: HandoffTarget.None
        }
        lastHandoff = links to target
        when (target) {
            HandoffTarget.Browser -> showToast(Toast.HandoffWeb(walk))
            HandoffTarget.None -> showToast(Toast.HandoffFailed)
            else -> Unit
        }
    }

    // ------------------------------------------------------------------------------------------ cards (5.9)

    /** Tappable rows only (M§15.5): a sight, or a night with a hotel. */
    fun tappable(s: StopDto): Boolean = s.kind == "sight" || (s.kind == "overnight" && s.hotelOptions.isNotEmpty())

    /** A Road-ahead row → its card; the row is the focus for the way back. */
    fun openCard(stop: StopDto) {
        if (!tappable(stop)) return
        roadFocusId = stop.id
        val hotel = stop.kind == "overnight"
        val option = if (hotel) stop.hotelOptions.firstOrNull { it.placeId == stop.selectedHotelId } ?: stop.hotelOptions.firstOrNull() else null
        val placeId = if (hotel) option?.placeId ?: stop.placeId else stop.placeId
        val base = app.verst.feature.card.CardUi(
            name = stop.name, sign = stop.sign, tags = stop.tags, kind = if (hotel) "hotel" else "sight",
            loading = placeId != null, offline = !connectivity.online, hotel = option, booked = isBooked(stop.id),
            canReplace = stop.replaceable && stop.alternatives.isNotEmpty(),
        )
        card = CardState(CardSource.ROAD, stop.id, placeId, base)
        loadCard(placeId, stop.id)
    }

    /** A walk stop → its card (sights / museums: sight card; bars: bar card with the ODbL line). */
    fun openWalkCard(ws: app.verst.core.model.dto.WalkStopDto) {
        if (!ws.tappable) return
        val base = app.verst.feature.card.CardUi(
            name = ws.nameRu, sign = if (ws.isBar) "service" else "tourist", tags = listOf(ws.kind), kind = if (ws.isBar) "bar" else "sight",
            loading = ws.poiId != null, offline = !connectivity.online, walkStop = true,
        )
        card = CardState(CardSource.WALK, ws.id, ws.poiId, base)
        walkFocusId = ws.id
        loadCard(ws.poiId, ws.id)
    }

    private fun loadCard(placeId: String?, rowId: String) {
        if (placeId == null) return
        scope.launch {
            val r = gateway.poiDetails(placeId)
            val c = card ?: return@launch
            if (c.rowId != rowId) return@launch
            var d = (r as? EngineResult.Ok)?.value
            // S3-R3 debug: real Commons files instead of the catalogue's (round robin) — real photos before the data run
            if (d != null && debugRealPhotos) {
                val files = app.verst.core.model.CommonsPhotos.DEBUG_FILES
                d = d.copy(image = app.verst.core.model.CommonsPhotos.debugImage(d.image, files[debugPhotoIndex++ % files.size]))
            }
            card = c.copy(ui = c.ui.copy(loading = false, details = d, offline = !connectivity.online))
        }
    }

    /** Debug panel «Настоящие фото Commons»: [app.verst.core.model.CommonsPhotos.DEBUG_FILES] on every card. */
    var debugRealPhotos by mutableStateOf(false)
    var debugPhotoIndex = 0

    fun closeCard() {
        val c = card ?: return
        card = null
        if (c.source == CardSource.ROAD) roadFocusSeq += 1 else walkFocusSeq += 1
    }

    // ------------------------------------------------------------------------------------------ D-7 report

    /** D-5 «Сообщить об ошибке» and the row's TalkBack action. */
    fun openReport(stop: StopDto) {
        stopMenu = null
        stopHandoff = null
        roadFocusId = stop.id
        startReport(ReportTarget(stop.name, stop.placeId, stop.id, "road", fromWalk = false))
    }

    /** 5.9 C10 «Сообщить об ошибке» on a card (road or walk). */
    fun reportFromCard() {
        val c = card ?: return
        card = null
        val walk = c.source == CardSource.WALK
        startReport(ReportTarget(c.ui.details?.nameRu ?: c.ui.name, c.poiId, c.rowId, if (walk) "walk" else "card", fromWalk = walk))
    }

    private fun startReport(t: ReportTarget) {
        report = t
        reportReason = null
        reportComment = ""
    }

    fun pickReportReason(r: String) {
        if (r in app.verst.core.model.Reports.REASONS) reportReason = r
    }

    fun setReportCommentText(t: String) {
        reportComment = t.take(app.verst.core.model.Reports.COMMENT_MAX)
    }

    fun closeReport() {
        val t = report ?: return
        report = null
        if (t.fromWalk) walkFocusSeq += 1 else roadFocusSeq += 1
    }

    /** «Отправить»: queued on the device (no endpoint yet); event `feedback_sent`. */
    fun sendReport() {
        val t = report ?: return
        val reason = reportReason ?: return
        val online = connectivity.online
        val r = app.verst.core.model.ReportDto(
            id = java.util.UUID.randomUUID().toString(), at = now(), reason = reason, comment = reportComment.trim(),
            name = t.name, placeId = t.placeId, stopId = t.stopId, source = t.source, world = gateway.world, online = online,
        )
        pendingReports += r
        writes.trySend(Unit)
        runCatching { android.util.Log.i("VerstEvent", "feedback_sent reason=$reason source=${t.source} place=${t.placeId}") }
        reportsSent += 1
        closeReport()
        showToast(if (online) Toast.ReportThanks else Toast.ReportQueued)
    }

    /** Reports queued this session (debug / tests). */
    var reportsSent by mutableStateOf(0)
        private set

    /** Hotel card «Выбрать отель» → 5.7 for that night. */
    fun cardPickHotel() {
        val c = card ?: return
        card = null
        openExit(c.rowId)
    }

    /** Sight card «Заменить» → D-6. */
    fun cardReplace() {
        val c = card ?: return
        val stop = result?.trip?.daysList?.flatMap { it.stops }?.firstOrNull { it.id == c.rowId } ?: return
        card = null
        openReplace(stop)
    }

    /** Walk card «Убрать эту точку»: the walk is solved again without it. */
    fun cardRemoveWalkStop() {
        val c = card ?: return
        card = null
        c.poiId?.let { if (it !in walkExclude) walkExclude += it }
        lastOtherAdded = listOfNotNull(c.poiId)
        buildWalk(WalkBuild.REMOVE)
    }

    fun openAboutData() {
        aboutData = true
    }

    fun openParking(stop: StopDto) {
        roadParking = stop
    }

    fun closeParking() {
        roadParking = null
    }

    /**
     * 5.5 §10.1: the day «Вести в навигаторе» starts with — the trip's day of today when the trip is under way
     * (start date ≤ today ≤ last day), else day 1.
     */
    fun handoffDay(trip: app.verst.core.model.dto.TripDto, today: java.time.LocalDate = java.time.LocalDate.now()): Int {
        val first = trip.daysList.firstOrNull()?.day ?: 1
        val start = (trip.daysList.firstOrNull()?.startAt ?: trip.input.startAt)?.takeIf { it.length >= 10 }
            ?.let { runCatching { java.time.LocalDate.parse(it.substring(0, 10)) }.getOrNull() } ?: return first
        val n = java.time.temporal.ChronoUnit.DAYS.between(start, today).toInt() + first
        return if (trip.daysList.any { it.day == n }) n else first
    }

    fun closeAboutData() {
        aboutData = false
    }


    fun walkFocusShown() {
        walkFocusId = null
    }

    // ------------------------------------------------------------------------------------------ budget (5.8)

    /** Drive «Смотреть варианты» / auto-advance: Drive is replaced by the no-fit screen. */
    fun openNoFit() {
        if (noFit == null) return
        if (top == Route.Drive) stack[stack.lastIndex] = Route.NoFit else push(Route.NoFit)
    }

    /** An option → Instruments with it applied; the user presses ПОЕХАЛИ again (5.8 §2). */
    fun applyBudgetOption(o: app.verst.core.model.dto.BudgetOptionDto) {
        when (o.kind) {
            "raise_budget" -> o.budgetRub?.let { budgetCustom = it }
            "shorten", "cheaper_route" -> {
                val id = o.readyRouteId
                if (id != null) {
                    val known = (windshield as? WindshieldData.Routes)?.routes?.firstOrNull { it.id == id }
                    val base = known ?: readyRoute
                    if (base != null) {
                        readyRoute = if (known != null) known else base.copy(id = id, title = o.titleRu ?: base.title, subtitle = "")
                        destination = null
                    }
                } else {
                    // a free trip: the same route in fewer days → a longer daily pace
                    val days = o.days
                    val km = figures?.figures?.km ?: noFit?.minimum?.trip?.km
                    if (days != null && days > 0 && km != null) {
                        dailyKmTouched = true
                        dailyKm = (((km + days - 1) / days + 49) / 50 * 50).coerceIn(TripMath.KM_MIN, TripMath.KM_MAX)
                    }
                }
            }
        }
        backToInstruments()
    }

    private fun backToInstruments() {
        val i = stack.lastIndexOf(Route.Instruments)
        if (i >= 0) {
            while (stack.size > i + 1) stack.removeAt(stack.lastIndex)
        } else {
            while (stack.lastOrNull() == Route.NoFit) stack.removeAt(stack.lastIndex)
            push(Route.Instruments)
        }
    }

    /** «Показать самый экономный вариант»: Road ahead with the minimum, over budget everywhere. */
    fun showMinimum() {
        val nf = noFit ?: return
        val m = nf.minimum ?: return
        showTrip(m, lastPlanRequest, readyRoute?.bearing8 ?: "N", savedId = null, fromSaved = false)
        showingMinimum = true
        if (top == Route.NoFit) stack[stack.lastIndex] = Route.Road else push(Route.Road)
    }

    /** Waybill over budget «Подогнать под бюджет»: the same trip planned again (the fitter runs) → Drive. */
    fun refit() {
        val req = resultRequest ?: lastPlanRequest ?: return
        val i = stack.lastIndexOf(Route.Road)
        if (i >= 0) while (stack.size > i) stack.removeAt(stack.lastIndex)
        push(Route.Drive)
        startPlan(req)
    }

    /** Instruments caption: the engine's budget verdict for the current draft (`estimate.outcome`). */
    val budgetEstimate: EstimateDto?
        get() = draft()?.let { estimates[it] }?.takeIf { it.outcome != null && request().budgetRub != null }

    // ------------------------------------------------------------------------------------------ location (5.12)

    private fun onNavigatorOpened() {
        when {
            debugMockLocation != null -> if (!originFromGps || gps != GpsState.On) locate()
            locator?.granted() == true -> if (originFromGps || !locationAsked) locate()
            !locationAsked -> locationSheet = true
        }
    }

    /** «ВЫ: …» on the Windshield, or the first «По городу»: the rationale once, else locate again. */
    fun askLocation() {
        when {
            debugMockLocation != null || locator?.granted() == true -> locate()
            !locationAsked -> locationSheet = true
            else -> askLocationPermission?.invoke(false) ?: showToast(Toast.LocationBlocked)
        }
    }

    /** Rationale «Разрешить» → the system dialog for coarse location. */
    fun allowLocation() {
        locationSheet = false
        locationAsked = true
        val ask = askLocationPermission
        if (debugMockLocation != null || locator?.granted() == true) locate() else if (ask != null) ask(false) else showToast(Toast.LocationDenied(origin.label))
    }

    /** Rationale «Выберу сам» → the ОТКУДА input. */
    fun manualLocation() {
        locationSheet = false
        locationAsked = true
        if (top == Route.Navigator) startEditFrom()
    }

    /** Kept for R1 callers: «Не разрешать» = «Выберу сам» without the input. */
    fun denyLocation() {
        locationSheet = false
        locationAsked = true
        showToast(Toast.LocationDenied(origin.label))
    }

    /** «Точнее» → the fine-location dialog. */
    fun preciseLocation() {
        askLocationPermission?.invoke(true)
    }

    /** The system dialog's answer; [blocked] = «don't ask again» (only the settings can allow it now). */
    fun onLocationPermission(granted: Boolean, blocked: Boolean) {
        if (granted) locate() else showToast(if (blocked) Toast.LocationBlocked else Toast.LocationDenied(origin.label))
    }

    /** «Моё местоположение» in ОТКУДА. */
    fun useMyLocation() {
        locationAsked = true
        locationSheet = false
        when {
            debugMockLocation != null || locator?.granted() == true -> locate(fromRow = true)
            askLocationPermission != null -> askLocationPermission?.invoke(false)
            else -> showToast(Toast.LocationTimeout(origin.label))
        }
    }

    /** The toast action: «Настройки» / «Включить» / «Выбрать». */
    fun toastAction() {
        val t = toast
        dismissToast()
        when (t) {
            Toast.LocationBlocked -> openAppSettings?.invoke()
            Toast.LocationOff -> openLocationSettings?.invoke()
            is Toast.LocationDenied -> if (top == Route.Navigator) startEditFrom()
            Toast.WalkRebuildFailed -> retryWalk()
            else -> Unit
        }
    }

    /** R1 name of [toastAction]. */
    fun toastSettings() = toastAction()

    private var locateJob: Job? = null

    /** The phone's position → `geo_nearest` (the catalogue town) → the origin; online also the street address. */
    fun locate(fromRow: Boolean = false) {
        locateJob?.cancel()
        if (debugMockLocation == null && locator?.enabled() == false) {
            showToast(Toast.LocationOff)
            return
        }
        gps = GpsState.Waiting
        locateJob = scope.launch {
            val mock = debugMockLocation
            val p = mock ?: locator?.current()
            if (p == null) {
                gps = GpsState.Failed
                showToast(Toast.LocationTimeout(origin.label))
                return@launch
            }
            val nearest = gateway.geoNearest(p)
            val town: SuggestionDto? = when (nearest) {
                is EngineResult.Ok -> {
                    val n = nearest.value
                    val t = n.town
                    if (!n.insideRussia || t == null) {
                        gps = GpsState.Failed
                        outsideRussia = true
                        return@launch
                    }
                    SuggestionDto("city", t.name, t.regionRu ?: "", t.lat, t.lon, t.id, nameGenRu = t.nameGenRu, namePrepRu = t.namePrepRu)
                }
                is EngineResult.Err -> nearestTown(p) // a gateway without v2 (unit tests)
            }
            if (town == null) {
                gps = GpsState.Failed
                showToast(Toast.LocationTimeout(origin.label))
                return@launch
            }
            outsideRussia = false
            gps = GpsState.On
            originFromGps = true
            gpsApprox = mock == null && locator?.precise() != true
            // the trip starts at the fix; «ВЫ: <ГОРОД>» names the catalogue town
            val o = GeoPoint(town.name, p.lat, p.lon)
            if (o != origin) {
                origin = o
                originGen = town.nameGenRu ?: town.name
                if (town.nameGenRu == null) loadOriginForms()
                rowKm.clear()
                loadRoutes()
            }
            originAddress = null
            if (fromRow && editingFrom) { // «Моё местоположение» picked: ОТКУДА is done
                focusToField = false // 5.12 §5: after a GPS fix nothing gets focus, the IME stays down
                editingFrom = false
                updateQuery("")
            }
            if (cityPickingStart || top == Route.City) {
                cityStart = null
                loadCityPresets()
            }
            if (connectivity.online) {
                val a = address.reverse(p.lat, p.lon)
                if (a is app.verst.data.net.AddressResult.Ok && origin == o) originAddress = a.value
            }
        }
    }

    /** The engine's town within 30 km (`reverse` + its `suggest` row), else the nearest popular town. */
    private suspend fun nearestTown(p: GeoPoint): SuggestionDto? {
        val name = (gateway.reverse(p) as? EngineResult.Ok)?.value?.name
        if (name != null) {
            val row = (gateway.suggest(name, p) as? EngineResult.Ok)?.value?.firstOrNull { it.name == name && it.nameGenRu != null }
            if (row != null) return row
        }
        val towns = (gateway.popular() as? EngineResult.Ok)?.value.orEmpty().filter { it.nameGenRu != null }
        return towns.minByOrNull { TownMath.km(p.lat, p.lon, it.lat, it.lon) }
    }

    // ------------------------------------------------------------------------------------------ addresses (5.12 §2)

    /** «Найти адрес» row: the query has a digit, «ул», «пр», «пер», «д.» or a comma. */
    fun looksLikeAddress(q: String): Boolean {
        val t = q.trim().lowercase()
        if (t.length < 3) return false
        return t.any { it.isDigit() } || t.contains(',') || ADDRESS_WORDS.any { w -> Regex("(^|\\s)$w(\\s|\\.|$)").containsMatchIn(t) }
    }

    /** Explicit submit (the action row or the IME «Найти»): one Nominatim request, never per keystroke. */
    fun submitAddress() {
        val q = query.trim()
        if (!looksLikeAddress(q)) return
        if (!connectivity.online) {
            addressState = AddressState.Offline
            return
        }
        addressJob?.cancel()
        addressState = AddressState.Searching
        addressJob = scope.launch {
            when (val r = address.search(q)) {
                is app.verst.data.net.AddressResult.Ok -> {
                    addressResults = r.value
                    addressState = if (r.value.isEmpty()) AddressState.None else AddressState.Done
                    fetchRowKm(r.value)
                }
                app.verst.data.net.AddressResult.Offline -> addressState = AddressState.Offline
                is app.verst.data.net.AddressResult.Failed -> {
                    // CEO S4: nothing online ever shows an error — a failure is «уточним при интернете»
                    addressResults = emptyList()
                    addressState = AddressState.Later
                }
            }
        }
    }

    private fun clearAddresses() {
        addressJob?.cancel()
        addressResults = emptyList()
        addressState = AddressState.Idle
    }

    // ------------------------------------------------------------------------------------------ «По городу» (5.10)

    /** Windshield «По городу пешком» → 5.10; the start = the GPS origin or the last chosen point. */
    fun openCity() {
        walkExclude.clear()
        cityError = null
        walkFew = null
        walkOtherNone = false
        cityPicker = null
        push(Route.City)
        if (!locationAsked && locator?.granted() != true && debugMockLocation == null) locationSheet = true
        loadCityPresets()
    }

    val cityStartPoint: GeoPoint get() = cityStart ?: origin

    private var presetsJob: Job? = null

    fun loadCityPresets() {
        presetsJob?.cancel()
        cityLoading = true
        cityError = null
        val p = cityStartPoint
        presetsJob = scope.launch {
            when (val r = gateway.cityPresets(p)) {
                is EngineResult.Ok -> {
                    cityPresets = r.value
                    val available = visibleCityPresets()
                    val current = available.firstOrNull { it.preset == cityPreset }
                    if (current == null) available.firstOrNull { !it.adultOnly }?.let { selectDefaults(it) } else selectDefaults(current)
                }
                is EngineResult.Err -> {
                    cityPresets = null
                    cityError = r.error.code
                }
            }
            cityLoading = false
        }
    }

    /**
     * 5.10 §10 step 4: the city's presets, «Прогулка с собакой» (`dog_walk`) first and only with the dog, «Свой
     * маршрут» last. Children never hide or disable a preset.
     */
    fun visibleCityPresets(): List<app.verst.core.model.dto.CityPresetDto> {
        val all = cityPresets?.presets.orEmpty().filter { it.available && (it.preset != DOG_WALK || cityDog) }
        return all.sortedBy { CityPresetOrder.indexOf(it.preset).let { i -> if (i < 0) 90 else i } }
    }

    /** A preset's defaults fill only what the user has not chosen (S4: custom values persist). */
    private fun selectDefaults(p: app.verst.core.model.dto.CityPresetDto) {
        cityPreset = p.preset
        if (!cityDurationTouched) cityDurationMin = p.defaultDurationMin
        if (!cityPaceTouched) p.defaultPace?.let { cityPace = it }
    }

    /** «изменить» on the start field → the ОТКУДА search; the pick comes back here. */
    fun cityChangeStart() {
        cityPickingStart = true
        openNavigator()
        startEditFrom()
    }

    /**
     * A preset plate: 18+ asks «Вам есть 18?» every time (S4: children never block — the walk carries a warning);
     * «Свой маршрут» opens the sheet with the user's own values.
     */
    fun selectCityPreset(preset: String) {
        val p = cityPresets?.presets?.firstOrNull { it.preset == preset } ?: return
        if (preset == "custom") {
            if (cityPreset != "custom") {
                selectDefaults(p)
                onWalkInputChanged()
            }
            cityCustomSheet = true
            return
        }
        if (p.adultOnly) {
            adultConfirmed = false
            ageGate = AgeGate(preset = preset)
            return
        }
        adultConfirmed = false
        if (cityPreset != preset) {
            selectDefaults(p)
            onWalkInputChanged()
        }
    }

    /** «Да» applies the pending choice; «Нет» keeps the previous preset — and no request is sent. */
    fun answerAge(yes: Boolean) {
        val g = ageGate ?: return
        ageGate = null
        if (!yes) return
        adultConfirmed = true
        if (g.preset != null) {
            cityPresets?.presets?.firstOrNull { it.preset == g.preset }?.let { selectDefaults(it) }
        } else if (g.interest != null && g.interest !in cityInterests) {
            cityInterests += g.interest
        }
        onWalkInputChanged()
    }

    /** null = «без ограничения». */
    fun setCityDuration(min: Int?) {
        cityDurationTouched = true
        if (cityDurationMin == min) return
        cityDurationMin = min
        onWalkInputChanged()
    }

    fun toggleCityInterest(i: String) {
        if (i in cityInterests) {
            if (cityInterests.size > 1) {
                cityInterests -= i
                onWalkInputChanged()
            }
            return
        }
        if (i == "bars") {
            ageGate = AgeGate(interest = i)
            return
        }
        cityInterests += i
        onWalkInputChanged()
    }

    fun pickCityPace(p: String) {
        cityPaceTouched = true
        if (cityPace == p) return
        cityPace = p
        onWalkInputChanged()
    }

    fun pickCityBudget(rub: Int?) {
        if (cityBudget == rub) return
        cityBudget = rub
        onWalkInputChanged()
    }

    fun toggleCityReturn() {
        cityReturn = !cityReturn
        onWalkInputChanged()
    }

    fun pickCityAdults(n: Int) {
        val v = n.coerceIn(1, 9)
        if (v == cityAdults) return
        cityAdults = v
        onWalkInputChanged()
    }

    fun pickCityChildren(n: Int) {
        val v = n.coerceIn(0, 9)
        if (v == cityChildren) return
        cityChildren = v
        onWalkInputChanged()
    }

    /** The dog toggle; «Собака останется дома» = off (a dog walk then falls back to the overview). */
    fun pickCityDog(on: Boolean) {
        if (on == cityDog) return
        cityDog = on
        if (!on && cityPreset == DOG_WALK) visibleCityPresets().firstOrNull { !it.adultOnly }?.let { selectDefaults(it) }
        onWalkInputChanged()
    }

    fun closeCityCustom() {
        cityCustomSheet = false
    }

    fun openCityPicker(p: CityPicker?) {
        cityPicker = p
    }

    /** «Собрать прогулку» in the custom sheet. */
    fun buildCustomWalk() {
        if (cityInterests.isEmpty()) cityInterests += "history"
        cityCustomSheet = false
        buildWalk()
    }

    fun walkRequest(): WalkRequest = WalkRequest(
        start = cityStartPoint,
        preset = cityPreset,
        durationMin = cityDurationMin,
        unlimited = cityDurationMin == null,
        interests = if (cityPreset == "custom") cityInterests.toList() else emptyList(),
        pace = cityPace,
        budgetRub = cityBudget,
        returnToStart = cityReturn,
        adults = cityAdults,
        children = cityChildren,
        dog = cityDog,
        adultConfirmed = adultConfirmed,
        exclude = walkExclude.toList(),
    )

    /**
     * 5.11 §10.2 (fixes the S4 bugs a, b): any change of preset, duration, crew, pace, interests, budget or the
     * return clears `exclude`; on the walk screen the walk rebuilds 400 ms after the last change.
     */
    private fun onWalkInputChanged() {
        walkExclude.clear()
        lastOtherAdded = emptyList()
        walkOtherNone = false
        if (top == Route.Walk) {
            rebuildJob?.cancel()
            rebuildJob = scope.launch {
                delay(DesignTokens.motion.walkRebuild.durationMs.toLong())
                buildWalk(WalkBuild.FILTER)
            }
        }
    }

    /**
     * ПОШЛИ / «Собрать прогулку» ([WalkBuild.GO]), a filter change on 5.11 ([WalkBuild.FILTER]), «Другой вариант»
     * ([WalkBuild.OTHER]) → `city_route` (cancellable). A newer request supersedes an older one. On 5.11 the
     * previous walk stays while rebuilding and after a failure: the screen never leaves 5.11 by itself.
     */
    fun buildWalk(mode: WalkBuild = WalkBuild.GO) {
        val p = cityPresets?.presets?.firstOrNull { it.preset == cityPreset }
        if (p?.adultOnly == true && !adultConfirmed) {
            ageGate = AgeGate(preset = cityPreset)
            return
        }
        walkJob?.cancel()
        walkBuilding = true
        if (mode == WalkBuild.GO) {
            cityError = null
            walkFew = null
        }
        val req = walkRequest()
        // M6 `requestKey`: the engine's key of a request we sent before (learned from its answer). A filter change
        // that leads back to the walk on screen sends nothing; an answer whose key is not the sent one is stale.
        val input = req.toInputJson()
        val sentKey = walkKeyByInput[input]
        if (mode == WalkBuild.FILTER && sentKey != null && sentKey == walk?.requestKey && walkFew == null) {
            walkBuilding = false
            return
        }
        val id = UUID.randomUUID().toString()
        val seq = ++walkSeq
        walkJob = scope.launch {
            val r = gateway.cityRoute(id, req)
            if (seq != walkSeq) return@launch // superseded by a newer request
            val key = when (r) {
                is EngineResult.Ok -> r.value.requestKey
                is EngineResult.Err -> r.error.requestKey
            }
            if (key != null) {
                if (sentKey != null && key != sentKey) {
                    walkBuilding = false
                    return@launch // an answer to another request: stale
                }
                if (walkKeyByInput.size > 64) walkKeyByInput.clear()
                walkKeyByInput[input] = key
            }
            val onWalk = top == Route.Walk
            when (r) {
                is EngineResult.Ok -> {
                    walk = r.value
                    walkFew = null
                    cityError = null
                    walkHandoff = null
                    walkFocusId = null
                    savedWalkId = null
                    if (!onWalk) push(Route.Walk)
                    loadWalkHandoff()
                }
                is EngineResult.Err -> when (r.error.code) {
                    "CANCELLED" -> Unit
                    "NOT_ENOUGH_POIS" -> when {
                        mode == WalkBuild.REMOVE -> {
                            // removing it leaves too few places: keep the walk as it is
                            walkExclude.removeAll(lastOtherAdded.toSet())
                            lastOtherAdded = emptyList()
                            showToast(Toast.WalkRebuildFailed)
                        }
                        mode == WalkBuild.OTHER -> {
                            // no new places: keep this walk, give the stops back, disable «Другой вариант»
                            walkExclude.removeAll(lastOtherAdded.toSet())
                            lastOtherAdded = emptyList()
                            walkOtherNone = true
                        }
                        else -> {
                            walkFew = WalkFew(req.durationMin, req.unlimited, r.error.walkSuggestions, r.error.count)
                            if (!onWalk) cityError = r.error.code
                        }
                    }
                    "NO_CITY" -> if (onWalk) showToast(Toast.WalkRebuildFailed) else cityError = r.error.code
                    else -> showToast(if (onWalk) Toast.WalkRebuildFailed else Toast.EngineFailed)
                }
            }
            walkBuilding = false
        }
    }

    /** «Другой вариант»: the same walk without the current stops. */
    fun otherWalk() {
        val w = walk ?: return
        if (walkOtherNone || walkBuilding) return
        lastOtherAdded = w.stops.mapNotNull { it.poiId }.filter { it !in walkExclude }
        walkExclude += lastOtherAdded
        buildWalk(WalkBuild.OTHER)
    }

    /** A verified `NOT_ENOUGH_POIS` suggestion → apply it and build again (never an app-made guess). */
    fun applyWalkSuggestion(sg: app.verst.core.model.dto.WalkSuggestion) {
        when {
            sg.clearExclude -> walkExclude.clear()
            sg.unlimited -> {
                cityDurationTouched = true
                cityDurationMin = null
            }
            sg.durationMin != null -> {
                cityDurationTouched = true
                cityDurationMin = sg.durationMin
            }
            sg.preset != null -> cityPresets?.presets?.firstOrNull { it.preset == sg.preset }?.let { selectDefaults(it) }
        }
        if (!sg.clearExclude) walkExclude.clear()
        walkOtherNone = false
        walkFew = null
        cityError = null
        buildWalk(if (top == Route.Walk) WalkBuild.FILTER else WalkBuild.GO)
    }

    /** The rebuild-failed toast «Повторить». */
    fun retryWalk() {
        buildWalk(if (top == Route.Walk) WalkBuild.FILTER else WalkBuild.GO)
    }

    private fun loadWalkHandoff() {
        val w = walk ?: return
        scope.launch {
            val h = engineHandoff(w.json, HandoffArgs.walk())
            if (walk?.id == w.id) walkHandoff = h ?: localWalkHandoff(w)
        }
    }

    private fun localWalkHandoff(w: app.verst.core.model.dto.WalkRouteDto): HandoffDto {
        val pts = listOf(app.verst.core.model.LatLon(w.start.lat, w.start.lon)) + w.stops.map { app.verst.core.model.LatLon(it.lat, it.lon) } +
            listOfNotNull(w.finish?.let { app.verst.core.model.LatLon(it.lat, it.lon) })
        return NaviLinks.walking(pts).toDto(null, mode = "walk")
    }

    /** «Пешком в Яндекс Картах» (part [index] of a split walk). */
    fun walkHandoffGo(index: Int = 1) {
        val h = walkHandoff ?: walk?.let { localWalkHandoff(it) } ?: return
        val part = h.parts.firstOrNull { it.index == index } ?: h.parts.firstOrNull() ?: return
        launchHandoff(part.links, walk = true)
        walkFocusSeq += 1
    }


    /** Save the walk to «Мои поездки» (schema 2, `kind = walk`). */
    fun saveWalk() {
        val w = walk ?: return
        if (!tripsLoaded) return
        val id = savedWalkId ?: UUID.randomUUID().toString()
        val entry = SavedTrips.walkEntry(id, now(), w)
        val i = saved.indexOfFirst { it.id == id }
        if (i >= 0) saved[i] = entry else saved.add(entry)
        savedWalkId = id
        persist()
        showToast(Toast.Saved)
    }

    /** Share text of a walk: title, stops, the cost and (alcohol presets) the responsible line. */
    fun walkShareText(): String {
        val w = walk ?: return ""
        val lines = mutableListOf(w.titleRu)
        w.stops.forEachIndexed { i, s -> lines += "${i + 1}. ${s.nameRu}" + (s.arriveAt?.let { " · " + (RuFormat.clock(it) ?: "") } ?: "") }
        lines += "≈ ${RuFormat.thousands(w.cost.totalRub)} ₽ на всех · ≈ ${w.walkKm} км пешком"
        w.responsibleNoteRu?.let { lines += it }
        return lines.joinToString("\n")
    }

    /** «Мои поездки» → a saved walk. */
    private fun openSavedWalk(t: SavedTripDto) {
        val w = t.walk?.let { runCatching { EngineJson.walk(it.toString()) }.getOrNull() } ?: return
        walk = w
        savedWalkId = t.id
        walkHandoff = null
        tripsSheet = false
        while (stack.size > 1) stack.removeAt(stack.lastIndex)
        push(Route.Walk)
        loadWalkHandoff()
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
        roadFocusId = stopId
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
        roadFocusId = stop.id
        replace = ReplaceUi(stop)
    }

    fun pickAlternative(altId: String?) {
        replace = replace?.copy(picked = altId)
    }

    fun closeReplace() {
        if (replace?.busy != true) {
            replace = null
            roadFocusSeq += 1
        }
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
                    roadFocusSeq += 1
                    showToast(Toast.Replaced(n.value.trip.cost.totalRub))
                }
                is EngineResult.Err -> {
                    result = r
                    replace = null
                    roadFocusSeq += 1
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
            delay(
                when {
                    t is Toast.Replaced || t is Toast.TripDeleted || t is Toast.Booked -> 6_000
                    t is Toast.HandoffOpen -> 1_000 // 5.13 §5: a 1 s toast, then the app
                    else -> 3_000
                },
            )
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
    private val pendingReports = mutableListOf<app.verst.core.model.ReportDto>()
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
            while (pendingReports.isNotEmpty()) {
                val r = pendingReports.removeAt(0)
                withContext(io) { runCatching { store.appendReport(r) } }
            }
        }
    }

    /** Changes whenever last.json must be rewritten: the trip (identity), booking, saved id and screen. */
    private fun lastKey(): Any? = listOf(result, booked.toMap(), savedId, lastScreen(), exitStopId, roadFocusId, roadTopId, roadScrollY)

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
                    roadFocusId = roadFocusId, roadTopId = roadTopId, roadScrollY = roadScrollY,
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
        // S3-R1: the row we left from (or the top visible row) comes back with the trip.
        roadFocusId = l.roadFocusId ?: if (screen == "exit") l.exitStopId else null
        roadTopId = l.roadTopId
        roadScrollY = l.roadScrollY
        roadFocusSeq += 1
    }

    // ------------------------------------------------------------------------------------------ defaults (P2-10)

    private var dailyKmTouched = false

    private fun defaultsNow() = DefaultsDto(
        frontAdult = frontAdult, seats = seats.map { it.name }, dog = dog, dailyKm = if (dailyKmTouched) dailyKm else null,
        budgetIndex = budgetIndex, mood = mood.name, moodTouched = moodTouched,
        originLabel = origin.label, originLat = origin.lat, originLon = origin.lon, originGen = originGen,
        locationAsked = locationAsked, originFromGps = originFromGps,
        walkAdults = cityAdults, walkChildren = cityChildren, walkDog = cityDog,
        handoffRemember = handoffRemember, handoffApp = handoffRememberedApp?.name,
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
        mood = Mood.parse(d.mood) ?: Mood.FUN
        moodTouched = d.moodTouched
        locationAsked = d.locationAsked
        originFromGps = d.originFromGps
        cityAdults = d.walkAdults.coerceIn(1, 9)
        cityChildren = d.walkChildren.coerceIn(0, 9)
        cityDog = d.walkDog
        handoffRemember = d.handoffRemember
        handoffRememberedApp = d.handoffApp?.let { n -> HandoffApp.entries.firstOrNull { it.name == n } }
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
        if (s.kind == "walk") {
            openSavedWalk(s)
            return
        }
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

enum class GpsState { Off, Waiting, On, Failed }

/** Where a hand-off went. */
/** Where a hand-off went (or would go: the dry runs of the e2e). */
enum class HandoffTarget { Navigator, Maps, Browser, None, NavigatorDryRun, MapsDryRun, BrowserDryRun }

/** Opens ADR-0014 links outside the app: car navigator → maps → web, walk maps → web (the activity uses intents). */
interface HandoffLauncher {
    fun navigatorInstalled(): Boolean
    fun mapsInstalled(): Boolean = false
    fun open(links: HandoffLinksDto, walk: Boolean): HandoffTarget

    /**
     * 5.13 §5 (S4): open exactly the app the user chose with [uri]; Карты without the app → [web] in the browser;
     * Навигатор without the app → [HandoffTarget.None] (the sheet offers the store instead).
     */
    fun openIn(app: HandoffApp, uri: String?, web: String?): HandoffTarget =
        open(if (app == HandoffApp.NAVI) HandoffLinksDto(navigator = uri) else HandoffLinksDto(maps = uri, web = web), walk = app == HandoffApp.MAPS)

    /** «Установить из магазина приложений». */
    fun openStore(app: HandoffApp) = Unit
}

/** The two hand-off apps of the S4 sheet (5.13 §5). */
enum class HandoffApp { MAPS, NAVI }

/** 5.13 §5: the open hand-off sheet: [day] or the «До след.» scope ([day] = null), and the engine's day hand-off. */
data class HandoffSheet(val day: Int?, val handoff: HandoffDto? = null, val handoffDay: Int = day ?: 1)

/** The phone's position (5.12: `LocationManager`; FusedLocation needs Play services the mock does not ship). */
interface Locator {
    fun granted(): Boolean
    suspend fun current(): GeoPoint?
    /** Fine location granted (else the fix is «примерно, по сети» and «Точнее» shows). */
    fun precise(): Boolean = true
    /** Location services on at all (off → «Геолокация на телефоне выключена» + «Включить»). */
    fun enabled(): Boolean = true
}

enum class CardSource { ROAD, WALK }

/** D-7: what the report is about; [fromWalk] = focus goes back to the walk row. */
data class ReportTarget(val name: String, val placeId: String?, val stopId: String?, val source: String, val fromWalk: Boolean)

/** An open 5.9 card: the row it came from ([rowId] = stop id), the place id and what it shows. */
data class CardState(val source: CardSource, val rowId: String, val poiId: String?, val ui: app.verst.feature.card.CardUi)

/** 5.10 18+ dialog: the alcohol preset or the «бары» interest waiting for the answer. */
data class AgeGate(val preset: String? = null, val interest: String? = null)

/** 5.12 §2 address search state under the ОТКУДА / КУДА field. */
/** [Later]: the service failed (timeout, 5xx, garbage, breaker) → the quiet «уточним при интернете» (ADR-0016 OR-4). */
enum class AddressState { Idle, Searching, Done, None, Offline, Later }

/** 5.10 «СКОЛЬКО ГУЛЯЕМ» chips, minutes. */
val WalkDurations = listOf(120, 240, 360, 480)

/** S4 (ADR-0015 §6): the dog preset; shown first, and only with the dog in the walk's crew. */
const val DOG_WALK = "dog_walk"

/** 5.10 §10 step 4: preset order (unknown presets after these, «Свой маршрут» last). */
val CityPresetOrder = listOf(DOG_WALK, "overview", "museums", "ryumochnye", "beer", "custom")

/** How a walk is requested (5.11 §10.2): it decides what a `NOT_ENOUGH_POIS` does. */
enum class WalkBuild { GO, FILTER, OTHER, REMOVE }

/** `NOT_ENOUGH_POIS` for the request ([durationMin], [unlimited]) with the engine's verified suggestions. */
data class WalkFew(
    val durationMin: Int?,
    val unlimited: Boolean,
    val suggestions: List<app.verst.core.model.dto.WalkSuggestion>,
    val count: Int?,
)

/** The picker sheets of 5.10 (prefs) and 5.11 (filter bar). */
enum class CityPicker { DURATION, PRESET, CREW, BUDGET, PACE }

private val ADDRESS_WORDS = listOf("ул", "пр", "пер", "д", "просп", "наб", "пл", "ш")

/** The R1 local links as an ADR-0014 hand-off (the fallback when the engine call fails). */
fun NaviHandoff.toDto(day: Int?, mode: String = "car"): HandoffDto =
    HandoffDto(mode, day, listOf(HandoffPartDto(1, emptyList(), HandoffLinksDto(navi, mapsApp, web))), truncated = false)

/** Great-circle distance for «the nearest town». */
object TownMath {
    fun km(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val r = 6371.0
        val dLat = Math.toRadians(lat2 - lat1)
        val dLon = Math.toRadians(lon2 - lon1)
        val a = kotlin.math.sin(dLat / 2).let { it * it } +
            kotlin.math.cos(Math.toRadians(lat1)) * kotlin.math.cos(Math.toRadians(lat2)) * kotlin.math.sin(dLon / 2).let { it * it }
        return 2 * r * kotlin.math.asin(kotlin.math.sqrt(a))
    }
}
