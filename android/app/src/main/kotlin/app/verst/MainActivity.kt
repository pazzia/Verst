package app.verst

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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.platform.LocalContext
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
import app.verst.feature.road.RoadActions
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
        val flow = (application as VerstApp).flow
        Log.i(EngineHost.TAG, "build ${BuildConfig.BUILD_NUMBER} ${BuildConfig.GIT_SHA}")
        setContent { VerstRoot(flow) }
    }
}

/** Android share sheet with the engine's share text (5.5 T2, 5.6 K2). */
private fun share(context: Context, text: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
    context.startActivity(Intent.createChooser(send, null).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

@Composable
fun VerstRoot(flow: VerstFlow) {
    val context = LocalContext.current
    BackHandler(enabled = flow.stack.size > 1 || flow.replace != null || flow.tripsSheet) { flow.back() }
    when (flow.top) {
        Route.Windshield -> WindshieldScreen(
            WindshieldUi(
                flow.origin.label, flow.windshield, flow.selectedRoute, flow.adults, flow.children, flow.dog,
                trips = SavedTrips.ordered(flow.saved), tripsSheet = flow.tripsSheet,
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
            },
        )
        Route.Navigator -> NavigatorScreen(
            NavigatorUi(
                flow.origin, flow.editingFrom, flow.query, flow.searching, flow.suggestions, flow.popular,
                flow.suggestFailed, flow.destination, flow.routeError,
                rowKm = flow.rowKm.toMap(),
                tripKm = flow.figures?.figures?.km,
                tripErrorCode = flow.draftError?.code,
            ),
            onBack = { flow.back() },
            onQuery = flow::updateQuery,
            onPick = flow::pick,
            onEditFrom = flow::startEditFrom,
            onStart = flow::openInstrumentsFree,
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
                    RoadUi(r.trip, flow.resultBearing, flow.openedFromSaved, flow.savedCurrent, flow.replace, flow.toast, flow.canUndo),
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
                    },
                )
            }
        }
        Route.Waybill -> {
            val r = flow.result
            if (r == null) {
                LaunchedEffect(Unit) { flow.back() }
            } else {
                WaybillScreen(
                    WaybillUi(
                        r.trip, flow.waybillNumber, flow.savedCurrent, flow.expandedLine, flow.costBusy,
                        r.pricesMonthRu, r.pricesYear, flow.toast,
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
