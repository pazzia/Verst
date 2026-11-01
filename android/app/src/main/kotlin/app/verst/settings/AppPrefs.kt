package app.verst.settings

import android.content.Context
import android.util.AtomicFile
import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import app.verst.BuildConfig
import app.verst.core.model.AppSettings
import app.verst.core.model.EngineJson
import app.verst.core.model.Money
import app.verst.core.model.RatesDto
import java.io.File
import java.io.FileNotFoundException
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer

/**
 * D-IR-20 personal cabinet: the settings, the build's currency rates and the builds seen on this phone.
 * Snapshot state, so a composable that formats money or shows a setting recomposes when it changes. Loaded once in
 * `VerstApp.onCreate`, before the first activity reads the language.
 */
object AppPrefs {
    var settings by mutableStateOf(AppSettings())
        private set
    var rates by mutableStateOf(RatesDto())
        private set
    var builds by mutableStateOf<List<BuildSeen>>(emptyList())
        private set
    /** The last mirror of saved trips into the folder (storage = FOLDER): time or error, for the settings row. */
    var folderStatus by mutableStateOf<FolderStatus?>(null)

    private var dir: File? = null

    fun init(context: Context) {
        val d = File(context.filesDir, "settings").apply { mkdirs() }
        dir = d
        settings = AppSettings.decode(read(File(d, "settings.json")))
        rates = RatesDto.decode(
            runCatching { context.assets.open("rates.json").bufferedReader(Charsets.UTF_8).use { it.readText() } }.getOrNull(),
        )
        builds = recordBuild(File(d, "builds.json"), System.currentTimeMillis())
    }

    /** Applies [change] and saves it. Returns the previous settings (the caller decides on recreate / restart). */
    fun update(change: (AppSettings) -> AppSettings): AppSettings {
        val old = settings
        val new = change(old).sanitized()
        settings = new
        dir?.let { write(File(it, "settings.json"), AppSettings.encode(new)) }
        return old
    }

    /** Money in the chosen currency (the engine computes roubles). */
    fun money(rub: Int): String = Money.format(rub, settings.currency, rates)

    /** The converted number alone, for columns whose header carries the currency (Waybill). */
    fun amount(rub: Int): String = app.verst.core.model.RuFormat.thousands(
        Money.convert(rub, settings.currency, rates).coerceIn(Int.MIN_VALUE.toLong(), Int.MAX_VALUE.toLong()).toInt(),
    )

    /** The symbol of the currency actually shown (roubles when the build has no rate for the chosen one). */
    fun symbol(): String = Money.symbol(Money.effective(settings.currency, rates))

    // ------------------------------------------------------------------------------------------ server (SRV-01)

    /** The backend this build talks to (`VERST_SERVER_URL` at build time); null = the phone engine only. */
    val serverUrl: String? = BuildConfig.SERVER_URL.takeIf { it.isNotBlank() }

    /** The device registration on the server, in `files/settings/server.json` (ADR-0007: the token is shown once). */
    val serverAuth: app.verst.data.net.ServerClient.AuthStore = object : app.verst.data.net.ServerClient.AuthStore {
        override fun load(): app.verst.data.net.ServerAuth? = dir?.let { d ->
            try {
                read(File(d, "server.json"))?.let { EngineJson.json.decodeFromString(app.verst.data.net.ServerAuth.serializer(), it) }
            } catch (_: Exception) {
                null
            }
        }

        override fun save(auth: app.verst.data.net.ServerAuth?) {
            val f = File(dir ?: return, "server.json")
            if (auth == null) f.delete() else write(f, EngineJson.json.encodeToString(app.verst.data.net.ServerAuth.serializer(), auth))
        }
    }

    // ------------------------------------------------------------------------------------------ builds

    /** Adds this build to `builds.json` the first time it runs on the phone (newest first, at most 50). */
    private fun recordBuild(file: File, now: Long): List<BuildSeen> {
        val list = try {
            EngineJson.json.decodeFromString(ListSerializer(BuildSeen.serializer()), read(file) ?: "[]")
        } catch (_: Exception) {
            emptyList()
        }
        val me = BuildSeen(BuildConfig.BUILD_NUMBER, BuildConfig.VERSION_NAME, BuildConfig.GIT_SHA, BuildConfig.BUILD_DATE, now)
        if (list.firstOrNull()?.let { it.number == me.number && it.gitSha == me.gitSha } == true) return list
        val out = (listOf(me) + list).take(50)
        write(file, EngineJson.json.encodeToString(ListSerializer(BuildSeen.serializer()), out))
        return out
    }

    private fun read(f: File): String? = try {
        AtomicFile(f).readFully().toString(Charsets.UTF_8)
    } catch (_: FileNotFoundException) {
        null
    }

    private fun write(f: File, text: String) {
        val a = AtomicFile(f)
        val out = a.startWrite()
        try {
            out.write(text.toByteArray(Charsets.UTF_8))
            a.finishWrite(out)
        } catch (e: Exception) {
            a.failWrite(out)
            Log.w("VerstPrefs", "cannot write ${f.name}", e)
        }
    }
}

/** A build that ran on this phone: number, version, commit, build date (CI) and when it first started here. */
@Serializable
data class BuildSeen(val number: Int, val versionName: String, val gitSha: String, val buildDate: String, val firstRunAt: Long)

sealed interface FolderStatus {
    data class Written(val at: Long, val trips: Int) : FolderStatus
    data class Failed(val at: Long, val reason: String) : FolderStatus
}
