#!/usr/bin/env python3
"""DES-106: writes design/qa/<screen>.json (7 screens) from the redlines in design/screens/*.md and the
checklist §2–8. Coordinates are dp; road edges use the components §9.1 projection. theme.json is written by
`qa_sample.py --write-theme`. Run: python3 design/tools/gen_qa_points.py
"""
import json, math, os
QA=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'qa')
def road(top,H,P,deg,W,y_d):
    a=math.radians(deg); s=P/(P+y_d*math.sin(a)); y=top+(H-y_d*math.cos(a))*s; return y, W/2*s
def edge_pts(item, top,H,P,deg,W, ds, match, state='default', seed=195, size='390x844', edge=6, lane=8):
    """Asphalt run on each side of the lane: |x| between lane/2 and W/2 - edge, both scaled (components §9.1)."""
    out=[]
    for d in ds:
        a=math.radians(deg); s=P/(P+d*math.sin(a)); y=top+(H-d*math.cos(a))*s
        outer=(W/2-edge)*s; inner=lane/2*s
        mid=(outer+inner)/2
        out.append({'item':item,'state':state,'size':size,'kind':'edge','y':round(y,2),'seed':round(195-mid,2),'match':match,'match_tol':4,'expect':[round(195-outer,2),None],'tol_dp':1})
        out.append({'item':item,'state':state,'size':size,'kind':'edge','y':round(y,2),'seed':round(195+mid,2),'match':match,'match_tol':4,'expect':[None,round(195+outer,2)],'tol_dp':1})
    return out
def C(item,x,y,hexv,state='default',**k): d={'item':item,'state':state,'x':x,'y':y,'hex':hexv}; d.update(k); return d
def T(item,region,state='default',**k): d={'item':item,'state':state,'kind':'text','region':region}; d.update(k); return d
def PR(item,region,hexv,n,state='default',**k): d={'item':item,'state':state,'kind':'present','region':region,'hex':hexv,'min_px':n}; d.update(k); return d
def E(item,axis,fixed,seed,match,expect,state='default',size='390x844',tol=1): d={'item':item,'state':state,'size':size,'kind':'edge',axis:fixed,'seed':seed,'match':match,'expect':expect,'tol_dp':tol}; return d
ROADW=['#3A3A3F']
MOTION='motion: checked on the clock-sequence screenshots <state>-t<ms> (DES-11x step 5), not in a static frame'
SEM='semantics/touch: XScreenSemanticsTest (build/tests/failures.txt), not visual'
files={}
# ---------------- 5.1
p=[C('W-01',60,50,'#2B2850'),C('W-01',60,255,'#D9655A','no-routes'),C('W-01',60,284,'#F29A5E','no-routes'),
   C('W-02',130,292,'#3C3346','no-routes'),C('W-02',270,280,'#FFD99A','no-routes'),C('W-02',60,370,'#2C3A33')]
p+=edge_pts('W-03',300,240,210,76,230,[100,250],ROADW)
p+=[C('W-06',38,350,'#55565C'),C('W-06',352,350,'#55565C'),C('W-07',195,4,'#0E0E10'),C('W-07',5,450,'#0E0E10'),
    C('W-08',121.5,40,'#2A2A2E'),C('W-08',195,12,'#2A2A2E'),C('W-08',205,26,'#4E3768'),C('W-08',176,55,'#2C3A33'),T('W-08',[148,65,94,14]),
    C('W-10',22,150,'#1E4FA3'),C('W-10',25,150,'#F4F4F0'),C('W-10',29,105,'#1E4FA3'),T('W-11',[38,96,170,14]),T('W-12',[70,124,150,22]),
    C('W-13',200,116,'#163B7A'),C('W-13',200,160,'#1E4FA3'),C('W-13',200,116,'#1E4FA3','row2-selected'),C('W-13',200,160,'#163B7A','row2-selected'),
    T('W-14',[38,290,200,14]),C('W-16',100,830,'#161618'),C('W-16',195,519,'#232327'),C('W-17',21,600,'#232327'),C('W-17',30,665,'#0B1218'),
    C('W-19',300,592,'#16222C'),T('W-20',[22,727,150,24]),C('W-21',282,742,'#232327'),C('W-21',298,735,'#1C1C1F'),C('W-21',324,705.5,'#D8402B'),
    C('W-22',324,705.5,'#55555E','loading'),C('W-24',324,705.5,'#55555E','offline-empty'),T('W-23',[36,558,200,14],'offline-cached'),
    T('W-24',[32,96,320,60],'offline-empty'),C('W-25',37,610,'#FFD23F','no-routes'),T('W-26',[32,96,320,60],'error'),
    T('W-27',[22,753,140,44],'trips-plate'),E('W-30','x',250,240,['#1E4FA3','#163B7A','#F4F4F0'],[None,256],'default','360x640'),
    C('W-22',324,705.5,'#55555E','engine-starting'),T('W-26',[32,96,320,90],'engine-failed')]
files['5.1-windshield']=(p,{'W-04':MOTION,'W-05':MOTION,'W-09':'silhouette slots use the glass colour #0D0D0F; checked by reading the default and crew-variant screenshots (DES-11x step 4)',
 'W-15':'arrow direction = data mapping; checked by reading (step 4) and the bearing unit test','W-18':SEM,'W-28':'not in the mock build (open-issues D-16: location is not requested)',
 'W-29':'sheet content height is data-driven; checked by the overlay against the canvas (step 3)','W-31':SEM},
 'Road edges are measured on the asphalt runs left and right of the lane (|x| from lane/2 to W/2 − edge, scaled by the projection). Bands 2–5 are hidden behind the sign and the A-pillars in the default state; bands 4–5 are sampled on no-routes, where the sign is shorter; bands 2–3 stay inside the sign shadow (0 8 18 black 35 %) in every state and are checked by the overlay (step 3). Thin (≤ 1 dp) borders are not sampled (< 2 px inside).')
# ---------------- 5.2
p=[C('N-01',60,20,'#2B2850'),C('N-01',60,60,'#8E4A6B'),C('N-01',60,85,'#D9655A'),C('N-01',60,99,'#F29A5E'),C('N-01',40,120,'#2C3A33')]
p+=edge_pts('N-01',104,46,120,80,160,[100],ROADW,'default-query-yaro',edge=4,lane=6)
p+=[C('N-02',195,131,'#232327'),C('N-02',300,165,'#161618'),T('N-03',[34,150,70,26]),C('N-04',17.5,400,'#232327'),C('N-04',24,400,'#0B1218'),T('N-05',[33,207,150,14]),
    C('N-06',250,236,'#16222C'),C('N-06',47.5,256,'#7FA6D9'),C('N-07',34,319,'#FFD23F'),C('N-07',300,296,'#16222C'),C('N-07',53,319,'#FFD23F'),
    C('N-08',300,362,'#1A2C3B'),C('N-08',300,414,'#0F1A22'),C('N-08',49,383,'#1E4FA3'),C('N-08',49,539,'#6B3E26'),T('N-10',[40,562,140,22]),
    C('N-11',40,453,'#16222C','popular-chips'),T('N-11',[33,411,200,14],'popular-chips'),T('N-12',[22,762,200,23]),C('N-12',288,775,'#232327'),C('N-12',305,768,'#1C1C1F'),C('N-12',327,741.5,'#D8402B'),
    C('N-14',327,741.5,'#55555E','no-destination'),T('N-14',[22,762,200,23],'no-destination'),T('N-15',[22,785,240,17],'too-short'),T('N-15',[22,785,240,17],'unreachable'),
    C('N-16',351,362,'#0F1A22','no-results'),T('N-16',[45,365,280,40],'no-results'),T('N-16',[45,365,280,40],'outside-russia'),
    C('N-18',22,680,'#232327','map-unavailable-plate'),T('N-18',[34,640,320,40],'map-unavailable-plate'),T('N-17',[33,231,324,220],'vias-3')]
for q in p: q.setdefault('state','default-query-yaro')
for q in p:
    if q['state']=='default': q['state']='default-query-yaro'
files['5.2-navigator']=(p,{'N-09':'debounce / ≤ 6 rows: NavigatorViewModelTest.debounceCancelsStale + reading','N-13':'IME behaviour: not rendered by Robolectric; emulator journey (DES-117)','N-19':SEM},
 'GPS indicator is hidden in the mock build (D-16): N-05 checks only the header text. Dashed borders (1 dp) are not sampled.')
# ---------------- 5.3
p=[C('I-01',250,30,'#2B2850'),C('I-01',195,309,'#161618'),T('I-02',[16,10,106,32]),
   C('I-03',22.5,140,'#2A2A2E'),C('I-03',195,30,'#2A2A2E'),C('I-04',50,200,'#3A3A42'),C('I-05',89.7,156,'#E9E2F2'),C('I-05',195,165,'#FFD23F'),C('I-05',300,175,'#2A2A30'),
   C('I-06',311,112,'#C99A5B'),C('I-07',207,248,'#F4F4F0'),T('I-08',[20,276,250,26]),C('I-09',16,400,'#232327'),C('I-09',25,400,'#0F0F11'),
   C('I-10',47,375,'#000000'),C('I-10',132.5,361.5,'#F4F4F0'),C('I-10',50.5,361.5,'#1C1C1F'),T('I-11',[46,404,111,32]),C('I-12',52,452,'#2A2A2E'),C('I-12',60,486.9,'#0E0E10'),
   C('I-12',60,486.9,'#2A2A2E','km-150'),C('I-13',288.5,357,'#2A2A2E'),C('I-13',238.7,391.9,'#D8402B'),C('I-13',288.5,412,'#F4F4F0'),C('I-13',281.1,387.2,'#FFD23F'),
   T('I-14',[223.5,385,130,15]),C('I-15',26,573,'#F4F4F0'),C('I-15',25,681,'#2A2A2E'),C('I-16',274,770,'#232327'),C('I-16',320,730.5,'#D8402B'),C('I-16',298,762,'#1C1C1F'),
   C('I-05',300,175,'#2A2A30','crew-full',),T('I-17',[20,54,350,260],'third-row'),T('I-18',[20,400,350,400],'settings-sheet'),C('I-13',288.5,357,'#2A2A2E','budget-any')]
p[-4]={'item':'I-05','state':'crew-full','kind':'absent','region':[255,150,90,40],'hex':'#2A2A30'}
files['5.3-instruments']=(p,{'I-19':'persistence: DataStoreDefaults test (restart)','I-20':SEM},
 'The sky bands under the mirror are always in the mirror shadow (0 10 24 black 45 %), so only band 1 and the surface below the shadow are sampled. Gauge sample points derived from the arc centre (288.5, 410) and radius 53 (components §6). In crew-full the right seat is filled, so the bench colour must be absent inside it.')
# ---------------- 5.4
p=[C('D-01',60,60,'#2B2850','t1500'),C('D-01',60,150,'#4E3768','t1500'),C('D-01',60,215,'#8E4A6B','t1500'),C('D-01',60,258,'#D9655A','t1500'),C('D-01',60,288,'#F29A5E','t1500'),C('D-01',195,285,'#FFD99A','t1500')]
p+=edge_pts('D-02',300,260,210,76,240,[100,250],ROADW,'t1500')
p+=[C('D-05',195,539,'#232327','t1500'),C('D-05',21,650,'#232327','t1500'),C('D-05',30,735,'#0B1218','t1500'),T('D-06',[38,580,150,14],'t1500'),
    C('D-07',345,604,'#1E2E3A','t1500'),C('D-07',45,604,'#FFD23F','t1500'),T('D-08',[56,616,200,42],'t1500'),C('D-09',26,770,'#FFD23F','done'),T('D-09',[36,778,250,22],'done'),
    C('D-10',26,789,'#232327','slow'),C('D-10',205,789,'#FFD23F','slow'),T('D-10',[56,616,250,90],'slow'),T('D-11',[38,580,150,14],'error-internal'),C('D-11',26,789,'#FFD23F','error-internal'),
    T('D-11',[38,600,300,60],'error-unreachable'),T('D-11',[38,600,300,60],'error-too-short'),T('D-11',[38,600,300,60],'error-invalid'),T('D-12',[38,580,150,14],'offline'),C('D-12',26,789,'#FFD23F','offline'),
    T('D-08',[56,616,250,90],'no-lodging'),T('B1',[16,18,90,32],'t1500')]
p[-1]['item']='D-13'
files['5.4-drive']=(p,{'D-03':MOTION,'D-04':MOTION+' (flying signs at t1500 / t4000)','D-13':'cancellation: network/engine log in the instrumented journey; the back link text is sampled','D-14':SEM},
 'Road edges are measured on the asphalt run each side of the lane (|x| from lane/2 to W/2 − edge, scaled), so the filtered white lines never decide the result. Flying signs and posts move: no colour point is placed on their paths at t1500. D-13 point checks the «Отменить» back link is drawn.')
# ---------------- 5.5
p=[C('R-01',200,25,'#2B2850','g02-top'),C('R-01',2,70,'#8E4A6B','g02-top'),C('R-01',2,97,'#D9655A','g02-top'),C('R-01',2,118,'#F29A5E','g02-top'),C('R-01',195,140,'#161618','g02-top'),
   PR('R-02',[290,12,88,44],'#E9E2F2',20,'g02-top'),C('R-03',21.5,80,'#1E4FA3','g02-top'),C('R-03',24,80,'#F4F4F0','g02-top'),T('R-03',[35,62,200,30],'g02-top'),
   C('R-04',25,197,'#2A2A2E','g02-top'),T('R-04',[20,150,250,29],'g02-top'),C('R-05',22,600,'#3A3A3F','g02-top'),C('R-05',15.5,600,'#F4F4F0','g02-top'),
   E('R-05','y',600,22,['#3A3A3F','#F4F4F0','#FFD23F','#141416'],[14,60],'g02-top'),PR('R-06',[39,268,14,480],'#FFD23F',100,'g02-top'),
   T('R-07',[72,268.4,47,19.5],'g02-top'),C('R-08',67,337.4,'#55565C','g02-top'),C('R-09',73,320,'#F4F4F0','g02-top'),C('R-09',75.5,320,'#141416','g02-top'),C('R-09',79.5,311,'#F4F4F0','g02-top'),
   PR('R-10',[78,380,56,370],'#6B3E26',600,'g02-top'),PR('R-11',[81,380,50,370],'#1E4FA3',400,'g02-top'),PR('R-12',[144,380,200,370],'#FFD23F',20,'g02-top'),
   PR('R-13',[249,300,125,450],'#1E4FA3',200,'g02-day2'),C('R-14',22,788,'#F4F4F0','g02-top'),C('R-14',195,834,'#161618','g02-top'),T('R-14',[34,766,190,44],'g02-top'),
   PR('R-16',[20,255,350,70],'#FFD23F',100,'no-lodging-over-budget'),PR('R-16',[34,766,250,15],'#B3261E',20,'no-lodging-over-budget'),PR('R-16',[20,255,350,60],'#E6604A',10,'offline'),
   T('R-15',[0,300,390,544],'stop-menu'),T('R-15',[0,300,390,544],'replace-sheet'),T('R-15',[0,300,390,544],'report-sheet'),T('R-16',[18,600,354,140],'saved-toast'),T('R-16',[18,600,354,140],'limit-45'),
   PR('R-13',[249,300,125,450],'#1E4FA3',200,'booked-row'),T('R-15',[0,300,390,544],'replace-none-note')]
files['5.5-road-ahead']=(p,{'R-17':'frame timing: Macrobenchmark / JankStats on the emulator (DEV-130)','R-18':SEM},
 'Row positions depend on text wrapping (5.5 §2.3 formula), so itinerary signs are checked with `present` regions over the sign column; R-08 exact geometry is the connector of row 1 (fixed position). g02-day2 is scrolled to the day 2 hotel row for R-13.')
# ---------------- 5.6
inkst=composite=None
def comp(f,a,b):
    f=[int(f[i:i+2],16) for i in (1,3,5)]; b=[int(b[i:i+2],16) for i in (1,3,5)]
    return '#%02X%02X%02X'%tuple(round(f[i]*a+b[i]*(1-a)) for i in range(3))
p=[T('P-01',[14,14,108,32],'reference'),C('P-02',20,200,'#EEF2F4','reference'),C('P-03',140,60,'#8C8C93','reference'),C('P-03',195,78,'#5D5D63','reference'),
   C('P-04',195,147.9,'#22313D','reference'),T('P-05',[122,156.9,200,22.8],'reference'),C('P-06',30.75,400,'#22313D','reference'),T('P-06',[37,244.8,150,20],'reference'),
   PR('P-07',[289,266.6,70,220],'#1B3FA0',30,'reference'),T('P-08',[289,486.6,70,44],'reserve-off'),T('P-09',[31,266.6,327,120],'line-expanded'),
   PR('P-10',[200,582,160,40],'#B3261E',20,'over-budget'),T('P-10',[200,582,160,40],'no-budget'),C('P-11',317,606.8,comp('#5B3FA0',.85,'#EEF2F4'),'stamp-final',tol=1),
   PR('P-13',[20,720,350,34],'#FFD23F',20,'reference'),C('P-14',24,796,'#232327','reference'),C('P-14',210,796,'#FFD23F','reference'),C('P-14',195,834,'#161618','reference'),
   T('P-13',[0,300,390,544],'pro-sheet'),T('P-13',[0,300,390,544],'pro-joined'),PR('P-15',[289,266.6,70,280],'#1B3FA0',30,'g02')]
files['5.6-waybill']=(p,{'P-12':MOTION,'P-16':SEM,'P-15':'exact figures are read against the fixture (step 4); the ink presence in the ₽ column is sampled'},
 'P-11 samples the stamp ring at its top (centre 317, 652.3; radius 45.5) drawn at alpha 0.85 over the paper: expected composite, ±1.')
# ---------------- 5.7
p=[C('E-01',200,20,'#121130'),C('E-01',40,180,'#2B2850'),C('E-01',40,225,'#4E3768'),C('E-01',75,66,'#F2E3B3'),C('E-01',40,300,'#1A231F')]
p+=edge_pts('E-02',240,190,200,76,230,[250,400],['#2E2E33'])
p+=[C('E-03',180,330,comp('#FFECAA',.10,'#2E2E33'),tol=1),C('E-04',164,150,'#1E4FA3'),C('E-04',167,150,'#F4F4F0'),C('E-04',180,156,'#F4F4F0'),C('E-04',317,250,'#55565C'),
    C('E-05',195,409,'#232327'),T('E-05',[34,424,94,32]),C('E-06',17,600,'#232327'),C('E-06',26,590,'#0B1218'),T('E-06',[32,504,200,24]),
    C('E-07',40,603,'#16222C'),C('E-07',40,672,'#0B1218'),C('E-07',46,698,'#5A7893'),C('E-07',54,629.7,'#FFD23F'),C('E-07',54,624.7,'#0B1218'),C('E-08',22,790,'#FFD23F'),
    C('E-08',22,790,'#232327','offline'),T('E-08',[32,772,200,36],'offline'),T('E-07',[32,598,326,210],'three-options'),T('E-08',[32,598,326,140],'no-lodging'),
    T('E-09',[0,300,390,544],'mock-partner-sheet'),T('E-09',[24,300,342,300],'booked-dialog'),PR('E-09',[32,598,326,62],'#FFD23F',20,'booked')]
files['5.7-exit']=(p,{'E-10':SEM},
 'E-02 edges are scanned at y 298.5 and 271.7, above the headlight polygon (it starts at y 300), so anti-aliased headlight edges do not break the asphalt run. Turn-signal blink (E-05) is motion: only the back link is sampled.')
for name,(pts,just,notes) in files.items():
    for q in pts: q.setdefault('state','default'); q.setdefault('size','390x844')
    json.dump({'screen':name,'notes':notes,'points':pts,'justified':just},open(os.path.join(QA,name+'.json'),'w'),ensure_ascii=False,indent=1)
    print(name,len(pts),'points')
