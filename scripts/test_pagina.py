#!/usr/bin/env python3
"""Humo de la pagina: que cargue y renderice, con los datos reales del repo.

Existe por un error concreto: editando index.html por posicion de texto borre sin
darme cuenta todo el bloque del marcador en vivo. render() llamaba a una funcion
que ya no existia, la excepcion cortaba el primer render y la app quedo en
"Cargando..." en produccion. Los tests de Python pasaban, porque el problema
estaba del lado del navegador.

Corre Chromium contra index.html y los JSON de data/, y falla si hay un error de
JavaScript o si alguna pestana queda vacia.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROMIUM = "/opt/pw-browsers/chromium"
PESTANAS = [("picks", "article.pick"), ("combis", ".ticket"),
            ("historial", "article.pick"), ("precision", "tr")]


def servir(w: Path, puerto: int) -> subprocess.Popen:
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(puerto), "-d", str(w)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    return srv


def humo_liquidacion(pw) -> list[str]:
    """Que la pagina liquide sola con /api/final, sin esperar a Actions.

    Existe porque es el camino critico nuevo: GitHub honra 3 a 6 de los ~23 turnos
    de cron por dia, asi que esto es lo que decide si el usuario ve el resultado
    cuando termina el partido o una hora y media despues.
    """
    ayer = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7200))
    picks = [
        # terminados 2-1: 1X acierta, 12 acierta, O1.5 acierta, U3.5 acierta
        dict(id="a", lg="ucl", home="Slavia Praha", away="Arsenal", ko=ayer, key="1X",
             label="Local o empate", cat="Doble oportunidad", grupo="resultado",
             p=0.7, cuota=1.3, estado="pendiente", resultado=None),
        dict(id="b", lg="ucl", home="Slavia Praha", away="Arsenal", ko=ayer, key="O1.5",
             label="Mas de 1.5 goles", cat="Goles", grupo="goles",
             p=0.7, cuota=1.3, estado="pendiente", resultado=None),
        # terminado 0-0: X2 acierta, O1.5 falla
        dict(id="c", lg="uel", home="Rennes", away="Olympiakos Piraeus", ko=ayer, key="O1.5",
             label="Mas de 1.5 goles", cat="Goles", grupo="goles",
             p=0.7, cuota=1.3, estado="pendiente", resultado=None),
        # estadisticas: no sale del marcador, tiene que seguir esperando
        dict(id="d", lg="premier", home="Sunderland", away="Leeds United", ko=ayer,
             key="yel_a_u3.5", label="Menos de 3.5 amarillas visitante", cat="Tarjetas",
             grupo="estadisticas", p=0.7, cuota=1.3, estado="pendiente", resultado=None),
        # partido que la fuente no trae: tampoco se toca
        dict(id="e", lg="laliga", home="Getafe", away="Osasuna", ko=ayer, key="1X",
             label="Local o empate", cat="Doble oportunidad", grupo="resultado",
             p=0.7, cuota=1.3, estado="pendiente", resultado=None),
    ]
    legs = [{"id": x["id"], "lg": x["lg"], "liga": x["lg"], "home": x["home"],
             "away": x["away"], "label": x["label"], "p": x["p"], "ko": x["ko"],
             "key": x["key"], "cuota": 1.3} for x in picks[:3]]
    parlays = [{"id": "t1", "jornada": ayer[:10], "tipo": "dia", "alcance": ayer[:10],
                "patas": 3, "prob": 0.4, "cuota": 2.2, "legs": legs, "estado": "pendiente"}]
    # LiveScore nombra la ciudad en ingles: el mismo caso que dejo el pick sin liquidar.
    final = {"ts": 0, "partidos": [
        {"lg": "ucl", "h": "slavia-prague", "a": "arsenal", "hn": "Slavia Prague",
         "an": "Arsenal", "hg": 2, "ag": 1, "est": "FT"},
        {"lg": "uel", "h": "rennes", "a": "olympiacos", "hn": "Rennes",
         "an": "Olympiacos", "hg": 0, "ag": 0, "est": "FT"},
        # en curso: no debe liquidar nada
        {"lg": "premier", "h": "sunderland", "a": "leeds-united", "hn": "Sunderland",
         "an": "Leeds United", "hg": 1, "ag": 0, "est": "63'"},
    ]}

    w = Path(tempfile.mkdtemp(prefix="montoglory-liq-"))
    shutil.copy(ROOT / "index.html", w / "index.html")
    (w / "data").mkdir()
    (w / "data" / "picks.json").write_text(json.dumps(picks))
    (w / "data" / "parlays.json").write_text(json.dumps(parlays))
    (w / "data" / "estado.json").write_text(json.dumps({"fecha": ayer, "conCuotas": []}))
    (w / "api").mkdir()
    (w / "api" / "vivo").write_text(json.dumps({"ts": 0, "partidos": []}))
    (w / "api" / "final").write_text(json.dumps(final))

    esperado = {"a": ("ganado", "2-1"), "b": ("ganado", "2-1"), "c": ("perdido", "0-0")}
    fallas: list[str] = []
    srv = servir(w, 8813)
    try:
        b = pw.chromium.launch(executable_path=CHROMIUM)
        pg = b.new_page(viewport={"width": 1150, "height": 900})
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8813/index.html", wait_until="networkidle")
        pg.wait_for_timeout(1500)
        fallas += [f"error de JavaScript: {e}" for e in errs]
        got = {p["id"]: (p["estado"], p["resultado"], bool(p.get("provisional")))
               for p in pg.evaluate("PICKS.map(p=>({id:p.id,estado:p.estado,"
                                    "resultado:p.resultado,provisional:p.provisional}))")}
        for pid, (est, res) in esperado.items():
            g = got.get(pid)
            print(f"  {pid}: {g}")
            if not g or g[0] != est or g[1] != res or not g[2]:
                fallas.append(f"el pick {pid} tenia que quedar {est} {res}, quedo {g}")
        for pid in ("d", "e"):
            g = got.get(pid)
            print(f"  {pid}: {g}")
            if not g or g[0] != "pendiente":
                fallas.append(f"el pick {pid} no sale del marcador y no debia liquidarse: {g}")
        tk = pg.evaluate("TICKETS.map(t=>t.estado)")
        print(f"  combinada: {tk}")
        if tk != ["perdido"]:
            fallas.append(f"la combinada tenia una pata perdida y debia caerse: {tk}")

        # El mismo corpus que usa el matcher de Python. Los dos tienen que dar lo
        # mismo: si la pagina reconoce menos nombres, muestra "Esperando resultado"
        # sobre partidos que el pipeline ya liquido, y si reconoce mas, liquida algo
        # que el pipeline despues contradice.
        casos = json.loads((ROOT / "scripts" / "casos_nombres.json").read_text("utf-8"))
        res = pg.evaluate(
            "cs=>({equipo:cs.equipo.map(([a,b])=>compartenFicha(a,b)),"
            "partido:cs.partido.map(([p,q])=>compartenFicha(p[0],q[0])&&compartenFicha(p[1],q[1]))})",
            {"equipo": [c[:2] for c in casos["equipo"]],
             "partido": [c[:2] for c in casos["partido"]]})
        for clase in ("equipo", "partido"):
            for caso, dio in zip(casos[clase], res[clase]):
                if dio != caso[-1]:
                    fallas.append(f"el matcher de la pagina difiere del de Python en "
                                  f"{clase} {caso[0]} / {caso[1]}: dio {dio}")
        print(f"  matcher: {len(casos['equipo'])} equipos y {len(casos['partido'])} "
              f"partidos comparados contra el corpus de Python")
        b.close()
    finally:
        srv.terminate()
    return fallas


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright no instalado, se saltea el humo de la pagina")
        return 0

    w = Path(tempfile.mkdtemp(prefix="montoglory-humo-"))
    shutil.copy(ROOT / "index.html", w / "index.html")
    (w / "data").mkdir()
    for f in ("picks.json", "parlays.json", "estado.json"):
        if (ROOT / "data" / f).exists():
            shutil.copy(ROOT / "data" / f, w / "data" / f)
    # /api/vivo no existe fuera de Vercel: se simula vacio para no falsear el humo
    (w / "api").mkdir()
    (w / "api" / "vivo").write_text(json.dumps({"ts": 0, "partidos": []}))

    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8812", "-d", str(w)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    fallas: list[str] = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=CHROMIUM)
            pg = b.new_page(viewport={"width": 1150, "height": 900})
            errs: list[str] = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto("http://localhost:8812/index.html", wait_until="networkidle")
            pg.wait_for_timeout(1200)
            if errs:
                fallas += [f"error de JavaScript: {e}" for e in errs]
            for tab, sel in PESTANAS:
                pg.click(f'button[data-t="{tab}"]')
                pg.wait_for_timeout(350)
                n = pg.locator(f"#p-{tab} {sel}").count()
                vacio = pg.locator(f"#p-{tab} .empty").count()
                print(f"  {tab:10s} {n:4d} elementos" + ("  (vista vacia)" if vacio else ""))
                # Una pestana puede estar legitimamente vacia (sin picks abiertos),
                # pero entonces tiene que decirlo con su cartel, no quedar en blanco.
                if n == 0 and not vacio:
                    fallas.append(f"la pestana {tab} no renderizo nada ni mostro un vacio")
                if pg.locator(f"#p-{tab}").inner_text().startswith("Cargando"):
                    fallas.append(f"la pestana {tab} se quedo en 'Cargando'")
            b.close()
            print("\nliquidacion con /api/final:")
            fallas += humo_liquidacion(pw)
    finally:
        srv.terminate()

    for f in fallas:
        print(f"   MAL {f}")
    if fallas:
        print(f"\n{len(fallas)} fallas en la pagina")
        return 1
    print("\nla pagina carga y renderiza sin errores de JavaScript")
    return 0


if __name__ == "__main__":
    sys.exit(main())
