package app.verst.feature.navigator

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.GeoPoint
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.SuggestionDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.CraftBadge
import app.verst.core.ui.components.CraftBadgeColor
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftSectionTitle
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.DashedDivider
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.LocateIcon
import app.verst.core.ui.components.PlaceholderPlate
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
import app.verst.core.ui.components.craftShadow
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.ScreenRoot
import app.verst.nav.AddressState
import app.verst.nav.GpsState
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

data class NavigatorUi(
    val origin: GeoPoint,
    val editingFrom: Boolean,
    val query: String,
    val searching: Boolean,
    val suggestions: List<SuggestionDto>,
    val popular: List<SuggestionDto>,
    val suggestFailed: Boolean,
    val destination: SuggestionDto?,
    val routeError: String?,
    /** Engine base-route km per suggestion row (`estimate_points`); missing = not known yet (no number). */
    val rowKm: Map<String, Int?> = emptyMap(),
    /** The engine's km of the picked trip (`estimate`, = the later plan); null while it is computed. */
    val tripKm: Int? = null,
    /** TOO_SHORT / UNREACHABLE of the picked trip, known before planning. */
    val tripErrorCode: String? = null,
    /** 5.12: the GPS state, the rationale sheet, the fix (coarse / address / outside Russia). */
    val gps: GpsState = GpsState.Off,
    val locationSheet: Boolean = false,
    val originFromGps: Boolean = false,
    val gpsApprox: Boolean = false,
    val originAddress: String? = null,
    val outsideRussia: Boolean = false,
    /** 5.12 §2: the address search under the field. */
    val online: Boolean = true,
    val addressQuery: Boolean = false,
    /** The address row above the town / place rows (an address-looking query, or nothing else matched). */
    val addressFirst: Boolean = true,
    val addressState: AddressState = AddressState.Idle,
    val addressResults: List<SuggestionDto> = emptyList(),
    /** 5.12 §5: КУДА autofocuses (false after a GPS fix set ОТКУДА). */
    val focusTo: Boolean = true,
    /**
     * CEO 29.10: КУДА is an address abroad and nothing can plan it now (offline, or no server in this build; the phone
     * engine plans only in Russia): the plate and the button that opens the road in [abroadMaps] (the preferred maps app).
     */
    val abroad: Boolean = false,
    val abroadMaps: app.verst.nav.HandoffApp = app.verst.nav.HandoffApp.MAPS,
    /** CEO 29.10 (wave 1): КУДА is abroad and the server plans it — one line says so, ПОЕХАЛИ works. */
    val abroadServer: Boolean = false,
    /** The plate's reason: this build has no server (else: no internet now). */
    val abroadNoServer: Boolean = false,
)

/** 5.12: location and address answers of the Navigator. */
interface LocationActions {
    fun allow()
    fun manual() = Unit
    fun deny() = Unit
    fun precise() = Unit
    fun myLocation()
    fun findAddress() = Unit
    fun closeSheet() = Unit
}

private val NoLocation = object : LocationActions {
    override fun allow() = Unit
    override fun myLocation() = Unit
}

/** Row fill of the results and address rows (white paper inside the paper page). */
private val RowShape = RoundedCornerShape(14.dp)

/**
 * 5.2 Navigator, camper-ui fork (mockup screen 2): a paper page — the «Поиск направления» card with ОТКУДА / КУДА,
 * the results as craft rows under it, the route summary and the full-width ПОЕХАЛИ at the bottom.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun NavigatorScreen(
    ui: NavigatorUi,
    onBack: () -> Unit,
    onQuery: (String) -> Unit,
    onPick: (SuggestionDto) -> Unit,
    onEditFrom: () -> Unit,
    onStart: () -> Unit,
    location: LocationActions = NoLocation,
    /** CEO 29.10: the abroad plate's button → the maps app with ОТКУДА and КУДА. */
    onAbroadMaps: () -> Unit = {},
) {
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    var inputFocused by remember { mutableStateOf(false) }
    val pick: (SuggestionDto) -> Unit = {
        keyboard?.hide()
        focus.clearFocus(force = true) // S-26: after a pick КУДА loses focus (no orange frame, no caret)
        inputFocused = false
        onPick(it)
    }
    val imeUp = WindowInsets.isImeVisible
    // 5.12 §5.5 (S3-FINAL P1-01): a GPS fix that sets ОТКУДА hides the IME and clears focus together
    var lastGps by remember { mutableStateOf(ui.gps) }
    LaunchedEffect(ui.gps) {
        if (ui.gps == GpsState.On && lastGps != GpsState.On) {
            focus.clearFocus(force = true)
            inputFocused = false
            keyboard?.hide()
        }
        lastGps = ui.gps
    }
    LaunchedEffect(imeUp, inputFocused) {
        // 5.12 §5: no field has focus (a GPS fix set ОТКУДА) → the IME goes down; the delay skips focus hand-overs
        if (imeUp && !inputFocused) {
            kotlinx.coroutines.delay(400)
            if (!inputFocused) keyboard?.hide()
        }
    }
    ScreenRoot(C.camper.page) {
        Column(Modifier.fillMaxSize().imePadding()) {
            // While typing (IME up) the back link and the caption give their room to the results.
            val typing = WindowInsets.isImeVisible
            if (!typing) {
                val back = stringResource(R.string.common_back_to_windshield)
                BackLink(back, C.camper.inkSoft, stringResource(R.string.cd_back, back), onBack, Modifier.padding(start = 10.dp, top = 4.dp))
            }
            Panel(ui, typing, onQuery, pick, onEditFrom, location, onAbroadMaps, { inputFocused = it }, Modifier.weight(1f).fillMaxWidth())
            // 5.2 §1: the caption row hides while typing and returns after a pick.
            if (!typing) Caption(ui, onStart)
        }
        if (ui.locationSheet) {
            BoxWithConstraints(Modifier.matchParentSize()) {
                val h = maxHeight
                Box(Modifier.matchParentSize()) { LocationSheet(h, location) }
            }
        }
    }
}

@Composable
private fun Panel(
    ui: NavigatorUi,
    typing: Boolean,
    onQuery: (String) -> Unit,
    onPick: (SuggestionDto) -> Unit,
    onEditFrom: () -> Unit,
    location: LocationActions,
    onAbroadMaps: () -> Unit,
    onFocus: (Boolean) -> Unit,
    modifier: Modifier,
) {
    val scroll = rememberScrollState()
    // 5.12 §5 (S3-QA P1-01): fixed card + focused field + helper; only the result list scrolls. A new query
    // starts the list at its top (the «Найти адрес «…»» action row is the first item).
    LaunchedEffect(ui.query) { scroll.scrollTo(0) }
    val fromValue = when {
        ui.gps == GpsState.Waiting -> stringResource(R.string.loc_searching)
        ui.originFromGps && ui.originAddress != null -> stringResource(R.string.loc_here_address, ui.originAddress)
        ui.originFromGps -> stringResource(R.string.loc_here_town, ui.origin.label)
        else -> stringResource(R.string.navigator_from_here, ui.origin.label)
    }
    val q = ui.query.trim()
    val picked = !ui.editingFrom && ui.destination != null && ui.query == ui.destination.name
    val outer = rememberScrollState()
    Column(
        modifier
            // not typing: one scroll for the card and the list (small windows); typing: only the list scrolls
            .then(if (typing) Modifier else Modifier.verticalScroll(outer))
            .padding(top = if (typing) 8.dp else 4.dp),
        verticalArrangement = Arrangement.spacedBy(if (typing) 8.dp else CraftDefaults.Gap),
    ) {
        // fixed: «Поиск направления» — the header with the GPS state and the fields
        CraftCard(Modifier.fillMaxWidth().padding(horizontal = CraftDefaults.ScreenGutter), spacing = if (typing) 6.dp else 10.dp) {
            Row(Modifier.fillMaxWidth().testTag("navigator.header"), verticalAlignment = Alignment.CenterVertically) {
                Txt(stringResource(R.string.navigator_header), CraftType.sectionTitle, C.camper.ink, Modifier.weight(1f), maxLines = 1)
                // S3-R1: «GPS ●» once the origin is the town of the fix, «GPS ○» while asking the phone.
                when (ui.gps) {
                    GpsState.On -> CraftBadge(stringResource(R.string.navigator_gps_on), Modifier.testTag("navigator.gps.on"), CraftBadgeColor.GREEN)
                    GpsState.Waiting -> CraftBadge(stringResource(R.string.navigator_gps_wait), Modifier.testTag("navigator.gps.wait"))
                    else -> Unit
                }
            }
            if (!typing) DashedDivider()
            // While typing, the other field collapses to one line (h 28) under the header.
            if (ui.editingFrom) {
                if (typing) CollapsedLine(ui.destination?.name ?: stringResource(R.string.navigator_to_hint), "navigator.to.collapsed", null)
                Input(stringResource(R.string.navigator_from), ui.query, onQuery, round = true, tag = "navigator.from", onFocus = onFocus, autoFocus = true, onSubmit = location::findAddress)
                if (!typing) {
                    MyLocationRow(ui.gps == GpsState.Waiting, location::myLocation)
                    ValueField(stringResource(R.string.navigator_to_label), ui.destination?.name ?: stringResource(R.string.navigator_to_hint), square = true)
                }
            } else {
                if (ui.outsideRussia) {
                    OutsideRussia(onEditFrom)
                } else if (typing) {
                    CollapsedLine(fromValue, "navigator.from.collapsed", onEditFrom)
                } else {
                    // 5.12 §1: «Ищем вас…» while the fix runs; the address (online) or «Ярославль (по GPS)»; coarse → «Точнее»
                    val approx = ui.originFromGps && ui.gpsApprox && ui.gps == GpsState.On
                    ValueField(
                        stringResource(R.string.navigator_from),
                        fromValue,
                        square = false,
                        action = stringResource(if (approx) R.string.loc_precise else R.string.navigator_change),
                        onAction = if (approx) location::precise else onEditFrom,
                        sub = if (approx) stringResource(R.string.loc_approx_note) else null,
                        actionTag = if (approx) "navigator.precise" else "navigator.change",
                    )
                }
                Input(
                    stringResource(R.string.navigator_to_label), ui.query, onQuery, round = false, tag = "navigator.to", onFocus = onFocus,
                    autoFocus = ui.destination == null && ui.focusTo, onSubmit = location::findAddress,
                )
            }
            // fixed: the address helper line
            if (!picked && ui.addressQuery) Txt(stringResource(R.string.addr_find_hint), CraftType.caption, C.camper.inkMuted, Modifier.testTag("address.hint"))
        }
        // the only scrolling part while typing: rows (the address action first), «© OpenStreetMap» under the address rows
        Column(
            Modifier
                .fillMaxWidth()
                .then(if (typing) Modifier.weight(1f, fill = false).verticalScroll(scroll) else Modifier)
                // inside the scroll clip: the gutter and the bottom keep the rows' hard shadow visible
                .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, bottom = 6.dp)
                .testTag("navigator.list"),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (ui.editingFrom && typing) MyLocationRow(ui.gps == GpsState.Waiting, location::myLocation)
            if (!picked && ui.addressQuery && ui.addressFirst) AddressBlock(ui, q, location::findAddress, onPick)
            when {
                picked -> {
                    if (ui.abroad) AbroadPlate(ui.destination?.name.orEmpty(), ui.abroadMaps, ui.abroadNoServer, onAbroadMaps)
                    if (ui.abroadServer) AbroadServerLine()
                }
                q.length < 2 -> if (ui.popular.isNotEmpty()) {
                    CraftSectionTitle(stringResource(R.string.navigator_popular), Modifier.padding(top = 4.dp))
                    Rows(ui.popular.take(6), ui.rowKm, onPick)
                }
                ui.searching && ui.suggestions.isEmpty() -> Skeleton()
                ui.suggestFailed -> Block(stringResource(R.string.navigator_suggest_error), null)
                ui.suggestions.isEmpty() && ui.addressQuery -> Unit // the address row / results speak for themselves (5.12 §2)
                ui.suggestions.isEmpty() -> Block(
                    stringResource(R.string.navigator_no_results_title, q),
                    stringResource(R.string.navigator_no_results_text),
                )
                else -> Rows(ui.suggestions, ui.rowKm, onPick)
            }
            // a street that also matched towns («Мира» → «Мирный»): the address row after them
            if (!picked && ui.addressQuery && !ui.addressFirst) AddressBlock(ui, q, location::findAddress, onPick)
        }
    }
}

/** 5.12 §5: the other field while typing — one line, h 28, caption `inkSoft`; tap = edit it. */
@Composable
private fun CollapsedLine(value: String, tag: String, onClick: (() -> Unit)?) {
    Box(
        Modifier.fillMaxWidth().height(28.dp)
            .then(if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier)
            .testTag(tag),
        contentAlignment = Alignment.CenterStart,
    ) { Txt(value, CraftType.caption, C.camper.inkSoft, maxLines = 1) }
}

/** A typed field (mockup «Куда:»): the label above, white paper frame, orange while focused, «×» to clear. */
@Composable
private fun Input(caption: String, value: String, onChange: (String) -> Unit, round: Boolean, tag: String, onFocus: (Boolean) -> Unit, autoFocus: Boolean, onSubmit: () -> Unit = {}) {
    val fr = remember { FocusRequester() }
    var focused by remember { mutableStateOf(false) }
    LaunchedEffect(tag) { if (autoFocus) fr.requestFocus() }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Txt(caption, CraftType.fieldLabel, C.camper.inkSoft, maxLines = 1)
        Row(
            Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 48.dp)
                .craftField(focused = focused)
                .padding(start = 12.dp, end = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Marker(round, C.camper.orangeText)
            Spacer(Modifier.width(10.dp))
            BasicTextField(
                value = value,
                onValueChange = onChange,
                singleLine = true,
                textStyle = CraftType.field.copy(color = C.camper.ink),
                cursorBrush = SolidColor(C.camper.orange),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { onSubmit() }),
                modifier = Modifier
                    .weight(1f)
                    .padding(vertical = 12.dp)
                    .focusRequester(fr)
                    .onFocusChanged { focused = it.isFocused; onFocus(it.isFocused) }
                    .testTag(tag),
                decorationBox = { inner ->
                    Box {
                        if (value.isEmpty()) Txt(stringResource(R.string.navigator_to_hint), CraftType.field, C.camper.inkMuted, maxLines = 1)
                        inner()
                    }
                },
            )
            if (value.isNotEmpty()) {
                val cd = stringResource(R.string.cd_navigator_clear)
                Box(
                    Modifier.size(DesignTokens.size.touchMin).clip(CircleShape).clickable(role = Role.Button) { onChange("") }.semantics { contentDescription = cd },
                    contentAlignment = Alignment.Center,
                ) { Txt("×", T.button.glyph, C.camper.inkSoft) }
            }
        }
    }
}

/** A read-only field (mockup «Откуда:», the sunken tan fill) with an optional action («изменить» / «Точнее»). */
@Composable
private fun ValueField(
    caption: String,
    value: String,
    square: Boolean,
    action: String? = null,
    onAction: (() -> Unit)? = null,
    sub: String? = null,
    actionTag: String = "navigator.change",
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Txt(caption, CraftType.fieldLabel, C.camper.inkSoft, maxLines = 1)
        Row(
            Modifier
                .fillMaxWidth()
                .defaultMinSize(minHeight = 48.dp)
                .craftField(fill = C.camper.header)
                .padding(start = 12.dp, end = 4.dp, top = 2.dp, bottom = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Marker(!square, if (square) C.camper.orangeText else C.camper.border)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f).padding(vertical = 6.dp)) {
                Txt(value, CraftType.field, C.camper.ink, Modifier.testTag("navigator.from.value"), maxLines = 1)
                if (sub != null) Txt(sub, CraftType.caption, C.camper.inkMuted, maxLines = 1)
            }
            if (action != null && onAction != null) {
                Box(
                    Modifier
                        .defaultMinSize(minWidth = DesignTokens.size.touchMin, minHeight = DesignTokens.size.touchMin)
                        .clip(RoundedCornerShape(DesignTokens.radius.r8))
                        .clickable(role = Role.Button, onClick = onAction)
                        .testTag(actionTag)
                        .padding(horizontal = 8.dp),
                    contentAlignment = Alignment.Center,
                ) { Txt(action, T.body.smStrong, C.camper.orangeText, maxLines = 1) }
            }
        }
    }
}

@Composable
private fun Marker(round: Boolean, color: Color) {
    if (round) {
        Box(Modifier.size(12.dp).border(3.dp, color, CircleShape))
    } else {
        Box(Modifier.size(12.dp).clip(RoundedCornerShape(3.dp)).background(color))
    }
}

/** The results as craft rows: one card, dashed rules between the rows. */
@Composable
private fun Rows(items: List<SuggestionDto>, rowKm: Map<String, Int?>, onPick: (SuggestionDto) -> Unit, tagPrefix: String = "navigator.suggestion", address: Boolean = false) {
    CraftCard(Modifier.fillMaxWidth(), padding = PaddingValues(4.dp), spacing = 0.dp) {
        items.forEachIndexed { i, s ->
            if (i > 0) DashedDivider(Modifier.padding(horizontal = 8.dp))
            SuggestionRow(s, rowKm[s.pointKey], i, tagPrefix, address) { onPick(s) }
        }
    }
}

@Composable
private fun SuggestionRow(s: SuggestionDto, km: Int?, index: Int, tagPrefix: String, address: Boolean, onClick: () -> Unit) {
    // The engine's road km to the place (before a trip exists); the trip itself adds its stop detours.
    val kmText = km?.let { stringResource(R.string.common_km_approx, RuFormat.thousands(it)) } ?: ""
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = DesignTokens.size.suggestionRowMinH)
            .clip(RowShape)
            .clickable(role = Role.Button, onClick = onClick)
            .testTag("$tagPrefix.$index")
            .padding(horizontal = 8.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        val city = s.kind == "city"
        val tileShape = RoundedCornerShape(8.dp)
        Box(
            Modifier.size(28.dp).clip(tileShape).background(if (city || address) C.camper.blue else C.camper.green)
                .border(CraftDefaults.BadgeBorder, C.camper.border, tileShape),
            contentAlignment = Alignment.Center,
        ) {
            // 5.12 §2: address rows carry «У» (улица)
            Txt(
                if (address) stringResource(R.string.navigator_type_address) else stringResource(if (city) R.string.navigator_type_city else R.string.navigator_type_place),
                T.badge, C.camper.onOrange,
            )
        }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Txt(s.name, CraftType.cardTitle, C.camper.ink, maxLines = 1)
            Txt(if (address) stringResource(R.string.addr_sub, s.subtitle) else s.subtitle, CraftType.caption, C.camper.inkSoft, maxLines = 1)
        }
        Txt(kmText, T.body.smStrong, C.camper.inkSoft, Modifier.padding(start = 8.dp), align = TextAlign.End)
    }
}

@Composable
private fun Skeleton() {
    CraftCard(Modifier.fillMaxWidth(), spacing = 12.dp) {
        repeat(3) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                PlaceholderPlate(28.dp, 28.dp, C.camper.header)
                Spacer(Modifier.width(10.dp))
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    PlaceholderPlate(140.dp, 12.dp, C.camper.header)
                    PlaceholderPlate(90.dp, 10.dp, C.camper.header)
                }
            }
        }
    }
}

@Composable
private fun Block(title: String, text: String?) {
    CraftCard(Modifier.fillMaxWidth(), spacing = 4.dp) {
        Txt(title, CraftType.cardTitle, C.camper.ink)
        if (text != null) Txt(text, CraftType.caption, C.camper.inkSoft)
    }
}

/** The route summary card (МАРШРУТ · title · engine km or the error) and the full-width ПОЕХАЛИ. */
@Composable
private fun Caption(ui: NavigatorUi, onStart: () -> Unit) {
    val dest = ui.destination
    val km = if (dest != null) ui.tripKm else null
    val error = ui.routeError ?: when (ui.tripErrorCode.takeIf { dest != null }) {
        "TOO_SHORT" -> stringResource(R.string.error_too_short)
        "UNREACHABLE" -> stringResource(R.string.error_unreachable)
        else -> null
    }
    // 5.12: a Russian start first; CEO 29.10: and a Russian destination (abroad: the plate, no plan)
    val enabled = dest != null && error == null && !ui.outsideRussia && !ui.abroad
    Column(
        Modifier.fillMaxWidth().padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 4.dp, bottom = CraftDefaults.ScreenGutter),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        CraftCard(
            Modifier.fillMaxWidth().semantics(mergeDescendants = true) {},
            padding = PaddingValues(horizontal = 12.dp, vertical = 10.dp),
            spacing = 2.dp,
        ) {
            Txt(stringResource(R.string.navigator_route_label), CraftType.overline, C.camper.orangeText, maxLines = 1)
            Txt(
                if (dest != null) stringResource(R.string.navigator_route_title, ui.origin.label, dest.name)
                else stringResource(R.string.navigator_route_no_to, ui.origin.label),
                CraftType.cardTitle, C.camper.ink, maxLines = 1,
            )
            val meta = when {
                error != null -> error
                dest != null && km != null -> stringResource(R.string.common_km, RuFormat.thousands(km)) +
                    stringResource(R.string.common_join_dot) + dest.subtitle
                dest != null -> dest.subtitle
                else -> stringResource(R.string.navigator_route_no_to_meta)
            }
            Txt(meta, CraftType.caption, if (error != null) C.accent.redText else C.camper.inkSoft, Modifier.testTag("navigator.meta"), maxLines = 2)
        }
        val cd = if (enabled) stringResource(R.string.common_go) else stringResource(R.string.cd_start_disabled_destination)
        CraftButton(
            stringResource(R.string.common_go), onStart,
            Modifier.fillMaxWidth().semantics { contentDescription = cd }.testTag("navigator.start"),
            icon = R.drawable.ic_ui_compass,
            enabled = enabled,
        )
    }
}

/** 5.12 §1 rationale sheet «Откуда поедем?»: «Разрешить» (coarse) or «Выберу сам» (→ ОТКУДА input). */
@Composable
private fun BoxScope.LocationSheet(windowH: Dp, a: LocationActions) {
    BottomSheet(stringResource(R.string.loc_rationale_title), a::closeSheet, "location", windowH) {
        LocateIcon(C.camper.orangeText, 32.dp, Modifier.padding(bottom = 8.dp))
        Txt(stringResource(R.string.loc_rationale_body), CraftType.body, C.camper.inkSoft, Modifier.padding(bottom = 16.dp))
        CraftButton(
            stringResource(R.string.loc_allow), a::allow,
            Modifier.fillMaxWidth().padding(end = 4.dp, bottom = 6.dp).testTag("location.allow"),
            icon = R.drawable.ic_ui_location_arrow,
        )
        Box(
            Modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = a::manual).testTag("location.manual"),
            contentAlignment = Alignment.Center,
        ) { Txt(stringResource(R.string.loc_manual), T.body.mdStrong, C.camper.inkSoft) }
    }
}

/**
 * CEO 29.10: КУДА is abroad and cannot be planned now. Only the server plans trips abroad (the phone engine knows only
 * Russia), so the plate says honestly why not now — no internet, or no server in this build — and offers the road
 * itself in the preferred maps app (ОТКУДА → КУДА). Mockup: a dashed craft card with the blue badge.
 */
@Composable
private fun AbroadPlate(place: String, maps: app.verst.nav.HandoffApp, noServer: Boolean, onMaps: () -> Unit) {
    val radius = CraftDefaults.CardRadius
    Column(
        Modifier
            .fillMaxWidth()
            .craftShadow(radius)
            .clip(RoundedCornerShape(radius))
            .background(C.camper.field)
            .drawBehind {
                val w = CraftDefaults.Border.toPx()
                drawRoundRect(
                    C.camper.border, topLeft = Offset(w / 2, w / 2), size = Size(size.width - w, size.height - w),
                    cornerRadius = CornerRadius(radius.toPx() - w / 2),
                    style = Stroke(w, pathEffect = PathEffect.dashPathEffect(floatArrayOf(8.dp.toPx(), 5.dp.toPx()))),
                )
            }
            .padding(12.dp)
            .testTag("navigator.abroad"),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            CraftBadge(stringResource(R.string.waybill_abroad_title), color = CraftBadgeColor.BLUE)
            Spacer(Modifier.weight(1f))
            Icon(R.drawable.ic_ui_passport, C.camper.border, 18.dp)
        }
        Txt(stringResource(R.string.navigator_abroad_title), CraftType.cardTitle, C.camper.ink)
        Txt(stringResource(if (noServer) R.string.navigator_abroad_body_no_server else R.string.navigator_abroad_body, place), CraftType.caption, C.camper.inkSoft)
        val label = stringResource(if (maps == app.verst.nav.HandoffApp.GOOGLE) R.string.handoff_google_car else R.string.handoff_maps_car)
        CraftButton(label, onMaps, Modifier.fillMaxWidth().padding(top = 4.dp, end = 4.dp, bottom = 4.dp).testTag("navigator.abroad.maps"))
    }
}

/** CEO 29.10 (wave 1): КУДА abroad goes to the server — one line under the picked КУДА. */
@Composable
private fun AbroadServerLine() {
    Row(Modifier.fillMaxWidth().padding(top = 4.dp).testTag("navigator.abroad.server"), verticalAlignment = Alignment.CenterVertically) {
        GlyphIcon(Glyph.INFO, C.camper.inkSoft, 14.dp)
        Spacer(Modifier.width(6.dp))
        Txt(stringResource(R.string.abroad_server_line), CraftType.caption, C.camper.inkSoft)
    }
}

/** 5.12 §1 outside Russia: the state block in place of ОТКУДА. */
@Composable
private fun OutsideRussia(onChoose: () -> Unit) {
    Column(
        Modifier.fillMaxWidth()
            .craftSurface(fill = C.camper.header, radius = 14.dp, border = CraftDefaults.BorderThin, shadow = null)
            .padding(12.dp)
            .testTag("navigator.outside"),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Txt(stringResource(R.string.loc_outside_title), CraftType.cardTitle, C.camper.ink)
        Txt(stringResource(R.string.loc_outside_body), CraftType.caption, C.camper.inkSoft)
        Box(
            Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = onChoose).testTag("navigator.outside.choose"),
            contentAlignment = Alignment.CenterStart,
        ) { Txt(stringResource(R.string.loc_outside_action), T.body.smStrong, C.camper.orangeText) }
    }
}

/** A white-paper craft row outside a card (the address action, «Моё местоположение»): 2 dp border, 2 × 2 shadow. */
private fun Modifier.craftRow(): Modifier =
    craftSurface(fill = C.camper.field, radius = 14.dp, border = CraftDefaults.BorderThin, shadowX = 2.dp, shadowY = 2.dp)

/**
 * 5.12 §2: an address-like query → the helper line and «Найти адрес «…»» (explicit submit, never per keystroke);
 * then the address rows + «© OpenStreetMap»; offline → the hint row instead.
 */
@Composable
private fun AddressBlock(ui: NavigatorUi, q: String, onFind: () -> Unit, onPick: (SuggestionDto) -> Unit) {
    when {
        !ui.online || ui.addressState == AddressState.Offline -> Row(
            Modifier.fillMaxWidth().craftRow().padding(12.dp).testTag("address.offline"),
            verticalAlignment = Alignment.CenterVertically,
        ) { Txt(stringResource(R.string.addr_offline), CraftType.caption, C.camper.inkSoft) }
        ui.addressState == AddressState.Done -> {
            Rows(ui.addressResults, ui.rowKm, onPick, tagPrefix = "address.row", address = true)
            Txt(stringResource(R.string.addr_attribution), T.caption.md, C.camper.inkMuted, Modifier.fillMaxWidth().height(24.dp).testTag("address.attribution"), align = TextAlign.End)
        }
        else -> {
            // designer В-2: the error right under the field, above the action, in the error colour
            if (ui.addressState == AddressState.None) {
                Txt(stringResource(R.string.addr_none), CraftType.caption, C.accent.redText, Modifier.testTag("address.none"))
            }
            if (ui.addressState == AddressState.Failed) {
                Txt(stringResource(R.string.addr_failed), CraftType.caption, C.accent.redText, Modifier.testTag("address.failed"))
            }
            val searching = ui.addressState == AddressState.Searching
            Row(
                Modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.suggestionRowMinH)
                    .craftRow()
                    .clickable(enabled = !searching, role = Role.Button, onClick = onFind).testTag("address.find")
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(R.drawable.ic_ui_search, C.camper.orangeText, 18.dp)
                Spacer(Modifier.width(10.dp))
                Txt(
                    if (searching) stringResource(R.string.addr_searching) else stringResource(R.string.addr_find_query, q),
                    CraftType.cardTitle, C.camper.orangeText, Modifier.weight(1f), maxLines = 1,
                )
            }
        }
    }
}

/** «Моё местоположение» while editing ОТКУДА: the town nearest to the phone. */
@Composable
private fun MyLocationRow(waiting: Boolean, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.suggestionRowMinH)
            .craftRow()
            .clickable(role = Role.Button, onClick = onClick).testTag("navigator.mylocation")
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(R.drawable.ic_ui_location_arrow, C.camper.orangeText, 18.dp)
        Spacer(Modifier.width(10.dp))
        Txt(stringResource(R.string.navigator_my_location), CraftType.cardTitle, C.camper.ink, Modifier.weight(1f), maxLines = 1)
        Txt(stringResource(if (waiting) R.string.navigator_gps_wait else R.string.navigator_gps_on), CraftType.overline, C.camper.inkSoft)
    }
}
