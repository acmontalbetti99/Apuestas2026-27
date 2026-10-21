"""Walk-forward backtest on the 4 target leagues, 2021-2025.
Every model is fitted ONLY on matches before each prediction date.
Benchmark = Bet365 closing odds with the vig removed (log loss 0.9679).
"""
import pandas as pd, numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

D = pd.read_csv('data/Matches.csv', low_memory=False)
D['MatchDate'] = pd.to_datetime(D['MatchDate'])
TGT = {'E0':'Premier','SP1':'LaLiga','I1':'SerieA','D1':'Bundesliga'}
f = D[D.Division.isin(TGT)].copy()
f['season'] = np.where(f.MatchDate.dt.month>=7, f.MatchDate.dt.year, f.MatchDate.dt.year-1)
f = f[(f.season>=2014)&(f.season<=2025)].dropna(subset=['FTHome','FTAway','OddHome','HomeElo']).sort_values('MatchDate').reset_index(drop=True)
f['res'] = f.FTResult

# ---- market probabilities (vig removed proportionally) ----
inv = 1/f.OddHome + 1/f.OddDraw + 1/f.OddAway
f['mH']=(1/f.OddHome)/inv; f['mD']=(1/f.OddDraw)/inv; f['mA']=(1/f.OddAway)/inv

TEST = f[f.season>=2021].index
print(f'training pool 2014-2020, test set {len(TEST)} matches (2021-2025)\n')

# =============== 1. DIXON-COLES (goals) and a SOT-based variant ===============
def dc_loglike(params, hg, ag, hi, ai, nt, xw):
    att = params[:nt]; dfn = params[nt:2*nt]; hfa = params[2*nt]; rho = params[2*nt+1]
    lh = np.exp(att[hi] - dfn[ai] + hfa); la = np.exp(att[ai] - dfn[hi])
    lh = np.clip(lh,0.05,8); la = np.clip(la,0.05,8)
    ll = poisson.logpmf(hg,lh) + poisson.logpmf(ag,la)
    # Dixon-Coles low-score correction
    tau = np.ones(len(hg))
    m00=(hg==0)&(ag==0); m01=(hg==0)&(ag==1); m10=(hg==1)&(ag==0); m11=(hg==1)&(ag==1)
    tau[m00]=1-lh[m00]*la[m00]*rho; tau[m01]=1+lh[m01]*rho
    tau[m10]=1+la[m10]*rho;         tau[m11]=1-rho
    ll = ll + np.log(np.clip(tau,1e-6,None))
    return -(ll*xw).sum()

def fit_dc(sub, teams, half_life_days, asof, goal_cols=('FTHome','FTAway')):
    nt=len(teams); ix={t:i for i,t in enumerate(teams)}
    hi=sub.HomeTeam.map(ix).values; ai=sub.AwayTeam.map(ix).values
    hg=sub[goal_cols[0]].values; ag=sub[goal_cols[1]].values
    age=(asof-sub.MatchDate).dt.days.values
    xw=np.exp(-np.log(2)*age/half_life_days)
    p0=np.concatenate([np.zeros(nt), np.zeros(nt), [0.25],[ -0.03]])
    cons=({'type':'eq','fun':lambda p: p[:nt].sum()},)
    r=minimize(dc_loglike,p0,args=(hg,ag,hi,ai,nt,xw),method='SLSQP',constraints=cons,
               options={'maxiter':120,'ftol':1e-4})
    return r.x, ix, nt

def dc_probs(params, ix, nt, home, away, scale=1.0):
    att=params[:nt]; dfn=params[nt:2*nt]; hfa=params[2*nt]; rho=params[2*nt+1]
    if home not in ix or away not in ix: return None
    h,a=ix[home],ix[away]
    lh=np.clip(np.exp(att[h]-dfn[a]+hfa)*scale,0.05,8); la=np.clip(np.exp(att[a]-dfn[h])*scale,0.05,8)
    K=11; ph=poisson.pmf(np.arange(K),lh); pa=poisson.pmf(np.arange(K),la)
    M=np.outer(ph,pa)
    M[0,0]*=1-lh*la*rho; M[0,1]*=1+lh*rho; M[1,0]*=1+la*rho; M[1,1]*=1-rho
    M/=M.sum()
    return M[np.tril_indices(K,-1)].sum(), np.trace(M), M[np.triu_indices(K,1)].sum(), M

# =============== 2. ELO logistic (fit on training window) ===============
from sklearn.linear_model import LogisticRegression
tr = f[f.season<2021]
Xtr = np.c_[(tr.HomeElo-tr.AwayElo).values/100]
elo_lr = LogisticRegression(max_iter=1000).fit(Xtr, tr.res.values)

# =============== walk-forward ===============
results=[]
f['sotG_H'] = f.HomeTarget*0.32   # SOT -> goal-equivalents, scaled below
f['sotG_A'] = f.AwayTarget*0.32

refit_every = 20   # matchdays
for lg_code, lg in TGT.items():
    L = f[f.Division==lg_code].reset_index(drop=True)
    test_idx = L.index[L.season>=2021]
    model_cache = {}
    last_fit = -999
    for i in test_idx:
        row = L.loc[i]
        if i - last_fit >= refit_every:
            hist = L.loc[:i-1]
            hist = hist[hist.MatchDate < row.MatchDate]
            hist = hist[hist.MatchDate >= row.MatchDate - pd.Timedelta(days=1100)]
            teams = sorted(set(hist.HomeTeam)|set(hist.AwayTeam))
            if len(hist) < 300: continue
            try:
                pg = fit_dc(hist, teams, 240, row.MatchDate)
                hs = hist.dropna(subset=['HomeTarget','AwayTarget'])
                scale = (hist.FTHome.mean()+hist.FTAway.mean())/(hs.HomeTarget.mean()+hs.AwayTarget.mean())
                hs = hs.assign(sh=(hs.HomeTarget*scale).round().astype(int),
                               sa=(hs.AwayTarget*scale).round().astype(int))
                ps = fit_dc(hs, teams, 240, row.MatchDate, goal_cols=('sh','sa'))
            except Exception:
                continue
            model_cache = {'g':pg, 's':ps}
            last_fit = i
        if not model_cache: continue
        og = dc_probs(*model_cache['g'], row.HomeTeam, row.AwayTeam)
        os_ = dc_probs(*model_cache['s'], row.HomeTeam, row.AwayTeam)
        if og is None or os_ is None: continue
        pe = elo_lr.predict_proba(np.array([[(row.HomeElo-row.AwayElo)/100]]))[0]
        pe = dict(zip(elo_lr.classes_, pe))
        results.append({'lg':lg,'res':row.res,
            'mH':row.mH,'mD':row.mD,'mA':row.mA,
            'gH':og[0],'gD':og[1],'gA':og[2],
            'sH':os_[0],'sD':os_[1],'sA':os_[2],
            'eH':pe['H'],'eD':pe['D'],'eA':pe['A']})

R = pd.DataFrame(results)
print(f'scored {len(R)} matches\n')

def score(df, pre, label):
    P = df[[pre+'H',pre+'D',pre+'A']].values
    P = P/P.sum(axis=1,keepdims=True)
    y = df.res.map({'H':0,'D':1,'A':2}).values
    pact = P[np.arange(len(y)),y]
    ll = -np.log(np.clip(pact,1e-9,None)).mean()
    oh = np.eye(3)[y]
    br = ((P-oh)**2).sum(axis=1).mean()
    hit = (P.argmax(axis=1)==y).mean()
    return {'modelo':label,'log loss':ll,'Brier':br,'acierto':100*hit}

rows=[score(R,'m','Mercado (Bet365 cierre)'), score(R,'e','Elo (logística)'),
      score(R,'g','Dixon-Coles sobre goles'), score(R,'s','Dixon-Coles sobre tiros al arco')]

# blends
for name, parts in [('DC-goles + Elo',['g','e']), ('DC-goles + DC-tiros',['g','s']),
                    ('DC-goles + DC-tiros + Elo',['g','s','e']),
                    ('Modelo propio (3) + Mercado',['g','s','e','m'])]:
    for o in 'HDA':
        R['b'+o] = np.mean([R[p+o] for p in parts], axis=0)
    rows.append(score(R,'b',name))

out = pd.DataFrame(rows).set_index('modelo')
print('=== BACKTEST WALK-FORWARD, 4 LIGAS, 2021-2025 ===')
print(out.round(4).to_string())
print('\n(menor log loss = mejor. El mercado es la referencia.)')

print('\n=== por liga: log loss ===')
tab={}
for lg in TGT.values():
    s=R[R.lg==lg]
    if len(s)<100: continue
    for o in 'HDA': s=s.assign(**{'b'+o: np.mean([s['g'+o],s['s'+o],s['e'+o]],axis=0)})
    tab[lg]={'n':len(s),'mercado':score(s,'m','')['log loss'],
             'modelo propio':score(s,'b','')['log loss'],
             'DC-goles':score(s,'g','')['log loss']}
print(pd.DataFrame(tab).T.round(4).to_string())

R.to_csv('backtest_probs.csv',index=False)
print('\nguardado backtest_probs.csv')
