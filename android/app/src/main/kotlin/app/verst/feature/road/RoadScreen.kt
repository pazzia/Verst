package app.verst.feature.road

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.verst.core.model.RuFormat
import app.verst.core.model.dto.DayDto
import app.verst.core.model.dto.StopDto
import app.verst.core.model.dto.TripDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.InfoChip
import app.verst.core.ui.components.RoadSign
import app.verst.core.ui.components.SkyStrip
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.arrowFor
import app.verst.core.ui.components.dashboardSurface
import app.verst.core.ui.components.overheadPlate
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.ScreenRoot
import app.verst.feature.common.crewShort
import app.verst.feature.common.days
import app.verst.feature.common.rub
import app.verst.R as AppR
import kotlin.math.roundToInt

private val C = DesignTokens.color
private val T = DesignTokens.type

private sealed interface Item {
    val key: String

    data object Intro : Item {
        override val key = "intro"
    }

    data class Day(val day: DayDto, val last: Boolean) : Item {
        override val key = "day${day.day}"
    }

    data class Stop(val stop: StopDto, val first: Boolean) : Item {
        override val key = stop.id
    }

    data object Bottom : Item {
        override val key = "bottom"
    }
}

/** 5.5 Road ahead, simplified: the day-by-day signs of the plan and the total in the pinned footer. */
@Composable
fun RoadScreen(trip: TripDto, bearing8: String, onBack: () -> Unit) {
    val rows = buildList<Item> {
        add(Item.Intro)
        trip.daysList.forEachIndexed { di, d ->
            add(Item.Day(d, di == trip.daysList.lastIndex))
            d.stops.forEachIndexed { si, s -> add(Item.Stop(s, di == 0 && si == 0)) }
        }
        add(Item.Bottom)
    }
    ScreenRoot(C.dash.raised) {
        Column(Modifier.fillMaxSize()) {
            Box(Modifier.fillMaxWidth().height(150.dp)) {
                SkyStrip(132.dp)
                Box(Modifier.fillMaxSize().padding(top = 110.dp).dashboardSurface(curve = 30.dp))
                val back = stringResource(R.string.common_back_instruments)
                BackLink(back, C.mirror.label, stringResource(R.string.cd_back, back), onBack, Modifier.padding(start = 12.dp, top = 10.dp).testTag("road.back"))
                TitleSign(trip, bearing8, Modifier.padding(start = 20.dp, end = 20.dp, top = 56.dp).fillMaxWidth())
            }
            Box(Modifier.weight(1f).fillMaxWidth()) {
                LazyColumn(Modifier.fillMaxSize().testTag("road.list")) {
                    items(rows, key = { it.key }) { item ->
                        when (item) {
                            Item.Intro -> Intro(trip)
                            is Item.Day -> DayHeader(item.day, trip.roundTrip && item.last && trip.days > 1)
                            is Item.Stop -> StopRow(item.stop, item.first)
                            Item.Bottom -> Spacer(Modifier.height(24.dp))
                        }
                    }
                }
                Box(
                    Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(24.dp)
                        .background(Brush.verticalGradient(listOf(C.dash.raised.copy(alpha = 0f), C.dash.raised))),
                )
            }
            Footer(trip)
        }
    }
}

@Composable
private fun TitleSign(trip: TripDto, bearing8: String, modifier: Modifier) {
    val cd = "${trip.title}, ${trip.km}"
    Row(
        modifier
            .height(49.dp)
            .overheadPlate(outer = 3.dp, radius = 7.dp, innerRadius = 5.dp)
            .semantics(mergeDescendants = true) { heading(); contentDescription = cd }
            .padding(horizontal = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(arrowFor(bearing8), C.sign.white, 20.dp)
        Spacer(Modifier.width(8.dp))
        Txt(trip.title, T.sign.xl, C.sign.white, Modifier.weight(1f), maxLines = 1)
        Txt(RuFormat.thousands(trip.km), T.sign.xl, C.sign.white)
    }
}

@Composable
private fun Intro(trip: TripDto) {
    Column(Modifier.padding(start = 20.dp, end = 20.dp, top = 4.dp, bottom = 14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Txt(stringResource(R.string.road_title), T.display, C.text.primary, Modifier.semantics { heading() })
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            val nights = if (trip.nights > 0) {
                stringResource(R.string.common_join_dot) + "${trip.nights} ${pluralStringResource(R.plurals.plural_night, trip.nights)}"
            } else ""
            InfoChip(days(trip.days) + nights)
            InfoChip(crewShort(trip.input.crew.adults, trip.input.crew.children, trip.input.crew.dog))
            InfoChip(stringResource(R.string.road_chip_pace, RuFormat.thousands(trip.input.dailyKm)))
        }
        Txt(stringResource(R.string.road_intro), T.body.mdTight, C.text.secondary)
        for (w in trip.warnings) {
            val msg = w.message ?: continue
            Row(
                Modifier.fillMaxWidth().padding(top = 4.dp)
                    .border(DesignTokens.stroke.w1, C.accent.yellow, RoundedCornerShape(DesignTokens.radius.r10))
                    .padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(Modifier.width(14.dp).height(14.dp).clip(RoundedCornerShape(7.dp)).background(C.accent.yellow), contentAlignment = Alignment.Center) {
                    Txt("!", T.caption.bold, C.text.onLight)
                }
                Txt(msg, T.body.md, C.text.primary)
            }
        }
    }
}

/** The road column of one list item (5.5 §2.4): asphalt, edge lines, lane dashes; per item, so it scrolls. */
private fun Modifier.roadColumn(connector: Boolean): Modifier = drawBehind {
    val dp = 1.dp.toPx()
    drawRect(C.scene.road, Offset(14 * dp, 0f), Size(46 * dp, size.height))
    drawRect(C.scene.roadEdge, Offset(14 * dp, 0f), Size(3 * dp, size.height))
    drawRect(C.scene.roadEdge, Offset(57 * dp, 0f), Size(3 * dp, size.height))
    var y = 8 * dp
    while (y < size.height) {
        drawRect(C.scene.roadEdge, Offset(35.5f * dp, y), Size(3 * dp, minOf(32 * dp, size.height - y)))
        y += 64 * dp
    }
    if (connector) drawRect(C.interior.pole, Offset(60 * dp, 38 * dp), Size(14 * dp, 3 * dp))
}

@Composable
private fun DayHeader(day: DayDto, home: Boolean) {
    val hours = (day.driveMin / 60.0).roundToInt()
    val meta = if (home) stringResource(R.string.road_day_meta_home, RuFormat.thousands(day.km))
    else stringResource(R.string.road_day_meta, RuFormat.thousands(day.km), hours)
    val cd = stringResource(R.string.cd_road_day, day.day, day.km.toString(), hours, pluralStringResource(R.plurals.plural_hour, hours))
    Row(
        Modifier.fillMaxWidth().roadColumn(false).padding(start = 72.dp, end = 16.dp, top = 6.dp, bottom = 10.dp)
            .semantics(mergeDescendants = true) { heading(); contentDescription = cd },
        verticalAlignment = Alignment.Bottom,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Txt(stringResource(R.string.road_day, day.day), T.title.sm, C.accent.yellow)
        Txt(meta, T.body.sm, C.text.muted, maxLines = 1)
    }
}

@Composable
private fun StopRow(s: StopDto, first: Boolean) {
    val line1 = if (first || s.kind == "start") stringResource(R.string.road_start)
    else stringResource(R.string.road_ahead_km, RuFormat.thousands(s.kmFromPrev))
    val unverified = if (!s.verified) stringResource(R.string.common_join_dot) + stringResource(R.string.common_unverified) else ""
    val time = RuFormat.clock(s.arriveAt ?: s.departAt) ?: ""
    val name = when (s.kind) {
        "overnight" -> stringResource(R.string.road_name_night, s.name)
        else -> s.name
    }
    val note = s.note ?: s.reason
    val cost: String? = when (s.kind) {
        "sight" -> if (s.costRub == 0) stringResource(R.string.road_free) else rub(s.costRub)
        "food", "overnight" -> rub(s.costRub)
        "rest" -> stringResource(R.string.common_rub, "0")
        "fuel" -> if (s.costRub > 0) rub(s.costRub) else null
        else -> null
    }
    val cd = listOfNotNull(line1 + unverified, time, name, note, cost).joinToString(", ")
    Row(
        Modifier.fillMaxWidth().roadColumn(true).padding(top = 8.dp, bottom = 12.dp, end = 16.dp)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("road.stop.${s.id}"),
    ) {
        Box(Modifier.padding(start = 72.dp).width(68.dp), contentAlignment = Alignment.TopCenter) {
            RoadSign(s.sign, s.name, s.tags)
        }
        Column(Modifier.weight(1f).padding(start = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Txt(line1 + unverified, T.body.sm, C.text.muted, Modifier.weight(1f), maxLines = 1)
                Txt(time, T.body.sm, C.text.muted, align = TextAlign.End)
            }
            Txt(name, T.title.md, C.text.primary, maxLines = 2)
            if (!note.isNullOrBlank()) Txt(note, T.body.md, C.text.note)
            if (cost != null) Txt(cost, T.body.mdStrong, C.accent.yellow, Modifier.padding(top = 2.dp))
        }
    }
}

@Composable
private fun Footer(trip: TripDto) {
    val c = trip.cost
    val over = c.overBudget && c.budgetRub != null
    val label = if (over) stringResource(R.string.road_waybill_over, RuFormat.thousands(c.totalRub - (c.budgetRub ?: 0)))
    else stringResource(R.string.road_waybill_label)
    val total = rub(c.totalRub)
    val perPerson = stringResource(AppR.string.slice_per_person, RuFormat.thousands(c.perPersonRub))
    val cd = stringResource(R.string.cd_road_waybill, RuFormat.thousands(c.totalRub)) + ". " + perPerson
    Row(
        Modifier
            .fillMaxWidth()
            .padding(start = 16.dp, end = 16.dp, bottom = 24.dp)
            .height(DesignTokens.size.ctaWaybillH)
            .clip(RoundedCornerShape(DesignTokens.radius.r12))
            .background(C.sign.white)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("road.total")
            .padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Txt(label, T.body.smStrong, if (over) C.paper.inkRed else C.text.onLightMuted, maxLines = 1)
            Txt(total, T.amount, C.text.onLight, Modifier.testTag("road.total.amount"), maxLines = 1)
        }
        Txt(perPerson, T.body.mdStrong, C.text.onLightMuted, align = TextAlign.End)
    }
}
