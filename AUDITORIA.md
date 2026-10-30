# Auditoria · 2026-10-30 16:50 UTC

**1 de severidad alta · 3 media · 1 baja**

## 🔴 Alta

- **[liquidacion]** 1 picks de Premier League sin liquidar tras 120 h (suele ser un nombre de equipo que no coincide)
  - `Sunderland v Leeds United (2026-10-25T16:30)`

## 🟡 Media

- **[combinadas]** dia-2026-11-03-3patas-589daef6 apunta a picks que ya no existen
  - `feyenoord__inter__x2`
- **[combinadas]** dia-2026-11-03-4patas-80ac0e5b apunta a picks que ya no existen
  - `feyenoord__inter__x2`
- **[sitio]** el sitio publica 231 picks y el repo tiene 343: el despliegue quedo atras

## ⚪ Baja

- **[valor]** ninguno de los 37 picks con precio supera la cuota justa: valor medio -5.40%. Es lo esperable, pero conviene no apostarlos

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 173 | 80.8% | 75.1% | -1.92 |
| resultado | 77 | 79.2% | 72.7% | -1.41 |
| goles | 50 | 78.0% | 76.0% | -0.34 |
| estadisticas | 46 | 86.7% | 78.3% | -1.69 |
| banda 0.70-0.75 | 33 | 73.4% | 63.6% | -1.26 |
| banda 0.75-0.80 | 50 | 77.1% | 72.0% | -0.87 |
| banda 0.80-0.85 | 24 | 82.7% | 75.0% | -1.00 |
| banda 0.85-0.90 | 65 | 87.0% | 83.1% | -0.93 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 37 de 170 picks pendientes traen precio de la casa
- 0 superan la cuota justa · valor medio -5.40%

