package app.verst.engine

import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * Sprint 3 (DEV-300): the real network ([network], fed by `NetworkConnectivity`) plus the debug panel's
 * «Имитировать отсутствие сети» ([simulatedOffline], DEV-127). Offline everything but photos and addresses works
 * (the engine is on the phone); the designed offline states (5.7 E-08, 5.9, 5.12) follow [online].
 */
class Connectivity(online: Boolean = true) {
    var network by mutableStateOf(online)
    var simulatedOffline by mutableStateOf(false)

    val online: Boolean get() = network && !simulatedOffline

    /** From a binder thread (the network callback): applied on the main thread. */
    fun post(value: Boolean) {
        val main = Looper.getMainLooper()
        if (Looper.myLooper() == main) network = value else Handler(main).post { network = value }
    }
}
