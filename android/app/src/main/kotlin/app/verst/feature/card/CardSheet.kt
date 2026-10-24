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
}

/** 5.9 card in a `BottomSheet` (components §19). */
@Composable
fun BoxScope.CardSheet(ui: CardUi, windowH: Dp, a: CardActions) {
    val d = ui.details
    val name = d?.nameRu ?: ui.name
    BottomSheet(name, a::close, "card", windowH, pane = stringResource(R.string.cd_card, name)) {
        Txt(kindLine(ui), T.body.sm, C.text.muted, Modifier.padding(top = 0.dp).testTag("card.kind"))
        Spacer(Modifier.height(12.dp))
        val img = d?.image
        val area = ui.kind == "hotel" || img?.isArea == true
        val credit = when {
            img == null -> if (area) d?.townName?.let { stringResource(R.string.card_photo_area, it) } else null
            area -> img.labelRu ?: stringResource(R.string.card_photo_area, d?.townName ?: "")
            img.credit?.author != null -> stringResource(R.string.card_photo_credit, img.credit!!.author!!, img.credit!!.licence ?: "")
            else -> stringResource(R.string.card_photo_credit_short)
        }
        val town = d?.townName ?: ""
        PhotoFrame(
            url = if (ui.loading) null else img?.card,
            placeholder = if (area) Placeholder.CITY else placeholderFor(d?.poiKind, ui.kind),
            credit = credit,
            area = area,
            offline = ui.offline,
            contentDescription = if (area) stringResource(R.string.cd_card_photo_area, town) else stringResource(R.string.cd_card_photo, name),
            onCredit = img?.page?.let { p -> { a.openPage(p) } },
        )
        if (ui.kind == "hotel") {
            Txt(stringResource(R.string.card_hotel_fictional), T.body.sm, C.text.secondary, Modifier.padding(top = 6.dp).testTag("card.fictional"))
        }
        val desc = d?.descriptionRu
        if (!desc.isNullOrBlank()) {
            var more by remember(desc) { mutableStateOf(false) }
            Txt(desc, T.body.md, C.text.note, Modifier.padding(top = 12.dp).clickable { more = !more }, maxLines = if (more) Int.MAX_VALUE else 6)
        }
        val facts = facts(ui)
        if (facts.isNotEmpty()) {
            Column(Modifier.padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                facts.forEach { Txt(it, T.body.sm, C.text.secondary) }
            }
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
        if (d?.attributionRu?.isNotEmpty() == true || ui.kind == "bar") {
            Txt(stringResource(R.string.card_osm), T.caption.md, C.text.muted, Modifier.padding(top = 8.dp).testTag("card.osm"))
        }
    }
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
                " " + stringResource(app.verst.R.string.card_per_night)
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

