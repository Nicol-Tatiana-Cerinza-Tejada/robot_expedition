# Incidente controlado · bloqueo del corredor y sensor degradado

> **Paso 10 del plan:** secciones 14 y 17 del enunciado.
>
> - **Evidencia:** [`resultados/incidente.json`](resultados/incidente.json),
>   con resultados por caso.
> - **MLflow:** experimento `robot-expedition-incidentes`, run
>   `acac2f8a758b4e80b9da99e6ab11de29`.
> - **Reproducir:** `python scripts/incident.py --run 92cdc692fdca465b917fa7c5e8a9902d`.

## 1. Perturbación

El nivel N3 ([ficha](ambiente-v1.md#n3--incidente-bloqueo-y-sensor-degradado))
introduce dos cambios frente a N2:

1. **Obstáculo nuevo:** al visitar B1 aparece en MuJoCo una roca de
   2.2 × 0.6 × 0.8 m en (9.7, 0). Corta el camino directo B1 → B2.
2. **Sensor degradado:**
   - el ruido de los rayos sube de σ = 0.02 a σ = 0.08 m;
   - el rayo frontal (índice 4, 0°) queda muerto y siempre marca 5 m.

## 2. Antes y después

- **Modelo:** el recomendado de N2 (`92cdc692…`, exp-004 semilla 1,
  `catalog-v2`), con SHA-256 `0d34e588ae74…`.
- **Semillas:** las mismas 50 en todas las condiciones (las de `suite-n3-v1`).
  Solo cambian las condiciones del ambiente, así que se puede atribuir la
  causa.

| Condición | Bloqueo | Ruido σ | Rayo muerto | Éxito | Fallos | Choques/ep. | Pasos | Balizas |
|---|---|---|---|---|---|---|---|---|
| **Antes:** N2 | no | 0.02 | — | **100 %** | — | 0.00 | 84.7 | 2.0 |
| Solo bloqueo | sí | 0.02 | — | **0 %** | batería 50 | 1.16 | 258.4 | 1.0 |
| Solo sensor | no | 0.08 | 4 | **100 %** | — | 0.12 | 88.4 | 2.0 |
| **Después:** N3 | sí | 0.08 | 4 | **0 %** | batería 49, tiempo 1 | 11.38 | 272.1 | 1.0 |

**Degradación:** el éxito cae **100 puntos** con la perturbación completa.

- **El bloqueo explica toda la caída. El sensor degradado, por sí solo, no
  cambia el éxito.**
- **Qué hace el rover:**
  1. visita B1 (1 baliza);
  2. al aparecer el bloqueo, gira en el sitio y avanza a ratos sin encontrar
     el rodeo: recorre unos 15 m en 250–340 pasos;
  3. agota la batería.
- **Por qué:** el modelo nunca vio el bloqueo al entrenar. El objetivo B2
  queda justo detrás de la roca y la política "apuntar al objetivo" lo empuja
  contra ella.

**Ejemplos para ver en la web** (Catálogo → `92cdc692` → *Evaluar en N3*,
o *Cargar y evaluar* con estas semillas):

| Semilla | Fin | Pasos | Balizas | Choques | Recorrido |
|---|---|---|---|---|---|
| 300000 | batería | 336 | 1 | 13 | 15.2 m |
| 300002 | batería | 243 | 1 | 0 | 13.8 m |
| 300004 | batería | 259 | 1 | 0 | 14.0 m |

**Otros modelos:**
- Todos los PPO entrenados en N2 caen al **0 %** en N3 (exp-002, exp-003 y
  exp-004). Lo hacen por tiempo, con más de 340 choques por episodio, o por
  batería.
- Q-learning cae menos: 50 ± 23 %.
- La regla fija llega a 98 %, porque gira hacia el lado con más espacio cuando
  el frente está bloqueado.

## 3. Intervención

**Candidato:** exp-005, PPO entrenado **en N3**, con el mismo presupuesto
(300k pasos) e hiperparámetros que exp-002. Las semillas 2 y 3 se entrenaron
**con el pipeline de Prefect**
([evidencia](evidencia/pipeline/20261103T021303Z-pipeline.json)), y la
semilla 1 con `train.py`.

| Run | N1 | N2 | **N3** |
|---|---|---|---|
| exp-005 semilla 1 (`4b9b4353`) | 2 % | 16 % | **100 %** |
| exp-005 semilla 2 (`f3b2dc4c`) | 70 % | 100 % | **100 %** |
| exp-005 semilla 3 (`3dd6e0f7`) | 78 % | 16 % | **100 %** |
| Media ± d.e. | 50 ± 42 % | 44 ± 48 % | **100 ± 0 %** |

## 4. Decisión con los criterios fijados antes

Criterios en [`configs/selection.yaml`](../configs/selection.yaml) v1: hay que
mejorar ≥ 5 puntos al recomendado y no sumar más de 1 vuelco ni más de 1 caída
en la grieta.

- **N3: se acepta.**
  - Todos los candidatos entrenados en N2 tienen 0 % en N3 y el mejor de
    Q-learning tiene 68 %.
  - exp-005 semilla 3 tiene 100 % y 0 choques, y se publica como recomendado
    de N3 (`catalog-v1`).
  - Las tres semillas llegan al 100 %, así que el resultado no depende de la
    semilla.
- **N2: se rechaza.**
  - La hipótesis decía "sin perder más de 5 puntos en N2", y exp-005 pierde
    56 puntos de media frente a exp-002.
  - El catálogo registra a las tres semillas como *rechazado* en N2, con su
    motivo.
  - El modelo especializado en N3 aprendió a contar con el bloqueo. Cuando no
    está (N2), dos de cada tres semillas toman una ruta que agota la batería.
- **Resultado operativo:** se sirve **un recomendado por nivel**.
  - N2 sigue con un PPO entrenado en N2.
  - N3 usa el PPO entrenado en N3.
  - El candidato y sus semillas fallidas en N2 se conservan en el catálogo
    como evidencia.

**Siguiente hipótesis razonable:** entrenar con el bloqueo en una fracción de
los episodios (por ejemplo, el 30 %). Debería dar un solo modelo que sirva en
N2 y N3, y se mediría con las mismas suites y los mismos criterios.

## 5. Monitoreo

- La web (sección **Monitoreo**) muestra:
  - el éxito del recomendado por escenario (N1, N2 y N3) y sus causas de fallo;
  - la latencia y los errores de cada ruta de la API (`/monitor`);
  - la versión servida (`/version`) frente al catálogo cargado.
- La degradación de un modelo servido también se vio en la
  [prueba de rollback](evidencia/rollback.md): una promoción errónea a N2 bajó
  el éxito servido de 100 % a 16 % y se restauró la versión anterior.
