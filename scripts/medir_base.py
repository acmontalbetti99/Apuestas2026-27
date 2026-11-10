#!/usr/bin/env python3
"""Mide las medias por liga que usa el modelo de estadisticas y las compara con
las que tiene cargadas.

Para que sirve: BASE en stats_engine.py son las medias de cornners, tarjetas,
remates al arco y atajadas por partido y por lado. Si envejecen, el modelo queda
sesgado de forma sistematica, y ese sesgo no se ve como un error grande en un
partido sino como un pick que parece mas probable de lo que es. Las lineas de
tarjetas son cortas, asi que ahi se nota primero: con 3.55 amarillas esperadas,
"menos de 3.5" parece bastante mas probable de lo que es si en realidad caen 3.99.

No cambia nada: imprime y sale. Correrlo a mano cuando se sospeche del sesgo o al
empezar una temporada, desde el workflow "Medir las bases del modelo".

No se puede correr en el contenedor de Claude, que tiene la salida restringida a
los registros de paquetes y a GitHub. football-data.co.uk solo se alcanza desde
Actions.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from refresh import DIVS, load_results, log, prefer_ipv4  # noqa: E402
from stats_engine import BASE, CALIB, DISP  # noqa: E402

# Columnas de football-data por estadistica, (local, visitante).
COLS = {"cor": ("HC", "AC"), "yel": ("HY", "AY"),
        "sho": ("HST", "AST"), "sav": ("savH", "savA")}
DESDE = "2023-07-01"           # mismo recorte que uso el PR, para poder comparar


def main() -> int:
    prefer_ipv4()
    D = load_results(datetime.now(timezone.utc))
    if D is None or D.empty:
        log("sin datos, no se puede medir")
        return 1

    D = D[pd.to_datetime(D["fecha"]) >= DESDE]
    log(f"Medias por partido medidas sobre {len(D)} partidos desde {DESDE}")
    log("")
    log(f"{'liga':<11}{'stat':<6}{'n':>6}{'cargado':>18}{'medido':>18}{'desvio':>18}")

    peor = []
    for lg in sorted(set(DIVS.values())):
        S = D[D["Div"].map(DIVS).eq(lg)] if "Div" in D.columns else D[D["lg"].eq(lg)]
        for stat, (ch, ca) in COLS.items():
            if ch not in S.columns or ca not in S.columns:
                log(f"{lg:<11}{stat:<6}{'-':>6}  faltan columnas {ch}/{ca}")
                continue
            h = pd.to_numeric(S[ch], errors="coerce")
            a = pd.to_numeric(S[ca], errors="coerce")
            ok = h.notna() & a.notna()
            n = int(ok.sum())
            if n < 200:
                log(f"{lg:<11}{stat:<6}{n:>6}  muestra corta, no se concluye")
                continue
            mh, ma = float(h[ok].mean()), float(a[ok].mean())
            bh, ba = BASE[lg][stat]
            dh = 100 * (mh - bh) / bh
            da = 100 * (ma - ba) / ba
            log(f"{lg:<11}{stat:<6}{n:>6}"
                f"{f'({bh:.2f},{ba:.2f})':>18}{f'({mh:.2f},{ma:.2f})':>18}"
                f"{f'{dh:+.1f}% / {da:+.1f}%':>18}")
            if max(abs(dh), abs(da)) >= 8:
                peor.append((lg, stat, dh, da))
            # dispersion: el modelo usa una sola por estadistica, no por liga
            for lado, v in (("local", h[ok]), ("visitante", a[ok])):
                m = float(v.mean())
                if m > 0:
                    r = float(v.var()) / m
                    if abs(r - DISP[stat]) / DISP[stat] >= 0.25:
                        log(f"             dispersion {lado}: {r:.3f} contra "
                            f"{DISP[stat]:.3f} cargada")

    log("")
    if peor:
        log("Desvios de 8% o mas, que son los que mueven una linea corta:")
        for lg, stat, dh, da in sorted(peor, key=lambda x: -max(abs(x[2]), abs(x[3]))):
            log(f"  {lg} {stat}: {dh:+.1f}% local, {da:+.1f}% visitante")
    else:
        log("Ningun desvio llega al 8%: las bases cargadas siguen sirviendo.")
    log("")
    log(f"CALIB cargado: {CALIB}")
    log("Ojo: CALIB se ajusto contra las bases viejas. El factor por cubo que mide")
    log("refresh.py sobre los picks liquidados es el que manda ahora, y ese se")
    log("reajusta solo en cada corrida.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
