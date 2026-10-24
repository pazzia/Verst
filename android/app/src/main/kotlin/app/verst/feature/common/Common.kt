package app.verst.feature.common

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.windowInsetsBottomHeight
import androidx.compose.foundation.layout.windowInsetsTopHeight
import androidx.compose.ui.Alignment
import app.verst.core.ui.theme.DesignTokens
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import app.verst.core.model.RuFormat
import app.verst.core.ui.R

/**
 * Edge-to-edge root: the background runs under the system bars, the content sits inside them. S-02 /
 * components §0.2: the status-bar band is filled with [statusBar] (the colour the scene has at its top), the
 * navigation-bar band with `color.dash.raised`; the bar icons are light (MainActivity).
 */
@Composable
fun ScreenRoot(background: Color, statusBar: Color = background, content: @Composable BoxScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(background)) {
        Box(Modifier.fillMaxWidth().windowInsetsTopHeight(WindowInsets.statusBars).background(statusBar))
        Box(Modifier.align(Alignment.BottomCenter).fillMaxWidth().windowInsetsBottomHeight(WindowInsets.navigationBars).background(DesignTokens.color.dash.raised))
        Box(Modifier.fillMaxSize().systemBarsPadding(), content = content)
    }
}

/**
 * Town name in the genitive for «ИЗ МОСКВЫ» / «из Москвы» (copy-ru `windshield_sign_header`). The fixture
 * worlds carry only nominative/prepositional names; the slice knows the mock origin. Unknown towns keep the
 * nominative (open: engine field `nameGenRu`).
 */
fun genitive(town: String): String = when (town) {
    "Москва" -> "Москвы"
    "Тестовск" -> "Тестовска"
    else -> town
}

/** «2 взр · 1 реб · пёс» (mirror caption, Road ahead crew chip). */
@Composable
fun crewShort(adults: Int, children: Int, dog: Boolean): String {
    val parts = mutableListOf(stringResource(R.string.crew_adults_short, adults))
    if (children > 0) parts += stringResource(R.string.crew_children_short, children)
    if (dog) parts += stringResource(R.string.crew_dog_short)
    return parts.joinToString(stringResource(R.string.common_join_dot))
}

@Composable
fun rub(n: Int): String = stringResource(R.string.common_estimate_rub, RuFormat.thousands(n))

@Composable
fun days(n: Int): String = "$n ${pluralStringResource(R.plurals.plural_day, n)}"

/** Copy of the plate toasts (5.5 §4 Saved, D-6, 5.6 §3). */
@Composable
fun toastText(t: app.verst.nav.Toast): String = when (t) {
    is app.verst.nav.Toast.Replaced -> stringResource(R.string.road_replaced_toast, RuFormat.thousands(t.totalRub))
    app.verst.nav.Toast.Saved -> stringResource(R.string.common_saved_toast)
    is app.verst.nav.Toast.SavedNearLimit -> stringResource(R.string.common_saved_near_limit, t.count)
    app.verst.nav.Toast.StorageFull -> stringResource(R.string.common_storage_full_title) + ". " + stringResource(R.string.common_storage_full_body)
    app.verst.nav.Toast.EngineFailed -> stringResource(R.string.waybill_sync_failed)
}
