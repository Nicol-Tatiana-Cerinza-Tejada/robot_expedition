# Resultados

| Archivo | Qué contiene |
|---|---|
| [`baselines.md`](baselines.md) | Tabla de los baselines en N1, N2 y N3 (se regenera con `python pipelines/evaluate.py --baselines --qlearning-model models/qlearning_balizas.npz`) |
| `baseline-<política>-<nivel>.json` | Resultado completo: identidad (commit, suite, ambiente, hash del modelo), métricas y los 50 casos |

## Lectura de los baselines (2 nov 2026, commit `9289227`)

1. **La política aleatoria nunca cumple la misión (0 % en los tres niveles).**
   Confirma que el éxito no se logra por azar. Sus fallos se reparten entre
   tiempo agotado, grieta, batería y vuelco.
2. **La regla resuelve N1 y N2 al 100 %, sin choques, y N3 al 98 %.**
   - Es una referencia exigente: un agente aprendido tiene que **igualarla o
     superarla en éxito y además ganar en algo medible** (pasos, batería o
     robustez).
   - También sugiere que N2 es fácil para una heurística, porque el mapa es
     fijo. Para el paso 6 (experimentos) conviene endurecer los niveles, por
     ejemplo con rocas movidas (`rock_jitter`), balizas aleatorias o más ruido,
     o justificar por qué así está bien.
   - La separación lateral importa mucho: sin ella la regla chocaba 72 veces
     por episodio en N1.
3. **El Q-learning del 28 de octubre (entrenado solo en N2):**
   - **N2:** 100 %, igual que la regla pero en más pasos (122 contra 99) y con
     menos batería al final (55 % contra 60 %).
   - **N1:** 54 %; cae en la grieta en 21 de 50 episodios. Nunca practicó
     volver a la base directamente desde B1, así que la política no transfiere
     a la ruta nueva.
   - **N3:** 6 %. Se queda empujando el bloqueo (300 pasos con choque por
     episodio) y además el rayo frontal está muerto. Es la degradación que el
     paso 10 (incidente) tiene que medir y corregir.
4. **La recompensa no es el éxito:** en N1 el Q-learning tiene retorno medio
   35 ± 57 con 54 % de éxito, mientras la regla tiene 87 ± 0.4 con 100 %.

Este Q-learning todavía no tiene manifiesto ni está en DVC: es una referencia
informal identificada por su SHA-256. Los modelos formales los registra el
pipeline de entrenamiento (paso 3).
