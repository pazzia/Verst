package app.verst.feature.budget

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.verst.core.model.dto.BudgetOptionDto
import app.verst.core.model.dto.NoFitDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.Glyph
import app.verst.core.ui.components.GlyphIcon
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.SkyStrip
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.dashboardSurface
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.ScreenRoot
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

interface NoFitActions {
    fun back()
    fun option(o: BudgetOptionDto)
    fun showMinimum()
}

/**
 * 5.8 «Не помещается в бюджет» (ADR-0011): the round «ограничение» sign with the budget, the engine's text, the
 * cheapest plate, the options (engine order: shorten, cheaper_route, raise_budget) and «Показать самый экономный
 * вариант». Replaces Road ahead after Drive.
 */
@Composable
fun NoFitScreen(nf: NoFitDto, a: NoFitActions) {
    val min = nf.minimumTotalRub
    val cd = stringResource(R.string.cd_budget_nofit, app.verst.settings.AppPrefs.money(nf.budgetRub), app.verst.settings.AppPrefs.money(min))
    ScreenRoot(C.dash.raised, statusBar = C.sky.band1) {
        Column(Modifier.fillMaxSize().semantics { contentDescription = cd; liveRegion = LiveRegionMode.Polite }.testTag("nofit")) {
            Box(Modifier.fillMaxWidth().height(160.dp)) {
                SkyStrip(132.dp)
                Box(Modifier.fillMaxSize().padding(top = 110.dp).dashboardSurface(curve = 30.dp, rim = false))
                val back = stringResource(R.string.common_back_instruments)
                BackLink(back, C.mirror.label, stringResource(R.string.cd_back, back), a::back, Modifier.padding(start = 12.dp, top = 10.dp).testTag("nofit.back"))
                LimitSign(nf.budgetRub, Modifier.align(Alignment.TopCenter).padding(top = 56.dp))
            }
            Column(
                Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Spacer(Modifier.height(8.dp))
                Txt(stringResource(R.string.budget_nofit_title), T.display, C.text.primary, Modifier.semantics { heading() }, align = TextAlign.Center)
                Spacer(Modifier.height(8.dp))
                val text = nf.textRu ?: stringResource(R.string.budget_nofit_min, app.verst.settings.AppPrefs.money(min))
                Txt(text, T.body.md, C.text.secondary, Modifier.fillMaxWidth().testTag("nofit.text"), align = TextAlign.Center)
                Spacer(Modifier.height(12.dp))
                // BudgetOverPlate
                Column(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(DesignTokens.radius.r10)).background(C.budget.overFill)
                        .border(DesignTokens.stroke.w1, C.budget.overBorder, RoundedCornerShape(DesignTokens.radius.r10)).padding(12.dp)
                        .testTag("nofit.minimum"),
                ) {
                    Txt(stringResource(R.string.budget_nofit_min_label), T.label.md, C.accent.redText)
                    Txt(stringResource(R.string.common_estimate_rub, app.verst.settings.AppPrefs.money(min)), T.amount, C.text.primary)
                }
                Spacer(Modifier.height(20.dp))
                Txt(stringResource(R.string.budget_nofit_options), T.label.md, C.text.muted, Modifier.fillMaxWidth())
                Spacer(Modifier.height(8.dp))
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    nf.options.forEachIndexed { i, o -> OptionRow(o, i, nf.budgetRub) { a.option(o) } }
                }
                Spacer(Modifier.height(12.dp))
                if (nf.minimum != null) {
                    Box(
                        Modifier.defaultMinSize(minHeight = DesignTokens.size.touchMin).clickable(role = Role.Button, onClick = a::showMinimum).testTag("nofit.showMinimum"),
                        contentAlignment = Alignment.Center,
                    ) { Txt(stringResource(R.string.budget_show_minimum), T.body.mdStrong, C.text.secondary) }
                }
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}

/** components §20 `LimitSign`: 96 dp, white field, 10 dp red ring, 2 dp white outline; `limitSignIn` on entry. */
@Composable
private fun LimitSign(budget: Int, modifier: Modifier) {
    val reduced = LocalReducedMotion.current
    val k = remember { Animatable(if (reduced) 1f else 0f) }
    LaunchedEffect(Unit) { if (!reduced) k.animateTo(1f, tween(DesignTokens.motion.limitSignIn.durationMs, easing = DesignTokens.motion.limitSignIn.easing)) }
    val text = stringResource(R.string.budget_nofit_sign, app.verst.settings.AppPrefs.money(budget))
    val style = if (text.length >= 9) T.sign.lgBold.copy(fontSize = 15.sp) else T.sign.lgBold
    Box(
        modifier.size(96.dp).graphicsLayer { scaleX = 0.8f + 0.2f * k.value; scaleY = 0.8f + 0.2f * k.value; alpha = k.value }
            .clip(CircleShape).background(C.sign.white).padding(2.dp).clip(CircleShape).background(C.accent.red).padding(10.dp)
            .clip(CircleShape).background(C.sign.white).clearAndSetSemantics {}.testTag("nofit.sign"),
        contentAlignment = Alignment.Center,
    ) { Txt(text, style, C.text.onLight, maxLines = 1, align = TextAlign.Center) }
}

/** components §20 `BudgetOption`. */
@Composable
private fun OptionRow(o: BudgetOptionDto, index: Int, budget: Int, onClick: () -> Unit) {
    val total = o.totalRub?.let { app.verst.settings.AppPrefs.money(it) } ?: ""
    val (title, sub) = when (o.kind) {
        "shorten" -> stringResource(R.string.budget_option_shorten, o.days ?: 0, pluralStringResource(R.plurals.plural_day_until, o.days ?: 0)) to // «до 2 дней»
            stringResource(R.string.budget_option_shorten_sub, o.titleRu ?: "", total)
        "cheaper_route" -> stringResource(R.string.budget_option_cheaper, o.titleRu ?: "") to
            // `fits = false` (ARCH-301): the cheapest candidate is still over the budget — never «помещается»
            (if (o.fits) stringResource(R.string.budget_option_cheaper_sub, total) else stringResource(R.string.budget_option_cheaper_sub_over, total))
        else -> stringResource(R.string.budget_option_raise, app.verst.settings.AppPrefs.money(o.budgetRub ?: budget)) to stringResource(R.string.budget_option_raise_sub)
    }
    val cd = stringResource(R.string.cd_budget_option, title, sub)
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 64.dp).clip(shape).background(C.navi.field)
            .border(DesignTokens.stroke.w1, C.navi.fieldBorder, shape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("nofit.option.$index").padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Txt(title, T.title.sm, C.text.primary, maxLines = 2)
            Txt(sub, T.body.sm, C.navi.labelSecondary, maxLines = 2)
        }
        Spacer(Modifier.width(8.dp))
        GlyphIcon(Glyph.RIGHT, C.navi.label, 14.dp)
    }
}
