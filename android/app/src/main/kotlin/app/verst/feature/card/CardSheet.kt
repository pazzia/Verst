package app.verst.feature.card

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.HotelOptionDto
import app.verst.core.model.dto.PoiDetailsDto
import app.verst.core.ui.R
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.common.scaled
import app.verst.feature.city.BarSign
import app.verst.core.ui.components.RoadSign
import app.verst.feature.exit.tagLine
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** What a 5.9 card shows: the row it came from, the engine's `poi_details` once known. */
data class CardUi(
    val name: String,
    /** RoadSign kind of the mini sign (tourist / hotel / service). */
    val sign: String,
    val tags: List<String> = emptyList(),
    val kind: String, // sight | hotel | bar
    val details: PoiDetailsDto? = null,
    val loading: Boolean = false,
    val offline: Boolean = false,
    /** Hotel rows: the selected option (tags, price) and whether it is booked. */
    val hotel: HotelOptionDto? = null,
    val booked: Boolean = false,
    val canReplace: Boolean = false,
    val walkStop: Boolean = false,
)

interface CardActions {
    fun close()
    fun pickHotel() = Unit
    fun replace() = Unit
    fun removeStop() = Unit
    fun openPage(url: String) = Unit
    /** C10 → D-7. */
    fun report() = Unit
}

/** 5.9 card in a `BottomSheet` (components §19). */
@Composable
fun BoxScope.CardSheet(ui: CardUi, windowH: Dp, a: CardActions) {
    val d = ui.details
    val name = d?.nameRu ?: ui.name
    BottomSheet(name, a::close, "card", windowH, pane = stringResource(R.string.cd_card, name), leading = { CardMiniSign(ui) }) {
        // 5.9 §9: the KindTag + the kind/place line; «Почему здесь: …» when the engine says why
        val tagWord = if (ui.kind == "sight") app.verst.feature.common.kindWord(d?.poiKind) else null
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (tagWord != null) app.verst.feature.common.KindTag(tagWord)
            Txt(kindLine(ui), T.body.sm, C.text.muted, Modifier.weight(1f, fill = false).testTag("card.kind"), maxLines = 1)
        }
        d?.whyRu?.takeIf { it.isNotBlank() }?.let {
            Txt(stringResource(R.string.card_why, it), T.body.sm, C.text.secondary, Modifier.padding(top = 4.dp).testTag("card.why"))
        }
        Spacer(Modifier.height(12.dp))
        val img = d?.image
        val area = ui.kind == "hotel" || img?.isArea == true
        val credit = when {
            img == null -> if (area) d?.townName?.let { stringResource(R.string.card_photo_area, it) } else null
            area -> img.labelRu ?: stringResource(R.string.card_photo_area, d?.townName ?: "")
            // 5.9 §9 level 3: a Commons photo ≤ 300 m from the place
            img.source == "geosearch" || img.source == "nearby" -> img.labelRu
                ?: stringResource(R.string.card_photo_nearby_credit, img.credit?.author ?: "Wikimedia Commons", img.credit?.licence ?: "")
            img.credit?.author != null -> stringResource(R.string.card_photo_credit, img.credit!!.author!!, img.credit!!.licence ?: "")
            // release-s3: no usable author → «Фото: Wikimedia Commons · CC BY-SA 4.0» (the licence stays)
            img.credit?.licence != null -> stringResource(R.string.card_photo_credit_short) + stringResource(R.string.common_join_dot) + img.credit!!.licence!!
            else -> stringResource(R.string.card_photo_credit_short)
        }
        val town = d?.townName ?: ""
        var photoShown by remember(img?.card) { mutableStateOf(false) }
        val descText = d?.textRu?.takeUnless { d.isFictional }?.let { cleanDescription(it, kindLine(ui), d?.townName) }
        val illWord = if (!area && ui.kind != "bar") (tagWord ?: kindLine(ui).substringBefore(" · ").uppercase()) else null
        PhotoFrame(
            url = if (ui.loading) null else img?.card,
            placeholder = if (area) Placeholder.CITY else placeholderFor(d?.poiKind, ui.kind),
            credit = credit,
            area = area,
            offline = ui.offline,
            contentDescription = if (area) stringResource(R.string.cd_card_photo_area, town) else stringResource(R.string.cd_card_photo, name),
            onCredit = img?.page?.let { p -> { a.openPage(p) } },
            onShown = { photoShown = it },
            plate = if (img?.source == "geosearch" || img?.source == "nearby") stringResource(R.string.card_photo_nearby_label) else null,
            // levels 4–5: the category illustration; «фото пока нет» only without a description (OSM-only)
            illustration = illWord?.let { Illustration(it, caption = descText.isNullOrBlank()) },
        )
        if (ui.kind == "hotel") {
            // 5.9 §3: «на фото район, а не она» only while the area photo is on screen
            Txt(
                stringResource(if (photoShown) R.string.card_hotel_fictional else R.string.card_hotel_fictional_nophoto),
                T.body.sm, C.text.secondary, Modifier.padding(top = 6.dp).testTag("card.fictional"),
            )
        }
        // the fictional status is said once (S3-QA P1-05): no engine «Демо: вымышленная гостиница» line
        val desc = descText
        if (desc.isNullOrBlank() && ui.offline && ui.kind == "sight" && d?.wikidataId != null && d.textSource != "osm") {
            // ADR-0016 OR-4 / CEO S4: an online-only value is missing offline → the quiet line in its place
            Txt(stringResource(R.string.online_later), T.body.md, C.text.muted, Modifier.padding(top = 12.dp).testTag("card.later"))
        }
        if (!desc.isNullOrBlank()) {
            var more by remember(desc) { mutableStateOf(false) }
            Txt(desc, T.body.md, C.text.note, Modifier.padding(top = 12.dp).clickable { more = !more }, maxLines = if (more) Int.MAX_VALUE else 6)
            // the source line under the text (a link to the page when the engine has it)
            val src = when (d?.textSource) {
                "wikipedia" -> stringResource(R.string.card_desc_wikipedia)
                "wikivoyage" -> stringResource(R.string.card_desc_wikivoyage)
                "osm" -> stringResource(R.string.card_osm)
                else -> d?.extractSource?.nameRu?.let { n -> stringResource(R.string.card_desc_source, listOfNotNull(n, d?.extractSource?.licence).joinToString(" · ")) }
            }
            if (src != null) Txt(src, T.caption.md, C.text.muted, Modifier.padding(top = 4.dp).testTag("card.desc.source"))
        }
        if (ui.kind == "hotel") {
            val facts = facts(ui)
            if (facts.isNotEmpty()) {
                Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    facts.forEach { Txt(it, T.body.sm, C.text.secondary) }
                }
            }
        } else {
            FactChips(ui)
        }
        val action: Pair<String, () -> Unit>? = when {
            ui.kind == "hotel" && !ui.walkStop -> stringResource(R.string.card_pick_hotel) to a::pickHotel
            ui.walkStop -> stringResource(R.string.walk_remove_stop) to a::removeStop
            ui.canReplace -> stringResource(R.string.stopmenu_swap) to a::replace
            else -> null
        }
        if (action != null) {
            Spacer(Modifier.height(16.dp))
            SecondaryButton(action.first, "card.action", action.second)
        }
        // C10: text button «Сообщить об ошибке» (hug × 44) → D-7; not on hotels (the hotel is fictional)
        if (ui.kind != "hotel") {
            Spacer(Modifier.height(4.dp))
            Box(
                Modifier.height(44.dp).clickable(role = Role.Button, onClick = a::report).testTag("card.report"),
                contentAlignment = Alignment.CenterStart,
            ) { Txt(stringResource(R.string.card_report), T.body.smStrong, C.text.muted, maxLines = 1) }
        }
        if ((d?.attributionRu?.isNotEmpty() == true || ui.kind == "bar") && d?.textSource != "osm") {
            Txt(stringResource(R.string.card_osm), T.caption.md, C.text.muted, Modifier.padding(top = 8.dp).testTag("card.osm"))
        }
    }
}

/**
 * 5.9 §9 facts as chips (min-h 28, radius 14): hours (green open / red closed), ticket, dogs, parking (blue tint);
 * one open-data line with the dotted ring when any fact is open data. «не проверено» is never shown.
 */
@Composable
@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
private fun FactChips(ui: CardUi) {
    val d = ui.details ?: return
    val chips = mutableListOf<Triple<String, androidx.compose.ui.graphics.Color, androidx.compose.ui.graphics.Color>>()
    val h = d.hours
    if (h != null) {
        when {
            h.allDay -> chips += Triple(stringResource(R.string.hours_24), C.hours.open, C.hours.openFill)
            h.openNow == true && h.todayRu != null -> chips += Triple(stringResource(R.string.hours_today_open, h.todayRu ?: ""), C.hours.open, C.hours.openFill)
            h.openNow == false -> chips += Triple(stringResource(R.string.hours_closed), C.hours.closed, C.hours.closedFill)
            !h.textRu.isNullOrBlank() -> hoursRu(h.textRu!!)?.let { chips += Triple(it.replace("{24}", stringResource(R.string.hours_24)).replace("{daily}", stringResource(R.string.card_hours_daily)), C.text.secondary, C.dash.control) }
        }
    }
    val t = d.ticket
    if (t != null && (t.adultRub ?: 0) > 0) {
        var line = stringResource(R.string.card_ticket, RuFormat.thousands(t.adultRub ?: 0), RuFormat.thousands(t.childRub ?: 0))
        if (t.estimate) line += stringResource(R.string.common_join_dot) + stringResource(R.string.card_price_estimate)
        chips += Triple(line, C.text.secondary, C.dash.control)
    } else if (t != null && ui.kind == "sight") {
        chips += Triple(stringResource(R.string.card_ticket_free), C.text.secondary, C.dash.control)
    }
    d.dogsAllowed?.let { chips += Triple(stringResource(if (it) R.string.card_dogs_yes else R.string.card_dogs_no), C.text.secondary, C.dash.control) }
    val p = d.parking
    if (p != null && p.known) {
        val text = if (p.free) stringResource(R.string.card_parking_free) else stringResource(R.string.card_parking_paid, RuFormat.thousands(p.rubPerHour ?: 0))
        chips += Triple(text, C.navi.text, C.sign.blue.copy(alpha = 0.25f))
    }
    if (d.heritage) chips += Triple(stringResource(R.string.card_heritage), C.text.secondary, C.dash.control)
    if (chips.isNotEmpty()) {
        androidx.compose.foundation.layout.FlowRow(
            Modifier.padding(top = 10.dp).fillMaxWidth().testTag("card.facts"),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            chips.forEach { (text, fg, bg) ->
                Box(
                    Modifier.defaultMinSize(minHeight = 28.dp).clip(RoundedCornerShape(14.dp)).background(bg).padding(horizontal = 10.dp, vertical = 4.dp),
                    contentAlignment = Alignment.Center,
                ) { Txt(text, T.body.smStrong, fg) }
            }
        }
    }
    if (!d.verified || h?.verified == false) {
        Row(Modifier.padding(top = 8.dp).testTag("card.opendata"), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            app.verst.feature.common.OpenDataRing()
            Txt(stringResource(R.string.card_open_data), T.body.sm, C.text.muted)
        }
    }
}

/** 5.9 C2: the row's RoadSign at 0.7 (tourist 39 × 39, hotel service 35 × 43); bars get the §21 bar sign. */
@Composable
private fun CardMiniSign(ui: CardUi) {
    if (ui.kind == "bar") BarSign(ui.tags.firstOrNull() ?: "bar")
    else Box(Modifier.scaled(0.7f)) { RoadSign(ui.sign, ui.name, ui.tags) }
}

@Composable
private fun SecondaryButton(text: String, tag: String, onClick: () -> Unit) {
    val shape = RoundedCornerShape(DesignTokens.radius.r12)
    Box(
        Modifier.fillMaxWidth().height(56.dp).clip(shape).border(DesignTokens.stroke.w1, C.dash.outline, shape)
            .background(C.dash.control).clickable(role = Role.Button, onClick = onClick).testTag(tag),
        contentAlignment = Alignment.Center,
    ) { Txt(text, T.button.md, C.text.primary, maxLines = 1) }
}

/**
 * Raw OSM `opening_hours` must never reach the card in English («Mo-Su 05:00-21:00»): the daily form becomes
 * «{daily} 05:00–21:00», `24/7` → «{24}»; anything else with Latin letters is dropped (the open-data line stays).
 */
internal fun hoursRu(text: String): String? {
    val t = text.trim()
    if (t == "24/7") return "{24}"
    Regex("""^Mo-Su (\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$""").matchEntire(t)?.let { m -> return "{daily} ${m.groupValues[1]}–${m.groupValues[2]}" }
    // OSM day abbreviations → Russian («Tu-Su 10:00-18:00; Mo off» → «вт–вс 10:00–18:00; пн выходной»)
    val days = mapOf("Mo" to "пн", "Tu" to "вт", "We" to "ср", "Th" to "чт", "Fr" to "пт", "Sa" to "сб", "Su" to "вс", "PH" to "праздники")
    var r = Regex("""\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b""").replace(t) { days.getValue(it.value) }
    r = r.replace(Regex("""\boff\b|\bclosed\b"""), "выходной")
    r = Regex("""(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})""").replace(r) { "${it.groupValues[1]}–${it.groupValues[2]}" }
    r = Regex("""([а-я]{2})-([а-я]{2})""").replace(r) { "${it.groupValues[1]}–${it.groupValues[2]}" }
    return if (r.any { it in 'A'..'Z' || it in 'a'..'z' }) null else r
}

/**
 * S3-FINAL P2-04: Wikidata descriptions like «площадь в г. Иваново» only repeat the kind line («площадь ·
 * Иваново») — hidden; others start with a capital letter and end with a full stop.
 */
internal fun cleanDescription(text: String, kindLine: String, town: String?): String? {
    val t = text.trim()
    if (t.isEmpty()) return null
    val filler = setOf("в", "г", "г.", "городе", "города", "на", "у", "близ", "·", "-", "—", ",")
    val known = (kindLine.lowercase().split(' ', '·', ',') + (town ?: "").lowercase().split(' ', '-'))
        .map { it.trim('.', ',', ' ') }.filter { it.isNotEmpty() }.toSet()
    val words = t.lowercase().split(' ', ',').map { it.trim('.', ',', ' ') }.filter { it.isNotEmpty() && it !in filler }
    if (words.isNotEmpty() && words.all { w -> known.any { k -> w == k || (k.length >= 4 && w.startsWith(k.dropLast(1))) } }) return null
    val cap = t.replaceFirstChar { it.uppercase() }
    return if (cap.last() in ".!?…»)") cap else "$cap."
}

@Composable
private fun kindLine(ui: CardUi): String {
    val d = ui.details
    val town = d?.townName
    if (ui.kind == "hotel") return stringResource(R.string.card_kind_hotel, town ?: "")
    val word = when (d?.poiKind) {
        "museum" -> stringResource(R.string.card_kind_museum)
        "church" -> stringResource(R.string.card_kind_church)
        "monastery" -> stringResource(R.string.card_kind_monastery)
        "kremlin" -> stringResource(R.string.card_kind_kremlin)
        "park", "garden" -> stringResource(R.string.card_kind_park)
        "monument", "memorial" -> stringResource(R.string.card_kind_monument)
        "viewpoint", "view" -> stringResource(R.string.card_kind_view)
        "square" -> stringResource(R.string.card_kind_square)
        "embankment" -> stringResource(R.string.card_kind_embankment)
        "ryumochnaya" -> stringResource(R.string.card_kind_ryumochnaya)
        "pub" -> stringResource(R.string.card_kind_pub)
        "craft" -> stringResource(R.string.card_kind_craft)
        "bar", "beer" -> stringResource(R.string.card_kind_bar)
        else -> if (ui.kind == "bar") stringResource(R.string.card_kind_bar) else stringResource(R.string.card_kind_sight)
    }
    return if (town.isNullOrBlank()) word else stringResource(R.string.card_kind_line, word, town)
}

@Composable
private fun facts(ui: CardUi): List<String> {
    val d = ui.details
    val out = mutableListOf<String>()
    if (ui.kind == "hotel") {
        ui.hotel?.let { h ->
            val tags = tagLine(h)
            if (tags.isNotBlank()) out += tags
            out += if (ui.booked) stringResource(R.string.exit_booked_price)
            else stringResource(R.string.common_estimate_rub, RuFormat.thousands(h.priceCrewRub.takeIf { it > 0 } ?: h.priceNightRub)) +
                " " + stringResource(R.string.card_per_night)
        }
        return out
    }
    if (d?.hours?.verified == false) out += stringResource(R.string.card_hours_unverified)
    val t = d?.ticket
    if (t != null && (t.adultRub ?: 0) > 0) {
        var line = stringResource(R.string.card_ticket, RuFormat.thousands(t.adultRub ?: 0), RuFormat.thousands(t.childRub ?: 0))
        if (t.estimate) line += stringResource(R.string.common_join_dot) + stringResource(R.string.card_price_estimate)
        out += line
    } else if (t != null && ui.kind == "sight") {
        out += stringResource(R.string.card_ticket_free)
    }
    if (d?.heritage == true) out += stringResource(R.string.card_heritage)
    if (d != null && !d.verified) out += stringResource(R.string.card_unverified)
    return out
}

