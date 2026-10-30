package app.verst.nav

import app.verst.core.model.EngineResult
import app.verst.core.model.GeoPoint
import app.verst.core.model.SavedTripDto
import app.verst.core.model.SavedTrips
import app.verst.core.model.NaviLinks
import app.verst.core.model.LatLon
import app.verst.core.model.HandoffArgs
import app.verst.core.model.WalkRequest
import app.verst.core.model.EngineJson
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.HandoffDto
import java.util.UUID
import app.verst.core.ui.theme.DesignTokens
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** HYG-02: «По городу» (5.10 / 5.11): presets, the walk and its edits — `VerstFlow` extensions (the state stays in the class). */

// ---- «По городу» (5.10)

/** Windshield «По городу пешком» → 5.10; the start = the GPS origin or the last chosen point. */
fun VerstFlow.openCity() {
    walkExclude.clear()
    cityError = null
    walkFew = null
    walkOtherNone = false
    cityPicker = null
    push(Route.City)
    if (!locationAsked && locator?.granted() != true && debugMockLocation == null) locationSheet = true
    loadCityPresets()
}

val VerstFlow.cityStartPoint: GeoPoint get() = cityStart ?: origin

fun VerstFlow.loadCityPresets() {
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
fun VerstFlow.visibleCityPresets(): List<app.verst.core.model.dto.CityPresetDto> {
    val all = cityPresets?.presets.orEmpty().filter { it.available && (it.preset != DOG_WALK || cityDog) }
    return all.sortedBy { CityPresetOrder.indexOf(it.preset).let { i -> if (i < 0) 90 else i } }
}

/**
 * CEO 29.10: the presets the engine could not offer because our catalogue has no such places in this town
 * (`noData`) — 5.10 shows them disabled with the engine's reason; other unavailable presets stay hidden.
 */
fun VerstFlow.noDataCityPresets(): List<app.verst.core.model.dto.CityPresetDto> =
    cityPresets?.presets.orEmpty().filter { !it.available && it.noData && (it.preset != DOG_WALK || cityDog) }
        .sortedBy { CityPresetOrder.indexOf(it.preset).let { i -> if (i < 0) 90 else i } }

/** A preset's defaults fill only what the user has not chosen (S4: custom values persist). */
internal fun VerstFlow.selectDefaults(p: app.verst.core.model.dto.CityPresetDto) {
    cityPreset = p.preset
    if (!cityDurationTouched) cityDurationMin = p.defaultDurationMin
    if (!cityPaceTouched) p.defaultPace?.let { cityPace = it }
}

/** «изменить» on the start field → the ОТКУДА search; the pick comes back here. */
fun VerstFlow.cityChangeStart() {
    cityPickingStart = true
    openNavigator()
    startEditFrom()
}

/**
 * A preset plate: 18+ asks «Вам есть 18?» every time (S4: children never block — the walk carries a warning);
 * «Свой маршрут» opens the sheet with the user's own values.
 */
fun VerstFlow.selectCityPreset(preset: String) {
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
fun VerstFlow.answerAge(yes: Boolean) {
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
fun VerstFlow.setCityDuration(min: Int?) {
    cityDurationTouched = true
    if (cityDurationMin == min) return
    cityDurationMin = min
    onWalkInputChanged()
}

fun VerstFlow.toggleCityInterest(i: String) {
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

fun VerstFlow.pickCityPace(p: String) {
    cityPaceTouched = true
    if (cityPace == p) return
    cityPace = p
    onWalkInputChanged()
}

fun VerstFlow.pickCityBudget(rub: Int?) {
    if (cityBudget == rub) return
    cityBudget = rub
    onWalkInputChanged()
}

fun VerstFlow.toggleCityReturn() {
    cityReturn = !cityReturn
    onWalkInputChanged()
}

fun VerstFlow.pickCityAdults(n: Int) {
    val v = n.coerceIn(1, 9)
    if (v == cityAdults) return
    cityAdults = v
    onWalkInputChanged()
}

fun VerstFlow.pickCityChildren(n: Int) {
    val v = n.coerceIn(0, 9)
    if (v == cityChildren) return
    cityChildren = v
    onWalkInputChanged()
}

/** The dog toggle; «Собака останется дома» = off (a dog walk then falls back to the overview). */
fun VerstFlow.pickCityDog(on: Boolean) {
    if (on == cityDog) return
    cityDog = on
    if (!on && cityPreset == DOG_WALK) visibleCityPresets().firstOrNull { !it.adultOnly }?.let { selectDefaults(it) }
    onWalkInputChanged()
}

fun VerstFlow.closeCityCustom() {
    cityCustomSheet = false
}

fun VerstFlow.openCityPicker(p: CityPicker?) {
    cityPicker = p
}

/** «Собрать прогулку» in the custom sheet. */
fun VerstFlow.buildCustomWalk() {
    if (cityInterests.isEmpty()) cityInterests += "history"
    cityCustomSheet = false
    buildWalk()
}

fun VerstFlow.walkRequest(): WalkRequest = WalkRequest(
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
internal fun VerstFlow.onWalkInputChanged() {
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
fun VerstFlow.buildWalk(mode: WalkBuild = WalkBuild.GO) {
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
                        // CEO 29.10: `reason: "no_data"` → the engine's sentence, no «longer walk» suggestions
                        walkFew = WalkFew.of(req.durationMin, req.unlimited, r.error)
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
fun VerstFlow.otherWalk() {
    val w = walk ?: return
    if (walkOtherNone || walkBuilding) return
    lastOtherAdded = w.stops.mapNotNull { it.poiId }.filter { it !in walkExclude }
    walkExclude += lastOtherAdded
    buildWalk(WalkBuild.OTHER)
}

/** A verified `NOT_ENOUGH_POIS` suggestion → apply it and build again (never an app-made guess). */
fun VerstFlow.applyWalkSuggestion(sg: app.verst.core.model.dto.WalkSuggestion) {
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
fun VerstFlow.retryWalk() {
    buildWalk(if (top == Route.Walk) WalkBuild.FILTER else WalkBuild.GO)
}

internal fun VerstFlow.loadWalkHandoff() {
    val w = walk ?: return
    scope.launch {
        val h = engineHandoff(w.json, HandoffArgs.walk(handoffSigner?.client))
        if (walk?.id == w.id) walkHandoff = h ?: localWalkHandoff(w)
    }
}

internal fun VerstFlow.localWalkHandoff(w: app.verst.core.model.dto.WalkRouteDto): HandoffDto {
    val pts = listOf(app.verst.core.model.LatLon(w.start.lat, w.start.lon)) + w.stops.map { app.verst.core.model.LatLon(it.lat, it.lon) } +
        listOfNotNull(w.finish?.let { app.verst.core.model.LatLon(it.lat, it.lon) })
    return NaviLinks.walking(pts).toDto(null, mode = "walk")
}

/** «Вести пешком» (part [index] of a split walk): the preferred maps app (CEO 29.10), walking mode. */
fun VerstFlow.walkHandoffGo(index: Int = 1) {
    val h = walkHandoff ?: walk?.let { localWalkHandoff(it) } ?: return
    if (h.parts.isEmpty()) return
    launchApp(preferredMaps, h, next = false, walk = true, partIndex = index)
    walkFocusSeq += 1
}

/** Save the walk to «Мои поездки» (schema 2, `kind = walk`). */
fun VerstFlow.saveWalk() {
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
fun VerstFlow.walkShareText(): String {
    val w = walk ?: return ""
    val lines = mutableListOf(w.titleRu)
    w.stops.forEachIndexed { i, s -> lines += "${i + 1}. ${s.nameRu}" + (s.arriveAt?.let { " · " + (RuFormat.clock(it) ?: "") } ?: "") }
    // CEO 29.10: unknown café prices are never «≈ 0 ₽»; a sum without them says so
    val money = when {
        w.priceUnknown && w.cost.totalRub <= 0 -> "цены в кафе не указаны"
        w.priceUnknown -> "≈ ${app.verst.settings.AppPrefs.money(w.cost.totalRub)} на всех без кафе"
        else -> "≈ ${app.verst.settings.AppPrefs.money(w.cost.totalRub)} на всех"
    }
    lines += "$money · ≈ ${w.walkKm} км пешком"
    w.responsibleNoteRu?.let { lines += it }
    return lines.joinToString("\n")
}

/** «Мои поездки» → a saved walk. */
internal fun VerstFlow.openSavedWalk(t: SavedTripDto) {
    val w = t.walk?.let { runCatching { EngineJson.walk(it.toString()) }.getOrNull() } ?: return
    walk = w
    savedWalkId = t.id
    walkHandoff = null
    tripsSheet = false
    while (stack.size > 1) stack.removeAt(stack.lastIndex)
    push(Route.Walk)
    loadWalkHandoff()
}
