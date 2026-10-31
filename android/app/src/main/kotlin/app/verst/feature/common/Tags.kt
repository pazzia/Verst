package app.verst.feature.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import app.verst.core.ui.R
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/**
 * The ADR-0015 §2 whitelist kind → its `kind_*` word (uppercase copy); null = no tag. Only a fallback for data
 * without the engine's `poiKindRu` (trips and walks saved before M9).
 */
@Composable
fun kindWord(kind: String?): String? = when (kind) {
    "museum", "gallery" -> stringResource(R.string.kind_museum)
    "kremlin" -> stringResource(R.string.kind_kremlin)
    "monastery" -> stringResource(R.string.kind_monastery)
    "temple", "church", "cathedral" -> stringResource(R.string.kind_temple)
    "park", "garden" -> stringResource(R.string.kind_park)
    "nature" -> stringResource(R.string.kind_nature)
    "viewpoint", "view" -> stringResource(R.string.kind_viewpoint)
    "square" -> stringResource(R.string.kind_square)
    "embankment" -> stringResource(R.string.kind_embankment)
    "theatre", "theater" -> stringResource(R.string.kind_theatre)
    "zoo" -> stringResource(R.string.kind_zoo)
    "interactive" -> stringResource(R.string.kind_interactive)
    "playground" -> stringResource(R.string.kind_playground)
    "monument", "memorial" -> stringResource(R.string.kind_monument)
    // CEO 29.10: walk food places (OSM) and the bar kinds, for walks without the engine's `poiKindRu`
    "restaurant" -> stringResource(R.string.kind_restaurant)
    "cafe" -> stringResource(R.string.kind_cafe)
    "fast_food" -> stringResource(R.string.kind_fast_food)
    "food_court" -> stringResource(R.string.kind_food_court)
    "ryumochnaya" -> stringResource(R.string.kind_ryumochnaya)
    "pub", "beer" -> stringResource(R.string.kind_pub)
    "craft" -> stringResource(R.string.kind_craft)
    "bar" -> stringResource(R.string.kind_bar)
    else -> null
}

/** CEO 29.10: an OSM `cuisine` tag → its word («georgian» → «грузинская кухня»); null = no word (never shown raw). */
fun cuisineRes(tag: String): Int? = when (tag) {
    "russian" -> R.string.cuisine_russian
    "georgian" -> R.string.cuisine_georgian
    "armenian" -> R.string.cuisine_armenian
    "azerbaijani" -> R.string.cuisine_azerbaijani
    "uzbek" -> R.string.cuisine_uzbek
    "caucasian" -> R.string.cuisine_caucasian
    "ukrainian" -> R.string.cuisine_ukrainian
    "italian" -> R.string.cuisine_italian
    "pizza" -> R.string.cuisine_pizza
    "japanese" -> R.string.cuisine_japanese
    "sushi" -> R.string.cuisine_sushi
    "chinese" -> R.string.cuisine_chinese
    "asian" -> R.string.cuisine_asian
    "korean" -> R.string.cuisine_korean
    "vietnamese" -> R.string.cuisine_vietnamese
    "thai" -> R.string.cuisine_thai
    "indian" -> R.string.cuisine_indian
    "french" -> R.string.cuisine_french
    "european" -> R.string.cuisine_european
    "mediterranean" -> R.string.cuisine_mediterranean
    "greek" -> R.string.cuisine_greek
    "turkish" -> R.string.cuisine_turkish
    "mexican" -> R.string.cuisine_mexican
    "american" -> R.string.cuisine_american
    "burger" -> R.string.cuisine_burger
    "steak_house", "steak" -> R.string.cuisine_steak_house
    "seafood" -> R.string.cuisine_seafood
    "fish" -> R.string.cuisine_fish
    "kebab" -> R.string.cuisine_kebab
    "shawarma" -> R.string.cuisine_shawarma
    "regional", "local" -> R.string.cuisine_regional
    "coffee_shop", "coffee" -> R.string.cuisine_coffee_shop
    "bakery", "pastry" -> R.string.cuisine_bakery
    "cake", "dessert" -> R.string.cuisine_cake
    "pancake", "crepe" -> R.string.cuisine_pancake
    "ice_cream" -> R.string.cuisine_ice_cream
    "sandwich" -> R.string.cuisine_sandwich
    "chicken" -> R.string.cuisine_chicken
    "vegetarian" -> R.string.cuisine_vegetarian
    "vegan" -> R.string.cuisine_vegan
    else -> null
}

/**
 * CEO 29.10: the words for a food place's OSM `cuisine` («georgian;pizza» → «грузинская кухня, пицца»), at most
 * [max] of them; null when the app has a word for none of the tags.
 */
@Composable
fun cuisineWords(cuisine: String?, max: Int = 2): String? {
    val words = mutableListOf<String>()
    for (tag in app.verst.core.model.dto.cuisineTags(cuisine)) {
        if (words.size >= max) break
        val res = cuisineRes(tag) ?: continue
        words += stringResource(res)
    }
    return words.takeIf { it.isNotEmpty() }?.joinToString(", ")
}

/**
 * S4-QA P2-01: one pictogram table from the place kind for the row sign, the card mini sign and the illustration —
 * the kind's tag for `touristPictogram` (kremlin / monastery / museum / view / walk), else the engine's tags.
 */
fun signTags(poiKind: String?, tags: List<String>): List<String> = when (poiKind) {
    "kremlin" -> listOf("kremlin")
    "monastery", "temple", "church", "cathedral" -> listOf("monastery")
    "museum", "gallery", "theatre", "theater", "interactive" -> listOf("museum")
    "viewpoint", "view", "nature", "embankment", "park", "garden" -> listOf("view")
    "playground", "zoo" -> listOf("walk")
    "monument", "memorial", "square", "attraction" -> listOf("monument")
    else -> tags
}

/** components §26 `KindTag`: h 20, radius 4, `kind.*` colours, the uppercase category word. */
@Composable
fun KindTag(word: String, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(DesignTokens.radius.r4)
    Box(
        modifier.height(DesignTokens.size.kindTagH).clip(shape).background(C.kind.fill).border(DesignTokens.stroke.w1, C.kind.border, shape)
            .padding(horizontal = 6.dp).testTag("tag.kind"),
        contentAlignment = Alignment.Center,
    ) { Txt(word, T.tag.kind, C.kind.text, maxLines = 1) }
}

/** components §26 `StretchTag` «РАЗМИНКА 30 МИН» (fun-preset stops), always before the kind tag. */
@Composable
fun StretchTag(minutes: Int, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(DesignTokens.radius.r4)
    Box(
        modifier.height(DesignTokens.size.kindTagH).clip(shape).background(C.stretch.fill).border(DesignTokens.stroke.w1, C.stretch.border, shape)
            .padding(horizontal = 6.dp).testTag("tag.stretch"),
        contentAlignment = Alignment.Center,
    ) { Txt(stringResource(R.string.road_stretch_tag, minutes), T.tag.kind, C.stretch.text, maxLines = 1) }
}

/** components §26 open-data ring: 12 × 12, 1.5 dp dotted `text.muted` (replaces every «не проверено» on rows). */
@Composable
fun OpenDataRing(modifier: Modifier = Modifier) {
    Box(
        modifier.size(12.dp).testTag("tag.opendata").clearAndSetSemantics {}.drawBehind {
            val w = 1.5.dp.toPx()
            drawCircle(
                C.text.muted, radius = size.minDimension / 2 - w / 2,
                style = Stroke(w, pathEffect = PathEffect.dashPathEffect(floatArrayOf(1.6.dp.toPx(), 1.6.dp.toPx()))),
            )
        },
    )
}

/** One tag row: `StretchTag` and/or `KindTag`, then the open-data ring. Hidden when empty. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TagRow(kind: String?, stretchMin: Int?, openData: Boolean, modifier: Modifier = Modifier, label: String? = null) {
    // M9: the engine's `poiKindRu` as given; the kind word only for trips saved before it
    val word = label?.uppercase() ?: kindWord(kind)
    if (word == null && stretchMin == null && !openData) return
    // S4-RELEASE: wraps instead of clipping «РАЗМИНКА 30 МИН» + a long label («ДЕТСКАЯ ПЛОЩАДКА») on a phone
    FlowRow(modifier, horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        if (stretchMin != null) StretchTag(stretchMin)
        if (word != null) KindTag(word)
        if (openData) OpenDataRing(Modifier.align(Alignment.CenterVertically))
    }
}

enum class HoursState { OPEN, CLOSED, ALLDAY, UNKNOWN }

/** components §29 `HoursPill` (untimed walks): «сегодня 11:00–20:00 · открыто» / «сегодня закрыто» / … */
@Composable
fun HoursPill(state: HoursState, text: String, modifier: Modifier = Modifier) {
    val (fg, bg) = when (state) {
        HoursState.OPEN, HoursState.ALLDAY -> C.hours.open to C.hours.openFill
        HoursState.CLOSED -> C.hours.closed to C.hours.closedFill
        HoursState.UNKNOWN -> C.hours.unknown to C.dash.control
    }
    Row(
        modifier.height(DesignTokens.size.hoursPillH).clip(RoundedCornerShape(12.dp)).background(bg).padding(horizontal = 8.dp).testTag("hours.pill"),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        GlyphIcon(Glyph.CLOCK, fg, 13.dp)
        Txt(text, T.tag.hoursLg, fg, maxLines = 1)
    }
}
