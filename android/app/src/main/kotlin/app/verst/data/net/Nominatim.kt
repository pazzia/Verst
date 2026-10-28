package app.verst.data.net

import app.verst.core.model.dto.SuggestionDto
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request

/** What an address search or a reverse lookup gave. */
sealed interface AddressResult<out T> {
    data class Ok<T>(val value: T) : AddressResult<T>
    data object Offline : AddressResult<Nothing>
    data class Failed(val reason: String) : AddressResult<Nothing>
}

/** The address search the app uses (Nominatim in the app; a fake in unit tests). */
interface AddressSearch {
    suspend fun search(query: String): AddressResult<List<SuggestionDto>>
    suspend fun reverse(lat: Double, lon: Double): AddressResult<String?>
}

/**
 * DEV-302 / ADR-0012 §5: Nominatim `/search` and `/reverse`, **only on an explicit submit** (the usage policy
 * forbids autocomplete), ≤ 1 request per second (a token bucket shared by both: a second call waits), a 24 h
 * in-memory cache, `countrycodes=ru`, `accept-language=ru`, the Verst User-Agent (the shared OkHttp client).
 * CI never talks to the real service: the tests point [baseUrl] at MockWebServer.
 */
class NominatimClient(
    private val http: () -> OkHttpClient = { Net.okHttp },
    var baseUrl: String = DEFAULT_BASE,
    private val online: () -> Boolean = { true },
    private val now: () -> Long = System::currentTimeMillis,
    private val minGapMs: Long = 1_000,
) : AddressSearch {
    private val bucket = Mutex()
    private var lastCall = 0L
    private val cache = HashMap<String, Pair<Long, Any?>>()

    /** Requests actually sent (tests). */
    @Volatile var requests = 0
        private set

    override suspend fun search(query: String): AddressResult<List<SuggestionDto>> {
        val q = query.trim()
        if (q.isEmpty()) return AddressResult.Ok(emptyList())
        val url = baseUrl.trimEnd('/').plus("/search").toHttpUrl().newBuilder()
            .addQueryParameter("q", q)
            .addQueryParameter("format", "jsonv2")
            .addQueryParameter("addressdetails", "1")
            .addQueryParameter("countrycodes", "ru")
            .addQueryParameter("accept-language", "ru")
            .addQueryParameter("limit", "5")
            .build().toString()
        return get(url) { body -> parseSearch(body) }
    }

    override suspend fun reverse(lat: Double, lon: Double): AddressResult<String?> {
        val url = baseUrl.trimEnd('/').plus("/reverse").toHttpUrl().newBuilder()
            .addQueryParameter("lat", "%.6f".format(java.util.Locale.US, lat))
            .addQueryParameter("lon", "%.6f".format(java.util.Locale.US, lon))
            .addQueryParameter("format", "jsonv2")
            .addQueryParameter("addressdetails", "1")
            .addQueryParameter("zoom", "18")
            .addQueryParameter("accept-language", "ru")
            .build().toString()
        return get(url) { body -> (json.parseToJsonElement(body) as? JsonObject)?.let { streetLabel(it) } }
    }

    @Suppress("UNCHECKED_CAST")
    private suspend fun <T> get(url: String, parse: (String) -> T): AddressResult<T> {
        cache[url]?.let { (at, v) -> if (now() - at < CACHE_MS) return AddressResult.Ok(v as T) }
        if (!online()) return AddressResult.Offline
        return bucket.withLock {
            val wait = lastCall + minGapMs - now()
            if (wait > 0) delay(wait)
            lastCall = now()
            requests++
            try {
                val host = url.toHttpUrl().host
                val body = withContext(Dispatchers.IO) {
                    http().newCall(Request.Builder().url(url).build()).execute().use { r ->
                        if (!r.isSuccessful) throw IOException("HTTP ${r.code}")
                        // OR-5: HTML, a wrong content type or a body over 1 MB is no data
                        r.jsonBodyOrNull() ?: run {
                            OnlineStats.dropped(host)
                            throw IOException("not json")
                        }
                    }
                }
                // OR-5: truncated or garbage JSON is no data, never an exception out of the data layer
                val v = try {
                    parse(body)
                } catch (e: Exception) {
                    OnlineStats.dropped(host)
                    throw IOException("garbage", e)
                }
                cache[url] = now() to v
                AddressResult.Ok(v)
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            } catch (e: java.net.UnknownHostException) {
                AddressResult.Offline // designer В-2: airplane mode before the system notices is offline, not «try again»
            } catch (e: java.net.ConnectException) {
                AddressResult.Offline
            } catch (e: Exception) {
                AddressResult.Failed(e.toString())
            }
        }
    }

    companion object {
        const val DEFAULT_BASE = "https://nominatim.openstreetmap.org"
        const val CACHE_MS = 24L * 60 * 60 * 1000
        private val json = Json { ignoreUnknownKeys = true }

        private fun JsonObject.str(k: String): String? = (this[k] as? JsonPrimitive)?.content?.takeIf { it.isNotBlank() }

        /** «ул. Советская, 1» from the `address` object (street + house), else the first part of the display name. */
        fun streetLabel(o: JsonObject): String? {
            val a = o["address"] as? JsonObject
            val road = a?.str("road") ?: a?.str("pedestrian") ?: a?.str("square")
            val house = a?.str("house_number")
            return when {
                road != null && house != null -> "$road, $house"
                road != null -> road
                else -> o.str("name") ?: o.str("display_name")?.substringBefore(",")
            }
        }

        fun city(o: JsonObject): String? {
            val a = o["address"] as? JsonObject ?: return null
            return a.str("city") ?: a.str("town") ?: a.str("village") ?: a.str("municipality") ?: a.str("county") ?: a.str("state")
        }

        /** Up to 5 address rows: kind `address`, name «ул. Советская, 1», subtitle = the city (the screen adds «адрес ·»). */
        fun parseSearch(body: String): List<SuggestionDto> {
            val arr = json.parseToJsonElement(body) as? JsonArray ?: return emptyList()
            return arr.mapNotNull { e ->
                val o = e as? JsonObject ?: return@mapNotNull null
                val lat = o.str("lat")?.toDoubleOrNull() ?: return@mapNotNull null
                val lon = o.str("lon")?.toDoubleOrNull() ?: return@mapNotNull null
                val name = streetLabel(o) ?: return@mapNotNull null
                SuggestionDto("address", name, city(o) ?: "", lat, lon, id = o.str("place_id")?.let { "osm_$it" })
            }.distinctBy { it.name + it.subtitle }.take(5)
        }
    }
}
