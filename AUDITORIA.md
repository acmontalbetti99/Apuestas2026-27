# Auditoria · 2026-10-24 14:08 UTC

**0 de severidad alta · 2 media · 1 baja**

## 🟡 Media

- **[liquidacion]** 3 picks de Bundesliga sin liquidar tras 19 h (suele ser un nombre de equipo que no coincide)
  - `Stuttgart v Monchengladbach (2026-10-23T19:30)`
  - `Stuttgart v Monchengladbach (2026-10-23T19:30)`
  - `Stuttgart v Monchengladbach (2026-10-23T19:30)`
- **[cobertura]** sin ODDS_API_KEY no se generan picks de Conference League: football-data solo publica ligas domesticas

## ⚪ Baja

- **[valor]** ninguno de los 33 picks con precio supera la cuota justa: valor medio -5.11%. Es lo esperable, pero conviene no apostarlos

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 40 | 79.2% | 75.0% | -0.66 |
| resultado | 33 | 79.5% | 75.8% | -0.54 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 33 de 143 picks pendientes traen precio de la casa
- 0 superan la cuota justa · valor medio -5.11%

