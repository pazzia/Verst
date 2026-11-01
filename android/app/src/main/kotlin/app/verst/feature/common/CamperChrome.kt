package app.verst.feature.common

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsBottomHeight
import androidx.compose.foundation.layout.windowInsetsTopHeight
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.isTraversalGroup
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import app.verst.core.ui.R
import app.verst.core.ui.components.CraftIconTile
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.nav.AppTab
import app.verst.core.ui.theme.DesignTokens.color as C

/*
 * Fork camper-ui (CEO 31.10): the app chrome of the «Кемпер-гид» design around every screen — the header (logo
 * tile, «ВЕРСТА», «КЕМПЕР-ГИД», gear → Settings) and the bottom tab bar. Drawn by `VerstRoot` (MainActivity); the
 * screens get the height between them. Both bars paint under their system bar (status / navigation) themselves.
 */

/** Height of the header row below the status bar. */
val AppHeaderHeight = 56.dp

/** Height of the tab bar above the navigation bar. */
val AppTabBarHeight = 60.dp

/**
 * The header: amber logo tile with the van, wordmark and tagline, the gear on the right. [onScrim] non-null =
 * a sheet of the screen is open: the header is dimmed like the screen and a tap closes the sheet.
 */
@Composable
fun AppHeader(settingsActive: Boolean, onSettings: () -> Unit, onScrim: (() -> Unit)?, modifier: Modifier = Modifier) {
    val settingsCd = stringResource(R.string.settings_entry_cd)
    Box(modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().background(C.camper.header).testTag("app.header")) {
            Spacer(Modifier.fillMaxWidth().windowInsetsTopHeight(WindowInsets.statusBars))
            Row(
                Modifier.fillMaxWidth().height(AppHeaderHeight).padding(start = 14.dp, end = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                CraftIconTile(R.drawable.ic_ui_van, active = false, size = 32.dp, fill = C.camper.amber, tint = C.camper.border)
                Column(Modifier.weight(1f).semantics(mergeDescendants = true) { heading() }) {
                    Txt(stringResource(R.string.camper_brand), CraftType.wordmark, C.camper.ink, maxLines = 1)
                    Txt(stringResource(R.string.camper_tagline), CraftType.overline, C.camper.orangeText, maxLines = 1)
                }
                Box(
                    Modifier
                        .size(DesignTokens.size.touchMin)
                        .clip(RoundedCornerShape(DesignTokens.radius.r8))
                        .clickable(enabled = onScrim == null, role = Role.Button, onClick = onSettings)
                        .semantics { contentDescription = settingsCd }
                        .testTag("app.header.settings"),
                    contentAlignment = Alignment.Center,
                ) { CraftIconTile(R.drawable.ic_ui_gear, active = settingsActive, size = 30.dp) }
            }
            Box(Modifier.fillMaxWidth().height(2.dp).background(C.camper.border))
        }
        if (onScrim != null) BarScrim(onScrim)
    }
}

/**
 * The bottom tab bar: Старт / Приборы / Дорога / Пешком / Путевой. [enabled] false = dimmed, not clickable
 * (Дорога and Путевой without a trip); [onScrim] as in [AppHeader].
 */
@Composable
fun AppTabBar(
    active: AppTab,
    enabled: (AppTab) -> Boolean,
    onTab: (AppTab) -> Unit,
    onScrim: (() -> Unit)?,
    modifier: Modifier = Modifier,
) {
    val needTrip = stringResource(R.string.cd_camper_tab_need_trip)
    val tabsCd = stringResource(R.string.cd_camper_tabs)
    Box(modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth().background(C.camper.header)) {
            Box(Modifier.fillMaxWidth().height(2.dp).background(C.camper.border))
            Row(
                Modifier
                    .fillMaxWidth()
                    .height(AppTabBarHeight)
                    .padding(horizontal = 6.dp)
                    .semantics {
                        isTraversalGroup = true
                        contentDescription = tabsCd
                    },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                for (tab in AppTab.entries) {
                    val on = tab == active
                    val can = enabled(tab)
                    val label = stringResource(tabLabel(tab))
                    Column(
                        Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .clip(RoundedCornerShape(DesignTokens.radius.r10))
                            .clickable(enabled = can && onScrim == null, role = Role.Tab) { onTab(tab) }
                            .semantics {
                                selected = on
                                if (!can) stateDescription = needTrip
                            }
                            .testTag(tabTag(tab))
                            .alpha(if (can) 1f else 0.4f),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(4.dp, Alignment.CenterVertically),
                    ) {
                        CraftIconTile(tabIcon(tab), active = on, size = 30.dp)
                        Txt(label, CraftType.tab, if (on) C.camper.orangeText else C.camper.inkMuted, maxLines = 1)
                    }
                }
            }
            Spacer(Modifier.fillMaxWidth().windowInsetsBottomHeight(WindowInsets.navigationBars))
        }
        if (onScrim != null) BarScrim(onScrim)
    }
}

/** The screen's sheet scrim continued over a bar; a tap closes the sheet (like a tap on the screen's scrim). */
@Composable
private fun androidx.compose.foundation.layout.BoxScope.BarScrim(onTap: () -> Unit) {
    Box(
        Modifier
            .matchParentSize()
            .background(C.overlay.scrim)
            .clickable(remember { MutableInteractionSource() }, indication = null, onClick = onTap),
    )
}

/** testTags of the tabs (the e2e journey taps them). */
fun tabTag(tab: AppTab): String = when (tab) {
    AppTab.WINDSHIELD -> "tab.windshield"
    AppTab.INSTRUMENTS -> "tab.instruments"
    AppTab.ROAD -> "tab.road"
    AppTab.CITY -> "tab.city"
    AppTab.WAYBILL -> "tab.waybill"
}

private fun tabLabel(tab: AppTab): Int = when (tab) {
    AppTab.WINDSHIELD -> R.string.camper_tab_windshield
    AppTab.INSTRUMENTS -> R.string.camper_tab_instruments
    AppTab.ROAD -> R.string.camper_tab_road
    AppTab.CITY -> R.string.camper_tab_city
    AppTab.WAYBILL -> R.string.camper_tab_waybill
}

private fun tabIcon(tab: AppTab): Int = when (tab) {
    AppTab.WINDSHIELD -> R.drawable.ic_ui_compass
    AppTab.INSTRUMENTS -> R.drawable.ic_ui_sliders
    AppTab.ROAD -> R.drawable.ic_ui_route
    AppTab.CITY -> R.drawable.ic_tourist_walk
    AppTab.WAYBILL -> R.drawable.ic_ui_receipt
}
