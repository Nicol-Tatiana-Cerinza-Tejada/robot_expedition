# Informe final · Robot Expedition

**Equipo:** Suleily Moreno, Tomás González, Natalia Ríos y Nicol Cerinza.
**Curso:** MLOps, Universidad Externado de Colombia, noviembre de 2026.

## 1. Problema y misión

Un rover con tracción diferencial, en un mundo 3D simulado con MuJoCo
(gravedad de Marte, dunas, grieta, rocas y arena), debe hacer lo siguiente:

1. salir de la base;
2. visitar las balizas en orden;
3. volver antes de agotar la batería.

Hay tres niveles con el mismo contrato de observación (20 floats) y de
acciones (`Discrete(5)`):

| Nivel | Contenido | Decisión nueva |
|---|---|---|
| N1 | 1 baliza, 2 rocas, sin dunas | Orientarse y rodear un obstáculo |
| N2 | 2 balizas, 5 rocas, dunas | Secuenciar dos objetivos y administrar la batería |
| N3 | N2 + bloqueo que aparece a mitad de la misión + sensor degradado | Replanificar |

El detalle está en la [ficha v1](ambiente-v1.md).

## 2. Decisiones de diseño

| Decisión | Por qué |
|---|---|
| La API Python es la única autoridad de la física | El enunciado advierte que exportar la red al navegador no traslada el ambiente. Así, un modelo histórico se evalúa con sus reglas originales; una prueba compara la API con la suite offline caso por caso |
| La etapa 3 significa siempre "volver a la base" | Un modelo entrenado en un nivel se puede evaluar en otro sin adaptador |
| Las suites fijas tienen semillas lejanas a las de entrenamiento y un test reservado fuera de Git | Separar el ajuste de la evaluación final |
| Hay un manifiesto por run con SHA-256 de modelo, config, ambiente y suite | La API se niega a servir pesos que no coinciden (409) |
| El catálogo está versionado, con historial y pin de rollback | Repetir una publicación no crea versión; un rollback no se deshace solo |
| Los criterios de selección se fijaron antes de los resultados (`configs/selection.yaml`) | Evitar elegir el criterio según el resultado |
| Los modelos se publican en una release (ZIP con SHA256SUMS), además de DVC | El remoto DVC de DagsHub es privado. El docente necesita recuperarlos sin cuenta |

## 3. Resultados por nivel

Éxito en las suites fijas de 50 episodios; media ± desviación estándar entre
semillas. Detalle en [experimentos.md](experimentos.md).

| | N1 | N2 | N3 |
|---|---|---|---|
| Aleatorio | 0 % | 0 % | 0 % |
| Regla | 100 % | 100 % | 98 % |
| Q-learning (exp-001, 3 semillas) | 39 ± 48 % | 97 ± 5 % | 50 ± 23 % |
| PPO (exp-002, 3 semillas) | 100 ± 0 % | 100 ± 0 % | 0 ± 0 % |
| PPO entrenado en N3 (exp-005, 3 semillas) | 50 ± 42 % | 44 ± 48 % | 100 ± 0 % |
| **Recomendado servido** | **100 %** (`a1752d56`) | **100 %** (`92cdc692`) | **100 %** (`3dd6e0f7`) |

**Finalistas** (exp-001 contra exp-002, 3 semillas cada uno). En el test
reservado:
- Q-learning: 98 / 100 / 100 %.
- PPO: 100 / 100 / 100 %.

PPO no es significativamente más exitoso, pero sí más eficiente (unos 85 pasos
frente a 117–195) y estable entre semillas. Se selecciona PPO y Q-learning
queda como baseline aprendido.

## 4. Incidente

Ver [incidente.md](incidente.md).
- **Medición:** se tomó el recomendado de N2 y se midió con las mismas
  50 semillas.
  - Su éxito cae de **100 % a 0 %** en N3.
  - Separando las causas, **el bloqueo explica toda la caída**; el sensor
    degradado solo no la cambia.
  - El rover gira frente a la roca hasta agotar la batería.
- **Intervención:** entrenar en N3 (exp-005, por el pipeline de Prefect).
  - Recupera el 100 % en N3.
  - Pero cae a 44 ± 48 % en N2.
- **Decisión con los criterios fijados:** se acepta para N3 y se rechaza para
  N2. Se sirve un modelo por nivel.

**Rollback** ([evidencia](evidencia/rollback.md)):
1. Una promoción manual errónea (`catalog-v3`) bajó el éxito servido en N2 a
   16 %.
2. El flow de rollback restauró el run de `catalog-v2` (`catalog-v4`).
3. La API confirmó la versión servida (`in_sync: true`) y el 100 %.

## 5. Costo

| Concepto | Valor |
|---|---|
| Entrenamiento | 12 runs, **125 min de CPU** en un portátil de 12 hilos, sin GPU. PPO: unos 13 min por run de 300k pasos. Q-learning: unos 9 min |
| Evaluación | 50 episodios en unos 15–30 s por modelo y nivel |
| Inferencia | 0.03 ms (Q-learning) y 0.25–0.4 ms (PPO) por decisión, con decisiones a 2 Hz |
| Servicios | Gratuitos: Vercel, Render (plan gratuito), GitHub Releases y DagsHub |

## 6. Límites

- **Mundo fijo:** balizas, base, grieta y dunas son fijas, y las semillas solo
  cambian el ruido. Un 100 % significa dominar *este* mapa, no navegar en
  general.
- **Techo:** en N2 varios candidatos llegan al 100 %. Con criterios de +5
  puntos, la selección no distingue entre ellos (exp-004 quedó recomendado
  por publicarse primero). Hace falta una suite más difícil o una métrica
  secundaria en la selección.
- **Sin repeticiones:** exp-003 (currículo) y exp-004 tienen una sola semilla.
  Son evidencia exploratoria.
- **Grieta invisible:** los rayos no ven la grieta. Los modelos de N2 que no
  son PPO caen en ella en N1.
- **MLflow sin interfaz pública:** el MLflow del equipo es local y se publica
  como archivo en la release. `scripts/mlflow_sync.py` lo copia a DagsHub, pero
  falta ejecutarlo con el token de Tomás.

## 7. Siguiente hipótesis razonable

> **Entrenar PPO con el bloqueo en el 30 % de los episodios** (y con el sensor
> degradado) produce un único modelo con éxito de al menos 95 % en N2 y N3.

Se compararía contra exp-002 (N2) y exp-005 (N3), con 300k pasos y 3 semillas.
Si falla, la alternativa es dar a la observación un "obstáculo en el camino al
objetivo" (un rayo dirigido al objetivo) en lugar de solo los 9 rayos fijos.

## 8. Contribuciones

| Integrante | Aportes (según el historial de Git y los PR) |
|---|---|
| **Suleily Moreno** | Base del repositorio y primer ambiente (bípedo y terreno marciano); paso 1: niveles N1, N2 y N3 en YAML, `environment_hash`, contratos (`docs/contratos.md`) y dependencias fijadas (PR #2) |
| **Tomás González** | Paso 3: pipeline de entrenamiento trazable (`pipelines/train.py`: MLflow, manifiestos, checkpoints y continuación con `parent_run_id`); remoto DVC en DagsHub; release pública `models-v1` (PR #3) |
| **Natalia Ríos** | Paso 5: web Vite + TypeScript + Three.js (escena 3D, HUD, control manual y replay rotulado) y despliegue en Vercel (PR #4 y #5) |
| **Nicol Cerinza** | Ambiente 3D del rover en MuJoCo y ficha v0.1; integración de las ramas; paso 2 (suite fija y baselines); paso 4 (API); pasos 6–11 (experimentos, ficha v1, Prefect, catálogo y selección, vista del docente, incidente y rollback); documentación final |

**Uso de asistentes:** parte del código y de los documentos se escribió con
asistentes de código (Copilot y Claude Code). Cada afirmación de este informe
sale de un archivo del repositorio (run_id, JSON de resultados o evidencia), y
todos los integrantes deben poder explicarlas
([guion-defensa.md](guion-defensa.md)).
