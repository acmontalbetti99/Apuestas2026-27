# Auditoria · 2026-11-26 19:52 UTC

**0 de severidad alta · 0 media · 2 baja**

## ⚪ Baja

- **[calibracion]** estadisticas/tiros: 68.9% real contra 86.7% predicho sobre 45 (z=-3.52), ya corregido con factor 0.515
- **[valor]** ningun pick pendiente trae precio de bet365: sin eso no se puede saber cual tiene valor de verdad

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 735 | 80.9% | 80.0% | -0.60 |
| estadisticas/corners-tarjetas | 118 | 86.5% | 86.4% | -0.01 |
| estadisticas/tiros | 45 | 86.7% | 68.9% | -3.52 |
| goles | 243 | 78.8% | 78.6% | -0.07 |
| resultado | 329 | 79.6% | 80.2% | +0.31 |
| banda 0.70-0.75 | 130 | 73.4% | 70.8% | -0.69 |
| banda 0.75-0.80 | 206 | 77.2% | 79.6% | +0.81 |
| banda 0.80-0.85 | 141 | 82.6% | 80.8% | -0.55 |
| banda 0.85-0.90 | 250 | 87.1% | 84.8% | -1.08 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 0 de 53 picks pendientes traen precio de la casa

