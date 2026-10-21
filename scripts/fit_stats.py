import pandas as pd, numpy as np, sys
sys.path.insert(0,'.')
D=pd.read_csv('data/Matches.csv',low_memory=False); D['MatchDate']=pd.to_datetime(D['MatchDate'])
T={'E0':'premier','SP1':'laliga','I1':'seriea','D1':'bundesliga'}
D=D[D.Division.isin(T)].copy(); D['lg']=D.Division.map(T)
D['season']=np.where(D.MatchDate.dt.month>=7,D.MatchDate.dt.year,D.MatchDate.dt.year-1)
r=D[(D.season>=2018)&(D.season<=2025)].dropna(
  subset=['OddHome','OddDraw','OddAway','HomeCorners','HomeYellow','HomeShots','HomeTarget']).copy()
inv=1/r.OddHome+1/r.OddDraw+1/r.OddAway
r['pH']=(1/r.OddHome)/inv; r['pA']=(1/r.OddAway)/inv; r['sup']=(r.pH-r.pA).abs()
r['savH']=(r.AwayTarget-r.FTAway).clip(lower=0); r['savA']=(r.HomeTarget-r.FTHome).clip(lower=0)
cols={'cor':('HomeCorners','AwayCorners'),'yel':('HomeYellow','AwayYellow'),
      'sho':('HomeShots','AwayShots'),'sav':('savH','savA')}
print('=== EFECTO DEL DESEQUILIBRIO sobre cada estadistica (n=%d) ==='%len(r))
print('   coeficiente b en:  valor = media * (1 + b*(sup - 0.2847))')
fits={}
for s,(ch,ca) in cols.items():
    tot=r[ch]+r[ca]; m=tot.mean()
    b=np.polyfit(r.sup-0.2847, tot/m, 1)[0]
    # per-side check
    bh=np.polyfit(r.sup-0.2847, r[ch]/r[ch].mean(),1)[0]
    ba=np.polyfit(r.sup-0.2847, r[ca]/r[ca].mean(),1)[0]
    fits[s]=round(float(b),4)
    print(f'  {s}: total b={b:+.4f}   local b={bh:+.4f}  visita b={ba:+.4f}   (media partido {m:.2f})')
print()
print('MISMATCH =',fits)
print()
print('=== VARIANZA/MEDIA por lado (para la binomial negativa) ===')
dd={}
for s,(ch,ca) in cols.items():
    v=(r[ch].var()/r[ch].mean()+r[ca].var()/r[ca].mean())/2
    dd[s]=round(float(v),3); print(f'  {s}: {v:.3f}')
print('DISP =',dd)
print()
print('=== cuanto aporta el historial del equipo? (ratio temporada previa) ===')
for s,(ch,ca) in cols.items():
    hist={}
    pred_base=[];pred_team=[];act=[]
    for lg in T.values():
        g=r[r.lg==lg].sort_values('MatchDate')
        acc={}
        mH=g[ch].mean()
        for _,x in g.iterrows():
            a=acc.get(x.HomeTeam,[])
            if len(a)>=10:
                ratio=np.mean(a[-20:])/mH
                pred_base.append(mH); pred_team.append(mH*(1+0.5*(ratio-1))); act.append(x[ch])
            acc.setdefault(x.HomeTeam,[]).append(x[ch])
    pb,pt,ac=np.array(pred_base),np.array(pred_team),np.array(act)
    print(f'  {s}: MAE base {np.abs(ac-pb).mean():.3f} -> con equipo (shrink 0.5) {np.abs(ac-pt).mean():.3f}'
          f'   mejora {100*(1-np.abs(ac-pt).mean()/np.abs(ac-pb).mean()):+.1f}%')
