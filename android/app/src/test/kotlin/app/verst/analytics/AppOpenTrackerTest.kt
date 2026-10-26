package app.verst.analytics

import app.verst.analytics.AnalyticsEvent.StartType.COLD
import app.verst.analytics.AnalyticsEvent.StartType.WARM
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** `app_open`: cold once per process, warm per return from the background, nothing for a rotation. */
class AppOpenTrackerTest {
    @Test
    fun coldThenWarmAndNotOnRotation() {
        val t = AppOpenTracker()
        assertEquals(COLD, t.onStart())
        t.onStop(changingConfigurations = true) // rotation: stop + start of the new activity
        assertNull(t.onStart())
        t.onStop(changingConfigurations = false) // home button
        assertEquals(WARM, t.onStart())
        assertNull(t.onStart()) // a second start without a stop (never reported twice)
        t.onStop(changingConfigurations = false)
        assertEquals(WARM, t.onStart())
    }
}
