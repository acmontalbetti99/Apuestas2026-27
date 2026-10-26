#!/usr/bin/env python3
"""Cuotas de las competencias UEFA desde The Odds API.

Por que hace falta: football-data.co.uk solo publica ligas domesticas, asi que
Champions, Europa y Conference no tenian de donde sacar cuotas y por eso no se les
podian generar picks. The Odds API agrega varias casas, bet365 entre ellas, con
capa gratuita de 500 consultas al mes.

Por que no se raspa bet365 directo: no tiene API publica y sus terminos prohiben
el acceso automatizado. Esta es la via licenciada para las mismas cuotas.

Sin la variable ODDS_API_KEY el script no hace nada y sale con 0, para que el
workflow siga andando igual. Escribe data/cuotas_extra.json, que refresh.py suma
a los fixtures de football-data.

Consumo: una consulta por competencia y corrida. Con la corrida diaria son ~90 al
mes sobre 500, asi que entra holgado aun sumando las cuatro ligas domesticas.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from refresh import DATA, es_femenino, log, prefer_ipv4  # noqa: E402

BASE = "https://api.the-odds-api.com/v4"

# clave de la competencia en The Odds API -> nuestro codigo
COMPETENCIAS = {
    "soccer_uefa_champs_league": "ucl",
    "soccer_uefa_europa_league": "uel",
    "soccer_uefa_europa_conference_league": "uecl",
    "soccer_uefa_nations_league": "unl",
    "soccer_fifa_world_cup_qualifiers_europe": "wcq_eu",
    "soccer_conmebol_world_cup_qualifiers": "wcq_sa",
    "soccer_africa_cup_of_nations": "afcon",
    "soccer_conmebol_copa_america": "copa",
}
# Una competencia fuera de temporada devuelve 404 y no es un error: se saltea sola.

# Como nombra cada equipo The Odds API frente a como lo nombran nuestros picks.
# Se completa a medida que aparezcan diferencias; el log avisa cual falta.
ALIAS = {
    "Inter Milan": "Inter", "Internazionale": "Inter", "AC Milan": "Milan",
    "Atletico Madrid": "Atletico Madrid", "Athletic Bilbao": "Athletic Bilbao",
    "Club Brugge": "Club Brujas", "RC Lens": "Lens", "Lens": "Lens",
    "Real Betis": "Real Betis", "Feyenoord": "Feyenoord",
    "Galatasaray": "Galatasaray", "Lille": "Lille", "Como": "Como",
    "Shakhtar Donetsk": "Shakhtar Donetsk", "LASK": "LASK Linz",
    "Sporting Lisbon": "Sporting CP", "Sporting CP": "Sporting CP",
    "Bayern Munich": "Bayern Munich", "Borussia Dortmund": "Dortmund",
    "Bayer Leverkusen": "Leverkusen", "RB Leipzig": "RB Leipzig",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "Manchester United": "Manchester United", "Manchester City": "Manchester City",
    "Tottenham Hotspur": "Tottenham", "Newcastle United": "Newcastle",
    "Nottingham Forest": "Nottingham Forest", "Wolverhampton Wanderers": "Wolves",
}


def nombre(raw: str) -> str:
    return ALIAS.get(str(raw).strip(), str(raw).strip())


def sin_margen(o1: float, ox: float, o2: float) -> tuple[float, float, float]:
    """Probabilidades normalizadas: le saca el margen de la casa por proporcion."""
    inv = [1 / o1, 1 / ox, 1 / o2]
    s = sum(inv)
    return inv[0] / s, inv[1] / s, inv[2] / s


def consenso(bookmakers: list[dict], home: str, away: str) -> dict | None:
    """Promedia el 1X2 de todas las casas y guarda aparte lo que paga bet365.

    El promedio esta mejor calibrado que una casa sola, asi que de ahi sale la
    probabilidad. Bet365 entra solo como el precio contra el cual se compara.
    """
    cuotas, b365 = [], {}
    mejor: dict[str, tuple[float, str]] = {}   # mejor precio por resultado y quien lo paga
    for bk in bookmakers:
        for m in bk.get("markets", []):
            if m.get("key") != "h2h":
                continue
            d = {o.get("name"): o.get("price") for o in m.get("outcomes", [])}
            o1, ox, o2 = d.get(home), d.get("Draw"), d.get(away)
            if not all(isinstance(v, (int, float)) and v > 1 for v in (o1, ox, o2)):
                continue
            cuotas.append((o1, ox, o2))
            for k, v in (("1", o1), ("X", ox), ("2", o2)):
                if k not in mejor or v > mejor[k][0]:
                    mejor[k] = (v, bk.get("key", "?"))
            if bk.get("key") == "bet365":
                b365 = {"1": round(o1, 2), "X": round(ox, 2), "2": round(o2, 2)}
                comb = lambda a, b: round(1 / (1 / a + 1 / b), 2)
                b365.update({"1X": comb(o1, ox), "12": comb(o1, o2), "X2": comb(ox, o2),
                             "_estimadas": ["1X", "12", "X2"]})
    if not cuotas:
        return None
    probs = [sin_margen(*c) for c in cuotas]
    n = len(probs)
    pH, pD, pA = (sum(p[i] for p in probs) / n for i in range(3))
    s = pH + pD + pA
    # El mejor precio del mercado es el unico sitio donde aparece valor positivo:
    # medido sobre 242 selecciones y 31 casas, la mejor cuota deja -1.17% de media
    # contra -5.11% de bet365 sola, y en el 19% de los casos da positivo.
    best: dict[str, float] = {}
    quien: dict[str, str] = {}
    for k, (v, bk) in mejor.items():
        best[k] = round(v, 2)
        quien[k] = bk
    comb = lambda a, b: round(1 / (1 / a + 1 / b), 2)   # noqa: E731
    if "1" in best and "X" in best: best["1X"] = comb(best["1"], best["X"])
    if "1" in best and "2" in best: best["12"] = comb(best["1"], best["2"])
    if "X" in best and "2" in best: best["X2"] = comb(best["X"], best["2"])
    return {"pH": pH / s, "pD": pD / s, "pA": pA / s, "b365": b365,
            "mejor": best, "quien": quien, "casas": n}


def main() -> int:
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        log("The Odds API: sin ODDS_API_KEY, no se piden cuotas UEFA")
        return 0

    log(f"The Odds API {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    prefer_ipv4()
    s = requests.Session()
    s.headers["User-Agent"] = "montoglory-odds"

    out, restantes = [], None
    for sport, lg in COMPETENCIAS.items():
        if es_femenino(sport):       # red de seguridad si alguien agrega una clave
            continue
        url = f"{BASE}/sports/{sport}/odds"
        try:
            r = s.get(url, timeout=30, params={
                "apiKey": key, "regions": "eu,uk", "markets": "h2h",
                "oddsFormat": "decimal", "dateFormat": "iso"})
        except requests.RequestException as e:
            log(f"  ! {sport}: {e}")
            continue
        restantes = r.headers.get("x-requests-remaining", restantes)
        if r.status_code == 404:
            continue                      # fuera de temporada, normal
        if r.status_code != 200:
            log(f"  ! {sport}: HTTP {r.status_code} {r.text[:160]}")
            continue
        try:
            juegos = r.json()
        except ValueError as e:
            log(f"  ! {sport}: no es JSON ({e})")
            continue

        casas = set()
        for j in juegos:
            for bk in j.get("bookmakers", []):
                casas.add(bk.get("key"))
        if casas:
            log(f"    casas devueltas: {', '.join(sorted(casas))}")
        n = 0
        for j in juegos:
            home, away = j.get("home_team"), j.get("away_team")
            if es_femenino(home, away):
                continue
            c = consenso(j.get("bookmakers", []), home, away)
            if not c:
                continue
            out.append({"lg": lg, "home": nombre(home), "away": nombre(away),
                        "ko": str(j.get("commence_time", "")).replace("+00:00", "Z"),
                        "pH": round(c["pH"], 4), "pD": round(c["pD"], 4),
                        "pA": round(c["pA"], 4), "b365": c["b365"],
                        "mejor": c["mejor"], "quien": c["quien"], "casas": c["casas"]})
            n += 1
        if n:
            log(f"  {LGN_corto(lg)}: {n} partidos con cuotas")

    if restantes is not None:
        log(f"  consultas restantes este mes: {restantes}")
    if not out:
        log("  sin cuotas UEFA que guardar")
        return 0

    path = DATA / "cuotas_extra.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    log(f"  {len(out)} partidos en cuotas_extra.json "
        f"({sum(1 for r in out if r['b365'])} con precio de bet365)")
    return 0


def LGN_corto(lg: str) -> str:
    from refresh import LGN
    return LGN.get(lg, lg)


if __name__ == "__main__":
    sys.exit(main())
