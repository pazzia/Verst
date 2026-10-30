package app.verst.data.net

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.util.Log
import app.verst.engine.Connectivity
import coil.ImageLoader
import coil.disk.DiskCache
import coil.memory.MemoryCache
import java.io.File
import java.util.concurrent.TimeUnit
import okhttp3.Interceptor
import okhttp3.OkHttpClient

/** DEV-300 (ADR-0012 §6–7): the one OkHttp client of the app; every request carries the Verst User-Agent. */
object Net {
    const val USER_AGENT = "Verst/0.3 (Android; +https://github.com/pazzia/Verst)"
    const val IMAGE_CACHE_BYTES = 64L * 1024 * 1024

    val userAgent = Interceptor { chain ->
        chain.proceed(chain.request().newBuilder().header("User-Agent", USER_AGENT).build())
    }

    /** ADR-0016 OR-6: one breaker for the whole app (per host). */
    val breaker = CircuitBreaker()

    /**
     * ADR-0016 OR-1: connect 3 s, read 5 s per attempt; the call (both attempts with the jitter) ends by
     * [callTimeoutMs]. The interceptor adds the one retry, the breaker and the debug counters (OR-6, OR-8).
     */
    fun client(
        connectMs: Long = 3_000,
        readMs: Long = 5_000,
        callTimeoutMs: Long = 13_500,
        guard: OnlineInterceptor = OnlineInterceptor(breaker),
    ): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(userAgent)
        .addInterceptor(guard)
        .connectTimeout(connectMs, TimeUnit.MILLISECONDS)
        .readTimeout(readMs, TimeUnit.MILLISECONDS)
        .callTimeout(callTimeoutMs, TimeUnit.MILLISECONDS)
        .build()

    @Volatile private var http: OkHttpClient? = null
    val okHttp: OkHttpClient get() = http ?: synchronized(this) { http ?: client().also { http = it } }

    /** Photos: 10 s in total (5.9 §4 «Фото не загрузилось»), the same rules otherwise. */
    @Volatile private var photoHttp: OkHttpClient? = null
    val photos: OkHttpClient
        get() = photoHttp ?: synchronized(this) { photoHttp ?: okHttp.newBuilder().callTimeout(10, TimeUnit.SECONDS).build().also { photoHttp = it } }

    /** Coil with the shared client and a 64 MB disk cache in `cacheDir/images` (nothing bundled in the APK). */
    fun imageLoader(context: Context): ImageLoader = ImageLoader.Builder(context)
        .okHttpClient { photos }
        .memoryCache { MemoryCache.Builder(context).maxSizePercent(0.15).build() }
        .diskCache { DiskCache.Builder().directory(File(context.cacheDir, "images")).maxSizeBytes(IMAGE_CACHE_BYTES).build() }
        .respectCacheHeaders(false) // Commons files never change under the same name; offline needs the cache
        .crossfade(false) // `motion.photoFadeIn` is drawn by PhotoFrame
        .build()
}

/**
 * DEV-300: the real network state (`ConnectivityManager` callback) feeding [Connectivity]; the debug panel's
 * «Имитировать отсутствие сети» stays on top of it (`Connectivity.simulatedOffline`).
 */
class NetworkConnectivity(context: Context, private val target: Connectivity) {
    private val cm = context.getSystemService(ConnectivityManager::class.java)
    private val live = mutableSetOf<Network>()

    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) = update { live += network }
        override fun onLost(network: Network) = update { live -= network }
        override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) = update {
            if (caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) live += network else live -= network
        }
    }

    private fun update(change: () -> Unit) {
        val now = synchronized(live) {
            change()
            live.isNotEmpty()
        }
        target.post(now)
    }

    fun start() {
        val m = cm ?: return
        val active = m.activeNetwork
        val caps = active?.let { m.getNetworkCapabilities(it) }
        if (active != null && caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true) synchronized(live) { live += active }
        target.post(synchronized(live) { live.isNotEmpty() })
        try {
            m.registerDefaultNetworkCallback(callback)
        } catch (e: Exception) {
            Log.w("VerstNet", "no network callback", e)
        }
    }
}
