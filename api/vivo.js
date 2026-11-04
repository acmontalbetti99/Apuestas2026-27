// Marcador y minuto en vivo, para la columna de la derecha de cada pick.
//
// Por que una funcion y no el JSON de siempre: data/picks.json lo regenera Actions
// cuando corre, y un marcador que se actualiza asi no es en vivo. Esta funcion
// consulta LiveScore al vuelo y la pagina la llama cada 45 s mientras haya
// partidos jugandose.
//
// El endpoint /live/ devuelve SOLO lo que esta en curso, asi que la respuesta es
// chica (unos pocos kB) aunque haya futbol en todo el mundo. El reverso es que un
// partido terminado desaparece: los finales salen de /api/final.
//
// El filtro de competencias vive en _fuente.js, compartido con /api/final.

import { extraer, pedir } from "./_fuente.js";

export default async function handler(req, res) {
  // La pagina la llama seguido; 20 s de cache en el edge alcanzan para no castigar
  // la fuente y el minuto igual se mueve a tiempo.
  res.setHeader("Cache-Control", "public, s-maxage=20, stale-while-revalidate=40");

  try {
    const partidos = extraer(await pedir("/live/soccer/0"));
    res.status(200).json({ ts: Date.now(), partidos });
  } catch (e) {
    // Nunca romper la pagina por esto: sin marcador en vivo la app sigue sirviendo.
    res.status(200).json({ partidos: [], error: String(e.message || e) });
  }
}
