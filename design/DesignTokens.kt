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
            val base: Color = Color(0xFFF5EFEB)
            /** Dashboard surface; root of Instruments, Road ahead, Waybill */
            val raised: Color = Color(0xFFFAF4EE)
            /** Bezels: navigator frame, start-button bezel, instrument-well border, dashboard rim line, secondary button fill */
            val control: Color = Color(0xFFE9DDD0)
            /** Keys (- / +), mirror bezel and stem, info chips */
            val controlAlt: Color = Color(0xFFFFFDF9)
            /** Instrument well (odometer, fuel gauge) background */
            val well: Color = Color(0xFFFFFDF9)
            /** Start-button face; odometer drums 1-3 */
            val face: Color = Color(0xFFFFF9F2)
            /** Inset bottom edge of keys (0 -3dp) */
            val keyShadow: Color = Color(0xFFC2AC95)
            /** Pressed row background on dashboard surfaces (mockup :hover) */
            val pressed: Color = Color(0xFFF0E5D9)
            /** Outline buttons (заменить, Сохранить офлайн); filled seat background */
            val outline: Color = Color(0xFFA08468)
            /** Empty-seat dashed border; front-passenger chip border when off */
            val outlineDashed: Color = Color(0xFF86694F)
            /** Back bench inside the large mirror */
            val bench: Color = Color(0xFFEADFD2)
            /** Odometer digit frame */
            val odometerFrame: Color = Color(0xFF2A1D13)
            /** Odometer drums 1-3 behind sign.white digits (D-IR-20 day palette: proposed token) */
            val odometerDrum: Color = Color(0xFF3A2A1D)
        }
        object interior {
            /** Roof liner and A-pillars */
            val liner: Color = Color(0xFFD2BEA6)
            /** Static roadside poles; itinerary row connector stub */
            val pole: Color = Color(0xFF8A735D)
        }
        object mirror {
            /** Mirror glass background and crew silhouettes in the small mirror */
            val glass: Color = Color(0xFF4A3525)
            /** Diagonal glare band on the small mirror */
            val glare: Color = Color(0xFFFFFFFF).copy(alpha = 0.22f)
            /** Mirror caption, back links on sky, adult silhouette in the large mirror */
            val label: Color = Color(0xFF2C1E13)
        }
        object text {
            /** Main text on dark */
            val primary: Color = Color(0xFF2C1E13)
            /** Secondary text on dark */
            val secondary: Color = Color(0xFF5C4636)
            /** Labels, captions, back links (min 11 sp) */
            val muted: Color = Color(0xFF6E5847)
            /** Stop note line on Road ahead */
            val note: Color = Color(0xFF4F3B2C)
            /** Empty-seat label "свободно" (AA fix; mockup #8C8C93 = 4.27:1) */
            val seatEmpty: Color = Color(0xFF644E3E)
            /** Text and pictograms on white or yellow */
            val onLight: Color = Color(0xFF2C1E13)
            /** Small label on the white Waybill button */
            val onLightMuted: Color = Color(0xFF5C4636)
            /** Disabled glyphs and labels (WCAG-exempt, still >= 3:1 on #161618) */
            val disabled: Color = Color(0xFF85705E)
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
            val white: Color = Color(0xFFFFFAF2)
            /** City-sign border, pictogram strokes */
            val black: Color = Color(0xFF2A1D13)
        }
        object accent {
            /** Selection, primary CTAs, prices, focus ring; dark backgrounds only */
            val yellow: Color = Color(0xFFF5A867)
            /** Pressed yellow CTA; pressed yellow link (mockup a:hover) */
            val yellowPressed: Color = Color(0xFFEB9550)
            /** Start-button ring, fuel-gauge E arc */
            val red: Color = Color(0xFFB23A22)
            /** Start-button pulse ring at t=0 */
            val redPulse: Color = Color(0xFFB23A22).copy(alpha = 0.55f)
            /** Red text on dark: gauge "E", overspend, offline plate (AA fix; #D8402B = 4.27:1 on well) */
            val redText: Color = Color(0xFFA3301B)
            /** Yellow as TEXT or thin line (prices, «вести», icons, radio, input focus border, cursor, progress fill, step check) (D-IR-20 day palette: proposed token) */
            val yellowText: Color = Color(0xFFA84B14)
        }
        object signal {
            /** Turn signal only */
            val green: Color = Color(0xFF588157)
        }
        object navi {
            /** Navigator display background */
            val screen: Color = Color(0xFFFBF6F0)
            /** Inputs and chips on the navigator; selected hotel row */
            val field: Color = Color(0xFFFFFDF9)
            /** Input border; outline button border; street badge */
            val fieldBorder: Color = Color(0xFF7A5E48)
            /** Navigator labels, secondary actions */
            val label: Color = Color(0xFFA84B14)
            /** Field captions, sub-lines */
            val labelSecondary: Color = Color(0xFF644E3E)
            /** Distances, reason sentence, chip text */
            val text: Color = Color(0xFF2C1E13)
            /** Placeholder and section labels on the navigator (AA fix; mockup #5F7487 = 3.34:1 on field) */
            val hint: Color = Color(0xFF6E5847)
            /** Suggestion row background */
            val list: Color = Color(0xFFFFFDF9)
            /** Selected suggestion row */
            val listSelected: Color = Color(0xFFFCE6D3)
            /** List border/dividers, progress-bar track */
            val divider: Color = Color(0xFFE3D4C3)
            /** Dashed button borders (text identifies the control) */
            val dashed: Color = Color(0xFF9C8169)
            /** Unselected radio ring (WCAG 1.4.11 fix; mockup #3A5266 = 2.31:1 on screen) */
            val radio: Color = Color(0xFF7A6350)
        }
        object sky {
            /** Sunset band 1 (top) */
            val band1: Color = Color(0xFFF1D3B3)
            /** Sunset band 2; mirror sky */
            val band2: Color = Color(0xFFF4DCC1)
            /** Sunset band 3 */
            val band3: Color = Color(0xFFF6E4CF)
            /** Sunset band 4 */
            val band4: Color = Color(0xFFF8EBDC)
            /** Sunset band 5 (horizon) */
            val band5: Color = Color(0xFFFAF1E7)
            /** Night sky on Exit */
            val night: Color = Color(0xFF2B2018)
            /** Hill silhouette */
            val hills: Color = Color(0xFFA9B48F)
        }
        object scene {
            /** Sun disc; town lights on Exit */
            val sun: Color = Color(0xFFFFD9A0)
            /** Crescent moon on Exit */
            val moon: Color = Color(0xFFF2E3B3)
            /** Stars on Exit */
            val star: Color = Color(0xFFFFF6E8)
            /** Fields (day/dusk); mirror ground */
            val groundDay: Color = Color(0xFF9CAF7E)
            /** Fields at night (Exit) */
            val groundNight: Color = Color(0xFF1F2A1C)
            /** Asphalt; itinerary road column */
            val road: Color = Color(0xFF6E6258)
            /** Asphalt at night (Exit) */
            val roadNight: Color = Color(0xFF2E2A27)
            /** Road edge lines and lane dashes */
            val roadEdge: Color = Color(0xFFFFFAF2)
            /** Road edge lines at night (Exit) */
            val roadEdgeNight: Color = Color(0xFFD9D2C6)
            /** Headlight beam on Exit */
            val headlight: Color = Color(0xFFFFECAA).copy(alpha = 0.1f)
        }
        object crew {
            /** Adult silhouette (large mirror) */
            val adult: Color = Color(0xFF4A3525)
            /** Child silhouette (large mirror) */
            val child: Color = Color(0xFFE87A3D)
            /** Dog in the boot */
            val dog: Color = Color(0xFFB07A45)
        }
        object paper {
            /** Waybill paper */
            val sheet: Color = Color(0xFFFFFBF5)
            /** Form lines, row dividers */
            val lines: Color = Color(0xFFC9B6A1)
            /** Printed text, table rules */
            val text: Color = Color(0xFF2C1E13)
            /** Printed small labels (AA fix; mockup #5B7186 = 4.49:1) */
            val label: Color = Color(0xFF644E3E)
            /** Handwriting ink */
            val ink: Color = Color(0xFF1E4FA3)
            /** Handwritten overspend (new; #D8402B on paper = 3.98:1) */
            val inkRed: Color = Color(0xFFB23A22)
            /** Stamp (drawn at 0.85 alpha = #715AAD effective) */
            val stamp: Color = Color(0xFFB23A22)
            /** Clipboard clip */
            val clip: Color = Color(0xFF8A735D)
            /** Clip inset bottom edge */
            val clipShadow: Color = Color(0xFF5C4636)
        }
        object city {
            /** City-walk scene: evening sky behind the facades (= sky.band1) */
            val sky: Color = Color(0xFFF1D3B3)
            /** City scene: near facades */
            val facadeA: Color = Color(0xFFCDA27C)
            /** City scene: middle facades */
            val facadeB: Color = Color(0xFFDDC3A6)
            /** City scene: far facades and roof line */
            val facadeC: Color = Color(0xFFC9B9A6)
            /** Lit windows and shop fronts (= scene.sun tone) */
            val window: Color = Color(0xFFFBEBD3)
            /** Unlit windows */
            val windowOff: Color = Color(0xFF6B5545)
            /** Street-lamp heads and their glow core */
            val lamp: Color = Color(0xFFEFE6DC)
            /** Street-lamp glow disc */
            val lampGlow: Color = Color(0xFFFFFFFF).copy(alpha = 0.12f)
            /** Pavement of the walk column and the city scene */
            val sidewalk: Color = Color(0xFFCFC2B3)
            /** Pavement tile joints */
            val joint: Color = Color(0xFFB8A998)
            /** Kerb line beside the pavement */
            val curb: Color = Color(0xFF8A7A6A)
            /** Moving footprints in the walk column */
            val footprint: Color = Color(0xFF4A3525).copy(alpha = 0.45f)
        }
        object photo {
            /** Photo frame background: placeholder, letterbox mat, loading base */
            val mat: Color = Color(0xFFEFE6DC)
            /** Placeholder pattern and shimmer highlight */
            val matHighlight: Color = Color(0xFFF7F0E8)
            /** Bottom gradient behind the photo credit (alpha at the bottom edge) */
            val scrim: Color = Color(0xFF000000).copy(alpha = 0.62f)
            /** Photo credit text on the scrim */
            val credit: Color = Color(0xFFF4F4F0)
            /** 1 dp inner border of the photo frame (keeps white photos from bleeding into white text) */
            val border: Color = Color(0xFFA68E77)
            /** Placeholder illustration lines */
            val ink: Color = Color(0xFF8A735D)
            /** Placeholder illustration fills (dome, trees, glass) */
            val accent: Color = Color(0xFFCDBCA8)
            /** Placeholder mat: museum */
            val phMuseum: Color = Color(0xFFEFE6DC)
            /** Placeholder mat: church, monastery, kremlin */
            val phChurch: Color = Color(0xFFF0E4DE)
            /** Placeholder mat: park, garden */
            val phPark: Color = Color(0xFFE5EADB)
            /** Placeholder mat: monument, memorial, square */
            val phMonument: Color = Color(0xFFEEE7DF)
            /** Placeholder mat: viewpoint, embankment */
            val phView: Color = Color(0xFFE4E8E5)
            /** Placeholder mat: bar, рюмочная, pub, craft */
            val phBar: Color = Color(0xFFF2E4D5)
            /** Placeholder mat: town, hotel area, other */
            val phCity: Color = Color(0xFFECE5DD)
        }
        object budget {
            /** «Не помещается в бюджет» plate fill */
            val overFill: Color = Color(0xFFF9E1D9)
            /** «Не помещается» plate border (= accent.red) */
            val overBorder: Color = Color(0xFFB23A22)
            /** «Впритык» text and dot (= accent.yellow) */
            val tight: Color = Color(0xFF8A4E0A)
        }
        object kind {
            /** Category tag fill (МУЗЕЙ, ПАРК…) on rows and cards (Sprint 4) */
            val fill: Color = Color(0xFFF6E6D6)
            /** Category tag border (= tourist brown) */
            val border: Color = Color(0xFF6B3E26)
            /** Category tag text (AA on fill) */
            val text: Color = Color(0xFF6B3E26)
        }
        object stretch {
            /** «РАЗМИНКА N МИН» tag fill (fun preset stops) */
            val fill: Color = Color(0xFFFDEBD3)
            /** «РАЗМИНКА» tag border */
            val border: Color = Color(0xFFB36A1E)
            /** «РАЗМИНКА» tag text (= accent.yellow) */
            val text: Color = Color(0xFF8A4E0A)
        }
        object hours {
            /** Opening hours «открыто» text / dot (Sprint 4 walks, cards) */
            val open: Color = Color(0xFF44703F)
            /** «открыто» pill fill */
            val openFill: Color = Color(0xFF44703F).copy(alpha = 0.12f)
            /** «сегодня закрыто» text (= accent.redText) */
            val closed: Color = Color(0xFFA3301B)
            /** «закрыто» pill fill */
            val closedFill: Color = Color(0xFFA3301B).copy(alpha = 0.1f)
            /** «часы не указаны» (= text.secondary) */
            val unknown: Color = Color(0xFF5C4636)
        }
        object info {
            /** Green info plate fill: how the walk was adapted to the crew */
            val fill: Color = Color(0xFFE6EEDF)
            /** Green info plate border */
            val border: Color = Color(0xFF9DB58F)
            /** Green info plate check disc */
            val mark: Color = Color(0xFF44703F)
        }
        object odometer {
            /** Odometer tag under a Road-ahead sign («193 км») */
            val fill: Color = Color(0xFF2A1D13)
            /** Odometer tag border (= dash.outline) */
            val border: Color = Color(0xFF5C4636)
        }
        object overlay {
            /** Scrim behind bottom sheets and dialogs (new) */
            val scrim: Color = Color(0xFF2C1E13).copy(alpha = 0.45f)
            /** Keyboard focus ring, 2dp, offset 2dp */
            val focus: Color = Color(0xFF1E4FA3)
            /** Returned-row highlight on Road ahead / walk list (motion.returnToItem) */
            val returnFlash: Color = Color(0xFFF4A261).copy(alpha = 0.3f)
        }
        /** Fork camper-ui (CEO 31.10): the «Кемпер-гид» paper palette of the Craft components (design/tokens-camper.json). */
        object camper {
            /** Camper: page background behind every screen (--bg-paper) */
            val page: Color = Color(0xFFF5EFEB)
            /** Camper: card paper (CraftCard, secondary button, idle icon tile; --card-paper) */
            val paper: Color = Color(0xFFFAF4EE)
            /** Camper: header bar, tab bar, sunken wells and the «Заменить» button fill */
            val header: Color = Color(0xFFEFE6DC)
            /** Camper: input / read-only field fill (white paper) */
            val field: Color = Color(0xFFFFFDF9)
            /** Camper: brown border of cards, buttons, fields, tiles and badges (--border-brown) */
            val border: Color = Color(0xFF4A3525)
            /** Camper: hard offset shadow of cards (3, 4 dp; --border-brown at 25 %) */
            val shadow: Color = Color(0xFF4A3525).copy(alpha = 0.25f)
            /** Camper: thin and dashed dividers inside cards (--border-brown at 20 %) */
            val divider: Color = Color(0xFF4A3525).copy(alpha = 0.2f)
            /** Camper: main text (--text-dark, darkened 2 % for 4.5:1 on dash.outline) */
            val ink: Color = Color(0xFF2C1E13)
            /** Camper: secondary text, field captions (8.0:1 on paper) */
            val inkSoft: Color = Color(0xFF5C4636)
            /** Camper: muted labels and footnotes (>= 4.5:1 on page, paper, header) */
            val inkMuted: Color = Color(0xFF6E5847)
            /** Camper: primary accent fill (CraftButton, active tab and tile, selected chip; --accent-orange) */
            val orange: Color = Color(0xFFE87A3D)
            /** Camper: pressed primary button fill */
            val orangePressed: Color = Color(0xFFD2672C)
            /** Camper: orange as TEXT on paper (overlines «КЕМПЕР-ГИД», links, prices) = accent.yellowText */
            val orangeText: Color = Color(0xFFA84B14)
            /** Camper: text and icons on camper.orange / green / blue fills (mockup white) */
            val onOrange: Color = Color(0xFFFFFFFF)
            /** Camper: badge fill, logo tile (--accent-amber) */
            val amber: Color = Color(0xFFF4A261)
            /** Camper: badge text on amber (mockup brown) */
            val onAmber: Color = Color(0xFF4A3525)
            /** Camper: green accent fill, badges «Включён», walking mode (--accent-green #588157, 2 % darker for 4.5:1 with white) */
            val green: Color = Color(0xFF557C54)
            /** Camper: green as TEXT on paper (savings «−4 000 ₽», «Резерв») */
            val greenText: Color = Color(0xFF44703F)
            /** Camper: blue accent (abroad, border badge; --accent-blue = sign.blue) */
            val blue: Color = Color(0xFF1E4FA3)
            /** Camper: stamp red (dashed stamp «ПРОВЕРЕНО», over-budget disc) */
            val stamp: Color = Color(0xFFB23A22)
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
        object photo {
            /** Photo credit on the scrim «Фото: … · Wikimedia Commons» */
            val credit: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W500,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** «ФОТО РАЙОНА» label over a hotel-area photo (uppercase copy) */
            val label: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.08.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
        object street {
            /** Street-name plate (city walk), e.g. «Покровка» */
            val name: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 22.sp,
                lineHeight = 24.2.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Street plate small line «улица», house number */
            val kind: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 12.sp,
                lineHeight = 14.4.sp,
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
        object tag {
            /** Category / «РАЗМИНКА» tag (uppercase copy) */
            val kind: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.06.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Odometer tag «193 км» under a Road-ahead sign */
            val odometer: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexMono,
                fontWeight = FontWeight.W600,
                fontSize = 11.sp,
                lineHeight = 14.3.sp,
                letterSpacing = 0.em,
                fontFeatureSettings = "tnum",
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Opening-hours line on a timed walk / card */
            val hours: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W600,
                fontSize = 12.sp,
                lineHeight = 15.6.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
            /** Opening-hours pill on an untimed walk («без ограничения») */
            val hoursLg: TextStyle = TextStyle(
                fontFamily = DesignTokens.font.plexSansCondensed,
                fontWeight = FontWeight.W700,
                fontSize = 14.sp,
                lineHeight = 18.2.sp,
                letterSpacing = 0.em,
                platformStyle = NoFontPadding,
                lineHeightStyle = CenteredLineHeight,
            )
        }
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
        /** Place-card photo frame width at 390 (= sheet content width; stretches L20/R20) */
        val photoW: Dp = 350.dp
        /** Card photo frame height = width / 1.5 (3:2 fixed aspect, ADR-0012 §6) */
        val photoH: Dp = 233.dp
        /** City-walk preset plate height */
        val presetH: Dp = 76.dp
        /** Street-name plate height */
        val streetPlateH: Dp = 64.dp
        /** Category tag height */
        val kindTagH: Dp = 20.dp
        /** Odometer tag min width */
        val odometerTagW: Dp = 50.dp
        /** Odometer tag height */
        val odometerTagH: Dp = 20.dp
        /** Road-ahead «Вести в навигаторе» button min height */
        val handoffCtaH: Dp = 60.dp
        /** Windshield «По городу пешком» plate height */
        val cityEntryH: Dp = 64.dp
        /** City-start crew stepper cell height */
        val crewCellH: Dp = 118.dp
        /** Untimed walk hours pill height */
        val hoursPillH: Dp = 24.dp
        /** Road-ahead car marker width */
        val carMarkerW: Dp = 18.dp
        /** Road-ahead car marker height */
        val carMarkerH: Dp = 32.dp
        /** Km post plate width */
        val kmPostW: Dp = 22.dp
        /** Km post plate height */
        val kmPostH: Dp = 26.dp
        /** Road-ahead road column width (incl. edges) */
        val roadW: Dp = 52.dp
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
        object photoFadeIn {
            const val durationMs: Int = 250
            val easing: Easing = DesignTokens.motion.easing.standard
            const val infinite: Boolean = false
        }
        object returnToItem {
            const val durationMs: Int = 0
            const val highlightMs: Int = 1200
            const val holdMs: Int = 400
            val easing: Easing = DesignTokens.motion.easing.easeOut
            const val infinite: Boolean = false
        }
        object footsteps {
            const val durationMs: Int = 1800
            val easing: Easing = DesignTokens.motion.easing.linear
            val periodDp: Dp = 48.dp
            const val infinite: Boolean = true
        }
        object lamps {
            const val durationMs: Int = 3200
            val easing: Easing = DesignTokens.motion.easing.easeInOut
            const val fromAlpha: Float = 0.7f
            const val toAlpha: Float = 1.0f
            const val infinite: Boolean = true
        }
        object shimmerDelay {
            const val durationMs: Int = 300
            val easing: Easing = DesignTokens.motion.easing.linear
            const val infinite: Boolean = false
        }
        object rebuildPulse {
            const val durationMs: Int = 1200
            val easing: Easing = DesignTokens.motion.easing.easeInOut
            const val fromAlpha: Float = 0.35f
            const val toAlpha: Float = 0.6f
            const val infinite: Boolean = true
        }
        object walkRebuild {
            const val durationMs: Int = 400
            val easing: Easing = DesignTokens.motion.easing.linear
            const val infinite: Boolean = false
        }
        object cityEntryPress {
            const val durationMs: Int = 90
            val easing: Easing = DesignTokens.motion.easing.standard
            const val infinite: Boolean = false
        }
        object limitSignIn {
            const val durationMs: Int = 400
            val easing: Easing = DesignTokens.motion.easing.decelerate
            const val fromScale: Float = 0.8f
            const val infinite: Boolean = false
        }
        const val frameBudgetMs: Int = 16
    }
}
