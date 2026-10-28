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
import app.verst.nav.HandoffApp
import app.verst.nav.Locator
import kotlin.coroutines.resume
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.launch
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
        val known = providers.mapNotNull { runCatching { m.getLastKnownLocation(it) }.getOrNull() }.maxByOrNull { it.time }
        // CEO 29.10: a fix from the last two minutes is where the phone is — no wait
        if (known != null && System.currentTimeMillis() - known.time < FRESH_MS) return known.toPoint()
        // all providers at once (they used to take turns, 10 s each: indoors GPS alone ate the time), the first wins
        val fix = withTimeoutOrNull(FIX_TIMEOUT_MS) {
            channelFlow<Location> {
                for (p in providers) launch { single(m, p)?.let { send(it) } }
            }.firstOrNull()
        }
        return (fix ?: known)?.toPoint()
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
        const val FIX_TIMEOUT_MS = 20_000L
        const val FRESH_MS = 2 * 60_000L
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

    override fun openIn(app: HandoffApp, uri: String?, web: String?): HandoffTarget {
        if (app == HandoffApp.NAVI) {
            return if (uri != null && navigatorInstalled() && start(uri, NaviLinks.NAVI_PACKAGE)) HandoffTarget.Navigator else HandoffTarget.None
        }
        if (uri != null && mapsInstalled() && start(uri, NaviLinks.MAPS_PACKAGE)) return HandoffTarget.Maps
        val w = web ?: return HandoffTarget.None
        return try {
            activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(w)).addCategory(Intent.CATEGORY_BROWSABLE))
            HandoffTarget.Browser
        } catch (e: ActivityNotFoundException) {
            Log.w(TAG, "no browser for $w", e)
            HandoffTarget.None
        }
    }

    override fun openStore(app: HandoffApp) {
        val pkg = if (app == HandoffApp.NAVI) NaviLinks.NAVI_PACKAGE else NaviLinks.MAPS_PACKAGE
        val market = Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$pkg"))
        if (runCatching { activity.startActivity(market) }.isFailure) {
            runCatching { activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$pkg"))) }
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

/**
 * CEO 29.10: the phone's own geocoder ([android.location.Geocoder]: Google's on most phones, the vendor's
 * elsewhere, absent on some) as the fallback of the address search and of «where am I» when Nominatim fails or
 * does not know the street / house. Not a primary source: its data are not open, so it only fills a gap.
 */
class AndroidGeocoder(private val context: Context) : app.verst.data.net.AddressSearch {
    private fun geocoder(): android.location.Geocoder? =
        if (android.location.Geocoder.isPresent()) android.location.Geocoder(context, java.util.Locale("ru", "RU")) else null

    override suspend fun search(query: String, near: GeoPoint?): app.verst.data.net.AddressResult<List<app.verst.core.model.dto.SuggestionDto>> {
        val g = geocoder() ?: return app.verst.data.net.AddressResult.Failed("no geocoder")
        return try {
            val d = app.verst.data.net.NominatimClient.NEAR_DEG
            // the user's area first; then anywhere (the box is a filter for the platform geocoder)
            val found = near?.let { byName(g, query, doubleArrayOf(it.lat - d, it.lon - d, it.lat + d, it.lon + d)) }.orEmpty()
                .ifEmpty { byName(g, query, null) }
            app.verst.data.net.AddressResult.Ok(
                found.mapNotNull { a -> label(a)?.let { app.verst.core.model.dto.SuggestionDto("address", it, town(a) ?: "", a.latitude, a.longitude) } }
                    .distinctBy { it.name + it.subtitle }.take(8),
            )
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (e: Exception) {
            app.verst.data.net.AddressResult.Failed(e.toString())
        }
    }

    override suspend fun reverse(lat: Double, lon: Double): app.verst.data.net.AddressResult<String?> {
        val g = geocoder() ?: return app.verst.data.net.AddressResult.Failed("no geocoder")
        return try {
            val a = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                suspendCancellableCoroutine { cont ->
                    g.getFromLocation(lat, lon, 1, object : android.location.Geocoder.GeocodeListener {
                        override fun onGeocode(addresses: MutableList<android.location.Address>) = cont.resume(addresses.firstOrNull())
                        override fun onError(errorMessage: String?) = cont.resume(null)
                    })
                }
            } else {
                kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                    @Suppress("DEPRECATION")
                    g.getFromLocation(lat, lon, 1)?.firstOrNull()
                }
            }
            app.verst.data.net.AddressResult.Ok(a?.let { label(it) })
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (e: Exception) {
            app.verst.data.net.AddressResult.Failed(e.toString())
        }
    }

    /** [box]: south, west, north, east. */
    private suspend fun byName(g: android.location.Geocoder, q: String, box: DoubleArray?): List<android.location.Address> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            suspendCancellableCoroutine { cont ->
                val l = object : android.location.Geocoder.GeocodeListener {
                    override fun onGeocode(addresses: MutableList<android.location.Address>) = cont.resume(addresses.toList())
                    override fun onError(errorMessage: String?) = cont.resume(emptyList())
                }
                if (box == null) g.getFromLocationName(q, MAX, l) else g.getFromLocationName(q, MAX, box[0], box[1], box[2], box[3], l)
            }
        } else {
            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                @Suppress("DEPRECATION")
                (if (box == null) g.getFromLocationName(q, MAX) else g.getFromLocationName(q, MAX, box[0], box[1], box[2], box[3])).orEmpty()
            }
        }

    private fun label(a: android.location.Address): String? {
        val road = a.thoroughfare
        val house = a.subThoroughfare
        return when {
            road != null && house != null -> "$road, $house"
            road != null -> road
            else -> a.featureName?.takeIf { it != a.locality }
        }
    }

    private fun town(a: android.location.Address): String? = a.locality ?: a.subAdminArea ?: a.adminArea

    private companion object {
        const val MAX = 10
    }
}
