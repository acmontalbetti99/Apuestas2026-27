# Auditoria · 2026-11-14 16:46 UTC

**0 de severidad alta · 2 media · 2 baja**

## 🟡 Media

- **[liquidacion]** 2 picks de Nations League sin liquidar tras 48 h (un nombre de equipo que no coincide, o la estadistica que el mercado necesita que la fuente nunca publico)
  - `Turkey v Belgium (2026-11-12T17:00)`
  - `Turkey v Belgium (2026-11-12T17:00)`
- **[sitio]** el sitio publica 560 picks y el repo tiene 591: el despliegue quedo atras

## ⚪ Baja

- **[calibracion]** estadisticas/tiros: 68.9% real contra 86.7% predicho sobre 45 (z=-3.52), ya corregido con factor 0.515
- **[valor]** ningun pick pendiente trae precio de bet365: sin eso no se puede saber cual tiene valor de verdad

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 491 | 80.8% | 78.0% | -1.58 |
| estadisticas/corners-tarjetas | 79 | 86.8% | 82.3% | -1.19 |
| estadisticas/tiros | 45 | 86.7% | 68.9% | -3.52 |
| goles | 143 | 78.1% | 78.3% | +0.07 |
| resultado | 224 | 79.2% | 78.1% | -0.40 |
| banda 0.70-0.75 | 91 | 73.4% | 67.0% | -1.38 |
| banda 0.75-0.80 | 138 | 77.1% | 79.7% | +0.72 |
| banda 0.80-0.85 | 82 | 82.7% | 81.7% | -0.23 |
| banda 0.85-0.90 | 173 | 87.1% | 80.9% | -2.43 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 0 de 100 picks pendientes traen precio de la casa

