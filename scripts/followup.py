import pandas as pd, numpy as np
R = pd.read_csv('backtest_probs.csv')
# clean: keep rows where every model produced a valid simplex
for p in ['m','e','g','s']:
    c=[p+'H',p+'D',p+'A']
    R=R[np.isfinite(R[c]).all(axis=1) & (R[c]>0).all(axis=1)]
    s=R[c].sum(axis=1); R=R[(s>0.9)&(s<1.1)]
    R[c]=R[c].div(R[c].sum(axis=1),axis=0)
print(f'clean n = {len(R)}\n')
y = R.res.map({'H':0,'D':1,'A':2}).values; oh=np.eye(3)[y]
def sc(P):
    P=np.clip(P,1e-6,1); P=P/P.sum(axis=1,keepdims=True)
    return (-np.log(P[np.arange(len(y)),y]).mean(), ((P-oh)**2).sum(1).mean(), 100*(P.argmax(1)==y).mean())
M=lambda p: R[[p+'H',p+'D',p+'A']].values

print('=== 1. MODELOS INDIVIDUALES (n=%d) ==='%len(R))
for p,lab in [('m','Mercado (Bet365 cierre, sin vig)'),('e','Elo (logística)'),
              ('g','Dixon-Coles sobre goles'),('s','Dixon-Coles sobre tiros al arco')]:
    ll,br,hit=sc(M(p)); print(f'  {lab:36s} log loss {ll:.4f}   Brier {br:.4f}   acierto {hit:.1f}%')

print('\n=== 2. ¿CUÁNTO PESO MERECE EL MODELO PROPIO? ===')
own = (M('g')+M('e')+M('s'))/3
best=None
for w in np.arange(0,1.01,0.1):
    P = (1-w)*M('m') + w*own
    ll,br,hit = sc(P)
    star = ''
    if best is None or ll<best[1]: best=(w,ll); star=''
    print(f'  {100*(1-w):3.0f}% mercado + {100*w:3.0f}% modelo propio -> log loss {ll:.4f}  acierto {hit:.1f}%')
print(f'  -> mejor mezcla: {100*best[0]:.0f}% modelo propio (log loss {best[1]:.4f})')

print('\n=== 3. ¿EL MODELO APORTA DONDE EL MERCADO DUDA? ===')
R['dis'] = np.abs(M('m')-own).sum(1)/2
for lo,hi in [(0,.05),(.05,.10),(.10,.20),(.20,1)]:
    s=(R.dis>=lo)&(R.dis<hi)
    if s.sum()<150: continue
    yl=y[s.values]; ohl=np.eye(3)[yl]
    f=lambda P: -np.log(np.clip(P[np.arange(len(yl)),yl],1e-6,1)).mean()
    print(f'  desacuerdo {100*lo:2.0f}-{100*hi:3.0f}%  n={s.sum():4d}   mercado {f(M("m")[s.values]):.4f}   propio {f(own[s.values]):.4f}   50/50 {f(0.5*M("m")[s.values]+0.5*own[s.values]):.4f}')

print('\n=== 4. CORRECCIÓN DE CALIBRACIÓN DEL MERCADO (¿es explotable?) ===')
# fit a single-parameter power transform on 2021-23, test on 2024-25
R['half'] = np.arange(len(R)) < len(R)//2
def pw(P,k):
    Q=np.clip(P,1e-6,1)**k; return Q/Q.sum(axis=1,keepdims=True)
tr,te = R.half.values, ~R.half.values
ytr,yte = y[tr], y[te]
best=(1,9)
for k in np.arange(0.80,1.35,0.01):
    P=pw(M('m')[tr],k); ll=-np.log(np.clip(P[np.arange(len(ytr)),ytr],1e-9,1)).mean()
    if ll<best[1]: best=(k,ll)
k=best[0]
f=lambda P,yy: -np.log(np.clip(P[np.arange(len(yy)),yy],1e-9,1)).mean()
print(f'  exponente ajustado en la 1a mitad: k = {k:.2f}  (k>1 = el mercado es poco confiado)')
print(f'  2a mitad (fuera de muestra):  mercado crudo {f(M("m")[te],yte):.4f}   mercado corregido {f(pw(M("m")[te],k),yte):.4f}')
print(f'  mejora = {f(M("m")[te],yte)-f(pw(M("m")[te],k),yte):+.4f}')

print('\n=== 5. VALOR POR BANDA DE CUOTA (con el margen real de la casa) ===')
D = pd.read_csv('data/Matches.csv',low_memory=False)
D['MatchDate']=pd.to_datetime(D['MatchDate'])
D=D[D.Division.isin(['E0','SP1','I1','D1'])]
D['season']=np.where(D.MatchDate.dt.month>=7,D.MatchDate.dt.year,D.MatchDate.dt.year-1)
D=D[(D.season>=2021)&(D.season<=2025)].dropna(subset=['OddHome','MaxHome'])
rows=[]
for side,oc,mc,win in [('H','OddHome','MaxHome',D.FTResult=='H'),('D','OddDraw','MaxDraw',D.FTResult=='D'),('A','OddAway','MaxAway',D.FTResult=='A')]:
    rows.append(pd.DataFrame({'b365':D[oc],'best':D[mc],'w':win}))
A=pd.concat(rows).dropna()
A['band']=pd.cut(A.b365,[1,1.5,2,2.5,3.5,5,8,1000])
print('  ROI apostando a ciegas, con Bet365 vs tomando la MEJOR cuota del mercado:')
t=A.groupby('band',observed=True).apply(lambda x: pd.Series({
 'n':len(x),'%gana':100*x.w.mean(),
 'ROI Bet365 %':100*((x.w*x.b365).mean()-1),
 'ROI mejor cuota %':100*((x.w*x.best).mean()-1)}), include_groups=False)
print(t.round(2).to_string())
