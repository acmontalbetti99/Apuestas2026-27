#!/usr/bin/env python3
"""Refresco diario. Corre en GitHub Actions, no en la sesion de Claude.

Por que aca y no en la sesion: el contenedor de Claude sale a internet por un proxy
con lista blanca que rechaza football-data.co.uk. Actions no tiene esa restriccion,
asi que la ingesta vive aca y la sesion solo publica.

Hace cuatro cosas, en orden:

  1. Baja los partidos jugados de las cuatro ligas (temporada actual + anterior).
  2. Liquida los picks pendientes cuyo partido ya termino.
  3. Mide el acierto acumulado y mueve el umbral si el desvio lo justifica.
  4. Baja los proximos partidos con cuotas y genera los picks y las combinadas.

Nunca escribe a medias: si una descarga falla, deja los datos como estaban y sale
con codigo distinto de cero para que el workflow quede en rojo y se vea.

Champions League queda afuera. football-data.co.uk no publica ni cuotas ni
resultados de Champions, y los picks de Champions salen justamente del mercado.
Los que ya estan cargados se liquidan a mano o caducan; ver EXPIRA_UCL.
"""
from __future__ import annotations

import io
import json
import os
import re
import socket
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).parent))
from engine import FAMILY, markets  # noqa: E402
import stats_engine as SE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

BASE_URL = "https://www.football-data.co.uk"
DIVS = {"E0": "premier", "SP1": "laliga", "I1": "seriea", "D1": "bundesliga"}
LGN = {"premier": "Premier League", "laliga": "La Liga", "seriea": "Serie A",
       "bundesliga": "Bundesliga", "ucl": "Champions League",
       "uel": "Europa League", "uecl": "Conference League",
       "afcon": "Copa Africana", "unl": "Nations League",
       "wcq_eu": "Clasificatorias UEFA", "wcq_sa": "Clasificatorias CONMEBOL",
       "copa": "Copa America"}

# La base historica son ligas domesticas de clubes 2018-2025. Nada de esto aplica a
# copas europeas ni a seleccciones: distinta dispersion de nivel, localia que a veces
# no existe, y muchos menos enfrentamientos repetidos. Para estas competencias solo se
# ofrece lo que ES el mercado (1X2 y doble oportunidad), sin pasar por ningun modelo.
SOLO_MERCADO = {"ucl", "uel", "uecl", "afcon", "unl", "wcq_eu", "wcq_sa", "copa"}

# Torneos de selecciones: el pick aparece recien cuando faltan pocos dias, porque la
# cuota se acerca al cierre y es ahi donde mejor predice. Sobre 7.149 partidos medimos
# que la cuota de cierre le gana a cualquier modelo propio; la de apertura es peor.
TORNEOS = {"afcon", "unl", "wcq_eu", "wcq_sa", "copa"}
DIAS_ANTES_TORNEO = 3

UMBRAL_BASE = 0.65
UMBRAL_MAX = 0.80
CEIL_GOAL, CEIL_STAT = 0.90, 0.88
MIN_LIQ_AJUSTE = 60          # por debajo de esto el error de muestra supera al ajuste
EXPIRA_UCL = 3               # dias despues del kickoff que un pick de UCL sin resultado sobrevive
PARLAY_LO, PARLAY_HI = 0.40, 0.52
RATIO_MIN_PARTIDOS = 8
RATIO_VENTANA = 20

# los mercados liquidos: lo demas se puede calcular pero no se puede apostar a precio decente
GOAL_LIQ = {"1": "1X2", "2": "1X2",
            "1X": "Doble oportunidad", "12": "Doble oportunidad", "X2": "Doble oportunidad",
            "O1.5": "Goles", "O2.5": "Goles", "U2.5": "Goles", "U3.5": "Goles",
            "BTTS": "Ambos marcan", "NBTTS": "Ambos marcan"}

# football-data.co.uk -> como lo muestra la app
DISPLAY = {
    "Man City": "Manchester City", "Man United": "Manchester United",
    "Nott'm Forest": "Nottingham Forest", "Newcastle": "Newcastle",
    "Sheffield United": "Sheffield United", "Wolves": "Wolves",
    "Ath Madrid": "Atletico Madrid", "Ath Bilbao": "Athletic Bilbao",
    "Sociedad": "Real Sociedad", "Celta": "Celta de Vigo",
    "Vallecano": "Rayo Vallecano", "Betis": "Real Betis", "La Coruna": "Deportivo",
    "Santander": "Racing Santander", "Espanol": "Espanyol",
    "M'gladbach": "Monchengladbach", "FC Koln": "Colonia", "Hamburg": "Hamburgo",
    "Ein Frankfurt": "Eintracht Frankfurt", "Leverkusen": "Leverkusen",
    "Bayern Munich": "Bayern Munich", "RB Leipzig": "RB Leipzig",
    "Inter": "Inter", "Milan": "Milan", "Verona": "Hellas Verona",
}

STAT_COLS = {"cor": ("HC", "AC"), "yel": ("HY", "AY"),
             "sho": ("HS", "AS"), "sav": ("savH", "savA")}
STAT_WORD = {"cor": "corners", "yel": "amarillas", "sho": "remates", "sav": "atajadas"}

# de mas fiable a menos: media de cierre, Bet365 de cierre, media de apertura, Bet365
ODDS_SETS = [("AvgCH", "AvgCD", "AvgCA"), ("B365CH", "B365CD", "B365CA"),
             ("AvgH", "AvgD", "AvgA"), ("B365H", "B365D", "B365A")]


def log(msg: str) -> None:
    print(msg, flush=True)


def prefer_ipv4() -> None:
    """Resolver IPv4 primero.

    football-data.co.uk publica A (217.160.0.118) y AAAA (2001:8d8:100f:f000::200),
    y el resolver de los runners de Actions devuelve el AAAA primero. El runner no
    tiene ruta IPv6, asi que la conexion muere con 'Network is unreachable' antes de
    salir. curl no se entera porque prueba las dos familias y se queda con la que
    responde; requests toma la primera direccion y se rinde. De ahi que el CSV baje
    desde un navegador y falle en Actions.
    """
    original = socket.getaddrinfo

    def patched(host, port, family=0, type=0, proto=0, flags=0):
        if family == 0:
            try:
                if (v4 := original(host, port, socket.AF_INET, type, proto, flags)):
                    return v4
            except socket.gaierror:
                pass          # sin registro A: que lo intente como pueda
        return original(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched


def session() -> requests.Session:
    """Sesion con reintentos: football-data corta de a ratos y un 503 no debe voltear el dia."""
    s = requests.Session()
    retry = requests.adapters.Retry(total=3, backoff_factor=1.5,
                                    status_forcelist=(429, 500, 502, 503, 504),
                                    allowed_methods=("GET",))
    s.mount("https://", requests.adapters.HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = "montoglory-refresh"
    return s


SESSION: requests.Session | None = None


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def canon(name: str) -> str:
    """Clave de comparacion que aguanta los dos juegos de nombres."""
    return slug(DISPLAY.get(str(name).strip(), str(name).strip()))


def show(name: str) -> str:
    return DISPLAY.get(str(name).strip(), str(name).strip())


def seasons(today: datetime, n: int = 2) -> list[str]:
    """Codigos de temporada de football-data: 2026-27 es '2627'."""
    start = today.year if today.month >= 7 else today.year - 1
    return [f"{str(y)[2:]}{str(y + 1)[2:]}" for y in range(start, start - n, -1)]


def fetch_csv(url: str, timeout: int = 60) -> pd.DataFrame | None:
    global SESSION
    if SESSION is None:
        SESSION = session()
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        log(f"  ! {url}: {e}")
        return None
    if r.status_code != 200:
        log(f"  ! {url}: HTTP {r.status_code}")
        return None
    try:
        df = pd.read_csv(io.BytesIO(r.content), encoding="latin-1",
                         low_memory=False, on_bad_lines="skip")
    except Exception as e:  # noqa: BLE001 - un CSV corrupto no debe tumbar el refresco
        log(f"  ! {url}: no se pudo parsear ({e})")
        return None
    # los CSV vienen con BOM y leidos como latin-1 la primera columna queda 'i»¿Div'
    df.columns = [str(c).replace("﻿", "").replace("ï»¿", "").strip() for c in df.columns]
    return df.dropna(how="all")


def pick_odds(row: pd.Series) -> tuple[float, float, float] | None:
    """Probabilidades 1X2 del mercado, normalizadas para sacarle el margen."""
    for h, d, a in ODDS_SETS:
        if h not in row or d not in row or a not in row:
            continue
        try:
            oh, od, oa = float(row[h]), float(row[d]), float(row[a])
        except (TypeError, ValueError):
            continue
        if not all(np.isfinite([oh, od, oa])) or min(oh, od, oa) <= 1.0:
            continue
        inv = np.array([1 / oh, 1 / od, 1 / oa])
        return tuple(float(x) for x in inv / inv.sum())
    return None


# --------------------------------------------------------------------------- resultados

def load_results(today: datetime) -> pd.DataFrame | None:
    frames = []
    for season in seasons(today):
        for div, lg in DIVS.items():
            df = fetch_csv(f"{BASE_URL}/mmz4281/{season}/{div}.csv")
            if df is None or "FTHG" not in df:
                continue
            df = df.dropna(subset=["FTHG", "FTAG", "HomeTeam", "AwayTeam"]).copy()
            df["lg"] = lg
            frames.append(df)
            log(f"  {div} {season}: {len(df)} partidos")
    if not frames:
        return None
    D = pd.concat(frames, ignore_index=True)
    D["fecha"] = pd.to_datetime(D["Date"], dayfirst=True, errors="coerce")
    D = D.dropna(subset=["fecha"])
    # una division o temporada puede no traer la columna de estadisticas: se crea vacia
    # para que el resto siga funcionando y esos mercados queden sin liquidar, no mal liquidados
    for col in ("FTHG", "FTAG", "HC", "AC", "HY", "AY", "HS", "AS", "HST", "AST"):
        D[col] = pd.to_numeric(D[col], errors="coerce") if col in D.columns else np.nan
    # atajadas del arquero local = remates al arco del visitante menos sus goles
    D["savH"] = (D["AST"] - D["FTAG"]).clip(lower=0)
    D["savA"] = (D["HST"] - D["FTHG"]).clip(lower=0)
    D["kH"], D["kA"] = D["HomeTeam"].map(canon), D["AwayTeam"].map(canon)

    extra = load_resultados_extra()
    if extra is not None:
        D = pd.concat([D, extra], ignore_index=True)
        log(f"  resultados_extra.json: {len(extra)} partidos")
    return D.sort_values("fecha")


def load_resultados_extra() -> pd.DataFrame | None:
    """Resultados inyectados a mano: Champions, que football-data no publica, y
    cualquier partido que una fuente en vivo quiera liquidar antes de que
    football-data lo publique (su CSV tarda horas en aparecer).

    Los alimenta una sesion de Claude o, mas adelante, una API con clave. El
    formato es el minimo que necesita la liquidacion:
      [{"home","away","ko","hg","ag", "lg" opcional (default ucl),
        y opcionalmente "hc","ac","hy","ay","hs","as","hst","ast"}]
    Los nombres tienen que ser los mismos que usan los picks; canon() aguanta las
    variantes habituales, pero no un nombre inventado.
    """
    path = DATA / "resultados_extra.json"
    if not path.exists():
        return None
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log(f"  ! resultados_extra.json: {e} - se ignora")
        return None
    if not isinstance(rows, list) or not rows:
        return None

    out = []
    for r in rows:
        try:
            out.append({
                "Div": "UCL", "lg": r.get("lg", "ucl"),
                "HomeTeam": r["home"], "AwayTeam": r["away"],
                "fecha": pd.to_datetime(r["ko"], utc=True).tz_localize(None),
                "FTHG": float(r["hg"]), "FTAG": float(r["ag"]),
                "HC": r.get("hc"), "AC": r.get("ac"),
                "HY": r.get("hy"), "AY": r.get("ay"),
                "HS": r.get("hs"), "AS": r.get("as"),
                "HST": r.get("hst"), "AST": r.get("ast"),
                "kH": canon(r["home"]), "kA": canon(r["away"]),
            })
        except (KeyError, TypeError, ValueError) as e:
            log(f"  ! resultados_extra.json: fila invalida {r!r}: {e}")
    if not out:
        return None
    D = pd.DataFrame(out)
    for col in ("HC", "AC", "HY", "AY", "HS", "AS", "HST", "AST"):
        D[col] = pd.to_numeric(D[col], errors="coerce")
    D["savH"] = (D["AST"] - D["FTAG"]).clip(lower=0)
    D["savA"] = (D["HST"] - D["FTHG"]).clip(lower=0)
    return D


# --------------------------------------------------------------------------- liquidacion

def _ou(key: str) -> tuple[str, float] | None:
    m = re.fullmatch(r"([OU])(\d+\.5)", key)
    return (m.group(1), float(m.group(2))) if m else None


def settle_key(key: str, r: pd.Series) -> bool | None:
    """True si el pick entro, False si fallo, None si no se puede saber."""
    hg, ag = int(r["FTHG"]), int(r["FTAG"])
    tot = hg + ag

    if key == "1": return hg > ag
    if key == "X": return hg == ag
    if key == "2": return ag > hg
    if key == "1X": return hg >= ag
    if key == "12": return hg != ag
    if key == "X2": return ag >= hg
    if key == "BTTS": return hg > 0 and ag > 0
    if key == "NBTTS": return hg == 0 or ag == 0
    if key == "CS_H": return ag == 0
    if key == "CS_A": return hg == 0

    if (ou := _ou(key)):
        side, line = ou
        return tot > line if side == "O" else tot < line

    m = re.fullmatch(r"([HA])([OU])(\d+\.5)", key)
    if m:
        who, side, line = m.group(1), m.group(2), float(m.group(3))
        v = hg if who == "H" else ag
        return v > line if side == "O" else v < line

    m = re.fullmatch(r"(cor|yel|sho|sav)_([mha])_([ou])(\d+\.5)", key)
    if m:
        stat, scope, side, line = m.group(1), m.group(2), m.group(3), float(m.group(4))
        ch, ca = STAT_COLS[stat]
        vh, va = r.get(ch), r.get(ca)
        if pd.isna(vh) or pd.isna(va):
            return None
        v = float(vh) + float(va) if scope == "m" else (float(vh) if scope == "h" else float(va))
        return v > line if side == "o" else v < line

    return None


def settle_label(pick: dict, r: pd.Series) -> str:
    hg, ag = int(r["FTHG"]), int(r["FTAG"])
    base = f"{hg}-{ag}"
    m = re.fullmatch(r"(cor|yel|sho|sav)_([mha])_[ou]\d+\.5", pick["key"])
    if not m:
        return base
    stat, scope = m.group(1), m.group(2)
    ch, ca = STAT_COLS[stat]
    vh, va = r.get(ch), r.get(ca)
    if pd.isna(vh) or pd.isna(va):
        return base
    v = float(vh) + float(va) if scope == "m" else (float(vh) if scope == "h" else float(va))
    return f"{base} · {v:g} {STAT_WORD[stat]}"


def settle(picks: list[dict], D: pd.DataFrame, today: datetime) -> dict:
    """Liquida en sitio. Devuelve el conteo de lo que paso."""
    idx: dict[tuple[str, str], list[pd.Series]] = {}
    for _, r in D.iterrows():
        idx.setdefault((r["kH"], r["kA"]), []).append(r)

    n = {"ganado": 0, "perdido": 0, "sin_datos": 0, "caducado": 0, "espera": 0}
    vivos = []
    for p in picks:
        if p.get("estado") != "pendiente":
            vivos.append(p)
            continue
        ko = pd.to_datetime(p["ko"], utc=True, errors="coerce")
        if pd.isna(ko) or ko > today:
            vivos.append(p)
            n["espera"] += 1
            continue

        cands = idx.get((canon(p["home"]), canon(p["away"])), [])
        # el mismo cruce se repite entre temporadas: el partido mas cercano al kickoff
        gap = lambda x: abs((x["fecha"].tz_localize("UTC") - ko).total_seconds())
        r = min(cands, key=gap, default=None)
        if r is not None and gap(r) > 5 * 86400:
            r = None

        if r is None:
            if (today - ko).days > EXPIRA_UCL:
                n["caducado"] += 1          # se descarta: no contamina el acierto
                continue
            vivos.append(p)
            n["espera"] += 1
            continue

        hit = settle_key(p["key"], r)
        if hit is None:
            n["sin_datos"] += 1
            vivos.append(p)
            continue
        p["estado"] = "ganado" if hit else "perdido"
        p["resultado"] = settle_label(p, r)
        n["ganado" if hit else "perdido"] += 1
        vivos.append(p)

    picks[:] = vivos
    return n


def settle_parlays(parlays: list[dict], picks: list[dict]) -> None:
    by_id = {p["id"]: p for p in picks}
    for t in parlays:
        if t.get("estado") != "pendiente":
            continue
        estados = []
        for leg in t.get("legs", []):
            pid = leg.get("id") or pick_id(leg.get("home", ""), leg.get("away", ""), leg.get("key", ""))
            estados.append(by_id.get(pid, {}).get("estado", "pendiente"))
        if "perdido" in estados:
            t["estado"] = "perdido"
        elif estados and all(e == "ganado" for e in estados):
            t["estado"] = "ganado"


# --------------------------------------------------------------------------- calibracion

def calibrate(picks: list[dict]) -> dict:
    done = [p for p in picks if p.get("estado") in ("ganado", "perdido")]
    n = len(done)
    out = {"fecha": datetime.now(timezone.utc).date().isoformat(), "nLiquidados": n,
           "predicho": None, "real": None, "desvio": None, "umbralVigente": UMBRAL_BASE,
           "referencia": {"resultadoYGoles": {"predicho": 0.798, "real": 0.805, "n": 74391},
                          "estadisticas": {"predicho": 0.763, "real": 0.759, "n": 213359}}}
    if not n:
        return out
    pred = sum(p["p"] for p in done) / n
    real = sum(p["estado"] == "ganado" for p in done) / n
    out.update(predicho=round(pred, 4), real=round(real, 4), desvio=round(real - pred, 4))
    if n >= MIN_LIQ_AJUSTE and real < pred:
        # el modelo viene inflado: se le descuenta el desvio al umbral
        out["umbralVigente"] = round(min(UMBRAL_BASE + (pred - real), UMBRAL_MAX), 4)
    por_grupo = {}
    for g in ("resultado", "goles", "estadisticas"):
        s = [p for p in done if p.get("grupo") == g]
        if s:
            por_grupo[g] = {"n": len(s),
                            "predicho": round(sum(p["p"] for p in s) / len(s), 4),
                            "real": round(sum(p["estado"] == "ganado" for p in s) / len(s), 4)}
    out["porGrupo"] = por_grupo
    return out


# --------------------------------------------------------------------------- generacion

def team_ratios(D: pd.DataFrame) -> dict:
    """Ratio de cada equipo contra la media de su liga, por lado. Entra contraido a la mitad."""
    lgmean = {}
    for lg in DIVS.values():
        g = D[D.lg == lg]
        for s, (ch, ca) in STAT_COLS.items():
            lgmean[(lg, s, "H")] = g[ch].mean()
            lgmean[(lg, s, "A")] = g[ca].mean()

    out: dict[tuple[str, str, str], dict] = {}
    for lg in DIVS.values():
        g = D[D.lg == lg]
        for side, col in (("H", "kH"), ("A", "kA")):
            for team, sub in g.groupby(col):
                sub = sub.tail(RATIO_VENTANA)
                if len(sub) < RATIO_MIN_PARTIDOS:
                    continue
                d = {}
                for s, (ch, ca) in STAT_COLS.items():
                    base = lgmean[(lg, s, side)]
                    v = sub[ch if side == "H" else ca].mean()
                    if base and np.isfinite(base) and np.isfinite(v) and base > 0:
                        d[s] = float(v / base)
                if d:
                    out[(lg, team, side)] = d
    return out


def load_fixtures(today: datetime) -> list[dict] | None:
    df = fetch_csv(f"{BASE_URL}/fixtures.csv")
    if df is None or "HomeTeam" not in df:
        return None
    df = df[df["Div"].isin(DIVS)].copy()
    df["fecha"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["fecha", "HomeTeam", "AwayTeam"])

    fx = []
    for _, r in df.iterrows():
        probs = pick_odds(r)
        if probs is None:
            continue
        hora = str(r.get("Time") or "15:00").strip()
        try:
            hh, mm = (int(x) for x in hora.split(":")[:2])
        except ValueError:
            hh, mm = 15, 0
        ko = r["fecha"].to_pydatetime().replace(hour=hh, minute=mm, tzinfo=timezone.utc)
        if ko < today - timedelta(hours=2):
            continue
        fx.append({"lg": DIVS[r["Div"]], "ko": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "home": show(r["HomeTeam"]), "away": show(r["AwayTeam"]),
                   "kH": canon(r["HomeTeam"]), "kA": canon(r["AwayTeam"]),
                   "pH": probs[0], "pD": probs[1], "pA": probs[2],
                   "b365": cuotas_b365(r)})

    fx += load_cuotas_extra(today)
    return fx


def load_cuotas_extra(today: datetime) -> list[dict]:
    """Partidos con cuotas que football-data no publica (competencias UEFA).

    Lo escribe scripts/odds_api.py cuando hay ODDS_API_KEY. Mismo formato que
    load_fixtures, asi que build_picks no distingue de donde vino cada partido.
    """
    path = DATA / "cuotas_extra.json"
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8")) or []
    except (OSError, json.JSONDecodeError) as e:
        log(f"  ! cuotas_extra.json: {e} - se ignora")
        return []
    out = []
    for r in rows:
        try:
            if r["lg"] not in LGN:
                continue
            ko = pd.to_datetime(r["ko"], utc=True)
            if ko < today - timedelta(hours=2):
                continue
            s = float(r["pH"]) + float(r["pD"]) + float(r["pA"])
            if not (0.95 < s < 1.05):
                log(f"  ! cuotas_extra: probabilidades que no suman 1 en {r.get('home')} "
                    f"v {r.get('away')} ({s:.3f}), se saltea")
                continue
            out.append({"lg": r["lg"], "ko": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "home": r["home"], "away": r["away"],
                        "kH": canon(r["home"]), "kA": canon(r["away"]),
                        "pH": float(r["pH"])/s, "pD": float(r["pD"])/s, "pA": float(r["pA"])/s,
                        "b365": r.get("b365") or {}})
        except (KeyError, TypeError, ValueError) as e:
            log(f"  ! cuotas_extra: fila invalida {r!r}: {e}")
    if out:
        log(f"  cuotas_extra.json: {len(out)} partidos")
    return out


def cuotas_b365(r: pd.Series) -> dict:
    """Lo que paga bet365, para comparar contra la cuota justa.

    Ojo con la distincion: la PROBABILIDAD sale del promedio de casas, que esta mejor
    calibrado; una casa sola te mete su margen dentro de la estimacion. Bet365 entra
    solo como el precio contra el cual se compara.

    El CSV trae su 1X2 y su linea de 2.5 goles. La doble oportunidad no la publica, asi
    que se arma con la combinacion sin arbitraje de su propio 1X2 (1/(1/o1 + 1/ox)), que
    es como la cotizan las casas; queda marcada como estimada.
    """
    def num(col):
        try:
            v = float(r.get(col))
            return v if np.isfinite(v) and v > 1.0 else None
        except (TypeError, ValueError):
            return None

    o1, ox, o2 = num("B365H"), num("B365D"), num("B365A")
    out: dict[str, float] = {}
    if o1: out["1"] = round(o1, 2)
    if ox: out["X"] = round(ox, 2)
    if o2: out["2"] = round(o2, 2)
    comb = lambda a, b: round(1 / (1 / a + 1 / b), 2)
    if o1 and ox: out["1X"] = comb(o1, ox)
    if o1 and o2: out["12"] = comb(o1, o2)
    if ox and o2: out["X2"] = comb(ox, o2)
    for col, k in (("B365>2.5", "O2.5"), ("B365<2.5", "U2.5")):
        if (v := num(col)):
            out[k] = round(v, 2)
    # las derivadas van marcadas para no hacerlas pasar por precio publicado
    out["_estimadas"] = [k for k in ("1X", "12", "X2") if k in out]
    return out


def pick_id(home: str, away: str, key: str) -> str:
    return f"{slug(home)}__{slug(away)}__{slug(key)}"


def build_picks(fx: list[dict], ratios: dict, umbral: float,
                ahora: datetime | None = None) -> list[dict]:
    ahora = ahora or datetime.now(timezone.utc)
    todas, diferidos = [], 0
    for f in fx:
        lg, pH, pD, pA = f["lg"], f["pH"], f["pD"], f["pA"]

        if lg in TORNEOS:
            ko = pd.to_datetime(f["ko"], utc=True, errors="coerce")
            if pd.isna(ko) or (ko - ahora) > timedelta(days=DIAS_ANTES_TORNEO):
                diferidos += 1
                continue
        base = {"lg": lg, "liga": LGN[lg], "ko": f["ko"], "home": f["home"], "away": f["away"],
                "b365": f.get("b365") or {}}

        if lg in SOLO_MERCADO:
            # Sin base historica para goles ni estadisticas: solo 1X2 y doble oportunidad,
            # que son el mercado mismo y no pasan por ningun modelo.
            for k, lab, p in (("1", "Gana local", pH), ("2", "Gana visitante", pA),
                              ("1X", "Local o empate", pH + pD),
                              ("12", "Local o visitante (no empate)", pH + pA),
                              ("X2", "Empate o visitante", pD + pA)):
                if umbral < p <= CEIL_GOAL:
                    todas.append({**base, "key": k, "fam": "res",
                                  "cat": "1X2" if k in ("1", "2") else "Doble oportunidad",
                                  "label": lab, "p": round(float(p), 4),
                                  "cuota": round(1 / float(p), 2), "grupo": "resultado"})
            continue

        mk, lh, la = markets(lg, pH, pD, pA)
        for k, (lab, p) in mk.items():
            if k in GOAL_LIQ and umbral < p <= CEIL_GOAL:
                fam = FAMILY[k]
                todas.append({**base, "key": k, "fam": fam, "cat": GOAL_LIQ[k], "label": lab,
                              "p": round(float(p), 4), "cuota": round(1 / float(p), 2),
                              "grupo": "resultado" if fam == "res" else "goles"})

        rH = ratios.get((lg, f["kH"], "H"), {})
        rA = ratios.get((lg, f["kA"], "A"), {})
        for k, (lab, p, fam, cat) in SE.stat_markets(lg, pH - pA, f["home"], f["away"], rH, rA).items():
            if umbral < p <= CEIL_STAT:
                todas.append({**base, "key": k, "fam": fam, "cat": cat, "label": lab,
                              "p": round(float(p), 4), "cuota": round(1 / float(p), 2),
                              "grupo": "estadisticas"})

    # a lo sumo un pick por partido y por familia de mercado, para que no se solapen
    todas.sort(key=lambda s: -s["p"])
    mejor: dict[tuple, dict] = {}
    for s in todas:
        k = ((s["home"], s["away"]), s["grupo"])
        mejor.setdefault(k, s)

    if diferidos:
        log(f"  {diferidos} partidos de torneo todavia lejos "
            f"(entran a {DIAS_ANTES_TORNEO} dias del arranque)")

    picks = []
    for s in sorted(mejor.values(), key=lambda s: (s["ko"], -s["p"])):
        b = s.get("b365") or {}
        casa = b.get(s["key"])
        pick = {"id": pick_id(s["home"], s["away"], s["key"]),
                "lg": s["lg"], "home": s["home"], "away": s["away"], "ko": s["ko"],
                "key": s["key"], "label": s["label"], "cat": s["cat"], "grupo": s["grupo"],
                "p": s["p"], "cuota": s["cuota"],
                "estado": "pendiente", "resultado": None}
        if casa:
            pick["casa"] = casa
            # valor esperado por unidad apostada: positivo = la casa paga de mas
            pick["valor"] = round(s["p"] * casa - 1, 4)
            if s["key"] in (b.get("_estimadas") or []):
                pick["casaEst"] = True
        picks.append(pick)
    return picks


def build_parlays(picks: list[dict], hoy: str) -> list[dict]:
    """Combinadas entre 40% y 52% conjunto, una sola pata por partido y sin equipos repetidos."""
    abiertos = [p for p in picks if p["estado"] == "pendiente"]
    salida = []
    for n in (2, 3, 4, 5):
        objetivo = PARLAY_LO ** (1 / n)      # probabilidad por pata que lleva al rango
        pool = sorted(abiertos, key=lambda p: abs(p["p"] - objetivo))[:14]
        mejor = None
        for combo in combinations(pool, n):
            equipos = [t for p in combo for t in (p["home"], p["away"])]
            if len(set(equipos)) != 2 * n:
                continue
            prob = float(np.prod([p["p"] for p in combo]))
            if not (PARLAY_LO <= prob <= PARLAY_HI):
                continue
            if mejor is None or prob > mejor[0]:
                mejor = (prob, combo)
        if mejor is None:
            continue
        prob, combo = mejor
        salida.append({
            "id": f"{hoy}__{n}patas", "jornada": hoy, "patas": n,
            "prob": round(prob, 4), "cuota": round(1 / prob, 2),
            "legs": [{"id": p["id"], "liga": LGN[p["lg"]], "lg": p["lg"],
                      "home": p["home"], "away": p["away"], "label": p["label"],
                      "p": p["p"], "ko": p["ko"], "key": p["key"], "cuota": p["cuota"]}
                     for p in combo],
            "estado": "pendiente"})
    return salida


# --------------------------------------------------------------------------- io

def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log(f"  ! {path.name}: {e} - arranco de cero")
        return default


def write_json(path: Path, obj) -> None:
    """Escritura atomica: un Actions cortado a la mitad no deja un JSON roto."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    today = datetime.now(timezone.utc)
    # Las corridas frecuentes solo liquidan: bajar fixtures y regenerar picks cada media
    # hora no aporta nada (la ventana de fixtures.csv cambia una vez al dia) y haria
    # bailar las recomendaciones a lo largo del dia.
    solo_liquidar = "--solo-liquidar" in sys.argv
    log(f"Refresco {today:%Y-%m-%d %H:%M} UTC{' (solo liquidar)' if solo_liquidar else ''}")
    prefer_ipv4()

    log("Bajando resultados...")
    D = load_results(today)
    if D is None or D.empty:
        log("ABORTO: no pude bajar ningun resultado. Los datos quedan como estaban.")
        return 1
    log(f"  {len(D)} partidos en base")

    picks = read_json(DATA / "picks.json", [])
    parlays = read_json(DATA / "parlays.json", [])
    if not isinstance(picks, list):
        log("ABORTO: picks.json no es una lista.")
        return 1

    log("Liquidando...")
    n = settle(picks, D, today)
    settle_parlays(parlays, picks)
    log(f"  {n['ganado']} acertados · {n['perdido']} fallados · {n['espera']} en espera"
        f" · {n['sin_datos']} sin estadisticas · {n['caducado']} caducados")

    calib = calibrate(picks)
    log(f"  acierto {calib['real']} vs predicho {calib['predicho']}"
        f" sobre {calib['nLiquidados']} · umbral {calib['umbralVigente']}")

    if solo_liquidar:
        fx, nuevos = None, []
    else:
        log("Bajando proximos partidos...")
        fx = load_fixtures(today)
    if solo_liquidar:
        pass
    elif fx is None:
        log("  ! sin fixtures: dejo los picks abiertos como estaban")
        nuevos = [p for p in picks if p["estado"] == "pendiente"]
    else:
        log(f"  {len(fx)} partidos con cuotas")
        nuevos = build_picks(fx, team_ratios(D), calib["umbralVigente"])
        log(f"  {len(nuevos)} picks sobre el {100 * calib['umbralVigente']:.0f}%")

    # El refresco es aditivo, nunca destructivo. fixtures.csv solo publica una ventana
    # de uno o dos dias, asi que si se reconstruyera la lista desde cero un dia flaco
    # se llevaria puestos los picks del fin de semana que ya estaban bien calculados.
    # Precedencia: liquidado > recien generado (prob fresca) > pendiente aun por jugar.
    final: dict[str, dict] = {}
    for p in picks:
        if p["estado"] != "pendiente":
            final[p["id"]] = p

    # Un partido que se vuelve a cotizar se reemplaza completo: las cuotas frescas
    # mandan, y asi se respeta la regla de un solo pick por partido y por grupo, que
    # se rompia si se mezclaban los viejos con los nuevos del mismo partido.
    recotizados = {(p["home"], p["away"]) for p in nuevos}
    for p in nuevos:
        final.setdefault(p["id"], p)

    # El resto de los pendientes se arrastra tal cual. Que un pick siga vivo ya lo
    # decidio settle(), que es quien conoce la regla de caducidad; volver a filtrar
    # por fecha aca borraba los que estaban pasado el kickoff esperando resultado.
    conservados = 0
    for p in picks:
        if p["estado"] != "pendiente" or p["id"] in final:
            continue
        if (p["home"], p["away"]) in recotizados:
            continue
        final[p["id"]] = p
        conservados += 1
    if conservados:
        log(f"  {conservados} picks pendientes de dias anteriores se mantienen")
    final = sorted(final.values(), key=lambda p: (p["ko"], -p["p"]))

    hoy = today.date().isoformat()
    if solo_liquidar:
        parlays_final = parlays          # ya re-liquidadas arriba, no se rearman
    else:
        abiertas = build_parlays(final, hoy) if fx is not None else []
        cerradas = [t for t in parlays if t.get("estado") != "pendiente"]
        cerradas_ids = {t["id"] for t in cerradas}
        parlays_final = cerradas + [t for t in abiertas if t["id"] not in cerradas_ids]
        log(f"  {len(abiertas)} combinadas armadas")

    write_json(DATA / "picks.json", final)
    write_json(DATA / "parlays.json", parlays_final)
    write_json(DATA / "calibracion.json", calib)
    n_liq = sum(p["estado"] != "pendiente" for p in final)
    log(f"Listo: {len(final)} picks ({n_liq} liquidados), {len(parlays_final)} combinadas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
