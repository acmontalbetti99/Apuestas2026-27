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
