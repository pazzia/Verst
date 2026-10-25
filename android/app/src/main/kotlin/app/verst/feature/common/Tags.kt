package app.verst.feature.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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

/** The ADR-0015 §2 whitelist kind → its `kind_*` word (uppercase copy); null = no tag. */
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
    else -> null
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
@Composable
fun TagRow(kind: String?, stretchMin: Int?, openData: Boolean, modifier: Modifier = Modifier) {
    val word = kindWord(kind)
    if (word == null && stretchMin == null && !openData) return
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
        if (stretchMin != null) StretchTag(stretchMin)
        if (word != null) KindTag(word)
        if (openData) OpenDataRing()
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
