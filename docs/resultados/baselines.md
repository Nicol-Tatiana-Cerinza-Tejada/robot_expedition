# Resultados de los baselines

Generado con `python pipelines/evaluate.py --baselines` (paso 2 del plan).
Commit `9289227847` · ambiente `robot-expedition-3d/1.0.0` · suites `suite-n1-v1`, `suite-n2-v1` y `suite-n3-v1` (50 episodios cada una, semillas fijas).

La **tasa de éxito** mide la misión. El **retorno** (recompensa acumulada) se reporta
aparte y solo se compara dentro de un mismo nivel: no equivale al éxito.

| Nivel | Política | Éxito | Fallos por causa | Balizas | Pasos | Choques/ep. | Batería (éxitos) | Eficiencia | Retorno medio ± d.e. | Latencia media (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| N1 | [random](baseline-random-n1.json) | **0%** | bateria 19, grieta 7, tiempo 21, volco 3 | 0.08 | 348.22 | 133.12 | — | — | -98.8 ± 24.8 | 0.01 |
| N1 | [rule](baseline-rule-n1.json) | **100%** | — | 1.00 | 81.56 | 0.00 | 68.73 | 0.98 | 87.4 ± 0.4 | 0.01 |
| N1 | [qlearning](baseline-qlearning-n1.json) | **54%** | grieta 21, tiempo 2 | 1.00 | 96.34 | 0.00 | 67.12 | 0.94 | 35.2 ± 56.7 | 0.03 |
| N2 | [random](baseline-random-n2.json) | **0%** | bateria 4, grieta 12, tiempo 34 | 0.08 | 336.04 | 157.72 | — | — | -97.7 ± 29.6 | 0.01 |
| N2 | [rule](baseline-rule-n2.json) | **100%** | — | 2.00 | 98.76 | 0.00 | 59.63 | 1.03 | 101.4 ± 0.3 | 0.01 |
| N2 | [qlearning](baseline-qlearning-n2.json) | **100%** | — | 2.00 | 121.94 | 0.00 | 54.55 | 0.94 | 100.3 ± 0.2 | 0.03 |
| N3 | [random](baseline-random-n3.json) | **0%** | bateria 6, grieta 11, tiempo 29, volco 4 | 0.06 | 329.08 | 150.96 | — | — | -99.7 ± 29.8 | 0.01 |
| N3 | [rule](baseline-rule-n3.json) | **98%** | bateria 1 | 2.00 | 165.70 | 9.68 | 41.63 | 0.86 | 89.8 ± 24.3 | 0.01 |
| N3 | [qlearning](baseline-qlearning-n3.json) | **6%** | bateria 1, tiempo 46 | 1.06 | 385.88 | 300.36 | 41.08 | 0.81 | -130.3 ± 56.6 | 0.03 |

- **Balizas:** media de balizas visitadas en orden (N1 tiene 1, N2 y N3 tienen 2).
- **Eficiencia:** ruta de referencia de centro a centro / distancia recorrida, solo en éxitos, en línea recta (N1: 17.5 m; N2 y N3: 24.5 m). Puede pasar de 1 porque basta con entrar al radio de 0.6 m.
- **Latencia:** tiempo de decisión de la política por paso, sin contar la física.
- Cada JSON enlazado tiene los resultados por caso (semilla, causa de fin, pasos, batería, choques, recorrido, retorno y latencia).
- **qlearning:** modelo `models/qlearning_balizas.npz`, SHA-256 `09ab393b964273d7994178b6263af68d0d68548179b2dda70b8a445f521f5d9e`.
