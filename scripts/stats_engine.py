"""Corners, cards, shots and goalkeeper saves — match total and per team.

Design note: my own audit found a team's own history predicts these barely better
than the league mean (corners +0.9%, fouls +1.5%, cards -1.8%). So the model leans
on the league baseline split home/away, adjusted by the mismatch between the sides,
with only a heavily shrunk team term. Everything is negative binomial except cards,
which measured Poisson (var/mean 0.93-0.98).
"""
import numpy as np
from scipy.stats import nbinom, poisson

# Medias por partido y por lado (local, visitante), medidas sobre 4.620 partidos de
# 2023-2027. Reemplazan a las de 2018-2025, que habian quedado desfasadas: las
# amarillas de Premier subieron 12,4% y las de Serie A bajaron 11,1%, y las atajadas
# de Serie A cayeron 12,9%. Ver el PR 'recalibrar-estadisticas' para la medicion.
BASE = {
 'premier':   {'cor':(5.60,4.72), 'yel':(1.83,2.16), 'sho':(14.35,11.90), 'sav':(2.81,3.30)},
 'laliga':    {'cor':(5.37,4.17), 'yel':(2.17,2.37), 'sho':(13.70,10.86), 'sav':(2.55,3.33)},
 'seriea':    {'cor':(5.20,4.07), 'yel':(1.80,2.11), 'sho':(13.71,11.29), 'sav':(2.57,3.12)},
 'bundesliga':{'cor':(5.56,4.25), 'yel':(1.85,2.06), 'sho':(14.82,11.94), 'sav':(2.81,3.61)},
}
# variance/mean, measured per side
DISP = {'cor':1.607, 'yel':0.956, 'sho':2.077, 'sav':1.376}
# how each side moves with SIGNED market supremacy (pH - pA): (home b, away b).
# Measured: a big home favourite takes 6.78 corners to the underdog's 3.38, and
# 16.94 shots to 8.66, while its keeper drops to 2.20 saves against the other's 4.27.
MISMATCH = {'cor':(0.5347,-0.5488), 'yel':(-0.2707,0.1331),
            'sho':(0.5209,-0.5304), 'sav':(-0.5406,0.5350)}
CALIB = {'cor':0.965, 'yel':0.995, 'sho':0.980, 'sav':0.960}  # p' = .5 + c(p-.5), fitted on
# the first half of 2021-25 and verified on the second: -0.93 pp -> -0.32 pp at the 65% filter
SHRINK = 0.5   # weight on the team's own historical ratio (MAE: shots +5.7%, corners +2.6%)


def nb_pmf(mean, vm, kmax):
    """Negative binomial with the measured variance/mean ratio; Poisson when vm<=1."""
    k = np.arange(kmax)
    if vm <= 1.02:
        return poisson.pmf(k, max(mean, 0.05))
    var = mean * vm
    r = mean * mean / max(var - mean, 1e-6)
    p = r / (r + mean)
    return nbinom.pmf(k, r, p)


def side_mean(lg, stat, side, sup, team_ratio=1.0):
    """Expected value for one side. sup = pH - pA from the market, WITH sign."""
    i = 0 if side == 'H' else 1
    b = BASE[lg][stat][i]
    m = b * (1 + MISMATCH[stat][i] * sup)
    if SHRINK and team_ratio:
        m *= 1 + SHRINK * (team_ratio - 1)
    return max(m, 0.05)


KMAX = {'cor': 22, 'yel': 11, 'sho': 42, 'sav': 16}


def dists(lg, stat, sup, rH=1.0, rA=1.0):
    """(home pmf, away pmf, match-total pmf) for one stat."""
    km = KMAX[stat]
    mh = side_mean(lg, stat, 'H', sup, rH)
    ma = side_mean(lg, stat, 'A', sup, rA)
    ph = nb_pmf(mh, DISP[stat], km)
    pa = nb_pmf(ma, DISP[stat], km)
    tot = np.convolve(ph, pa)
    return ph / ph.sum(), pa / pa.sum(), tot / tot.sum(), mh, ma


LINES = {
 'cor': {'match':[7.5,8.5,9.5,10.5,11.5,12.5], 'team':[2.5,3.5,4.5,5.5,6.5]},
 'yel': {'match':[2.5,3.5,4.5,5.5],            'team':[0.5,1.5,2.5,3.5]},
 'sho': {'match':[19.5,21.5,23.5,25.5,27.5],   'team':[8.5,10.5,12.5,14.5]},
 'sav': {'match':[3.5,4.5,5.5,6.5,7.5],        'team':[1.5,2.5,3.5,4.5]},
}
ES = {'cor':('Corners','corners'), 'yel':('Tarjetas','amarillas'),
      'sho':('Remates','remates'), 'sav':('Atajadas','atajadas')}


def stat_markets(lg, sup, home, away, rH=None, rA=None):
    """Every corner/card/shot/save market, as {key: (label, prob, family)}."""
    out = {}
    for stat in ('cor', 'yel', 'sho', 'sav'):
        ph, pa, tot, mh, ma = dists(lg, stat, sup,
                                    (rH or {}).get(stat, 1.0), (rA or {}).get(stat, 1.0))
        cat, word = ES[stat]
        cum = np.cumsum(tot)
        for L in LINES[stat]['match']:
            i = int(np.floor(L))
            over = float(1 - cum[i]) if i < len(cum) else 0.0
            o = 0.5 + CALIB[stat] * (over - 0.5)
            out[f'{stat}_m_o{L}'] = (f'Mas de {L} {word} en el partido', o, f'{stat}_m', cat)
            out[f'{stat}_m_u{L}'] = (f'Menos de {L} {word} en el partido', 1 - o, f'{stat}_m', cat)
        for side, pmf, nm, mean in (('h', ph, home, mh), ('a', pa, away, ma)):
            c = np.cumsum(pmf)
            who = f'{nm}' if stat != 'sav' else f'arquero de {nm}'
            for L in LINES[stat]['team']:
                i = int(np.floor(L))
                over = float(1 - c[i]) if i < len(c) else 0.0
                o = 0.5 + CALIB[stat] * (over - 0.5)
                out[f'{stat}_{side}_o{L}'] = (f'Mas de {L} {word}: {who}', o, f'{stat}_{side}', cat)
                out[f'{stat}_{side}_u{L}'] = (f'Menos de {L} {word}: {who}', 1 - o, f'{stat}_{side}', cat)
    return out
