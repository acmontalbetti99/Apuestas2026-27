# Auditoria · 2026-11-10 18:23 UTC

**1 de severidad alta · 0 media · 5 baja**

## 🔴 Alta

- **[liquidacion]** 1 picks de Premier League sin liquidar tras 386 h (un nombre de equipo que no coincide, o la estadistica que el mercado necesita que la fuente nunca publico)
  - `Sunderland v Leeds United (2026-10-25T16:30)`

## ⚪ Baja

- **[calibracion]** estadisticas/tiros: 68.9% real contra 86.7% predicho sobre 45 (z=-3.52), ya corregido con factor 0.515
- **[calibracion]** banda 85%-90%: 80.2% real contra 87.1% predicho sobre 167 (z=-2.65)
- **[valor]** ningun pick pendiente trae precio de bet365: sin eso no se puede saber cual tiene valor de verdad
- **[cobertura]** ningun pick para hoy (2026-11-10)
- **[sitio]** no se pudo chequear el sitio: ProxyError: HTTPSConnectionPool(host='montoglory.vercel.app', port=443): Max retries exceeded with url: / (Caused by ProxyError('Unable to connect to proxy', OSError('Tunnel connection failed: 403 Forbidden')))

## Calibracion

| Corte | n | Predicho | Real | z |
| --- | ---: | ---: | ---: | ---: |
| Todo | 458 | 80.9% | 77.7% | -1.76 |
| estadisticas/corners-tarjetas | 79 | 86.8% | 82.3% | -1.19 |
| estadisticas/tiros | 45 | 86.7% | 68.9% | -3.52 |
| goles | 128 | 78.3% | 78.1% | -0.06 |
| resultado | 206 | 79.0% | 77.7% | -0.49 |
| banda 0.70-0.75 | 87 | 73.5% | 70.1% | -0.71 |
| banda 0.75-0.80 | 130 | 77.1% | 78.5% | +0.36 |
| banda 0.80-0.85 | 73 | 82.6% | 79.5% | -0.71 |
| banda 0.85-0.90 | 167 | 87.1% | 80.2% | -2.65 |

`z` compara los aciertos contra los que el propio modelo esperaba, con la varianza Poisson-binomial. Entre -2 y +2 es ruido.

## Valor contra bet365

- 0 de 54 picks pendientes traen precio de la casa

