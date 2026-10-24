package app.verst

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.sp
import app.verst.core.model.BuildInfo
import app.verst.core.ui.HelloTheme
import app.verst.core.ui.HelloText
import app.verst.engine.EngineStatus

/** DEV-101: «Движок <engineVersion> · <totalMs> мс» once ready, the error code otherwise. */
fun engineLine(status: EngineStatus): String = when (status) {
    is EngineStatus.Starting -> "Движок: STARTING"
    is EngineStatus.Ready -> "Движок ${status.info.engineVersion} · ${status.info.timings.totalMs} мс"
    is EngineStatus.Failed -> "Движок: ${status.code}"
}

/** DEV-100: the hello screen — «Верста» and «Сборка <n> · <sha7>» on the night background. */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val engine = (application as VerstApp).engine
        setContent {
            val status by engine.status.collectAsState()
            HelloScreen(BuildInfo(BuildConfig.BUILD_NUMBER, BuildConfig.GIT_SHA), engineLine(status))
        }
    }
}

@Composable
fun HelloScreen(info: BuildInfo, engine: String) {
    HelloTheme {
        Column(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            BasicText("Верста", style = TextStyle(color = HelloText, fontSize = 40.sp))
            BasicText(info.label, style = TextStyle(color = HelloText, fontSize = 14.sp))
            BasicText(engine, style = TextStyle(color = HelloText, fontSize = 14.sp))
        }
    }
}
