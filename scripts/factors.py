import pandas as pd, numpy as np
pd.set_option('display.width', 200)
D = pd.read_csv('data/Matches.csv', low_memory=False)
D['MatchDate'] = pd.to_datetime(D['MatchDate'])
TGT = {'E0':'Premier','SP1':'LaLiga','I1':'SerieA','D1':'Bundesliga'}
f = D[D.Division.isin(TGT)].copy()
f['lg'] = f.Division.map(TGT)
f['season'] = np.where(f.MatchDate.dt.month>=7, f.MatchDate.dt.year, f.MatchDate.dt.year-1)
f = f[f.season>=2010].copy()
f['g'] = f.FTHome + f.FTAway
f['cards'] = f.HomeYellow + f.AwayYellow
f['reds'] = f.HomeRed + f.AwayRed
f['corners'] = f.HomeCorners + f.AwayCorners
f['fouls'] = f.HomeFouls + f.AwayFouls
f['sot'] = f.HomeTarget + f.AwayTarget
f['shots'] = f.HomeShots + f.AwayShots

H = lambda t: print('\n' + '='*78 + '\n' + t + '\n' + '='*78)

# ---------- 1. HOME ADVANTAGE ----------
H('1. VENTAJA DE LOCAL — por liga y por temporada')
f['res'] = f.FTResult
ha = f.pivot_table(index='season', columns='lg', values='res', aggfunc=lambda s: 100*(s=='H').mean())
print('% de victorias locales')
print(ha.round(1).to_string())
print('\nventaja de local en goles (GF local - GF visita), promedio por partido')
f['gd'] = f.FTHome - f.FTAway
print(f.pivot_table(index='season', columns='lg', values='gd', aggfunc='mean').round(3).to_string())
print('\nagregado por era:')
for lo,hi,lab in [(2010,2018,'2010-18 (pre-COVID)'),(2019,2020,'2019-20 (COVID/sin público)'),(2021,2025,'2021-25 (post)')]:
    s = f[(f.season>=lo)&(f.season<=hi)]
    row = s.groupby('lg').apply(lambda x: pd.Series({
        '%local': 100*(x.res=='H').mean(), '%empate': 100*(x.res=='D').mean(),
        '%visita': 100*(x.res=='A').mean(), 'dif.goles': (x.FTHome-x.FTAway).mean(),
        'amar.local': x.HomeYellow.mean(), 'amar.visita': x.AwayYellow.mean()}), include_groups=False)
    print(f'\n{lab}  (n={len(s)})'); print(row.round(2).to_string())

# ---------- 2. LÍNEAS BASE ----------
H('2. LÍNEAS BASE por liga (2021-2025, post-COVID)')
r = f[(f.season>=2021)&(f.season<=2025)]
base = r.groupby('lg').agg(n=('g','size'), goles=('g','mean'), **{
 'más2.5':('g', lambda s: 100*(s>2.5).mean())}, amarillas=('cards','mean'), rojas=('reds','mean'),
 corners=('corners','mean'), faltas=('fouls','mean'), remates=('shots','mean'), aPuerta=('sot','mean'))
base['ambosMarcan'] = r.groupby('lg').apply(lambda x: 100*((x.FTHome>0)&(x.FTAway>0)).mean(), include_groups=False)
print(base.round(2).to_string())
print('\ndispersión: varianza/media (1.0 = Poisson puro, >1 = sobredispersión -> usar binomial negativa)')
vm = r.groupby('lg').agg(**{c:(c, lambda s: s.var()/s.mean()) for c in ['g','cards','corners','fouls','sot','shots']})
print(vm.round(2).to_string())

# ---------- 3. EL MERCADO COMO BENCHMARK ----------
H('3. EL MERCADO: qué tan bueno es (benchmark a batir)')
m = r.dropna(subset=['OddHome','OddDraw','OddAway']).copy()
inv = 1/m.OddHome + 1/m.OddDraw + 1/m.OddAway
m['pH']=(1/m.OddHome)/inv; m['pD']=(1/m.OddDraw)/inv; m['pA']=(1/m.OddAway)/inv
m['vig'] = 100*(inv-1)
act = m.res.map({'H':'pH','D':'pD','A':'pA'})
m['pAct'] = [m.loc[i,c] for i,c in act.items()]
ll = -np.log(m.pAct).mean()
br = ((m.pH-(m.res=='H'))**2+(m.pD-(m.res=='D'))**2+(m.pA-(m.res=='A'))**2).mean()
pick = m[['pH','pD','pA']].idxmax(axis=1).map({'pH':'H','pD':'D','pA':'A'})
print(f'n={len(m)}   margen medio de la casa (vig) = {m.vig.mean():.2f}%')
print(f'log loss (Bet365 cierre, sin vig) = {ll:.4f}')
print(f'Brier                              = {br:.4f}')
print(f'acierto 1X2 del favorito           = {100*(pick==m.res).mean():.1f}%')
print(f'siempre local                      = {100*(m.res=="H").mean():.1f}%')
print('\ncalibración del mercado por banda de probabilidad:')
for lo in np.arange(0,1.0,0.1):
    sel = (m.pH>=lo)&(m.pH<lo+0.1)
    if sel.sum()>80:
        print(f'  mercado dice {100*lo:3.0f}-{100*lo+10:3.0f}%  n={sel.sum():5d}  dice {100*m.pH[sel].mean():5.1f}%  cae {100*(m.res[sel]=="H").mean():5.1f}%')
print('\nsesgo favorito-perdedor (favourite-longshot): rendimiento de apostar a ciegas por banda de cuota')
allo = pd.concat([
 pd.DataFrame({'o':m.OddHome,'w':(m.res=='H')}), pd.DataFrame({'o':m.OddDraw,'w':(m.res=='D')}),
 pd.DataFrame({'o':m.OddAway,'w':(m.res=='A')})])
allo['band']=pd.cut(allo.o,[1,1.5,2,2.5,3.5,5,8,15,1000])
print(allo.groupby('band',observed=True).apply(lambda x: pd.Series({
 'n':len(x),'cuota media':x.o.mean(),'% gana':100*x.w.mean(),
 'ROI %':100*((x.w*x.o).mean()-1)}), include_groups=False).round(2).to_string())

# ---------- 4. ELO ----------
H('4. ELO solo: cuánta señal trae')
e = r.dropna(subset=['HomeElo','AwayElo']).copy()
e['d'] = e.HomeElo - e.AwayElo
e['band'] = pd.cut(e.d, [-2000,-200,-100,-50,0,50,100,200,2000])
print(e.groupby('band',observed=True).apply(lambda x: pd.Series({
 'n':len(x),'%local':100*(x.res=='H').mean(),'%empate':100*(x.res=='D').mean(),
 '%visita':100*(x.res=='A').mean(),'dif.goles':(x.FTHome-x.FTAway).mean()}), include_groups=False).round(1).to_string())
print(f'\ncorrelación Elo-dif vs diferencia de goles: {e.d.corr(e.FTHome-e.FTAway):.3f}')
print(f'correlación Elo-dif vs prob. implícita del mercado: {e.d.corr((1/e.OddHome)/(1/e.OddHome+1/e.OddDraw+1/e.OddAway)):.3f}')

# ---------- 5. DESCANSO ----------
H('5. DÍAS DE DESCANSO (congestión de calendario)')
lastm = {}
rows=[]
for _, x in f.sort_values('MatchDate').iterrows():
    for side,team in [('H',x.HomeTeam),('A',x.AwayTeam)]:
        prev = lastm.get((x.Division,team))
        rows.append({'i':_, 'side':side, 'rest':(x.MatchDate-prev).days if prev else np.nan})
    lastm[(x.Division,x.HomeTeam)] = x.MatchDate; lastm[(x.Division,x.AwayTeam)] = x.MatchDate
R = pd.DataFrame(rows)
rest = R.pivot_table(index='i',columns='side',values='rest')
g = f.join(rest.rename(columns={'H':'restH','A':'restA'}))
g = g[(g.season>=2015)&g.restH.notna()&g.restA.notna()&(g.restH<30)&(g.restA<30)]
g['adv'] = g.restH - g.restA
g['ab'] = pd.cut(g.adv, [-30,-4,-2,-1,1,2,4,30], labels=['local -4+','local -3/-4','local -2','igual','local +2','local +3/+4','local +4+'])
print('ventaja de descanso del local (días) vs resultado:')
print(g.groupby('ab',observed=True).apply(lambda x: pd.Series({
 'n':len(x),'%local':100*(x.res=='H').mean(),'dif.goles':(x.FTHome-x.FTAway).mean(),
 'pts/partido local':(3*(x.res=='H')+(x.res=='D')).mean()}), include_groups=False).round(2).to_string())
print('\nrendimiento del equipo con <=3 días de descanso vs >=6:')
for lab,sel in [('local con <=3 días', g.restH<=3), ('local con >=6 días', g.restH>=6)]:
    x=g[sel]; print(f'  {lab:22s} n={len(x):5d}  %local {100*(x.res=="H").mean():.1f}%  goles a favor {x.FTHome.mean():.2f}')

# ---------- 6. RECIÉN ASCENDIDOS ----------
H('6. RECIÉN ASCENDIDOS')
f2 = f.copy()
seen = {}
first=[]
for _, x in f2.sort_values('MatchDate').iterrows():
    for t in (x.HomeTeam, x.AwayTeam):
        seen.setdefault((x.Division,t), x.season)
for lg in TGT.values():
    s = f2[(f2.lg==lg)&(f2.season>=2012)&(f2.season<=2025)]
    newteams = []
    for season in sorted(s.season.unique())[1:]:
        prev = set(s[s.season==season-1].HomeTeam); cur = set(s[s.season==season].HomeTeam)
        newteams += [(season,t) for t in cur-prev]
    idx = s.apply(lambda x: (x.season,x.HomeTeam) in newteams, axis=1)
    ida = s.apply(lambda x: (x.season,x.AwayTeam) in newteams, axis=1)
    ptsN = pd.concat([ (3*(s[idx].res=='H')+(s[idx].res=='D')), (3*(s[ida].res=='A')+(s[ida].res=='D')) ]).mean()
    ptsO = pd.concat([ (3*(s[~idx].res=='H')+(s[~idx].res=='D')), (3*(s[~ida].res=='A')+(s[~ida].res=='D')) ]).mean()
    gfN = pd.concat([s[idx].FTHome, s[ida].FTAway]).mean(); gaN = pd.concat([s[idx].FTAway, s[ida].FTHome]).mean()
    print(f'  {lg:11s} ascendidos: {ptsN:.2f} pts/partido, {gfN:.2f} GF, {gaN:.2f} GC   |  resto: {ptsO:.2f} pts/partido   (déficit {100*(1-ptsN/ptsO):.0f}%)')

# ---------- 7. CORRELACIÓN ENTRE MERCADOS ----------
H('7. CORRELACIÓN ENTRE MERCADOS (clave para parlays)')
cc = r[['g','cards','corners','fouls','sot','shots','reds']].corr()
print(cc.round(3).to_string())
print('\ncondicionales que rompen la independencia:')
print(f"  córners promedio | partido con más de 2.5 goles : {r[r.g>2.5].corners.mean():.2f}")
print(f"  córners promedio | partido con menos de 2.5     : {r[r.g<2.5].corners.mean():.2f}")
print(f"  amarillas promedio | hubo roja                  : {r[r.reds>0].cards.mean():.2f}")
print(f"  amarillas promedio | sin roja                   : {r[r.reds==0].cards.mean():.2f}")
print(f"  amarillas | partido cerrado (dif<=1)            : {r[(r.FTHome-r.FTAway).abs()<=1].cards.mean():.2f}")
print(f"  amarillas | goleada (dif>=3)                    : {r[(r.FTHome-r.FTAway).abs()>=3].cards.mean():.2f}")
print(f"  faltas | partido cerrado                        : {r[(r.FTHome-r.FTAway).abs()<=1].fouls.mean():.2f}")
print(f"  faltas | goleada                                : {r[(r.FTHome-r.FTAway).abs()>=3].fouls.mean():.2f}")
