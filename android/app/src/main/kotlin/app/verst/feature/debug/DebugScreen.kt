package app.verst.feature.debug

import app.verst.data.net.OnlineStats
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import app.verst.BuildConfig
import app.verst.VerstApp
import app.verst.R as AppR
import app.verst.feature.road.AboutDataSheet
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.engine.EngineStatus
import app.verst.feature.common.NaviDialog
import app.verst.feature.common.ScreenRoot
import app.verst.nav.VerstFlow
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T
import app.verst.nav.closeAboutData
import app.verst.nav.locate
import app.verst.nav.openAboutData

/**
 * DEV-127 debug panel (architecture-android-mvp §9): a plain list, not part of visual QA. World, clock (system /
 * golden), simulated offline, slow plan, forced engine error, engine timings, build, reset data.
 * Entry: a 2 s long-press on «НАВИГАТОР» on the Windshield (there is no D-4 settings sheet yet).
 */
@Composable
fun DebugScreen(flow: VerstFlow) {
    val app = LocalContext.current.applicationContext as VerstApp
    val status by app.engine.status.collectAsState()
    val catalogueMs by app.engine.catalogueMs.collectAsState()
    ScreenRoot(C.dash.raised) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp).testTag("debug"), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            val back = stringResource(R.string.common_back_to_windshield)
            BackLink(back, C.text.muted, stringResource(R.string.cd_back, back), { flow.back() })
            Txt(stringResource(R.string.debug_label_title), T.title.xl, C.text.primary)
            Label(stringResource(R.string.debug_label_world))
            Choices(listOf("russia_v1", "central_russia_v1", "edge_cases_v1"), flow.debugWorld, "debug.world") { flow.setWorld(it) }
            Label(stringResource(R.string.debug_label_clock))
            Choices(
                listOf(stringResource(R.string.debug_clock_system), stringResource(R.string.debug_clock_golden)),
                if (flow.debugGolden) stringResource(R.string.debug_clock_golden) else stringResource(R.string.debug_clock_system), "debug.clock",
            ) { flow.setGoldenClock(it == app.getString(R.string.debug_clock_golden)) }
            Label(stringResource(R.string.debug_label_offline))
            Choices(listOf("0", "1"), if (flow.connectivity.online) "0" else "1", "debug.offline") { flow.setOffline(it == "1") }
            Label(stringResource(R.string.debug_label_slow))
            Choices(listOf("0", "5", "25"), flow.debugSlowSec.toString(), "debug.slow") { flow.debugSlowSec = it.toInt() }
            Label(stringResource(R.string.debug_label_force_error))
            val none = stringResource(R.string.debug_force_none)
            Choices(listOf(none, "INTERNAL", "UNREACHABLE", "TOO_SHORT", "INVALID_INPUT"), flow.debugForceError ?: none, "debug.error") {
                flow.debugForceError = if (it == none) null else it
            }
            // S3-R1: a fixed position instead of the phone's (e2e; on the emulator also `adb emu geo fix`).
            Label(stringResource(R.string.debug_mock_location))
            Choices(listOf(none) + MockPlaces.keys, flow.debugMockLocation?.label ?: none, "debug.mock") {
                flow.debugMockLocation = MockPlaces[it]
                if (flow.debugMockLocation != null) flow.locate()
            }
            // S3-R3: real Commons files on the cards (ADR-0012 §6 URLs), before the data run brings them
            Label(stringResource(R.string.debug_real_photos))
            Choices(listOf("0", "1"), if (flow.debugRealPhotos) "1" else "0", "debug.photos") { flow.debugRealPhotos = it == "1" }
            flow.lastHandoff?.let { (h, target) ->
                Txt("$target · ${h.navigator ?: h.maps ?: h.web}", T.body.sm, C.text.secondary, Modifier.testTag("debug.handoff"))
            }
            // ADR-0016 OR-8: online failures go here, never to the user (host · requests / failures / blocked / dropped)
            val online = OnlineStats.snapshot()
            if (online.isNotEmpty()) {
                Txt(
                    online.entries.joinToString("\n") { e -> val h: OnlineStats.Host = e.value; "${e.key} · ${h.requests} / ${h.failures} / ${h.blocked} / ${h.dropped} · ${h.lastCode ?: "—"} · ${h.lastMs} ms" },
                    T.body.sm, C.text.secondary, Modifier.testTag("debug.online"),
                )
            }
            Label(stringResource(R.string.debug_label_timings))
            val s = status
            Txt(
                if (s is EngineStatus.Ready) s.info.timings.let { "python ${it.pythonStartMs} · import ${it.importMs} · worlds ${it.worldsMs} · selfcheck ${it.selfcheckMs} · ready ${it.totalMs} · catalogue ${catalogueMs ?: "…"} ms" } else s.toString(),
                T.body.md, C.text.secondary,
            )
            // DEV-300: «О данных» (Wikidata CC0, OSM ODbL, Commons per-file licences, approximate distances)
            Box(
                Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp).clip12().border(DesignTokens.stroke.w1, C.dash.outline, RoundedCornerShape(12.dp))
                    .clickable(role = Role.Button) { flow.openAboutData() }.testTag("debug.about"),
                contentAlignment = Alignment.Center,
            ) { Txt(stringResource(R.string.about_data_title), T.button.md, C.text.primary) }
            Label(stringResource(R.string.debug_label_build))
            Txt(stringResource(R.string.mock_build_line, BuildConfig.BUILD_NUMBER, BuildConfig.GIT_SHA), T.body.md, C.text.secondary)
            Box(
                Modifier.fillMaxWidth().defaultMinSize(minHeight = 48.dp).clip12().border(DesignTokens.stroke.w1, C.accent.redText, RoundedCornerShape(12.dp))
                    .clickable(role = Role.Button) { flow.askReset() }.testTag("debug.reset"),
                contentAlignment = Alignment.Center,
            ) { Txt(stringResource(R.string.debug_reset), T.button.md, C.accent.redText) }
        }
        if (flow.aboutData) {
            androidx.compose.foundation.layout.BoxWithConstraints(Modifier.matchParentSize()) {
                val h = maxHeight
                androidx.compose.foundation.layout.Box(Modifier.matchParentSize()) { AboutDataSheet(h, flow::closeAboutData) }
            }
        }
        // Release review P2-3: «Сбросить данные» deletes every saved trip — ask first.
        if (flow.resetAsk) {
            NaviDialog(
                stringResource(R.string.debug_reset_title), stringResource(R.string.debug_reset_body),
                stringResource(R.string.debug_reset_yes), stringResource(R.string.debug_reset_no), "reset",
                flow::resetData, flow::cancelReset,
            )
        }
    }
}

/** Mock positions: near fixture towns, and one far from any (the nearest-town fallback). */
private val MockPlaces = linkedMapOf(
    "Ярославль" to app.verst.core.model.GeoPoint("Ярославль", 57.6261, 39.8845),
    "Тула" to app.verst.core.model.GeoPoint("Тула", 54.1931, 37.6177),
    "Владимир" to app.verst.core.model.GeoPoint("Владимир", 56.1290, 40.4066),
    "поле" to app.verst.core.model.GeoPoint("поле", 58.40, 43.90),
)

private fun Modifier.clip12() = this.then(Modifier.background(C.dash.raised, RoundedCornerShape(12.dp)))

@Composable
private fun Label(text: String) = Txt(text, T.label.md, C.text.muted)

@Composable
private fun Choices(options: List<String>, current: String, tag: String, onPick: (String) -> Unit) {
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { o ->
            val on = o == current
            Box(
                Modifier.defaultMinSize(minHeight = 44.dp).background(if (on) C.sign.white else C.dash.control, RoundedCornerShape(10.dp))
                    .clickable(role = Role.RadioButton) { onPick(o) }.testTag("$tag.$o").padding(horizontal = 12.dp),
                contentAlignment = Alignment.Center,
            ) { Txt(o, T.body.mdStrong, if (on) C.text.onLight else C.text.secondary, maxLines = 1) }
        }
    }
}
