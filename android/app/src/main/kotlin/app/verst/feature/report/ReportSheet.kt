package app.verst.feature.report

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.Reports
import app.verst.core.ui.R
import app.verst.core.ui.components.Txt
import app.verst.core.ui.theme.DesignTokens
import app.verst.feature.common.BottomSheet
import app.verst.core.ui.theme.DesignTokens.color as C
import app.verst.core.ui.theme.DesignTokens.type as T

/** What D-7 shows: the place (for TalkBack), the chosen reason, the comment. */
data class ReportUi(val name: String, val reason: String? = null, val comment: String = "")

interface ReportActions {
    fun close()
    fun reason(r: String)
    fun comment(t: String)
    fun send()
}

/**
 * D-7 «Что не так с местом?» (open-issues §4): four radio rows, an optional comment (≤ 280), «Отправить»
 * (YellowButton, disabled until a reason is chosen). Local in S3-R3: the report goes to the on-device queue.
 */
@Composable
fun BoxScope.ReportSheet(ui: ReportUi, windowH: Dp, a: ReportActions) {
    BottomSheet(stringResource(R.string.report_title), a::close, "report", windowH, pane = stringResource(R.string.report_title)) {
        Txt(ui.name, T.body.sm, C.text.muted, Modifier.testTag("report.place"), maxLines = 1)
        Spacer(Modifier.height(12.dp))
        val labels = mapOf(
            "closed" to stringResource(R.string.report_closed),
            "tags" to stringResource(R.string.report_tags),
            "price" to stringResource(R.string.report_price),
            "other" to stringResource(R.string.report_other),
        )
        Column(Modifier.fillMaxWidth().selectableGroup(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Reports.REASONS.forEach { r -> ReasonRow(labels.getValue(r), ui.reason == r, "report.reason.$r") { a.reason(r) } }
        }
        Spacer(Modifier.height(12.dp))
        CommentField(ui.comment, a::comment)
        Spacer(Modifier.height(16.dp))
        val enabled = ui.reason != null
        val shape = RoundedCornerShape(DesignTokens.radius.r12)
        Box(
            Modifier.fillMaxWidth().height(DesignTokens.size.buttonH).clip(shape)
                .background(if (enabled) C.accent.yellow else C.dash.controlAlt)
                .clickable(enabled = enabled, role = Role.Button, onClick = a::send)
                .semantics { if (!enabled) disabled() }
                .testTag("report.send"),
            contentAlignment = Alignment.Center,
        ) {
            Txt(stringResource(R.string.report_send).uppercase(), T.cta.sm, if (enabled) C.text.onLight else C.text.disabled, maxLines = 1, align = TextAlign.Center)
        }
    }
}

/** The D-6 radio look: min-h 52, `dash.controlAlt`, radius 10; selected = yellow ring + border. */
@Composable
private fun ReasonRow(label: String, selected: Boolean, tag: String, onClick: () -> Unit) {
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 52.dp).clip(shape).background(C.dash.controlAlt)
            .then(if (selected) Modifier.border(DesignTokens.stroke.w1, C.accent.yellow, shape) else Modifier)
            .selectable(selected, role = Role.RadioButton, onClick = onClick)
            .testTag(tag)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(18.dp).border(2.dp, if (selected) C.accent.yellow else C.text.secondary, RoundedCornerShape(9.dp)),
            contentAlignment = Alignment.Center,
        ) {
            if (selected) Box(Modifier.size(6.dp).clip(RoundedCornerShape(3.dp)).background(C.accent.yellow))
        }
        Spacer(Modifier.size(12.dp))
        Txt(label, T.body.md, C.text.primary, Modifier.weight(1f), maxLines = 2)
    }
}

/** NaviInput style (components §4): navi field, yellow border when focused, the placeholder `report_comment`. */
@Composable
private fun CommentField(value: String, onChange: (String) -> Unit) {
    var focused by remember { mutableStateOf(false) }
    val shape = RoundedCornerShape(DesignTokens.radius.r10)
    val hint = stringResource(R.string.report_comment)
    Box(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 56.dp).clip(shape).background(C.navi.field)
            .border(if (focused) DesignTokens.stroke.w2 else DesignTokens.stroke.w1, if (focused) C.accent.yellow else C.navi.fieldBorder, shape)
            .padding(horizontal = 12.dp, vertical = 14.dp),
    ) {
        BasicTextField(
            value = value,
            onValueChange = { onChange(it.take(Reports.COMMENT_MAX)) },
            textStyle = T.body.md.copy(color = C.text.primary),
            cursorBrush = SolidColor(C.accent.yellow),
            maxLines = 4,
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Default),
            modifier = Modifier.fillMaxWidth().onFocusChanged { focused = it.isFocused }
                .semantics { contentDescription = hint }.testTag("report.comment"),
            decorationBox = { inner ->
                Box {
                    if (value.isEmpty()) Txt(hint, T.body.md, C.navi.hint)
                    inner()
                }
            },
        )
    }
}
