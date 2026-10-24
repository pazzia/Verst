package app.verst.feature.navigator

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
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
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.verst.core.model.GeoPoint
import app.verst.core.model.RuFormat
import app.verst.core.model.TripMath
import app.verst.core.model.dto.SuggestionDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.PlaceholderPlate
import app.verst.core.ui.components.SkyStrip
import app.verst.core.ui.components.StartButton
import app.verst.core.ui.components.StartSize
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.dashboardSurface
import app.verst.core.ui.components.naviPanel
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.ScreenRoot
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** Straight-line distance under which no car trip is offered (5.2 §4.4). */
private const val TOO_SHORT_KM = 15

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
)

/** 5.2 Navigator, simplified: ОТКУДА (changeable) and КУДА via the engine's `suggest`; no vias, no map. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun NavigatorScreen(
    ui: NavigatorUi,
    onBack: () -> Unit,
    onQuery: (String) -> Unit,
    onPick: (SuggestionDto) -> Unit,
    onEditFrom: () -> Unit,
    onStart: () -> Unit,
) {
    val keyboard = LocalSoftwareKeyboardController.current
    val focus = LocalFocusManager.current
    var inputFocused by remember { mutableStateOf(false) }
    val pick: (SuggestionDto) -> Unit = {
        keyboard?.hide()
        focus.clearFocus()
        inputFocused = false
        onPick(it)
    }
    ScreenRoot(C.dash.base) {
        Column(Modifier.fillMaxSize().imePadding()) {
            Box(Modifier.fillMaxWidth().height(150.dp)) {
                SkyStrip(150.dp, ground = true)
                Box(Modifier.fillMaxSize().padding(top = 132.dp).dashboardSurface(curve = 30.dp))
            }
            Column(Modifier.weight(1f).fillMaxWidth().background(C.dash.raised)) {
                val back = stringResource(R.string.common_back_to_windshield)
                BackLink(back, C.text.muted, stringResource(R.string.cd_back, back), onBack, Modifier.padding(start = 16.dp, top = 0.dp))
                Panel(ui, onQuery, pick, onEditFrom, { inputFocused = it }, Modifier.weight(1f).padding(horizontal = 14.dp).padding(top = 6.dp, bottom = 12.dp))
                // 5.2 §1: the caption row hides while typing (IME open on a focused field) and returns after a pick.
                if (!(inputFocused && WindowInsets.isImeVisible)) Caption(ui, onStart)
            }
        }
    }
}

@Composable
private fun Panel(
    ui: NavigatorUi,
    onQuery: (String) -> Unit,
    onPick: (SuggestionDto) -> Unit,
    onEditFrom: () -> Unit,
    onFocus: (Boolean) -> Unit,
    modifier: Modifier,
) {
    Column(
        modifier
            .fillMaxWidth()
            .naviPanel(bezel = 7.dp, radius = 18.dp)
            .padding(19.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Txt(stringResource(R.string.navigator_header), T.label.md, C.navi.label)
        if (ui.editingFrom) {
            Input(stringResource(R.string.navigator_from), ui.query, onQuery, round = true, tag = "navigator.from", onFocus = onFocus)
            ValueField(stringResource(R.string.navigator_to_label), ui.destination?.name ?: stringResource(R.string.navigator_to_hint), square = true)
        } else {
            ValueField(
                stringResource(R.string.navigator_from),
                stringResource(R.string.navigator_from_here, ui.origin.label),
                square = false,
                action = stringResource(R.string.navigator_change),
                onAction = onEditFrom,
            )
            Input(stringResource(R.string.navigator_to_label), ui.query, onQuery, round = false, tag = "navigator.to", onFocus = onFocus)
        }
        val q = ui.query.trim()
        val picked = !ui.editingFrom && ui.destination != null && ui.query == ui.destination.name
        when {
            picked -> Unit
            q.length < 2 -> if (ui.popular.isNotEmpty()) {
                Txt(stringResource(R.string.navigator_popular), T.label.md, C.navi.hint, Modifier.padding(top = 4.dp))
                Rows(ui.popular.take(6), ui.origin, onPick)
            }
            ui.searching && ui.suggestions.isEmpty() -> Skeleton()
            ui.suggestFailed -> Block(stringResource(R.string.navigator_suggest_error), null)
            ui.suggestions.isEmpty() -> Block(
                stringResource(R.string.navigator_no_results_title, q),
                stringResource(R.string.navigator_no_results_text),
            )
            else -> Rows(ui.suggestions, ui.origin, onPick)
        }
    }
}

@Composable
private fun Input(caption: String, value: String, onChange: (String) -> Unit, round: Boolean, tag: String, onFocus: (Boolean) -> Unit) {
    val fr = remember { FocusRequester() }
    LaunchedEffect(tag) { fr.requestFocus() }
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 56.dp)
            .clip(shape)
            .background(C.navi.field)
            .border(DesignTokens.stroke.w2, C.accent.yellow, shape)
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Marker(round, C.accent.yellow)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Txt(caption, T.caption.md, C.navi.labelSecondary)
            BasicTextField(
                value = value,
                onValueChange = onChange,
                singleLine = true,
                textStyle = T.field.lg.copy(color = C.text.primary),
                cursorBrush = SolidColor(C.accent.yellow),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                modifier = Modifier.fillMaxWidth().focusRequester(fr).onFocusChanged { onFocus(it.isFocused) }.testTag(tag),
                decorationBox = { inner ->
                    Box {
                        if (value.isEmpty()) Txt(stringResource(R.string.navigator_to_hint), T.field.lg, C.navi.hint)
                        inner()
                    }
                },
            )
        }
        if (value.isNotEmpty()) {
            val cd = stringResource(R.string.cd_navigator_clear)
            Box(
                Modifier.size(44.dp).clickable(role = Role.Button) { onChange("") }.semantics { contentDescription = cd },
                contentAlignment = Alignment.Center,
            ) { Txt("×", T.button.glyph, C.navi.labelSecondary) }
        }
    }
}

@Composable
private fun ValueField(
    caption: String,
    value: String,
    square: Boolean,
    action: String? = null,
    onAction: (() -> Unit)? = null,
) {
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 50.dp)
            .clip(shape)
            .background(C.navi.field)
            .border(DesignTokens.stroke.w1, C.navi.fieldBorder, shape)
            .padding(start = 12.dp, end = 8.dp, top = 6.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Marker(!square, if (square) C.accent.yellow else C.navi.label)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Txt(caption, T.caption.md, C.navi.labelSecondary, maxLines = 1)
            Txt(value, T.field.md, C.text.primary, maxLines = 1)
        }
        if (action != null && onAction != null) {
            Box(
                Modifier
                    .height(44.dp)
                    .clickable(role = Role.Button, onClick = onAction)
                    .testTag("navigator.change"),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    Modifier
                        .height(36.dp)
                        .border(DesignTokens.stroke.w1, C.navi.fieldBorder, RoundedCornerShape(DesignTokens.radius.r8))
                        .padding(horizontal = 10.dp),
                    contentAlignment = Alignment.Center,
                ) { Txt(action, T.body.smStrong, C.navi.label) }
            }
        }
    }
}

@Composable
private fun Marker(round: Boolean, color: androidx.compose.ui.graphics.Color) {
    if (round) {
        Box(Modifier.size(12.dp).border(3.dp, color, CircleShape))
    } else {
        Box(Modifier.size(12.dp).clip(RoundedCornerShape(3.dp)).background(color))
    }
}

@Composable
private fun Rows(items: List<SuggestionDto>, origin: GeoPoint, onPick: (SuggestionDto) -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(DesignTokens.radius.r10))
            .border(DesignTokens.stroke.w1, C.navi.divider, RoundedCornerShape(DesignTokens.radius.r10)),
    ) {
        items.forEachIndexed { i, s ->
            if (i > 0) Box(Modifier.fillMaxWidth().height(1.dp).background(C.navi.divider))
            SuggestionRow(s, origin, i) { onPick(s) }
        }
    }
}

@Composable
private fun SuggestionRow(s: SuggestionDto, origin: GeoPoint, index: Int, onClick: () -> Unit) {
    val km = TripMath.haversineKm(origin, GeoPoint(s.name, s.lat, s.lon)).toInt()
    val kmText = stringResource(R.string.common_km_approx, RuFormat.thousands(km))
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = DesignTokens.size.suggestionRowMinH)
            .background(C.navi.list)
            .clickable(role = Role.Button, onClick = onClick)
            .testTag("navigator.suggestion.$index")
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        val city = s.kind == "city"
        Box(
            Modifier.size(26.dp).clip(RoundedCornerShape(DesignTokens.radius.r6)).background(if (city) C.sign.blue else C.sign.brown),
            contentAlignment = Alignment.Center,
        ) {
            Txt(stringResource(if (city) R.string.navigator_type_city else R.string.navigator_type_place), T.badge, C.text.primary)
        }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Txt(s.name, T.list.title, C.text.primary, maxLines = 1)
            Txt(s.subtitle, T.body.sm, C.navi.labelSecondary, maxLines = 1)
        }
        Txt(kmText, T.body.mdTight, C.navi.text, Modifier.padding(start = 8.dp), align = TextAlign.End)
    }
}

@Composable
private fun Skeleton() {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        repeat(3) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                PlaceholderPlate(26.dp, 26.dp, C.navi.field)
                Spacer(Modifier.width(10.dp))
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    PlaceholderPlate(140.dp, 12.dp, C.navi.field)
                    PlaceholderPlate(90.dp, 10.dp, C.navi.field)
                }
            }
        }
    }
}

@Composable
private fun Block(title: String, text: String?) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(DesignTokens.radius.r10)).background(C.navi.list).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Txt(title, T.list.title, C.text.primary)
        if (text != null) Txt(text, T.body.sm, C.navi.labelSecondary)
    }
}

@Composable
private fun Caption(ui: NavigatorUi, onStart: () -> Unit) {
    val dest = ui.destination
    val km = dest?.let { TripMath.haversineKm(ui.origin, GeoPoint(it.name, it.lat, it.lon)).toInt() }
    val tooShort = km != null && km < TOO_SHORT_KM
    val error = ui.routeError ?: if (tooShort) stringResource(R.string.error_too_short) else null
    val enabled = dest != null && error == null
    Row(
        Modifier.fillMaxWidth().padding(start = 22.dp, end = 20.dp, bottom = 26.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f).padding(end = 14.dp).semantics(mergeDescendants = true) {}) {
            Txt(stringResource(R.string.navigator_route_label), T.label.md, C.text.muted)
            Txt(
                if (dest != null) stringResource(R.string.navigator_route_title, ui.origin.label, dest.name)
                else stringResource(R.string.navigator_route_no_to, ui.origin.label),
                T.title.lg, C.text.primary, maxLines = 1,
            )
            val meta = when {
                error != null -> error
                dest != null && km != null -> stringResource(R.string.common_km_approx, RuFormat.thousands(km)) +
                    stringResource(R.string.common_join_dot) + dest.subtitle
                else -> stringResource(R.string.navigator_route_no_to_meta)
            }
            Txt(meta, T.body.mdTight, if (error != null) C.accent.redText else C.text.secondary, Modifier.padding(top = 2.dp), maxLines = 2)
        }
        StartButton(
            StartSize.S, stringResource(R.string.common_go), enabled,
            cd = if (enabled) stringResource(R.string.common_go) else stringResource(R.string.cd_start_disabled_destination),
            onClick = onStart, modifier = Modifier.testTag("navigator.start"),
        )
    }
}
