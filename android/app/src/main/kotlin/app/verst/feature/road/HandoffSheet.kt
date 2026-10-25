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
import androidx.compose.foundation.layout.height
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.HandoffDto
import app.verst.core.model.dto.TripDto
import app.verst.core.ui.R
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.PlaceholderPlate
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.nav.HandoffApp
import app.verst.nav.HandoffSheet
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** What the hand-off sheet needs besides the sheet state (installed apps, signing, «Запомнить выбор»). */
data class HandoffSheetUi(
    val sheet: HandoffSheet,
    val mapsInstalled: Boolean,
    val naviInstalled: Boolean,
    val signed: Boolean,
    val remember: Boolean,
)

interface HandoffSheetActions {
    fun scope(day: Int?)
    fun pick(app: HandoffApp)
    fun install(app: HandoffApp)
    fun remember()
    fun close()
}

/**
 * 5.13 §5 (S4) the hand-off sheet: tabs «День N» … «До след.», the scope line, two `HandoffAppCard`s (the
 * recommended one first: unsigned day → Карты with the whole day, «До след.» → Навигатор), the explanation,
 * «Запомнить выбор».
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
        Row(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(C.dash.well).padding(4.dp)
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
        Txt(line, T.body.md, C.text.secondary, Modifier.padding(top = 10.dp, bottom = 12.dp).testTag("handoff.line"), maxLines = 2)
        if (h == null) {
            // the engine's links arrive within a moment (never a guessed route)
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                PlaceholderPlate(350.dp, 72.dp, C.dash.controlAlt)
                PlaceholderPlate(350.dp, 72.dp, C.dash.controlAlt)
            }
        } else {
            val mapsCard: @Composable (Boolean) -> Unit = { rec ->
                AppCard(
                    HandoffApp.MAPS, stringResource(R.string.handoff_app_maps),
                    if (next) stringResource(R.string.handoff_maps_next) else stringResource(R.string.handoff_maps_day, pointsText),
                    if (ui.mapsInstalled) null else stringResource(R.string.handoff_maps_missing),
                    recommended = rec, badge = rec && !next, installed = true, dimGlyph = !ui.mapsInstalled, a = a,
                )
            }
            val naviCard: @Composable (Boolean) -> Unit = { rec ->
                val sub = if (ui.signed && !next) stringResource(R.string.handoff_navi_day, pointsText)
                else stringResource(R.string.handoff_navi_next, nextName, RuFormat.thousands(nextKm))
                AppCard(
                    HandoffApp.NAVI, stringResource(R.string.handoff_app_navi), sub,
                    when {
                        !ui.naviInstalled -> stringResource(R.string.handoff_navi_missing)
                        !ui.signed -> stringResource(R.string.handoff_navi_limit)
                        else -> null
                    },
                    recommended = rec, badge = rec && !next && ui.signed, installed = ui.naviInstalled, dimGlyph = !ui.naviInstalled, a = a,
                )
            }
            val naviFirst = next || ui.signed
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (naviFirst && ui.naviInstalled) {
                    naviCard(true)
                    mapsCard(false)
                } else {
                    mapsCard(true)
                    naviCard(false)
                }
            }
        }
        Txt(
            stringResource(if (ui.signed) R.string.handoff_explain_signed else R.string.handoff_explain_unsigned),
            T.body.smRelaxed, C.text.muted, Modifier.padding(top = 12.dp),
        )
        // «Запомнить выбор» (switch 44 × 26)
        Row(
            Modifier.fillMaxWidth().padding(top = 8.dp).defaultMinSize(minHeight = DesignTokens.size.touchMin)
                .toggleable(ui.remember, role = Role.Switch, onValueChange = { a.remember() }).testTag("handoff.remember"),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Txt(stringResource(R.string.handoff_remember), T.list.title, C.text.primary, Modifier.weight(1f), maxLines = 1)
            Box(
                Modifier.size(44.dp, 26.dp).clip(RoundedCornerShape(13.dp)).background(if (ui.remember) C.accent.yellow else C.dash.controlAlt).padding(3.dp),
                contentAlignment = if (ui.remember) Alignment.CenterEnd else Alignment.CenterStart,
            ) { Box(Modifier.size(20.dp).clip(CircleShape).background(if (ui.remember) C.text.onLight else C.text.muted)) }
        }
    }
}

@Composable
private fun Tab(text: String, cd: String?, selected: Boolean, tag: String, width: Modifier, onClick: () -> Unit) {
    Box(
        width.defaultMinSize(minWidth = 64.dp, minHeight = 40.dp).clip(RoundedCornerShape(9.dp))
            .background(if (selected) C.text.primary else C.dash.well)
            .selectable(selected, role = Role.Tab, onClick = onClick)
            .then(if (cd != null) Modifier.semantics { contentDescription = cd } else Modifier)
            .testTag(tag).padding(horizontal = 10.dp),
        contentAlignment = Alignment.Center,
    ) { Txt(text, T.body.mdStrong, if (selected) C.text.onLight else C.text.secondary, maxLines = 1) }
}

/** components §30 `HandoffAppCard`: glyph square 40, title 17/700 + badge, sub 13/17, note 12, out-arrow 16. */
@Composable
private fun AppCard(
    app: HandoffApp, title: String, sub: String, note: String?, recommended: Boolean, badge: Boolean, installed: Boolean, dimGlyph: Boolean,
    a: HandoffSheetActions,
) {
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    val install = !installed
    val tag = if (app == HandoffApp.MAPS) "handoff.maps" else "handoff.navi"
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 72.dp).clip(shape)
            // recommended fill #1F2A14 has no token: `dash.face` + the 2 dp yellow border (dev-notes S4)
            .background(C.dash.face)
            .border(if (recommended) DesignTokens.stroke.w2 else DesignTokens.stroke.w1, if (recommended) C.accent.yellow else C.dash.controlAlt, shape)
            .clickable(role = Role.Button) { if (install) a.install(app) else a.pick(app) }
            .semantics(mergeDescendants = true) {}
            .testTag(tag)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Box(
            Modifier.size(40.dp).clip(RoundedCornerShape(10.dp)).background(if (dimGlyph) C.dash.controlAlt else C.sign.white),
            contentAlignment = Alignment.Center,
        ) {
            GlyphIcon(if (app == HandoffApp.MAPS) Glyph.PIN else Glyph.NAVIGATOR, if (dimGlyph) C.text.muted else C.text.onLight, 22.dp, filled = app == HandoffApp.NAVI)
        }
        Column(Modifier.weight(1f).alpha(if (install) 0.55f else 1f)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Txt(title, T.title.md, C.text.primary, maxLines = 1)
                if (badge) {
                    Box(Modifier.height(20.dp).clip(RoundedCornerShape(4.dp)).background(C.accent.yellow).padding(horizontal = 6.dp).testTag("$tag.badge"), contentAlignment = Alignment.Center) {
                        Txt(stringResource(R.string.handoff_badge_day), T.tag.kind, C.text.onLight, maxLines = 1)
                    }
                }
            }
            Txt(sub, T.body.md, C.text.note, Modifier.padding(top = 2.dp))
            if (note != null) Txt(note, T.body.sm, C.navi.labelSecondary, Modifier.padding(top = 2.dp).testTag("$tag.note"))
        }
        if (install) {
            Txt(stringResource(R.string.handoff_install), T.body.smStrong, C.accent.yellow, Modifier.width(96.dp).testTag("$tag.install"))
        } else {
            GlyphIcon(Glyph.UP_RIGHT, C.text.secondary, 16.dp)
        }
    }
}
