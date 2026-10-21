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
