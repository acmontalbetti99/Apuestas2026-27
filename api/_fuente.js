// Lo que comparten /api/vivo y /api/final: las dos leen el mismo feed de
// LiveScore y tienen que quedarse exactamente con las mismas competencias. Antes
// el filtro estaba copiado en vivo.js; con dos copias, agregar una competencia en
// una y olvidarla en la otra deja el marcador y la liquidacion en desacuerdo.
//
// El prefijo _ es lo que hace que Vercel NO publique este archivo como ruta.

const BASE = "https://prod-public-api.livescore.com/v1/api/app";

const CABECERAS = {
  "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " +
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  "Referer": "https://www.livescore.com/",
  "Accept": "application/json, text/plain, */*",
};

// Competencias donde LiveScore pone la competencia en Cnm. Se compara el nombre
// COMPLETO, no por substring: hay homonimas de otras confederaciones (Cnm="Africa",
// Snm="CAF Champions League") que no son las nuestras.
const COMPETENCIAS = new Set([
  "champions league", "europa league", "conference league",
  "uefa champions league", "uefa europa league", "uefa conference league",
  "uefa europa conference league", "europa conference league",
  "nations league", "uefa nations league",
  "africa cup of nations", "copa america", "conmebol copa america",
  "world cup qualification",
]);

// Ligas domesticas: ahi el pais va en Cnm y la liga en Snm.
const PAISES = new Map([
  ["england|premier league", "premier"],
  ["spain|laliga", "laliga"],
  ["italy|serie a", "seriea"],
  ["germany|bundesliga", "bundesliga"],
]);

// Nunca femenino ni juveniles, igual que el resto de la app.
const EXCLUIR = ["women", "femen", "femin", "femmin", "frauen", "dames", "ladies",
                 "youth", "u17", "u19", "u20", "u21", "u23"];

const TERMINADO = /^(FT|AET|AP|FT_PEN|Finished)$/i;

function canon(s) {
  return String(s || "")
    .normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .replace(/ł/g, "l").replace(/ø/g, "o").replace(/đ/g, "d")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

// Saca de la respuesta los partidos de nuestras competencias. `soloFinal` deja
// unicamente los terminados, que es lo que sirve para liquidar.
function extraer(datos, soloFinal = false) {
  const out = [];
  for (const stg of datos?.Stages || []) {
    const cnm = String(stg.Cnm || "").toLowerCase().trim();
    const snm = String(stg.Snm || "").toLowerCase().trim();
    if (EXCLUIR.some((w) => `${cnm} ${snm}`.includes(w))) continue;
    // Cnm o Snm, siempre por nombre completo: en las copas de clubes la competencia
    // viene en Cnm, pero la Nations League puede llegar como Cnm="Europe" con
    // Snm="UEFA Nations League". Comparar completo deja afuera a las homonimas de
    // otras confederaciones, que no estan en el set. Misma regla que livescore.py.
    const lg = COMPETENCIAS.has(cnm) ? cnm
             : COMPETENCIAS.has(snm) ? snm
             : PAISES.get(`${cnm}|${snm}`);
    if (!lg) continue;

    for (const e of stg.Events || []) {
      const h = e.T1?.[0]?.Nm, a = e.T2?.[0]?.Nm;
      if (!h || !a) continue;
      const est = String(e.Eps ?? "");
      if (soloFinal && !TERMINADO.test(est)) continue;
      out.push({
        lg, h: canon(h), a: canon(a), hn: h, an: a,
        hg: Number(e.Tr1 ?? 0), ag: Number(e.Tr2 ?? 0), est,
      });
    }
  }
  return out;
}

async function pedir(ruta, ms = 8000) {
  const r = await fetch(`${BASE}${ruta}`, {
    headers: CABECERAS, signal: AbortSignal.timeout(ms),
  });
  if (!r.ok) throw new Error(`fuente HTTP ${r.status}`);
  return r.json();
}

// YYYYMMDD en UTC, que es como indexa el feed por fecha.
function diaUTC(desplazamiento = 0) {
  const d = new Date(Date.now() + desplazamiento * 86400e3);
  return d.toISOString().slice(0, 10).replace(/-/g, "");
}

export { extraer, pedir, canon, diaUTC, TERMINADO };
