"""Market-anchored match model + pick generator.

1X2 comes straight from the market (it beats every model I tested).
Goals markets come from a Dixon-Coles surface fitted so that:
  - its total expected goals matches league baseline x measured supremacy effect
  - its 1X2 split matches the market's home/away ratio
Everything else is derived from that surface, so no market can contradict another.
"""
import numpy as np
from scipy.stats import poisson
from scipy.optimize import brentq

# measured on 11,567 matches (2018-2025), see calibration run
LEAGUE_BASE = {'premier': 2.927, 'laliga': 2.595, 'seriea': 2.605, 'bundesliga': 3.176}
SUP_SLOPE   = 0.3678        # goles = base * (1 + 0.3678*|pH-pA|) / (1 + 0.3678*mean|sup|)
MEAN_SUP    = 0.2847        # mean |supremacy| in the calibration sample
RHO         = {'premier': -0.015, 'laliga': -0.055, 'seriea': -0.022, 'bundesliga': -0.065}
KMAX        = 12


def tau(i, j, lh, la, rho):
    if i == 0 and j == 0: return 1 - lh * la * rho
    if i == 0 and j == 1: return 1 + lh * rho
    if i == 1 and j == 0: return 1 + la * rho
    if i == 1 and j == 1: return 1 - rho
    return 1.0


def surface(lh, la, rho):
    """Full scoreline probability matrix with the Dixon-Coles low-score correction."""
    ph = poisson.pmf(np.arange(KMAX), lh)
    pa = poisson.pmf(np.arange(KMAX), la)
    M = np.outer(ph, pa)
    for i in (0, 1):
        for j in (0, 1):
            M[i, j] *= tau(i, j, lh, la, rho)
    return M / M.sum()


def fit_lambdas(lg, pH, pA):
    """Find (lambdaH, lambdaA) whose total matches the league/supremacy baseline
    and whose home/away win ratio matches the market."""
    sup = abs(pH - pA)
    total = LEAGUE_BASE[lg] * (1 + SUP_SLOPE * sup) / (1 + SUP_SLOPE * MEAN_SUP)
    rho = RHO[lg]
    target = pH / (pH + pA)

    def ratio(s):
        lh, la = (total + s) / 2, (total - s) / 2
        lh, la = max(lh, 0.05), max(la, 0.05)
        M = surface(lh, la, rho)
        h = np.tril(M, -1).sum()
        a = np.triu(M, 1).sum()
        return h / (h + a) - target

    lo, hi = -total + 0.1, total - 0.1
    try:
        s = brentq(ratio, lo, hi, xtol=1e-4)
    except ValueError:
        s = np.clip((pH - pA) * total, lo, hi)
    lh, la = max((total + s) / 2, 0.05), max((total - s) / 2, 0.05)
    return lh, la, rho


def markets(lg, pH, pD, pA):
    """Every market we can price, as {key: (label, probability)}."""
    lh, la, rho = fit_lambdas(lg, pH, pA)
    M = surface(lh, la, rho)
    tot = np.add.outer(np.arange(KMAX), np.arange(KMAX))
    hg = np.repeat(np.arange(KMAX)[:, None], KMAX, 1)
    ag = np.repeat(np.arange(KMAX)[None, :], KMAX, 0)
    out = {}
    P = lambda mask: float(M[mask].sum())

    # 1X2 and double chance come from the market itself, exact
    out['1']    = ('Gana local', pH)
    out['X']    = ('Empate', pD)
    out['2']    = ('Gana visitante', pA)
    out['1X']   = ('Local o empate', pH + pD)
    out['12']   = ('Local o visitante (no empate)', pH + pA)
    out['X2']   = ('Empate o visitante', pD + pA)

    # goals markets from the fitted surface
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        out[f'O{line}'] = (f'Mas de {line} goles', P(tot > line))
        out[f'U{line}'] = (f'Menos de {line} goles', P(tot < line))
    out['BTTS']  = ('Ambos marcan', P((hg > 0) & (ag > 0)))
    out['NBTTS'] = ('Ambos marcan: NO', P((hg == 0) | (ag == 0)))
    for line in (0.5, 1.5, 2.5):
        out[f'HO{line}'] = (f'Local mas de {line}', P(hg > line))
        out[f'HU{line}'] = (f'Local menos de {line}', P(hg < line))
        out[f'AO{line}'] = (f'Visitante mas de {line}', P(ag > line))
        out[f'AU{line}'] = (f'Visitante menos de {line}', P(ag < line))
    out['CS_H'] = ('Local no recibe gol', P(ag == 0))
    out['CS_A'] = ('Visitante no recibe gol', P(hg == 0))
    return out, lh, la


# markets that are nearly the same bet - never put two of these on one ticket,
# and never recommend both for the same match
FAMILY = {'1':'res','X':'res','2':'res','1X':'res','12':'res','X2':'res',
          'BTTS':'btts','NBTTS':'btts','CS_H':'btts','CS_A':'btts'}
for L in (0.5,1.5,2.5,3.5,4.5):
    FAMILY[f'O{L}']='tot'; FAMILY[f'U{L}']='tot'
for L in (0.5,1.5,2.5):
    FAMILY[f'HO{L}']='hteam'; FAMILY[f'HU{L}']='hteam'
    FAMILY[f'AO{L}']='ateam'; FAMILY[f'AU{L}']='ateam'
