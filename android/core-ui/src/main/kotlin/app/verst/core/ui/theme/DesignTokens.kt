@file:Suppress("ClassName", "ObjectPropertyName", "MemberVisibilityCanBePrivate", "unused")

// GENERATED from design/tokens.json (Verst design v5 "За рулём", tokens 1.0.0). Do not edit by hand:
// change tokens.json and regenerate so that names and values stay identical.
// Naming rule: JSON path a.b.c == DesignTokens.a.b.c

package app.verst.core.ui.theme

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.Easing
import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.PlatformTextStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import app.verst.core.ui.R

/** A CSS-like box shadow. Draw with Paint.setShadowLayer (outer) or a clipped inset fill (inset). */
@Immutable
data class ShadowToken(
    val x: Dp,
    val y: Dp,
    val blur: Dp,
    val spread: Dp,
    val color: Color,
    val inset: Boolean,
)

private val NoFontPadding = PlatformTextStyle(includeFontPadding = false)
private val CenteredLineHeight = LineHeightStyle(
    alignment = LineHeightStyle.Alignment.Center,
    trim = LineHeightStyle.Trim.None,
)

object DesignTokens {
    object font {
        /** IBM Plex Sans Condensed (OFL-1.1), bundled in res/font */
        val plexSansCondensed: FontFamily = FontFamily(
            Font(R.font.ibm_plex_sans_condensed_regular, FontWeight.Normal),
            Font(R.font.ibm_plex_sans_condensed_medium, FontWeight.Medium),
            Font(R.font.ibm_plex_sans_condensed_semibold, FontWeight.SemiBold),
            Font(R.font.ibm_plex_sans_condensed_bold, FontWeight.Bold),
        )
        /** IBM Plex Mono (OFL-1.1), bundled in res/font */
        val plexMono: FontFamily = FontFamily(
            Font(R.font.ibm_plex_mono_semibold, FontWeight.SemiBold),
        )
        /** Marck Script (OFL-1.1), bundled in res/font */
        val marckScript: FontFamily = FontFamily(
            Font(R.font.marck_script_regular, FontWeight.Normal),
        )
    }
    object color {
        object dash {
            /** App background; root of Windshield, Navigator, Drive, Exit */
            val base: Color = Color(0xFF141416)
            /** Dashboard surface; root of Instruments, Road ahead, Waybill */
            val raised: Color = Color(0xFF161618)
            /** Bezels: navigator frame, start-button bezel, instrument-well border, dashboard rim line, secondary button fill */
            val control: Color = Color(0xFF232327)
            /** Keys (- / +), mirror bezel and stem, info chips */
            val controlAlt: Color = Color(0xFF2A2A2E)
            /** Instrument well (odometer, fuel gauge) background */
            val well: Color = Color(0xFF0F0F11)
            /** Start-button face; odometer drums 1-3 */
            val face: Color = Color(0xFF1C1C1F)
            /** Inset bottom edge of keys (0 -3dp) */
            val keyShadow: Color = Color(0xFF0E0E10)
            /** Pressed row background on dashboard surfaces (mockup :hover) */
            val pressed: Color = Color(0xFF1C1C20)
            /** Outline buttons (заменить, Сохранить офлайн); filled seat background */
            val outline: Color = Color(0xFF3A3A42)
            /** Empty-seat dashed border; front-passenger chip border when off */
            val outlineDashed: Color = Color(0xFF55555E)
            /** Back bench inside the large mirror */
            val bench: Color = Color(0xFF2A2A30)
            /** Odometer digit frame */
            val odometerFrame: Color = Color(0xFF000000)
        }
        object interior {
            /** Roof liner and A-pillars */
            val liner: Color = Color(0xFF0E0E10)
            /** Static roadside poles; itinerary row connector stub */
            val pole: Color = Color(0xFF55565C)
        }
        object mirror {
            /** Mirror glass background and crew silhouettes in the small mirror */
            val glass: Color = Color(0xFF0D0D0F)
            /** Diagonal glare band on the small mirror */
            val glare: Color = Color(0xFFFFFFFF).copy(alpha = 0.08f)
            /** Mirror caption, back links on sky, adult silhouette in the large mirror */
            val label: Color = Color(0xFFE9E2F2)
        }
        object text {
            /** Main text on dark */
            val primary: Color = Color(0xFFF4F4F0)
            /** Secondary text on dark */
            val secondary: Color = Color(0xFFB9B9C0)
            /** Labels, captions, back links (min 11 sp) */
            val muted: Color = Color(0xFF8C8C93)
            /** Stop note line on Road ahead */
            val note: Color = Color(0xFFC4C4CA)
            /** Empty-seat label "свободно" (AA fix; mockup #8C8C93 = 4.27:1) */
            val seatEmpty: Color = Color(0xFFA0A0A7)
            /** Text and pictograms on white or yellow */
            val onLight: Color = Color(0xFF141416)
            /** Small label on the white Waybill button */
            val onLightMuted: Color = Color(0xFF55565C)
            /** Disabled glyphs and labels (WCAG-exempt, still >= 3:1 on #161618) */
            val disabled: Color = Color(0xFF6C6C74)
        }
        object sign {
            /** GOST blue: overhead sign, service signs, exit sign, hotel button, city badge */
            val blue: Color = Color(0xFF1E4FA3)
            /** Selected overhead-sign row (AA fix; mockup rgba(255,255,255,.14) = #3E68B0 gives yellow 3.82:1) */
            val blueSelected: Color = Color(0xFF163B7A)
            /** Pressed overhead-sign row and pressed blue button */
            val bluePressed: Color = Color(0xFF1A468F)
            /** Small text on blue signs (header, footer) */
            val blueText: Color = Color(0xFFD6E0F5)
            /** Loading placeholder plates on blue signs */
            val plate: Color = Color(0xFFFFFFFF).copy(alpha = 0.1f)
            /** Shimmer highlight on placeholder plates */
            val plateHighlight: Color = Color(0xFFFFFFFF).copy(alpha = 0.2f)
            /** Tourist (sight) signs; place badge */
            val brown: Color = Color(0xFF6B3E26)
            /** City sign plate, sign borders, pictogram plates */
            val white: Color = Color(0xFFF4F4F0)
            /** City-sign border, pictogram strokes */
            val black: Color = Color(0xFF141416)
        }
        object accent {
            /** Selection, primary CTAs, prices, focus ring; dark backgrounds only */
            val yellow: Color = Color(0xFFFFD23F)
            /** Pressed yellow CTA; pressed yellow link (mockup a:hover) */
            val yellowPressed: Color = Color(0xFFFFE27A)
            /** Start-button ring, fuel-gauge E arc */
            val red: Color = Color(0xFFD8402B)
            /** Start-button pulse ring at t=0 */
            val redPulse: Color = Color(0xFFD8402B).copy(alpha = 0.55f)
            /** Red text on dark: gauge "E", overspend, offline plate (AA fix; #D8402B = 4.27:1 on well) */
            val redText: Color = Color(0xFFE6604A)
        }
        object signal {
            /** Turn signal only */
            val green: Color = Color(0xFF6FD18A)
        }
        object navi {
            /** Navigator display background */
            val screen: Color = Color(0xFF0B1218)
            /** Inputs and chips on the navigator; selected hotel row */
            val field: Color = Color(0xFF16222C)
            /** Input border; outline button border; street badge */
            val fieldBorder: Color = Color(0xFF2B3D4D)
            /** Navigator labels, secondary actions */
            val label: Color = Color(0xFF7FA6D9)
            /** Field captions, sub-lines */
            val labelSecondary: Color = Color(0xFF8FA4B8)
            /** Distances, reason sentence, chip text */
            val text: Color = Color(0xFFB9C6D3)
            /** Placeholder and section labels on the navigator (AA fix; mockup #5F7487 = 3.34:1 on field) */
            val hint: Color = Color(0xFF768DA3)
            /** Suggestion row background */
            val list: Color = Color(0xFF0F1A22)
            /** Selected suggestion row */
            val listSelected: Color = Color(0xFF1A2C3B)
            /** List border/dividers, progress-bar track */
            val divider: Color = Color(0xFF1E2E3A)
            /** Dashed button borders (text identifies the control) */
            val dashed: Color = Color(0xFF3A5266)
            /** Unselected radio ring (WCAG 1.4.11 fix; mockup #3A5266 = 2.31:1 on screen) */
            val radio: Color = Color(0xFF5A7893)
        }
        object sky {
            /** Sunset band 1 (top) */
            val band1: Color = Color(0xFF2B2850)
            /** Sunset band 2; mirror sky */
            val band2: Color = Color(0xFF4E3768)
            /** Sunset band 3 */
            val band3: Color = Color(0xFF8E4A6B)
            /** Sunset band 4 */
            val band4: Color = Color(0xFFD9655A)
            /** Sunset band 5 (horizon) */
            val band5: Color = Color(0xFFF29A5E)
            /** Night sky on Exit */
            val night: Color = Color(0xFF121130)
            /** Hill silhouette */
            val hills: Color = Color(0xFF3C3346)
        }
        object scene {
            /** Sun disc; town lights on Exit */
            val sun: Color = Color(0xFFFFD99A)
            /** Crescent moon on Exit */
            val moon: Color = Color(0xFFF2E3B3)
            /** Stars on Exit */
            val star: Color = Color(0xFFF4F4F0)
            /** Fields (day/dusk); mirror ground */
            val groundDay: Color = Color(0xFF2C3A33)
            /** Fields at night (Exit) */
            val groundNight: Color = Color(0xFF1A231F)
            /** Asphalt; itinerary road column */
            val road: Color = Color(0xFF3A3A3F)
            /** Asphalt at night (Exit) */
            val roadNight: Color = Color(0xFF2E2E33)
            /** Road edge lines and lane dashes */
            val roadEdge: Color = Color(0xFFF4F4F0)
            /** Road edge lines at night (Exit) */
            val roadEdgeNight: Color = Color(0xFFD9D9D2)
            /** Headlight beam on Exit */
            val headlight: Color = Color(0xFFFFECAA).copy(alpha = 0.1f)
        }
        object crew {
            /** Adult silhouette (large mirror) */
            val adult: Color = Color(0xFFE9E2F2)
            /** Child silhouette (large mirror) */
            val child: Color = Color(0xFFFFD23F)
            /** Dog in the boot */
            val dog: Color = Color(0xFFC99A5B)
        }
        object paper {
            /** Waybill paper */
            val sheet: Color = Color(0xFFEEF2F4)
            /** Form lines, row dividers */
            val lines: Color = Color(0xFF9FB0BE)
            /** Printed text, table rules */
            val text: Color = Color(0xFF22313D)
            /** Printed small labels (AA fix; mockup #5B7186 = 4.49:1) */
            val label: Color = Color(0xFF53687C)
            /** Handwriting ink */
            val ink: Color = Color(0xFF1B3FA0)
            /** Handwritten overspend (new; #D8402B on paper = 3.98:1) */
            val inkRed: Color = Color(0xFFB3261E)
            /** Stamp (drawn at 0.85 alpha = #715AAD effective) */
            val stamp: Color = Color(0xFF5B3FA0)
            /** Clipboard clip */
            val clip: Color = Color(0xFF8C8C93)
            /** Clip inset bottom edge */
            val clipShadow: Color = Color(0xFF5D5D63)
        }
        object overlay {
            /** Scrim behind bottom sheets and dialogs (new) */
            val scrim: Color = Color(0xFF000000).copy(alpha = 0.6f)
            /** Keyboard focus ring, 2dp, offset 2dp */
            val focus: Color = Color(0xFFFFD23F)
        }
    }
    object type {
        /** Screen title "Дорога впереди" */
        val display: TextStyle = TextStyle(
            fontFamily = DesignTokens.font.plexSansCondensed,
            fontWeight = FontWeight.W700,
            fontSize = 28.sp,
            lineHeight = 29.4.sp,
            letterSpacing = 0.em,
            platformStyle = NoFontPadding,
            lineHeightStyle = CenteredLineHeight,
        )
        object sign {
            /** Road-ahead overhead sign (title, km) */
            val xl: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 20.sp,
                lineHeight = 26.sp,
                letterSpacing = 0.em,
                fontFeatureSettings = "tnum",
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Exit sign town name */
            val xlTight: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 20.sp,
                lineHeight = 21.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Overhead-sign rows (name, km) */
            val lg: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 18.sp,
                lineHeight = 19.8.sp,
                letterSpacing = 0.em,
                fontFeatureSettings = "tnum",
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Distances on flying/exit signs ("70", "800 м") */
            val lgBold: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 18.sp,
                lineHeight = 23.4.sp,
                letterSpacing = 0.em,
                fontFeatureSettings = "tnum",
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Flying sign, 2-line town name */
            val md: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 15.sp,
                lineHeight = 15.75.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Exit sign second line "центр" */
            val mdSub: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 15.sp,
                lineHeight = 15.75.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Flying signs with pictogram, 2 lines */
            val sm: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 14.sp,
                lineHeight = 14.7.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** City-entrance sign text (uppercase copy) */
            val city: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 11.sp,
                lineHeight = 11.55.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object title {
            /** Windshield caption title, Exit town name */
            val xl: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 22.sp,
                lineHeight = 24.2.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Navigator/Instruments caption title */
            val lg: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 20.sp,
                lineHeight = 23.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Crew summary, budget value */
            val lgNum: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 20.sp,
                lineHeight = 26.sp,
                letterSpacing = 0.em,
                fontFeatureSettings = "tnum",
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Stop name */
            val md: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 17.sp,
                lineHeight = 19.55.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Day name, hotel option name and price */
            val sm: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 15.sp,
                lineHeight = 19.5.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        /** Waybill button amount "≈ 34 500 ₽" */
        val amount: TextStyle = TextStyle(
            fontFamily = DesignTokens.font.plexSansCondensed,
            fontWeight = FontWeight.W700,
            fontSize = 22.sp,
            lineHeight = 28.6.sp,
            letterSpacing = 0.em,
            fontFeatureSettings = "tnum",
            platformStyle = NoFontPadding,
            lineHeightStyle = CenteredLineHeight,
        )
        object cta {
            /** "Забронировать ночь" */
            val lg: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 18.sp,
                lineHeight = 19.8.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** "Дорога готова — смотреть знаки" */
            val md: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 17.sp,
                lineHeight = 22.1.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** "Отправить экипажу" */
            val sm: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 15.sp,
                lineHeight = 19.5.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object button {
            /** "Сохранить офлайн" (Waybill) */
            val md: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 15.sp,
                lineHeight = 19.5.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** "−" / "+" keys */
            val glyph: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 20.sp,
                lineHeight = 26.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** "ПОЕХАЛИ" on start button L/M */
            val startLabel: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 12.sp,
                lineHeight = 15.6.sp,
                letterSpacing = 0.06.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** "ПОЕХАЛИ" on start button S */
            val startLabelSm: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.06.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object field {
            /** Navigator text input value */
            val lg: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 18.sp,
                lineHeight = 26.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Navigator field value / entry title */
            val md: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 16.sp,
                lineHeight = 20.8.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object list {
            /** Suggestion name */
            val title: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 15.sp,
                lineHeight = 19.5.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object body {
            /** Drive progress steps */
            val step: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 14.sp,
                lineHeight = 18.2.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Notes, reasons (line-height 1.4) */
            val md: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 13.sp,
                lineHeight = 18.2.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Caption meta lines, hints, back links */
            val mdTight: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 13.sp,
                lineHeight = 16.9.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Costs, outline buttons, chips 13 */
            val mdStrong: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 13.sp,
                lineHeight = 16.9.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Sub-lines, "через N км", time */
            val sm: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 12.sp,
                lineHeight = 15.6.sp,
                letterSpacing = 0.em,
                fontFeatureSettings = "tnum",
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Info chips, "заменить", "изменить", turn label */
            val smStrong: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 12.sp,
                lineHeight = 15.6.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** CTA sub-line "через Яндекс Путешествия" */
            val smMedium: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W500,
                fontSize = 12.sp,
                lineHeight = 15.6.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Odometer read-out (line-height 1.35) */
            val smRelaxed: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 12.sp,
                lineHeight = 16.2.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object label {
            /** Section labels (uppercase copy) */
            val md: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.08.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Instrument-well labels (uppercase copy) */
            val wide: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.1.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object caption {
            /** Field captions, sign footer */
            val md: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Mirror caption, seat labels */
            val strong: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Gauge letters E/F, dog label */
            val bold: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        /** Suggestion type badge Г/У/М */
        val badge: TextStyle = TextStyle(
            fontFamily = DesignTokens.font.plexSansCondensed,
            fontWeight = FontWeight.W700,
            fontSize = 12.sp,
            lineHeight = 15.6.sp,
            letterSpacing = 0.em,
            platformStyle = NoFontPadding,
            lineHeightStyle = CenteredLineHeight,
        )
        /** Odometer digits */
        val odometer: TextStyle = TextStyle(
            fontFamily = DesignTokens.font.plexMono,
            fontWeight = FontWeight.W600,
            fontSize = 22.sp,
            lineHeight = 28.6.sp,
            letterSpacing = 0.em,
            fontFeatureSettings = "tnum",
            platformStyle = NoFontPadding,
            lineHeightStyle = CenteredLineHeight,
        )
        object paper {
            /** "ПУТЕВОЙ ЛИСТ" */
            val title: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 20.sp,
                lineHeight = 21.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Cost line name */
            val body: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 13.sp,
                lineHeight = 16.9.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** "ИТОГО" */
            val total: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 14.sp,
                lineHeight = 18.2.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** "легкового автомобиля" */
            val sub: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 12.sp,
                lineHeight = 15.6.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Form labels, reserve sub-line, footnote (mockup 10-11 sp) */
            val label: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** "ФОРМА ПОЕЗДКИ · ВЕРСТА" (mockup 10 sp) */
            val header: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.08.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** "СТАТЬЯ И РАСЧЁТ | ₽" (mockup 10 sp) */
            val tableHead: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W400,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.06.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object stamp {
            /** Stamp outer words (decorative, hidden from TalkBack) */
            val sm: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 10.sp,
                lineHeight = 12.sp,
                letterSpacing = 0.06.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Stamp centre "В ПУТЬ" */
            val lg: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 15.sp,
                lineHeight = 18.sp,
                letterSpacing = 0.06.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object hand {
            /** Handwritten total */
            val xl: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.marckScript,
                fontWeight = FontWeight.W400,
                fontSize = 26.sp,
                lineHeight = 31.2.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Handwritten form number "001" */
            val lg: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.marckScript,
                fontWeight = FontWeight.W400,
                fontSize = 20.sp,
                lineHeight = 24.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Handwritten values */
            val md: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.marckScript,
                fontWeight = FontWeight.W400,
                fontSize = 19.sp,
                lineHeight = 22.8.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Handwritten formulas */
            val sm: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.marckScript,
                fontWeight = FontWeight.W400,
                fontSize = 15.sp,
                lineHeight = 17.25.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
    }
    object space {
        val s1: Dp = 1.dp
        val s2: Dp = 2.dp
        val s3: Dp = 3.dp
        val s4: Dp = 4.dp
        val s5: Dp = 5.dp
        val s6: Dp = 6.dp
        val s8: Dp = 8.dp
        val s9: Dp = 9.dp
        val s10: Dp = 10.dp
        val s12: Dp = 12.dp
        val s14: Dp = 14.dp
        val s16: Dp = 16.dp
        val s18: Dp = 18.dp
        val s20: Dp = 20.dp
        val s22: Dp = 22.dp
        val s24: Dp = 24.dp
        val s26: Dp = 26.dp
    }
    object radius {
        /** Pictogram plate */
        val r2: Dp = 2.dp
        /** Odometer drum; tourist inner border */
        val r3: Dp = 3.dp
        /** City/service sign; sign row; paper */
        val r4: Dp = 4.dp
        /** Tourist sign outer; small sign inner border */
        val r5: Dp = 5.dp
        /** Overhead inner border; badge; odometer frame; flying sign outer */
        val r6: Dp = 6.dp
        /** Road-ahead overhead sign outer */
        val r7: Dp = 7.dp
        /** Small buttons; exit sign outer; clip */
        val r8: Dp = 8.dp
        /** Windshield overhead sign outer */
        val r9: Dp = 9.dp
        /** Fields, keys, hotel rows, dashed buttons */
        val r10: Dp = 10.dp
        /** CTAs; info chips */
        val r12: Dp = 12.dp
        /** Seat top corners; navigator chips */
        val r14: Dp = 14.dp
        /** Navigator panel; bottom sheets (new) */
        val r16: Dp = 16.dp
        /** Navigator panel (Navigator screen) */
        val r18: Dp = 18.dp
        /** Pill chip (front passenger) */
        val r20: Dp = 20.dp
        /** Small mirror */
        val r22: Dp = 22.dp
        /** Instrument wells */
        val r24: Dp = 24.dp
        /** Large mirror */
        val r40: Dp = 40.dp
        /** Circles (start button, sun, radio, stamp) */
        val full: Dp = 9999.dp
    }
    object stroke {
        /** Field border, dividers */
        val w1: Dp = 1.dp
        /** Paper table rules, checkbox */
        val w1_5: Dp = 1.5.dp
        /** Sign inner border, focus ring, seat border */
        val w2: Dp = 2.dp
        /** City sign border, start ring, mirror bezel S, road edge (itinerary) */
        val w3: Dp = 3.dp
        /** Well border; road edge (Navigator) */
        val w4: Dp = 4.dp
        /** Mirror bezel L */
        val w5: Dp = 5.dp
        /** Navigator bezel; road edge (Windshield/Drive/Exit) */
        val w6: Dp = 6.dp
        /** Navigator bezel (Navigator screen) */
        val w7: Dp = 7.dp
        object icon {
            /** Direction arrows on signs */
            val sign: Dp = 3.dp
            /** Tourist pictogram */
            val thin: Dp = 2.dp
            /** Service pictograms */
            val pictogram: Dp = 2.2.dp
            /** Search, power icons */
            val ui: Dp = 2.4.dp
            /** Back arrow */
            val back: Dp = 2.5.dp
            /** CTA arrows */
            val cta: Dp = 2.6.dp
        }
    }
    object shadow {
        /** Windshield overhead sign */
        val signLg = ShadowToken(x = 0.dp, y = 8.dp, blur = 18.dp, spread = 0.dp, color = Color(0xFF000000).copy(alpha = 0.35f), inset = false)
        /** Road-ahead overhead sign */
        val signMd = ShadowToken(x = 0.dp, y = 6.dp, blur = 14.dp, spread = 0.dp, color = Color(0xFF000000).copy(alpha = 0.35f), inset = false)
        /** Exit sign */
        val exitSign = ShadowToken(x = 0.dp, y = 8.dp, blur = 22.dp, spread = 0.dp, color = Color(0xFF000000).copy(alpha = 0.5f), inset = false)
        /** Large mirror */
        val mirror = ShadowToken(x = 0.dp, y = 10.dp, blur = 24.dp, spread = 0.dp, color = Color(0xFF000000).copy(alpha = 0.45f), inset = false)
        /** Waybill sheet */
        val paper = ShadowToken(x = 0.dp, y = 10.dp, blur = 26.dp, spread = 0.dp, color = Color(0xFF000000).copy(alpha = 0.5f), inset = false)
        /** Dashboard top rim line */
        val dashRim = ShadowToken(x = 0.dp, y = -2.dp, blur = 0.dp, spread = 0.dp, color = Color(0xFF232327), inset = false)
        /** Key bottom edge */
        val key = ShadowToken(x = 0.dp, y = -3.dp, blur = 0.dp, spread = 0.dp, color = Color(0xFF0E0E10), inset = true)
        /** Key bottom edge while pressed (new) */
        val keyPressed = ShadowToken(x = 0.dp, y = -2.dp, blur = 0.dp, spread = 0.dp, color = Color(0xFF0E0E10), inset = true)
        /** Clipboard clip bottom edge */
        val clip = ShadowToken(x = 0.dp, y = -4.dp, blur = 0.dp, spread = 0.dp, color = Color(0xFF5D5D63), inset = true)
        /** Text shadow under the mirror caption */
        val mirrorText = ShadowToken(x = 0.dp, y = 1.dp, blur = 2.dp, spread = 0.dp, color = Color(0xFF000000), inset = false)
    }
    object size {
        /** Minimum touch target */
        val touchMin: Dp = 44.dp
        /** Back link visual height (hit area 44) */
        val backLinkH: Dp = 32.dp
        /** Overhead-sign row height (mockup 42, raised to 44) */
        val signRowH: Dp = 44.dp
        /** Start button L bezel */
        val startLOuter: Dp = 100.dp
        /** Start button L face */
        val startLFace: Dp = 82.dp
        /** Start button L icon */
        val startLIcon: Dp = 20.dp
        /** Start button M bezel */
        val startMOuter: Dp = 92.dp
        /** Start button M face */
        val startMFace: Dp = 76.dp
        /** Start button M icon */
        val startMIcon: Dp = 18.dp
        /** Start button S bezel */
        val startSOuter: Dp = 86.dp
        /** Start button S face */
        val startSFace: Dp = 70.dp
        /** Start button S icon */
        val startSIcon: Dp = 16.dp
        /** Start ring stroke */
        val startRing: Dp = 3.dp
        /** Odometer drum width */
        val drumW: Dp = 24.dp
        /** Odometer drum height */
        val drumH: Dp = 34.dp
        /** Key width */
        val keyW: Dp = 52.dp
        /** Key height */
        val keyH: Dp = 44.dp
        /** Fuel gauge width */
        val gaugeW: Dp = 130.dp
        /** Fuel gauge height */
        val gaugeH: Dp = 62.dp
        /** Small mirror width */
        val mirrorSW: Dp = 150.dp
        /** Small mirror height */
        val mirrorSH: Dp = 44.dp
        /** Large mirror height (width = screen - 40) */
        val mirrorLH: Dp = 174.dp
        /** Seat button height */
        val seatH: Dp = 68.dp
        /** Drive CTA height */
        val ctaH: Dp = 58.dp
        /** Exit CTA height */
        val ctaBookH: Dp = 60.dp
        /** Road-ahead waybill button height */
        val ctaWaybillH: Dp = 64.dp
        /** Waybill buttons height */
        val buttonH: Dp = 56.dp
        /** Service sign width */
        val serviceSignW: Dp = 50.dp
        /** Service sign height */
        val serviceSignH: Dp = 62.dp
        /** Service sign white square */
        val pictogramPlate: Dp = 40.dp
        /** Tourist sign square */
        val touristSign: Dp = 56.dp
        /** City sign width */
        val citySignW: Dp = 64.dp
        /** City sign min height */
        val citySignMinH: Dp = 40.dp
        /** Hotel option min height */
        val hotelRowMinH: Dp = 60.dp
        /** Suggestion row min height */
        val suggestionRowMinH: Dp = 52.dp
        /** Bottom-sheet handle width (new) */
        val sheetHandleW: Dp = 36.dp
        /** Bottom-sheet handle height (new) */
        val sheetHandleH: Dp = 4.dp
    }
    object motion {
        object easing {
            val linear: Easing = CubicBezierEasing(0.0f, 0.0f, 1.0f, 1.0f)
            val standard: Easing = CubicBezierEasing(0.25f, 0.1f, 0.25f, 1.0f)
            val easeOut: Easing = CubicBezierEasing(0.0f, 0.0f, 0.58f, 1.0f)
            val easeInOut: Easing = CubicBezierEasing(0.42f, 0.0f, 0.58f, 1.0f)
            val postIn: Easing = CubicBezierEasing(0.55f, 0.0f, 1.0f, 0.45f)
            val rushIn: Easing = CubicBezierEasing(0.6f, 0.0f, 1.0f, 0.5f)
            val overshoot: Easing = CubicBezierEasing(0.3f, 1.4f, 0.5f, 1.0f)
            val decelerate: Easing = CubicBezierEasing(0.2f, 0.8f, 0.3f, 1.0f)
            val accelerate: Easing = CubicBezierEasing(0.4f, 0.0f, 1.0f, 1.0f)
        }
        object lane {
            object idle {
                const val durationMs: Int = 900
                val easing: Easing = DesignTokens.motion.easing.linear
                val periodDp: Dp = 160.dp
                val dashDp: Dp = 70.dp
                const val infinite: Boolean = true
            }
            object drive {
                const val durationMs: Int = 450
                val easing: Easing = DesignTokens.motion.easing.linear
                val periodDp: Dp = 160.dp
                val dashDp: Dp = 70.dp
                const val infinite: Boolean = true
            }
            object navi {
                const val durationMs: Int = 1400
                val easing: Easing = DesignTokens.motion.easing.linear
                val periodDp: Dp = 160.dp
                val dashDp: Dp = 70.dp
                const val infinite: Boolean = true
            }
            object exit {
                const val durationMs: Int = 1600
                val easing: Easing = DesignTokens.motion.easing.linear
                val periodDp: Dp = 160.dp
                val dashDp: Dp = 70.dp
                const val infinite: Boolean = true
            }
            object itinerary {
                const val durationMs: Int = 2200
                val easing: Easing = DesignTokens.motion.easing.linear
                val periodDp: Dp = 64.dp
                val dashDp: Dp = 32.dp
                const val infinite: Boolean = true
            }
        }
        object post {
            object idle {
                const val durationMs: Int = 2600
                const val offsetMs: Int = 1300
                val easing: Easing = DesignTokens.motion.easing.postIn
                const val fromScale: Float = 0.3f
                const val toScale: Float = 2.2f
                val dxDp: Dp = 150.dp
                val dyDp: Dp = 260.dp
                const val fadeInFraction: Float = 0.1f
                const val infinite: Boolean = true
            }
            object drive {
                const val durationMs: Int = 1100
                const val offsetMs: Int = 550
                val easing: Easing = DesignTokens.motion.easing.rushIn
                const val fromScale: Float = 0.2f
                const val toScale: Float = 2.4f
                val dxDp: Dp = 170.dp
                val dyDp: Dp = 230.dp
                const val fadeInFraction: Float = 0.1f
                const val infinite: Boolean = true
            }
        }
        object flyingSign {
            const val durationMs: Int = 3600
            const val staggerMs: Int = 1200
            val easing: Easing = DesignTokens.motion.easing.rushIn
            const val fromScale: Float = 0.12f
            const val toScale: Float = 1.7f
            val dxDp: Dp = 230.dp
            val dyDp: Dp = 40.dp
            const val fadeInFraction: Float = 0.15f
            const val infinite: Boolean = true
        }
        object startPulse {
            const val durationMs: Int = 1800
            val easing: Easing = DesignTokens.motion.easing.easeOut
            val fromSpreadDp: Dp = 0.dp
            val toSpreadDp: Dp = 16.dp
            val toSpreadSmDp: Dp = 14.dp
            const val fromAlpha: Float = 0.55f
            const val toAlpha: Float = 0.0f
            const val infinite: Boolean = true
        }
        object startPress {
            const val durationMs: Int = 120
            val easing: Easing = DesignTokens.motion.easing.standard
            const val toScale: Float = 0.96f
            const val infinite: Boolean = false
        }
        object mirrorSway {
            const val durationMs: Int = 4000
            val easing: Easing = DesignTokens.motion.easing.easeInOut
            const val fromDeg: Float = -1.5f
            const val toDeg: Float = 1.5f
            const val infinite: Boolean = true
        }
        object dogWag {
            const val durationMs: Int = 1200
            val easing: Easing = DesignTokens.motion.easing.easeInOut
            const val fromDeg: Float = -6.0f
            const val toDeg: Float = 6.0f
            const val infinite: Boolean = true
        }
        object selection {
            const val durationMs: Int = 200
            val easing: Easing = DesignTokens.motion.easing.standard
            const val infinite: Boolean = false
        }
        object needle {
            const val stiffness: Float = 300.0f
            const val dampingRatio: Float = 0.6f
            const val fromDeg: Float = -90.0f
            const val toDeg: Float = 90.0f
            const val stepDeg: Float = 36.0f
            const val infinite: Boolean = false
        }
        object odometerRoll {
            const val durationMs: Int = 300
            val easing: Easing = DesignTokens.motion.easing.decelerate
            const val infinite: Boolean = false
        }
        object caret {
            const val durationMs: Int = 1000
            const val onFraction: Float = 0.5f
            const val infinite: Boolean = true
        }
        object stepAppear {
            const val durationMs: Int = 350
            const val minGapMs: Int = 400
            val easing: Easing = DesignTokens.motion.easing.easeOut
            val fromDxDp: Dp = -6.dp
            const val infinite: Boolean = false
        }
        object progress {
            const val durationMs: Int = 400
            val easing: Easing = DesignTokens.motion.easing.easeInOut
            const val infinite: Boolean = false
        }
        object ctaAppear {
            const val durationMs: Int = 350
            val easing: Easing = DesignTokens.motion.easing.easeOut
            val fromDxDp: Dp = -6.dp
            const val autoAdvanceMs: Int = 1000
            const val infinite: Boolean = false
        }
        object stamp {
            const val durationMs: Int = 500
            const val delayMs: Int = 1000
            val easing: Easing = DesignTokens.motion.easing.overshoot
            const val fromScale: Float = 2.4f
            const val midScale: Float = 0.92f
            const val toScale: Float = 1.0f
            const val midFraction: Float = 0.6f
            const val rotationDeg: Float = -14.0f
            const val midAlpha: Float = 0.9f
            const val toAlpha: Float = 0.85f
            const val infinite: Boolean = false
        }
        object sheetSlide {
            const val durationMs: Int = 600
            val easing: Easing = DesignTokens.motion.easing.decelerate
            val fromDyDp: Dp = 40.dp
            const val infinite: Boolean = false
        }
        object exitNear {
            const val durationMs: Int = 2200
            val easing: Easing = DesignTokens.motion.easing.decelerate
            const val fromScale: Float = 0.7f
            val fromDxDp: Dp = -21.dp
            val fromDyDp: Dp = -14.dp
            const val fromAlpha: Float = 0.6f
            const val pivotX: Float = 0.3f
            const val pivotY: Float = 1.0f
            const val infinite: Boolean = false
        }
        object twinkle {
            const val durationMs: Int = 2400
            const val staggerMs: Int = 800
            val easing: Easing = DesignTokens.motion.easing.easeInOut
            const val fromAlpha: Float = 0.3f
            const val toAlpha: Float = 1.0f
            const val infinite: Boolean = true
        }
        object turnSignal {
            const val durationMs: Int = 900
            const val onMs: Int = 495
            const val offAlpha: Float = 0.15f
            const val infinite: Boolean = true
        }
        object carMarker {
            const val durationMs: Int = 14000
            val easing: Easing = DesignTokens.motion.easing.linear
            const val speedDpPerS: Float = 124.0f
            const val infinite: Boolean = true
        }
        object shimmer {
            const val durationMs: Int = 1200
            val easing: Easing = DesignTokens.motion.easing.linear
            const val infinite: Boolean = true
        }
        object bottomSheetIn {
            const val durationMs: Int = 300
            val easing: Easing = DesignTokens.motion.easing.decelerate
            const val infinite: Boolean = false
        }
        object bottomSheetOut {
            const val durationMs: Int = 200
            val easing: Easing = DesignTokens.motion.easing.accelerate
            const val infinite: Boolean = false
        }
        object toastIn {
            const val durationMs: Int = 200
            val easing: Easing = DesignTokens.motion.easing.decelerate
            val fromDyDp: Dp = 8.dp
            const val showMs: Int = 3000
            const val showWithActionMs: Int = 6000
            const val infinite: Boolean = false
        }
        object toastOut {
            const val durationMs: Int = 150
            val easing: Easing = DesignTokens.motion.easing.accelerate
            const val infinite: Boolean = false
        }
        object dialogIn {
            const val durationMs: Int = 200
            val easing: Easing = DesignTokens.motion.easing.decelerate
            const val fromScale: Float = 0.96f
            const val scrimAlpha: Float = 0.6f
            const val infinite: Boolean = false
        }
        object dialogOut {
            const val durationMs: Int = 150
            val easing: Easing = DesignTokens.motion.easing.accelerate
            const val infinite: Boolean = false
        }
        object captionFade {
            const val durationMs: Int = 150
            val easing: Easing = DesignTokens.motion.easing.standard
            const val infinite: Boolean = false
        }
        object laneSlowDown {
            const val durationMs: Int = 800
            val easing: Easing = DesignTokens.motion.easing.decelerate
            const val fromPeriodMs: Int = 450
            const val toPeriodMs: Int = 900
            const val infinite: Boolean = false
        }
        object rowFlash {
            const val durationMs: Int = 1200
            val easing: Easing = DesignTokens.motion.easing.easeOut
            const val infinite: Boolean = false
        }
        object valueCrossfade {
            const val durationMs: Int = 200
            val easing: Easing = DesignTokens.motion.easing.standard
            const val infinite: Boolean = false
        }
        object fieldPulse {
            const val durationMs: Int = 1200
            const val totalMs: Int = 2400
            val easing: Easing = DesignTokens.motion.easing.easeInOut
            const val fromAlpha: Float = 1.0f
            const val toAlpha: Float = 0.4f
            const val infinite: Boolean = false
        }
        object spinner {
            const val durationMs: Int = 900
            val easing: Easing = DesignTokens.motion.easing.linear
            const val sweepDeg: Float = 270.0f
            const val infinite: Boolean = true
        }
        object loadingDots {
            const val durationMs: Int = 900
            const val stepMs: Int = 300
            val dotDp: Dp = 4.dp
            const val infinite: Boolean = true
        }
        object rowRemove {
            const val durationMs: Int = 250
            val easing: Easing = DesignTokens.motion.easing.accelerate
            const val infinite: Boolean = false
        }
        object screen {
            object zoomToNavi {
                const val durationMs: Int = 450
                val easing: Easing = DesignTokens.motion.easing.decelerate
                const val infinite: Boolean = false
            }
            object lookAtMirror {
                const val durationMs: Int = 400
                val easing: Easing = DesignTokens.motion.easing.decelerate
                const val infinite: Boolean = false
            }
            object launch {
                const val durationMs: Int = 300
                val easing: Easing = DesignTokens.motion.easing.standard
                const val laneRampMs: Int = 800
                const val infinite: Boolean = false
            }
            object arrive {
                const val durationMs: Int = 450
                val easing: Easing = DesignTokens.motion.easing.decelerate
                const val infinite: Boolean = false
            }
            object overlay {
                const val durationMs: Int = 300
                val easing: Easing = DesignTokens.motion.easing.standard
                const val infinite: Boolean = false
            }
            object back {
                const val durationMs: Int = 300
                val easing: Easing = DesignTokens.motion.easing.decelerate
                const val infinite: Boolean = false
            }
        }
        const val frameBudgetMs: Int = 16
    }
}
