# Auditoria · 2026-10-23 20:57 UTC

**0 de severidad alta · 2 media · 1 baja**

## 🟡 Media

- **[cobertura]** sin ODDS_API_KEY no se generan picks de Conference League: football-data solo publica ligas domesticas
- **[sitio]** el sitio publica 185 picks y el repo tiene 198: el despliegue quedo atras

## ⚪ Baja

- **[valor]** ninguno de los 37 picks con precio supera la cuota justa: valor medio -5.05%. Es lo esperable, pero conviene no apostarlos

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 34 | 79.6% | 79.4% | -0.02 |
| resultado | 30 | 79.8% | 83.3% | +0.49 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 37 de 164 picks pendientes traen precio de la casa
- 0 superan la cuota justa · valor medio -5.05%

