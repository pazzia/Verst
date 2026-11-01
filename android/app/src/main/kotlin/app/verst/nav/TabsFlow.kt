package app.verst.nav

/**
 * Fork camper-ui (CEO 31.10): the five tabs of the «Кемпер-гид» bottom bar. A tab never invents state: it pops back
 * to a screen that is already on the stack, or opens one the way its own button does (the same flow functions, so
 * analytics, estimates and the location question behave as before). Popping goes through [VerstFlow.back], so the
 * screens' own clean-up runs (a running plan is cancelled, the walk jobs stop).
 */
enum class AppTab { WINDSHIELD, INSTRUMENTS, ROAD, CITY, WAYBILL }

/** The tab a route belongs to; null for the routes that take their parent's tab (Drive, Exit, NoFit, Settings, Debug). */
fun Route.tab(): AppTab? = when (this) {
    Route.Windshield -> AppTab.WINDSHIELD
    Route.Navigator, Route.Instruments -> AppTab.INSTRUMENTS
    Route.Road -> AppTab.ROAD
    Route.Waybill -> AppTab.WAYBILL
    Route.City, Route.Walk -> AppTab.CITY
    Route.Drive, Route.Exit, Route.NoFit, Route.Settings, Route.Debug -> null
}

/** The highlighted tab: the top route's, else the nearest parent's on the stack. */
val VerstFlow.activeTab: AppTab
    get() = stack.asReversed().firstNotNullOfOrNull { it.tab() } ?: AppTab.WINDSHIELD

/** Дорога and Путевой need a built trip; the others are always available. */
fun VerstFlow.tabEnabled(tab: AppTab): Boolean = when (tab) {
    AppTab.ROAD, AppTab.WAYBILL -> result != null
    else -> true
}

/** A tab tapped in the bottom bar. */
fun VerstFlow.selectTab(tab: AppTab) {
    if (!tabEnabled(tab)) return
    when (tab) {
        AppTab.WINDSHIELD -> popToRoot()
        AppTab.INSTRUMENTS -> tabInstruments()
        AppTab.ROAD -> {
            if (popTo(Route.Road)) return
            popToRoot()
            openRoad()
        }
        AppTab.WAYBILL -> {
            if (popTo(Route.Waybill)) return
            if (!popTo(Route.Road)) {
                popToRoot()
                openRoad()
            }
            openWaybill()
        }
        AppTab.CITY -> {
            if (popTo(Route.City)) return
            popToRoot()
            openCity()
        }
    }
}

/** The header's gear: Settings on top of the current screen (once). */
fun VerstFlow.openSettingsFromHeader() {
    if (top != Route.Settings) openSettings()
}

/**
 * Приборы: back to Instruments when it is on the stack; else Instruments for the chosen ready route or destination;
 * else the Navigator (choose where to go first).
 */
private fun VerstFlow.tabInstruments() {
    if (popTo(Route.Instruments)) return
    val route = readyRoute
    when {
        route != null -> {
            popToRoot()
            readyRoute = route
            push(Route.Instruments)
        }
        destination != null -> {
            if (!popTo(Route.Navigator)) popToRoot()
            openInstrumentsFree()
            // abroad without the server: Instruments refuses; the Navigator explains why
            if (top != Route.Instruments && top != Route.Navigator) openNavigator()
        }
        else -> if (!popTo(Route.Navigator)) {
            popToRoot()
            openNavigator()
        }
    }
}

/** Back until [route] is on top; false (nothing popped) when it is not on the stack. */
private fun VerstFlow.popTo(route: Route): Boolean {
    if (route !in stack) return false
    var guard = 0
    while (top != route && stack.size > 1 && guard++ < MAX_POPS) {
        if (!back()) break
    }
    return top == route
}

/** Back to the Windshield (sheets close on the way). */
private fun VerstFlow.popToRoot() {
    var guard = 0
    while (stack.size > 1 && guard++ < MAX_POPS) {
        if (!back()) break
    }
}

private const val MAX_POPS = 64
