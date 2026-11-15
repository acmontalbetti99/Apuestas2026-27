# Auditoria · 2026-11-15 17:27 UTC

**1 de severidad alta · 1 media · 2 baja**

## 🔴 Alta

- **[liquidacion]** 4 picks de Nations League sin liquidar tras 72 h (un nombre de equipo que no coincide, o la estadistica que el mercado necesita que la fuente nunca publico)
  - `Turkey v Belgium (2026-11-12T17:00)`
  - `Turkey v Belgium (2026-11-12T17:00)`
  - `Austria v Iceland (2026-11-14T19:45)`
  - `Austria v Iceland (2026-11-14T19:45)`

## 🟡 Media

- **[sitio]** el sitio publica 591 picks y el repo tiene 607: el despliegue quedo atras

## ⚪ Baja

- **[calibracion]** estadisticas/tiros: 68.9% real contra 86.7% predicho sobre 45 (z=-3.52), ya corregido con factor 0.515
- **[valor]** ningun pick pendiente trae precio de bet365: sin eso no se puede saber cual tiene valor de verdad

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 506 | 80.7% | 77.7% | -1.75 |
| estadisticas/corners-tarjetas | 79 | 86.8% | 82.3% | -1.19 |
| estadisticas/tiros | 45 | 86.7% | 68.9% | -3.52 |
| goles | 149 | 78.1% | 77.8% | -0.07 |
| resultado | 233 | 79.2% | 77.7% | -0.56 |
| banda 0.70-0.75 | 95 | 73.4% | 66.3% | -1.56 |
| banda 0.75-0.80 | 141 | 77.1% | 79.4% | +0.65 |
| banda 0.80-0.85 | 87 | 82.6% | 80.5% | -0.53 |
| banda 0.85-0.90 | 175 | 87.1% | 81.1% | -2.36 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 0 de 101 picks pendientes traen precio de la casa

