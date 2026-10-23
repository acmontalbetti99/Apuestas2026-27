# Auditoria · 2026-10-23 15:30 UTC

**0 de severidad alta · 2 media · 1 baja**

## 🟡 Media

- **[cobertura]** sin ODDS_API_KEY no se generan picks de Conference League: football-data solo publica ligas domesticas
- **[sitio]** el sitio publica 165 picks y el repo tiene 185: el despliegue quedo atras

## ⚪ Baja

- **[valor]** ninguno de los 39 picks con precio supera la cuota justa: valor medio -5.09%. Es lo esperable, pero conviene no apostarlos

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 30 | 79.9% | 80.0% | +0.01 |
| resultado | 28 | 79.9% | 82.1% | +0.30 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 39 de 155 picks pendientes traen precio de la casa
- 0 superan la cuota justa · valor medio -5.09%

