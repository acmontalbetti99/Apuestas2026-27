# Auditoria · 2026-10-24 16:11 UTC

**0 de severidad alta · 2 media · 1 baja**

## 🟡 Media

- **[liquidacion]** 3 picks de Bundesliga sin liquidar tras 21 h (suele ser un nombre de equipo que no coincide)
  - `Stuttgart v Monchengladbach (2026-10-23T19:30)`
  - `Stuttgart v Monchengladbach (2026-10-23T19:30)`
  - `Stuttgart v Monchengladbach (2026-10-23T19:30)`
- **[cobertura]** sin ODDS_API_KEY no se generan picks de Conference League: football-data solo publica ligas domesticas

## ⚪ Baja

- **[valor]** ninguno de los 26 picks con precio supera la cuota justa: valor medio -5.17%. Es lo esperable, pero conviene no apostarlos

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 54 | 79.2% | 75.9% | -0.60 |
| resultado | 40 | 79.3% | 77.5% | -0.28 |
| banda 0.70-0.75 | 15 | 73.2% | 66.7% | -0.58 |
| banda 0.75-0.80 | 15 | 76.8% | 60.0% | -1.55 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 26 de 129 picks pendientes traen precio de la casa
- 0 superan la cuota justa · valor medio -5.17%

