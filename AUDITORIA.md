# Auditoria · 2026-11-17 19:27 UTC

**1 de severidad alta · 3 media · 2 baja**

## 🔴 Alta

- **[liquidacion]** 3 picks de Nations League sin liquidar tras 72 h (un nombre de equipo que no coincide, o la estadistica que el mercado necesita que la fuente nunca publico)
  - `Austria v Iceland (2026-11-14T19:45)`
  - `Austria v Iceland (2026-11-14T19:45)`
  - `France v Turkey (2026-11-15T19:45)`

## 🟡 Media

- **[combinadas]** dia-2026-11-12-3patas-84d8900a sigue abierta y tiene patas sin pick de un partido ya jugado
  - `turkey__belgium__12`
- **[combinadas]** dia-2026-11-12-4patas-199dbc8f sigue abierta y tiene patas sin pick de un partido ya jugado
  - `turkey__belgium__o1-5`
- **[combinadas]** fecha-2026-11-12-a-2026-11-14-3patas-d4344dd9 sigue abierta y tiene patas sin pick de un partido ya jugado
  - `turkey__belgium__12`

## ⚪ Baja

- **[calibracion]** estadisticas/tiros: 68.9% real contra 86.7% predicho sobre 45 (z=-3.52), ya corregido con factor 0.515
- **[valor]** ningun pick pendiente trae precio de bet365: sin eso no se puede saber cual tiene valor de verdad

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 532 | 80.7% | 78.6% | -1.23 |
| estadisticas/corners-tarjetas | 79 | 86.8% | 82.3% | -1.19 |
| estadisticas/tiros | 45 | 86.7% | 68.9% | -3.52 |
| goles | 161 | 78.1% | 78.9% | +0.24 |
| resultado | 247 | 79.3% | 79.0% | -0.12 |
| banda 0.70-0.75 | 99 | 73.4% | 67.7% | -1.29 |
| banda 0.75-0.80 | 152 | 77.1% | 80.3% | +0.92 |
| banda 0.80-0.85 | 92 | 82.6% | 81.5% | -0.26 |
| banda 0.85-0.90 | 181 | 87.1% | 81.8% | -2.15 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 0 de 73 picks pendientes traen precio de la casa

