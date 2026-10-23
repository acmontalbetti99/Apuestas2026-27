# Auditoria · 2026-10-23 22:43 UTC

**0 de severidad alta · 2 media · 1 baja**

## 🟡 Media

- **[cobertura]** sin ODDS_API_KEY no se generan picks de Conference League: football-data solo publica ligas domesticas
- **[sitio]** el sitio publica 185 picks y el repo tiene 183: el despliegue quedo atras

## ⚪ Baja

- **[valor]** ninguno de los 35 picks con precio supera la cuota justa: valor medio -5.10%. Es lo esperable, pero conviene no apostarlos

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 36 | 79.3% | 77.8% | -0.22 |
| resultado | 31 | 79.5% | 80.7% | +0.15 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 35 de 147 picks pendientes traen precio de la casa
- 0 superan la cuota justa · valor medio -5.10%

