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
import app.verst.analytics.Analytics
import app.verst.analytics.AnalyticsEvent
import app.verst.analytics.Buckets
import app.verst.analytics.NoopAnalytics
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
enum class Route { Windshield, Navigator, Instruments, Drive, Road, Waybill, Exit, Debug, NoFit, City, Walk, Settings }

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

    /** 5.13 hand-off toasts; [google]: Google Карты were the app (not installed → the browser). */
    data class HandoffWeb(val walk: Boolean, val google: Boolean = false) : Toast
    data object HandoffOffline : Toast
    data object HandoffFailed : Toast
    /** 5.13 §5: «Открываем Яндекс Карты / Google Карты / Навигатор» (1 s) before the app opens. */
    data class HandoffOpen(val app: HandoffApp) : Toast

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
    internal val gateway: PlannerGateway,
    internal val scope: CoroutineScope,
    private val store: TripStore,
    private val io: CoroutineDispatcher = Dispatchers.IO,
    internal val now: () -> Long = System::currentTimeMillis,
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
        internal set
    var windshield: WindshieldData by mutableStateOf(WindshieldData.Loading)
        private set
    var selectedRoute by mutableStateOf(0)

    // ---- GPS origin (S3-R1 → 5.12, DEV-301)
    /** Off (not used) / Waiting («Ищем вас…») / On (the origin is the fix's town) / Failed. */
    var gps by mutableStateOf(GpsState.Off)
        internal set
    /** 5.12 rationale sheet «Откуда поедем?» (until answered once). */
    var locationSheet by mutableStateOf(false)
        internal set
    internal var locationAsked = false
    var originFromGps by mutableStateOf(false)
        internal set
    /** The fix is coarse («примерно, по сети» + «Точнее»). */
    var gpsApprox by mutableStateOf(false)
        internal set
    /** Online reverse geocoding of the fix: «ул. Советская, 1». */
    var originAddress: String? by mutableStateOf(null)
        internal set
    /** 5.12: the fix is outside Russia (`insideRussia = false`); ПОЕХАЛИ stays disabled until a Russian start. */
    var outsideRussia by mutableStateOf(false)
        internal set
    /** The phone's position; set by the app (LocationManager), null in tests without one. */
    var locator: Locator? = null

    /** CEO 29.10: the phone's geocoder, asked when Nominatim fails or finds nothing (search and «where am I»). */
    var addressFallback: app.verst.data.net.AddressSearch? = null
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
        internal set
    /** e2e: record the hand-off without leaving the app. */
    var debugHandoffDryRun = false
    /** D-5 stop menu (long-press on a Road-ahead row) and its engine hand-off. */
    var stopMenu: StopDto? by mutableStateOf(null)
        internal set
    var stopHandoff: HandoffDto? by mutableStateOf(null)
        internal set
    /** 5.13 day menu «В навигатор: день N». */
    var dayMenu: Int? by mutableStateOf(null)
        internal set
    var dayHandoff: HandoffDto? by mutableStateOf(null)
        internal set
    /**
     * 5.13 §5 (S4) the hand-off sheet, and «Запомнить выбор» (persisted with the defaults): with it on, the maps app
     * picked in the sheet becomes the «Настройки → Навигация» choice.
     */
    var handoffSheet: HandoffSheet? by mutableStateOf(null)
        internal set
    var handoffRemember by mutableStateOf(false)
        internal set
    /**
     * CEO 29.10 «Навигация»: the user's maps choice (AppPrefs in the app; unit tests swap both for a variable).
     * Compose reads it through AppPrefs' state, so the screens follow a change.
     */
    var mapsChoiceRead: () -> app.verst.core.model.MapsChoice = { app.verst.settings.AppPrefs.settings.mapsApp }
    var mapsChoiceWrite: (app.verst.core.model.MapsChoice) -> Unit = { c -> app.verst.settings.AppPrefs.update { it.copy(mapsApp = c) } }
    /** Where the phone is now (TelephonyManager, set by the app); null = unknown → Яндекс Карты. */
    var countrySource: CountrySource? = null
    /**
     * ADR-0015 §1: the build's Яндекс signing key (MainActivity, from BuildConfig). CEO 29.10: we do not get a key, so
     * the Навигатор gets the next point only and the whole day goes to the maps apps; the signer stays for the record.
     */
    var handoffSigner: app.verst.core.model.HandoffSigner? = null
    val handoffSigned: Boolean get() = handoffSigner != null

    // ---- 5.9 cards
    var card: CardState? by mutableStateOf(null)

    /** CEO 29.10: the cards' reverse-geocoded street addresses for this session, per place id (else row id). */
    internal val cardAddresses = HashMap<String, String>()

    /** D-7 report sheet: the place, the reason (one of [app.verst.core.model.Reports.REASONS]), the comment. */
    var report: ReportTarget? by mutableStateOf(null)
    var reportReason: String? by mutableStateOf(null)
    var reportComment: String by mutableStateOf("")
        internal set
    /** 5.12 §3 «О данных» sheet. */
    var aboutData by mutableStateOf(false)
    /** 5.5 §10.6: the stop whose ParkingSheet is open (Road ahead). */
    var roadParking: StopDto? by mutableStateOf(null)
        internal set
    /** CEO 29.10 (trips abroad): the border stop whose sheet is open (documents, fees, facts with sources). */
    var roadBorder: StopDto? by mutableStateOf(null)
        internal set

    // ---- 5.8 budget fit
    var noFit: app.verst.core.model.dto.NoFitDto? by mutableStateOf(null)
        private set
    /** A no-fit «Поднять бюджет до …» value between the presets («до 42 000 ₽»); cleared by the stepper. */
    var budgetCustom: Int? by mutableStateOf(null)
        internal set
    /** The minimum trip of a no-fit, opened by «Показать самый экономный вариант» (over budget everywhere). */
    var showingMinimum by mutableStateOf(false)
        internal set
    /** `estimate` budget figures per request (Instruments caption meta). */
    internal val estimates = mutableStateMapOf<PlanRequest, EstimateDto>()

    // ---- 5.12 address search
    var addressResults: List<SuggestionDto> by mutableStateOf(emptyList())
        internal set
    var addressState by mutableStateOf(AddressState.Idle)
        internal set
    internal var addressJob: Job? = null

    // ---- 5.10 / 5.11 «По городу»
    var cityPresets: app.verst.core.model.dto.CityPresetsDto? by mutableStateOf(null)
        internal set
    var cityLoading by mutableStateOf(false)
        internal set
    /** `NO_CITY` / `NOT_ENOUGH_POIS` / another engine code of the last presets or walk call. */
    var cityError: String? by mutableStateOf(null)
        internal set
    var cityPreset by mutableStateOf("overview")
        internal set
    /** null = «без ограничения» (S4, ADR-0015 §6). */
    var cityDurationMin: Int? by mutableStateOf(240)
        internal set
    /** S4: values the user chose are kept — a preset's defaults only fill what was never touched. */
    internal var cityDurationTouched = false
    internal var cityPaceTouched = false
    /** S4 5.10 §10: the walk's own crew (not the car's), remembered for walks only. */
    var cityAdults by mutableStateOf(2)
        internal set
    var cityChildren by mutableStateOf(0)
        internal set
    var cityDog by mutableStateOf(false)
        internal set
    /** S4 5.11 §10.2: «Другой вариант» found nothing new — the button is disabled until the input changes. */
    var walkOtherNone by mutableStateOf(false)
        internal set
    /**
     * S4 5.11 §10.5 / 5.10: `NOT_ENOUGH_POIS` with the engine's verified suggestions (never guessed here); CEO 29.10:
     * with `reason: "no_data"` it carries the engine's `messageRu` instead of «мало мест».
     */
    var walkFew: WalkFew? by mutableStateOf(null)
        internal set
    /** M6: request input → the engine's `requestKey` (stale answers and same-request rebuilds). */
    internal val walkKeyByInput = HashMap<String, String>()
    /** S4: which picker sheet is open (5.10 prefs, 5.11 filter bar). */
    var cityPicker: CityPicker? by mutableStateOf(null)
        internal set
    internal var walkSeq = 0
    internal var rebuildJob: Job? = null
    internal var lastOtherAdded: List<String> = emptyList()
    val cityInterests = mutableStateListOf<String>()
    var cityPace by mutableStateOf("normal")
        internal set
    var cityBudget: Int? by mutableStateOf(null)
        internal set
    var cityReturn by mutableStateOf(true)
        internal set
    var cityCustomSheet by mutableStateOf(false)
        internal set
    /** 18+ dialog: what to apply on «Да, мне есть 18» (a preset, or the «бары» interest). */
    var ageGate: AgeGate? by mutableStateOf(null)
        internal set
    internal var adultConfirmed = false
    var walkBuilding by mutableStateOf(false)
        internal set
    var walk: app.verst.core.model.dto.WalkRouteDto? by mutableStateOf(null)
        internal set
    internal val walkExclude = mutableListOf<String>()
    internal var walkJob: Job? = null
    var walkHandoff: HandoffDto? by mutableStateOf(null)
        internal set
    /** The walk start (the GPS origin or a picked point); null = the trip origin. */
    var cityStart: GeoPoint? by mutableStateOf(null)
        internal set
    internal var cityPickingStart = false

    // ---- Road-ahead focus restore (S3-R1, CEO 2.1)
    /** The row acted on (Exit, replace, stop menu): scrolled into view and highlighted on the way back. */
    var roadFocusId: String? by mutableStateOf(null)
        internal set
    /** The top visible row while scrolling (restores the position after Waybill / process death). */
    var roadTopId: String? by mutableStateOf(null)
        private set
    /** Bumps on every return to Road ahead (back from a screen, a sheet closed, a restore). */
    var roadFocusSeq by mutableStateOf(0)
        internal set
    /** 5.9 §5: the scroll offset of Road ahead, restored exactly on the way back (also after process death). */
    var roadScrollY: Int? by mutableStateOf(null)
        private set
    /** Walk result focus restore (as Road ahead). */
    var walkFocusId: String? by mutableStateOf(null)
        internal set
    var walkFocusSeq by mutableStateOf(0)
        internal set
    /** The saved id of the walk on screen (DEV-308). */
    var savedWalkId: String? by mutableStateOf(null)
        internal set

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
        internal set
    var editingFrom by mutableStateOf(false)
        internal set

    /** 5.12 §5 autofocus: КУДА takes focus after a hand-picked ОТКУДА, not after a GPS fix (S3-QA P1-01). */
    var focusToField by mutableStateOf(true)
        internal set

    /** Base-route km from the origin to suggestion rows («lat,lon» → km; null = unreachable). */
    val rowKm = mutableStateMapOf<String, Int?>()

    /** TOO_SHORT / UNREACHABLE from the last plan, shown in the Navigator caption (5.2 §4.4). */
    var routeError: String? by mutableStateOf(null)
        private set
    private var suggestJob: Job? = null

    // ---- Instruments
    var readyRoute: ReadyRouteDto? by mutableStateOf(null)
        internal set
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
    internal val known = mutableStateListOf<Pair<PlanRequest, TripFigures>>()

    /** The estimate error of a request (TOO_SHORT / UNREACHABLE / INVALID_INPUT before the plan). */
    var estimateError: Pair<PlanRequest, EngineErrorDto>? by mutableStateOf(null)
        private set

    // ---- Drive / Road / Waybill
    var drive by mutableStateOf(DriveUi())
        private set

    /** The trip on Road ahead and the Waybill (fresh plan or reopened saved trip). */
    var result: PlanResultDto? by mutableStateOf(null)
        internal set

    /** The request [result] was planned from (null for a reopened saved trip). */
    internal var resultRequest: PlanRequest? = null
    var resultBearing by mutableStateOf("N")
        private set
    var openedFromSaved by mutableStateOf(false)
        private set
    private var planJob: Job? = null

    var expandedLine: String? by mutableStateOf(null)
        private set
    var costBusy by mutableStateOf(false)
        internal set
    var replace: ReplaceUi? by mutableStateOf(null)
        internal set
    var toast: Toast? by mutableStateOf(null)
        internal set
    internal var undoTrip: PlanResultDto? = null
    internal var toastJob: Job? = null

    // ---- saved trips
    val saved = mutableStateListOf<SavedTripDto>()

    /** Id of [result] in [saved] (null = never saved); [savedCurrent] = the saved copy equals [result]. */
    var savedId: String? by mutableStateOf(null)
        internal set
    var savedCurrent by mutableStateOf(false)
        internal set
    var tripsSheet by mutableStateOf(false)
        internal set

    /** D-1 deletion: the trip awaiting confirmation (NaviDialog), the last deleted one for «Вернуть». */
    var deleteAsk: SavedTripDto? by mutableStateOf(null)
        private set
    internal var lastDeleted: Pair<Int, SavedTripDto>? = null

    /** 5.5 §4 limit: the «Место для поездок закончилось» dialog. */
    var limitDialog by mutableStateOf(false)
        private set

    // ---- Exit 5.7 / D-10
    var exitStopId: String? by mutableStateOf(null)
        internal set
    var partnerOpen by mutableStateOf(false)
        internal set
    var bookedDialog by mutableStateOf(false)
        internal set

    /** 5.7 §8: per overnight stop, the hotel marked «Забронировали» (persisted with a saved trip). */
    val booked = mutableStateMapOf<String, String>()
    internal var undoBooked: String? = null

    /** OI-39: the origin's genitive from the engine («Москвы»), the nominative until known. */
    var originGen by mutableStateOf(DefaultOrigin.label)
        internal set

    /** Trips whose Waybill stamp has played (motion.stamp once per trip version, 5.6 §3.1). */
    private val stampShown = mutableSetOf<String>()

    // ---- DEV-127 debug panel (plain list, not part of visual QA)
    var debugGolden by mutableStateOf(false)
        private set
    var debugSlowSec by mutableStateOf(0)
    /** null = no forced error; else the engine code the next plan returns. */
    var debugForceError: String? by mutableStateOf(null)
    val debugWorld: String get() = gateway.world

    // ---- ENG-05 analytics (SPEC §15, docs/traction/tracking-plan.md §2)
    /** Set by the activity ([app.verst.analytics.VerstAnalytics]); [NoopAnalytics] until then and in tests. */
    var analytics: Analytics = NoopAnalytics

    /**
     * The analytics `trip_id` of [result]: a new random id for each ПОЕХАЛИ, kept through replace, re-cost and refit
     * of an unsaved trip; once the trip is saved it is its saved id (so a reopened trip reports the same id).
     */
    var tripId: String? = null
        internal set

    /** The `trip_id` the running (or last) plan will give its trip. */
    internal var planTripId: String? = null

    /** `search_started` was sent in this Navigator visit. */
    private var searchStarted = false

    /** `start_city` of the last origin asked (the engine's catalogue town within 30 km, else `other`). */
    private var startCity: Pair<GeoPoint, String>? = null

    /** Builds and sends an event only when analytics is on (a no-op build computes nothing). */
    internal inline fun track(event: () -> AnalyticsEvent?) {
        val a = analytics
        if (a.enabled) event()?.let(a::track)
    }

    /** `app_open` (the activity knows cold / warm, see [app.verst.analytics.AppOpenTracker]). */
    fun appOpened(start: AnalyticsEvent.StartType) = track { AnalyticsEvent.AppOpen(start, offline = !connectivity.online) }

    /** The trip's share sheet was opened (Road ahead / Waybill «Поделиться»); the chosen app is not known. */
    fun tripShared() = track { AnalyticsEvent.TripShared(tripId, AnalyticsEvent.ShareChannel.UNKNOWN) }

    /**
     * ENG-05 `trip_driven_confirmed` (tracking plan §2.3): the answer to «Вы съездили?» for saved trip [id], dated
     * [today] (Moscow). «Да» / «Частично» send the event, «Нет» sends nothing; so does a trip that is not saved, has no
     * start date, or has not ended yet (the question comes from the day after its last day E). The post-trip question
     * that calls this is a later UI task (feature freeze). Returns whether the event was sent.
     */
    fun answerTripDriven(id: String, answer: DrivenAnswer, today: java.time.LocalDate = java.time.LocalDate.now(MOSCOW)): Boolean {
        val completion = when (answer) {
            DrivenAnswer.FULL -> AnalyticsEvent.Completion.FULL
            DrivenAnswer.PARTIAL -> AnalyticsEvent.Completion.PARTIAL
            DrivenAnswer.NO -> return false
        }
        val t = saved.firstOrNull { it.id == id && it.kind == "trip" } ?: return false
        val start = Buckets.date(t.startAt)?.let { java.time.LocalDate.parse(it) } ?: return false
        val end = start.plusDays((t.days - 1).coerceAtLeast(0).toLong())
        val sinceEnd = java.time.temporal.ChronoUnit.DAYS.between(end, today).toInt()
        if (sinceEnd < 1) return false
        val event = AnalyticsEvent.TripDrivenConfirmed(t.id, completion, sinceEnd, Buckets.km(t.km), t.dog, Buckets.children(t.children))
        if (!analytics.enabled) return false
        analytics.track(event)
        return true
    }

    /**
     * `ready_route_id` of trip [r]: the template of the request it was planned from, else (a reopened or restored trip)
     * the one the engine echoes in the trip's input; [AnalyticsEvent.NO_READY_ROUTE] for a free A → B trip.
     */
    private fun readyRouteIdOf(r: PlanResultDto): String =
        resultRequest?.readyRouteId ?: r.trip.input.readyRouteId ?: AnalyticsEvent.NO_READY_ROUTE

    /** `navigator_opened.app` of a hand-off target (the e2e dry runs count as the app they stand for). */
    internal fun naviApp(target: HandoffTarget): AnalyticsEvent.NaviApp? = when (target) {
        HandoffTarget.Navigator, HandoffTarget.NavigatorDryRun -> AnalyticsEvent.NaviApp.YANDEX_NAVIGATOR
        HandoffTarget.Maps, HandoffTarget.MapsDryRun -> AnalyticsEvent.NaviApp.YANDEX_MAPS
        HandoffTarget.Google, HandoffTarget.GoogleDryRun -> AnalyticsEvent.NaviApp.GOOGLE_MAPS
        HandoffTarget.Browser, HandoffTarget.BrowserDryRun -> AnalyticsEvent.NaviApp.WEB
        HandoffTarget.None -> null
    }

    fun openDebug() = push(Route.Debug)

    /** D-IR-20 personal cabinet (the profile button on the Windshield). */
    fun openSettings() = push(Route.Settings)

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
        cardAddresses.clear() // another world's place ids
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
        // ENG-05 `ready_route_shown`: once per showing of the Windshield list; an empty list (NoRoutes) counts as 0.
        scope.launch {
            snapshotFlow {
                if (top != Route.Windshield) {
                    null
                } else {
                    when (val w = windshield) {
                        is WindshieldData.Routes -> w.routes.size to origin
                        WindshieldData.NoRoutes -> 0 to origin
                        else -> null
                    }
                }
            }.distinctUntilChanged().collect { shown ->
                if (shown != null && analytics.enabled) {
                    analytics.track(AnalyticsEvent.ReadyRouteShown(shown.first, startCityOf(shown.second)))
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
        if (route == Route.Navigator) searchStarted = false // ENG-05: a new Navigator visit
        stack.add(route)
    }

    /** System back and every back link. Sheets close first. Returns false on the root (the activity finishes). */
    fun back(): Boolean {
        if (abroadConsentAsk) {
            answerAbroadConsent(false)
            return true
        }
        if (roadBorder != null) {
            closeBorder()
            return true
        }
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

    /** A ready-route row tapped on the Windshield (ENG-05 `ready_route_selected`; rank = the row from 1). */
    fun selectReadyRoute(i: Int) {
        selectedRoute = i
        track { (windshield as? WindshieldData.Routes)?.routes?.getOrNull(i)?.let { AnalyticsEvent.ReadyRouteSelected(it.id, i + 1) } }
    }

    /** `start_city` of [o]: the engine's catalogue town within 30 km (`reverse`), never the address or the point. */
    private suspend fun startCityOf(o: GeoPoint): String {
        startCity?.takeIf { it.first == o }?.let { return it.second }
        val town = (gateway.reverse(o) as? EngineResult.Ok)?.value?.name ?: AnalyticsEvent.OTHER
        startCity = o to town
        return town
    }

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
        if (!searchStarted) {
            searchStarted = true
            track { AnalyticsEvent.SearchStarted(q.trim().length) } // the length only, never the query
        }
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

    internal fun fetchRowKm(rows: List<SuggestionDto>) {
        // CEO 29.10: no engine km for an address abroad (the engine does not route outside Russia)
        val missing = rows.filter { it.pointKey !in rowKm && !it.abroad }
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
        track {
            val rank = listOf(addressResults, suggestions, popular).firstNotNullOfOrNull { rows -> rows.indexOf(s).takeIf { it >= 0 } }
            AnalyticsEvent.SearchSelected(query.trim().length, AnalyticsEvent.SearchResultType.of(s.kind), rank?.plus(1) ?: 0)
        }
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

    /**
     * CEO 29.10: the picked КУДА is an address abroad. The phone engine plans only in Russia (`INVALID_INPUT`
     * outside_russia): no estimate is asked for it, and (wave 1) only the server plans it — see [abroadOnServer].
     */
    val destinationAbroad: Boolean get() = readyRoute == null && destination?.abroad == true

    /**
     * CEO 29.10 (trips abroad, wave 1): this build has a server, which plans trips abroad. The app's gateway knows it;
     * unit tests with a fake engine set it.
     */
    var serverConfigured: () -> Boolean = { (gateway as? app.verst.engine.ServerPlannerGateway)?.serverConfigured == true }

    /** Security review В-1: the tester's consent to plan on the server (AppPrefs in the app; unit tests swap both). */
    var serverConsentRead: () -> Boolean = { app.verst.settings.AppPrefs.settings.serverConsent }
    var serverConsentWrite: () -> Unit = { app.verst.settings.AppPrefs.update { it.copy(serverConsent = true) } }

    /**
     * CEO 29.10 (wave 1): КУДА is abroad and the server can plan it now (a server in this build, the phone online) —
     * whatever «Где строить маршрут» says. The screens say so in one line («Поездку за границу строит сервер Версты —
     * нужен интернет.»).
     */
    val abroadOnServer: Boolean get() = destinationAbroad && serverConfigured() && connectivity.online

    /**
     * КУДА is abroad and nothing can plan it now (offline, or a build without a server): the Navigator's plate with the
     * maps hand-off ([abroadHandoff]); no plan is sent.
     */
    val abroadBlocked: Boolean get() = destinationAbroad && !abroadOnServer

    /** Security review В-1 before the first trip abroad: the settings' consent dialog («Согласен» / «Не сейчас»). */
    var abroadConsentAsk by mutableStateOf(false)
        private set

    /** ПОЕХАЛИ on 5.2 → Instruments with A → B. */
    fun openInstrumentsFree() {
        val d = destination ?: return
        // CEO 29.10: never a doomed plan abroad — only the server plans there (the plate says why when it can't)
        if (d.abroad && !(serverConfigured() && connectivity.online)) return
        readyRoute = null
        if (!dailyKmTouched) dailyKm = TripMath.defaultDailyKm(rowKm[d.pointKey] ?: 0)
        push(Route.Instruments)
    }

    // ------------------------------------------------------------------------------------------ instruments

    /** The draft request when it has a target (destination or ready route), else null. */
    fun draft(): PlanRequest? = if (readyRoute != null || destinationPoint != null) request() else null

    private fun estimateTarget(): PlanRequest? =
        if (destinationAbroad) null // CEO 29.10: the engine rejects a destination abroad — nothing to estimate
        else if ((top == Route.Navigator && !editingFrom) || top == Route.Instruments) draft() else null

    /** The engine's km/days of the draft: exact for this request, stale while a newer estimate runs, or null. */
    val figures: TripFiguresPick.Picked?
        get() = TripFiguresPick.pick(draft(), known)

    /** TOO_SHORT / UNREACHABLE of the current draft (before any plan). */
    val draftError: EngineErrorDto?
        get() = estimateError?.takeIf { it.first == draft() }?.second

    internal fun record(r: PlanRequest, f: TripFigures) {
        known.removeAll { it.first == r }
        known.add(r to f)
        while (known.size > 48) known.removeAt(0)
    }

    val tripTitle: String
        get() = readyRoute?.title ?: "${origin.label} → ${destination?.name ?: "?"}"

    /** Seat cycle empty → adult → child → empty; ≤ 8 people incl. the driver (OI-07). */
    fun cycleSeat(i: Int) {
        val a = adults
        val c = children
        seats[i] = when (seats[i]) {
            Seat.EMPTY -> Seat.ADULT
            Seat.ADULT -> Seat.CHILD
            Seat.CHILD -> Seat.EMPTY
        }
        crewChanged(a, c)
    }

    /** Instruments front passenger seat (adult / empty). */
    fun toggleFrontAdult() {
        val a = adults
        val c = children
        frontAdult = !frontAdult
        crewChanged(a, c)
    }

    /** Instruments dog. */
    fun toggleDog() {
        dog = !dog
        track { AnalyticsEvent.ParamsChanged(AnalyticsEvent.ParamField.DOG, Buckets.yesNo(dog)) }
    }

    /** ENG-05 `params_changed` for the crew counts that moved (an adult seat turned child moves both). */
    private fun crewChanged(adultsBefore: Int, childrenBefore: Int) {
        if (adults != adultsBefore) track { AnalyticsEvent.ParamsChanged(AnalyticsEvent.ParamField.ADULTS, Buckets.adults(adults)) }
        if (children != childrenBefore) track { AnalyticsEvent.ParamsChanged(AnalyticsEvent.ParamField.CHILDREN, Buckets.children(children)) }
    }

    fun pickMood(m: Mood) {
        moodTouched = true
        mood = m
    }

    fun stepKm(delta: Int) {
        val before = dailyKm
        dailyKmTouched = true
        dailyKm = (dailyKm + delta).coerceIn(TripMath.KM_MIN, TripMath.KM_MAX)
        if (dailyKm != before) track { AnalyticsEvent.ParamsChanged(AnalyticsEvent.ParamField.PACE, Buckets.pace(dailyKm)) }
    }

    fun stepBudget(delta: Int) {
        val before = budgetRub
        stepBudgetValue(delta)
        if (budgetRub != before) track { AnalyticsEvent.ParamsChanged(AnalyticsEvent.ParamField.BUDGET, Buckets.budget(budgetRub)) }
    }

    private fun stepBudgetValue(delta: Int) {
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
        vehicle = carVehicle(),
        avoidTolls = app.verst.settings.AppPrefs.settings.avoidTolls,
        abroad = destinationAbroad, // CEO 29.10: the server plans it, never the phone
    )

    /** The car from the settings (traveller К4), or null while it is the engine's default car. */
    private fun carVehicle(): app.verst.core.model.VehicleInput? {
        val s = app.verst.settings.AppPrefs.settings
        val car = app.verst.core.model.VehicleInput(s.consumption, s.fuelType, s.tankL)
        val default = app.verst.core.model.VehicleInput(
            app.verst.core.model.Car.DEFAULT_CONSUMPTION, app.verst.core.model.Car.DEFAULT_FUEL, app.verst.core.model.Car.DEFAULT_TANK,
        )
        return car.takeIf { it != default }
    }

    /** The budget the gauge shows: a no-fit «Поднять бюджет до …» value, else the preset. */
    val budgetRub: Int? get() = budgetCustom ?: BudgetPresets[budgetIndex]

    // ------------------------------------------------------------------------------------------ drive

    /**
     * ПОЕХАЛИ on 5.3 → Drive; the plan runs on `verst-python` (or the server), the steps are paced ≥ 400 ms (5.4 §6).
     * CEO 29.10: a trip abroad goes to the server only — nothing without one or offline (the plate), and the consent
     * dialog first when the tester has not agreed to plan on the server yet.
     */
    fun go() {
        if (abroadBlocked) return // a plan abroad on the phone would only fail (`INVALID_INPUT` outside_russia)
        if (destinationAbroad && !serverConsentRead()) {
            abroadConsentAsk = true
            return
        }
        if (top != Route.Drive) push(Route.Drive)
        val r = request()
        track {
            // the engine's estimate of exactly this request; none yet → `unknown`
            val f = figures?.takeUnless { it.stale }?.figures
            AnalyticsEvent.PlanRequested(
                Buckets.km(f?.km), f?.days, r.dog, Buckets.children(r.children), r.mood?.wire,
                r.readyRouteId ?: AnalyticsEvent.NO_READY_ROUTE,
            )
        }
        startPlan(r, planId = UUID.randomUUID().toString()) // tracking plan §2.5 q3: a new trip_id per ПОЕХАЛИ only
    }

    /** The consent dialog's answer: «Согласен» records the consent and plans on the server; «Не сейчас» stays. */
    fun answerAbroadConsent(agree: Boolean) {
        abroadConsentAsk = false
        if (!agree) return
        serverConsentWrite()
        if (serverConsentRead()) go()
    }

    fun retryPlan() = startPlan(lastPlanRequest ?: request())

    internal var lastPlanRequest: PlanRequest? = null

    /** [planId]: the `trip_id` the planned trip gets (a retry keeps the one of the plan it retries). */
    internal fun startPlan(request: PlanRequest = request(), planId: String = planTripId ?: UUID.randomUUID().toString()) {
        planJob?.cancel()
        drive = DriveUi()
        lastPlanRequest = request
        planTripId = planId
        val id = UUID.randomUUID().toString()
        val startedAt = now()
        planJob = scope.launch {
            val pending = ArrayDeque<Pair<String, Float>>() // stage text, engine progress at that stage
            var days = 0
            var finished: EngineResult<app.verst.core.model.dto.PlanOutcome>? = null
            var doneAt: Long? = null // ENG-05 latency: when the engine answered (the pacer below only paces the text)
            val forced = debugForceError
            val slowMs = debugSlowSec * 1000L
            val engine = launch {
                if (forced != null) {
                    delay(STEP_GAP_MS)
                    finished = EngineResult.Err(EngineErrorDto(forced, "debug: forced"))
                    doneAt = now()
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
                doneAt = now()
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
            val latencyMs = (doneAt ?: now()) - startedAt
            when (val r = finished) {
                is EngineResult.Ok -> when (val o = r.value) {
                    is app.verst.core.model.dto.PlanOutcome.Plan -> {
                        val bearing = readyRoute?.bearing8 ?: request.destination?.let { TripMath.bearing8(request.origin, it) } ?: "N"
                        noFit = null
                        showingMinimum = false
                        showTrip(o.result, request, bearing, savedId = null, fromSaved = false, tripId = planId)
                        track {
                            val source = if (o.result.trip.approxDistances) AnalyticsEvent.RoutingSource.FALLBACK else AnalyticsEvent.RoutingSource.ROAD
                            AnalyticsEvent.PlanSucceeded(planId, latencyMs, source, request.readyRouteId ?: AnalyticsEvent.NO_READY_ROUTE)
                        }
                        drive = drive.copy(progress = 1f, done = true, days = o.result.trip.days)
                        delay(AUTO_ADVANCE_MS)
                        if (top == Route.Drive) openRoad()
                    }
                    is app.verst.core.model.dto.PlanOutcome.NoFit -> {
                        // 5.8: «Смотреть варианты», auto-advance after 1 s as for a plan
                        noFit = o.noFit
                        track { AnalyticsEvent.PlanFailed(latencyMs, NO_FIT_CODE) }
                        drive = drive.copy(progress = 1f, done = true, noFit = true)
                        delay(AUTO_ADVANCE_MS)
                        if (top == Route.Drive) openNoFit()
                    }
                }
                is EngineResult.Err -> if (r.error.code == "CANCELLED") {
                    if (top == Route.Drive) stack.removeAt(stack.lastIndex)
                } else {
                    track { AnalyticsEvent.PlanFailed(latencyMs, r.error.code) }
                    drive = drive.copy(error = r.error)
                }
                null -> {
                    track { AnalyticsEvent.PlanFailed(latencyMs, "INTERNAL") }
                    drive = drive.copy(error = EngineErrorDto("INTERNAL", "no result"))
                }
            }
        }
    }

    internal fun showTrip(
        r: PlanResultDto,
        request: PlanRequest?,
        bearing: String,
        savedId: String?,
        fromSaved: Boolean,
        tripId: String?,
        bookedStops: Map<String, String> = emptyMap(),
    ) {
        result = r
        this.tripId = tripId
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
        roadBorder = null
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
        "UNREACHABLE", "TOO_SHORT", app.verst.engine.ServerPlannerGateway.ABROAD_NO_SERVER -> DriveAction.CHANGE_ROUTE
        app.verst.engine.ServerPlannerGateway.ABROAD_NO_CONSENT -> DriveAction.TO_INSTRUMENTS
        else -> DriveAction.RETRY
    }

    /**
     * CEO 29.10: the engine's verdict about a point abroad (a closed border, no crossing, a country it does not plan)
     * is about the route — back to the Navigator with the server's own sentence; the rest by [code][driveAction].
     */
    fun driveAction(e: EngineErrorDto): DriveAction = if (e.abroadVerdict) DriveAction.CHANGE_ROUTE else driveAction(e.code)

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

    // ---- state of the cards, report and location sections (their functions: CardsFlow.kt, LocationFlow.kt, HYG-02)

    /** Debug panel «Настоящие фото Commons»: [app.verst.core.model.CommonsPhotos.DEBUG_FILES] on every card. */
    var debugRealPhotos by mutableStateOf(false)
    var debugPhotoIndex = 0

    /** Reports queued this session (debug / tests). */
    var reportsSent by mutableStateOf(0)
        internal set

    internal var locateJob: Job? = null

    internal var presetsJob: Job? = null

    // ------------------------------------------------------------------------------------------ road / waybill

    /** Road footer «ПУТЕВОЙ ЛИСТ · СКОЛЬКО СТОИТ» → Waybill 5.6. */
    fun openWaybill() {
        val r = result ?: return
        expandedLine = null
        push(Route.Waybill)
        track { AnalyticsEvent.WaybillOpened(tripId, Buckets.total(r.trip.cost.totalRub), r.trip.cost.overBudget) }
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
        track { AnalyticsEvent.ReserveToggled(tripId, on) }
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
    internal fun localCost(r: PlanResultDto, f: (kotlinx.serialization.json.JsonObject) -> app.verst.core.model.dto.TripDto) {
        runCatching { f(LocalCost.parse(r.tripJson)) }.onSuccess { result = r.copy(trip = it) }
    }

    /** Waybill stamp: true the first time it is asked for this trip version (then the final frame). */
    fun stampOnce(): Boolean = stampShown.add(tripSession.toString())

    /** Increments when a new trip is shown (plan or reopened saved trip); cost edits keep the session. */
    var tripSession by mutableStateOf(0)
        private set

    // ------------------------------------------------------------------------------------------ saved trips

    /** Save (5.5 T1 / 5.6 K1): upsert into the saved list, then write the file. */
    fun save(silent: Boolean = false) {
        val r = result ?: return
        if (!tripsLoaded) {
            pendingSave = true // P1-1: never write before the stored trips are in memory
            return
        }
        // ENG-05: a new saved trip is keyed by its trip_id, so a reopened trip reports the same id; if that key is
        // taken (the saved copy was deleted and brought back), a new key as before, and the trip_id follows it.
        val id = savedId ?: tripId?.takeIf { t -> saved.none { it.id == t } } ?: UUID.randomUUID().toString()
        when (val up = SavedTrips.upsert(saved.toList(), SavedTrips.entry(id, now(), r, resultBearing, booked.toMap()))) {
            SavedTrips.Upsert.LimitReached -> limitDialog = true
            is SavedTrips.Upsert.Saved -> {
                saved.clear()
                saved.addAll(up.trips)
                savedId = id
                tripId = id
                if (!silent) {
                    track {
                        val start = r.trip.daysList.firstOrNull()?.startAt ?: r.trip.input.startAt
                        AnalyticsEvent.TripSaved(id, Buckets.date(start), r.trip.days, readyRouteIdOf(r))
                    }
                }
                savedCurrent = true
                if (!silent) showToast(if (up.nearLimit) Toast.SavedNearLimit(up.count) else Toast.Saved)
                persist()
            }
        }
    }

    internal fun persist() {
        pendingTrips = saved.toList()
        writes.trySend(Unit)
    }

    // ------------------------------------------------------------------------------------------ the one writer

    internal val writes = kotlinx.coroutines.channels.Channel<Unit>(kotlinx.coroutines.channels.Channel.CONFLATED)
    private var pendingTrips: List<SavedTripDto>? = null
    private var pendingLast: LastTripDto? = null
    private var lastDirty = false
    private var pendingDefaults: DefaultsDto? = null
    internal val pendingReports = mutableListOf<app.verst.core.model.ReportDto>()
    internal var tripsLoaded = false
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
                    trip = SavedTrips.entry(savedId ?: tripId ?: LAST_ID, now(), it, resultBearing, booked.toMap()),
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
        // ENG-05: last.json keys the trip by its trip_id (`enqueueLast`); a pre-ENG-05 file has «last» → a new id
        val restoredId = l.trip.id.takeUnless { it == LAST_ID } ?: UUID.randomUUID().toString()
        showTrip(
            r, request = null, bearing = l.trip.bearing8, savedId = if (stillSaved) l.savedId else null, fromSaved = true,
            tripId = restoredId, bookedStops = l.trip.bookedHotels,
        )
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

    internal var dailyKmTouched = false

    private fun defaultsNow() = DefaultsDto(
        frontAdult = frontAdult, seats = seats.map { it.name }, dog = dog, dailyKm = if (dailyKmTouched) dailyKm else null,
        budgetIndex = budgetIndex, mood = mood.name, moodTouched = moodTouched,
        originLabel = origin.label, originLat = origin.lat, originLon = origin.lon, originGen = originGen,
        locationAsked = locationAsked, originFromGps = originFromGps,
        walkAdults = cityAdults, walkChildren = cityChildren, walkDog = cityDog,
        // CEO 29.10: the remembered app is the «Навигация» setting now (AppSettings.mapsApp)
        handoffRemember = handoffRemember, handoffApp = null,
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
        showTrip(SavedTrips.result(s), request = null, bearing = s.bearing8, savedId = s.id, fromSaved = true, tripId = s.id, bookedStops = s.bookedHotels)
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

        /** The id of the current trip in last.json before ENG-05 (now its trip_id). */
        private const val LAST_ID = "last"

        /** ENG-05 `plan_failed.error_code` of a plan that found no trip within the budget (5.8). */
        const val NO_FIT_CODE = "NO_FIT"

        /** Moscow time: the tracking plan's clock (§0.4), and the day a «Вы съездили?» answer is dated. */
        val MOSCOW: java.time.ZoneId = java.time.ZoneId.of("Europe/Moscow")
    }
}

enum class GpsState { Off, Waiting, On, Failed }

/** The answers to the post-trip question «Вы съездили?» (tracking plan §2.3, VAL-04). */
enum class DrivenAnswer { FULL, PARTIAL, NO }

/** Where a hand-off went (or would go: the dry runs of the e2e). [Maps] = Яндекс Карты, [Google] = Google Карты. */
enum class HandoffTarget { Navigator, Maps, Google, Browser, None, NavigatorDryRun, MapsDryRun, GoogleDryRun, BrowserDryRun }

/** Opens ADR-0014 links outside the app: car navigator → maps → web, walk maps → web (the activity uses intents). */
interface HandoffLauncher {
    fun navigatorInstalled(): Boolean
    fun mapsInstalled(): Boolean = false
    /** CEO 29.10: the Google Maps app (`com.google.android.apps.maps`). */
    fun googleInstalled(): Boolean = false
    fun open(links: HandoffLinksDto, walk: Boolean): HandoffTarget

    /**
     * 5.13 §5 (S4): open exactly the app the user chose with [uri]; Яндекс / Google Карты without the app → [web] in
     * the browser; Навигатор without the app → [HandoffTarget.None] (the sheet offers the store instead).
     */
    fun openIn(app: HandoffApp, uri: String?, web: String?): HandoffTarget = when (app) {
        HandoffApp.NAVI -> open(HandoffLinksDto(navigator = uri), walk = false)
        HandoffApp.MAPS -> open(HandoffLinksDto(maps = uri, web = web), walk = true)
        HandoffApp.GOOGLE -> open(HandoffLinksDto(web = web), walk = true)
    }

    /** «Установить из магазина приложений». */
    fun openStore(app: HandoffApp) = Unit
}

/**
 * The hand-off apps of the S4 sheet (5.13 §5): [MAPS] Яндекс Карты and [GOOGLE] Google Карты take every point of the
 * day (CEO 29.10); [NAVI] Яндекс Навигатор takes one point from us, so it only goes to the next point.
 */
enum class HandoffApp { MAPS, GOOGLE, NAVI }

/** The sheet row / launcher app of a maps app. */
val app.verst.core.model.MapsApp.handoffApp: HandoffApp
    get() = when (this) {
        app.verst.core.model.MapsApp.YANDEX -> HandoffApp.MAPS
        app.verst.core.model.MapsApp.GOOGLE -> HandoffApp.GOOGLE
    }

/**
 * Where the phone is now, ISO 3166 alpha-2 (CEO 29.10: TelephonyManager network → SIM → the system locale in the
 * app); null = unknown. An interface so unit tests can fake the country.
 */
fun interface CountrySource {
    fun country(): String?
}

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
data class AgeGate(val preset: String? = null, val interest: String? = null, val thenBuild: Boolean = false)

/** 5.12 §2 address search state under the ОТКУДА / КУДА field. */
/**
 * [Failed]: online, but the service failed (timeout, 5xx, garbage, breaker) → `addr_failed` «Не получилось найти
 * адрес — попробуйте ещё раз» (5.5 §10.9, S4-QA P1-02); «уточним при интернете» is for [Offline] only.
 */
enum class AddressState { Idle, Searching, Done, None, Offline, Failed }

/** 5.10 «СКОЛЬКО ГУЛЯЕМ» chips, minutes. */
val WalkDurations = listOf(120, 240, 360, 480)

/** S4 (ADR-0015 §6): the dog preset; shown first, and only with the dog in the walk's crew. */
const val DOG_WALK = "dog_walk"

/** 5.10 §10 step 4: preset order (unknown presets after these, «Свой маршрут» last). */
val CityPresetOrder = listOf(DOG_WALK, "overview", "museums", "ryumochnye", "beer", "custom")

/** How a walk is requested (5.11 §10.2): it decides what a `NOT_ENOUGH_POIS` does. */
enum class WalkBuild { GO, FILTER, OTHER, REMOVE }

/**
 * `NOT_ENOUGH_POIS` for the request ([durationMin], [unlimited]) with the engine's verified suggestions. CEO 29.10:
 * [noData] — the engine's `reason: "no_data"`: our catalogue has no such places in this town (a gap of our base, not
 * a small town); the plate then says the engine's [messageRu] and offers other walks only.
 */
data class WalkFew(
    val durationMin: Int?,
    val unlimited: Boolean,
    val suggestions: List<app.verst.core.model.dto.WalkSuggestion>,
    val count: Int?,
    val noData: Boolean = false,
    val messageRu: String? = null,
) {
    companion object {
        /** The plate state of a `NOT_ENOUGH_POIS` [e] answering a request for [durationMin] / [unlimited]. */
        fun of(durationMin: Int?, unlimited: Boolean, e: app.verst.core.model.dto.EngineErrorDto): WalkFew = if (e.isNoData) {
            // a longer walk or the removed places back would not find what we never loaded: other walks only
            WalkFew(durationMin, unlimited, e.walkSuggestions.filter { it.preset != null }, e.count, noData = true, messageRu = e.messageRu)
        } else {
            WalkFew(durationMin, unlimited, e.walkSuggestions, e.count)
        }
    }
}

/** The picker sheets of 5.10 (prefs) and 5.11 (filter bar). */
enum class CityPicker { DURATION, PRESET, CREW, BUDGET, PACE }

/**
 * The R1 local links as an ADR-0014 hand-off (the fallback when the engine call fails). The points carry their roles
 * like the engine's (`origin` only when the route does not start at the phone), so Google Карты get the same route.
 */
fun NaviHandoff.toDto(day: Int?, mode: String = "car"): HandoffDto {
    val pts = points.mapIndexed { i, p ->
        val role = when {
            i == 0 && !fromHere && points.size > 1 -> "origin"
            i == points.lastIndex -> "destination"
            else -> "via"
        }
        app.verst.core.model.dto.HandoffPointDto(p.lat, p.lon, role = role)
    }
    return HandoffDto(mode, day, listOf(HandoffPartDto(1, pts, HandoffLinksDto(navi, mapsApp, web))), truncated = false)
}

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
