#!/usr/bin/env python3
"""Resultados en vivo desde LiveScore, para liquidar sin esperar a football-data.

Por que hace falta: football-data.co.uk publica su CSV con horas de retraso y no
cubre Champions. LiveScore devuelve el marcador apenas termina el partido y si
cubre Champions, asi que corriendo esto cada media hora los picks de resultado y
goles quedan liquidados el mismo dia, no al siguiente.

Que NO trae: cornners, tarjetas, remates ni atajadas. El unico endpoint que
responde desde Actions es el de partidos por fecha, y su campo de incidencias no
lleva tarjetas (medido). Esos mercados los sigue liquidando football-data en la
corrida diaria, con su retraso, que para ellos no molesta.

Escribe data/resultados_extra.json, que es el archivo que refresh.py suma a la
base antes de liquidar. No pisa lo que ya estaba: fusiona por partido.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from refresh import DATA, canon, log, prefer_ipv4  # noqa: E402

API = "https://prod-public-api.livescore.com/v1/api/app/date/soccer"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")

# Ligas domesticas: LiveScore pone el pais en Cnm y la liga en Snm.
DOMESTICAS = {
    ("england", "premier league"): "premier",
    ("spain", "laliga"): "laliga",
    ("italy", "serie a"): "seriea",
    ("germany", "bundesliga"): "bundesliga",
}

# Competencias UEFA: ahi Cnm ES la competencia. Se compara Cnm COMPLETO, no por
# substring, porque hay homonimas de otras confederaciones que llegan como
# Cnm="Africa" / Snm="CAF Champions League", y juveniles como Cnm="UEFA Youth
# League". Cualquier etapa sirve (fase liga, eliminatorias, final).
UEFA = {
    "champions league": "ucl", "uefa champions league": "ucl",
    "europa league": "uel", "uefa europa league": "uel",
    "conference league": "uecl", "uefa conference league": "uecl",
    "uefa europa conference league": "uecl", "europa conference league": "uecl",
}
# ni juveniles ni femeninas, que comparten nombre de competencia
EXCLUIR = ("youth", "u19", "u21", "u23", "women", "femenin", "qualification", "qualifying")

# LiveScore nombra algunos equipos distinto que nuestros picks. canon() resuelve
# los acentos y la puntuacion; esto resuelve el resto.
ALIAS = {
    "como 1907": "Como", "inter milano": "Inter", "internazionale": "Inter",
    "athletic club": "Athletic Bilbao", "atletico madrid": "Atletico Madrid",
    "club brugge": "Club Brujas", "racing club de lens": "Lens", "rc lens": "Lens",
    "real betis seville": "Real Betis", "real betis balompie": "Real Betis",
    "feyenoord rotterdam": "Feyenoord", "galatasaray istanbul": "Galatasaray",
    "lille osc": "Lille", "fc shakhtar donetsk": "Shakhtar Donetsk",
    "lask linz": "LASK Linz", "arsenal fc": "Arsenal", "sporting cp": "Sporting CP",
    "bayer leverkusen": "Leverkusen", "borussia dortmund": "Dortmund",
    "borussia monchengladbach": "Monchengladbach", "eintracht frankfurt": "Eintracht Frankfurt",
    "fc koln": "Colonia", "1. fc koln": "Colonia", "hamburger sv": "Hamburgo",
    "rb leipzig": "RB Leipzig", "bayern munich": "Bayern Munich",
    "manchester city": "Manchester City", "manchester united": "Manchester United",
    "nottingham forest": "Nottingham Forest", "tottenham hotspur": "Tottenham",
    "newcastle united": "Newcastle", "wolverhampton wanderers": "Wolves",
    "real sociedad": "Real Sociedad", "celta vigo": "Celta de Vigo",
    "rayo vallecano": "Rayo Vallecano", "deportivo la coruna": "Deportivo",
    "ac milan": "Milan", "as roma": "Roma", "ssc napoli": "Napoli",
    "juventus": "Juventus", "hellas verona": "Hellas Verona",
}

TERMINADO = {"FT", "AET", "AP", "FT_PEN", "Finished"}


def nombre(raw: str) -> str:
    return ALIAS.get(str(raw).strip().lower(), str(raw).strip())


def fetch(dia: datetime, s: requests.Session) -> dict | None:
    url = f"{API}/{dia:%Y%m%d}/0"
    try:
        r = s.get(url, timeout=30)
    except requests.RequestException as e:
        log(f"  ! {url}: {e}")
        return None
    if r.status_code != 200:
        log(f"  ! {url}: HTTP {r.status_code}")
        return None
    try:
        return r.json()
    except ValueError as e:
        log(f"  ! {url}: no es JSON ({e})")
        return None


def cosechar(dias: int = 3) -> list[dict]:
    """Partidos terminados de nuestras competencias en los ultimos `dias`."""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                      "Referer": "https://www.livescore.com/"})
    hoy = datetime.now(timezone.utc)
    out: list[dict] = []
    for n in range(dias):
        dia = hoy - timedelta(days=n)
        d = fetch(dia, s)
        if not d:
            continue
        hallados = 0
        for stg in d.get("Stages", []):
            cnm = str(stg.get("Cnm", "")).lower().strip()
            snm = str(stg.get("Snm", "")).lower().strip()
            if any(w in f"{cnm} {snm}" for w in EXCLUIR):
                continue
            lg = UEFA.get(cnm) or DOMESTICAS.get((cnm, snm))
            if not lg:
                continue
            for e in stg.get("Events", []):
                if e.get("Eps") not in TERMINADO:
                    continue
                t1 = (e.get("T1") or [{}])[0].get("Nm")
                t2 = (e.get("T2") or [{}])[0].get("Nm")
                hg, ag = e.get("Tr1"), e.get("Tr2")
                if not t1 or not t2 or hg is None or ag is None:
                    continue
                ko = e.get("Esd")      # formato YYYYMMDDHHMMSS
                try:
                    kodt = datetime.strptime(str(ko), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    kodt = dia.replace(hour=12, minute=0, second=0, microsecond=0)
                out.append({"lg": lg, "home": nombre(t1), "away": nombre(t2),
                            "ko": kodt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "hg": int(hg), "ag": int(ag)})
                hallados += 1
        log(f"  {dia:%Y-%m-%d}: {hallados} partidos terminados de nuestras ligas")
    return out


def fusionar(nuevos: list[dict]) -> int:
    """Suma los partidos nuevos al archivo sin pisar los que ya estaban."""
    path = DATA / "resultados_extra.json"
    viejos = []
    if path.exists():
        try:
            viejos = json.loads(path.read_text(encoding="utf-8")) or []
        except (OSError, json.JSONDecodeError) as e:
            log(f"  ! {path.name} ilegible ({e}), se reescribe")
            viejos = []

    por_clave = {(canon(r["home"]), canon(r["away"]), str(r.get("ko", ""))[:10]): r
                 for r in viejos if isinstance(r, dict) and "home" in r}
    antes = len(por_clave)
    for r in nuevos:
        por_clave[(canon(r["home"]), canon(r["away"]), r["ko"][:10])] = r

    final = sorted(por_clave.values(), key=lambda r: r.get("ko", ""))
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return len(final) - antes


def avisar_sin_emparejar(resultados: list[dict]) -> None:
    """Un pick vencido sin resultado suele ser un nombre que no coincide: hay que verlo."""
    try:
        picks = json.loads((DATA / "picks.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    tengo = {(canon(r["home"]), canon(r["away"])) for r in resultados}
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    huerfanos = {}
    for p in picks:
        if p.get("estado") != "pendiente" or p.get("ko", "") >= ahora:
            continue
        k = (canon(p["home"]), canon(p["away"]))
        if k not in tengo:
            huerfanos[k] = (p["lg"], p["home"], p["away"], p["ko"])
    if huerfanos:
        log(f"  {len(huerfanos)} partidos ya jugados sin resultado "
            f"(nombre que no coincide, o fuera de la ventana de dias):")
        for lg, h, a, ko in list(huerfanos.values())[:8]:
            log(f"     [{lg}] {h} v {a}  {ko}")


def main() -> int:
    log(f"LiveScore {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    prefer_ipv4()
    res = cosechar()
    if not res:
        log("  sin resultados nuevos")
        return 0
    agregados = fusionar(res)
    log(f"  {len(res)} resultados leidos, {agregados} nuevos en resultados_extra.json")
    avisar_sin_emparejar(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
