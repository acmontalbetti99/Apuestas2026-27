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
from datetime import datetime, timedelta, timezone
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


# --------------------------------------------------------------------------- goles

# Mercados de goles por evento. Van por el endpoint de evento y no por el de
# competencia, porque alternate_totals y btts son "additional markets" y ahi no
# salen. Es el unico camino para las lineas de 1.5 y 3.5: el endpoint de
# competencia devuelve la linea principal, que casi siempre es 2.5 y queda en un
# 50/50 que nunca pasa el umbral.
#
# Cuesta mercados x regiones por evento (una region: 2 creditos por partido), asi
# que se pide una sola vez por partido y solo dentro de la ventana en la que el
# partido ya puede generar picks.
MERCADOS_GOLES = "alternate_totals,btts"
REGION_GOLES = "eu"
DIAS_VENTANA = 4          # un dia mas que DIAS_ANTES_TORNEO, para llegar antes
RESERVA = 60              # creditos que no se gastan nunca, para no dejar sin 1X2

# Solo estas lineas: son las que el modelo propio ya usaba y las que la
# liquidacion sabe cerrar con el marcador.
LINEAS = (1.5, 2.5, 3.5)


def _sin_margen_par(o_si: float, o_no: float) -> float | None:
    """Probabilidad del lado 'si' sacandole el margen al par si/no."""
    if not all(isinstance(v, (int, float)) and v > 1 for v in (o_si, o_no)):
        return None
    a, b = 1 / o_si, 1 / o_no
    return a / (a + b)


def goles_de_evento(datos: dict) -> dict:
    """Promedia entre casas la probabilidad de cada linea de goles y de BTTS.

    El promedio de casas esta mejor calibrado que una casa sola, igual que en el
    1X2: una sola casa te mete su margen dentro de la estimacion.
    """
    por_linea: dict[float, list[float]] = {}
    btts: list[float] = []
    for bk in datos.get("bookmakers", []):
        for m in bk.get("markets", []):
            clave = m.get("key")
            if clave in ("alternate_totals", "totals"):
                # Cada punto trae Over y Under de la misma linea; se emparejan.
                pares: dict[float, dict[str, float]] = {}
                for o in m.get("outcomes", []):
                    pt = o.get("point")
                    if pt is None:
                        continue
                    pares.setdefault(float(pt), {})[str(o.get("name", "")).lower()] = o.get("price")
                for linea, d in pares.items():
                    if linea not in LINEAS:
                        continue
                    p = _sin_margen_par(d.get("over"), d.get("under"))
                    if p is not None:
                        por_linea.setdefault(linea, []).append(p)
            elif clave == "btts":
                d = {str(o.get("name", "")).lower(): o.get("price") for o in m.get("outcomes", [])}
                p = _sin_margen_par(d.get("yes"), d.get("no"))
                if p is not None:
                    btts.append(p)

    out: dict[str, float] = {}
    for linea, ps in por_linea.items():
        p = sum(ps) / len(ps)
        out[f"O{linea}"] = round(p, 4)
        out[f"U{linea}"] = round(1 - p, 4)
    if btts:
        p = sum(btts) / len(btts)
        out["BTTS"] = round(p, 4)
        out["NBTTS"] = round(1 - p, 4)
    return out


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
                        "evento": j.get("id"),
                        "pH": round(c["pH"], 4), "pD": round(c["pD"], 4),
                        "pA": round(c["pA"], 4), "b365": c["b365"],
                        "mejor": c["mejor"], "quien": c["quien"], "casas": c["casas"],
                        "sport": sport})
            n += 1
        if n:
            log(f"  {LGN_corto(lg)}: {n} partidos con cuotas")

    if not out:
        log("  sin cuotas UEFA que guardar")
        if restantes is not None:
            log(f"  consultas restantes este mes: {restantes}")
        return 0

    restantes = pedir_goles(s, key, out, restantes)

    if restantes is not None:
        log(f"  consultas restantes este mes: {restantes}")

    path = DATA / "cuotas_extra.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    log(f"  {len(out)} partidos en cuotas_extra.json "
        f"({sum(1 for r in out if r['b365'])} con precio de bet365)")
    return 0


def pedir_goles(s, key: str, filas: list[dict], restantes) -> object:
    """Agrega los mercados de goles a los partidos que estan por jugarse.

    Por que solo a algunos: cada partido cuesta dos creditos y el plan gratuito
    trae 500 al mes, asi que se piden solo los de la ventana en la que el partido
    ya puede generar picks, una vez por partido, y nunca por debajo de la reserva.
    El 1X2 es lo que no puede faltar: si la cuota se acaba, lo primero que se deja
    de pedir son los goles, no al revez.

    Lo que ya estaba guardado se reaprovecha: las lineas de goles se mueven poco y
    volver a pedirlas cada dia es tirar la cuota.
    """
    previo = {}
    path = DATA / "cuotas_extra.json"
    if path.exists():
        try:
            for r in json.loads(path.read_text(encoding="utf-8")) or []:
                if r.get("pGoles") and r.get("evento"):
                    previo[r["evento"]] = r["pGoles"]
        except (OSError, json.JSONDecodeError):
            pass

    ahora = datetime.now(timezone.utc)
    limite = ahora + timedelta(days=DIAS_VENTANA)
    pedidos = reusados = fallados = 0
    sin_cuota = False

    for r in filas:
        ev = r.get("evento")
        if not ev:
            continue
        if ev in previo:
            r["pGoles"] = previo[ev]
            reusados += 1
            continue
        try:
            ko = datetime.fromisoformat(str(r["ko"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if not (ahora < ko <= limite):
            continue
        if restantes is not None and int(restantes) <= RESERVA:
            sin_cuota = True
            continue
        try:
            q = s.get(f"{BASE}/sports/{r['sport']}/events/{ev}/odds", timeout=30, params={
                "apiKey": key, "regions": REGION_GOLES, "markets": MERCADOS_GOLES,
                "oddsFormat": "decimal", "dateFormat": "iso"})
        except requests.RequestException as e:
            log(f"  ! goles de {r['home']} v {r['away']}: {e}")
            fallados += 1
            continue
        restantes = q.headers.get("x-requests-remaining", restantes)
        if q.status_code != 200:
            # 422 = la casa no ofrece esos mercados para este partido. No es un error.
            if q.status_code not in (404, 422):
                log(f"  ! goles de {r['home']} v {r['away']}: HTTP {q.status_code}")
            fallados += 1
            continue
        try:
            g = goles_de_evento(q.json())
        except ValueError:
            fallados += 1
            continue
        pedidos += 1
        if g:
            r["pGoles"] = g

    con = sum(1 for r in filas if r.get("pGoles"))
    log(f"  goles de mercado: {con} partidos con lineas "
        f"({pedidos} pedidos nuevos, {reusados} reaprovechados, {fallados} sin datos)")
    if sin_cuota:
        log(f"  ! cuota mensual cerca del limite (reserva {RESERVA}): "
            f"no se pidieron mas goles, el 1X2 sigue igual")
    return restantes


def LGN_corto(lg: str) -> str:
    from refresh import LGN
    return LGN.get(lg, lg)


if __name__ == "__main__":
    sys.exit(main())
