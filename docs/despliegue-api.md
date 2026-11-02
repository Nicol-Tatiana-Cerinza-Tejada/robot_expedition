# API de Robot Expedition: ejecución y despliegue

La API (`api/main.py`, FastAPI) usa **el mismo ambiente MuJoCo y las mismas
políticas** que el entrenamiento y la suite de evaluación (`pipelines/`). Así,
la web evalúa cada modelo con sus reglas originales. Una prueba
(`test_evaluate_matches_the_offline_suite`) comprueba que la API y la suite
offline dan los mismos casos.

## Rutas

| Ruta | Qué hace |
|---|---|
| `GET /health` | Estado, tiempo encendida y sesiones abiertas |
| `GET /version` | Versión de la API, `git_commit`, `release`, `environment_version`, hash del ambiente por nivel y versión servida |
| `GET /monitor` | Solicitudes, errores y latencia (media y p95) por ruta, y los últimos errores |
| `GET /catalog` | `catalog/catalog.json` si el pipeline lo publicó; si no, los manifiestos de `manifests/` (sin `smoke/`). Siempre agrega `baseline-random` y `baseline-rule` |
| `GET /runs/{run_id}` | El manifiesto del run, o la descripción del baseline |
| `POST /evaluate` | Body `{run_id, level_id, seeds}` (hasta 20 semillas) o `{run_id, level_id, suite_id, episodes}`. Devuelve `metrics`, `cases`, `map` y `episode` con los cuadros del primer caso |
| `POST /sim/reset` | Body `{level_id, seed, policy}`. `policy` puede ser `manual` (por defecto), `baseline-rule`, `baseline-random` o un `run_id`. Devuelve `session_id`, `map` y el primer `frame` |
| `POST /sim/step` | Body `{session_id, action}`. Si es manual, `action` va de 0 a 4; si la sesión tiene política, se omite `action` y decide la política |

**Errores** (siempre JSON con `detail`):

| Código | Cuándo |
|---|---|
| `404` | Run, suite o sesión inexistente |
| `409` | El SHA-256 del modelo no coincide con su manifiesto, el ambiente es incompatible o el episodio ya terminó |
| `422` | Datos inválidos |
| `503` | Los pesos no se pueden recuperar |

Las sesiones manuales caducan a los 15 minutos y hay como máximo 50 abiertas.

## Ejecutar en local

```bash
python -m uvicorn api.main:app --reload --port 8000
# web: en web/.env.local -> VITE_API_BASE_URL=http://localhost:8000 ; luego npm run dev
```

Lo verificamos con la web de Vite en `localhost:5173`. Funcionan:
- el catálogo;
- "Evaluar modelo" (regla en N2: éxito, 2 balizas, 23.6 m);
- el control manual con las flechas.

Una evaluación de 5 episodios tarda unos 0.3 s, muy por debajo del límite de
12 s de la web.

## Desplegar en Hugging Face Spaces (gratis, HTTPS)

1. Crear un Space nuevo con **SDK: Docker** (por ejemplo `robot-expedition-api`).
2. Agregar el Space como remoto y subir el repositorio (usa el `Dockerfile` de
   la raíz y escucha en el puerto 7860):
   ```bash
   git remote add space https://huggingface.co/spaces/<usuario>/robot-expedition-api
   git push space main
   ```
   Hugging Face pide que el `README.md` del Space tenga al inicio
   `sdk: docker` y `app_port: 7860` en su encabezado YAML. Se puede subir
   desde una rama de despliegue que lo agregue.
3. En **Settings → Variables and secrets** del Space:
   - `ALLOWED_ORIGINS` = la URL de Vercel (por ejemplo `https://web-five-gules-83.vercel.app`).
   - `GIT_COMMIT` y `RELEASE`, para que `/version` identifique el código servido.
   - Secretos `DVC_REMOTE_USER` y `DVC_REMOTE_PASSWORD` (usuario y token de
     DagsHub), para que la API descargue los pesos con `dvc pull`.
4. Comprobar `https://<usuario>-robot-expedition-api.hf.space/health` y `/version`.
5. En Vercel, poner `VITE_API_BASE_URL` = esa URL HTTPS y volver a desplegar
   la web.

La imagen también sirve en Render o en cualquier servidor con Docker:

```bash
docker build -t robot-expedition-api --build-arg GIT_COMMIT=$(git rev-parse HEAD) .
docker run -p 7860:7860 -e ALLOWED_ORIGINS=https://web-five-gules-83.vercel.app robot-expedition-api
```

## Modelos

La API no guarda pesos en Git. Para cada run del catálogo:
1. Busca `models/<run_id>/` (`qlearning.npz`, o `ppo_model.zip` + `vecnormalize.pkl`).
2. Si no los encuentra y `API_DVC_PULL=1`, ejecuta `dvc pull models/<run_id>.dvc`.
3. Antes de usarlos, **verifica el SHA-256 contra el manifiesto**.

El remoto DVC actual (DagsHub de Tomás) es privado: hay que hacerlo público o
dar un token de lectura para que la API desplegada y el docente puedan
recuperar los modelos.
