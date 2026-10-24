package app.verst

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import app.verst.platform.IntentHandoffLauncher
import app.verst.platform.openAppSettings
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.reducedMotion
import app.verst.feature.common.NaviDialog
import app.verst.feature.common.PlateToast
import app.verst.feature.common.toastText
import app.verst.feature.debug.DebugScreen
import app.verst.feature.exit.ExitActions
import app.verst.feature.exit.ExitScreen
import app.verst.feature.exit.ExitUi
import app.verst.core.ui.R as UiR
import app.verst.core.model.RuFormat
import app.verst.core.model.SavedTrips
import app.verst.core.model.dto.StopDto
import app.verst.engine.EngineHost
import app.verst.feature.drive.DriveScreen
import app.verst.feature.instruments.InstrumentsActions
import app.verst.feature.instruments.InstrumentsScreen
import app.verst.feature.instruments.InstrumentsUi
import app.verst.feature.navigator.NavigatorScreen
import app.verst.feature.navigator.NavigatorUi
import app.verst.feature.navigator.LocationActions
import app.verst.feature.road.RoadActions
import app.verst.feature.road.RoadFocus
import app.verst.feature.road.RoadScreen
import app.verst.feature.road.RoadUi
import app.verst.feature.waybill.WaybillActions
import app.verst.feature.waybill.WaybillScreen
import app.verst.feature.waybill.WaybillUi
import app.verst.feature.windshield.TripsActions
import app.verst.feature.windshield.WindshieldScreen
import app.verst.feature.windshield.WindshieldUi
import app.verst.nav.Route
import app.verst.nav.VerstFlow
import java.util.Locale

/** The single activity: Windshield → (Navigator) → Instruments → Drive → Road ahead (DEV-SLICE). */
class MainActivity : ComponentActivity() {
    private val flow get() = (application as VerstApp).flow
    private val launcher by lazy { IntentHandoffLauncher(this) }

    /** S3-R1: the system location dialog; «don't ask again» = denied without a rationale to show. */
    private val locationPermission = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { res ->
        val granted = res.values.any { it }
        val blocked = !granted && !shouldShowRequestPermissionRationale(Manifest.permission.ACCESS_COARSE_LOCATION)
        flow.onLocationPermission(granted, blocked)
    }

    /** The app is Russian-only: plurals and formats follow Russian rules whatever the phone's language is. */
    override fun attachBaseContext(newBase: Context) {
        val config = Configuration(newBase.resources.configuration).apply { setLocale(Locale.forLanguageTag("ru-RU")) }
        super.attachBaseContext(newBase.createConfigurationContext(config))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // S-02: transparent bars with light icons on the dark UI (the scene/dashboard draw behind them).
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
        )
        super.onCreate(savedInstanceState)
        // S3-R1: activity-bound platform hooks (cleared in onDestroy so the app-scoped flow never leaks us).
        flow.handoffLauncher = launcher
        flow.askLocationPermission = { locationPermission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)) }
        flow.openAppSettings = { openAppSettings(this) }
        Log.i(EngineHost.TAG, "build ${BuildConfig.BUILD_NUMBER} ${BuildConfig.GIT_SHA}")
        setContent { VerstRoot(flow) }
    }

    override fun onDestroy() {
        val f = flow
        if (f.handoffLauncher === launcher) {
            f.handoffLauncher = null
            f.askLocationPermission = null
            f.openAppSettings = null
        }
        super.onDestroy()
    }
}

/** The shared text of the mock build: the engine's share text + `mock_share_note` (release review P0-1). */
fun mockShareText(context: Context, engineText: String): String =
    engineText.trimEnd() + "\n\n" + context.getString(app.verst.core.ui.R.string.mock_share_note)

/** Android share sheet with the engine's share text (5.5 T2, 5.6 K2), marked as demo data. */
private fun share(context: Context, text: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, mockShareText(context, text))
    context.startActivity(Intent.createChooser(send, null).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

@Composable
fun VerstRoot(flow: VerstFlow) {
    val context = LocalContext.current
    val reduced = remember { reducedMotion(context) }
    CompositionLocalProvider(LocalReducedMotion provides reduced) {
        Box(Modifier.fillMaxSize()) {
            Screens(flow, context)
            Overlays(flow)
        }
    }
}

/** Dialogs and the Windshield toast that are not owned by one screen (D-1 delete, 5.5 §4 limit). */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.Overlays(flow: VerstFlow) {
    val t = flow.toast
    if (flow.top == Route.Windshield && t != null) {
        // F-02: above the dashboard crest (324 dp dashboard + 16), never over the caption or ПОЕХАЛИ.
        PlateToast(toastText(t), bottom = 340.dp, action = if (flow.canUndoDelete) stringResource(UiR.string.common_undo) else null, onAction = flow::undoDelete)
    }
    if (flow.top == Route.Navigator && t != null) {
        // S3-R1 location toasts above the Navigator caption row (start button 120 + 16).
        val settings = t == app.verst.nav.Toast.LocationBlocked
        PlateToast(
            toastText(t), bottom = 150.dp,
            action = if (settings) stringResource(UiR.string.windshield_location_settings) else null, onAction = flow::toastSettings,
        )
    }
    flow.deleteAsk?.let { d ->
        NaviDialog(
            stringResource(UiR.string.trips_delete_title, d.title), stringResource(UiR.string.trips_delete_body),
            stringResource(UiR.string.trips_delete_yes), stringResource(UiR.string.trips_delete_no), "delete",
            flow::confirmDelete, flow::cancelDelete,
        )
    }
    if (flow.limitDialog) {
        NaviDialog(
            stringResource(UiR.string.common_storage_full_title), stringResource(UiR.string.common_storage_full_body),
            stringResource(UiR.string.common_storage_full_open), stringResource(UiR.string.common_dialog_cancel), "limit",
            flow::limitToTrips, flow::dismissLimit,
        )
    }
}

@Composable
private fun Screens(flow: VerstFlow, context: Context) {
    val overlayOpen = flow.replace != null || flow.tripsSheet || flow.partnerOpen || flow.bookedDialog || flow.deleteAsk != null || flow.limitDialog || flow.resetAsk
    BackHandler(enabled = flow.stack.size > 1 || overlayOpen) { flow.back() }
    when (flow.top) {
        Route.Windshield -> WindshieldScreen(
            WindshieldUi(
                flow.origin.label, flow.windshield, flow.selectedRoute, flow.adults, flow.children, flow.dog,
                trips = SavedTrips.ordered(flow.saved), tripsSheet = flow.tripsSheet, originGen = flow.originGen, routeKm = flow.routeKm,
            ),
            onSelect = { flow.selectedRoute = it },
            onStart = flow::openReadyRoute,
            onNavigator = flow::openNavigator,
            onRetry = flow::retryWindshield,
            trips = object : TripsActions {
                override fun open() = flow.openTrips()
                override fun close() {
                    flow.back()
                }
                override fun pick(id: String) = flow.openSaved(id)
                override fun delete(id: String) = flow.askDelete(id)
            },
            onDebug = flow::openDebug,
        )
        Route.Navigator -> NavigatorScreen(
            NavigatorUi(
                flow.origin, flow.editingFrom, flow.query, flow.searching, flow.suggestions, flow.popular,
                flow.suggestFailed, flow.destination, flow.routeError,
                rowKm = flow.rowKm.toMap(),
                tripKm = flow.figures?.figures?.km,
                tripErrorCode = flow.draftError?.code,
                gps = flow.gps,
                locationPrompt = flow.locationPrompt,
            ),
            onBack = { flow.back() },
            onQuery = flow::updateQuery,
            onPick = flow::pick,
            onEditFrom = flow::startEditFrom,
            onStart = flow::openInstrumentsFree,
            location = object : LocationActions {
                override fun allow() = flow.allowLocation()
                override fun deny() = flow.denyLocation()
                override fun myLocation() = flow.useMyLocation()
            },
        )
        Route.Instruments -> InstrumentsScreen(
            InstrumentsUi(
                title = flow.tripTitle,
                origin = flow.origin.label,
                roundTrip = flow.readyRoute?.roundTrip ?: false,
                tripKm = flow.figures?.figures?.km,
                frontAdult = flow.frontAdult,
                back = flow.seats.toList(),
                dog = flow.dog,
                adults = flow.adults,
                children = flow.children,
                dailyKm = flow.dailyKm,
                budgetIndex = flow.budgetIndex,
                mood = flow.mood,
                days = flow.figures?.figures?.days,
                originGen = flow.originGen,
            ),
            object : InstrumentsActions {
                override fun back() {
                    flow.back()
                }
                override fun seat(i: Int) = flow.cycleSeat(i)
                override fun front() {
                    flow.frontAdult = !flow.frontAdult
                }
                override fun dog() {
                    flow.dog = !flow.dog
                }
                override fun km(delta: Int) = flow.stepKm(delta)
                override fun budget(delta: Int) = flow.stepBudget(delta)
                override fun mood(m: app.verst.core.model.Mood) = flow.pickMood(m)
                override fun go() = flow.go()
            },
        )
        Route.Drive -> DriveScreen(
            flow.drive,
            // The engine figure of this request (estimate = plan); «—» only if ПОЕХАЛИ beat the first estimate.
            kmLabel = flow.figures?.figures?.km?.let { RuFormat.thousands(it) } ?: "—",
            action = { flow.driveAction(it.code) },
            onCancel = { flow.back() },
            onDone = flow::openRoad,
            onErrorAction = flow::onDriveError,
        )
        Route.Road -> {
            val r = flow.result
            if (r == null) {
                // Never blank: without a trip the Road screen is not reachable; go back.
                LaunchedEffect(Unit) { flow.back() }
            } else {
                RoadScreen(
                    RoadUi(r.trip, flow.resultBearing, flow.openedFromSaved, flow.savedCurrent, flow.replace, flow.toast, flow.canUndo,
                        r.trip.daysList.flatMap { it.stops }.filter { flow.isBooked(it.id) }.map { it.id }.toSet(), r.townPrepRu,
                        online = flow.connectivity.online,
                        stopMenu = flow.stopMenu, navigatorInstalled = flow.navigatorInstalled,
                        focus = RoadFocus(flow.roadFocusId, flow.roadTopId, flow.roadFocusSeq),
                    ),
                    object : RoadActions {
                        override fun back() {
                            flow.back()
                        }
                        override fun waybill() = flow.openWaybill()
                        override fun save() = flow.save()
                        override fun share() = share(context, r.shareText)
                        override fun replace(stop: StopDto) = flow.openReplace(stop)
                        override fun pick(altId: String?) = flow.pickAlternative(altId)
                        override fun confirmReplace() = flow.confirmReplace()
                        override fun closeReplace() = flow.closeReplace()
                        override fun undo() = flow.undo()
                        override fun hotel(stopId: String) = flow.openExit(stopId)
                        override fun dayNavigator(day: Int) = flow.openDayInNavigator(day)
                        override fun stopMenu(stop: StopDto) = flow.openStopMenu(stop)
                        override fun closeStopMenu() = flow.closeStopMenu()
                        override fun navigatorFromStop() = flow.navigatorFromStop()
                        override fun stopMenuReplace() = flow.stopMenuReplace()
                        override fun topRow(id: String?) = flow.roadTop(id)
                        override fun focusShown() = flow.roadFocusShown()
                    },
                )
            }
        }
        Route.Exit -> {
            val r = flow.result
            val stop = r?.trip?.daysList?.flatMap { it.stops }?.firstOrNull { it.id == flow.exitStopId }
            if (r == null || stop == null) {
                LaunchedEffect(Unit) { flow.back() }
            } else {
                val nights = r.trip.daysList.flatMap { it.stops }.filter { it.kind == "overnight" }
                ExitScreen(
                    ExitUi(
                        r.trip, stop, nights.indexOfFirst { it.id == stop.id } + 1, nights.size, flow.booked[stop.id],
                        !flow.connectivity.online, r.townPrepRu[stop.townId] ?: stop.name, flow.partnerOpen, flow.bookedDialog, flow.toast,
                        canUndo = flow.toast is app.verst.nav.Toast.Booked,
                    ),
                    object : ExitActions {
                        override fun back() {
                            flow.back()
                        }
                        override fun select(placeId: String) = flow.selectHotel(stop.id, placeId)
                        override fun book() = flow.book()
                        override fun closePartner() = flow.closePartner()
                        override fun answer(booked: Boolean) = flow.answerBooked(booked)
                        override fun needInternet() = flow.needInternet()
                        override fun undoBooking() = flow.undoBooking()
                    },
                )
            }
        }
        Route.Debug -> DebugScreen(flow)
        Route.Waybill -> {
            val r = flow.result
            if (r == null) {
                LaunchedEffect(Unit) { flow.back() }
            } else {
                WaybillScreen(
                    WaybillUi(
                        r.trip, flow.waybillNumber, flow.savedCurrent, flow.expandedLine, flow.costBusy,
                        r.pricesMonthRu, r.pricesYear, flow.toast, stamp = remember(flow.tripSession) { flow.stampOnce() },
                    ),
                    object : WaybillActions {
                        override fun back() {
                            flow.back()
                        }
                        override fun toggleLine(key: String) = flow.toggleLine(key)
                        override fun toggleReserve() = flow.toggleReserve()
                        override fun save() = flow.save()
                        override fun share() = share(context, r.shareText)
                    },
                )
            }
        }
    }
}
