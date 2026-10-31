package app.verst.analytics

/**
 * R-07 / SPEC §16 / tracking plan §0.3: what must never leave the phone in an analytics event. [violations] names
 * the rules an event's properties break (empty = clean). [GuardedAnalytics] drops an event that breaks any, and the
 * unit tests run every event the app builds through it.
 *
 * Rules:
 *  - `key`: keys are `snake_case`, ≤ 40 chars, and none of the personal-data names (`lat`, `address`, `email`, …);
 *  - `type`: values are Int, Long, Boolean or String only (a Double would be a coordinate);
 *  - `coordinates`: a decimal number inside a string («55.7558», «37,6173»);
 *  - `email`: an `@`;
 *  - `phone`: 10 or more digits in one run of digits, spaces, `+ ( ) -` (UUIDs and ISO dates are not runs of a phone);
 *  - `free_text`: longer than [MAX_TEXT] chars, or a line break.
 */
object PrivacyGuard {
    /** Longest string value: a UUID `trip_id` (36) fits, a sentence does not. */
    const val MAX_TEXT = 40

    private val KEY = Regex("[a-z][a-z0-9_]{0,39}")
    private val FORBIDDEN_KEYS = setOf(
        "lat", "lon", "lng", "latitude", "longitude", "coordinates", "location", "address", "street", "email", "phone",
        "name", "query", "text", "comment", "user_id", "ip",
    )
    private val DECIMAL = Regex("\\d[.,]\\d")
    private val PHONE_RUN = Regex("[+\\d][\\d\\s()+\\-]*\\d")
    private val UUID = Regex("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

    fun violations(params: Map<String, Any?>): List<String> {
        val out = linkedSetOf<String>()
        for ((k, v) in params) {
            if (!KEY.matches(k) || k in FORBIDDEN_KEYS) out += "key"
            when (v) {
                is Int, is Long, is Boolean -> Unit
                is String -> out += stringViolations(v)
                else -> out += "type"
            }
        }
        return out.toList()
    }

    fun stringViolations(v: String): List<String> {
        val out = mutableListOf<String>()
        if (DECIMAL.containsMatchIn(v)) out += "coordinates"
        if ('@' in v) out += "email"
        if (!UUID.matches(v) && PHONE_RUN.findAll(v).any { run -> run.value.count(Char::isDigit) >= 10 }) out += "phone"
        if (v.length > MAX_TEXT || '\n' in v || '\r' in v) out += "free_text"
        return out
    }
}
