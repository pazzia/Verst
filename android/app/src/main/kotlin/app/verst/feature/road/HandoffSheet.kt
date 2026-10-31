package app.verst.feature.road

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.TripDto
import app.verst.core.ui.R
import app.verst.core.ui.components.CraftBadge
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftIconTile
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.PlaceholderPlate
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.nav.HandoffApp
import app.verst.nav.HandoffSheet
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/**
 * What the hand-off sheet needs besides the sheet state: installed apps, «Запомнить выбор», and (CEO 29.10) the maps
 * app that leads here — [preferred] is Яндекс Карты ([HandoffApp.MAPS]) or Google Карты ([HandoffApp.GOOGLE]);
 * [chosen] = the user picked it in «Настройки» (badge «ваш выбор»), else it follows the country («рекомендуем здесь»).
 */
data class HandoffSheetUi(
    val sheet: HandoffSheet,
    val mapsInstalled: Boolean,
    val naviInstalled: Boolean,
    val remember: Boolean,
    val preferred: HandoffApp = HandoffApp.MAPS,
    val googleInstalled: Boolean = false,
    val chosen: Boolean = false,
)

interface HandoffSheetActions {
    fun scope(day: Int?)
    fun pick(app: HandoffApp)
    fun install(app: HandoffApp)
    fun remember()
    fun close()
}

/**
 * 5.13 §5 (S4) the hand-off sheet: tabs «День N» … «До след.», the scope line, the `HandoffAppCard`s, the
 * explanation, «Запомнить выбор». CEO 29.10: the preferred maps app first with its badge, the other maps app second
 * (both take every point of the day in order), the Навигатор last — it takes one point from us, so it goes to the
 * next point only.
 */
@Composable
fun BoxScope.HandoffSheetView(trip: TripDto, ui: HandoffSheetUi, windowH: Dp, a: HandoffSheetActions) {
    val sheet = ui.sheet
    val next = sheet.day == null
    val dayDto = trip.daysList.firstOrNull { it.day == sheet.handoffDay }
    val h = sheet.handoff
    BottomSheet(stringResource(R.string.handoff_sheet_title), a::close, "handoff", windowH) {
        // tabs (segmented): the days and «До след.»; more than 3 days scroll horizontally
        val count = trip.daysList.size + 1
        val scroll = count > 4
        // fork camper-ui: a white-paper field (craftField) with orange craft keys for the picked scope
        Row(
            Modifier.fillMaxWidth().craftField().padding(4.dp)
                .then(if (scroll) Modifier.horizontalScroll(rememberScrollState()) else Modifier).selectableGroup(),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            val w = if (scroll) Modifier else Modifier.weight(1f)
            trip.daysList.forEach { d ->
                Tab(stringResource(R.string.handoff_scope_day, d.day), null, !next && sheet.handoffDay == d.day, "handoff.tab.${d.day}", w) { a.scope(d.day) }
            }
            Tab(stringResource(R.string.handoff_scope_next), stringResource(R.string.handoff_cd_scope_next), next, "handoff.tab.next", w) { a.scope(null) }
        }
        // the scope line
        val part = h?.parts?.firstOrNull()
        val points = part?.points?.size?.takeIf { it > 0 } ?: dayDto?.stops?.count { it.lat != null } ?: 0
        val pointsText = "$points ${pluralStringResource(R.plurals.plural_point, points)}"
        val nextPt = part?.next ?: part?.points?.firstOrNull { it.role != "origin" }
        val nextName = nextPt?.nameRu ?: dayDto?.stops?.getOrNull(1)?.name ?: ""
        val nextKm = dayDto?.stops?.firstOrNull { it.name == nextName }?.kmFromPrev ?: dayDto?.stops?.getOrNull(1)?.kmFromPrev ?: 0
        val line = if (next) stringResource(R.string.handoff_next_line, nextName, RuFormat.thousands(nextKm))
        else stringResource(
            R.string.handoff_day_line, dayDto?.stops?.firstOrNull()?.name ?: "", dayDto?.stops?.lastOrNull()?.name ?: "",
            RuFormat.thousands(dayDto?.km ?: 0), pointsText,
        )
        Txt(line, T.body.md, C.camper.inkSoft, Modifier.padding(top = 10.dp, bottom = 12.dp).testTag("handoff.line"), maxLines = 2)
        if (h == null) {
            // the engine's links arrive within a moment (never a guessed route)
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                PlaceholderPlate(350.dp, 72.dp, C.camper.header)
                PlaceholderPlate(350.dp, 72.dp, C.camper.header)
                PlaceholderPlate(350.dp, 72.dp, C.camper.header)
            }
        } else {
            val badge = stringResource(if (ui.chosen) R.string.handoff_badge_chosen else R.string.handoff_badge_here)
            val yandexCard: @Composable (Boolean) -> Unit = { rec ->
                AppCard(
                    HandoffApp.MAPS, stringResource(R.string.handoff_app_maps),
                    if (next) stringResource(R.string.handoff_maps_next) else stringResource(R.string.handoff_maps_day, pointsText),
                    if (ui.mapsInstalled) null else stringResource(R.string.handoff_maps_missing),
                    badge = if (rec) badge else null, installed = true, dimGlyph = !ui.mapsInstalled, a = a,
                )
            }
            val googleCard: @Composable (Boolean) -> Unit = { rec ->
                AppCard(
                    HandoffApp.GOOGLE, stringResource(R.string.handoff_app_google),
                    if (next) stringResource(R.string.handoff_maps_next) else stringResource(R.string.handoff_google_day, pointsText),
                    if (ui.googleInstalled) null else stringResource(R.string.handoff_google_missing),
                    badge = if (rec) badge else null, installed = true, dimGlyph = !ui.googleInstalled, a = a,
                )
            }
            // the end / bottom padding keep the recommended card's hard shadow inside the sheet
            Column(Modifier.padding(end = CraftDefaults.ShadowX, bottom = CraftDefaults.ShadowY), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (ui.preferred == HandoffApp.GOOGLE) {
                    googleCard(true)
                    yandexCard(false)
                } else {
                    yandexCard(true)
                    googleCard(false)
                }
                // the Навигатор: a secondary option, to the next point only (no via points without Яндекс's signature)
                AppCard(
                    HandoffApp.NAVI, stringResource(R.string.handoff_app_navi),
                    stringResource(R.string.handoff_navi_next, nextName, RuFormat.thousands(nextKm)),
                    if (ui.naviInstalled) stringResource(R.string.handoff_navi_limit) else stringResource(R.string.handoff_navi_missing),
                    badge = null, installed = ui.naviInstalled, dimGlyph = !ui.naviInstalled, a = a,
                )
            }
        }
        Txt(stringResource(R.string.handoff_explain), T.body.smRelaxed, C.camper.inkMuted, Modifier.padding(top = 12.dp))
        // «Запомнить выбор» (switch 44 × 26)
        Row(
            Modifier.fillMaxWidth().padding(top = 8.dp).defaultMinSize(minHeight = DesignTokens.size.touchMin)
                .toggleable(ui.remember, role = Role.Switch, onValueChange = { a.remember() }).testTag("handoff.remember"),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Txt(stringResource(R.string.handoff_remember), T.list.title, C.camper.ink, Modifier.weight(1f), maxLines = 1)
            // the craft switch: a 2 dp brown frame, orange track when on, a white-paper knob with a brown rim
            Box(
                Modifier.size(46.dp, 28.dp).clip(RoundedCornerShape(14.dp)).background(if (ui.remember) C.camper.orange else C.camper.header)
                    .border(CraftDefaults.BorderThin, C.camper.border, RoundedCornerShape(14.dp)).padding(4.dp),
                contentAlignment = if (ui.remember) Alignment.CenterEnd else Alignment.CenterStart,
            ) { Box(Modifier.size(18.dp).clip(CircleShape).background(C.camper.field).border(1.5.dp, C.camper.border, CircleShape)) }
        }
    }
}

@Composable
private fun Tab(text: String, cd: String?, selected: Boolean, tag: String, width: Modifier, onClick: () -> Unit) {
    val shape = RoundedCornerShape(10.dp)
    Box(
        width.defaultMinSize(minWidth = 64.dp, minHeight = 40.dp).clip(shape)
            .background(if (selected) C.camper.orange else Color.Transparent)
            .then(if (selected) Modifier.border(CraftDefaults.BorderThin, C.camper.border, shape) else Modifier)
            .selectable(selected, role = Role.Tab, onClick = onClick)
            .then(if (cd != null) Modifier.semantics { contentDescription = cd } else Modifier)
            .testTag(tag).padding(horizontal = 10.dp),
        contentAlignment = Alignment.Center,
    ) { Txt(text, T.body.mdStrong, if (selected) C.camper.onOrange else C.camper.ink, maxLines = 1) }
}

/**
 * components §30 `HandoffAppCard`, fork camper-ui: a craft card — icon tile 40, title 17/700 + amber badge, sub, note,
 * out-arrow 16. A card with a [badge] is the recommended one (white paper, the 2.5 dp border and the hard shadow);
 * the others are flat paper with the 2 dp border.
 */
@Composable
private fun AppCard(
    app: HandoffApp, title: String, sub: String, note: String?, badge: String?, installed: Boolean, dimGlyph: Boolean,
    a: HandoffSheetActions,
) {
    val install = !installed
    val recommended = badge != null
    val tag = when (app) {
        HandoffApp.MAPS -> "handoff.maps"
        HandoffApp.GOOGLE -> "handoff.google"
        HandoffApp.NAVI -> "handoff.navi"
    }
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 72.dp)
            .craftSurface(
                fill = if (recommended) C.camper.field else C.camper.paper, radius = 16.dp,
                border = if (recommended) CraftDefaults.Border else CraftDefaults.BorderThin,
                shadow = if (recommended) C.camper.shadow else null,
            )
            .clickable(role = Role.Button) { if (install) a.install(app) else a.pick(app) }
            .semantics(mergeDescendants = true) {}
            .testTag(tag)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        CraftIconTile(
            if (app == HandoffApp.NAVI) R.drawable.ic_ui_location_arrow else R.drawable.ic_ui_route,
            active = recommended && !dimGlyph, size = 40.dp,
            fill = if (dimGlyph) C.camper.header else null, tint = if (dimGlyph) C.camper.inkMuted else null,
        )
        Column(Modifier.weight(1f)) {
          Column(Modifier.alpha(if (install) 0.55f else 1f)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Txt(title, T.title.md, C.camper.ink, maxLines = 1)
                if (badge != null) CraftBadge(badge, Modifier.testTag("$tag.badge"))
            }
            Txt(sub, T.body.md, C.camper.inkSoft, Modifier.padding(top = 2.dp))
            if (note != null) Txt(note, T.body.sm, C.camper.inkSoft, Modifier.padding(top = 2.dp).testTag("$tag.note"))
          }
            // S4-QA P2-05 / components §30: «Установить…» is the orange note line, not a right column
            if (install) Txt(stringResource(R.string.handoff_install), T.body.sm, C.camper.orangeText, Modifier.padding(top = 2.dp).testTag("$tag.install"))
        }
        if (!install) GlyphIcon(Glyph.UP_RIGHT, C.camper.inkSoft, 16.dp)
    }
}
