<!-- Generado por scripts/report_experiments.py desde catalog-v6 (2026-11-03T02:21:22+00:00). No editar a mano. -->

### Éxito por experimento y nivel (suite fija, 50 episodios; media ± d.e. entre semillas)

| Experimento | Algoritmo | Entrenado en | Semillas | Pasos | Tiempo (min) | Éxito N1 | Éxito N2 | Éxito N3 |
|---|---|---|---|---|---|---|---|---|
| exp-001 | QLEARNING | N2 | 1, 2, 3 | 300000 ± 0 | 8.8 ± 0.5 | 39 ± 48 % | 97 ± 5 % | 50 ± 23 % |
| exp-002 | PPO | N2 | 1, 2, 3 | 303104 ± 0 | 13.0 ± 0.7 | 100 ± 0 % | 100 ± 0 % | 0 ± 0 % |
| exp-003 | PPO | N2 | 1 | 155648 | 6.3 | 100 % | 100 % | 0 % |
| exp-003-n1 | PPO | N1 | 1 | 155648 | 5.8 | 100 % | 100 % | 20 % |
| exp-004 | PPO | N2 | 1 | 303104 | 12.2 | 100 % | 100 % | 0 % |
| exp-005 | PPO | N3 | 1, 2, 3 | 303104 ± 0 | 11.9 ± 1.6 | 50 ± 42 % | 44 ± 48 % | 100 ± 0 % |
| baseline-rule | rule | — | — | — | — | 100 % | 100 % | 98 % |
| baseline-random | random | — | — | — | — | 0 % | 0 % | 0 % |

### Detalle por run en la suite N1 (`suite-n1-v1`)

| Run | Experimento | Semilla | Éxito | Fallos por causa | Pasos | Choques/ep. | Batería final (éxitos) | Latencia media / p95 (ms) | Estado |
|---|---|---|---|---|---|---|---|---|---|
| `4d91d98f` | exp-001 | 1 | **20%** | grieta 33, volco 1, tiempo 6 | 163.6 | 1.34 | 51.9 % | 0.05 / 0.06 | completed |
| `4ecd569e` | exp-001 | 2 | **4%** | grieta 34, volco 14 | 75.8 | 0.00 | 65.3 % | 0.03 / 0.03 | completed |
| `b724b2e7` | exp-001 | 3 | **94%** | tiempo 3 | 107.7 | 0.00 | 68.7 % | 0.03 / 0.03 | completed |
| `a1752d56` | exp-002 | 1 | **100%** | — | 63.0 | 0.00 | 70.8 % | 0.41 / 0.57 | completed |
| `90be8649` | exp-002 | 2 | **100%** | — | 64.5 | 0.00 | 70.8 % | 0.24 / 0.25 | completed |
| `5d5c5839` | exp-002 | 3 | **100%** | — | 109.0 | 39.00 | 66.6 % | 0.24 / 0.25 | completed |
| `6376e42d` | exp-003 | 1 | **100%** | — | 65.0 | 0.00 | 71.4 % | 0.34 / 0.45 | completed |
| `37314d94` | exp-003-n1 | 1 | **100%** | — | 67.0 | 0.00 | 70.1 % | 0.44 / 0.56 | completed |
| `92cdc692` | exp-004 | 1 | **100%** | — | 63.0 | 0.00 | 71.5 % | 0.38 / 0.48 | completed |
| `4b9b4353` | exp-005 | 1 | **2%** | grieta 45, volco 2, tiempo 2 | 95.9 | 0.00 | 67.4 % | 0.39 / 0.47 | completed |
| `f3b2dc4c` | exp-005 | 2 | **70%** | grieta 5, volco 1, tiempo 9 | 130.7 | 0.00 | 70.3 % | 0.25 / 0.26 | completed |
| `3dd6e0f7` | exp-005 | 3 | **78%** | grieta 5, volco 2, tiempo 4 | 93.0 | 0.00 | 70.5 % | 0.24 / 0.25 | completed |
| baseline-rule | referencia | — | **100%** | — | 81.6 | 0.00 | 68.7 % | 0.02 / 0.02 | referencia |
| baseline-random | referencia | — | **0%** | grieta 7, volco 3, bateria 19, tiempo 21 | 348.2 | 133.12 | — | 0.01 / 0.01 | referencia |

### Detalle por run en la suite N2 (`suite-n2-v1`)

| Run | Experimento | Semilla | Éxito | Fallos por causa | Pasos | Choques/ep. | Batería final (éxitos) | Latencia media / p95 (ms) | Estado |
|---|---|---|---|---|---|---|---|---|---|
| `4d91d98f` | exp-001 | 1 | **92%** | bateria 4 | 194.6 | 9.40 | 32.5 % | 0.05 / 0.06 | completed |
| `4ecd569e` | exp-001 | 2 | **100%** | — | 117.3 | 0.00 | 55.2 % | 0.03 / 0.03 | completed |
| `b724b2e7` | exp-001 | 3 | **100%** | — | 130.6 | 0.00 | 54.4 % | 0.03 / 0.03 | completed |
| `a1752d56` | exp-002 | 1 | **100%** | — | 85.3 | 0.00 | 61.7 % | 0.36 / 0.47 | completed |
| `90be8649` | exp-002 | 2 | **100%** | — | 86.1 | 0.00 | 61.5 % | 0.25 / 0.26 | completed |
| `5d5c5839` | exp-002 | 3 | **100%** | — | 83.0 | 0.00 | 62.1 % | 0.25 / 0.26 | completed |
| `6376e42d` | exp-003 | 1 | **100%** | — | 88.0 | 0.00 | 61.4 % | 0.39 / 0.50 | completed |
| `37314d94` | exp-003-n1 | 1 | **100%** | — | 258.6 | 125.40 | 28.3 % | 0.45 / 0.58 | completed |
| `92cdc692` | exp-004 | 1 | **100%** | — | 84.6 | 0.00 | 62.2 % | 0.36 / 0.44 | completed |
| `4b9b4353` | exp-005 | 1 | **16%** | grieta 10, bateria 28, tiempo 4 | 341.9 | 23.66 | 5.4 % | 0.38 / 0.45 | completed |
| `f3b2dc4c` | exp-005 | 2 | **100%** | — | 110.5 | 17.62 | 56.9 % | 0.24 / 0.25 | completed |
| `3dd6e0f7` | exp-005 | 3 | **16%** | tiempo 42 | 366.7 | 308.00 | 46.7 % | 0.24 / 0.24 | completed |
| baseline-rule | referencia | — | **100%** | — | 98.8 | 0.00 | 59.6 % | 0.02 / 0.02 | referencia |
| baseline-random | referencia | — | **0%** | grieta 12, bateria 4, tiempo 34 | 336.0 | 157.72 | — | 0.01 / 0.01 | referencia |

### Detalle por run en la suite N3 (`suite-n3-v1`)

| Run | Experimento | Semilla | Éxito | Fallos por causa | Pasos | Choques/ep. | Batería final (éxitos) | Latencia media / p95 (ms) | Estado |
|---|---|---|---|---|---|---|---|---|---|
| `4d91d98f` | exp-001 | 1 | **58%** | bateria 3, tiempo 18 | 308.8 | 163.44 | 33.3 % | 0.05 / 0.06 | completed |
| `4ecd569e` | exp-001 | 2 | **24%** | tiempo 38 | 341.8 | 264.38 | 46.7 % | 0.03 / 0.03 | completed |
| `b724b2e7` | exp-001 | 3 | **68%** | bateria 2, tiempo 14 | 222.3 | 92.50 | 48.8 % | 0.03 / 0.03 | completed |
| `a1752d56` | exp-002 | 1 | **0%** | tiempo 50 | 400.0 | 348.66 | — | 0.36 / 0.44 | completed |
| `90be8649` | exp-002 | 2 | **0%** | bateria 50 | 242.9 | 41.94 | — | 0.24 / 0.25 | completed |
| `5d5c5839` | exp-002 | 3 | **0%** | tiempo 50 | 400.0 | 350.86 | — | 0.24 / 0.25 | completed |
| `6376e42d` | exp-003 | 1 | **0%** | bateria 47, tiempo 3 | 333.4 | 36.28 | — | 0.38 / 0.45 | completed |
| `37314d94` | exp-003-n1 | 1 | **20%** | tiempo 40 | 375.3 | 34.54 | 29.1 % | 0.41 / 0.48 | completed |
| `92cdc692` | exp-004 | 1 | **0%** | bateria 49, tiempo 1 | 272.1 | 11.38 | — | 0.35 / 0.41 | completed |
| `4b9b4353` | exp-005 | 1 | **100%** | — | 110.4 | 0.00 | 53.6 % | 0.40 / 0.48 | completed |
| `f3b2dc4c` | exp-005 | 2 | **100%** | — | 97.8 | 0.00 | 57.6 % | 0.24 / 0.25 | completed |
| `3dd6e0f7` | exp-005 | 3 | **100%** | — | 95.8 | 0.00 | 58.1 % | 0.24 / 0.25 | completed |
| baseline-rule | referencia | — | **98%** | bateria 1 | 165.7 | 9.68 | 41.6 % | 0.02 / 0.02 | referencia |
| baseline-random | referencia | — | **0%** | grieta 11, volco 4, bateria 6, tiempo 29 | 329.1 | 150.96 | — | 0.01 / 0.01 | referencia |

### Decisiones de selección (`configs/selection.yaml` v1)

| Nivel | Recomendado | Decisiones |
|---|---|---|
| N1 | exp-002 s1 (`a1752d56`) | exp-004 s1: rechazado — mejora +0% < +5% sobre a1752d56<br>exp-002 s2: rechazado — mejora +0% < +5% sobre a1752d56<br>exp-003 s1: rechazado — mejora +0% < +5% sobre a1752d56<br>exp-003-n1 s1: rechazado — mejora +0% < +5% sobre a1752d56<br>exp-002 s3: rechazado — mejora +0% < +5% sobre a1752d56<br>exp-001 s3: rechazado — mejora -6% < +5% sobre a1752d56<br>exp-005 s3: rechazado — mejora -22% < +5% sobre a1752d56<br>exp-005 s2: rechazado — mejora -30% < +5% sobre a1752d56<br>exp-001 s1: rechazado — mejora -80% < +5% sobre a1752d56<br>exp-001 s2: rechazado — mejora -96% < +5% sobre a1752d56<br>exp-005 s1: rechazado — mejora -98% < +5% sobre a1752d56<br>exp-002 s1: se mantiene — ningún candidato cumple los criterios de reemplazo |
| N2 | exp-004 s1 (`92cdc692`) | exp-002 s3: rechazado — mejora +0% < +5% sobre 92cdc692<br>exp-002 s1: rechazado — mejora +0% < +5% sobre 92cdc692<br>exp-002 s2: rechazado — mejora +0% < +5% sobre 92cdc692<br>exp-003 s1: rechazado — mejora +0% < +5% sobre 92cdc692<br>exp-001 s2: rechazado — mejora +0% < +5% sobre 92cdc692<br>exp-001 s3: rechazado — mejora +0% < +5% sobre 92cdc692<br>exp-005 s2: rechazado — mejora +0% < +5% sobre 92cdc692<br>exp-003-n1 s1: rechazado — mejora +0% < +5% sobre 92cdc692<br>exp-001 s1: rechazado — mejora -8% < +5% sobre 92cdc692<br>exp-005 s1: rechazado — mejora -84% < +5% sobre 92cdc692<br>exp-005 s3: rechazado — mejora -84% < +5% sobre 92cdc692<br>exp-004 s1: se mantiene — ningún candidato cumple los criterios de reemplazo |
| N3 | exp-005 s3 (`3dd6e0f7`) | exp-005 s2: rechazado — mejora +0% < +5% sobre 3dd6e0f7<br>exp-005 s1: rechazado — mejora +0% < +5% sobre 3dd6e0f7<br>exp-001 s3: rechazado — mejora -32% < +5% sobre 3dd6e0f7<br>exp-001 s1: rechazado — mejora -42% < +5% sobre 3dd6e0f7<br>exp-001 s2: rechazado — mejora -76% < +5% sobre 3dd6e0f7<br>exp-003-n1 s1: rechazado — mejora -80% < +5% sobre 3dd6e0f7<br>exp-004 s1: rechazado — mejora -100% < +5% sobre 3dd6e0f7<br>exp-003 s1: rechazado — mejora -100% < +5% sobre 3dd6e0f7<br>exp-002 s2: rechazado — mejora -100% < +5% sobre 3dd6e0f7<br>exp-002 s1: rechazado — mejora -100% < +5% sobre 3dd6e0f7<br>exp-002 s3: rechazado — mejora -100% < +5% sobre 3dd6e0f7<br>exp-005 s3: se mantiene — ningún candidato cumple los criterios de reemplazo |
