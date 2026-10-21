"""Does the >65% filter actually land 65%+? Settle every market the engine
would have recommended, on 7,229 real matches (2021-2025)."""
import pandas as pd, numpy as np, sys
sys.path.insert(0, '.')
from engine import markets, FAMILY

D = pd.read_csv('data/Matches.csv', low_memory=False)
D['MatchDate'] = pd.to_datetime(D['MatchDate'])
T = {'E0':'premier','SP1':'laliga','I1':'seriea','D1':'bundesliga'}
D = D[D.Division.isin(T)].copy(); D['lg'] = D.Division.map(T)
D['season'] = np.where(D.MatchDate.dt.month>=7, D.MatchDate.dt.year, D.MatchDate.dt.year-1)
r = D[(D.season>=2021)&(D.season<=2025)].dropna(
      subset=['OddHome','OddDraw','OddAway','FTHome','FTAway']).copy()
inv = 1/r.OddHome + 1/r.OddDraw + 1/r.OddAway
r['pH'] = (1/r.OddHome)/inv; r['pD'] = (1/r.OddDraw)/inv; r['pA'] = (1/r.OddAway)/inv
print(f'settling {len(r)} matches\n')

def settle(key, h, a):
    t = h + a
    if key == '1':  return h > a
    if key == 'X':  return h == a
    if key == '2':  return a > h
    if key == '1X': return h >= a
    if key == '12': return h != a
    if key == 'X2': return a >= h
    if key == 'BTTS':  return h > 0 and a > 0
    if key == 'NBTTS': return h == 0 or a == 0
    if key == 'CS_H':  return a == 0
    if key == 'CS_A':  return h == 0
    if key[0] == 'O':  return t > float(key[1:])
    if key[0] == 'U':  return t < float(key[1:])
    if key[:2] == 'HO': return h > float(key[2:])
    if key[:2] == 'HU': return h < float(key[2:])
    if key[:2] == 'AO': return a > float(key[2:])
    if key[:2] == 'AU': return a < float(key[2:])
    raise ValueError(key)

rows = []
for _, x in r.iterrows():
    mk, lh, la = markets(x.lg, x.pH, x.pD, x.pA)
    for k, (lab, p) in mk.items():
        rows.append({'lg':x.lg, 'key':k, 'fam':FAMILY[k], 'p':p,
                     'ok':settle(k, x.FTHome, x.FTAway)})
S = pd.DataFrame(rows)
print(f'{len(S)} market evaluations\n')

print('='*74)
print('CALIBRACION GENERAL (todos los mercados, todas las probabilidades)')
print('='*74)
for lo in np.arange(0, 1.0, 0.1):
    s = S[(S.p>=lo)&(S.p<lo+0.1)]
    if len(s) < 150: continue
    err = 1.96*np.sqrt(s.ok.mean()*(1-s.ok.mean())/len(s))
    flag = '' if abs(s.ok.mean()-s.p.mean()) < err else '  <-- fuera del IC 95%'
    print(f'  dice {100*lo:3.0f}-{100*lo+10:3.0f}%   n={len(s):6d}   predice {100*s.p.mean():5.1f}%   cae {100*s.ok.mean():5.1f}%   {100*(s.ok.mean()-s.p.mean()):+5.1f} pp{flag}')

print()
print('='*74)
print('EL FILTRO QUE PEDISTE: picks con probabilidad > 65%')
print('='*74)
pick = S[S.p > 0.65]
print(f'  selecciones: {len(pick)}  ({len(pick)/len(r):.1f} por partido)')
print(f'  probabilidad media predicha: {100*pick.p.mean():.1f}%')
print(f'  tasa real de acierto:        {100*pick.ok.mean():.1f}%')
se = np.sqrt(pick.ok.mean()*(1-pick.ok.mean())/len(pick))
print(f'  desvio de calibracion:       {100*(pick.ok.mean()-pick.p.mean()):+.2f} pp  (+/- {100*1.96*se:.2f} IC95)')
print()
print('  por banda dentro del filtro:')
for lo in [0.65,0.70,0.75,0.80,0.85,0.90,0.95]:
    hi = lo+0.05 if lo<0.95 else 1.01
    s = pick[(pick.p>=lo)&(pick.p<hi)]
    if len(s)<100: continue
    print(f'    {100*lo:3.0f}-{100*hi:3.0f}%  n={len(s):6d}  predice {100*s.p.mean():5.1f}%  cae {100*s.ok.mean():5.1f}%  {100*(s.ok.mean()-s.p.mean()):+5.1f} pp')
print()
print('  por tipo de mercado:')
for fam, lab in [('res','1X2 y doble oportunidad'),('tot','mas/menos goles'),
                 ('btts','ambos marcan / valla invicta'),('hteam','goles del local'),('ateam','goles del visitante')]:
    s = pick[pick.fam==fam]
    if len(s)<50: continue
    print(f'    {lab:28s} n={len(s):6d}  predice {100*s.p.mean():5.1f}%  cae {100*s.ok.mean():5.1f}%  {100*(s.ok.mean()-s.p.mean()):+5.1f} pp')
print()
print('  por liga:')
for lg in ['premier','laliga','seriea','bundesliga']:
    s = pick[pick.lg==lg]
    print(f'    {lg:11s} n={len(s):6d}  predice {100*s.p.mean():5.1f}%  cae {100*s.ok.mean():5.1f}%  {100*(s.ok.mean()-s.p.mean()):+5.1f} pp')

print()
print('='*74)
print('COMBINADAS: probabilidad conjunta > 40%, una pata por partido')
print('='*74)
# simulate weekly ticket building exactly as the app will do it
r2 = r.reset_index(drop=True)
r2['wk'] = r2.MatchDate.dt.to_period('W')
best = {}
for i, x in r2.iterrows():
    mk, _, _ = markets(x.lg, x.pH, x.pD, x.pA)
    cand = [(k, p, settle(k, x.FTHome, x.FTAway)) for k,(l,p) in mk.items() if 0.65 < p < 0.93]
    if cand:
        k,p,ok = max(cand, key=lambda z: z[1])
        best.setdefault(x.wk, []).append((p, ok))
res = {2:[],3:[],4:[]}
for wk, legs in best.items():
    legs.sort(key=lambda z: -z[0])
    for n in (2,3,4):
        for start in range(0, max(1,len(legs)-n+1), n):
            grp = legs[start:start+n]
            if len(grp) < n: break
            jp = np.prod([g[0] for g in grp])
            if jp > 0.40:
                res[n].append((jp, all(g[1] for g in grp)))
for n in (2,3,4):
    v = res[n]
    if not v: continue
    pr = np.mean([z[0] for z in v]); hit = np.mean([z[1] for z in v])
    se = np.sqrt(hit*(1-hit)/len(v))
    print(f'  {n} patas:  n={len(v):5d}  predice {100*pr:5.1f}%  cae {100*hit:5.1f}%  {100*(hit-pr):+5.1f} pp (+/- {100*1.96*se:.1f})')
    print(f'            cuota justa {1/pr:.2f}  ->  con esa cuota el ROI real seria {100*(hit/pr-1):+.1f}%')
S.to_csv('validate_markets.csv', index=False)
