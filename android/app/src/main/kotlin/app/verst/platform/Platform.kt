package app.verst.platform

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.os.CancellationSignal
import android.os.Looper
import android.provider.Settings
import android.util.Log
import app.verst.core.model.GeoPoint
import app.verst.core.model.dto.HandoffLinksDto
import app.verst.core.model.NaviLinks
import app.verst.nav.HandoffLauncher
import app.verst.nav.HandoffTarget
import app.verst.nav.Locator
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull

/**
 * S3-R1 GPS through the platform `LocationManager` (decision: no FusedLocation — it needs Google Play services,
 * which RuStore phones may lack and the mock does not ship). One fresh fix per provider (fused on API 31+, GPS,
 * network) with a timeout, else the newest last-known fix.
 */
class AndroidLocator(private val context: Context) : Locator {
    private val lm get() = context.getSystemService(LocationManager::class.java)

    override fun precise(): Boolean =
        context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    override fun enabled(): Boolean = lm?.let { m ->
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) m.isLocationEnabled else true
    } ?: true

    override fun granted(): Boolean =
        context.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
            context.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    @SuppressLint("MissingPermission") // checked by granted()
    override suspend fun current(): GeoPoint? {
        if (!granted()) return null
        val m = lm ?: return null
        val all = m.allProviders.toSet()
        val providers = buildList {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) add(LocationManager.FUSED_PROVIDER)
            add(LocationManager.GPS_PROVIDER)
            add(LocationManager.NETWORK_PROVIDER)
        }.filter { it in all && runCatching { m.isProviderEnabled(it) }.getOrDefault(false) }
        for (p in providers) {
            val fix = withTimeoutOrNull(FIX_TIMEOUT_MS) { single(m, p) }
            if (fix != null) return fix.toPoint()
        }
        return providers.mapNotNull { runCatching { m.getLastKnownLocation(it) }.getOrNull() }.maxByOrNull { it.time }?.toPoint()
    }

    @SuppressLint("MissingPermission")
    private suspend fun single(m: LocationManager, provider: String): Location? = suspendCancellableCoroutine { cont ->
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val cancel = CancellationSignal()
            cont.invokeOnCancellation { cancel.cancel() }
            m.getCurrentLocation(provider, cancel, context.mainExecutor) { cont.resume(it) }
        } else {
            val listener = object : LocationListener {
                override fun onLocationChanged(location: Location) {
                    m.removeUpdates(this)
                    if (cont.isActive) cont.resume(location)
                }
                @Deprecated("API < 29") override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) = Unit
                override fun onProviderEnabled(provider: String) = Unit
                override fun onProviderDisabled(provider: String) = Unit
            }
            cont.invokeOnCancellation { m.removeUpdates(listener) }
            @Suppress("DEPRECATION")
            m.requestSingleUpdate(provider, listener, Looper.getMainLooper())
        }
    }

    private fun Location.toPoint() = GeoPoint("GPS", latitude, longitude)

    companion object {
        const val FIX_TIMEOUT_MS = 10_000L
    }
}

/**
 * 5.13 / ADR-0014 hand-off: car → Яндекс Навигатор → Яндекс Карты → the web route; walk → Карты → web. One tap
 * opens the target (no chooser); an `ActivityNotFoundException` falls through to the next link. The packages and
 * the schemes are declared in `<queries>`.
 */
class IntentHandoffLauncher(private val activity: Activity) : HandoffLauncher {
    override fun navigatorInstalled(): Boolean =
        activity.packageManager.getLaunchIntentForPackage(NaviLinks.NAVI_PACKAGE) != null

    override fun mapsInstalled(): Boolean =
        activity.packageManager.getLaunchIntentForPackage(NaviLinks.MAPS_PACKAGE) != null

    override fun open(links: HandoffLinksDto, walk: Boolean): HandoffTarget {
        val navi = links.navigator
        if (!walk && navi != null && navigatorInstalled() && start(navi, NaviLinks.NAVI_PACKAGE)) return HandoffTarget.Navigator
        val maps = links.maps
        if (maps != null && mapsInstalled() && start(maps, NaviLinks.MAPS_PACKAGE)) return HandoffTarget.Maps
        val web = links.web ?: return HandoffTarget.None
        return try {
            activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(web)).addCategory(Intent.CATEGORY_BROWSABLE))
            HandoffTarget.Browser
        } catch (e: ActivityNotFoundException) {
            Log.w(TAG, "no browser for $web", e)
            HandoffTarget.None
        }
    }

    private fun start(uri: String, pkg: String): Boolean = try {
        activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(uri)).setPackage(pkg))
        true
    } catch (e: ActivityNotFoundException) {
        Log.w(TAG, "$pkg did not take the link", e)
        false
    }

    companion object {
        const val TAG = "VerstHandoff"
    }
}

/** Location services off → the system location settings («Включить»). */
fun openLocationSettings(activity: Activity) {
    runCatching { activity.startActivity(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)) }
}

/** The app's page in the system settings (a blocked location permission). */
fun openAppSettings(activity: Activity) {
    runCatching {
        activity.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", activity.packageName, null)))
    }
}
