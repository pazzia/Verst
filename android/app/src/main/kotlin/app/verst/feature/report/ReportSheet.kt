package app.verst.feature.report

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import app.verst.core.model.Reports
import app.verst.core.ui.R
import app.verst.core.ui.components.CraftButton
import app.verst.core.ui.components.CraftDefaults
import app.verst.core.ui.components.CraftType
import app.verst.core.ui.components.Txt
import app.verst.core.ui.components.craftField
import app.verst.feature.common.BottomSheet
import app.verst.core.ui.theme.DesignTokens.color as C

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
        Txt(ui.name, CraftType.caption, C.camper.inkSoft, Modifier.testTag("report.place"), maxLines = 1)
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
        // components §22 (S3-FINAL P1-03): no autofocus — the IME comes up only on a tap in the comment, then the
        // comment and «ОТПРАВИТЬ» are brought into view above it
        val bring = remember { androidx.compose.foundation.relocation.BringIntoViewRequester() }
        var commentFocused by remember { mutableStateOf(false) }
        // follow the IME while it animates in: every inset change brings the comment + button back into view
        val imeBottom = WindowInsets.ime.getBottom(androidx.compose.ui.platform.LocalDensity.current)
        androidx.compose.runtime.LaunchedEffect(commentFocused, imeBottom) {
            if (commentFocused) {
                kotlinx.coroutines.delay(50)
                bring.bringIntoView()
            }
        }
        Column(Modifier.fillMaxWidth().bringIntoViewRequester(bring)) {
        CommentField(ui.comment, a::comment) { commentFocused = it }
        Spacer(Modifier.height(16.dp))
        // the orange craft button, disabled (tan, no shadow) until a reason is chosen
        CraftButton(
            stringResource(R.string.report_send).uppercase(), a::send,
            Modifier.fillMaxWidth().testTag("report.send"), enabled = ui.reason != null,
        )
        }
    }
}

/** The D-6 radio row, camper fork: a white-paper craft field (min-h 52); selected = orange 2.5 dp border + orange dot. */
@Composable
private fun ReasonRow(label: String, selected: Boolean, tag: String, onClick: () -> Unit) {
    val shape = RoundedCornerShape(CraftDefaults.FieldRadius)
    Row(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 52.dp).clip(shape).background(C.camper.field)
            .border(if (selected) CraftDefaults.Border else CraftDefaults.BorderThin, if (selected) C.camper.orange else C.camper.border, shape)
            .selectable(selected, role = Role.RadioButton, onClick = onClick)
            .testTag(tag)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(20.dp).clip(CircleShape).background(C.camper.paper).border(2.dp, C.camper.border, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            if (selected) Box(Modifier.size(10.dp).clip(CircleShape).background(C.camper.orange))
        }
        Spacer(Modifier.size(12.dp))
        Txt(label, CraftType.body, C.camper.ink, Modifier.weight(1f), maxLines = 2)
    }
}

/** The comment field, camper fork: [craftField] (white paper, brown border; orange while focused), the placeholder `report_comment`. */
@Composable
private fun CommentField(value: String, onChange: (String) -> Unit, onFocused: (Boolean) -> Unit = {}) {
    var focused by remember { mutableStateOf(false) }
    val hint = stringResource(R.string.report_comment)
    Box(
        Modifier.fillMaxWidth().defaultMinSize(minHeight = 56.dp).craftField(focused = focused)
            .padding(horizontal = 12.dp, vertical = 14.dp),
    ) {
        BasicTextField(
            value = value,
            onValueChange = { onChange(it.take(Reports.COMMENT_MAX)) },
            textStyle = CraftType.field.copy(color = C.camper.ink),
            cursorBrush = SolidColor(C.camper.orange),
            maxLines = 4,
            keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Default),
            modifier = Modifier.fillMaxWidth().onFocusChanged { focused = it.isFocused; onFocused(it.isFocused) }
                .semantics { contentDescription = hint }.testTag("report.comment"),
            decorationBox = { inner ->
                Box {
                    if (value.isEmpty()) Txt(hint, CraftType.field, C.camper.inkMuted)
                    inner()
                }
            },
        )
    }
}
