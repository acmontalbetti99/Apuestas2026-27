// Marcador y minuto en vivo, para la columna de la derecha de cada pick.
//
// Por que una funcion y no el JSON de siempre: data/picks.json lo regenera Actions
// cada 30 minutos. Un marcador que se actualiza cada media hora no es en vivo, y un
// cronometro asi es peor que no tenerlo. Esta funcion consulta LiveScore al vuelo y
// la pagina la llama cada 45 s mientras haya partidos jugandose.
//
// El endpoint /live/ devuelve SOLO lo que esta en curso, asi que la respuesta es
// chica (unos pocos kB) aunque haya futbol en todo el mundo.

const FUENTE = "https://prod-public-api.livescore.com/v1/api/app/live/soccer/0";

// Las mismas competencias que sigue la app. Se compara el nombre completo, no por
// substring: hay homonimas de otras confederaciones (Cnm="Africa", Snm="CAF
// Champions League") que no son las nuestras.
const COMPETENCIAS = new Set([
  "champions league", "europa league", "conference league",
  "uefa champions league", "uefa europa league", "uefa conference league",
  "nations league", "africa cup of nations", "copa america",
  "world cup qualification",
]);
const PAISES = new Map([
  ["england|premier league", "premier"],
  ["spain|laliga", "laliga"],
  ["italy|serie a", "seriea"],
  ["germany|bundesliga", "bundesliga"],
]);
// Nunca futbol femenino ni juveniles, igual que el resto de la app.
const EXCLUIR = ["women", "femen", "femin", "femmin", "frauen", "dames", "ladies",
                 "youth", "u17", "u19", "u20", "u21", "u23"];

function canon(s) {
  return String(s || "")
    .normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default async function handler(req, res) {
  // La pagina la llama seguido; 20 s de cache en el edge alcanzan para no castigar
  // la fuente y el minuto igual se mueve a tiempo.
  res.setHeader("Cache-Control", "public, s-maxage=20, stale-while-revalidate=40");

  let datos;
  try {
    const r = await fetch(FUENTE, {
      headers: {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " +
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://www.livescore.com/",
        "Accept": "application/json, text/plain, */*",
      },
      signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) {
      return res.status(200).json({ partidos: [], error: `fuente HTTP ${r.status}` });
    }
    datos = await r.json();
  } catch (e) {
    // Nunca romper la pagina por esto: sin marcador en vivo la app sigue sirviendo.
    return res.status(200).json({ partidos: [], error: String(e.message || e) });
  }

  const partidos = [];
  for (const stg of datos?.Stages || []) {
    const cnm = String(stg.Cnm || "").toLowerCase().trim();
    const snm = String(stg.Snm || "").toLowerCase().trim();
    if (EXCLUIR.some((w) => `${cnm} ${snm}`.includes(w))) continue;
    const lg = COMPETENCIAS.has(cnm) ? cnm : PAISES.get(`${cnm}|${snm}`);
    if (!lg) continue;

    for (const e of stg.Events || []) {
      const h = e.T1?.[0]?.Nm, a = e.T2?.[0]?.Nm;
      if (!h || !a) continue;
      // Eps trae el minuto ("19'"), o HT / FT / NS segun el momento.
      partidos.push({
        h: canon(h), a: canon(a),
        hn: h, an: a,
        hg: Number(e.Tr1 ?? 0), ag: Number(e.Tr2 ?? 0),
        est: String(e.Eps ?? ""),
      });
    }
  }
  res.status(200).json({ ts: Date.now(), partidos });
}
