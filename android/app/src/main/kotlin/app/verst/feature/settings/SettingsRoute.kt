package app.verst.feature.settings

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.ContextWrapper
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import app.verst.BuildConfig
import app.verst.MainActivity
import app.verst.VerstApp
import app.verst.core.model.AppLanguage
import app.verst.core.model.AppTheme
import app.verst.core.model.Car
import app.verst.core.model.TripStorage
import app.verst.core.ui.theme.Palette
import app.verst.engine.EngineStatus
import app.verst.nav.VerstFlow
import app.verst.settings.AppPrefs
import app.verst.settings.Themes
import kotlinx.coroutines.launch

/** D-IR-20: the settings screen with the app's state and the activity-bound actions (picker, restart, clipboard). */
@Composable
fun SettingsRoute(flow: VerstFlow) {
    val ctx = LocalContext.current
    val activity = ctx.findActivity()
    val app = ctx.applicationContext as VerstApp
    val status by app.engine.status.collectAsState()
    val catalogue by app.engine.catalogueVersion.collectAsState()
    var copied by remember { mutableStateOf(false) }
    var serverChecking by remember { mutableStateOf(false) }
    var serverCheck by remember { mutableStateOf<app.verst.data.net.ServerCheck?>(null) }
    var consentAsk by remember { mutableStateOf(false) }
    var forgotten by remember { mutableStateOf<Boolean?>(null) }
    val scope = rememberCoroutineScope()
    val s = AppPrefs.settings
    val ready = status as? EngineStatus.Ready
    val build = BuildLines(
        BuildConfig.VERSION_NAME, BuildConfig.BUILD_NUMBER, BuildConfig.GIT_SHA, BuildConfig.BUILD_DATE,
        ready?.info?.engineVersion, ready?.info?.python, catalogue,
    )
    val ui = SettingsUi(
        s, AppPrefs.rates, build, AppPrefs.builds, AppPrefs.folderStatus,
        themePending = Themes.isDay(ctx, s.theme) != Palette.day, copied = copied,
        serverUrl = AppPrefs.serverUrl, serverChecking = serverChecking, serverCheck = serverCheck, lastPlan = app.gateway.lastPlan,
        serverConsentAsk = consentAsk, serverForgotten = forgotten,
    )
    SettingsScreen(
        ui,
        object : SettingsActions {
            override fun back() {
                flow.back()
            }

            override fun language(l: AppLanguage) {
                if (l == AppPrefs.settings.language) return
                AppPrefs.update { it.copy(language = l) }
                activity?.recreate() // attachBaseContext reads the new language
            }

            override fun currency(code: String) {
                AppPrefs.update { it.copy(currency = code) }
            }

            override fun theme(t: AppTheme) {
                AppPrefs.update { it.copy(theme = t) }
            }

            override fun restart() {
                activity?.let(Themes::restart)
            }

            override fun storageDevice() {
                AppPrefs.update { it.copy(storage = TripStorage.DEVICE) }
            }

            override fun pickFolder() {
                (activity as? MainActivity)?.pickTripsFolder()
            }

            override fun writeFolderNow() {
                Thread { app.tripStore.mirrorCurrent() }.start()
            }

            override fun copyBuild() {
                val text = buildText(build, s.language, s.currency, AppPrefs.rates.asOf)
                (ctx.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager)
                    ?.setPrimaryClip(ClipData.newPlainText("Verst build", text))
                copied = true
            }

            override fun developer() = flow.openDebug()

            override fun planOnServer(on: Boolean) {
                // security review В-1: the first «На сервере» asks for consent; «На телефоне» never asks
                if (on && !AppPrefs.settings.serverConsent) consentAsk = true
                else AppPrefs.update { it.copy(planOnServer = on) }
            }

            override fun serverConsent(agree: Boolean) {
                consentAsk = false
                if (agree) {
                    forgotten = null
                    AppPrefs.update { it.copy(serverConsent = true, planOnServer = true) }
                }
            }

            override fun openPrivacy() {
                val base = AppPrefs.serverUrl ?: return
                runCatching {
                    ctx.startActivity(
                        android.content.Intent(android.content.Intent.ACTION_VIEW, android.net.Uri.parse(base.trimEnd('/') + "/privacy"))
                            .addCategory(android.content.Intent.CATEGORY_BROWSABLE)
                            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK),
                    )
                }
            }

            override fun forgetServer() {
                // the phone plans from now on, whatever the server answers
                AppPrefs.update { it.copy(planOnServer = false, serverConsent = false) }
                scope.launch { forgotten = app.server.forget() }
            }

            override fun consumption(steps: Int) {
                AppPrefs.update { it.copy(consumption = it.consumption + steps * Car.CONSUMPTION_STEP) }
            }

            override fun tank(steps: Int) {
                AppPrefs.update { it.copy(tankL = it.tankL + steps * Car.TANK_STEP) }
            }

            override fun fuel(type: String) {
                AppPrefs.update { it.copy(fuelType = type) }
            }

            override fun avoidTolls(on: Boolean) {
                AppPrefs.update { it.copy(avoidTolls = on) }
            }

            override fun checkServer() {
                if (serverChecking) return
                serverChecking = true
                scope.launch {
                    serverCheck = app.server.check()
                    serverChecking = false
                }
            }
        },
    )
}

/** Plain text for a bug report: one fact per line, language-independent. */
internal fun buildText(b: BuildLines, language: AppLanguage, currency: String, ratesAsOf: String?): String = listOf(
    "Verst ${b.versionName} (build ${b.number})",
    "commit ${b.gitSha}",
    "built ${b.buildDate}",
    "engine ${b.engine ?: "—"} · python ${b.python ?: "—"}",
    "catalogue ${b.catalogue ?: "—"}",
    "settings ${language.name} · $currency · rates ${ratesAsOf ?: "none"}",
    "android ${android.os.Build.VERSION.RELEASE} (API ${android.os.Build.VERSION.SDK_INT}) · ${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}",
).joinToString("\n")

private fun Context.findActivity(): Activity? {
    var c: Context? = this
    while (c is ContextWrapper) {
        if (c is Activity) return c
        c = c.baseContext
    }
    return null
}
