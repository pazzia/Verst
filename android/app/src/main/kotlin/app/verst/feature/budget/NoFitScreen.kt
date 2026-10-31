package app.verst.feature.budget

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.verst.core.model.dto.BudgetOptionDto
import app.verst.core.model.dto.NoFitDto
import app.verst.core.ui.R
import app.verst.core.ui.components.BackLink
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftCard
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftSectionTitle
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.DashedDivider
import app.verst.core.ui.components.Icon
import app.verst.core.ui.components.LocalReducedMotion
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftShadow
import app.verst.core.ui.components.craftSurface
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
 * 5.8 «Не помещается в бюджет» (ADR-0011), camper-ui fork (mockup screen 5): one card — the round red limit badge
 * with the budget, the title, the engine's text and the cheapest estimate — then the options as craft rows (engine
 * order: shorten, cheaper_route, raise_budget; the estimate green when it fits) and «Показать самый экономный
 * вариант» as the full-width button. Replaces Road ahead after Drive.
 */
@Composable
fun NoFitScreen(nf: NoFitDto, a: NoFitActions) {
    val min = nf.minimumTotalRub
    val cd = stringResource(R.string.cd_budget_nofit, app.verst.settings.AppPrefs.money(nf.budgetRub), app.verst.settings.AppPrefs.money(min))
    ScreenRoot(C.camper.page) {
        Column(Modifier.fillMaxSize().semantics { contentDescription = cd; liveRegion = LiveRegionMode.Polite }.testTag("nofit")) {
            val back = stringResource(R.string.common_back_instruments)
            BackLink(back, C.camper.inkSoft, stringResource(R.string.cd_back, back), a::back, Modifier.padding(start = 10.dp, top = 4.dp).testTag("nofit.back"))
            Column(
                Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, bottom = CraftDefaults.Gap),
                verticalArrangement = Arrangement.spacedBy(CraftDefaults.Gap),
            ) {
                CraftCard(Modifier.fillMaxWidth(), padding = PaddingValues(16.dp), spacing = 10.dp) {
                    LimitSign(nf.budgetRub, Modifier.align(Alignment.CenterHorizontally))
                    Txt(
                        stringResource(R.string.budget_nofit_title), CraftType.cardTitle, C.camper.ink,
                        Modifier.fillMaxWidth().semantics { heading() }, align = TextAlign.Center,
                    )
                    val text = nf.textRu ?: stringResource(R.string.budget_nofit_min, app.verst.settings.AppPrefs.money(min))
                    Txt(text, CraftType.body, C.camper.inkSoft, Modifier.fillMaxWidth().testTag("nofit.text"), align = TextAlign.Center)
                    DashedDivider()
                    // BudgetOverPlate: the cheapest variant's estimate
                    Column(Modifier.fillMaxWidth().testTag("nofit.minimum"), horizontalAlignment = Alignment.CenterHorizontally) {
                        Txt(stringResource(R.string.budget_nofit_min_label), CraftType.overline, C.accent.redText)
                        Txt(stringResource(R.string.common_estimate_rub, app.verst.settings.AppPrefs.money(min)), T.amount, C.camper.ink)
                    }
                }
                if (nf.options.isNotEmpty()) {
                    CraftSectionTitle(stringResource(R.string.budget_nofit_options))
                    CraftCard(Modifier.fillMaxWidth(), spacing = 8.dp) {
                        nf.options.forEachIndexed { i, o -> OptionRow(o, i, nf.budgetRub) { a.option(o) } }
                    }
                }
            }
            if (nf.minimum != null) {
                CraftButton(
                    stringResource(R.string.budget_show_minimum), a::showMinimum,
                    Modifier
                        .fillMaxWidth()
                        .padding(start = CraftDefaults.ScreenGutter, end = CraftDefaults.ScreenGutter, top = 4.dp, bottom = CraftDefaults.ScreenGutter)
                        .testTag("nofit.showMinimum"),
                )
            }
        }
    }
}

/**
 * components §20 `LimitSign` as the mockup's round red badge: the stamp-red disc with the brown frame and the hard
 * shadow, the budget in white; `limitSignIn` on entry.
 */
@Composable
private fun LimitSign(budget: Int, modifier: Modifier) {
    val reduced = LocalReducedMotion.current
    val k = remember { Animatable(if (reduced) 1f else 0f) }
    LaunchedEffect(Unit) { if (!reduced) k.animateTo(1f, tween(DesignTokens.motion.limitSignIn.durationMs, easing = DesignTokens.motion.limitSignIn.easing)) }
    val text = stringResource(R.string.budget_nofit_sign, app.verst.settings.AppPrefs.money(budget))
    val style = if (text.length >= 9) T.sign.lgBold.copy(fontSize = 14.sp) else T.sign.lgBold
    Box(
        modifier
            .size(84.dp)
            .graphicsLayer { scaleX = 0.8f + 0.2f * k.value; scaleY = 0.8f + 0.2f * k.value; alpha = k.value }
            .craftShadow(42.dp, CraftDefaults.TileShadow, CraftDefaults.TileShadow, C.camper.border)
            .background(C.camper.stamp, CircleShape)
            .border(CraftDefaults.BorderThin, C.camper.border, CircleShape)
            .padding(6.dp)
            .clearAndSetSemantics {}
            .testTag("nofit.sign"),
        contentAlignment = Alignment.Center,
    ) { Txt(text, style, C.camper.onOrange, maxLines = 1, align = TextAlign.Center) }
}

/** components §20 `BudgetOption` as a craft row: title, sub, the estimate (green when it fits), chevron. */
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
    // the engine's estimate of the option, green when it fits the budget (raising the budget keeps the same trip)
    val amount = if ((o.kind == "shorten" || o.kind == "cheaper_route") && o.totalRub != null) stringResource(R.string.common_estimate_rub, total) else null
    Row(
        Modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 64.dp)
            .craftSurface(fill = C.camper.field, radius = 14.dp, border = CraftDefaults.BorderThin, shadow = null)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics(mergeDescendants = true) { contentDescription = cd }
            .testTag("nofit.option.$index")
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Txt(title, CraftType.cardTitle, C.camper.ink, maxLines = 2)
            Txt(sub, CraftType.caption, C.camper.inkSoft, maxLines = 2)
        }
        if (amount != null) Txt(amount, T.body.smStrong, if (o.fits) C.camper.greenText else C.camper.inkSoft, maxLines = 1)
        Icon(R.drawable.ic_ui_chevron_right, C.camper.border, 14.dp)
    }
}
