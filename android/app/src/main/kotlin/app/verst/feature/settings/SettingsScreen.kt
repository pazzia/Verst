package app.verst.feature.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import app.verst.core.model.AppLanguage
import app.verst.core.model.AppSettings
import app.verst.core.model.AppTheme
import app.verst.core.model.Money
import app.verst.core.model.RatesDto
import app.verst.core.model.TripStorage
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.ScreenRoot
import app.verst.data.net.ServerCheck
import app.verst.engine.PlanSource
import app.verst.settings.BuildSeen
import app.verst.settings.FolderStatus
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** What the build screen shows about the running build (DEV-100 + D-IR-20). */
data class BuildLines(
    val versionName: String,
    val number: Int,
    val gitSha: String,
    val buildDate: String,
    val engine: String?,
    val python: String?,
    val catalogue: String?,
)

/** D-IR-20 personal cabinet: everything here is stored on the phone; there is no account yet. */
data class SettingsUi(
    val settings: AppSettings,
    val rates: RatesDto,
    val build: BuildLines,
    val builds: List<BuildSeen>,
    val folderStatus: FolderStatus?,
    /** The theme picked differs from the palette this process draws with: offer a restart. */
    val themePending: Boolean,
    val copied: Boolean = false,
    /** SRV-01: the backend of this build (null = none), the last connection check and where the last plan ran. */
    val serverUrl: String? = null,
    val serverChecking: Boolean = false,
    val serverCheck: ServerCheck? = null,
    val lastPlan: PlanSource? = null,
)

interface SettingsActions {
    fun back()
    fun language(l: AppLanguage)
    fun currency(code: String)
    fun theme(t: AppTheme)
    fun restart()
    fun storageDevice()
    fun pickFolder()
    fun writeFolderNow()
    fun copyBuild()
    fun developer()
    fun planOnServer(on: Boolean)
    fun checkServer()
}

@Composable
fun SettingsScreen(ui: SettingsUi, a: SettingsActions) {
    ScreenRoot(C.dash.raised) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 12.dp).testTag("settings"),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            val back = stringResource(R.string.common_back_to_windshield)
            BackLink(back, C.text.muted, stringResource(R.string.cd_back, back), a::back)
            Txt(stringResource(R.string.settings_title), T.title.xl, C.text.primary)
            Txt(stringResource(R.string.settings_subtitle), T.body.sm, C.text.secondary)

            Section(stringResource(R.string.settings_language))
            Choices(
                listOf(AppLanguage.RU to stringResource(R.string.settings_language_ru), AppLanguage.EN to stringResource(R.string.settings_language_en)),
                ui.settings.language, "settings.language", a::language,
            )
            Note(stringResource(R.string.settings_language_note))

            Section(stringResource(R.string.settings_currency))
            Choices(Money.SUPPORTED.map { it to "${Money.symbol(it)} $it" }, ui.settings.currency, "settings.currency", a::currency)
            Note(
                ui.rates.asOf?.let { stringResource(R.string.settings_currency_rate, it) } ?: stringResource(R.string.settings_currency_no_rate),
                Modifier.testTag("settings.rate"),
            )

            Section(stringResource(R.string.settings_theme))
            Choices(
                listOf(
                    AppTheme.NIGHT to stringResource(R.string.settings_theme_night),
                    AppTheme.DAY to stringResource(R.string.settings_theme_day),
                    AppTheme.SYSTEM to stringResource(R.string.settings_theme_system),
                ),
                ui.settings.theme, "settings.theme", a::theme,
            )
            if (ui.themePending) {
                Note(stringResource(R.string.settings_theme_restart))
                Button(stringResource(R.string.settings_restart), "settings.restart", C.accent.yellow, C.text.onLight, a::restart)
            }

            Section(stringResource(R.string.settings_storage))
            StorageRow(
                stringResource(R.string.settings_storage_device), stringResource(R.string.settings_storage_device_sub),
                ui.settings.storage == TripStorage.DEVICE, enabled = true, tag = "settings.storage.device", onClick = a::storageDevice,
            )
            StorageRow(
                stringResource(R.string.settings_storage_folder),
                ui.settings.folderName?.takeIf { ui.settings.storage == TripStorage.FOLDER }
                    ?.let { "$it · " + stringResource(R.string.settings_storage_folder_sub, FILE) }
                    ?: stringResource(R.string.settings_storage_folder_sub, FILE),
                ui.settings.storage == TripStorage.FOLDER, enabled = true, tag = "settings.storage.folder", onClick = a::pickFolder,
            )
            if (ui.settings.storage == TripStorage.FOLDER) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(stringResource(R.string.settings_storage_folder_pick), "settings.folder.pick", C.dash.control, C.text.primary, a::pickFolder)
                    Button(stringResource(R.string.settings_storage_folder_now), "settings.folder.now", C.dash.control, C.text.primary, a::writeFolderNow)
                }
                when (val s = ui.folderStatus) {
                    is FolderStatus.Written -> Note(stringResource(R.string.settings_storage_folder_written, time(s.at), s.trips), Modifier.testTag("settings.folder.status"))
                    is FolderStatus.Failed -> Txt(stringResource(R.string.settings_storage_folder_failed, s.reason), T.body.sm, C.accent.redText, Modifier.testTag("settings.folder.status"))
                    null -> Unit
                }
            }
            StorageRow(
                stringResource(R.string.settings_storage_cloud), stringResource(R.string.settings_storage_cloud_sub),
                selected = false, enabled = false, tag = "settings.storage.cloud", onClick = {},
            )

            Section(stringResource(R.string.settings_server))
            if (ui.serverUrl == null) {
                Note(stringResource(R.string.settings_server_none), Modifier.testTag("settings.server.none"))
            } else {
                Note(stringResource(R.string.settings_server_url, ui.serverUrl))
                Choices(
                    listOf(false to stringResource(R.string.settings_server_plan_phone), true to stringResource(R.string.settings_server_plan_server)),
                    ui.settings.planOnServer, "settings.server.plan", a::planOnServer,
                )
                Note(stringResource(R.string.settings_server_note))
                Button(stringResource(R.string.settings_server_check), "settings.server.check", C.dash.control, C.text.primary, a::checkServer)
                val status = when {
                    ui.serverChecking -> stringResource(R.string.settings_server_checking)
                    ui.serverCheck is ServerCheck.Ok && ui.serverCheck.registered -> stringResource(R.string.settings_server_ok, ui.serverCheck.ms)
                    ui.serverCheck is ServerCheck.Ok -> stringResource(R.string.settings_server_ok_unregistered, ui.serverCheck.ms)
                    ui.serverCheck is ServerCheck.Failed -> stringResource(R.string.settings_server_failed, ui.serverCheck.reason)
                    else -> null
                }
                if (status != null) {
                    val failed = ui.serverCheck is ServerCheck.Failed && !ui.serverChecking
                    Txt(status, T.body.sm, if (failed) C.accent.redText else C.text.secondary, Modifier.testTag("settings.server.status"))
                }
                ui.lastPlan?.let { p ->
                    Note(
                        if (p.server) stringResource(R.string.settings_server_last_server, p.ms)
                        else stringResource(R.string.settings_server_last_phone, p.fallbackReason ?: "—"),
                        Modifier.testTag("settings.server.last"),
                    )
                }
            }

            Section(stringResource(R.string.settings_build))
            val b = ui.build
            Column(
                Modifier.fillMaxWidth().background(C.dash.control, RoundedCornerShape(12.dp)).padding(12.dp).testTag("settings.build"),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Txt(stringResource(R.string.settings_build_version, b.versionName, b.number), T.body.mdStrong, C.text.primary)
                Txt(stringResource(R.string.settings_build_commit, b.gitSha.take(12)), T.body.sm, C.text.secondary)
                Txt(stringResource(R.string.settings_build_date, b.buildDate), T.body.sm, C.text.secondary)
                if (b.engine != null) Txt(stringResource(R.string.settings_build_engine, b.engine, b.python ?: "—"), T.body.sm, C.text.secondary)
                if (b.catalogue != null) Txt(stringResource(R.string.settings_build_catalogue, b.catalogue), T.body.sm, C.text.secondary)
            }
            Button(
                stringResource(if (ui.copied) R.string.settings_build_copied else R.string.settings_build_copy),
                "settings.build.copy", C.dash.control, C.text.primary, a::copyBuild,
            )
            if (ui.builds.isNotEmpty()) {
                Section(stringResource(R.string.settings_builds_seen))
                ui.builds.take(10).forEach { s ->
                    Txt(stringResource(R.string.settings_builds_row, s.number, s.gitSha.take(7), date(s.firstRunAt)), T.body.sm, C.text.secondary)
                }
            }
            Button(stringResource(R.string.settings_dev), "settings.dev", C.dash.control, C.text.muted, a::developer)
        }
    }
}

private const val FILE = app.verst.settings.MirroringTripStore.FILE

private fun time(ms: Long): String = SimpleDateFormat("dd.MM HH:mm", Locale.ROOT).format(Date(ms))

private fun date(ms: Long): String = SimpleDateFormat("dd.MM.yyyy", Locale.ROOT).format(Date(ms))

@Composable
private fun Section(text: String) = Txt(text, T.label.md, C.text.muted, Modifier.padding(top = 8.dp))

@Composable
private fun Note(text: String, modifier: Modifier = Modifier) = Txt(text, T.body.sm, C.text.secondary, modifier)

@Composable
private fun <K> Choices(options: List<Pair<K, String>>, current: K, tag: String, onPick: (K) -> Unit) {
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (key, label) ->
            val on = key == current
            Box(
                Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin)
                    .background(if (on) C.sign.white else C.dash.control, RoundedCornerShape(10.dp))
                    .clickable(role = Role.RadioButton) { onPick(key) }
                    .semantics { selected = on }
                    .testTag("$tag.$key").padding(horizontal = 12.dp),
                contentAlignment = Alignment.Center,
            ) { Txt(label, T.body.mdStrong, if (on) C.text.onLight else C.text.secondary, maxLines = 1) }
        }
    }
}

@Composable
private fun StorageRow(title: String, sub: String, selected: Boolean, enabled: Boolean, tag: String, onClick: () -> Unit) {
    val border = if (selected) C.sign.white else C.dash.outline
    Column(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 56.dp)
            .border(DesignTokens.stroke.w1, border, RoundedCornerShape(12.dp))
            .clickable(enabled = enabled, role = Role.RadioButton, onClick = onClick)
            .semantics { this.selected = selected }
            .testTag(tag).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Txt(title, T.body.mdStrong, if (enabled) C.text.primary else C.text.disabled)
        Txt(sub, T.body.sm, if (enabled) C.text.secondary else C.text.disabled)
    }
}

@Composable
private fun Button(label: String, tag: String, fill: Color, text: Color, onClick: () -> Unit) {
    Box(
        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .background(fill, RoundedCornerShape(12.dp))
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label }
            .testTag(tag).padding(horizontal = 16.dp),
        contentAlignment = Alignment.Center,
    ) { Txt(label, T.button.md, text) }
}
