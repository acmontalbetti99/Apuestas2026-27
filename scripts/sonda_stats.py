#!/usr/bin/env python3
"""Sonda: existe alguna forma de liquidar cornners y tarjetas de un partido de
torneo?

football-data.co.uk solo publica las cuatro ligas domesticas, asi que para
Champions, Europa League, Nations League o AFCON no hay de donde sacar cornners,
tarjetas, remates ni atajadas. Antes de ofrecer un pick de esos mercados en esas
competencias hay que saber si se puede CERRAR: un pick que nunca se liquida es
peor que no tenerlo, porque queda para siempre esperando resultado y no cuenta en
la precision.

Esto no se puede probar desde el contenedor de Claude, que tiene la salida
restringida a los registros de paquetes y a GitHub. Corre en Actions, imprime y no
escribe nada.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

CAB = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.livescore.com/",
    "Accept": "application/json, text/plain, */*",
}
BASE = "https://prod-public-api.livescore.com/v1/api/app"
PALABRAS = ("corner", "cornerkick", "yellow", "card", "shot", "shots", "save",
            "possession", "foul")


def pedir(url: str):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=CAB), timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:                                    # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def buscar(obj, camino="") -> list[str]:
    """Donde aparece una palabra de estadistica, con el valor que tiene al lado."""
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{camino}.{k}"
            if any(w in str(k).lower() for w in PALABRAS):
                hits.append(f"{p} = {json.dumps(v, ensure_ascii=False)[:120]}")
            hits += buscar(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:40]):
            hits += buscar(v, f"{camino}[{i}]")
    elif isinstance(obj, str) and any(w == obj.lower() for w in PALABRAS):
        hits.append(f"{camino} == {obj!r}")
    return hits


def main() -> int:
    ayer = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")
    hoy = datetime.now(timezone.utc).strftime("%Y%m%d")
    elegido = None
    for d in (hoy, ayer):
        st, datos = pedir(f"{BASE}/date/soccer/{d}/0")
        print(f"feed de {d}: HTTP {st}")
        if st != 200 or not isinstance(datos, dict):
            continue
        for stg in datos.get("Stages", []):
            cnm = str(stg.get("Cnm", "")).lower()
            if not any(w in cnm for w in ("champions", "europa", "conference",
                                          "nations", "world cup", "africa")):
                continue
            for e in stg.get("Events", []):
                if str(e.get("Eps", "")).upper() in ("FT", "AET", "AP"):
                    elegido = (stg.get("Cnm"), e)
                    break
            if elegido:
                break
        if elegido:
            break

    if not elegido:
        print("no se encontro un partido de torneo terminado en estos dos dias; "
              "la sonda no concluye nada")
        return 0

    comp, ev = elegido
    eid = ev.get("Eid") or ev.get("Esid") or ev.get("Id")
    h = (ev.get("T1") or [{}])[0].get("Nm")
    a = (ev.get("T2") or [{}])[0].get("Nm")
    print(f"\npartido elegido: [{comp}] {h} {ev.get('Tr1')}-{ev.get('Tr2')} {a}  Eid={eid}")
    print(f"claves del evento en el feed por fecha: {sorted(ev.keys())}")
    hits = buscar(ev)
    print(f"  estadisticas en el feed por fecha: {hits or 'ninguna'}")

    rutas = [
        f"/match/soccer/{eid}/0",
        f"/match-details/soccer/{eid}/0",
        f"/matchdetails/soccer/{eid}/0",
        f"/stats/soccer/{eid}/0",
        f"/match/soccer/{eid}/stats/0",
        f"/event/soccer/{eid}/0",
    ]
    for ruta in rutas:
        st, datos = pedir(f"{BASE}{ruta}")
        if st != 200:
            print(f"\n{ruta}: HTTP {st}")
            continue
        if not isinstance(datos, (dict, list)):
            print(f"\n{ruta}: HTTP 200 pero {datos}")
            continue
        hits = buscar(datos)
        print(f"\n{ruta}: HTTP 200, {len(json.dumps(datos))} bytes")
        print(f"  claves: {sorted(datos.keys())[:25] if isinstance(datos, dict) else 'lista'}")
        if hits:
            print(f"  SI HAY ESTADISTICAS ({len(hits)}):")
            for x in hits[:30]:
                print(f"    {x}")
        else:
            print("  sin cornners ni tarjetas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
