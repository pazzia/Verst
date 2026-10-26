package app.verst.analytics

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * The AppMetrica side of ENG-05 without activating the SDK: an empty or malformed key is the no-op (the public demo
 * APK), and the configuration a real key gets has location and advertising ids off (R-07).
 */
@RunWith(RobolectricTestRunner::class)
@Config(application = Application::class) // not VerstApp: no engine start for these tests
class VerstAnalyticsTest {
    private val testKey = "00000000-0000-4000-8000-000000000000"

    @Test
    fun withoutAUsableKeyNothingIsActivated() {
        val app = ApplicationProvider.getApplicationContext<Application>()
        for (key in listOf("", " ", "not-a-key", "0000000-0000-4000-8000-000000000000", "$testKey ")) {
            assertFalse(key, AnalyticsKey.usable(key))
            assertSame(key, NoopAnalytics, VerstAnalytics.create(app, key))
        }
        assertTrue(AnalyticsKey.usable(testKey))
        assertTrue(AnalyticsKey.usable(testKey.uppercase()))
        assertFalse(NoopAnalytics.enabled)
    }

    @Test
    fun configHasNoLocationNoAdvertisingIdsNoProfile() {
        val c = VerstAnalytics.config(testKey)
        assertEquals(testKey, c.apiKey)
        assertEquals(false, c.locationTracking)
        assertNull(c.location)
        assertEquals(false, c.advIdentifiersTracking)
        assertEquals(false, c.revenueAutoTrackingEnabled)
        assertEquals(false, c.appOpenTrackingEnabled)
        assertEquals(true, c.crashReporting)
        assertNull(c.userProfileID)
    }
}
