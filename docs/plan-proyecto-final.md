# Plan del proyecto final · Robot Expedition

Plan de trabajo del equipo (Suleily, Tomás, Natalia y Nicol) para el
**Proyecto final de MLOps**. Sale del enunciado del 30 de octubre de 2026 y de
lo que ya hay en el repositorio. Cada paso trae el **prompt** para pegar en
Claude Code (VS Code). El equipo decide quién hace cada paso.

## 1. Qué pide el enunciado

**El reto:** una **web en Vercel** donde el docente pueda:
- Ver los experimentos.
- Cargar modelos históricos.
- Ejecutar evaluaciones con el ambiente compatible de cada modelo.

**Lo que se entrega:**
- Una URL que funcione.
- Un repositorio reproducible.
- Un registro de experimentos en MLflow.
- Modelos que se puedan recuperar.

**Cómo se revisa:** el docente abre la web, elige una ejecución histórica,
comprueba su identidad, carga el modelo y lo evalúa. Luego pide comparar
candidatos, explicar fallos, reconstruir una evaluación desde la release y
**restaurar una versión anterior (rollback)**.

| Criterio de la rúbrica | Peso |
|---|---|
| Versionamiento, trazabilidad y recuperación histórica | **30 %** |
| Diseño experimental, comparación y análisis | **25 %** |
| Pipeline, despliegue, monitoreo y rollback | **20 %** |
| Contrato y funcionamiento del ambiente/agente | 10 % |
| Defensa, comunicación y participación individual | 15 % |

Lo que más pesa es la **trazabilidad**. Un modelo que no mejora, pero está
bien registrado y explicado, también suma puntos.

## 2. Qué ya tenemos y qué falta

| Pide el enunciado | Estado | Dónde |
|---|---|---|
| Ambiente Gymnasium con `reset`/`step`, éxito y fallo (`terminated`) y tiempo agotado (`truncated`) | ✅ Hecho (rover 3D en MuJoCo) | `robot_expedition/envs/beacon_expedition.py` |
| Ficha del ambiente | ✅ v0.1; falta documentar los 3 niveles | `docs/ambiente-v0.1.md` |
| Pruebas de reglas | ✅ 15 pruebas | `tests/` |
| Perturbación (obstáculo nuevo o sensor degradado) | ✅ Bloqueo y ruido de rayos | `--perturbation`, `--ray-noise` |
| Vista 3D con Three.js | 🟡 Es un HTML suelto que reproduce archivos JSON; falta el proyecto Vite + TypeScript conectado a una API | `expedicion_3d.html` |
| Agente | 🟡 Hay Q-learning. Falta **PPO (Stable-Baselines3)**, que es la referencia del curso | `robot_expedition/qlearning.py` |
| Baselines aleatorio y de regla | ❌ | — |
| Tres niveles N1, N2 y N3 con configuraciones versionadas | ❌ | — |
| MLflow: runs, métricas, artefactos y registro de modelos | ❌ | — |
| Manifiesto por modelo (SHA-256, normalización, contrato) | ❌ | — |
| DVC o almacenamiento recuperable de modelos | ❌ | — |
| Suite de evaluación fija, resultados por caso y test reservado | 🟡 Hay semillas fijas; faltan la suite versionada y el JSON por caso | — |
| Cuatro configuraciones con hipótesis y finalistas con 3 semillas | ❌ | — |
| Pipeline con Prefect | ❌ | — |
| API HTTPS (FastAPI) para simular y evaluar | ❌ | — |
| Web en Vercel: catálogo, cargar, evaluar, comparar, modos, errores | ❌ | — |
| Monitoreo, incidente con intervención y rollback | ❌ | — |
| Release `v1.0`, README final, informe y presentación | ❌ | — |

## 3. Contratos que todos respetan

Estos acuerdos permiten trabajar en paralelo sin chocar. Si alguien necesita
cambiar uno, lo anota en `docs/contratos.md` y avisa al equipo.

### 3.1 Niveles

Todos los niveles usan la **misma observación (20 valores) y las mismas 5
acciones**. Así un modelo de un nivel se puede evaluar en otro. Si un nivel
cambia las dimensiones, se crea una familia nueva de modelos.

| Nivel | Archivo | Misión | Qué decisión nueva toma el agente |
|---|---|---|---|
| **N1 · Misión base** | `configs/levels/n1.yaml` | Llegar a **una** baliza (B1) y volver a la base. Pocas rocas, sin dunas | Ir a una meta evitando obstáculos |
| **N2 · Más decisiones** | `configs/levels/n2.yaml` | B1 → B2 → base, con 5 rocas, dunas, grieta y arena (lo que hay hoy) | Orden de las balizas, rutas alternativas, terreno |
| **N3 · Operación exigente** | `configs/levels/n3.yaml` | N2 + **bloqueo** del corredor al visitar B1 + **sensor degradado** (ruido σ = 0.08 m y un rayo muerto) | Recuperarse de un obstáculo nuevo y de sensores malos |

### 3.2 Configuración de un experimento

Cada experimento es un archivo `configs/experiments/exp-XXX.yaml`:

```yaml
experiment_id: exp-002
hypothesis: "PPO con 300k pasos supera a Q-learning en éxito en N2"
level_id: n2
algorithm: ppo            # ppo | qlearning | random | rule
budget_timesteps: 300000
seeds: [1, 2, 3]
hyperparams: {learning_rate: 3.0e-4, n_steps: 2048, batch_size: 64, gamma: 0.99}
normalize_obs: true
parent_run_id: null       # o el run del que continúa
```

### 3.3 Manifiesto de cada modelo

Va en `manifests/<run_id>.json` y se guarda en Git:

```json
{
  "run_id": "...", "experiment_id": "exp-002", "level_id": "n2",
  "algorithm": "ppo", "environment_version": "robot-expedition-3d/1.0.0",
  "git_commit": "<sha completo>", "config_sha256": "...",
  "model_uri": "<dvc o mlflow>", "model_sha256": "...",
  "normalization_uri": "<vecnormalize.pkl o null>",
  "obs_spec": "20 floats, ver docs/ambiente", "action_spec": "Discrete(5)",
  "runtime_ref": "requirements.txt + python 3.12", "evaluation_suite_id": "suite-n2-v1",
  "seed": 1, "budget_timesteps": 300000, "parent_run_id": null,
  "status": "completed | failed | interrupted | rejected", "metrics": {"success_rate": 0.0}
}
```

### 3.4 Catálogo para la web y la API

`catalog/catalog.json` se genera con el pipeline a partir de los manifiestos.
Contiene la lista de runs (con sus métricas y estado), el `recommended_run_id`
por nivel y la `served_version`.

### 3.5 API (FastAPI)

| Ruta | Qué hace |
|---|---|
| `GET /health` | Estado del servicio |
| `GET /version` | Commit, release y versión del ambiente |
| `GET /catalog` | El catálogo |
| `GET /runs/{run_id}` | El manifiesto del run |
| `POST /evaluate` | Recibe `{run_id, level_id, seeds}` y devuelve métricas, resultados por caso y los cuadros de un episodio |
| `POST /sim/reset`, `POST /sim/step` | Control manual o por regla, con `session_id` |

### 3.6 Formato de un cuadro (para la vista 3D)

```
[x, y, z, qw, qx, qy, qz, etapa, bateria, accion, recompensa, choque, [9 rayos]]
```

Es el formato que ya usan el CLI y `expedicion_3d.html`.

### 3.7 Servicios gratuitos sugeridos

Hay que confirmarlos con el docente:

| Para qué | Servicio |
|---|---|
| MLflow y almacenamiento DVC | **DagsHub** (MLflow alojado y remoto DVC gratis) |
| API | **Hugging Face Spaces** (Docker) o Render |
| Web | Vercel |

### 3.8 Git

- `main` es la rama de entrega.
- Cada paso se hace en una rama `feature/<paso>` creada desde `main`
  actualizado.
- Se integra con un **Pull Request revisado por otra persona**.
- Al final se marca la release con `git tag v1.0`.

## 4. Orden de trabajo

```
Paso 0 ─ Paso 1 ─┬─ Paso 2 (evaluación) ─┬─ Paso 6 (experimentos) ─┬─ Paso 8 (pipeline) ─┬─ Paso 10 (incidente) ─┬─ Paso 11 (rollback y release)
                 ├─ Paso 3 (PPO + MLflow)┘                         │                      │                       └─ Paso 12 (informe, todos)
                 ├─ Paso 4 (API) ──────────────────────────────────┴─ Paso 9 (web: catálogo, comparar, monitoreo)
                 ├─ Paso 5 (web Vite + Vercel) ─────────────────────┘
                 └─ Paso 7 (ficha v1 y niveles)
```

- Los **pasos 0 y 1 van primero**: son cortos y desbloquean todo lo demás.
- Los **pasos 2, 3, 4, 5 y 7 se pueden hacer al mismo tiempo**.

### Paquetes sugeridos (uno por persona)

Son una sugerencia; el equipo los reparte como quiera.

| Paquete | Pasos | Tema |
|---|---|---|
| A | 1, 4, 7, 10 | Ambiente, niveles, API e incidente |
| B | 3, 6 | Entrenamiento PPO, MLflow y experimentos |
| C | 2, 8, 11 | Evaluación, pipeline, rollback y release |
| D | 5, 9 | Web Vite + Three.js, Vercel y monitoreo |
| Todos | 0, 12 | Integración, informe y defensa |

---

### Paso 0 · Integrar lo que hay y crear `main`
**Hito 1 · Lo hace quien administre el repositorio (Suleily) · 15 min**

```text
Estoy en el repositorio robot_expedition (proyecto Robot Expedition del curso de MLOps). La rama por defecto es 1experiment y la rama nicol tiene el trabajo más reciente (ambiente 3D en MuJoCo, Q-learning, CLI, vista 3D y ficha). Ayúdame a:
1) Revisar con git log/diff qué trae nicol frente a 1experiment y resumírmelo.
2) Abrir con gh un Pull Request de nicol hacia 1experiment y fusionarlo si no hay conflictos.
3) Crear la rama main desde 1experiment actualizado, subirla y dejarla como rama por defecto (gh repo edit --default-branch main).
4) Instalar el entorno y comprobar que pasan las pruebas: python -m pytest -q.
No borres ramas ni reescribas historia. Explícame cada comando antes de ejecutarlo.
```

### Paso 1 · Base reproducible, niveles y contratos
**Hito 1 · Bloquea a los demás · 1 persona**

```text
Proyecto Robot Expedition (MLOps). Lee README.md, docs/ambiente-v0.1.md y docs/plan-proyecto-final.md (sobre todo la sección 3, Contratos). Crea la rama feature/base-niveles desde main actualizado.
Objetivo: dejar la base reproducible sobre la que trabaja todo el equipo.
1) Entorno: Python 3.12 (el enunciado lo recomienda; comprueba que torch y stable-baselines3 instalan). Instala torch CPU (--index-url https://download.pytorch.org/whl/cpu), gymnasium, mujoco, stable-baselines3, mlflow, fastapi, uvicorn, numpy, pyyaml, prefect, pytest. Genera requirements.txt con versiones fijadas y documenta en el README los comandos exactos de instalación para Windows y Linux.
2) Estructura del enunciado sin romper imports: configs/levels, configs/experiments, pipelines/, manifests/, catalog/, web/ (vacía por ahora), docs/. El ambiente puede quedarse en robot_expedition/envs.
3) Niveles: crea configs/levels/n1.yaml, n2.yaml y n3.yaml según la sección 3.1 del plan. Haz que BeaconExpeditionEnv reciba una config de nivel (número de balizas, rocas activas, dunas sí/no, bloqueo, ruido y rayo muerto) manteniendo la observación de 20 valores y Discrete(5). Agrega la constante ENVIRONMENT_VERSION = "robot-expedition-3d/1.0.0" y una función que calcule el hash del código del ambiente más la config.
4) Escribe docs/contratos.md copiando y completando la sección 3 del plan (configuración, manifiesto, catálogo, API y formato de cuadros).
5) Agrega pruebas: cada nivel hace reset/step, las dimensiones son iguales en los 3 niveles, N1 termina con éxito tras B1 y la base, y N3 activa el bloqueo y degrada los rayos. Las 15 pruebas actuales deben seguir pasando.
6) .gitignore: .venv/, node_modules/, .env, mlruns/, logs/, models/. Crea un .env.example sin secretos.
Al final: python -m pytest -q, commit con mensaje claro, push y PR hacia main con gh explicando los contratos.
```

### Paso 2 · Suite de evaluación y baselines (aleatorio y regla)
**Hito 1 · En paralelo, después del paso 1**

```text
Proyecto Robot Expedition (MLOps). Lee docs/plan-proyecto-final.md (sección 3), docs/contratos.md y robot_expedition/envs/beacon_expedition.py. Rama feature/evaluacion desde main.
Objetivo: una evaluación fija y comparable para cualquier modelo.
1) pipelines/evaluate.py con evaluate(policy, level_id, suite_id) -> dict. Una suite (configs/suites/suite-n1-v1.yaml, suite-n2-v1.yaml, suite-n3-v1.yaml) fija las semillas y el número de episodios (50). Crea también una suite de test reservado (test-final) cuyas semillas NO se suban al repo público: léelas desde una variable de entorno o un archivo ignorado, y documéntalo.
2) Resultados por caso (semilla, éxito, causa de fin, pasos, batería, choques, recorrido, retorno, latencia media de inferencia) guardados en JSON. Métricas agregadas: tasa de éxito, fallos por causa, eficiencia de ruta, choques por episodio, batería final y latencia.
3) Baselines: política aleatoria y política de regla (girar hacia el objetivo y esquivar si el rayo frontal es menor que 0.8 m). Evalúalas en N1, N2 y N3 y guarda los resultados en docs/resultados/baselines.md.
4) Adaptador para el Q-learning que ya existe (models/*.npz) con la misma interfaz policy(obs) -> acción.
5) CLI: python -m pipelines.evaluate --policy rule --level n2 --suite suite-n2-v1.
6) Pruebas: la misma suite y la misma política dan el mismo resultado, y el JSON tiene todos los campos.
Recuerda: la recompensa acumulada no es la tasa de éxito; repórtalas por separado. Commit, push y PR hacia main.
```

### Paso 3 · Entrenamiento PPO + Q-learning con MLflow y manifiestos
**Hito 1 · En paralelo, después del paso 1**

```text
Proyecto Robot Expedition (MLOps). Lee docs/plan-proyecto-final.md (secciones 3.2 y 3.3), docs/contratos.md, robot_expedition/qlearning.py y robot_expedition/__main__.py. Rama feature/entrenamiento desde main.
Objetivo: entrenar con trazabilidad completa.
1) pipelines/train.py --config configs/experiments/exp-XXX.yaml. Algoritmos: ppo (Stable-Baselines3 con MlpPolicy, VecNormalize para las observaciones y un número fijo de envs) y qlearning (reusa el agente actual). Una ejecución por semilla.
2) MLflow: experimento "robot-expedition". Registra parámetros resueltos y las tags git_commit, environment_version, level_id, experiment_id, hypothesis y seed. Durante el entrenamiento registra la recompensa y el éxito de entrenamiento (con exploración); al final, el éxito de evaluación determinista, como curvas SEPARADAS. Guarda como artefactos el modelo, vecnormalize.pkl, config.json y evaluacion.json. Registra el modelo en el Model Registry. Usa MLFLOW_TRACKING_URI desde .env (local mlruns/ por defecto; DagsHub para compartir).
3) Manifiesto manifests/<run_id>.json con el formato de la sección 3.3 (SHA-256 de los pesos y de la config, commit, origen y presupuesto efectivo). Si el run falla o se interrumpe, escribe igual el manifiesto con status failed o interrupted, el diagnóstico y "sin checkpoint disponible".
4) Para continuar desde un checkpoint (parent_run_id), guarda el estado del optimizador y el contador de pasos.
5) Crea configs/experiments/exp-001.yaml (baseline Q-learning N2) y exp-002.yaml (PPO N2) y corre una prueba corta (pocos pasos) para validar todo el flujo.
6) DVC: inicializa DVC y deja los modelos versionados con un remoto (DagsHub o Google Drive; documenta cuál). En Git solo van los .dvc y los manifiestos.
Pruebas: un entrenamiento mínimo produce un manifiesto válido y un hash reproducible. Commit, push y PR hacia main.
```

### Paso 4 · API FastAPI desplegada con HTTPS
**Hito 1 · En paralelo, después del paso 1**

```text
Proyecto Robot Expedition (MLOps). Lee docs/plan-proyecto-final.md (secciones 3.4 a 3.6) y docs/contratos.md. Rama feature/api desde main.
Objetivo: una API que use el MISMO ambiente Python del entrenamiento para evaluar modelos desde la web.
1) api/main.py con FastAPI y las rutas de la sección 3.5. /evaluate carga el modelo del run según su manifiesto (PPO con su VecNormalize, o Q-learning), verifica el SHA-256, corre el nivel pedido y devuelve métricas, resultados por caso y los cuadros de un episodio en el formato de la sección 3.6. /sim/reset y /sim/step permiten control manual y por regla.
2) Errores claros (run inexistente, hash distinto, nivel incompatible) con códigos HTTP correctos. Mide y devuelve la latencia de inferencia.
3) CORS solo para localhost (desarrollo) y el dominio de Vercel (variable ALLOWED_ORIGINS).
4) Dockerfile listo para Hugging Face Spaces (o Render). Los modelos se descargan del remoto DVC/MLflow al arrancar; no dependen de carpetas personales. Documenta el despliegue en docs/despliegue-api.md.
5) Mientras no haya modelos PPO, prueba con el Q-learning actual (models/qlearning_balizas.npz).
6) Pruebas con TestClient: health, catalog, evaluate de un run de ejemplo y error 404.
Despliega y deja anotada en el README la URL HTTPS. Commit, push y PR hacia main.
```

### Paso 5 · Web con Vite + TypeScript + Three.js y Vercel
**Hito 1 · En paralelo, después del paso 1**

```text
Proyecto Robot Expedition (MLOps). Lee docs/plan-proyecto-final.md (secciones 3.4 a 3.6) y el archivo expedicion_3d.html, que ya tiene una vista 3D funcional con Three.js (terreno heightfield, rover, rayos, rastro y curva). Rama feature/web desde main.
Objetivo: convertirla en la app web del proyecto.
1) Crea web/ con: npm create vite@latest web -- --template vanilla-ts, luego npm install three y npm install -D @types/three. Registra en el README las versiones de Node y Vite. Sube package-lock.json.
2) Porta expedicion_3d.html a TypeScript en módulos (escena, terreno, rover, rayos, HUD, curva). Debe verse igual o mejor e incluir un "modo ligero" sin sombras.
3) Fuente de datos configurable con VITE_API_BASE_URL. Si la API responde, usa /catalog y /evaluate. Si no, muestra un ERROR visible (no datos falsos). Un replay de archivo se rotula "REPLAY".
4) Siempre visible: el modo (manual, aleatorio, regla, evaluación, entrenamiento-replay), episodio, objetivo activo, recompensa, causa de fallo, modelo (run_id) y ambiente (environment_version, nivel).
5) Control manual con las flechas usando /sim/step.
6) Despliega en Vercel: Root Directory web, Build npm run build, Output dist; configura VITE_API_BASE_URL. Comprueba que nada en producción apunte a localhost.
Al final: npm ci && npm run build sin errores, la URL de Vercel en el README, commit, push y PR hacia main.
```

### Paso 6 · Experimentos: 4 configuraciones con hipótesis en los 3 niveles
**Hito 2 · Necesita los pasos 2 y 3**

```text
Proyecto Robot Expedition (MLOps). Lee docs/plan-proyecto-final.md, docs/contratos.md, pipelines/train.py y pipelines/evaluate.py. Rama feature/experimentos desde main.
Objetivo: el diseño experimental (25 % de la nota).
1) Define al menos 4 configuraciones en configs/experiments/ con UNA hipótesis concreta cada una y un solo cambio frente a su referencia. Sugerencias:
   exp-001 Q-learning N2 (baseline aprendido); exp-002 PPO N2 (¿PPO supera a Q-learning?);
   exp-003 PPO N1 → N2 (¿empezar en N1 acelera N2?, parent_run_id);
   exp-004 PPO N2 con la inclinación y la grieta en la recompensa o con más pasos;
   exp-005 PPO entrenado con el bloqueo en el 30 % de los episodios (intervención para N3).
2) Presupuesto comparable entre candidatos (mismos timesteps) y registrado. Entrena todo con pipelines/train.py para que quede en MLflow con manifiesto. Conserva los runs fallidos, interrumpidos y rechazados.
3) Elige los 2 finalistas del contraste principal y entrena cada uno con 3 semillas independientes. Evalúalos con la suite fija y UNA sola vez con el test reservado.
4) Evalúa también los baselines aleatorio y de regla en la misma suite.
5) docs/experimentos.md: por experimento, la hipótesis, el cambio, el presupuesto, las semillas, los run_id, los resultados (éxito, fallos por causa, pasos, batería, choques, latencia) con media y desviación entre semillas, y la decisión (seleccionar, rechazar o recuperar) con su justificación. Agrega gráficas de las curvas de entrenamiento y de evaluación por separado.
Commit de configs, manifiestos, .dvc y docs. Push y PR hacia main.
```

### Paso 7 · Ficha v1.0 y documentación de los 3 niveles
**Hito 2 · En paralelo con el paso 6**

```text
Proyecto Robot Expedition (MLOps). Lee docs/ambiente-v0.1.md, configs/levels/*.yaml y robot_expedition/envs/beacon_expedition.py. Rama feature/ficha-v1 desde main.
Objetivo: docs/ambiente-v1.md, que cumpla la sección 02 del enunciado. Debe definir:
- unidades y rangos;
- acciones válidas, el paso físico (dt de MuJoCo = 0.02 s) y la frecuencia de decisión (2 Hz);
- éxito, fallos y truncamiento;
- simplificaciones;
- la pérdida de resolución de la discretización del Q-learning;
- y que la velocidad de animación no cambia las reglas.
Agrega una sección por nivel (N1, N2, N3) con la decisión nueva que toma el agente, cómo se mide la dificultad y el mapa de cada nivel (actualiza docs/mapa-ambiente-v0.1.svg o crea uno por nivel). Mantén v0.1 como historial y enlázalo. Verifica cada número contra el código y las pruebas. Commit, push y PR hacia main.
```

### Paso 8 · Pipeline con Prefect, selección y catálogo
**Hito 3 · Necesita los pasos 2 y 3**

```text
Proyecto Robot Expedition (MLOps). Lee la sección 14 del enunciado (resumida en docs/plan-proyecto-final.md), docs/contratos.md, pipelines/train.py y pipelines/evaluate.py. Rama feature/pipeline desde main.
Objetivo: pipelines/flow.py con Prefect. Cada etapa es una task que deja estado y evidencia:
1) validar perfil, rutas, esquema y compatibilidad del ambiente;
2) correr pytest;
3) entrenar un candidato o cargar un checkpoint compatible;
4) evaluar con la suite y guardar los resultados por caso;
5) registrar los artefactos y el modelo con sus hashes y su procedencia;
6) aplicar criterios de selección FIJADOS ANTES en configs/selection.yaml (por ejemplo: éxito ≥ el del recomendado + 5 puntos y sin aumento de vuelcos);
7) publicar catalog/catalog.json con el recommended_run_id por nivel;
8) comprobar la versión realmente servida por la API (/version y /catalog).
Si el entrenamiento falla, el historial se conserva y el diagnóstico queda en el manifiesto. Si la publicación se repite, debe identificar el mismo artefacto o crear una versión nueva explícita, nunca sobrescribir en silencio.
Documenta en el README cómo arrancar Prefect (versión, comando, interfaz) y guarda capturas o logs de una ejecución completa en docs/evidencia/. Commit, push y PR hacia main.
```

### Paso 9 · Web: catálogo, cargar, evaluar, comparar y monitoreo
**Hito 2 y 3 · Necesita los pasos 4 y 5**

```text
Proyecto Robot Expedition (MLOps). Lee docs/plan-proyecto-final.md, docs/contratos.md y web/. Rama feature/web-catalogo desde main.
Objetivo: la vista que usará el docente (sección 12 del enunciado, "Qué verá el docente en la web").
1) Catálogo de runs filtrable por nivel, con estos datos por run: hipótesis, cambio frente al baseline, run_id, semilla, pasos y tiempo de entrenamiento, métricas, estado (incluidos failed, interrupted y rejected), versión del modelo, commit (enlace a GitHub) y enlace a MLflow.
2) Botones "Cargar y evaluar", que llama a /evaluate y reproduce el episodio en 3D, y "Comparar", con dos o más runs compatibles lado a lado: éxito, fallos por causa, pasos, batería, latencia y curvas.
3) Al cargar, mostrar qué modelo, ambiente y configuración están activos. No mezclar modelos con niveles incompatibles.
4) Panel de monitoreo: éxito por escenario (N1, N2, N3), causas de fallo, latencia y errores de la API, y la versión servida frente a la recomendada.
5) Enlaces profundos (por ejemplo /run/<run_id>) que funcionen al recargar en Vercel (configura rewrites en vercel.json).
Prueba desde la URL publicada, en otra ventana o equipo. Commit, push y PR hacia main.
```

### Paso 10 · Incidente controlado: degradación e intervención
**Hito 3 · Necesita los pasos 6 y 8**

```text
Proyecto Robot Expedition (MLOps). Lee docs/experimentos.md, configs/levels/n3.yaml y pipelines/flow.py. Rama feature/incidente desde main.
Objetivo: la evidencia del incidente (secciones 14 y 17 del enunciado).
1) Mide el modelo recomendado ANTES y DESPUÉS de la perturbación de N3 (bloqueo del corredor y sensor degradado) con la misma suite. En una versión anterior ya se vio que el éxito bajaba de 100 % a 34 % con el bloqueo.
2) Registra la degradación en MLflow y en docs/incidente.md: éxito, causas de fallo, choques por episodio y ejemplos de episodios (run_id y semilla) para verlos en la web.
3) Intervención: entrena por el pipeline un candidato con la perturbación en una fracción de los episodios (o con la inclinación y los rayos mejor discretizados) y evalúalo en N2 y N3.
4) Decide con los criterios de configs/selection.yaml si se acepta o se rechaza. Conserva el candidato y la explicación aunque se rechace.
Commit, push y PR hacia main.
```

### Paso 11 · Rollback y release v1.0
**Hito 4 · Necesita los pasos 8 y 9**

```text
Proyecto Robot Expedition (MLOps). Lee docs/plan-proyecto-final.md, pipelines/flow.py y catalog/catalog.json. Rama feature/rollback desde main.
Objetivo: demostrar recuperación y cerrar la entrega.
1) Comando o flow de rollback: restaurar como servido un run_id anterior identificado, actualizar el catálogo y comprobar con /version y /evaluate que la API sirve ese modelo y que funciona. Deja registro de quién, cuándo, de qué versión a cuál y por qué.
2) Haz una prueba real de rollback y guarda la evidencia (logs y capturas) en docs/evidencia/rollback.md.
3) Reconstrucción: desde un clon limpio en la release, siguiendo solo el README, recupera un modelo histórico con DVC/MLflow y reproduce su evaluación. Anota cualquier paso que falte.
4) Verifica la lista de "Comprobaciones obligatorias" de la sección 16 del enunciado (HTTPS, CORS, nada apunta a localhost, modelo antiguo y recomendado evaluables, errores mostrados como errores, replay rotulado) y marca cada punto en docs/checklist-entrega.md.
5) Crea la release: git tag -a v1.0 -m "Entrega reproducible", push del tag y release en GitHub con gh. El deployment de Vercel y los manifiestos deben citar ese commit.
```

### Paso 12 · README final, informe y defensa
**Hito 4 · Entre todos**

```text
Proyecto Robot Expedition (MLOps). Lee todo docs/, README.md y la sección 17 y 18 del enunciado (resumida en docs/plan-proyecto-final.md). Rama feature/informe desde main.
1) README final: instalación (Python 3.12, torch CPU, npm ci), ejecución, variables (.env.example), arquitectura (diagrama: web en Vercel → API HTTPS → ambiente MuJoCo + modelos; MLflow/DVC; Prefect), reproducción y rollback.
2) docs/informe.md (breve): decisiones, resultados por nivel, finalistas con 3 semillas, incidente, límites, costo (tiempo de CPU), siguiente hipótesis razonable y contribuciones de cada integrante.
3) docs/guion-defensa.md siguiendo el guion sugerido del enunciado: problema y misión; baseline y evolución de dificultad; hipótesis que mejoraron o empeoraron; demo de un modelo histórico y del recomendado desde Vercel; incidente y rollback; costo y límites. Agrega una lista de preguntas probables con su respuesta (contrato del ambiente, versionamiento, cómo desplegar y reproducir). TODOS deben poder explicarlas.
Verifica que cada afirmación tenga evidencia (run_id, archivo o captura). Commit, push y PR hacia main.
```

## 5. Recordatorios

- **Primero un ciclo completo simple, después adornos:** N1 + PPO + MLflow +
  API + web en Vercel funcionando, antes de pulir gráficos o física (lo dice
  el enunciado).
- **Todos explican todo:** cada integrante debe poder explicar el contrato del
  ambiente, el versionamiento y cómo desplegar y reproducir. Revisen lo que
  genere Claude; no basta con pegar el prompt.
- **No se borran intentos:** los runs fallidos o rechazados también suman,
  porque son evidencia.
- **El test reservado** no se sube al repositorio público.
- Antes de cada PR: `python -m pytest -q` y, si tocaron la web,
  `npm run build`.
