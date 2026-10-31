package app.verst.feature.card

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
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
import androidx.compose.foundation.layout.size
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
import app.verst.core.model.dto.HotelOptionDto
import app.verst.core.model.dto.PoiDetailsDto
import app.verst.core.ui.R
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftSecondaryButton
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
import app.verst.core.ui.components.craftSurface
import app.verst.core.ui.components.servicePictogram
import app.verst.core.ui.components.touristPictogram
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.feature.city.walkSignGlyph
import app.verst.feature.exit.tagLine
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** What a 5.9 card shows: the row it came from, the engine's `poi_details` once known. */
data class CardUi(
    val name: String,
    /** RoadSign kind of the mini sign (tourist / hotel / service). */
    val sign: String,
    val tags: List<String> = emptyList(),
    val kind: String, // sight | hotel | bar | food (CEO 29.10: an OSM restaurant / café of a walk)
    val details: PoiDetailsDto? = null,
    val loading: Boolean = false,
    val offline: Boolean = false,
    /** Hotel rows: the selected option (tags, price) and whether it is booked. */
    val hotel: HotelOptionDto? = null,
    val booked: Boolean = false,
    val canReplace: Boolean = false,
    val walkStop: Boolean = false,
    /** CEO 29.10: the town the row knows (a walk's town, a night's town) until `poi_details` names one. */
    val town: String? = null,
    /**
     * CEO 29.10: the place's street address («ул. Ленина, 5»), reverse-geocoded from its coordinates when the card
     * opened online (Nominatim, else the phone's geocoder); null = not known (offline, not found).
     */
    val address: String? = null,
    /** The address lookup runs: «Адрес уточняется…». */
    val addressLoading: Boolean = false,
)

/**
 * CEO 29.10: the card's address line — the street address, and « · <town>» when it does not name the town itself
 * («ул. Ленина, 5 · Фрязино»).
 */
internal fun cardAddressLine(address: String, town: String?): String {
    val a = address.trim()
    val t = town?.trim()?.takeIf { it.isNotEmpty() } ?: return a
    return if (a.contains(t, ignoreCase = true)) a else "$a · $t"
}

interface CardActions {
    fun close()
    fun pickHotel() = Unit
    fun replace() = Unit
    fun removeStop() = Unit
    fun openPage(url: String) = Unit
    /** C10 → D-7. */
    fun report() = Unit
}

/**
 * 5.9 card in a `BottomSheet` (components §19); camper fork (mockup screen 12 «Карточка места»): the paper sheet
 * with the craft tile of the place, the kind line as the orange overline above the title, ✕; the photo in a brown
 * frame, the address, «Почему здесь», the description with its source, the fact badges, the actions as craft
 * buttons, «Сообщить об ошибке».
 */
@Composable
fun BoxScope.CardSheet(ui: CardUi, windowH: Dp, a: CardActions) {
    val d = ui.details
    val name = d?.nameRu ?: ui.name
    // CEO 29.10: the address under the kind line, and in the card's TalkBack title
    val addressLine = ui.address?.let { cardAddressLine(it, d?.townName ?: ui.town) }
    val pane = if (addressLine != null) stringResource(R.string.cd_card_with_address, name, addressLine) else stringResource(R.string.cd_card, name)
    val kind = kindLine(ui)
    BottomSheet(
        name, a::close, "card", windowH, pane = pane, leading = { CardMiniSign(ui) },
        // 5.9 §9: the kind/place line as the orange overline («МУЗЕЙ · КОЛОМНА»)
        overline = { Txt(kind.uppercase(), CraftType.overline, C.camper.orangeText, Modifier.testTag("card.kind"), maxLines = 1) },
    ) {
        // the kind word of the category illustration (the engine's label for sights)
        val tagWord = if (ui.kind == "sight") d?.poiKindRu?.uppercase() ?: app.verst.feature.common.kindWord(d?.poiKind) else null
        if (addressLine != null) {
            AddressLine(addressLine)
        } else if (ui.addressLoading) {
            Txt(stringResource(R.string.card_address_loading), CraftType.caption, C.camper.inkMuted, Modifier.padding(top = 2.dp).testTag("card.address.loading"), maxLines = 1)
        }
        d?.whyRu?.takeIf { it.isNotBlank() }?.let {
            // «Почему здесь: объект культурного наследия · …» (the engine starts each part with a capital)
            val why = it.split(" · ").joinToString(" · ") { p -> if (p.length > 1 && p[1].isLowerCase()) p.replaceFirstChar { c -> c.lowercase() } else p }
            Box(Modifier.padding(top = 6.dp).fillMaxWidth().craftField(C.camper.header).padding(horizontal = 10.dp, vertical = 8.dp)) {
                Txt(stringResource(R.string.card_why, why), CraftType.caption, C.camper.ink, Modifier.testTag("card.why"))
            }
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
        val descText = d?.textRu?.takeUnless { d.isFictional }?.let { cleanDescription(it, kind, d?.townName) }
        val illWord = if (!area && ui.kind != "bar") (tagWord ?: kind.substringBefore(" · ").uppercase()) else null
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
                CraftType.caption, C.camper.inkSoft, Modifier.padding(top = 6.dp).testTag("card.fictional"),
            )
        }
        // the fictional status is said once (S3-QA P1-05): no engine «Демо: вымышленная гостиница» line
        val desc = descText
        if (desc.isNullOrBlank() && ui.offline && ui.kind == "sight" && d?.wikidataId != null && d.textSource != "osm") {
            // ADR-0016 OR-4 / CEO S4: an online-only value is missing offline → the quiet line in its place
            Txt(stringResource(R.string.online_later), CraftType.body, C.camper.inkMuted, Modifier.padding(top = 12.dp).testTag("card.later"))
        }
        if (!desc.isNullOrBlank()) {
            var more by remember(desc) { mutableStateOf(false) }
            Txt(desc, CraftType.body, C.camper.ink, Modifier.padding(top = 12.dp).clickable { more = !more }, maxLines = if (more) Int.MAX_VALUE else 6)
            // the source line under the text (a link to the page when the engine has it)
            val src = when (d?.textSource) {
                "wikipedia" -> stringResource(R.string.card_desc_wikipedia)
                "wikivoyage" -> stringResource(R.string.card_desc_wikivoyage)
                "osm" -> stringResource(R.string.card_osm)
                // the engine's `nameRu` is the whole line («Описание: Викиданные»): no second «Описание:» here
                else -> d?.extractSource?.nameRu?.let { n -> listOfNotNull(n, d?.extractSource?.licence).joinToString(" · ") }
            }
            // R-09 (CC BY-SA 4.0): the line names the licence and the abridgement and opens the article, like the photo credit
            val page = d?.extractSource?.url
            if (src != null) {
                Txt(
                    src, T.caption.md, if (page != null) C.camper.orangeText else C.camper.inkMuted,
                    Modifier.padding(top = 4.dp)
                        .then(if (page != null) Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button) { a.openPage(page) } else Modifier)
                        .testTag("card.desc.source"),
                )
            }
        }
        if (ui.kind == "hotel") {
            val facts = facts(ui)
            if (facts.isNotEmpty()) {
                Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    facts.forEach { Txt(it, CraftType.caption, C.camper.inkSoft) }
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
            if (ui.kind == "hotel" && !ui.walkStop) {
                // choosing the hotel is the card's purpose: the orange craft button
                CraftButton(action.first, action.second, Modifier.fillMaxWidth().testTag("card.action"))
            } else {
                // mockup «Заменить» | «В маршрут»: the change as the paper button, «Готово» (the place stays) orange
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    CraftSecondaryButton(action.first, action.second, Modifier.weight(1.5f).testTag("card.action"))
                    CraftButton(stringResource(R.string.settings_done), a::close, Modifier.weight(1f).testTag("card.done"))
                }
            }
        }
        // C10: text button «Сообщить об ошибке» (hug × 44) → D-7; not on hotels (the hotel is fictional)
        if (ui.kind != "hotel") {
            Spacer(Modifier.height(4.dp))
            Box(
                Modifier.height(44.dp).clickable(role = Role.Button, onClick = a::report).testTag("card.report"),
                contentAlignment = Alignment.CenterStart,
            ) { Txt(stringResource(R.string.card_report), T.body.smStrong, C.camper.orangeText, maxLines = 1) }
        }
        // S4-QA P1-05 (ODbL): any place whose data comes from OSM says so, at every card level — unless the source
        // line under the text already did
        val osmShown = !desc.isNullOrBlank() && d?.textSource == "osm"
        if (osmData(ui) && !osmShown) {
            Txt(d?.placeAttributionRu ?: stringResource(R.string.card_osm), T.caption.md, C.camper.inkMuted, Modifier.padding(top = 8.dp).testTag("card.osm"))
        }
    }
}

/**
 * CEO 29.10: the address line under the kind line; a tap or a long press copies it to the clipboard with the toast
 * «Адрес скопирован» (a system toast: it shows above the sheet).
 */
@Composable
@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
private fun AddressLine(text: String) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val copied = stringResource(R.string.card_address_copied)
    val copyLabel = stringResource(R.string.cd_card_address_copy)
    val copy = {
        (ctx.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as? android.content.ClipboardManager)
            ?.setPrimaryClip(android.content.ClipData.newPlainText("Verst address", text))
        android.widget.Toast.makeText(ctx, copied, android.widget.Toast.LENGTH_SHORT).show()
    }
    Txt(
        text, CraftType.caption, C.camper.inkSoft,
        Modifier.padding(top = 2.dp).fillMaxWidth().defaultMinSize(minHeight = DesignTokens.size.touchMin)
            .combinedClickable(onClickLabel = copyLabel, onLongClickLabel = copyLabel, onLongClick = copy, onClick = copy)
            .testTag("card.address"),
        maxLines = 2,
    )
}

/**
 * 5.9 §9 facts as craft badges (min-h 28, radius 10, 1.5 dp brown border): hours (green open / red closed), ticket,
 * dogs, parking (blue tint); one open-data line with the dotted ring when any fact is open data. «не проверено» is
 * never shown.
 */
@Composable
@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
private fun FactChips(ui: CardUi) {
    val d = ui.details ?: return
    val chips = mutableListOf<Triple<String, androidx.compose.ui.graphics.Color, androidx.compose.ui.graphics.Color>>()
    val h = d.hours
    if (h != null) {
        when {
            // ADR-0019 E-1: unknown hours are said, never left out as if the place were open
            !h.known -> chips += Triple(stringResource(R.string.card_hours_unknown), C.camper.ink, C.camper.field)
            h.allDay -> chips += Triple(stringResource(R.string.hours_24), C.hours.open, C.hours.openFill)
            h.openNow == true && h.todayRu != null -> chips += Triple(stringResource(R.string.hours_today_open, h.todayRu ?: ""), C.hours.open, C.hours.openFill)
            h.openNow == false -> chips += Triple(stringResource(R.string.hours_closed), C.hours.closed, C.hours.closedFill)
            !h.textRu.isNullOrBlank() -> hoursRu(h.textRu!!)?.let { chips += Triple(it.replace("{24}", stringResource(R.string.hours_24)).replace("{daily}", stringResource(R.string.card_hours_daily)), C.camper.ink, C.camper.field) }
        }
    }
    val t = d.ticket
    if (t != null && !t.known) {
        // ADR-0019 E-2: an unknown price is not «вход свободный»
        chips += Triple(stringResource(R.string.card_ticket_unknown), C.camper.ink, C.camper.field)
    } else if (t != null && (t.adultRub ?: 0) > 0) {
        var line = stringResource(R.string.card_ticket, app.verst.settings.AppPrefs.money(t.adultRub ?: 0), app.verst.settings.AppPrefs.money(t.childRub ?: 0))
        if (t.estimate) line += stringResource(R.string.common_join_dot) + stringResource(R.string.card_price_estimate)
        chips += Triple(line, C.camper.ink, C.camper.field)
    } else if (t != null && ui.kind == "sight") {
        chips += Triple(stringResource(R.string.card_ticket_free), C.camper.ink, C.camper.field)
    }
    d.dogsAllowed?.let { chips += Triple(stringResource(if (it) R.string.card_dogs_yes else R.string.card_dogs_no), C.camper.ink, C.camper.field) }
    val p = d.parking
    if (p != null && p.known) {
        val text = if (p.free) stringResource(R.string.card_parking_free) else stringResource(R.string.card_parking_paid, app.verst.settings.AppPrefs.money(p.rubPerHour ?: 0))
        chips += Triple(text, C.camper.blue, C.camper.blue.copy(alpha = 0.12f))
    }
    if (d.heritage) chips += Triple(stringResource(R.string.card_heritage), C.camper.ink, C.camper.field)
    if (chips.isNotEmpty()) {
        androidx.compose.foundation.layout.FlowRow(
            Modifier.padding(top = 10.dp).fillMaxWidth().testTag("card.facts"),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            chips.forEach { (text, fg, bg) ->
                val shape = RoundedCornerShape(CraftDefaults.BadgeRadius)
                Box(
                    Modifier.defaultMinSize(minHeight = 28.dp).clip(shape).background(C.camper.field).background(bg)
                        .border(CraftDefaults.BadgeBorder, C.camper.border, shape).padding(horizontal = 10.dp, vertical = 4.dp),
                    contentAlignment = Alignment.Center,
                ) { Txt(text, T.body.smStrong, fg) }
            }
        }
    }
    if (!d.verified || (h?.verified == false && h?.known != false)) { // unknown hours have their own chip
        Row(Modifier.padding(top = 8.dp).testTag("card.opendata"), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            app.verst.feature.common.OpenDataRing()
            Txt(stringResource(R.string.card_open_data), CraftType.caption, C.camper.inkMuted)
        }
    }
}

/**
 * 5.9 C2, camper fork: the place's craft icon tile in the title row — the tourist pictogram of a sight, the service
 * one of a hotel, the bar / food glyph of a walk's bar or café (the §21 bar-sign pictograms).
 */
@Composable
private fun CardMiniSign(ui: CardUi) {
    Box(
        Modifier.size(36.dp).craftSurface(
            C.camper.field, radius = 10.dp, border = CraftDefaults.BorderThin, shadow = C.camper.border,
            shadowX = CraftDefaults.TileShadow, shadowY = CraftDefaults.TileShadow,
        ),
        contentAlignment = Alignment.Center,
    ) {
        when {
            ui.kind == "bar" || ui.kind == "food" -> GlyphIcon(walkSignGlyph(ui.tags.firstOrNull() ?: ui.kind), C.camper.border, 20.dp)
            ui.sign == "tourist" -> Icon(touristPictogram(app.verst.feature.common.signTags(ui.details?.poiKind, ui.tags)), C.camper.border, 22.dp)
            else -> Icon(servicePictogram(ui.sign), C.camper.border, 22.dp)
        }
    }
}

/**
 * The place's data comes (partly) from OpenStreetMap: the engine's OSM attribution, an OSM text or photo, a bar, or a
 * sight known only from the OSM layer (no Wikidata item, not a curated place).
 */
internal fun osmData(ui: CardUi): Boolean {
    val d = ui.details
    return ui.kind == "bar" || ui.kind == "food" || d?.osmSource == true || d?.placeSource == "osm" || d?.placeAttributionRu != null || d?.attributionRu?.any { it.contains("OpenStreetMap") } == true || d?.textSource == "osm" ||
        d?.image?.source == "osm" || (ui.kind == "sight" && d != null && d.wikidataId == null && !d.id.startsWith("pl_"))
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
    val t = wholeText(text.replace(STRESS_MARKS, "").trim())
    if (t.isEmpty()) return null
    val filler = setOf("в", "г", "г.", "городе", "города", "на", "у", "близ", "·", "-", "—", ",")
    val known = (kindLine.lowercase().split(' ', '·', ',') + (town ?: "").lowercase().split(' ', '-'))
        .map { it.trim('.', ',', ' ') }.filter { it.isNotEmpty() }.toSet()
    val words = t.lowercase().split(' ', ',').map { it.trim('.', ',', ' ') }.filter { it.isNotEmpty() && it !in filler }
    if (words.isNotEmpty() && words.all { w -> known.any { k -> w == k || (k.length >= 4 && w.startsWith(k.dropLast(1))) } }) return null
    val cap = t.replaceFirstChar { it.uppercase() }
    return if (cap.last() in ".!?…»)") cap else "$cap."
}

/** Wikipedia's stress marks (combining acute and grave): «Вы́ставка» reads as broken text (designer В-1). */
private val STRESS_MARKS = Regex("[\u0300\u0301]")

/**
 * Designer В-1: a description cut by its source («… выставочный комплекс в…») ends at its last whole sentence,
 * or, with none, at its last whole word; a bracket left without its pair is dropped.
 */
internal fun wholeText(text: String): String {
    var t = text
    val cut = t.endsWith("…") || t.endsWith("...")
    if (cut) {
        t = t.trimEnd('…', '.', ' ')
        val end = Regex("""[.!?»](?=\s)""").findAll(t).lastOrNull()?.range?.last
        t = if (end != null && end >= 20) {
            t.substring(0, end + 1)
        } else {
            val words = t.split(' ').toMutableList()
            if (words.size > 1) words.removeAt(words.lastIndex) // the word the source cut
            while (words.size > 1 && words.last().trimEnd(',', '—', '-').length <= 2) words.removeAt(words.lastIndex)
            words.joinToString(" ").trimEnd(',', ' ', '—', '-') + "…"
        }
    }
    val open = ArrayDeque<Int>()
    val drop = mutableSetOf<Int>()
    t.forEachIndexed { i, c ->
        if (c == '(') open.addLast(i)
        if (c == ')') { if (open.isEmpty()) drop += i else open.removeLast() }
    }
    if (open.isNotEmpty()) t = t.substring(0, open.first()).trimEnd(',', ' ', '—', '-').let { if (cut) "$it…" else it }
    return t.filterIndexed { i, _ -> i !in drop }.replace(Regex(" {2,}"), " ").replace(" )", ")").trim()
}

@Composable
private fun kindLine(ui: CardUi): String {
    val d = ui.details
    val town = d?.townName
    if (ui.kind == "hotel") return stringResource(R.string.card_kind_hotel, town ?: "")
    // M9: the engine's label as given for sights («музей · Коломна»); the local words for bars and old data
    val label = d?.poiKindRu?.takeIf { ui.kind == "sight" }?.lowercase()
    if (label != null) return if (town.isNullOrBlank()) label else stringResource(R.string.card_kind_line, label, town)
    // CEO 29.10: a food place has no engine card yet — its kind comes from the walk stop
    val word = when (d?.poiKind ?: ui.tags.firstOrNull()?.takeIf { ui.kind == "food" }) {
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
        "restaurant" -> stringResource(R.string.card_kind_restaurant)
        "cafe" -> stringResource(R.string.card_kind_cafe)
        "fast_food" -> stringResource(R.string.card_kind_fast_food)
        "food_court" -> stringResource(R.string.card_kind_food_court)
        // S4 kinds without a card word (playground, zoo, interactive, nature, theatre, temple…): the tag word
        else -> if (ui.kind == "bar") stringResource(R.string.card_kind_bar)
        else app.verst.feature.common.kindWord(d?.poiKind)?.lowercase() ?: stringResource(R.string.card_kind_sight)
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
            else stringResource(R.string.common_estimate_rub, app.verst.settings.AppPrefs.money(h.priceCrewRub.takeIf { it > 0 } ?: h.priceNightRub)) +
                " " + stringResource(R.string.card_per_night)
        }
        return out
    }
    if (d?.hours?.known == false) out += stringResource(R.string.card_hours_unknown)
    else if (d?.hours?.verified == false) out += stringResource(R.string.card_hours_unverified)
    val t = d?.ticket
    if (t != null && !t.known) {
        out += stringResource(R.string.card_ticket_unknown)
    } else if (t != null && (t.adultRub ?: 0) > 0) {
        var line = stringResource(R.string.card_ticket, app.verst.settings.AppPrefs.money(t.adultRub ?: 0), app.verst.settings.AppPrefs.money(t.childRub ?: 0))
        if (t.estimate) line += stringResource(R.string.common_join_dot) + stringResource(R.string.card_price_estimate)
        out += line
    } else if (t != null && ui.kind == "sight") {
        out += stringResource(R.string.card_ticket_free)
    }
    if (d?.heritage == true) out += stringResource(R.string.card_heritage)
    if (d != null && !d.verified) out += stringResource(R.string.card_unverified)
    return out
}

