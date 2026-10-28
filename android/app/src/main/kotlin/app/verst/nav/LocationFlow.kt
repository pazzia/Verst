package app.verst.nav

import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.core.model.dto.SuggestionDto
import kotlinx.coroutines.launch

/** HYG-02: GPS origin (5.12) and the address search (5.12 §2) — `VerstFlow` extensions (the state stays in the class). */

// ---- location (5.12)

internal fun VerstFlow.onNavigatorOpened() {
    when {
        debugMockLocation != null -> if (!originFromGps || gps != GpsState.On) locate()
        locator?.granted() == true -> if (originFromGps || !locationAsked) locate()
        !locationAsked -> locationSheet = true
    }
}

/** «ВЫ: …» on the Windshield, or the first «По городу»: the rationale once, else locate again. */
fun VerstFlow.askLocation() {
    when {
        debugMockLocation != null || locator?.granted() == true -> locate()
        !locationAsked -> locationSheet = true
        else -> askLocationPermission?.invoke(false) ?: showToast(Toast.LocationBlocked)
    }
}

/** Rationale «Разрешить» → the system dialog for coarse location. */
fun VerstFlow.allowLocation() {
    locationSheet = false
    locationAsked = true
    val ask = askLocationPermission
    if (debugMockLocation != null || locator?.granted() == true) locate() else if (ask != null) ask(false) else showToast(Toast.LocationDenied(origin.label))
}

/** Rationale «Выберу сам» → the ОТКУДА input. */
fun VerstFlow.manualLocation() {
    locationSheet = false
    locationAsked = true
    if (top == Route.Navigator) startEditFrom()
}

/** Kept for R1 callers: «Не разрешать» = «Выберу сам» without the input. */
fun VerstFlow.denyLocation() {
    locationSheet = false
    locationAsked = true
    showToast(Toast.LocationDenied(origin.label))
}

/** «Точнее» → the fine-location dialog. */
fun VerstFlow.preciseLocation() {
    askLocationPermission?.invoke(true)
}

/** The system dialog's answer; [blocked] = «don't ask again» (only the settings can allow it now). */
fun VerstFlow.onLocationPermission(granted: Boolean, blocked: Boolean) {
    if (granted) locate() else showToast(if (blocked) Toast.LocationBlocked else Toast.LocationDenied(origin.label))
}

/** «Моё местоположение» in ОТКУДА. */
fun VerstFlow.useMyLocation() {
    locationAsked = true
    locationSheet = false
    when {
        debugMockLocation != null || locator?.granted() == true -> locate(fromRow = true)
        askLocationPermission != null -> askLocationPermission?.invoke(false)
        else -> showToast(Toast.LocationTimeout(origin.label))
    }
}

/** The toast action: «Настройки» / «Включить» / «Выбрать». */
fun VerstFlow.toastAction() {
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
fun VerstFlow.toastSettings() = toastAction()

/** The phone's position → `geo_nearest` (the catalogue town) → the origin; online also the street address. */
fun VerstFlow.locate(fromRow: Boolean = false) {
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
            val street = (address.reverse(p.lat, p.lon) as? app.verst.data.net.AddressResult.Ok)?.value
                ?: (addressFallback?.reverse(p.lat, p.lon) as? app.verst.data.net.AddressResult.Ok)?.value
            if (street != null && origin == o) originAddress = street
        }
    }
}

/** The engine's town within 30 km (`reverse` + its `suggest` row), else the nearest popular town. */
internal suspend fun VerstFlow.nearestTown(p: GeoPoint): SuggestionDto? {
    val name = (gateway.reverse(p) as? EngineResult.Ok)?.value?.name
    if (name != null) {
        val row = (gateway.suggest(name, p) as? EngineResult.Ok)?.value?.firstOrNull { it.name == name && it.nameGenRu != null }
        if (row != null) return row
    }
    val towns = (gateway.popular() as? EngineResult.Ok)?.value.orEmpty().filter { it.nameGenRu != null }
    return towns.minByOrNull { TownMath.km(p.lat, p.lon, it.lat, it.lon) }
}

// ---- addresses (5.12 §2)

/**
 * CEO 29.10: «Найти адрес» is offered for any query of 3+ characters — a bare street («Ленина», «улица Мира») is
 * the main thing people type. It comes first when the query [looksLikeAddress] or no town / place matched.
 */
fun VerstFlow.addressOffered(q: String): Boolean = looksLikeAddress(q) || q.trim().length >= 3

/** The query reads as an address: a digit, a comma or a street word («ул», «улица», «проспект», «д.»…). */
fun VerstFlow.looksLikeAddress(q: String): Boolean {
    val t = q.trim().lowercase()
    if (t.length < 3) return false
    return t.any { it.isDigit() } || t.contains(',') || ADDRESS_WORDS.any { w -> Regex("(^|\\s)$w(\\s|\\.|$)").containsMatchIn(t) }
}

/** Explicit submit (the action row or the IME «Найти»): one Nominatim request, never per keystroke. */
fun VerstFlow.submitAddress() {
    val q = query.trim()
    if (!addressOffered(q)) return
    if (!connectivity.online) {
        addressState = AddressState.Offline
        return
    }
    addressJob?.cancel()
    addressState = AddressState.Searching
    addressJob = scope.launch {
        var r = address.search(q, origin)
        // CEO 29.10: OSM has no such street / house here, or Nominatim is unreachable → the phone's geocoder
        if (r is app.verst.data.net.AddressResult.Failed || (r as? app.verst.data.net.AddressResult.Ok)?.value?.isEmpty() == true) {
            val f = addressFallback?.search(q, origin)
            if (f is app.verst.data.net.AddressResult.Ok && f.value.isNotEmpty()) r = f
        }
        when (r) {
            is app.verst.data.net.AddressResult.Ok -> {
                addressResults = r.value
                addressState = if (r.value.isEmpty()) AddressState.None else AddressState.Done
                fetchRowKm(r.value)
            }
            app.verst.data.net.AddressResult.Offline -> addressState = AddressState.Offline
            is app.verst.data.net.AddressResult.Failed -> {
                // S4-QA P1-02: online and failed → the quiet «попробуйте ещё раз» (never an error screen);
                // gone offline meanwhile → the offline hint
                addressResults = emptyList()
                addressState = if (connectivity.online) AddressState.Failed else AddressState.Offline
            }
        }
    }
}

internal fun VerstFlow.clearAddresses() {
    addressJob?.cancel()
    addressResults = emptyList()
    addressState = AddressState.Idle
}

private val ADDRESS_WORDS = listOf(
    "ул", "улица", "пр", "пр-т", "просп", "проспект", "пер", "переулок", "д", "дом", "наб", "набережная", "пл",
    "площадь", "ш", "шоссе", "б-р", "бульвар", "проезд", "туп", "тупик", "мкр", "микрорайон", "корп", "стр", "кв",
)
