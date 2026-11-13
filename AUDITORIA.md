# Auditoria · 2026-11-13 18:09 UTC

**0 de severidad alta · 2 media · 3 baja**

## 🟡 Media

- **[liquidacion]** 2 picks de Nations League sin liquidar tras 25 h (un nombre de equipo que no coincide, o la estadistica que el mercado necesita que la fuente nunca publico)
  - `Turkey v Belgium (2026-11-12T17:00)`
  - `Turkey v Belgium (2026-11-12T17:00)`
- **[sitio]** el sitio publica 551 picks y el repo tiene 560: el despliegue quedo atras

## ⚪ Baja

- **[calibracion]** estadisticas/tiros: 68.9% real contra 86.7% predicho sobre 45 (z=-3.52), ya corregido con factor 0.515
- **[calibracion]** banda 85%-90%: 80.5% real contra 87.1% predicho sobre 169 (z=-2.58)
- **[valor]** ningun pick pendiente trae precio de bet365: sin eso no se puede saber cual tiene valor de verdad

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 471 | 80.9% | 77.9% | -1.66 |
| estadisticas/corners-tarjetas | 79 | 86.8% | 82.3% | -1.19 |
| estadisticas/tiros | 45 | 86.7% | 68.9% | -3.52 |
| goles | 134 | 78.3% | 79.1% | +0.22 |
| resultado | 213 | 79.1% | 77.5% | -0.59 |
| banda 0.70-0.75 | 89 | 73.5% | 68.5% | -1.05 |
| banda 0.75-0.80 | 134 | 77.1% | 79.1% | +0.54 |
| banda 0.80-0.85 | 77 | 82.7% | 80.5% | -0.50 |
| banda 0.85-0.90 | 169 | 87.1% | 80.5% | -2.58 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 0 de 89 picks pendientes traen precio de la casa

