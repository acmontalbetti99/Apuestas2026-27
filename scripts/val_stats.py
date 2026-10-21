import pandas as pd, numpy as np, sys
sys.path.insert(0,'.')
import stats_engine as SE

D=pd.read_csv('data/Matches.csv',low_memory=False); D['MatchDate']=pd.to_datetime(D['MatchDate'])
T={'E0':'premier','SP1':'laliga','I1':'seriea','D1':'bundesliga'}
D=D[D.Division.isin(T)].copy(); D['lg']=D.Division.map(T)
D['season']=np.where(D.MatchDate.dt.month>=7,D.MatchDate.dt.year,D.MatchDate.dt.year-1)
r=D[(D.season>=2021)&(D.season<=2025)].dropna(
  subset=['OddHome','OddDraw','OddAway','HomeCorners','HomeYellow','HomeShots','HomeTarget']).copy()
inv=1/r.OddHome+1/r.OddDraw+1/r.OddAway
r['sup']=(1/r.OddHome)/inv-(1/r.OddAway)/inv
r['savH']=(r.AwayTarget-r.FTAway).clip(lower=0); r['savA']=(r.HomeTarget-r.FTHome).clip(lower=0)
r=r.sort_values('MatchDate').reset_index(drop=True)
COLS={'cor':('HomeCorners','AwayCorners'),'yel':('HomeYellow','AwayYellow'),
      'sho':('HomeShots','AwayShots'),'sav':('savH','savA')}

# rolling team ratios, strictly from the past
hist={}; ratios=[]
lgmean={ (lg,s,side): r[r.lg==lg][COLS[s][0 if side=='H' else 1]].mean()
         for lg in T.values() for s in COLS for side in 'HA' }
for i,x in r.iterrows():
    rr={'H':{},'A':{}}
    for s,(ch,ca) in COLS.items():
        for side,team,col in (('H',x.HomeTeam,ch),('A',x.AwayTeam,ca)):
            k=(x.lg,s,side,team); a=hist.get(k,[])
            rr[side][s]=(np.mean(a[-20:])/lgmean[(x.lg,s,side)]) if len(a)>=10 else 1.0
    ratios.append(rr)
    for s,(ch,ca) in COLS.items():
        hist.setdefault((x.lg,s,'H',x.HomeTeam),[]).append(x[ch])
        hist.setdefault((x.lg,s,'A',x.AwayTeam),[]).append(x[ca])

def settle(key,x):
    stat,scope,ou=key.split('_')[0],key.split('_')[1],key.split('_')[2]
    L=float(ou[1:]); over=ou[0]=='o'
    ch,ca=COLS[stat]
    v = x[ch]+x[ca] if scope=='m' else (x[ch] if scope=='h' else x[ca])
    return (v>L) if over else (v<L)

rows=[]
for i,x in r.iterrows():
    mk=SE.stat_markets(x.lg,x.sup,x.HomeTeam,x.AwayTeam,ratios[i]['H'],ratios[i]['A'])
    for k,(lab,p,fam,cat) in mk.items():
        rows.append({'lg':x.lg,'key':k,'stat':k.split('_')[0],'scope':k.split('_')[1],
                     'p':p,'ok':settle(k,x)})
S=pd.DataFrame(rows)
print(f'{len(r)} partidos, {len(S)} evaluaciones de mercado\n')
print('='*72); print('CALIBRACION GENERAL — corners, tarjetas, remates y atajadas'); print('='*72)
for lo in np.arange(0,1.0,0.1):
    s=S[(S.p>=lo)&(S.p<lo+0.1)]
    if len(s)<200: continue
    e=1.96*np.sqrt(s.ok.mean()*(1-s.ok.mean())/len(s))
    f='' if abs(s.ok.mean()-s.p.mean())<e else '  <-- fuera del IC95'
    print(f'  dice {100*lo:3.0f}-{100*lo+10:3.0f}%  n={len(s):6d}  predice {100*s.p.mean():5.1f}%  cae {100*s.ok.mean():5.1f}%  {100*(s.ok.mean()-s.p.mean()):+5.1f} pp{f}')
print()
print('='*72); print('CON EL FILTRO DE 65% (y tope 90%)'); print('='*72)
pk=S[(S.p>0.65)&(S.p<=0.90)]
se=np.sqrt(pk.ok.mean()*(1-pk.ok.mean())/len(pk))
print(f'  n={len(pk)}  predice {100*pk.p.mean():.1f}%  cae {100*pk.ok.mean():.1f}%  desvio {100*(pk.ok.mean()-pk.p.mean()):+.2f} pp (+/-{100*1.96*se:.2f})')
print()
NM={'cor':'Corners','yel':'Tarjetas','sho':'Remates','sav':'Atajadas'}
SC={'m':'partido','h':'equipo local','a':'equipo visitante'}
print('  por estadistica y alcance:')
for st in ['cor','yel','sho','sav']:
    for sc in ['m','h','a']:
        s=pk[(pk.stat==st)&(pk.scope==sc)]
        if len(s)<100: continue
        e=1.96*np.sqrt(s.ok.mean()*(1-s.ok.mean())/len(s))
        d=100*(s.ok.mean()-s.p.mean())
        flag='  OK' if abs(d)<100*e else '  <-- SESGADO'
        print(f'    {NM[st]:9s} {SC[sc]:17s} n={len(s):6d}  predice {100*s.p.mean():5.1f}%  cae {100*s.ok.mean():5.1f}%  {d:+5.1f} pp{flag}')
S.to_csv('val_stats.csv',index=False)
