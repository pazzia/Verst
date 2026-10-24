package app.verst.feature.common

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import app.verst.core.model.RuFormat
import app.verst.core.ui.R

/** Edge-to-edge root: the background runs under the system bars, the content sits inside them. */
@Composable
fun ScreenRoot(background: Color, content: @Composable BoxScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(background)) {
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
