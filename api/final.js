// Resultados finales del dia, para que la pagina liquide sin esperar a que corra
// GitHub Actions.
//
// Por que hace falta: el cron de Actions esta programado cada 30 minutos entre las
// 13:00 y las 23:30 UTC, pero GitHub honra solo 3 a 6 de esos ~23 turnos por dia
// (medido sobre dos semanas de corridas). El 4 de noviembre los partidos de las
// 20:00 UTC terminaron cerca de las 21:50 y la primera corrida posterior fue a
// mano, pasadas las 23:20: casi hora y media con el resultado puesto y el pick
// todavia en "Esperando resultado".
//
// Esta funcion devuelve los partidos YA TERMINADOS de hoy y de ayer (en UTC, que
// es como indexa el feed). La pagina los usa para liquidar los mercados que
// dependen solo del marcador: resultado y total de goles. Cornners, tarjetas,
// remates y atajadas no salen de aca y los sigue liquidando football-data en la
// corrida diaria, que es la unica fuente que los publica.
//
// Lo que escribe el repo no cambia: Actions sigue siendo quien liquida de verdad
// y deja el historial. Esto solo adelanta lo que se ve, con la misma fuente y la
// misma cuenta, asi que cuando Actions corre el numero ya coincide.

import { extraer, pedir, diaUTC } from "./_fuente.js";

export default async function handler(req, res) {
  // Un partido que termino no vuelve a cambiar, asi que 60 s de cache en el edge
  // no retrasan nada y evitan castigar la fuente con cada visita.
  res.setHeader("Cache-Control", "public, s-maxage=60, stale-while-revalidate=120");

  // Ayer tambien: a las 00:30 de Lima siguen cerrando partidos que para UTC ya
  // son del dia anterior.
  const dias = [diaUTC(0), diaUTC(-1)];
  const partidos = [];
  const errores = [];

  for (const d of dias) {
    try {
      partidos.push(...extraer(await pedir(`/date/soccer/${d}/0`), true));
    } catch (e) {
      errores.push(`${d}: ${e.message || e}`);
    }
  }

  // Nunca romper la pagina por esto: sin esta respuesta la app sigue sirviendo,
  // solo que los picks quedan esperando a que corra Actions.
  res.status(200).json({
    ts: Date.now(),
    partidos,
    ...(errores.length ? { error: errores.join(" | ") } : {}),
  });
}
