# Montoglory

Recomendaciones de apuestas para Premier League, La Liga, Serie A, Bundesliga y Champions League.
Solo se publica lo que el modelo da por encima del **65%**, y combinadas de **40% a 52%** de
probabilidad conjunta.

## Qué hay acá

| Ruta | Qué es |
| --- | --- |
| `index.html` | La app. Lee `data/*.json`; dentro de un artifact de Claude lee la base del artifact. |
| `data/picks.json` | Los picks abiertos y liquidados. |
| `data/parlays.json` | Las combinadas. |
| `data/calibracion.json` | Acierto real contra predicho, y el umbral vigente. |
| `.github/workflows/refresh.yml` | Refresco diario (ver abajo). |

## Cómo se calcula

**Resultado (1X2 y doble oportunidad).** Sale del mercado, sin modelo propio. Sobre 7.149 partidos
de 2021-2025 medí que las cuotas de cierre dan 0,9693 de pérdida logarítmica contra 0,9833 del mejor
modelo que pude construir, y que cualquier peso que se le dé al modelo propio empeora el resultado.

**Goles.** Superficie Dixon-Coles ajustada para que el total coincida con la media de la liga
corregida por desequilibrio (`goles = base × (1 + 0,3678 × |pH − pA|)`, medido sobre 11.567 partidos)
y el reparto coincida con el mercado.

**Córners, tarjetas, remates y atajadas.** Binomial negativa por lado — Poisson para tarjetas, cuya
varianza/media medida es 0,956 — con el ajuste por desequilibrio, que es el efecto grande:

| Supremacía del local | Córners L/V | Remates L/V | Atajadas L/V | Amarillas L/V |
| --- | --- | --- | --- | --- |
| Visitante muy favorito | 3,61 / 6,18 | 9,17 / 15,71 | 4,04 / 2,32 | 1,95 / 1,64 |
| Parejo | 5,07 / 4,66 | 12,59 / 11,54 | 2,85 / 3,09 | 2,17 / 2,27 |
| Local muy favorito | 6,78 / 3,38 | 16,94 / 8,66 | 2,20 / 4,27 | 1,55 / 2,14 |

Sobre esas probabilidades va una contracción de calibración `p' = 0,5 + c(p − 0,5)`, con
c = 0,965 córners, 0,995 tarjetas, 0,980 remates, 0,960 atajadas. Se ajustó sobre la primera mitad
de 2021-2025 y se verificó en la segunda: el desvío pasó de −0,93 a −0,32 puntos.

**Champions League.** La base histórica no tiene partidos de Champions, así que ahí solo se ofrecen
resultado y doble oportunidad, que salen del mercado y no dependen de esa base.

## Qué dio en la prueba

Sobre 7.229 partidos reales de 2021-2025:

| Grupo | Selecciones | Predicho | Real |
| --- | --- | --- | --- |
| Resultado y goles | 74.391 | 79,8% | **80,5%** |
| Córners, tarjetas, remates, atajadas | 213.359 | 76,3% | **75,9%** |
| Combinadas de 40-52% | 2.625 | 47,2% | **48,0%** |

## El refresco diario

Una tarea programada corre todos los días a las 05:50 (hora de Lima): liquida los partidos
terminados, mide el acierto acumulado, ajusta el umbral si el desvío lo justifica y genera los picks
de lo que viene. Hoy escribe en la base del artifact de Claude. Para que además actualice este repo
— y con eso Vercel redespliegue solo — hace falta darle permiso de escritura a la app de Claude
sobre este repositorio.

## Lo que esto no es

Nada de lo medido produce ganancia esperada positiva apostando a ciegas. El filtro del 65% selecciona
cuotas cortas, que es la banda donde el margen de la casa es más chico, pero el margen sigue estando.
La cuota justa que muestra cada pick es el precio a partir del cual la apuesta deja de perder valor:
si la casa paga menos que eso, la apuesta pierde aunque entre seguido.

## Los motores

En `scripts/` queda el codigo con el que se midio y se genera todo:

| Archivo | Que hace |
| --- | --- |
| `engine.py` | Superficie Dixon-Coles anclada al mercado. `fit_lambdas` resuelve la supremacia con `brentq` para que el reparto local/visitante coincida con las cuotas. |
| `stats_engine.py` | Corners, tarjetas, remates y atajadas. Binomial negativa por lado con el ajuste por desequilibrio y la contraccion de calibracion. |
| `picks2.py` | Genera los picks sobre el umbral y arma las combinadas (una pata por partido, sin equipos repetidos). |
| `fit_stats.py` / `val_stats.py` | Ajuste y verificacion fuera de muestra de la contraccion de calibracion. |
| `backtest.py` / `validate_picks.py` / `followup.py` | Backtest walk-forward: log loss, Brier, acierto por banda. |
| `factors.py` | La exploracion inicial de factores (arbitros, clima, rachas) y por que la mayoria no sobrevivio. |

`scripts/refresh.py` es el refresco diario y corre en GitHub Actions, no en la sesion de
Claude: el contenedor de Claude sale a internet por un proxy con lista blanca que rechaza
football-data.co.uk, y Actions no tiene esa restriccion. Hace cuatro cosas en orden: baja los
partidos jugados de las cuatro ligas, liquida los picks cuyo partido ya termino, mide el acierto
y mueve el umbral si el desvio lo justifica, y baja los proximos partidos con cuotas para generar
los picks y las combinadas. Si una descarga falla no escribe nada y sale en rojo, asi que un dia
caido deja los datos del dia anterior en lugar de datos a medias.

Champions League queda afuera del refresco: football-data.co.uk no publica cuotas ni resultados
de Champions, y los picks de Champions salen justamente del mercado. Un pick de Champions
pendiente sobrevive 3 dias despues del kickoff y despues se descarta, para que no entre como
acierto ni como fallo y no ensucie la medicion.

La ventana de `fixtures.csv` es corta: publica solo uno o dos dias de partidos, no la
jornada completa. Por eso el refresco es **aditivo** y nunca reconstruye la lista desde cero:
cada corrida suma los partidos que entraron en la ventana y arrastra los pendientes que
siguen vigentes. Un partido que se vuelve a cotizar se reemplaza completo, porque las cuotas
frescas mandan y asi se respeta la regla de un solo pick por partido y por grupo.

El umbral solo se mueve con 60 o mas picks liquidados, y solo hacia arriba: si el modelo viene
inflado 3 puntos, el filtro pasa de 65% a 68%. Con menos de 60 el error de muestra es mayor que
el ajuste, asi que no se toca.

## Las pruebas

`python scripts/test_refresh.py` corre el refresco entero contra descargas simuladas con la
forma real de football-data, sin tocar la red ni los datos del repo. Cubre tres escenarios:

1. Liquidacion de los 26 mercados, verificada a mano contra el partido, incluidas las
   atajadas (remates al arco del rival menos sus goles), el ajuste de umbral y que una
   descarga caida aborte sin escribir nada.
2. Un dia con `fixtures.csv` flaco no borra los pendientes que siguen vigentes.
3. Un pick pasado el kickoff que espera resultado no se borra, y un partido recotizado no
   deja picks viejos y nuevos mezclados en el mismo grupo.

Los escenarios 2 y 3 son regresiones: las dos cosas pasaron de verdad y estan ahi para que
no vuelvan a pasar.
