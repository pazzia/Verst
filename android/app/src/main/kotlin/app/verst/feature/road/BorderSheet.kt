package app.verst.feature.road

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.dto.AbroadFactDto
import app.verst.core.model.dto.AbroadFeeDto
import app.verst.core.model.dto.BorderDto
import app.verst.core.model.dto.LocalMoney
import app.verst.core.model.dto.SourceDto
import app.verst.core.model.dto.StopDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BORDER_SIGN
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.CraftBadge
import app.verst.core.ui.components.CraftBadgeColor
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.DashedDivider
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.RoadSign
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.OpenDataRing
import app.verst.feature.common.scaled
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/*
 * CEO 29.10 (trips abroad, wave 1): the sheet of a `kind: "border"` stop on Road ahead. Everything the engine says
 * about a crossing comes from search results nobody opened, so every fact carries «не проверено» and its sources;
 * a source opens in the browser. The wait is unknown on every crossing but Псоу: the plan's margin is said to be our
 * estimate, not data.
 */

/** «2» / «1,5» hours of the planner's margin (Russian decimal comma unless [comma] is false). */
internal fun bufferHours(minutes: Int, comma: Boolean = true): String {
    val h = java.math.BigDecimal(minutes).divide(java.math.BigDecimal(60), 1, java.math.RoundingMode.HALF_UP).stripTrailingZeros().toPlainString()
    return if (comma) h.replace('.', ',') else h
}

/** The host of a source («lenta.ru»), the link text; the URL itself when it has none. */
internal fun sourceHost(url: String): String =
    runCatching { java.net.URI(url).host }.getOrNull()?.removePrefix("www.")?.takeIf { it.isNotBlank() } ?: url

/** The wait line: «Время ожидания неизвестно · в плане заложен запас 2 ч (это наша оценка, не данные)». */
@Composable
internal fun borderWaitLine(b: BorderDto): String {
    val hours = bufferHours(b.bufferMin, app.verst.settings.AppPrefs.settings.language == app.verst.core.model.AppLanguage.RU)
    return when {
        // a border without a checkpoint (Россия — Беларусь): no stop, the engine says so
        b.marker || b.bufferMin <= 0 -> if (b.waitKnown && b.waitRu != null) b.waitRu!! else b.bufferRu ?: stringResource(R.string.border_wait_unknown_no_buffer)
        !b.waitKnown -> stringResource(R.string.border_wait_unknown, hours)
        else -> listOfNotNull(b.waitRu?.trimEnd('.'), stringResource(R.string.border_wait_buffer, hours)).joinToString(". ")
    }
}

/** The amber tint of the border card (mockup `bg-amber-50`; opaque, the hard shadow must not show through). */
private val BorderTint = lerp(C.camper.paper, C.camper.amber, 0.16f)

/**
 * Fork camper-ui (mockup screen 7 «Шторка «Граница»»): the sheet's facts on one amber-tinted craft card — the blue
 * title with the passport, the crossing's name in a blue badge and the «граница» sign, the route, the wait, then the
 * bullet facts, each with «не проверено» and its sources — and the orange «Понятно».
 */
@Composable
internal fun BoxScope.BorderSheet(s: StopDto, windowH: Dp, onClose: () -> Unit) {
    val b = s.border ?: return
    val uri = LocalUriHandler.current
    val open: (String) -> Unit = { url -> runCatching { uri.openUri(url) } }
    BottomSheet(s.name, onClose, "border", windowH) {
        Column(
            Modifier.fillMaxWidth().padding(top = 4.dp, end = CraftDefaults.ShadowX, bottom = CraftDefaults.ShadowY)
                .craftSurface(fill = BorderTint).padding(14.dp),
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(Modifier.semantics(mergeDescendants = true) { heading() }, verticalAlignment = Alignment.CenterVertically) {
                        Icon(R.drawable.ic_ui_passport, C.camper.blue, 18.dp)
                        Spacer(Modifier.width(6.dp))
                        Txt(stringResource(R.string.border_label), CraftType.overline, C.camper.blue, maxLines = 1)
                    }
                    CraftBadge(s.name, color = CraftBadgeColor.BLUE)
                    val route = listOfNotNull(b.fromRu, b.toRu).joinToString(" → ")
                    if (route.isNotBlank()) Txt(route, CraftType.cardTitle, C.camper.ink, Modifier.testTag("border.route"))
                    if (b.unverified) Unverified("border.unverified")
                }
                RoadSign(BORDER_SIGN, s.name, emptyList(), Modifier.scaled(0.8f))
            }
            DashedDivider(Modifier.padding(top = 10.dp))
            Txt(borderWaitLine(b), T.body.md, C.camper.ink, Modifier.padding(top = 10.dp).testTag("border.wait"))
            Sources(b.waitSources, "border.wait", open)
            b.coordsNoteRu?.let { Txt(it, T.body.sm, C.camper.inkMuted, Modifier.padding(top = 6.dp).testTag("border.coords")) }
            Facts(stringResource(R.string.border_documents), b.documents, "border.doc", open)
            if (b.fees.isNotEmpty()) {
                SectionTitle(stringResource(R.string.border_fees))
                b.fees.forEachIndexed { i, f -> Fee(f, "border.fee.$i", open) }
            }
            Facts(stringResource(R.string.border_facts), b.facts, "border.fact", open)
            Facts(stringResource(R.string.border_risks), b.risks, "border.risk", open)
            Facts(stringResource(R.string.border_rules), b.rules, "border.rule", open)
            b.noteRu?.let { Txt(it, T.body.smRelaxed, C.camper.inkSoft, Modifier.padding(top = 12.dp).testTag("border.note")) }
        }
        CraftButton(
            stringResource(R.string.road_parking_ok), onClose,
            Modifier.padding(top = 14.dp, end = CraftDefaults.ShadowX, bottom = CraftDefaults.ShadowY).fillMaxWidth().testTag("border.ok"),
        )
    }
}

@Composable
private fun SectionTitle(title: String) {
    Txt(title, CraftType.cardTitle, C.camper.ink, Modifier.padding(top = 14.dp, bottom = 2.dp).semantics { heading() })
}

@Composable
private fun Facts(title: String, facts: List<AbroadFactDto>, tag: String, open: (String) -> Unit) {
    if (facts.isEmpty()) return
    SectionTitle(title)
    val onTrip = stringResource(R.string.border_risk_on_trip)
    facts.forEachIndexed { i, f ->
        Item(f.textRu, if (f.appliesOnTripDate == true) onTrip else null, f.sources, "$tag.$i", open)
    }
}

@Composable
private fun Fee(f: AbroadFeeDto, tag: String, open: (String) -> Unit) {
    val money = LocalMoney.approx(f.amount, f.currency)
    val line = when {
        f.counted && money != null -> stringResource(R.string.border_fee_counted, money)
        else -> f.notCountedRu
    }
    Item(f.textRu, line, (f.sources + f.ruleSources).distinctBy { it.url }, tag, open)
}

/** One bullet fact: «•», the text, an optional accent line, «не проверено» and its sources (each opens in the browser). */
@Composable
private fun Item(text: String, extra: String?, sources: List<SourceDto>, tag: String, open: (String) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 5.dp).testTag(tag)) {
        Txt("•", T.body.md, C.camper.border, Modifier.width(14.dp).clearAndSetSemantics {})
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Txt(text, T.body.md, C.camper.ink)
            if (extra != null) Txt(extra, T.body.smStrong, C.camper.orangeText, Modifier.testTag("$tag.extra"))
            Unverified("$tag.unverified")
            Sources(sources, tag, open)
        }
    }
}

/** «не проверено» with the dotted open-data ring (5.5 §10.2: the ring means nobody checked it). */
@Composable
private fun Unverified(tag: String) {
    Row(Modifier.testTag(tag), verticalAlignment = Alignment.CenterVertically) {
        OpenDataRing()
        Spacer(Modifier.width(6.dp))
        Txt(stringResource(R.string.common_unverified), T.body.sm, C.camper.inkMuted, maxLines = 1)
    }
}

@Composable
private fun Sources(sources: List<SourceDto>, tag: String, open: (String) -> Unit) {
    sources.filter { it.url.isNotBlank() }.forEachIndexed { j, src ->
        val host = sourceHost(src.url)
        val label = listOfNotNull(host, src.typeRu?.takeIf { it.isNotBlank() }).joinToString(" · ")
        val cd = stringResource(R.string.cd_border_source, label)
        Row(
            Modifier.fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.touchMin)
                .clickable(role = Role.Button) { open(src.url) }
                .semantics(mergeDescendants = true) { contentDescription = cd }
                .testTag("$tag.source.$j"),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Txt(label, T.body.smStrong, C.camper.orangeText, Modifier.weight(1f, fill = false), maxLines = 1)
            GlyphIcon(Glyph.UP_RIGHT, C.camper.inkSoft, 14.dp, Modifier.padding(start = 4.dp))
        }
    }
}
