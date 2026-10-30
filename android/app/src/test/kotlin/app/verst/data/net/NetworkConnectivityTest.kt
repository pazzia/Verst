package app.verst.data.net

import android.content.Context
import android.net.ConnectivityManager
import androidx.test.core.app.ApplicationProvider
import app.verst.engine.Connectivity
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.shadows.ShadowLooper

/** DEV-300: the network state reaches [Connectivity]; the debug «нет сети» stays on top of it. */
@RunWith(RobolectricTestRunner::class)
class NetworkConnectivityTest {
    private val context = ApplicationProvider.getApplicationContext<Context>()

    @Test
    fun followsTheDefaultNetworkCallbacks() {
        val c = Connectivity(online = false)
        NetworkConnectivity(context, c).start()
        ShadowLooper.idleMainLooper()
        val cm = context.getSystemService(ConnectivityManager::class.java)
        val callbacks = shadowOf(cm).networkCallbacks
        assertTrue("registered", callbacks.isNotEmpty())
        val net = org.robolectric.shadows.ShadowNetwork.newInstance(77)
        callbacks.forEach { it.onAvailable(net) }
        ShadowLooper.idleMainLooper()
        assertTrue(c.online)
        c.post(false) // what onLost of the last network does
        ShadowLooper.idleMainLooper()
        assertFalse(c.online)
        c.post(true)
        c.simulatedOffline = true
        assertFalse("the debug override wins", c.online)
    }
}
