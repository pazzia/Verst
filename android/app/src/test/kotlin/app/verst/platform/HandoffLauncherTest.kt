package app.verst.platform

import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.content.IntentFilter
import app.verst.core.model.NaviLinks
import app.verst.core.model.dto.HandoffLinksDto
import app.verst.nav.HandoffTarget
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf

/** DEV-307 acceptance (ShadowPackageManager): navigator installed → navigator; maps only → maps; neither → the web URL. */
@RunWith(RobolectricTestRunner::class)
class HandoffLauncherTest {
    private val links = HandoffLinksDto(
        navigator = "yandexnavi://build_route_on_map?lat_to=57.626100&lon_to=39.884500",
        maps = "yandexmaps://maps.yandex.ru/?rtext=~57.626100,39.884500&rtt=auto",
        web = "https://yandex.ru/maps/?rtext=~57.626100,39.884500&rtt=auto",
    )

    private fun activity(vararg packages: String): Activity {
        val a = Robolectric.buildActivity(Activity::class.java).setup().get()
        val pm = shadowOf(a.packageManager)
        for (p in packages) {
            val c = ComponentName(p, "$p.Main")
            pm.addActivityIfNotPresent(c)
            pm.addIntentFilterForActivity(c, IntentFilter(Intent.ACTION_MAIN).apply { addCategory(Intent.CATEGORY_LAUNCHER) })
        }
        return a
    }

    @Test
    fun navigatorFirst() {
        val a = activity(NaviLinks.NAVI_PACKAGE, NaviLinks.MAPS_PACKAGE)
        assertEquals(HandoffTarget.Navigator, IntentHandoffLauncher(a).open(links, walk = false))
        val i = shadowOf(a).nextStartedActivity
        assertEquals(NaviLinks.NAVI_PACKAGE, i.`package`)
        assertEquals(links.navigator, i.dataString)
    }

    @Test
    fun mapsWhenOnlyMapsAndAlwaysForWalks() {
        val a = activity(NaviLinks.MAPS_PACKAGE)
        assertEquals(HandoffTarget.Maps, IntentHandoffLauncher(a).open(links, walk = false))
        assertEquals(NaviLinks.MAPS_PACKAGE, shadowOf(a).nextStartedActivity.`package`)
        val b = activity(NaviLinks.NAVI_PACKAGE, NaviLinks.MAPS_PACKAGE)
        assertEquals(HandoffTarget.Maps, IntentHandoffLauncher(b).open(links, walk = true)) // the navigator drives only
    }

    @Test
    fun browserWithTheExactWebUrl() {
        val a = activity()
        assertEquals(HandoffTarget.Browser, IntentHandoffLauncher(a).open(links, walk = false))
        val i = shadowOf(a).nextStartedActivity
        assertNull(i.`package`)
        assertEquals(links.web, i.dataString)
        assertEquals(true, i.categories?.contains(Intent.CATEGORY_BROWSABLE))
    }
}
