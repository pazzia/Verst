# Single source of truth for Verst design tokens -> tokens.json + DesignTokens.kt
import json, collections
O = collections.OrderedDict
def c(hexv, use, src=None, alpha=None):
    d = O(value=hexv)
    if alpha is not None: d['alpha'] = alpha
    d['use'] = use
    if src: d['mockupSource'] = src
    return d

color = O()
color['dash'] = O(
  base=c('#141416','App background; root of Windshield, Navigator, Drive, Exit'),
  raised=c('#161618','Dashboard surface; root of Instruments, Road ahead, Waybill'),
  control=c('#232327','Bezels: navigator frame, start-button bezel, instrument-well border, dashboard rim line, secondary button fill'),
  controlAlt=c('#2A2A2E','Keys (- / +), mirror bezel and stem, info chips'),
  well=c('#0F0F11','Instrument well (odometer, fuel gauge) background'),
  face=c('#1C1C1F','Start-button face; odometer drums 1-3'),
  keyShadow=c('#0E0E10','Inset bottom edge of keys (0 -3dp)'),
  pressed=c('#1C1C20','Pressed row background on dashboard surfaces (mockup :hover)'),
  outline=c('#3A3A42','Outline buttons (заменить, Сохранить офлайн); filled seat background'),
  outlineDashed=c('#55555E','Empty-seat dashed border; front-passenger chip border when off'),
  bench=c('#2A2A30','Back bench inside the large mirror'),
  odometerFrame=c('#000000','Odometer digit frame'),
)
color['interior'] = O(
  liner=c('#0E0E10','Roof liner and A-pillars'),
  pole=c('#55565C','Static roadside poles; itinerary row connector stub'),
)
color['mirror'] = O(
  glass=c('#0D0D0F','Mirror glass background and crew silhouettes in the small mirror'),
  glare=c('#FFFFFF','Diagonal glare band on the small mirror', alpha=0.08),
  label=c('#E9E2F2','Mirror caption, back links on sky, adult silhouette in the large mirror'),
)
color['text'] = O(
  primary=c('#F4F4F0','Main text on dark'),
  secondary=c('#B9B9C0','Secondary text on dark'),
  muted=c('#8C8C93','Labels, captions, back links (min 11 sp)'),
  note=c('#C4C4CA','Stop note line on Road ahead'),
  seatEmpty=c('#A0A0A7','Empty-seat label "свободно" (AA fix; mockup #8C8C93 = 4.27:1)', '#8C8C93'),
  onLight=c('#141416','Text and pictograms on white or yellow'),
  onLightMuted=c('#55565C','Small label on the white Waybill button'),
  disabled=c('#6C6C74','Disabled glyphs and labels (WCAG-exempt, still >= 3:1 on #161618)'),
)
color['sign'] = O(
  blue=c('#1E4FA3','GOST blue: overhead sign, service signs, exit sign, hotel button, city badge'),
  blueSelected=c('#163B7A','Selected overhead-sign row (AA fix; mockup rgba(255,255,255,.14) = #3E68B0 gives yellow 3.82:1)', 'rgba(255,255,255,.14)'),
  bluePressed=c('#1A468F','Pressed overhead-sign row and pressed blue button'),
  blueText=c('#D6E0F5','Small text on blue signs (header, footer)'),
  plate=c('#FFFFFF','Loading placeholder plates on blue signs', alpha=0.10),
  plateHighlight=c('#FFFFFF','Shimmer highlight on placeholder plates', alpha=0.20),
  brown=c('#6B3E26','Tourist (sight) signs; place badge'),
  white=c('#F4F4F0','City sign plate, sign borders, pictogram plates'),
  black=c('#141416','City-sign border, pictogram strokes'),
)
color['accent'] = O(
  yellow=c('#FFD23F','Selection, primary CTAs, prices, focus ring; dark backgrounds only'),
  yellowPressed=c('#FFE27A','Pressed yellow CTA; pressed yellow link (mockup a:hover)'),
  red=c('#D8402B','Start-button ring, fuel-gauge E arc'),
  redPulse=c('#D8402B','Start-button pulse ring at t=0', alpha=0.55),
  redText=c('#E6604A','Red text on dark: gauge "E", overspend, offline plate (AA fix; #D8402B = 4.27:1 on well)', '#D8402B'),
)
color['signal'] = O(green=c('#6FD18A','Turn signal only'))
color['navi'] = O(
  screen=c('#0B1218','Navigator display background'),
  field=c('#16222C','Inputs and chips on the navigator; selected hotel row'),
  fieldBorder=c('#2B3D4D','Input border; outline button border; street badge'),
  label=c('#7FA6D9','Navigator labels, secondary actions'),
  labelSecondary=c('#8FA4B8','Field captions, sub-lines'),
  text=c('#B9C6D3','Distances, reason sentence, chip text'),
  hint=c('#768DA3','Placeholder and section labels on the navigator (AA fix; mockup #5F7487 = 3.34:1 on field)', '#5F7487'),
  list=c('#0F1A22','Suggestion row background'),
  listSelected=c('#1A2C3B','Selected suggestion row'),
  divider=c('#1E2E3A','List border/dividers, progress-bar track'),
  dashed=c('#3A5266','Dashed button borders (text identifies the control)'),
  radio=c('#5A7893','Unselected radio ring (WCAG 1.4.11 fix; mockup #3A5266 = 2.31:1 on screen)', '#3A5266'),
)
color['sky'] = O(
  band1=c('#2B2850','Sunset band 1 (top)'), band2=c('#4E3768','Sunset band 2; mirror sky'),
  band3=c('#8E4A6B','Sunset band 3'), band4=c('#D9655A','Sunset band 4'), band5=c('#F29A5E','Sunset band 5 (horizon)'),
  night=c('#121130','Night sky on Exit'), hills=c('#3C3346','Hill silhouette'),
)
color['scene'] = O(
  sun=c('#FFD99A','Sun disc; town lights on Exit'),
  moon=c('#F2E3B3','Crescent moon on Exit'),
  star=c('#F4F4F0','Stars on Exit'),
  groundDay=c('#2C3A33','Fields (day/dusk); mirror ground'),
  groundNight=c('#1A231F','Fields at night (Exit)'),
  road=c('#3A3A3F','Asphalt; itinerary road column'),
  roadNight=c('#2E2E33','Asphalt at night (Exit)'),
  roadEdge=c('#F4F4F0','Road edge lines and lane dashes'),
  roadEdgeNight=c('#D9D9D2','Road edge lines at night (Exit)'),
  headlight=c('#FFECAA','Headlight beam on Exit', alpha=0.10),
)
color['crew'] = O(
  adult=c('#E9E2F2','Adult silhouette (large mirror)'),
  child=c('#FFD23F','Child silhouette (large mirror)'),
  dog=c('#C99A5B','Dog in the boot'),
)
color['paper'] = O(
  sheet=c('#EEF2F4','Waybill paper'),
  lines=c('#9FB0BE','Form lines, row dividers'),
  text=c('#22313D','Printed text, table rules'),
  label=c('#53687C','Printed small labels (AA fix; mockup #5B7186 = 4.49:1)', '#5B7186'),
  ink=c('#1B3FA0','Handwriting ink'),
  inkRed=c('#B3261E','Handwritten overspend (new; #D8402B on paper = 3.98:1)'),
  stamp=c('#5B3FA0','Stamp (drawn at 0.85 alpha = #715AAD effective)'),
  clip=c('#8C8C93','Clipboard clip'),
  clipShadow=c('#5D5D63','Clip inset bottom edge'),
)
color['overlay'] = O(
  scrim=c('#000000','Scrim behind bottom sheets and dialogs (new)', alpha=0.60),
  focus=c('#FFD23F','Keyboard focus ring, 2dp, offset 2dp'),
)

F = O(
  plexSansCondensed=O(family='IBM Plex Sans Condensed', files=O([('400','ibm_plex_sans_condensed_regular.ttf'),('500','ibm_plex_sans_condensed_medium.ttf'),('600','ibm_plex_sans_condensed_semibold.ttf'),('700','ibm_plex_sans_condensed_bold.ttf')]), licence='OFL-1.1'),
  plexMono=O(family='IBM Plex Mono', files=O([('600','ibm_plex_mono_semibold.ttf')]), licence='OFL-1.1'),
  marckScript=O(family='Marck Script', files=O([('400','marck_script_regular.ttf')]), licence='OFL-1.1'),
)
def t(fam, w, size, lh, ls=0, tnum=False, use=''):
    d = O(fontFamily='font.'+fam, fontWeight=w, fontSizeSp=size, lineHeightSp=lh, letterSpacingEm=ls)
    d['fontFeatures'] = 'tnum' if tnum else ''
    d['use'] = use
    return d
S='plexSansCondensed'; M='plexMono'; H='marckScript'
typ = O()
typ['display'] = t(S,700,28,29.4,use='Screen title "Дорога впереди"')
typ['sign'] = O(
  xl=t(S,700,20,26,tnum=True,use='Road-ahead overhead sign (title, km)'),
  xlTight=t(S,700,20,21,use='Exit sign town name'),
  lg=t(S,600,18,19.8,tnum=True,use='Overhead-sign rows (name, km)'),
  lgBold=t(S,700,18,23.4,tnum=True,use='Distances on flying/exit signs ("70", "800 м")'),
  md=t(S,700,15,15.75,use='Flying sign, 2-line town name'),
  mdSub=t(S,600,15,15.75,use='Exit sign second line "центр"'),
  sm=t(S,700,14,14.7,use='Flying signs with pictogram, 2 lines'),
  city=t(S,700,11,11.55,use='City-entrance sign text (uppercase copy)'),
)
typ['title'] = O(
  xl=t(S,700,22,24.2,use='Windshield caption title, Exit town name'),
  lg=t(S,700,20,23,use='Navigator/Instruments caption title'),
  lgNum=t(S,700,20,26,tnum=True,use='Crew summary, budget value'),
  md=t(S,700,17,19.55,use='Stop name'),
  sm=t(S,700,15,19.5,use='Day name, hotel option name and price'),
)
typ['amount'] = t(S,700,22,28.6,tnum=True,use='Waybill button amount "≈ 34 500 ₽"')
typ['cta'] = O(
  lg=t(S,700,18,19.8,use='"Забронировать ночь"'),
  md=t(S,700,17,22.1,use='"Дорога готова — смотреть знаки"'),
  sm=t(S,700,15,19.5,use='"Отправить экипажу"'),
)
typ['button'] = O(
  md=t(S,600,15,19.5,use='"Сохранить офлайн" (Waybill)'),
  glyph=t(S,400,20,26,use='"−" / "+" keys'),
  startLabel=t(S,700,12,15.6,ls=0.06,use='"ПОЕХАЛИ" on start button L/M'),
  startLabelSm=t(S,700,11,14.3,ls=0.06,use='"ПОЕХАЛИ" on start button S'),
)
typ['field'] = O(
  lg=t(S,600,18,26,use='Navigator text input value'),
  md=t(S,600,16,20.8,use='Navigator field value / entry title'),
)
typ['list'] = O(title=t(S,600,15,19.5,use='Suggestion name'))
typ['body'] = O(
  step=t(S,400,14,18.2,use='Drive progress steps'),
  md=t(S,400,13,18.2,use='Notes, reasons (line-height 1.4)'),
  mdTight=t(S,400,13,16.9,use='Caption meta lines, hints, back links'),
  mdStrong=t(S,600,13,16.9,use='Costs, outline buttons, chips 13'),
  sm=t(S,400,12,15.6,tnum=True,use='Sub-lines, "через N км", time'),
  smStrong=t(S,600,12,15.6,use='Info chips, "заменить", "изменить", turn label'),
  smMedium=t(S,500,12,15.6,use='CTA sub-line "через Яндекс Путешествия"'),
  smRelaxed=t(S,400,12,16.2,use='Odometer read-out (line-height 1.35)'),
)
typ['label'] = O(
  md=t(S,600,11,14.3,ls=0.08,use='Section labels (uppercase copy)'),
  wide=t(S,600,11,14.3,ls=0.10,use='Instrument-well labels (uppercase copy)'),
)
typ['caption'] = O(
  md=t(S,400,11,14.3,use='Field captions, sign footer'),
  strong=t(S,600,11,14.3,use='Mirror caption, seat labels'),
  bold=t(S,700,11,14.3,use='Gauge letters E/F, dog label'),
)
typ['badge'] = t(S,700,12,15.6,use='Suggestion type badge Г/У/М')
typ['odometer'] = t(M,600,22,28.6,tnum=True,use='Odometer digits')
typ['paper'] = O(
  title=t(S,700,20,21,use='"ПУТЕВОЙ ЛИСТ"'),
  body=t(S,600,13,16.9,use='Cost line name'),
  total=t(S,700,14,18.2,use='"ИТОГО"'),
  sub=t(S,400,12,15.6,use='"легкового автомобиля"'),
  label=t(S,400,11,14.3,use='Form labels, reserve sub-line, footnote (mockup 10-11 sp)'),
  header=t(S,400,11,14.3,ls=0.08,use='"ФОРМА ПОЕЗДКИ · ВЕРСТА" (mockup 10 sp)'),
  tableHead=t(S,400,11,14.3,ls=0.06,use='"СТАТЬЯ И РАСЧЁТ | ₽" (mockup 10 sp)'),
)
typ['stamp'] = O(
  sm=t(S,700,10,12,ls=0.06,use='Stamp outer words (decorative, hidden from TalkBack)'),
  lg=t(S,700,15,18,ls=0.06,use='Stamp centre "В ПУТЬ"'),
)
typ['hand'] = O(
  xl=t(H,400,26,31.2,use='Handwritten total'),
  lg=t(H,400,20,24,use='Handwritten form number "001"'),
  md=t(H,400,19,22.8,use='Handwritten values'),
  sm=t(H,400,15,17.25,use='Handwritten formulas'),
)

def dp(v, use=''): return O(value=v, unit='dp', use=use)
space = O()
for v in [1,2,3,4,5,6,8,9,10,12,14,16,18,20,22,24,26]:
    space['s%d'%v] = dp(v)
radius = O()
for v,u in [(2,'Pictogram plate'),(3,'Odometer drum; tourist inner border'),(4,'City/service sign; sign row; paper'),(5,'Tourist sign outer; small sign inner border'),(6,'Overhead inner border; badge; odometer frame; flying sign outer'),(7,'Road-ahead overhead sign outer'),(8,'Small buttons; exit sign outer; clip'),(9,'Windshield overhead sign outer'),(10,'Fields, keys, hotel rows, dashed buttons'),(12,'CTAs; info chips'),(14,'Seat top corners; navigator chips'),(16,'Navigator panel; bottom sheets (new)'),(18,'Navigator panel (Navigator screen)'),(20,'Pill chip (front passenger)'),(22,'Small mirror'),(24,'Instrument wells'),(40,'Large mirror')]:
    radius['r%d'%v] = dp(v,u)
radius['full'] = dp(9999,'Circles (start button, sun, radio, stamp)')
stroke = O()
for k,v,u in [('w1',1,'Field border, dividers'),('w1_5',1.5,'Paper table rules, checkbox'),('w2',2,'Sign inner border, focus ring, seat border'),('w3',3,'City sign border, start ring, mirror bezel S, road edge (itinerary)'),('w4',4,'Well border; road edge (Navigator)'),('w5',5,'Mirror bezel L'),('w6',6,'Navigator bezel; road edge (Windshield/Drive/Exit)'),('w7',7,'Navigator bezel (Navigator screen)')]:
    stroke[k] = dp(v,u)
stroke['icon'] = O(
  sign=dp(3,'Direction arrows on signs'), thin=dp(2,'Tourist pictogram'), pictogram=dp(2.2,'Service pictograms'),
  ui=dp(2.4,'Search, power icons'), back=dp(2.5,'Back arrow'), cta=dp(2.6,'CTA arrows'))
def sh(x,y,blur,spread,col,alpha,inset,use):
    return O(xDp=x,yDp=y,blurDp=blur,spreadDp=spread,color=col,alpha=alpha,inset=inset,use=use)
shadow = O(
  signLg=sh(0,8,18,0,'#000000',0.35,False,'Windshield overhead sign'),
  signMd=sh(0,6,14,0,'#000000',0.35,False,'Road-ahead overhead sign'),
  exitSign=sh(0,8,22,0,'#000000',0.50,False,'Exit sign'),
  mirror=sh(0,10,24,0,'#000000',0.45,False,'Large mirror'),
  paper=sh(0,10,26,0,'#000000',0.50,False,'Waybill sheet'),
  dashRim=sh(0,-2,0,0,'#232327',1.0,False,'Dashboard top rim line'),
  key=sh(0,-3,0,0,'#0E0E10',1.0,True,'Key bottom edge'),
  keyPressed=sh(0,-2,0,0,'#0E0E10',1.0,True,'Key bottom edge while pressed (new)'),
  clip=sh(0,-4,0,0,'#5D5D63',1.0,True,'Clipboard clip bottom edge'),
  mirrorText=sh(0,1,2,0,'#000000',1.0,False,'Text shadow under the mirror caption'),
)
size = O(
  touchMin=dp(44,'Minimum touch target'),
  backLinkH=dp(32,'Back link visual height (hit area 44)'),
  signRowH=dp(44,'Overhead-sign row height (mockup 42, raised to 44)'),
  startLOuter=dp(100,'Start button L bezel'), startLFace=dp(82,'Start button L face'), startLIcon=dp(20,'Start button L icon'),
  startMOuter=dp(92,'Start button M bezel'), startMFace=dp(76,'Start button M face'), startMIcon=dp(18,'Start button M icon'),
  startSOuter=dp(86,'Start button S bezel'), startSFace=dp(70,'Start button S face'), startSIcon=dp(16,'Start button S icon'),
  startRing=dp(3,'Start ring stroke'),
  drumW=dp(24,'Odometer drum width'), drumH=dp(34,'Odometer drum height'),
  keyW=dp(52,'Key width'), keyH=dp(44,'Key height'),
  gaugeW=dp(130,'Fuel gauge width'), gaugeH=dp(62,'Fuel gauge height'),
  mirrorSW=dp(150,'Small mirror width'), mirrorSH=dp(44,'Small mirror height'),
  mirrorLH=dp(174,'Large mirror height (width = screen - 40)'),
  seatH=dp(68,'Seat button height'),
  ctaH=dp(58,'Drive CTA height'), ctaBookH=dp(60,'Exit CTA height'), ctaWaybillH=dp(64,'Road-ahead waybill button height'), buttonH=dp(56,'Waybill buttons height'),
  serviceSignW=dp(50,'Service sign width'), serviceSignH=dp(62,'Service sign height'), pictogramPlate=dp(40,'Service sign white square'),
  touristSign=dp(56,'Tourist sign square'), citySignW=dp(64,'City sign width'), citySignMinH=dp(40,'City sign min height'),
  hotelRowMinH=dp(60,'Hotel option min height'), suggestionRowMinH=dp(52,'Suggestion row min height'),
  sheetHandleW=dp(36,'Bottom-sheet handle width (new)'), sheetHandleH=dp(4,'Bottom-sheet handle height (new)'),
)
E = O(
  linear=[0,0,1,1], standard=[0.25,0.1,0.25,1], easeOut=[0,0,0.58,1], easeInOut=[0.42,0,0.58,1],
  postIn=[0.55,0,1,0.45], rushIn=[0.6,0,1,0.5], overshoot=[0.3,1.4,0.5,1], decelerate=[0.2,0.8,0.3,1], accelerate=[0.4,0,1,1],
)
easing = O((k, O(cubicBezier=v)) for k,v in E.items())
def m(**kw):
    d = O()
    for k,v in kw.items(): d[k]=v
    return d
motion = O()
motion['easing'] = easing
motion['lane'] = O(
  idle=m(durationMs=900, easing='linear', periodDp=160, dashDp=70, infinite=True),
  drive=m(durationMs=450, easing='linear', periodDp=160, dashDp=70, infinite=True),
  navi=m(durationMs=1400, easing='linear', periodDp=160, dashDp=70, infinite=True),
  exit=m(durationMs=1600, easing='linear', periodDp=160, dashDp=70, infinite=True),
  itinerary=m(durationMs=2200, easing='linear', periodDp=64, dashDp=32, infinite=True),
)
motion['post'] = O(
  idle=m(durationMs=2600, offsetMs=1300, easing='postIn', fromScale=0.3, toScale=2.2, dxDp=150, dyDp=260, fadeInFraction=0.10, infinite=True),
  drive=m(durationMs=1100, offsetMs=550, easing='rushIn', fromScale=0.2, toScale=2.4, dxDp=170, dyDp=230, fadeInFraction=0.10, infinite=True),
)
motion['flyingSign'] = m(durationMs=3600, staggerMs=1200, easing='rushIn', fromScale=0.12, toScale=1.7, dxDp=230, dyDp=40, fadeInFraction=0.15, infinite=True)
motion['startPulse'] = m(durationMs=1800, easing='easeOut', fromSpreadDp=0, toSpreadDp=16, toSpreadSmDp=14, fromAlpha=0.55, toAlpha=0, infinite=True)
motion['startPress'] = m(durationMs=120, easing='standard', toScale=0.96, infinite=False)
motion['mirrorSway'] = m(durationMs=4000, easing='easeInOut', fromDeg=-1.5, toDeg=1.5, infinite=True)
motion['dogWag'] = m(durationMs=1200, easing='easeInOut', fromDeg=-6, toDeg=6, infinite=True)
motion['selection'] = m(durationMs=200, easing='standard', infinite=False)
motion['needle'] = m(stiffness=300, dampingRatio=0.6, fromDeg=-90, toDeg=90, stepDeg=36, infinite=False)
motion['odometerRoll'] = m(durationMs=300, easing='decelerate', infinite=False)
motion['caret'] = m(durationMs=1000, onFraction=0.5, infinite=True)
motion['stepAppear'] = m(durationMs=350, minGapMs=400, easing='easeOut', fromDxDp=-6, infinite=False)
motion['progress'] = m(durationMs=400, easing='easeInOut', infinite=False)
motion['ctaAppear'] = m(durationMs=350, easing='easeOut', fromDxDp=-6, autoAdvanceMs=1000, infinite=False)
motion['stamp'] = m(durationMs=500, delayMs=1000, easing='overshoot', fromScale=2.4, midScale=0.92, toScale=1.0, midFraction=0.6, rotationDeg=-14, midAlpha=0.9, toAlpha=0.85, infinite=False)
motion['sheetSlide'] = m(durationMs=600, easing='decelerate', fromDyDp=40, infinite=False)
motion['exitNear'] = m(durationMs=2200, easing='decelerate', fromScale=0.7, fromDxDp=-21, fromDyDp=-14, fromAlpha=0.6, pivotX=0.3, pivotY=1.0, infinite=False)
motion['twinkle'] = m(durationMs=2400, staggerMs=800, easing='easeInOut', fromAlpha=0.3, toAlpha=1.0, infinite=True)
motion['turnSignal'] = m(durationMs=900, onMs=495, offAlpha=0.15, infinite=True)
motion['carMarker'] = m(durationMs=14000, easing='linear', speedDpPerS=124, infinite=True)
motion['shimmer'] = m(durationMs=1200, easing='linear', infinite=True)
motion['bottomSheetIn'] = m(durationMs=300, easing='decelerate', infinite=False)
motion['bottomSheetOut'] = m(durationMs=200, easing='accelerate', infinite=False)
motion['screen'] = O(
  zoomToNavi=m(durationMs=450, easing='decelerate', infinite=False),
  lookAtMirror=m(durationMs=400, easing='decelerate', infinite=False),
  launch=m(durationMs=300, easing='standard', laneRampMs=800, infinite=False),
  arrive=m(durationMs=450, easing='decelerate', infinite=False),
  overlay=m(durationMs=300, easing='standard', infinite=False),
  back=m(durationMs=300, easing='decelerate', infinite=False),
)
motion['frameBudgetMs'] = O(value=16, unit='ms', use='Per-frame budget at 60 fps (scene draw <= 4 ms)')

tokens = O()
tokens['$schema'] = 'verst-design-tokens/1'
tokens['$meta'] = O(name='Verst design v5 "За рулём"', version='1.0.0', date='2026-10-23',
  units='dp for sizes, sp for font sizes, em for letter-spacing, ms for durations',
  colorFormat='value = #RRGGBB (opaque); optional alpha 0..1 applied on top',
  naming='JSON path a.b.c == Kotlin DesignTokens.a.b.c (identical identifiers)',
  reference='390 x 844 dp safe area')
tokens['font'] = F
tokens['color'] = color
tokens['type'] = typ
tokens['space'] = space
tokens['radius'] = radius
tokens['stroke'] = stroke
tokens['shadow'] = shadow
tokens['size'] = size
tokens['motion'] = motion
json.dump(tokens, open('/home/claude/verst/design/tokens.json','w'), ensure_ascii=False, indent=2)

# ---------- Kotlin ----------
L = []
def w(s, ind): L.append('    '*ind + s)
def num(v):
    s = repr(float(v)) if not isinstance(v,int) else str(v)
    return s
def f(v): 
    s = ('%g' % v)
    if '.' not in s and 'e' not in s: s += '.0'
    return s + 'f'
def kcolor(d):
    hexv = d['value'][1:]
    base = 'Color(0xFF%s)' % hexv.upper()
    if 'alpha' in d: return '%s.copy(alpha = %s)' % (base, f(d['alpha']))
    return base
def kdp(v): 
    return ('%g' % v) + '.dp'
def ktype(d):
    fam = d['fontFamily'].split('.')[1]
    parts = ['fontFamily = DesignTokens.font.%s' % fam, 'fontWeight = FontWeight.W%d' % d['fontWeight'],
             'fontSize = %s.sp' % ('%g'%d['fontSizeSp']), 'lineHeight = %s.sp' % ('%g'%d['lineHeightSp']),
             'letterSpacing = %s.em' % ('%g'%d['letterSpacingEm'])]
    if d['fontFeatures']: parts.append('fontFeatureSettings = "%s"' % d['fontFeatures'])
    parts += ['platformStyle = NoFontPadding', 'lineHeightStyle = CenteredLineHeight']
    return 'TextStyle(\n' + ',\n'.join('            '+p for p in parts) + ',\n        )'

def emit_group(name, d, ind, kind):
    w('object %s {' % name, ind)
    for k,v in d.items():
        if kind=='color' and 'value' in v:
            w('/** %s */' % v['use'], ind+1); w('val %s: Color = %s' % (k, kcolor(v)), ind+1)
        elif kind=='type' and 'fontFamily' in v:
            w('/** %s */' % v['use'], ind+1)
            ts = ktype(v).replace('\n            ', '\n' + '    '*(ind+2)).replace('\n        )', '\n' + '    '*(ind+1) + ')')
            w('val %s: TextStyle = %s' % (k, ts), ind+1)
        elif kind=='dp' and 'value' in v:
            if v.get('use'): w('/** %s */' % v['use'], ind+1)
            w('val %s: Dp = %s' % (k, kdp(v['value'])), ind+1)
        elif kind=='shadow':
            w('/** %s */' % v['use'], ind+1)
            w('val %s = ShadowToken(x = %s, y = %s, blur = %s, spread = %s, color = %s, inset = %s)' % (k, kdp(v['xDp']), kdp(v['yDp']), kdp(v['blurDp']), kdp(v['spreadDp']), kcolor({'value':v['color'],'alpha':v['alpha']}) if v['alpha']!=1.0 else 'Color(0xFF%s)'%v['color'][1:], 'true' if v['inset'] else 'false'), ind+1)
        else:
            emit_group(k, v, ind+1, kind)
    w('}', ind)

def emit_motion(name, d, ind):
    w('object %s {' % name, ind)
    for k,v in d.items():
        if name=='easing':
            a=v['cubicBezier']; w('val %s: Easing = CubicBezierEasing(%s, %s, %s, %s)' % (k, f(a[0]),f(a[1]),f(a[2]),f(a[3])), ind+1); continue
        if k=='frameBudgetMs':
            w('const val frameBudgetMs: Int = %d' % v['value'], ind+1); continue
        leaf = any(not isinstance(x, dict) for x in v.values())
        if not leaf:
            emit_motion(k, v, ind+1); continue
        w('object %s {' % k, ind+1)
        for fk,fv in v.items():
            if fk=='easing': w('val easing: Easing = DesignTokens.motion.easing.%s' % fv, ind+2)
            elif fk=='infinite': w('const val infinite: Boolean = %s' % ('true' if fv else 'false'), ind+2)
            elif fk.endswith('Ms'): w('const val %s: Int = %d' % (fk, fv), ind+2)
            elif fk.endswith('Dp') or fk.endswith('DpPerS'): w('val %s: Dp = %s' % (fk, kdp(fv)) if fk.endswith('Dp') else 'const val %s: Float = %s' % (fk, f(fv)), ind+2)
            else: w('const val %s: Float = %s' % (fk, f(fv)), ind+2)
        w('}', ind+1)
    w('}', ind)

hdr = '''@file:Suppress("ClassName", "ObjectPropertyName", "MemberVisibilityCanBePrivate", "unused")

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

object DesignTokens {'''
L.append(hdr)
w('object font {', 1)
wmap={'400':'Normal','500':'Medium','600':'SemiBold','700':'Bold'}
for k,v in F.items():
    w('/** %s (%s), bundled in res/font */' % (v['family'], v['licence']), 2)
    w('val %s: FontFamily = FontFamily(' % k, 2)
    for wt,fn in v['files'].items():
        w('Font(R.font.%s, FontWeight.%s),' % (fn[:-4], wmap[wt]), 3)
    w(')', 2)
w('}', 1)
emit_group('color', color, 1, 'color')
emit_group('type', typ, 1, 'type')
emit_group('space', space, 1, 'dp')
emit_group('radius', radius, 1, 'dp')
emit_group('stroke', stroke, 1, 'dp')
emit_group('shadow', shadow, 1, 'shadow')
emit_group('size', size, 1, 'dp')
emit_motion('motion', motion, 1)
L.append('}')
open('/home/claude/verst/design/DesignTokens.kt','w').write('\n'.join(L)+'\n')
print('ok')
