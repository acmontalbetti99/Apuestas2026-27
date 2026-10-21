#!/usr/bin/env python3
"""Auditoria diaria. Mide, no opina.

La idea: todo lo que puede salir mal en esta app sale mal en silencio. Un nombre de
equipo que no coincide deja picks sin liquidar para siempre; una combinada puede
quedar apuntando a picks que ya no existen; el modelo puede irse de calibracion de
a poco. Nada de eso tira un error. Por eso se mide a diario y se deja escrito.

Cada hallazgo lleva severidad:
  alta   -> algo esta roto y hay que arreglarlo; la corrida termina en rojo
  media  -> degrada la calidad pero la app funciona
  baja   -> vale la pena mirarlo

Escribe data/auditoria.json (historico, una entrada por dia) y AUDITORIA.md
(el ultimo informe, legible). Sale distinto de cero si hay algo de severidad alta.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from refresh import (CEIL_GOAL, CEIL_STAT, DATA, LGN, MIN_LIQ_AJUSTE, PARLAY_HI,
                     PARLAY_LO, ROOT, SOLO_MERCADO, UMBRAL_BASE, canon, log)

SITIO = "https://montoglory.vercel.app"
VENCIDO_HORAS = 12      # un pick pasado el kickoff deberia liquidarse antes de esto


class Informe:
    def __init__(self) -> None:
        self.hallazgos: list[dict] = []
        self.metricas: dict = {}

    def add(self, sev: str, area: str, msg: str, detalle=None) -> None:
        self.hallazgos.append({"severidad": sev, "area": area, "mensaje": msg,
                               "detalle": detalle})

    def por_sev(self, sev: str) -> list[dict]:
        return [h for h in self.hallazgos if h["severidad"] == sev]


def leer(nombre: str, default):
    try:
        return json.loads((DATA / nombre).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# --------------------------------------------------------------------- integridad

def integridad(inf: Informe, picks: list[dict], parlays: list[dict]) -> None:
    ids = [p.get("id") for p in picks]
    dup = {k: v for k, v in Counter(ids).items() if v > 1}
    if dup:
        inf.add("alta", "integridad", f"{len(dup)} ids de pick duplicados", list(dup)[:10])

    estados = Counter(p.get("estado") for p in picks)
    raros = {k: v for k, v in estados.items() if k not in ("pendiente", "ganado", "perdido")}
    if raros:
        inf.add("alta", "integridad", "estados desconocidos", raros)

    pend = [p for p in picks if p.get("estado") == "pendiente"]
    claves = Counter((p.get("home"), p.get("away"), p.get("grupo")) for p in pend)
    solapados = {f"{h} v {a} [{g}]": n for (h, a, g), n in claves.items() if n > 1}
    if solapados:
        inf.add("alta", "integridad",
                f"{len(solapados)} partidos con mas de un pick en el mismo grupo",
                list(solapados)[:10])

    fuera, incoherentes = [], []
    for p in picks:
        pr, cu = p.get("p"), p.get("cuota")
        if not isinstance(pr, (int, float)) or not 0 < pr < 1:
            fuera.append(p.get("id")); continue
        techo = CEIL_STAT if p.get("grupo") == "estadisticas" else CEIL_GOAL
        if not (UMBRAL_BASE - 1e-9 < pr <= techo + 1e-9):
            fuera.append(f"{p.get('id')} p={pr}")
        if isinstance(cu, (int, float)) and abs(cu - 1 / pr) > 0.02:
            incoherentes.append(f"{p.get('id')} p={pr} cuota={cu}")
    if fuera:
        inf.add("media", "integridad", f"{len(fuera)} picks con probabilidad fuera de rango",
                fuera[:10])
    if incoherentes:
        inf.add("alta", "integridad", f"{len(incoherentes)} picks donde la cuota no es 1/p",
                incoherentes[:10])

    por_id = {p.get("id"): p for p in picks}
    for t in parlays:
        legs = t.get("legs") or []
        if not legs:
            inf.add("alta", "combinadas", f"{t.get('id')} sin patas"); continue
        equipos = [x for l in legs for x in (l.get("home"), l.get("away"))]
        if len(set(equipos)) != len(equipos):
            inf.add("alta", "combinadas", f"{t.get('id')} repite un equipo")
        prod = 1.0
        for l in legs:
            prod *= float(l.get("p") or 0)
        if abs(prod - float(t.get("prob") or 0)) > 0.005:
            inf.add("alta", "combinadas",
                    f"{t.get('id')} prob {t.get('prob')} no es el producto ({prod:.4f})")
        if t.get("estado") == "pendiente" and not (PARLAY_LO - 0.01 <= prod <= PARLAY_HI + 0.01):
            inf.add("media", "combinadas",
                    f"{t.get('id')} fuera de la banda objetivo: {prod:.3f}")
        huerf = [l.get("id") for l in legs if l.get("id") and l.get("id") not in por_id]
        if huerf:
            inf.add("media", "combinadas",
                    f"{t.get('id')} apunta a picks que ya no existen", huerf[:5])


# --------------------------------------------------------------------- liquidacion

def liquidacion(inf: Informe, picks: list[dict], ahora: datetime) -> None:
    limite = ahora - timedelta(hours=VENCIDO_HORAS)
    atrasados = defaultdict(list)
    for p in picks:
        if p.get("estado") != "pendiente":
            continue
        try:
            ko = datetime.fromisoformat(str(p["ko"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            inf.add("media", "liquidacion", f"{p.get('id')} con fecha ilegible: {p.get('ko')!r}")
            continue
        if ko < limite:
            atrasados[p.get("lg")].append((p.get("home"), p.get("away"), p["ko"]))
    inf.metricas["sinLiquidar"] = {k: len(v) for k, v in atrasados.items()}
    for lg, items in atrasados.items():
        horas = (ahora - datetime.fromisoformat(
            min(i[2] for i in items).replace("Z", "+00:00"))).total_seconds() / 3600
        sev = "alta" if horas > 48 else "media"
        inf.add(sev, "liquidacion",
                f"{len(items)} picks de {LGN.get(lg, lg)} sin liquidar tras {horas:.0f} h "
                f"(suele ser un nombre de equipo que no coincide)",
                [f"{h} v {a} ({ko[:16]})" for h, a, ko in items[:6]])


# -------------------------------------------------------------------- calibracion

def z_poisson_binomial(sel: list[dict]) -> tuple[float, float, float, float]:
    """Compara aciertos reales contra los esperados por el propio modelo.

    Cada pick tiene su probabilidad, asi que el total de aciertos es una
    Poisson-binomial, no una binomial: la varianza es la suma de p(1-p), no n*p(1-p)
    con la p media. Usar la media infla la varianza y esconde los desvios.
    Devuelve (predicho, real, z, n).
    """
    n = len(sel)
    if not n:
        return 0.0, 0.0, 0.0, 0
    esperados = sum(p["p"] for p in sel)
    var = sum(p["p"] * (1 - p["p"]) for p in sel)
    reales = sum(p["estado"] == "ganado" for p in sel)
    z = (reales - esperados) / math.sqrt(var) if var > 0 else 0.0
    return esperados / n, reales / n, z, n


def calibracion(inf: Informe, picks: list[dict], calib: dict) -> None:
    done = [p for p in picks if p.get("estado") in ("ganado", "perdido")]
    pred, real, z, n = z_poisson_binomial(done)
    inf.metricas["calibracion"] = {"n": n, "predicho": round(pred, 4),
                                   "real": round(real, 4), "z": round(z, 2)}
    if n < 10:
        inf.add("baja", "calibracion",
                f"solo {n} picks liquidados: todavia no se puede medir nada")
        return

    # |z| > 2 es, a grandes rasgos, un desvio que no se explica por azar
    if abs(z) > 2:
        sentido = "inflado" if z < 0 else "conservador"
        inf.add("media", "calibracion",
                f"el modelo viene {sentido}: {real:.1%} real contra {pred:.1%} predicho "
                f"sobre {n} picks (z={z:+.2f}, no es ruido)")
    for g in ("resultado", "goles", "estadisticas"):
        sel = [p for p in done if p.get("grupo") == g]
        if len(sel) < 25:
            continue
        gp, gr, gz, gn = z_poisson_binomial(sel)
        inf.metricas.setdefault("porGrupo", {})[g] = {
            "n": gn, "predicho": round(gp, 4), "real": round(gr, 4), "z": round(gz, 2)}
        if abs(gz) > 2:
            inf.add("media", "calibracion",
                    f"grupo {g}: {gr:.1%} real contra {gp:.1%} predicho sobre {gn} "
                    f"(z={gz:+.2f})")

    bandas = {}
    for lo in (0.65, 0.70, 0.75, 0.80, 0.85):
        sel = [p for p in done if lo <= p["p"] < lo + 0.05]
        if len(sel) < 15:
            continue
        bp, br, bz, bn = z_poisson_binomial(sel)
        bandas[f"{lo:.2f}-{lo+0.05:.2f}"] = {"n": bn, "predicho": round(bp, 4),
                                             "real": round(br, 4), "z": round(bz, 2)}
        if abs(bz) > 2.5:
            inf.add("baja", "calibracion",
                    f"banda {lo:.0%}-{lo+0.05:.0%}: {br:.1%} real contra {bp:.1%} "
                    f"predicho sobre {bn} (z={bz:+.2f})")
    if bandas:
        inf.metricas["porBanda"] = bandas

    umbral = calib.get("umbralVigente", UMBRAL_BASE)
    if n >= MIN_LIQ_AJUSTE and real < pred - 0.02 and umbral <= UMBRAL_BASE + 1e-9:
        inf.add("media", "calibracion",
                f"con {n} liquidados y el modelo inflado, el umbral deberia haber subido "
                f"y sigue en {umbral:.2f}")


# -------------------------------------------------------------------------- valor

def valor(inf: Informe, picks: list[dict]) -> None:
    pend = [p for p in picks if p.get("estado") == "pendiente"]
    con = [p for p in pend if isinstance(p.get("casa"), (int, float))]
    inf.metricas["valor"] = {"pendientes": len(pend), "conPrecioCasa": len(con)}
    if not con:
        if pend:
            inf.add("baja", "valor",
                    "ningun pick pendiente trae precio de bet365: sin eso no se puede "
                    "saber cual tiene valor de verdad")
        return
    buenos = [p for p in con if (p.get("valor") or 0) > 0]
    medio = sum(p.get("valor") or 0 for p in con) / len(con)
    inf.metricas["valor"].update({"conValorPositivo": len(buenos),
                                  "valorMedio": round(medio, 4)})
    if not buenos:
        inf.add("baja", "valor",
                f"ninguno de los {len(con)} picks con precio supera la cuota justa: "
                f"valor medio {medio:+.2%}. Es lo esperable, pero conviene no apostarlos")
    # un valor positivo enorme casi siempre es un error de datos, no una oportunidad
    raros = [f"{p['id']} {p.get('valor'):+.1%}" for p in con if (p.get("valor") or 0) > 0.25]
    if raros:
        inf.add("media", "valor",
                f"{len(raros)} picks con valor sospechosamente alto (revisar la cuota)",
                raros[:6])


# ----------------------------------------------------------------------- frescura

def frescura(inf: Informe, ahora: datetime) -> None:
    for nombre, horas, sev in (("_ultimo_refresco.log", 36, "alta"),
                               ("_ultimo_livescore.log", 36, "media")):
        f = DATA / nombre
        if not f.exists():
            inf.add(sev, "frescura", f"falta {nombre}: el refresco no dejo rastro")
            continue
        edad = (ahora.timestamp() - f.stat().st_mtime) / 3600
        inf.metricas.setdefault("edadHoras", {})[nombre] = round(edad, 1)
        if edad > horas:
            inf.add(sev, "frescura", f"{nombre} tiene {edad:.0f} h: el refresco no corre")
    txt = (DATA / "_ultimo_refresco.log").read_text(errors="ignore") if \
        (DATA / "_ultimo_refresco.log").exists() else ""
    if "ABORTO" in txt:
        inf.add("alta", "frescura", "la ultima corrida aborto sin escribir datos")
    for fuente, marca in (("football-data", "partidos en base"),
                          ("LiveScore", "resultados leidos")):
        pass  # el detalle por fuente ya queda en sus propios logs


# -------------------------------------------------------------------------- sitio

def sitio(inf: Informe) -> None:
    try:
        import requests
        from refresh import prefer_ipv4
        prefer_ipv4()
        s = requests.Session()
        for ruta, clave in (("/", None), ("/data/picks.json", "lista"),
                            ("/data/parlays.json", "lista")):
            r = s.get(SITIO + ruta, timeout=25)
            if r.status_code != 200:
                inf.add("alta", "sitio", f"{ruta} responde HTTP {r.status_code}")
                continue
            if clave == "lista":
                try:
                    d = r.json()
                except ValueError:
                    inf.add("alta", "sitio", f"{ruta} no es JSON valido"); continue
                if not isinstance(d, list):
                    inf.add("alta", "sitio", f"{ruta} no es una lista")
                else:
                    inf.metricas.setdefault("sitio", {})[ruta] = len(d)
            elif "<!doctype html>" not in r.text[:200].lower():
                inf.add("media", "sitio", "la pagina no arranca con doctype")
        # lo publicado deberia coincidir con lo que hay en el repo
        local = len(leer("picks.json", []))
        remoto = inf.metricas.get("sitio", {}).get("/data/picks.json")
        if remoto is not None and local and remoto != local:
            inf.add("media", "sitio",
                    f"el sitio publica {remoto} picks y el repo tiene {local}: "
                    f"el despliegue quedo atras")
    except Exception as e:  # noqa: BLE001 - la auditoria no debe caerse por el chequeo web
        inf.add("baja", "sitio", f"no se pudo chequear el sitio: {type(e).__name__}: {e}")


# ------------------------------------------------------------------------ informe

def escribir(inf: Informe, ahora: datetime) -> None:
    entrada = {"fecha": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "hallazgos": inf.hallazgos, "metricas": inf.metricas,
               "resumen": {s: len(inf.por_sev(s)) for s in ("alta", "media", "baja")}}
    hist = leer("auditoria.json", [])
    if not isinstance(hist, list):
        hist = []
    hist = [h for h in hist if h.get("fecha", "")[:10] != ahora.strftime("%Y-%m-%d")]
    hist.append(entrada)
    hist = sorted(hist, key=lambda h: h.get("fecha", ""))[-90:]   # 90 dias
    (DATA / "auditoria.json").write_text(
        json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")

    ic = {"alta": "🔴", "media": "🟡", "baja": "⚪"}
    L = [f"# Auditoria · {ahora:%Y-%m-%d %H:%M} UTC", ""]
    r = entrada["resumen"]
    L.append(f"**{r['alta']} de severidad alta · {r['media']} media · {r['baja']} baja**")
    L.append("")
    if not inf.hallazgos:
        L.append("Sin hallazgos. Todo lo que se mide esta dentro de lo esperado.")
    for sev in ("alta", "media", "baja"):
        hs = inf.por_sev(sev)
        if not hs:
            continue
        L.append(f"## {ic[sev]} {sev.capitalize()}")
        L.append("")
        for h in hs:
            L.append(f"- **[{h['area']}]** {h['mensaje']}")
            if h.get("detalle"):
                for d in (h["detalle"] if isinstance(h["detalle"], list)
                          else [h["detalle"]])[:6]:
                    L.append(f"  - `{d}`")
        L.append("")
    c = inf.metricas.get("calibracion")
    if c and c["n"]:
        L.append("## Calibracion")
        L.append("")
        L.append("| Corte | n | Predicho | Real | z |")
        L.append("| --- | ---: | ---: | ---: | ---: |")
        L.append(f"| Todo | {c['n']} | {c['predicho']:.1%} | {c['real']:.1%} | {c['z']:+.2f} |")
        for g, v in (inf.metricas.get("porGrupo") or {}).items():
            L.append(f"| {g} | {v['n']} | {v['predicho']:.1%} | {v['real']:.1%} | {v['z']:+.2f} |")
        for b, v in (inf.metricas.get("porBanda") or {}).items():
            L.append(f"| banda {b} | {v['n']} | {v['predicho']:.1%} | {v['real']:.1%} | {v['z']:+.2f} |")
        L.append("")
        L.append("`z` compara los aciertos contra los que el propio modelo esperaba, "
                 "con la varianza Poisson-binomial. Entre -2 y +2 es ruido.")
        L.append("")
    v = inf.metricas.get("valor")
    if v:
        L.append("## Valor contra bet365")
        L.append("")
        L.append(f"- {v.get('conPrecioCasa', 0)} de {v.get('pendientes', 0)} picks "
                 f"pendientes traen precio de la casa")
        if "valorMedio" in v:
            L.append(f"- {v['conValorPositivo']} superan la cuota justa · "
                     f"valor medio {v['valorMedio']:+.2%}")
        L.append("")
    (ROOT / "AUDITORIA.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    ahora = datetime.now(timezone.utc)
    log(f"Auditoria {ahora:%Y-%m-%d %H:%M} UTC")
    picks = leer("picks.json", [])
    parlays = leer("parlays.json", [])
    calib = leer("calibracion.json", {})
    inf = Informe()
    if not isinstance(picks, list) or not picks:
        inf.add("alta", "integridad", "picks.json vacio o ilegible")
    else:
        integridad(inf, picks, parlays if isinstance(parlays, list) else [])
        liquidacion(inf, picks, ahora)
        calibracion(inf, picks, calib if isinstance(calib, dict) else {})
        valor(inf, picks)
    frescura(inf, ahora)
    sitio(inf)
    escribir(inf, ahora)

    for sev in ("alta", "media", "baja"):
        for h in inf.por_sev(sev):
            log(f"  [{sev}] {h['area']}: {h['mensaje']}")
    altas = len(inf.por_sev("alta"))
    log(f"  {altas} alta · {len(inf.por_sev('media'))} media · {len(inf.por_sev('baja'))} baja")
    return 1 if altas else 0


if __name__ == "__main__":
    sys.exit(main())
