package app.verst.engine

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * M§9 `SimulatedConnectivity`: the mock build needs no network, so it is always online unless the debug panel
 * (DEV-127) switches «Имитировать отсутствие сети» on — then every designed offline state (5.7 E-08) shows.
 */
class Connectivity(online: Boolean = true) {
    var online by mutableStateOf(online)
}
