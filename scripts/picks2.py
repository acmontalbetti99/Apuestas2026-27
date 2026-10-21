import json, sys, itertools, numpy as np, pandas as pd
sys.path.insert(0,'.')
from engine import markets, FAMILY
import stats_engine as SE

GOAL_LIQ = {'1':'1X2','2':'1X2','1X':'Doble oportunidad','12':'Doble oportunidad','X2':'Doble oportunidad',
            'O1.5':'Goles','O2.5':'Goles','U2.5':'Goles','U3.5':'Goles','BTTS':'Ambos marcan','NBTTS':'Ambos marcan'}
LGN={'premier':'Premier League','laliga':'La Liga','seriea':'Serie A','bundesliga':'Bundesliga','ucl':'Champions League'}
CEIL_GOAL, CEIL_STAT = 0.90, 0.88

# team ratios from the historical base (style is stable; the base runs to Sep 2026)
D=pd.read_csv('data/Matches.csv',low_memory=False); D['MatchDate']=pd.to_datetime(D['MatchDate'])
T={'E0':'premier','SP1':'laliga','I1':'seriea','D1':'bundesliga'}
D=D[D.Division.isin(T)].copy(); D['lg']=D.Division.map(T)
D=D.dropna(subset=['HomeCorners','HomeYellow','HomeShots','HomeTarget']).sort_values('MatchDate')
D['savH']=(D.AwayTarget-D.FTAway).clip(lower=0); D['savA']=(D.HomeTarget-D.FTHome).clip(lower=0)
COLS={'cor':('HomeCorners','AwayCorners'),'yel':('HomeYellow','AwayYellow'),'sho':('HomeShots','AwayShots'),'sav':('savH','savA')}
ALIAS={'Monchengladbach':"M'gladbach",'Colonia':'FC Koln','Hamburgo':'Hamburg','Elversberg':'Elversberg',
       'Dortmund':'Dortmund','Eintracht Frankfurt':'Ein Frankfurt','Manchester City':'Man City',
       'Manchester United':'Man United','Nottingham Forest':"Nott'm Forest",'Newcastle':'Newcastle',
       'Tottenham':'Tottenham','Atletico Madrid':'Ath Madrid','Athletic Bilbao':'Ath Bilbao',
       'Real Sociedad':'Sociedad','Celta de Vigo':'Celta','Rayo Vallecano':'Vallecano','Real Betis':'Betis',
       'Deportivo':'La Coruna','Malaga':'Malaga','Racing Santander':'Santander','Milan':'Milan',
       'Inter':'Inter','Bayern Munich':'Bayern Munich','RB Leipzig':'RB Leipzig','Leverkusen':'Leverkusen'}
lgmean={}
for lg in T.values():
    g=D[D.lg==lg]
    for s,(ch,ca) in COLS.items():
        lgmean[(lg,s,'H')]=g[ch].mean(); lgmean[(lg,s,'A')]=g[ca].mean()
def ratios(lg,team,side):
    if lg not in lgmean_lgs: return {}
    t=ALIAS.get(team,team); g=D[D.lg==lg]
    col='HomeTeam' if side=='H' else 'AwayTeam'
    sub=g[g[col]==t].tail(20)
    if len(sub)<8: return {}
    out={}
    for s,(ch,ca) in COLS.items():
        v=sub[ch if side=='H' else ca].mean()
        out[s]=float(v/lgmean[(lg,s,side)])
    return out
lgmean_lgs=set(T.values())

fx=json.load(open('fixtures.json'))+json.load(open('cl_fixtures.json'))
allsel=[]
for lg,ko,home,away,pH,pD,pA,mid in fx:
    pH,pD,pA=pH/100,pD/100,pA/100
    base={'lg':lg,'liga':LGN[lg],'ko':ko,'home':home,'away':away,'mid':mid}
    if lg=='ucl':
        # no historical Champions data in the base: only the market-derived markets
        for k,lab,p in (('1','Gana local',pH),('2','Gana visitante',pA),('1X','Local o empate',pH+pD),
                        ('12','Local o visitante (no empate)',pH+pA),('X2','Empate o visitante',pD+pA)):
            if 0.65<p<=CEIL_GOAL:
                allsel.append({**base,'key':k,'fam':'res','cat':'1X2' if k in '12' else 'Doble oportunidad',
                               'label':lab,'p':round(float(p),4),'cuota':round(1/float(p),2),'grupo':'resultado'})
        continue
    mk,lh,la=markets(lg,pH,pD,pA)
    for k,(lab,p) in mk.items():
        if k in GOAL_LIQ and 0.65<p<=CEIL_GOAL:
            allsel.append({**base,'key':k,'fam':FAMILY[k],'cat':GOAL_LIQ[k],'label':lab,
                           'p':round(float(p),4),'cuota':round(1/float(p),2),'xgH':round(lh,2),'xgA':round(la,2),
                           'grupo':'resultado' if FAMILY[k]=='res' else 'goles'})
    sm=SE.stat_markets(lg,pH-pA,home,away,ratios(lg,home,'H'),ratios(lg,away,'A'))
    for k,(lab,p,fam,cat) in sm.items():
        if 0.65<p<=CEIL_STAT:
            allsel.append({**base,'key':k,'fam':fam,'cat':cat,'label':lab,
                           'p':round(float(p),4),'cuota':round(1/float(p),2),'grupo':'estadisticas'})
allsel.sort(key=lambda s:-s['p'])

# at most one pick per match per group, and never two from the same family
best={}
for s in allsel:
    mk_=(s['home'],s['away'])
    key=(mk_,s['grupo'])
    if key in best: continue
    best[key]=s
singles=sorted(best.values(), key=lambda s:(s['ko'],-s['p']))
json.dump({'singles':singles,'all':allsel,'fixtures':fx}, open('picks2.json','w'), ensure_ascii=False)
from collections import Counter
print(f'{len(allsel)} selecciones sobre umbral · {len(singles)} picks finales')
print('por categoria:',dict(Counter(s['cat'] for s in singles)))
print('por liga:',dict(Counter(s['liga'] for s in singles)))
print()
print('=== CHAMPIONS LEAGUE ===')
for s in singles:
    if s['lg']=='ucl': print(f"  {s['p']*100:5.1f}%  cuota {s['cuota']:4.2f}  {s['home'][:18]:18s} v {s['away'][:18]:18s}  {s['label']}")
print()
print('=== MUESTRA DE MERCADOS NUEVOS ===')
n=0
for s in singles:
    if s['grupo']=='estadisticas' and n<14:
        print(f"  {s['p']*100:5.1f}%  cuota {s['cuota']:4.2f}  {s['liga'][:11]:11s} {s['home'][:15]:15s} v {s['away'][:15]:15s}  {s['label']}"); n+=1
