"""Prueba de refresh.py con las descargas simuladas, con la forma real de football-data.co.uk."""
import json, sys, shutil, random, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np, pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import refresh as R
from refresh import PARLAY_LO, PARLAY_HI

random.seed(7); np.random.seed(7)
TODAY = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)

TEAMS = {
    "E0": ["Arsenal", "Chelsea", "Liverpool", "Man City", "Man United", "Newcastle",
           "Tottenham", "Everton", "Brighton", "Brentford", "Nott'm Forest", "Fulham"],
    "SP1": ["Barcelona", "Real Madrid", "Ath Madrid", "Ath Bilbao", "Sociedad", "Betis",
            "Celta", "Valencia", "Villarreal", "Vallecano", "Getafe", "Espanol"],
    "I1": ["Inter", "Milan", "Juventus", "Napoli", "Roma", "Lazio",
           "Atalanta", "Fiorentina", "Bologna", "Torino", "Udinese", "Genoa"],
    "D1": ["Bayern Munich", "Dortmund", "Leverkusen", "RB Leipzig", "M'gladbach", "FC Koln",
           "Ein Frankfurt", "Freiburg", "Hoffenheim", "Mainz", "Stuttgart", "Augsburg"],
}

_CACHE = {}
def played(div, season, n=140):
    """Temporada jugada con estadisticas y cuotas, como la publica football-data.
    Cacheada para que el test y main() vean exactamente los mismos partidos."""
    if (div, season) in _CACHE:
        return _CACHE[(div, season)]
    ts = TEAMS[div]; rows = []
    base = datetime(2025, 8, 10) if season.startswith("25") else datetime(2026, 8, 9)
    for i in range(n):
        h, a = random.sample(ts, 2)
        d = base + timedelta(days=int(i * 1.4))
        if d > TODAY.replace(tzinfo=None) - timedelta(days=1):
            break
        hg, ag = np.random.poisson(1.6), np.random.poisson(1.2)
        hst, ast = np.random.poisson(5) + ag, np.random.poisson(4) + hg
        oh, od, oa = round(random.uniform(1.3, 4.5), 2), round(random.uniform(3.0, 4.5), 2), round(random.uniform(1.4, 6.0), 2)
        rows.append({
            "Div": div, "Date": d.strftime("%d/%m/%Y"), "Time": "15:00",
            "HomeTeam": h, "AwayTeam": a, "FTHG": hg, "FTAG": ag,
            "FTR": "H" if hg > ag else ("A" if ag > hg else "D"),
            "HS": np.random.poisson(13), "AS": np.random.poisson(11),
            "HST": hst, "AST": ast,
            "HC": np.random.poisson(5), "AC": np.random.poisson(4),
            "HY": np.random.poisson(2), "AY": np.random.poisson(2),
            "AvgCH": oh, "AvgCD": od, "AvgCA": oa,
        })
    _CACHE[(div, season)] = pd.DataFrame(rows)
    return _CACHE[(div, season)]

def fixtures():
    rows = []
    for div, ts in TEAMS.items():
        pool = ts[:]; random.shuffle(pool)
        for j in range(0, 10, 2):
            h, a = pool[j], pool[j + 1]
            d = TODAY.replace(tzinfo=None) + timedelta(days=2 + j // 2)
            oh, od, oa = round(random.uniform(1.25, 4.0), 2), round(random.uniform(3.1, 4.6), 2), round(random.uniform(1.5, 7.0), 2)
            rows.append({"Div": div, "Date": d.strftime("%d/%m/%Y"), "Time": "16:30",
                         "HomeTeam": h, "AwayTeam": a,
                         "AvgH": oh, "AvgD": od, "AvgA": oa})
    return pd.DataFrame(rows)

CALLS = []
def fake_fetch(url, timeout=60):
    CALLS.append(url)
    if url.endswith("fixtures.csv"):
        return fixtures()
    parts = url.rstrip(".csv").split("/")
    div, season = parts[-1], parts[-2]
    return played(div, season) if div in TEAMS else None

R.fetch_csv = fake_fetch

class FakeDT(datetime):
    @classmethod
    def now(cls, tz=None): return TODAY
R.datetime = FakeDT

# ---- escenario: picks pendientes de una jornada que ya paso, cubriendo todos los mercados
work = Path(tempfile.mkdtemp(prefix="montoglory-test-"))
if work.exists(): shutil.rmtree(work)
(work / "data").mkdir(parents=True)
R.DATA = work / "data"

hist = played("E0", "2627", 200)
viejos = []
KEYS = ["1", "2", "1X", "12", "X2", "O1.5", "O2.5", "U2.5", "U3.5", "BTTS", "NBTTS",
        "cor_m_o8.5", "cor_h_o2.5", "cor_a_u6.5", "yel_m_o2.5", "yel_h_u3.5", "yel_a_o0.5",
        "sho_m_o21.5", "sho_h_o10.5", "sho_a_u12.5", "sav_m_o4.5", "sav_h_u4.5", "sav_a_o1.5",
        "CS_H", "HO1.5", "AU0.5"]
# cruces distintos: con pares repetidos el deduplicado quita uno, con razon, y el
# escenario dejaria de medir lo que quiere medir
_vistos = set()
_filas = []
for _, _r in hist.iterrows():
    _par = (_r["HomeTeam"], _r["AwayTeam"])
    if _par in _vistos:
        continue
    _vistos.add(_par)
    _filas.append(_r)
    if len(_filas) >= len(KEYS):
        break
assert len(_filas) >= len(KEYS), "no hay suficientes cruces distintos en la muestra"
for i, k in enumerate(KEYS):
    r = _filas[i]
    ko = datetime.strptime(r["Date"], "%d/%m/%Y").replace(hour=15, tzinfo=timezone.utc)
    viejos.append({"id": R.pick_id(R.show(r["HomeTeam"]), R.show(r["AwayTeam"]), k),
                   "lg": "premier", "home": R.show(r["HomeTeam"]), "away": R.show(r["AwayTeam"]),
                   "ko": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "key": k, "label": f"test {k}",
                   "cat": "test", "grupo": "estadisticas" if "_" in k else "goles",
                   "p": 0.75, "cuota": 1.33, "estado": "pendiente", "resultado": None})
# un pick de Champions sin fuente: debe caducar, no contaminar el acierto
viejos.append({"id": "bayern-munich__arsenal__12", "lg": "ucl", "home": "Bayern Munich",
               "away": "Arsenal", "ko": "2026-10-21T19:00:00Z", "key": "12",
               "label": "Local o visitante", "cat": "1X2", "grupo": "resultado",
               "p": 0.745, "cuota": 1.34, "estado": "pendiente", "resultado": None})

R.write_json(R.DATA / "picks.json", viejos)
R.write_json(R.DATA / "parlays.json", [{"id": "x__2patas", "jornada": "2026-10-21", "patas": 2,
    "prob": 0.5, "cuota": 2.0, "estado": "pendiente",
    "legs": [{"home": viejos[0]["home"], "away": viejos[0]["away"], "key": viejos[0]["key"],
              "liga": "Premier League", "label": "l", "p": 0.75, "ko": viejos[0]["ko"]},
             {"home": viejos[1]["home"], "away": viejos[1]["away"], "key": viejos[1]["key"],
              "liga": "Premier League", "label": "l", "p": 0.75, "ko": viejos[1]["ko"]}]}])

print("=" * 70)
rc = R.main()
print("=" * 70)
assert rc == 0, f"main() devolvio {rc}"

picks = json.loads((R.DATA / "picks.json").read_text())
parl = json.loads((R.DATA / "parlays.json").read_text())
calib = json.loads((R.DATA / "calibracion.json").read_text())

liq = [p for p in picks if p["estado"] in ("ganado", "perdido")]
pend = [p for p in picks if p["estado"] == "pendiente"]
print(f"\npicks: {len(picks)} ({len(liq)} liquidados, {len(pend)} pendientes)")
print(f"combinadas: {len(parl)}  calib: {calib['real']} vs {calib['predicho']} n={calib['nLiquidados']}")

# --- aserciones
assert len(liq) >= len(KEYS) - 1, f"se liquidaron {len(liq)} de {len(KEYS)}"
assert all(p["resultado"] for p in liq), "falta el string de resultado"
assert not any(p["lg"] == "ucl" for p in picks), "el pick de Champions debia caducar"
assert pend, "no se generaron picks nuevos"
assert all(0.65 < p["p"] <= 0.90 for p in pend), "pick fuera de rango"
assert all(p["grupo"] in ("resultado", "goles", "estadisticas") for p in pend)
assert len({(p["home"], p["away"], p["grupo"]) for p in pend}) == len(pend), "pick duplicado por partido/grupo"
assert len({p["id"] for p in picks}) == len(picks), "ids duplicados"
for t in parl:
    if t["estado"] != "pendiente": continue
    eq = [x for l in t["legs"] for x in (l["home"], l["away"])]
    assert len(set(eq)) == len(eq), f"equipo repetido en {t['id']}"
    pr = float(np.prod([l["p"] for l in t["legs"]]))
    assert 0.40 <= pr <= 0.52, f"{t['id']} fuera de rango: {pr:.3f}"
    assert abs(pr - t["prob"]) < 1e-3
assert calib["nLiquidados"] == len(liq)
assert calib["umbralVigente"] >= 0.65

# --- liquidacion verificada a mano contra el partido real
print("\nverificacion manual de liquidacion:")
ok = 0
D_all = R.load_results(TODAY)   # la misma base que vio main()
for p in liq[:8]:
    ko = pd.to_datetime(p["ko"], utc=True)
    sub = D_all[(D_all.kH == R.canon(p["home"])) & (D_all.kA == R.canon(p["away"]))].copy()
    sub["gap"] = (sub.fecha.dt.tz_localize("UTC") - ko).abs()
    r = sub.sort_values("gap").iloc[0]      # el mas cercano al kickoff, como hace refresh.py
    esperado = R.settle_key(p["key"], r)
    real = p["estado"] == "ganado"
    marca = "ok" if esperado == real else "MAL"
    if esperado == real: ok += 1
    print(f"  {marca}  {p['key']:14s} {int(r.FTHG)}-{int(r.FTAG)} "
          f"C{int(r.HC)}/{int(r.AC)} Y{int(r.HY)}/{int(r.AY)} -> {p['estado']} ({p['resultado']})")
assert ok == 8, "liquidacion inconsistente"

# --- el umbral se mueve cuando el modelo viene inflado
inflados = [{**p, "estado": "perdido", "p": 0.80, "grupo": "goles"} for p in range(0) ] or \
           [{"id": f"i{i}", "p": 0.80, "estado": "perdido" if i % 3 else "ganado",
             "grupo": "goles"} for i in range(90)]
c2 = R.calibrate(inflados)
print(f"\numbral con 90 liquidados al {c2['real']:.0%} real vs {c2['predicho']:.0%} "
      f"predicho -> {c2['umbralVigente']:.0%}")
assert c2["umbralVigente"] > 0.65, "el umbral no se ajusto"

# --- aborta sin romper nada si se cae la descarga
antes = (R.DATA / "picks.json").read_text()
R.fetch_csv = lambda url, timeout=60: None
assert R.main() == 1, "deberia abortar"
assert (R.DATA / "picks.json").read_text() == antes, "toco los datos aun abortando"
print("\naborta limpio sin tocar los datos: ok")

print("\nTODO OK")

# ===================== regresion: un dia flaco no debe borrar los pendientes =========
print("\n" + "=" * 70)
print("ESCENARIO 2: fixtures.csv con una sola fila (ventana flaca)")

antes_pend = [p for p in json.loads((R.DATA / "picks.json").read_text())
              if p["estado"] == "pendiente"]
futuros = {p["id"] for p in antes_pend
           if pd.to_datetime(p["ko"], utc=True) > TODAY}
print(f"  pendientes antes: {len(antes_pend)} ({len(futuros)} aun por jugar)")
assert futuros, "el escenario necesita pendientes futuros"

def fixtures_flaco():
    d = fixtures().iloc[:1].copy()      # una sola fila, como paso de verdad
    return d

R.fetch_csv = lambda url, timeout=60: (fixtures_flaco() if url.endswith("fixtures.csv")
                                       else fake_fetch(url, timeout))
assert R.main() == 0
despues = json.loads((R.DATA / "picks.json").read_text())
ids_despues = {p["id"] for p in despues}
perdidos = futuros - ids_despues
print(f"  picks tras el refresco flaco: {len(despues)}")
print(f"  pendientes futuros perdidos: {len(perdidos)}")
assert not perdidos, f"se borraron {len(perdidos)} picks que seguian vigentes"

# los liquidados tampoco se tocan
liq_ids = {p["id"] for p in despues if p["estado"] in ("ganado", "perdido")}
assert len(liq_ids) >= 26, f"se perdieron liquidados: quedan {len(liq_ids)}"
assert len({p["id"] for p in despues}) == len(despues), "ids duplicados tras el merge"
# y siguen ordenados por kickoff
kos = [p["ko"] for p in despues]
assert kos == sorted(kos), "el archivo quedo desordenado"
print("  liquidados intactos, sin duplicados, ordenado por kickoff: ok")

print("\nESCENARIO 2 OK")

# ===== regresion: pendientes pasado el kickoff y un pick por partido/grupo ==========
print("\n" + "=" * 70)
print("ESCENARIO 3: pick esperando resultado y recotizacion de un partido")

estado = json.loads((R.DATA / "picks.json").read_text())
# un pick cuyo kickoff ya paso pero que settle mantiene: no debe borrarlo el merge
esperando = {p["id"] for p in estado
             if p["estado"] == "pendiente" and pd.to_datetime(p["ko"], utc=True) <= TODAY}
print(f"  pendientes pasado el kickoff: {len(esperando)}")

# un partido de la ventana de fixtures: sus picks viejos deben ser reemplazados
fx1 = fixtures().iloc[0]
par = (R.show(fx1.HomeTeam), R.show(fx1.AwayTeam))
R.fetch_csv = lambda url, timeout=60: (fixtures().iloc[:1].copy() if url.endswith("fixtures.csv")
                                       else fake_fetch(url, timeout))
assert R.main() == 0
d = json.loads((R.DATA / "picks.json").read_text())
ids = {p["id"] for p in d}

perdidos = esperando - ids
print(f"  esperando resultado que se borraron: {len(perdidos)}")
assert not perdidos, f"el merge borro {len(perdidos)} picks que settle habia mantenido"

# un solo pick por partido y grupo, en todo el archivo
pend = [p for p in d if p["estado"] == "pendiente"]
claves = [(p["home"], p["away"], p["grupo"]) for p in pend]
from collections import Counter
dups = {k: v for k, v in Counter(claves).items() if v > 1}
print(f"  partidos con mas de un pick en el mismo grupo: {len(dups)}")
for k, v in list(dups.items())[:3]:
    print(f"     {k} x{v}")
assert not dups, "se rompio la regla de un pick por partido y grupo"

delpar = [p for p in pend if (p["home"], p["away"]) == par]
print(f"  picks del partido recotizado {par[0]} v {par[1]}: {len(delpar)} "
      f"(grupos: {sorted({p['grupo'] for p in delpar})})")
assert len(delpar) == len({p["grupo"] for p in delpar}), "quedaron viejos y nuevos mezclados"
print("\nESCENARIO 3 OK")

# ===================== futbol femenino: nunca, por decision de producto ==============
print("\n" + "=" * 70)
print("ESCENARIO 4: exclusion de futbol femenino")
from refresh import es_femenino
FEM = [("Women's World Cup Qualification","UEFA"), ("England","FA WSL"), ("USA","NWSL"),
       ("Germany","Frauen-Bundesliga"), ("Spain","Liga F Femenino"),
       ("International Friendlies","Women's Friendlies"), ("Arsenal (W)",),
       ("Chelsea W",), ("Barcelona Femeni",), ("Barcelona Femenino",),
       ("Olympique Lyonnais Feminin",), ("Juventus Femminile",), ("Lyon Dames",),
       ("Norway Kvinner",), ("Ladies FC",)]
MASC = [("England","Premier League"), ("World Cup Qualification","UEFA: Group C"),
        ("Champions League","League Stage"), ("Africa Cup of Nations","Group A"),
        ("Nations League","League A"), ("Copa America","Group B"),
        ("Wolves",), ("Werder Bremen",), ("West Ham",), ("Newcastle",), ("Swansea",),
        ("Como","Manchester United"), ("Athletic Bilbao",), ("Feyenoord",),
        ("Bayern Munich",), ("Real Madrid",), ("Wolfsburg",), ("Dortmund",)]
mal = []
for a in FEM:
    if not es_femenino(*a): mal.append(("no detectado", a))
for a in MASC:
    if es_femenino(*a): mal.append(("falso positivo", a))
for m in mal: print(f"   MAL {m[0]}: {m[1]}")
print(f"  {len(FEM)} casos femeninos detectados, {len(MASC)} masculinos intactos")
assert not mal, f"{len(mal)} errores en la exclusion de femenino"

# y que efectivamente no entre por ninguna de las tres puertas
import livescore as _LS, odds_api as _OA
assert _LS.es_femenino is es_femenino and _OA.es_femenino is es_femenino, \
    "las fuentes deben usar la MISMA regla, no copias"
assert not any(es_femenino(k) is False and "women" in k for k in _OA.COMPETENCIAS), \
    "hay una clave femenina en COMPETENCIAS"
print("  las tres fuentes comparten la misma regla: ok")
print("\nESCENARIO 4 OK")


# ============ regresion: nombres de dos fuentes distintas ===========================
print("\n" + "=" * 70)
print("ESCENARIO 5: emparejar nombres entre The Odds API y LiveScore")
from refresh import mismo_equipo, mismo_partido

# El corpus vive en casos_nombres.json porque lo comparte test_pagina.py: el
# matcher de la pagina tiene que dar lo MISMO que este, y cuando no lo daba la
# pagina mostraba "Esperando resultado" sobre un partido que el pipeline ya tenia
# liquidado. Un solo equipo es permisivo a proposito: "Inter" tiene que coincidir
# con "Inter Milano", y eso arrastra que tambien coincida con "Inter Miami". El
# partido completo es lo que se usa de verdad, y lo que cierra los ambiguos.
_CASOS = json.loads((Path(__file__).parent / "casos_nombres.json").read_text("utf-8"))
UNO = [(a, b, e) for a, b, e in _CASOS["equipo"]]
PAR = [((h1, a1), (h2, a2), e) for (h1, a1), (h2, a2), e in _CASOS["partido"]]

mal = []
for a, b, e in UNO:
    if mismo_equipo(a, b) != e: mal.append(("equipo", a, b, e))
for (h1, a1), (h2, a2), e in PAR:
    if mismo_partido(h1, a1, h2, a2) != e: mal.append(("partido", f"{h1} v {a1}", f"{h2} v {a2}", e))
for m in mal: print(f"   MAL {m}")
print(f"  {len(UNO)} comparaciones de equipo y {len(PAR)} de partido")
assert not mal, f"{len(mal)} errores de emparejamiento"
print("\nESCENARIO 5 OK")

# ============ combinadas: por dia y por fecha ======================================
print("\n" + "=" * 70)
print("ESCENARIO 6: las dos familias de combinadas")
from refresh import build_parlays
base = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
muestra = []
for i in range(40):                      # 4 dias, varias competencias
    dia = base + timedelta(days=1 + i % 4, hours=12)
    lg = ["premier", "laliga", "seriea", "bundesliga", "ucl"][i % 5]
    muestra.append({"id": f"p{i}", "lg": lg, "home": f"Local{i}", "away": f"Visita{i}",
                    "ko": dia.strftime("%Y-%m-%dT%H:%M:%SZ"), "key": "1X",
                    "label": "Local o empate", "cat": "Doble oportunidad",
                    "grupo": "resultado", "p": round(0.70 + (i % 9) * 0.02, 4),
                    "cuota": 1.3, "estado": "pendiente", "resultado": None})
# una pata ya empezada: no debe entrar en ninguna
muestra.append({**muestra[0], "id": "viejo", "home": "Empezado", "away": "YaJuega",
                "ko": (base - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")})
ts = build_parlays(muestra, "2026-11-20", ahora=base)
print(f"  {len(ts)} combinadas: "
      f"{sum(1 for t in ts if t['tipo']=='dia')} por dia, "
      f"{sum(1 for t in ts if t['tipo']=='fecha')} por fecha")
fallas = []
for t in ts:
    dias = {l["ko"][:10] for l in t["legs"]}
    eq = [q for l in t["legs"] for q in (l["home"], l["away"])]
    part = [(l["home"], l["away"]) for l in t["legs"]]
    pr = 1.0
    for l in t["legs"]: pr *= l["p"]
    if t["tipo"] == "dia" and len(dias) != 1: fallas.append((t["id"], "dia multiples fechas"))
    if t["tipo"] == "fecha" and len(dias) < 2: fallas.append((t["id"], "fecha de un solo dia"))
    if len(set(eq)) != len(eq): fallas.append((t["id"], "equipo repetido"))
    if len(set(part)) != len(part): fallas.append((t["id"], "partido repetido"))
    if not (PARLAY_LO - 1e-9 <= pr <= PARLAY_HI + 1e-9): fallas.append((t["id"], f"banda {pr:.3f}"))
    if abs(pr - t["prob"]) > 1e-3: fallas.append((t["id"], "prob != producto"))
    if any(l["home"] == "Empezado" for l in t["legs"]): fallas.append((t["id"], "pata ya empezada"))
for f in fallas: print(f"   MAL {f}")
assert ts, "no se armo ninguna combinada"
assert not fallas, f"{len(fallas)} problemas"
assert len({t["id"] for t in ts}) == len(ts), "ids duplicados"
# mezclar competencias esta permitido y de hecho pasa
assert any(len({l["lg"] for l in t["legs"]}) > 1 for t in ts), "ninguna mezcla competencias"
print("  una pata por partido, sin equipos repetidos, en banda, sin partidos empezados: ok")
print("  mezcla de competencias presente: ok")
print("\nESCENARIO 6 OK")

# ============ el mismo partido cargado dos veces ===================================
print("\n" + "=" * 70)
print("ESCENARIO 7: duplicados del mismo partido")
from refresh import _quitar_duplicados
dup = [
  # mismo partido, dos nombres y dos horarios: paso de verdad el 23/10
  {"id": "a1", "lg": "premier", "home": "Ipswich Town", "away": "Nottingham Forest",
   "ko": "2026-10-23T19:00:00Z", "grupo": "resultado", "p": 0.72, "cuota": 1.39,
   "key": "12", "label": "x", "cat": "c", "estado": "pendiente", "resultado": None},
  {"id": "a2", "lg": "premier", "home": "Ipswich", "away": "Nottingham Forest",
   "ko": "2026-10-23T20:00:00Z", "grupo": "resultado", "p": 0.73, "cuota": 1.37,
   "key": "12", "label": "x", "cat": "c", "estado": "pendiente", "resultado": None},
  {"id": "a3", "lg": "premier", "home": "Ipswich", "away": "Nottingham Forest",
   "ko": "2026-10-23T20:00:00Z", "grupo": "goles", "p": 0.80, "cuota": 1.25,
   "key": "O1.5", "label": "x", "cat": "c", "estado": "pendiente", "resultado": None},
  # partidos distintos que NO deben fusionarse
  {"id": "b1", "lg": "premier", "home": "Manchester United", "away": "Roma",
   "ko": "2026-10-23T19:00:00Z", "grupo": "resultado", "p": 0.70, "cuota": 1.43,
   "key": "12", "label": "x", "cat": "c", "estado": "pendiente", "resultado": None},
  {"id": "b2", "lg": "premier", "home": "Manchester City", "away": "Roma",
   "ko": "2026-10-23T19:00:00Z", "grupo": "resultado", "p": 0.75, "cuota": 1.33,
   "key": "12", "label": "x", "cat": "c", "estado": "pendiente", "resultado": None},
  # mismo cruce pero de otra semana: tampoco se fusiona
  {"id": "c1", "lg": "premier", "home": "Ipswich", "away": "Nottingham Forest",
   "ko": "2026-11-15T15:00:00Z", "grupo": "resultado", "p": 0.71, "cuota": 1.41,
   "key": "12", "label": "x", "cat": "c", "estado": "pendiente", "resultado": None},
]
out = _quitar_duplicados(dup)
ids = {p["id"] for p in out}
ipswich_oct = [p for p in out if "ipswich" in p["home"].lower() and p["ko"][:10] == "2026-10-23"]
print(f"  {len(dup)} entraron, {len(out)} quedaron")
for p in out: print(f"     {p['home'][:18]:18s} v {p['away'][:18]:18s} {p['ko'][:16]} {p['grupo']}")
assert len(ipswich_oct) == 2, f"deberian quedar 2 (un grupo cada uno), quedaron {len(ipswich_oct)}"
assert all(p["ko"] == "2026-10-23T20:00:00Z" for p in ipswich_oct), "debe quedar el horario corregido"
assert {"b1", "b2"} <= ids, "Manchester United y City se fusionaron: son equipos distintos"
assert "c1" in ids, "se fusiono un cruce de otra fecha"
print("\nESCENARIO 7 OK")

# un duplicado YA LIQUIDADO no debe contarse dos veces
print("\n--- duplicados ya liquidados")
liq = [
  {"id": "d1", "lg": "premier", "home": "Ipswich Town", "away": "Nottingham Forest",
   "ko": "2026-10-23T19:00:00Z", "grupo": "goles", "p": 0.80, "cuota": 1.25, "key": "O1.5",
   "label": "Mas de 1.5 goles", "cat": "c", "estado": "ganado", "resultado": "1-1"},
  {"id": "d2", "lg": "premier", "home": "Ipswich", "away": "Nottingham Forest",
   "ko": "2026-10-23T20:00:00Z", "grupo": "goles", "p": 0.81, "cuota": 1.23, "key": "O1.5",
   "label": "Mas de 1.5 goles", "cat": "c", "estado": "ganado", "resultado": "1-1"},
  {"id": "d3", "lg": "premier", "home": "Ipswich", "away": "Nottingham Forest",
   "ko": "2026-10-23T20:00:00Z", "grupo": "resultado", "p": 0.72, "cuota": 1.39, "key": "12",
   "label": "Local o visitante", "cat": "c", "estado": "perdido", "resultado": "1-1"},
]
o = _quitar_duplicados(liq)
print(f"  {len(liq)} entraron, {len(o)} quedaron: {[(x['grupo'], x['estado']) for x in o]}")
assert len(o) == 2, f"el mismo resultado quedo contado {len(o)} veces"
assert {x["grupo"] for x in o} == {"goles", "resultado"}
print("  un solo pick por grupo, sin contar dos veces el mismo resultado: ok")

# ===== regresion: la fuente sin estadisticas no debe tapar a la que si las tiene ====
print("\n" + "=" * 70)
print("ESCENARIO 8: dos fuentes para el mismo partido")
import pandas as _pd
from refresh import settle as _settle
_ko = "2026-10-25T14:00:00Z"
# LiveScore: hora exacta, solo goles. football-data: solo fecha, con estadisticas.
_filas = _pd.DataFrame([
  {"HomeTeam": "Crystal Palace", "AwayTeam": "Newcastle",
   "fecha": _pd.Timestamp("2026-10-25 14:00"), "FTHG": 0.0, "FTAG": 2.0,
   "HC": None, "AC": None, "HY": None, "AY": None, "HS": None, "AS": None,
   "HST": None, "AST": None, "savH": None, "savA": None,
   "kH": R.canon("Crystal Palace"), "kA": R.canon("Newcastle")},
  {"HomeTeam": "Crystal Palace", "AwayTeam": "Newcastle",
   "fecha": _pd.Timestamp("2026-10-25 00:00"), "FTHG": 0.0, "FTAG": 2.0,
   "HC": 7.0, "AC": 4.0, "HY": 3.0, "AY": 3.0, "HS": 12.0, "AS": 9.0,
   "HST": 4.0, "AST": 5.0, "savH": 3.0, "savA": 4.0,
   "kH": R.canon("Crystal Palace"), "kA": R.canon("Newcastle")},
])
def _pick(key, grupo):
    return {"id": f"cp-{key}", "lg": "premier", "home": "Crystal Palace", "away": "Newcastle",
            "ko": _ko, "key": key, "label": key, "cat": "c", "grupo": grupo,
            "p": 0.75, "cuota": 1.33, "estado": "pendiente", "resultado": None}
_ps = [_pick("X2", "resultado"), _pick("O1.5", "goles"),
       _pick("cor_m_o8.5", "estadisticas"), _pick("yel_m_o4.5", "estadisticas"),
       _pick("sav_h_u4.5", "estadisticas")]
_n = _settle(_ps, _filas, datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc))
for q in _ps:
    print(f"   {q['key']:12s} {q['grupo']:12s} -> {q['estado']}")
sin = [q for q in _ps if q["estado"] == "pendiente"]
assert not sin, f"quedaron sin liquidar: {[q['key'] for q in sin]} (la fuente sin stats tapo a la otra)"
assert _n["sin_datos"] == 0, f"sin_datos={_n['sin_datos']}"
print("  las cinco liquidaron, incluidas las de estadisticas: ok")
print("\nESCENARIO 8 OK")


print("\n" + "=" * 70)
print("ESCENARIO 9: combinada cuyo pick ya no existe")
# Siete combinadas del 30/10 al 3/11 quedaron en "pendiente" para siempre con las
# patas ya ganadas: el pick de una pata habia desaparecido de picks.json, porque al
# recotizar un partido se reemplaza entero y el deduplicador deja uno por grupo.
# La combinada tiene que liquidarse contra el resultado, como un pick.
from refresh import indices as _indices, settle_parlays as _sp
_ko9 = "2026-11-03T20:00:00Z"
_D9 = _pd.DataFrame([
  {"HomeTeam": "Bayern Munich", "AwayTeam": "Arsenal",
   "fecha": _pd.Timestamp("2026-11-03 20:00"), "FTHG": 3.0, "FTAG": 1.0,
   "HC": 6.0, "AC": 3.0, "HY": 1.0, "AY": 2.0, "HS": 14.0, "AS": 7.0,
   "HST": 6.0, "AST": 2.0, "savH": 1.0, "savA": 3.0,
   "kH": R.canon("Bayern Munich"), "kA": R.canon("Arsenal")},
  {"HomeTeam": "Inter", "AwayTeam": "Roma",
   "fecha": _pd.Timestamp("2026-11-03 20:00"), "FTHG": 0.0, "FTAG": 1.0,
   "HC": 5.0, "AC": 5.0, "HY": 2.0, "AY": 2.0, "HS": 11.0, "AS": 8.0,
   "HST": 3.0, "AST": 4.0, "savH": 3.0, "savA": 3.0,
   "kH": R.canon("Inter"), "kA": R.canon("Roma")},
])
_idx9, _dia9 = _indices(_D9)


def _leg(pid, home, away, key):
    return {"id": pid, "lg": "ucl", "liga": "ucl", "home": home, "away": away,
            "label": key, "p": 0.75, "ko": _ko9, "key": key, "cuota": 1.33}


# el pick de la primera pata sigue vivo y ganado; el de la segunda ya no existe
_picks9 = [{"id": "vive", "lg": "ucl", "home": "Bayern Munich", "away": "Arsenal",
            "ko": _ko9, "key": "1X", "label": "1X", "cat": "c", "grupo": "resultado",
            "p": 0.75, "cuota": 1.33, "estado": "ganado", "resultado": "3-1"}]
_t_gana = {"id": "t-gana", "tipo": "dia", "alcance": "2026-11-03", "estado": "pendiente",
           "patas": 2, "prob": 0.5, "cuota": 1.8,
           "legs": [_leg("vive", "Bayern Munich", "Arsenal", "1X"),
                    _leg("borrado", "Inter", "Roma", "X2")]}
_t_pierde = {"id": "t-pierde", "tipo": "dia", "alcance": "2026-11-03", "estado": "pendiente",
             "patas": 2, "prob": 0.5, "cuota": 1.8,
             "legs": [_leg("vive", "Bayern Munich", "Arsenal", "1X"),
                      _leg("borrado2", "Inter", "Roma", "1")]}
# partido que todavia no se jugo: tiene que seguir pendiente de verdad
_t_abre = {"id": "t-abre", "tipo": "dia", "alcance": "2026-11-24", "estado": "pendiente",
           "patas": 2, "prob": 0.5, "cuota": 1.8,
           "legs": [_leg("vive", "Bayern Munich", "Arsenal", "1X"),
                    {"id": "nadie", "lg": "ucl", "liga": "ucl", "home": "Lille",
                     "away": "Porto", "label": "1X", "p": 0.75,
                     "ko": "2026-11-24T20:00:00Z", "key": "1X", "cuota": 1.33}]}
_ts9 = [_t_gana, _t_pierde, _t_abre]
_sp(_ts9, _picks9, _idx9, _dia9)
for q in _ts9:
    print(f"   {q['id']:10s} -> {q['estado']}")
assert _t_gana["estado"] == "ganado", f"Inter 0-1 Roma hace ganar el X2: {_t_gana['estado']}"
assert _t_pierde["estado"] == "perdido", f"Inter 0-1 Roma hace perder el 1: {_t_pierde['estado']}"
assert _t_abre["estado"] == "pendiente", f"sin resultado no se liquida: {_t_abre['estado']}"

# sin indices (compatibilidad) no debe inventar nada
_t2 = {"id": "t2", "tipo": "dia", "alcance": "2026-11-03", "estado": "pendiente",
       "patas": 2, "prob": 0.5, "cuota": 1.8, "legs": _t_gana["legs"]}
_sp([_t2], _picks9)
assert _t2["estado"] == "pendiente", "sin indices tiene que quedarse quieta"
print("  la pata sin pick se liquida contra el resultado, y sin resultado no: ok")
print("\nESCENARIO 9 OK")

# --------------------------------------------------------------------------- 10
print()
from refresh import calibrate, build_picks, MIN_LIQ_GRUPO  # noqa: E402
_AHORA_10 = R.datetime(2026, 11, 26, 12, 0, tzinfo=R.timezone.utc)
print("ESCENARIO 10: corregir la probabilidad por grupo, no con un umbral global")
# Por que: con 458 picks liquidados, resultado y goles estaban calibrados y
# estadisticas predecia 86.8% y acertaba 77.4% (z -3.07). Un umbral global reparte
# ese castigo entre los tres y no corrige a ninguno, y la probabilidad publicada
# sigue inflada; las combinadas la multiplican y a cinco patas daba 46.2% predicho
# contra 17.2% real.


def _lote(grupo, n, p, aciertos):
    """n picks de un grupo, todos con probabilidad p, de los que aciertan `aciertos`."""
    return [{"grupo": grupo, "p": p, "ko": f"2026-10-{1 + i % 28:02d}T20:00:00Z",
             "estado": "ganado" if i < aciertos else "perdido"} for i in range(n)]


# estadisticas: dice 88% y acierta 77 de 100. goles: dice 78% y acierta 78 de 100.
_cal = calibrate(_lote("estadisticas", 100, 0.88, 77) + _lote("goles", 100, 0.78, 78))
print(f"   estadisticas: {_cal['porGrupo']['estadisticas']}")
print(f"   goles:        {_cal['porGrupo']['goles']}")
assert "estadisticas" in _cal["factores"], "el grupo inflado tiene que corregirse"
assert "goles" not in _cal["factores"], "el grupo calibrado no se toca"
_c = _cal["factores"]["estadisticas"]
# 0.5 + c(0.88-0.5) tiene que dar cerca del 77% real
assert abs((0.5 + _c * 0.38) - 0.77) < 0.01, f"el factor no reproduce el real: {_c}"

# un grupo que acierta MAS de lo que dice no se infla nunca
_sube = calibrate(_lote("goles", 100, 0.70, 85))
assert not _sube["factores"], f"nunca se infla: {_sube['factores']}"
print("   un grupo que acierta mas de lo que dice se deja como esta: ok")

# muestra chica: no se persigue ruido
_poco = calibrate(_lote("estadisticas", 20, 0.88, 12))
assert not _poco["factores"], f"con 20 picks no se corrige: {_poco['factores']}"
print(f"   con 20 picks no se corrige (minimo {MIN_LIQ_GRUPO}): ok")

# y el factor se aplica ANTES del umbral y de la cuota justa
_fx10 = [{"lg": "premier", "home": "Arsenal", "away": "Everton", "ko": "2026-11-28T20:00:00Z",
          "pH": 0.72, "pD": 0.18, "pA": 0.10, "kH": "arsenal", "kA": "everton",
          "b365": {}, "mejor": {}, "quien": {}}]
_sin = build_picks(_fx10, {}, 0.68, ahora=_AHORA_10)
_con = build_picks(_fx10, {}, 0.68, ahora=_AHORA_10, factores={"resultado": 0.70})
_d_sin = {p["key"]: p for p in _sin if p["grupo"] == "resultado"}
_d_con = {p["key"]: p for p in _con if p["grupo"] == "resultado"}
print(f"   sin factor: {sorted((k, v['p']) for k, v in _d_sin.items())}")
print(f"   con factor: {sorted((k, v['p']) for k, v in _d_con.items())}")
assert _d_con, "con factor tiene que quedar al menos un pick"
for k, v in _d_con.items():
    cruda = _d_sin[k]["p"]
    assert abs(v["p"] - (0.5 + 0.70 * (cruda - 0.5))) < 0.002, f"{k}: no se encogio bien"
    assert v["pModelo"] == cruda, f"{k}: se perdio la probabilidad cruda del modelo"
    assert "pModelo" not in _d_sin[k], f"{k}: sin correccion no hace falta guardarla"
    assert abs(v["cuota"] - round(1 / v["p"], 2)) < 0.011, f"{k}: la cuota justa quedo sobre la cruda"
    assert v["p"] > 0.68, f"{k}: quedo por debajo del umbral y no debia publicarse"
# lo que cae por debajo del umbral al corregirse deja de ofrecerse
assert len(_d_con) <= len(_d_sin), "corregir no puede agregar picks"
print("   se corrige antes del umbral y la cuota justa sale de la corregida: ok")
print("\nESCENARIO 10 OK")
