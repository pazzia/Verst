package app.verst

import android.content.Context
import android.content.res.Configuration
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import app.verst.core.model.RuFormat
import app.verst.engine.EngineHost
import app.verst.feature.drive.DriveScreen
import app.verst.feature.instruments.InstrumentsActions
import app.verst.feature.instruments.InstrumentsScreen
import app.verst.feature.instruments.InstrumentsUi
import app.verst.feature.navigator.NavigatorScreen
import app.verst.feature.navigator.NavigatorUi
import app.verst.feature.road.RoadScreen
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
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val flow = (application as VerstApp).flow
        Log.i(EngineHost.TAG, "build ${BuildConfig.BUILD_NUMBER} ${BuildConfig.GIT_SHA}")
        setContent { VerstRoot(flow) }
    }
}

@Composable
fun VerstRoot(flow: VerstFlow) {
    BackHandler(enabled = flow.stack.size > 1) { flow.back() }
    when (flow.top) {
        Route.Windshield -> WindshieldScreen(
            WindshieldUi(flow.origin.label, flow.windshield, flow.selectedRoute, flow.adults, flow.children, flow.dog),
            onSelect = { flow.selectedRoute = it },
            onStart = flow::openReadyRoute,
            onNavigator = flow::openNavigator,
            onRetry = flow::retryWindshield,
        )
        Route.Navigator -> NavigatorScreen(
            NavigatorUi(
                flow.origin, flow.editingFrom, flow.query, flow.searching, flow.suggestions, flow.popular,
                flow.suggestFailed, flow.destination, flow.routeError,
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
                tripKm = flow.tripKm,
                frontAdult = flow.frontAdult,
                back = flow.seats.toList(),
                dog = flow.dog,
                adults = flow.adults,
                children = flow.children,
                dailyKm = flow.dailyKm,
                budgetIndex = flow.budgetIndex,
                mood = flow.mood,
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
            kmLabel = flow.readyRoute?.let { RuFormat.thousands(it.kmTotal) } ?: "≈ ${RuFormat.thousands(flow.tripKm)}",
            action = { flow.driveAction(it.code) },
            onCancel = { flow.back() },
            onDone = flow::openRoad,
            onErrorAction = flow::onDriveError,
        )
        Route.Road -> {
            val trip = flow.result?.trip
            if (trip == null) {
                // Never blank: without a trip the Road screen is not reachable; go back to Instruments.
                LaunchedEffect(Unit) { flow.back() }
            } else {
                RoadScreen(trip, flow.readyRoute?.bearing8 ?: "N", onBack = { flow.back() })
            }
        }
    }
}
