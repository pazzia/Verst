package app.verst.feature.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import app.verst.core.model.AppLanguage
import app.verst.core.model.AppSettings
import app.verst.core.model.AppTheme
import app.verst.core.model.Car
import app.verst.core.model.MapsApp
import app.verst.core.model.MapsChoice
import app.verst.core.model.MapsCountries
import app.verst.core.model.Money
import app.verst.core.model.RatesDto
import app.verst.core.model.TripStorage
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftChip
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftSecondaryButton
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.DashedDivider
import app.verst.core.ui.components.StepperKey
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.NaviDialog
import app.verst.feature.common.ScreenRoot
import app.verst.data.net.ServerCheck
import app.verst.engine.PlanSource
import app.verst.settings.BuildSeen
import app.verst.settings.FolderStatus
import java.text.DateFormat
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
    /** Security review В-1: the consent dialog before the first «На сервере». */
    val serverConsentAsk: Boolean = false,
    /** «Отвязать от сервера»: null = not tried, true = done, false = the server did not answer. */
    val serverForgotten: Boolean? = null,
    /** CEO 29.10 «Навигация»: the country the phone is in now (ISO alpha-2), null = unknown. */
    val country: String? = null,
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
    fun serverConsent(agree: Boolean)
    fun openPrivacy()
    fun forgetServer()
    fun consumption(steps: Int)
    fun tank(steps: Int)
    fun fuel(type: String)
    fun avoidTolls(on: Boolean)
    /** CEO 29.10 «Навигация»: automatic / Яндекс Карты / Google Карты. */
    fun mapsApp(choice: MapsChoice) = Unit
}

/**
 * D-IR-20 settings, camper fork (mockup screen 13 «Настройки приложения»): craft cards on the paper page — the car,
 * navigation, language, currency, theme, storage, the server and the build; rows with the label on the left and
 * the control on the right (− value +), choices as craft chips under their label. The app header and the tab bar
 * are drawn around the screen by `VerstRoot`.
 */
@Composable
fun SettingsScreen(ui: SettingsUi, a: SettingsActions) {
    ScreenRoot(C.camper.page) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 4.dp, bottom = 16.dp).testTag("settings"),
            verticalArrangement = Arrangement.spacedBy(CraftDefaults.Gap),
        ) {
            val back = stringResource(R.string.common_back_to_windshield)
            BackLink(back, C.camper.inkSoft, stringResource(R.string.cd_back, back), a::back)
            Column(Modifier.padding(horizontal = 4.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Txt(stringResource(R.string.settings_screen_title), T.title.xl, C.camper.ink, Modifier.semantics { heading() })
                Txt(stringResource(R.string.settings_subtitle), CraftType.caption, C.camper.inkSoft)
            }

            // traveller К4: the car of the cost and «avoid toll roads» of the route
            val st = ui.settings
            SettingsCard(stringResource(R.string.settings_car)) {
                Stepper(
                    stringResource(R.string.settings_consumption), stringResource(R.string.settings_consumption_value, litres(st.consumption, ui.settings.language)),
                    "settings.consumption", stringResource(R.string.cd_settings_consumption_less), stringResource(R.string.cd_settings_consumption_more),
                    st.consumption > Car.CONSUMPTION_MIN, st.consumption < Car.CONSUMPTION_MAX, { a.consumption(-1) }, { a.consumption(1) },
                )
                DashedDivider()
                ChoiceRow(stringResource(R.string.settings_fuel)) {
                    Choices(
                        listOf(
                            "ai92" to stringResource(R.string.settings_fuel_92),
                            "ai95" to stringResource(R.string.settings_fuel_95),
                            "dt" to stringResource(R.string.settings_fuel_dt),
                        ),
                        st.fuelType, "settings.fuel", a::fuel,
                    )
                }
                DashedDivider()
                Stepper(
                    stringResource(R.string.settings_tank), stringResource(R.string.settings_tank_value, st.tankL),
                    "settings.tank", stringResource(R.string.cd_settings_tank_less), stringResource(R.string.cd_settings_tank_more),
                    st.tankL > Car.TANK_MIN, st.tankL < Car.TANK_MAX, { a.tank(-1) }, { a.tank(1) },
                )
                DashedDivider()
                ChoiceRow(stringResource(R.string.settings_tolls)) {
                    Choices(
                        listOf(false to stringResource(R.string.settings_tolls_allow), true to stringResource(R.string.settings_tolls_avoid)),
                        st.avoidTolls, "settings.tolls", a::avoidTolls,
                    )
                }
                Note(stringResource(R.string.settings_car_note))
            }

            // CEO 29.10: which maps app gets the day's route; the line says what «Автоматически» does here and now
            SettingsCard(stringResource(R.string.settings_maps)) {
                Choices(
                    listOf(
                        MapsChoice.AUTO to stringResource(R.string.settings_maps_auto),
                        MapsChoice.YANDEX to stringResource(R.string.handoff_app_maps),
                        MapsChoice.GOOGLE to stringResource(R.string.handoff_app_google),
                    ),
                    st.mapsApp, "settings.maps", a::mapsApp,
                )
                Txt(mapsLine(st.mapsApp, ui.country), DesignTokens.type.body.mdStrong, C.camper.ink, Modifier.testTag("settings.maps.line"))
                Note(stringResource(R.string.handoff_settings_note))
            }

            SettingsCard(stringResource(R.string.settings_language)) {
                Choices(
                    listOf(AppLanguage.RU to stringResource(R.string.settings_language_ru), AppLanguage.EN to stringResource(R.string.settings_language_en)),
                    ui.settings.language, "settings.language", a::language,
                )
                Note(stringResource(R.string.settings_language_note))
            }

            SettingsCard(stringResource(R.string.settings_currency)) {
                Choices(Money.SUPPORTED.map { it to "${Money.symbol(it)} $it" }, ui.settings.currency, "settings.currency", a::currency)
                Note(
                    ui.rates.asOf?.let { stringResource(R.string.settings_currency_rate, isoDate(it, ui.settings.language)) }
                        ?: stringResource(R.string.settings_currency_no_rate),
                    Modifier.testTag("settings.rate"),
                )
            }

            SettingsCard(stringResource(R.string.settings_theme)) {
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
                    CraftButton(stringResource(R.string.settings_restart), a::restart, Modifier.fillMaxWidth().testTag("settings.restart"))
                }
            }

            SettingsCard(stringResource(R.string.settings_storage)) {
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
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Button(stringResource(R.string.settings_storage_folder_pick), "settings.folder.pick", a::pickFolder, Modifier.weight(1f))
                        Button(stringResource(R.string.settings_storage_folder_now), "settings.folder.now", a::writeFolderNow, Modifier.weight(1f))
                    }
                    when (val s = ui.folderStatus) {
                        is FolderStatus.Written -> Note(stringResource(R.string.settings_storage_folder_written, time(s.at, ui.settings.language), s.trips), Modifier.testTag("settings.folder.status"))
                        is FolderStatus.Failed -> Txt(stringResource(R.string.settings_storage_folder_failed, s.reason), CraftType.caption, C.camper.stamp, Modifier.testTag("settings.folder.status"))
                        null -> Unit
                    }
                }
                StorageRow(
                    stringResource(R.string.settings_storage_cloud), stringResource(R.string.settings_storage_cloud_sub),
                    selected = false, enabled = false, tag = "settings.storage.cloud", onClick = {},
                )
            }

            SettingsCard(stringResource(R.string.settings_server)) {
                if (ui.serverUrl == null) {
                    Note(stringResource(R.string.settings_server_none), Modifier.testTag("settings.server.none"))
                } else {
                    Note(stringResource(R.string.settings_server_url, ui.serverUrl))
                    ChoiceRow(stringResource(R.string.settings_server_plan)) {
                        Choices(
                            listOf(false to stringResource(R.string.settings_server_plan_phone), true to stringResource(R.string.settings_server_plan_server)),
                            ui.settings.planOnServer, "settings.server.plan", a::planOnServer,
                        )
                    }
                    Note(stringResource(R.string.settings_server_note))
                    Button(stringResource(R.string.settings_server_privacy), "settings.server.privacy", a::openPrivacy, Modifier.fillMaxWidth())
                    Button(stringResource(R.string.settings_server_check), "settings.server.check", a::checkServer, Modifier.fillMaxWidth())
                    val status = when {
                        ui.serverChecking -> stringResource(R.string.settings_server_checking)
                        ui.serverCheck is ServerCheck.Ok && ui.serverCheck.registered -> stringResource(R.string.settings_server_ok, ui.serverCheck.ms)
                        ui.serverCheck is ServerCheck.Ok -> stringResource(R.string.settings_server_ok_unregistered, ui.serverCheck.ms)
                        ui.serverCheck is ServerCheck.Failed -> stringResource(R.string.settings_server_failed, ui.serverCheck.reason)
                        else -> null
                    }
                    if (status != null) {
                        val failed = ui.serverCheck is ServerCheck.Failed && !ui.serverChecking
                        Txt(status, CraftType.caption, if (failed) C.camper.stamp else C.camper.inkSoft, Modifier.testTag("settings.server.status"))
                    }
                    ui.lastPlan?.let { p ->
                        Note(
                            if (p.server) stringResource(R.string.settings_server_last_server, p.ms)
                            else stringResource(R.string.settings_server_last_phone, p.fallbackReason ?: "—"),
                            Modifier.testTag("settings.server.last"),
                        )
                    }
                    if (st.serverConsent) {
                        Button(stringResource(R.string.settings_server_forget), "settings.server.forget", a::forgetServer, Modifier.fillMaxWidth())
                    }
                    when (ui.serverForgotten) {
                        true -> Note(stringResource(R.string.settings_server_forgotten), Modifier.testTag("settings.server.forgotten"))
                        false -> Txt(stringResource(R.string.settings_server_forget_failed), CraftType.caption, C.camper.stamp, Modifier.testTag("settings.server.forgotten"))
                        null -> Unit
                    }
                }
            }

            SettingsCard(stringResource(R.string.settings_build)) {
                val b = ui.build
                Column(
                    Modifier.fillMaxWidth().craftField(C.camper.header).padding(12.dp).testTag("settings.build"),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Txt(stringResource(R.string.settings_build_version, b.versionName, b.number), DesignTokens.type.body.mdStrong, C.camper.ink)
                    Txt(stringResource(R.string.settings_build_commit, b.gitSha.take(12)), CraftType.caption, C.camper.inkSoft)
                    Txt(stringResource(R.string.settings_build_date, b.buildDate), CraftType.caption, C.camper.inkSoft)
                    if (b.engine != null) Txt(stringResource(R.string.settings_build_engine, b.engine, b.python ?: "—"), CraftType.caption, C.camper.inkSoft)
                    if (b.catalogue != null) Txt(stringResource(R.string.settings_build_catalogue, b.catalogue), CraftType.caption, C.camper.inkSoft)
                }
                Button(
                    stringResource(if (ui.copied) R.string.settings_build_copied else R.string.settings_build_copy),
                    "settings.build.copy", a::copyBuild, Modifier.fillMaxWidth(),
                )
                if (ui.builds.isNotEmpty()) {
                    SectionLabel(stringResource(R.string.settings_builds_seen))
                    ui.builds.take(10).forEach { s ->
                        Txt(stringResource(R.string.settings_builds_row, s.number, s.gitSha.take(7), date(s.firstRunAt, ui.settings.language)), CraftType.caption, C.camper.inkSoft)
                    }
                }
                DashedDivider()
                Button(stringResource(R.string.settings_dev), "settings.dev", a::developer, Modifier.fillMaxWidth())
            }
        }
        if (ui.serverConsentAsk) {
            NaviDialog(
                stringResource(R.string.settings_server_consent_title), stringResource(R.string.settings_server_consent_body),
                stringResource(R.string.settings_server_consent_yes), stringResource(R.string.settings_server_consent_no),
                "settings.server.consent", { a.serverConsent(true) }, { a.serverConsent(false) },
            )
        }
    }
}

private const val FILE = app.verst.settings.MirroringTripStore.FILE

// Designer В-9: one date style in the app's language («27 окт. 2026 г.» / «Oct 27, 2026»), not ISO.
private fun locale(l: AppLanguage): Locale = Locale.forLanguageTag(l.tag)

private fun time(ms: Long, l: AppLanguage = AppLanguage.RU): String =
    DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT, locale(l)).format(Date(ms))

private fun date(ms: Long, l: AppLanguage = AppLanguage.RU): String = DateFormat.getDateInstance(DateFormat.MEDIUM, locale(l)).format(Date(ms))

/** `2026-10-27` (the Bank of Russia date) in the app's date style; unparseable stays as is. */
private fun isoDate(iso: String, l: AppLanguage): String =
    runCatching { SimpleDateFormat("yyyy-MM-dd", Locale.ROOT).parse(iso)?.let { date(it.time, l) } }.getOrNull() ?: iso

/** «8,5» / «8.5» in the app's language. */
private fun litres(v: Double, l: AppLanguage): String =
    java.text.NumberFormat.getNumberInstance(locale(l)).apply { maximumFractionDigits = 1; minimumFractionDigits = 0 }.format(v)

/**
 * What «Навигация» does now: the user's own choice, or the automatic one for [country] — «Сейчас вы в России —
 * маршрут откроют Яндекс Карты», «…за рубежом … откроем Google Карты». Russian names only for the countries where
 * Яндекс routes (Georgia gets the neutral line: phones in Abkhazia report GE too).
 */
@Composable
private fun mapsLine(choice: MapsChoice, country: String?): String {
    val c = MapsCountries.normalize(country)
    return when (choice) {
        MapsChoice.YANDEX -> stringResource(R.string.handoff_settings_always_yandex)
        MapsChoice.GOOGLE -> stringResource(R.string.handoff_settings_always_google)
        MapsChoice.AUTO -> when (MapsCountries.auto(c)) {
            MapsApp.GOOGLE -> stringResource(R.string.handoff_settings_abroad)
            MapsApp.YANDEX -> {
                val where = countryIn(c)
                when {
                    c == null -> stringResource(R.string.handoff_settings_unknown)
                    where != null -> stringResource(R.string.handoff_settings_in, stringResource(where))
                    else -> stringResource(R.string.handoff_settings_yandex_here)
                }
            }
        }
    }
}

/** «в России», «в Казахстане»… for the countries where Яндекс routes; null for the rest (and for Georgia). */
private fun countryIn(iso: String?): Int? = when (iso) {
    "RU" -> R.string.settings_maps_in_ru
    "TR" -> R.string.settings_maps_in_tr
    "AZ" -> R.string.settings_maps_in_az
    "AM" -> R.string.settings_maps_in_am
    "KZ" -> R.string.settings_maps_in_kz
    "KG" -> R.string.settings_maps_in_kg
    "TJ" -> R.string.settings_maps_in_tj
    "BY" -> R.string.settings_maps_in_by
    "UZ" -> R.string.settings_maps_in_uz
    "MD" -> R.string.settings_maps_in_md
    else -> null
}

/**
 * A settings card (mockup «Настройки приложения»): the section title (uppercase copy, heading) over the thin brown
 * rule, then the rows.
 */
@Composable
private fun SettingsCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    CraftCard(Modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Txt(title, CraftType.sectionTitle, C.camper.ink, Modifier.semantics { heading() })
            Box(Modifier.fillMaxWidth().height(1.dp).background(C.camper.divider))
        }
        content()
    }
}

/** A caption inside a card («СБОРКИ НА ЭТОМ ТЕЛЕФОНЕ»). */
@Composable
private fun SectionLabel(text: String) = Txt(text, CraftType.fieldLabel, C.camper.inkSoft, Modifier.padding(top = 4.dp))

@Composable
private fun Note(text: String, modifier: Modifier = Modifier) = Txt(text, CraftType.caption, C.camper.inkSoft, modifier)

/** A row whose control is a set of choices: the label above, the chips under it (they may scroll sideways). */
@Composable
private fun ChoiceRow(label: String, control: @Composable () -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Txt(label, CraftType.fieldLabel, C.camper.inkSoft, maxLines = 2)
        control()
    }
}

/** Craft choice chips (orange + white when chosen, white paper else), a radio group; 44 dp high. */
@Composable
private fun <K> Choices(options: List<Pair<K, String>>, current: K, tag: String, onPick: (K) -> Unit) {
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (key, label) ->
            val on = key == current
            CraftChip(label, on, { onPick(key) }, Modifier.semantics { selected = on }.testTag("$tag.$key"), role = Role.RadioButton)
        }
    }
}

/** A storage choice: a white-paper craft field, the title and the line; the chosen one with the orange border and dot. */
@Composable
private fun StorageRow(title: String, sub: String, selected: Boolean, enabled: Boolean, tag: String, onClick: () -> Unit) {
    val shape = RoundedCornerShape(CraftDefaults.FieldRadius)
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 56.dp).clip(shape)
            .background(if (enabled) C.camper.field else C.camper.header)
            .border(
                if (selected) CraftDefaults.Border else CraftDefaults.BorderThin,
                when {
                    selected -> C.camper.orange
                    enabled -> C.camper.border
                    else -> C.camper.border.copy(alpha = 0.4f)
                },
                shape,
            )
            .clickable(enabled = enabled, role = Role.RadioButton, onClick = onClick)
            .semantics { this.selected = selected }
            .testTag(tag).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Txt(title, DesignTokens.type.body.mdStrong, if (enabled) C.camper.ink else C.camper.inkMuted)
            Txt(sub, CraftType.caption, if (enabled) C.camper.inkSoft else C.camper.inkMuted)
        }
        Box(
            Modifier.padding(start = 10.dp).size(20.dp).clip(CircleShape).background(C.camper.paper)
                .border(CraftDefaults.BorderThin, if (enabled) C.camper.border else C.camper.border.copy(alpha = 0.4f), CircleShape),
            contentAlignment = Alignment.Center,
        ) { if (selected) Box(Modifier.size(10.dp).clip(CircleShape).background(C.camper.orange)) }
    }
}

/** The paper craft button of the settings (it keeps its label as the TalkBack description). */
@Composable
private fun Button(label: String, tag: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    CraftSecondaryButton(label, onClick, modifier.semantics { contentDescription = label }.testTag(tag))
}

/** A value with − / + (the car's consumption and tank): the label and the value left, the craft keys right. */
@Composable
private fun Stepper(
    label: String, value: String, tag: String, cdLess: String, cdMore: String,
    lessEnabled: Boolean, moreEnabled: Boolean, onLess: () -> Unit, onMore: () -> Unit,
) {
    Row(Modifier.fillMaxWidth().testTag(tag), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Column(Modifier.weight(1f)) {
            Txt(label, CraftType.fieldLabel, C.camper.inkSoft)
            Txt(value, CraftType.fieldMono, C.camper.ink, Modifier.testTag("$tag.value"))
        }
        StepperKey("−", lessEnabled, cdLess, onLess, Modifier.testTag("$tag.less"))
        StepperKey("+", moreEnabled, cdMore, onMore, Modifier.padding(end = CraftDefaults.TileShadow).testTag("$tag.more"))
    }
}
