package app.verst.feature.windshield

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.SavedTripDto
import app.verst.core.model.dto.ReadyRouteDto
import app.verst.core.ui.R
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftChip
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftIconTile
import app.verst.core.ui.components.CraftSecondaryButton
import app.verst.core.ui.components.CraftSectionTitle
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.DashedDivider
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.PlaceholderPlate
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.arrowFor
import app.verst.core.ui.components.craftField
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.crewShort
import app.verst.nav.WindshieldData
import kotlinx.coroutines.withTimeoutOrNull
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

private const val SavedTripsWarn = app.verst.core.model.SavedTrips.WARN_FROM

/** Everything the Windshield draws (stateless; the caller maps `VerstFlow` into it). */
data class WindshieldUi(
    val origin: String,
    val data: WindshieldData,
    val selected: Int,
    val adults: Int,
    val children: Int,
    val dog: Boolean,
    /** Saved trips in D-1 order; the «Мои поездки» plate shows only when non-empty (W-27). */
    val trips: List<SavedTripDto> = emptyList(),
    val tripsSheet: Boolean = false,
    /** OI-39: the origin in the genitive from the engine («Москвы»); the nominative until it arrives. */
    val originGen: String = origin,
    /** F-01: engine km per ready route id (estimate for the current crew and pace); a placeholder until known. */
    val routeKm: Map<String, Int> = emptyMap(),
)

/** «Мои поездки» plate and the D-1 sheet. */
interface TripsActions {
    fun open()
    fun close()
    fun pick(id: String)
    fun delete(id: String)
}

private val NoTrips = object : TripsActions {
    override fun open() {}
    override fun close() {}
    override fun pick(id: String) {}
    override fun delete(id: String) {}
}

/**
 * 5.1 Windshield, camper-ui fork (mockup screen 1 «Лобовое»): a paper page with a column of craft cards — the crew
 * («Мой кемпер»), «Куда едем?» (→ Navigator), the ready routes near the origin, «По городу пешком» — and the
 * full-width ПОЕХАЛИ pinned under them. The header and the tab bar are drawn around it by MainActivity.
 */
@Composable
fun WindshieldScreen(
    ui: WindshieldUi,
    onSelect: (Int) -> Unit,
    onStart: () -> Unit,
    onNavigator: () -> Unit,
    onRetry: () -> Unit,
    trips: TripsActions = NoTrips,
    onDebug: () -> Unit = {},
    /** D-IR-20: settings (the gear on the crew card; the header carries one as well). */
    onSettings: () -> Unit = {},
    /** 5.10 «По городу · пешком» card; 5.12 a tap on «ВЫ: …» (locate). */
    onCity: () -> Unit = {},
    onYouAre: () -> Unit = {},
) {
    ScreenRoot(C.camper.page) {
        BoxWithConstraints(Modifier.matchParentSize()) {
            val windowH = maxHeight
            val routes = (ui.data as? WindshieldData.Routes)?.routes
            val selected = routes?.getOrNull(ui.selected)
            Column(Modifier.fillMaxSize()) {
                Column(
                    Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .verticalScroll(rememberScrollState())
                        // the gutter leaves room for the cards' hard shadow (3 × 4 dp) inside the scroll clip
                        .padding(horizontal = CraftDefaults.ScreenGutter, vertical = CraftDefaults.Gap),
                    verticalArrangement = Arrangement.spacedBy(CraftDefaults.Gap),
                ) {
                    // The crew is edited on the Instruments: with a route chosen, a tap opens them for that route.
                    CrewCard(ui.adults, ui.children, ui.dog, if (selected != null) onStart else null, onSettings)
                    NaviCard(ui.origin, ui.data is WindshieldData.NoRoutes, onNavigator, onDebug, onYouAre)
                    RoutesSection(ui, onSelect, onRetry, trips::open)
                    CityCard(ui.origin, onCity)
                }
                val goCd = if (selected != null) stringResource(R.string.cd_start_route, selected.title) else stringResource(R.string.cd_start_disabled_destination)
                CraftButton(
                    stringResource(R.string.common_go), onStart,
                    Modifier
                        .fillMaxWidth()
                        .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 4.dp, bottom = CraftDefaults.ScreenGutter)
                        .semantics { contentDescription = goCd }
                        .testTag("windshield.start"),
                    icon = R.drawable.ic_ui_compass,
                    enabled = selected != null,
                )
            }
            if (ui.tripsSheet && ui.trips.isNotEmpty()) TripsSheet(ui.trips, windowH, trips)
        }
    }
}

/**
 * «Мой кемпер / экипаж» (mockup): the van tile, the crew in words, the gear (settings), and one tile per traveller of
 * the current state (adults amber, children orange, the dog green). Clickable only when a ready route is chosen.
 */
@Composable
private fun CrewCard(adults: Int, children: Int, dog: Boolean, onEdit: (() -> Unit)?, onSettings: () -> Unit) {
    val cd = stringResource(R.string.cd_windshield_mirror, crewShort(adults, children, dog))
    val settingsCd = stringResource(R.string.settings_entry_cd)
    CraftCard(
        Modifier.fillMaxWidth().semantics(mergeDescendants = true) { if (onEdit != null) contentDescription = cd },
        onClick = onEdit,
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            CraftIconTile(R.drawable.ic_ui_van, active = false, fill = C.camper.amber, tint = C.camper.border)
            Txt(crewSummary(adults, children, dog), CraftType.cardTitle, C.camper.ink, Modifier.weight(1f), maxLines = 2)
            // D-IR-20: the settings entry of the windshield (was the round gear in the corner of the scene)
            CraftIconTile(
                R.drawable.ic_ui_gear, active = false, onClick = onSettings, size = 30.dp, cd = settingsCd,
                modifier = Modifier.testTag("windshield.settings"),
            )
        }
        DashedDivider()
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            repeat(adults.coerceAtLeast(0)) { CraftIconTile(R.drawable.ic_crew_adult, active = false, size = 28.dp, fill = C.camper.amber, tint = C.camper.border) }
            repeat(children.coerceAtLeast(0)) { CraftIconTile(R.drawable.ic_crew_child, active = true, size = 28.dp) }
            if (dog) CraftIconTile(R.drawable.ic_ui_dog, active = false, size = 28.dp, fill = C.camper.green, tint = C.camper.onOrange)
        }
    }
}

/** «2 взрослых · 1 ребёнок · собака» (the Instruments summary copy). */
@Composable
private fun crewSummary(adults: Int, children: Int, dog: Boolean): String {
    val parts = mutableListOf(stringResource(R.string.instruments_summary_adults, adults, pluralStringResource(R.plurals.plural_adult, adults)))
    if (children > 0) parts += stringResource(R.string.instruments_summary_children, children, pluralStringResource(R.plurals.plural_child, children))
    if (dog) parts += stringResource(R.string.instruments_summary_dog)
    return parts.joinToString(stringResource(R.string.common_join_dot))
}

/**
 * «Куда едем?» (mockup): the label (DEV-127: a 2 s long-press opens the debug panel), «ВЫ: …» (5.12: a tap locates),
 * the read-only search field; the whole card opens the Navigator. No routes nearby → the field gets the orange frame.
 */
@Composable
private fun NaviCard(origin: String, highlight: Boolean, onClick: () -> Unit, onDebug: () -> Unit, onYouAre: () -> Unit) {
    val cd = stringResource(R.string.cd_windshield_navi)
    CraftCard(
        Modifier.fillMaxWidth().semantics(mergeDescendants = true) { contentDescription = cd }.testTag("windshield.navi"),
        onClick = onClick,
        spacing = 6.dp,
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Txt(
                stringResource(R.string.windshield_no_routes_label), CraftType.sectionTitle, C.camper.ink,
                Modifier.weight(1f).testTag("windshield.debug").pointerInput(Unit) {
                    detectTapGestures(onPress = {
                        val released = withTimeoutOrNull(2_000) { tryAwaitRelease() }
                        if (released == null) onDebug()
                    })
                },
                maxLines = 1,
            )
            Row(
                Modifier
                    .defaultMinSize(minHeight = DesignTokens.size.touchMin)
                    .clip(RoundedCornerShape(DesignTokens.radius.r8))
                    .pointerInput(Unit) { detectTapGestures(onTap = { onYouAre() }) }
                    .testTag("windshield.youare")
                    .padding(horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Icon(R.drawable.ic_ui_location_arrow, C.camper.orangeText, 14.dp)
                Txt(stringResource(R.string.windshield_you_are, origin.uppercase()), CraftType.overline, C.camper.orangeText, maxLines = 1)
            }
        }
        Row(
            Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 52.dp)
                // 5.1 §4.7 (S-09): no routes nearby → the field is the way on (orange frame)
                .craftField(focused = highlight)
                .padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(R.drawable.ic_ui_search, C.camper.orangeText, 18.dp)
            Column(Modifier.weight(1f)) {
                Txt(stringResource(R.string.windshield_field_title), CraftType.field, C.camper.ink, maxLines = 1)
                Txt(stringResource(R.string.windshield_field_sub), CraftType.caption, C.camper.inkSoft, maxLines = 1)
            }
            Icon(R.drawable.ic_ui_chevron_right, C.camper.border, 16.dp)
        }
    }
}

/** The ready routes near the origin (was the overhead sign): title row (+ «Мои поездки»), one card of rows. */
@Composable
private fun RoutesSection(ui: WindshieldUi, onSelect: (Int) -> Unit, onRetry: () -> Unit, onTrips: () -> Unit) {
    val loadingCd = stringResource(R.string.windshield_loading_cd)
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            CraftSectionTitle(stringResource(R.string.windshield_sign_header, ui.originGen.uppercase()), Modifier.weight(1f))
            if (ui.trips.isNotEmpty()) TripsChip(ui.trips.size, onTrips)
        }
        CraftCard(Modifier.fillMaxWidth(), padding = PaddingValues(6.dp), spacing = 0.dp) {
            when (val d = ui.data) {
                is WindshieldData.Loading -> Column(Modifier.semantics(mergeDescendants = true) { contentDescription = loadingCd }) {
                    repeat(4) { i ->
                        if (i > 0) DashedDivider(Modifier.padding(horizontal = 6.dp))
                        Row(
                            Modifier.fillMaxWidth().height(56.dp).padding(horizontal = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            PlaceholderPlate(36.dp, 36.dp, C.camper.header)
                            Spacer(Modifier.width(10.dp))
                            PlaceholderPlate(150.dp, 14.dp, C.camper.header)
                            Spacer(Modifier.weight(1f))
                            PlaceholderPlate(40.dp, 14.dp, C.camper.header)
                        }
                    }
                }
                is WindshieldData.Routes -> d.routes.take(4).forEachIndexed { i, r ->
                    if (i > 0) DashedDivider(Modifier.padding(horizontal = 6.dp))
                    RouteRow(r, ui.routeKm[r.id], i == ui.selected, i) { onSelect(i) }
                }
                is WindshieldData.NoRoutes -> Column(Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Txt(stringResource(R.string.windshield_no_routes_sign), CraftType.cardTitle, C.camper.ink)
                    Txt(stringResource(R.string.windshield_no_routes_footer), CraftType.caption, C.camper.inkSoft)
                }
                is WindshieldData.Failed -> Column(Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (d.engineFailed) {
                        Txt(stringResource(R.string.engine_failed_title), CraftType.cardTitle, C.camper.ink)
                        Txt(stringResource(R.string.engine_failed_text), CraftType.caption, C.camper.inkSoft)
                    } else {
                        Txt(stringResource(R.string.windshield_error_sign), CraftType.cardTitle, C.camper.ink)
                    }
                    CraftSecondaryButton(
                        stringResource(R.string.common_retry), onRetry,
                        Modifier.fillMaxWidth().padding(top = 4.dp, end = 4.dp, bottom = 4.dp).testTag("windshield.retry"),
                        icon = R.drawable.ic_arrow_right,
                    )
                }
            }
        }
        val more = ((ui.data as? WindshieldData.Routes)?.routes?.size ?: 0) - 4
        if (more > 0) {
            Txt(
                stringResource(R.string.windshield_sign_more, more, pluralStringResource(R.plurals.plural_route, more)),
                CraftType.caption, C.camper.inkMuted, Modifier.padding(start = 4.dp),
            )
        }
    }
}

/** A ready route: bearing tile, title + meta, the engine's km (green) or a placeholder until it is known (F-01). */
@Composable
private fun RouteRow(r: ReadyRouteDto, km: Int?, isSelected: Boolean, index: Int, onClick: () -> Unit) {
    val shape = RoundedCornerShape(14.dp)
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 56.dp)
            .clip(shape)
            .then(if (isSelected) Modifier.background(C.camper.header).border(CraftDefaults.BorderThin, C.camper.orange, shape) else Modifier)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { selected = isSelected }
            .testTag("windshield.route.$index")
            .padding(horizontal = 8.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        CraftIconTile(arrowFor(r.bearing8), active = isSelected, size = 36.dp)
        Column(Modifier.weight(1f)) {
            Txt(r.title, CraftType.cardTitle, C.camper.ink, maxLines = 1)
            Txt(readyMeta(r), CraftType.caption, C.camper.inkSoft, maxLines = 1)
        }
        // Manager / F-01: never a template km — a static placeholder plate until the engine estimate of this route
        // for the current crew and pace is in.
        if (km != null) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                Icon(R.drawable.ic_ui_road, C.camper.greenText, 14.dp)
                Txt(
                    stringResource(R.string.common_km, RuFormat.thousands(km)), T.body.smStrong, C.camper.greenText,
                    Modifier.testTag("windshield.route.$index.km"), maxLines = 1,
                )
            }
        } else {
            PlaceholderPlate(40.dp, 14.dp, C.camper.header, Modifier.testTag("windshield.route.$index.km.pending"))
        }
    }
}

/** 5.1 §4.4 «Мои поездки · N» (a craft chip with the receipt icon, 44 dp touch). */
@Composable
private fun TripsChip(count: Int, onClick: () -> Unit) {
    val cd = stringResource(R.string.cd_windshield_my_trips, count, pluralStringResource(R.plurals.plural_saved, count))
    CraftChip(
        stringResource(R.string.windshield_my_trips, count), selected = false, onClick = onClick,
        modifier = Modifier.semantics { contentDescription = cd }.testTag("windshield.trips"),
        role = Role.Button, icon = R.drawable.ic_ui_receipt,
    )
}

/** components §24 `CityEntryPlate` as a craft card (5.1 §9): the walker tile, title + sub, chevron. */
@Composable
private fun CityCard(town: String, onClick: () -> Unit) {
    val cd = stringResource(R.string.cd_windshield_city, town)
    CraftCard(
        Modifier.fillMaxWidth().semantics(mergeDescendants = true) { contentDescription = cd }.testTag("windshield.city"),
        onClick = onClick,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            CraftIconTile(R.drawable.ic_tourist_walk, active = false, size = 36.dp, fill = C.camper.green, tint = C.camper.onOrange)
            Column(Modifier.weight(1f)) {
                Txt(stringResource(R.string.windshield_city_title), CraftType.cardTitle, C.camper.ink, maxLines = 1)
                Txt(stringResource(R.string.windshield_city_sub, town), CraftType.caption, C.camper.inkSoft, maxLines = 1)
            }
            Icon(R.drawable.ic_ui_chevron_right, C.camper.border, 18.dp)
        }
    }
}

/** D-1 «Мои поездки»: rows with the trip arrow, name, total and meta; tap → Road ahead. */
@Composable
private fun BoxScope.TripsSheet(trips: List<SavedTripDto>, windowH: Dp, a: TripsActions) {
    BottomSheet(stringResource(R.string.trips_title), a::close, "trips", windowH) {
        val n = trips.size
        Txt(
            stringResource(R.string.trips_subtitle, n, pluralStringResource(R.plurals.plural_saved, n)),
            CraftType.caption, C.camper.inkSoft, Modifier.padding(bottom = if (n >= SavedTripsWarn) 4.dp else 10.dp),
        )
        if (n >= SavedTripsWarn) Txt(stringResource(R.string.trips_near_limit, n), CraftType.caption, C.accent.redText, Modifier.padding(bottom = 10.dp))
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            trips.forEachIndexed { i, t -> TripRow(t, i, { a.delete(t.id) }) { a.pick(t.id) } }
        }
    }
}

@Composable
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
private fun TripRow(t: SavedTripDto, index: Int, onDelete: () -> Unit, onClick: () -> Unit) {
    val deleteLabel = stringResource(R.string.trips_delete_yes)
    val daysWord = pluralStringResource(R.plurals.plural_day, t.days)
    val date = tripDates(t.startAt, t.days)
    val walk = t.kind == "walk"
    val meta = if (walk) listOf(stringResource(R.string.walk_saved_kind), tripDates(t.startAt, 1)).filter { it.isNotBlank() }.joinToString(stringResource(R.string.common_join_dot))
    else stringResource(R.string.trips_row_meta, date, t.days, daysWord, crewShort(t.adults, t.children, t.dog))
    val total = app.verst.settings.AppPrefs.money(t.totalRub)
    val cd = stringResource(R.string.cd_trips_row, t.title, date, t.days, daysWord, total)
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 64.dp)
            .craftSurface(fill = C.camper.field, radius = 14.dp, border = CraftDefaults.BorderThin, shadow = null)
            // D-1: tap opens, long-press (or the TalkBack action «Удалить») asks to delete.
            .combinedClickable(role = Role.Button, onLongClick = onDelete, onClick = onClick)
            .semantics(mergeDescendants = true) {
                contentDescription = cd
                customActions = listOf(CustomAccessibilityAction(deleteLabel) { onDelete(); true })
            }
            .testTag("trips.row.$index")
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // DEV-308: a walk shows the walker instead of the bearing arrow
        CraftIconTile(if (walk) R.drawable.ic_tourist_walk else arrowFor(t.bearing8), active = false, size = 32.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Txt(t.title, CraftType.cardTitle, C.camper.ink, Modifier.weight(1f), maxLines = 1)
                // 5.8 §3 D-1: a yellow dot (small overrun) / a red dot (over budget) before the amount
                val dot = when (t.budgetStatus) {
                    "small_overrun" -> C.budget.tight
                    "over" -> C.accent.red
                    else -> null
                }
                if (dot != null) Box(Modifier.padding(start = 8.dp).size(6.dp).clip(RoundedCornerShape(3.dp)).background(dot))
                Txt(stringResource(R.string.common_estimate_rub, total), T.body.mdStrong, C.camper.orangeText, Modifier.padding(start = 8.dp), maxLines = 1)
            }
            Txt(meta, CraftType.caption, C.camper.inkSoft, maxLines = 1)
        }
    }
}

/** N-03 / D-1 dates: «31 октября», «7–9 ноября», «30 октября – 2 ноября» (+ year when not this year). */
@Composable
fun tripDates(startAt: String?, days: Int): String {
    val start = startAt?.takeIf { it.length >= 10 }?.let { runCatching { java.time.LocalDate.parse(it.substring(0, 10)) }.getOrNull() } ?: return ""
    val end = start.plusDays((days - 1).coerceAtLeast(0).toLong())
    val text = when {
        end == start -> stringResource(R.string.common_date_day, start.dayOfMonth.toString(), monthGen(start.monthValue))
        end.monthValue == start.monthValue -> stringResource(R.string.common_date_range_month, start.dayOfMonth.toString(), end.dayOfMonth.toString(), monthGen(end.monthValue))
        else -> stringResource(R.string.common_date_range, start.dayOfMonth.toString(), monthGen(start.monthValue), end.dayOfMonth.toString(), monthGen(end.monthValue))
    }
    return if (end.year != java.time.LocalDate.now().year) stringResource(R.string.common_date_with_year, text, end.year.toString()) else text
}

@Composable
private fun monthGen(m: Int): String = stringResource(
    when (m) {
        1 -> R.string.common_month_gen_01
        2 -> R.string.common_month_gen_02
        3 -> R.string.common_month_gen_03
        4 -> R.string.common_month_gen_04
        5 -> R.string.common_month_gen_05
        6 -> R.string.common_month_gen_06
        7 -> R.string.common_month_gen_07
        8 -> R.string.common_month_gen_08
        9 -> R.string.common_month_gen_09
        10 -> R.string.common_month_gen_10
        11 -> R.string.common_month_gen_11
        else -> R.string.common_month_gen_12
    },
)

/**
 * Meta of a ready route: its subtitle, plus «туда и обратно» for a there-and-back round trip (the km is the whole
 * trip, e.g. Ярославль ≈ 537). Loops already say «по кругу».
 */
@Composable
private fun readyMeta(r: ReadyRouteDto): String =
    if (r.roundTrip && !r.subtitle.contains("по кругу")) "${r.subtitle} · ${stringResource(R.string.windshield_meta_round_trip)}" else r.subtitle
