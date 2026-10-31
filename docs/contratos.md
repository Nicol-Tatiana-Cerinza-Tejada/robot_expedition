# Contratos del proyecto

Este documento fija la interfaz común descrita en la sección 3 de
`docs/plan-proyecto-final.md`. Los cambios incompatibles requieren actualizar
este documento y avisar al equipo.

## Niveles y configuración

N1 usa una baliza (B1), dos rocas y terreno sin dunas; el agente visita B1 y
regresa a la base. N2 usa B1, B2, cinco rocas y dunas. N3 es N2 con bloqueo del
corredor al visitar B1, ruido de rayos σ=0.08 m y el rayo central muerto.

Cada YAML contiene `level_id`, `beacons`, `active_rocks`, `dunes`, `blocking`,
`ray_noise` y `dead_ray`. Todos los niveles conservan observación de 20
`float32` y `Discrete(5)`. La versión del ambiente es
`robot-expedition-3d/1.0.0`; el hash SHA-256 de código y configuración se
obtiene con `environment_hash(config)`.

## Configuración de experimento

Los experimentos viven en `configs/experiments/exp-XXX.yaml` y declaran
hipótesis, nivel, algoritmo, presupuesto, semillas, hiperparámetros,
normalización y `parent_run_id`.

## Manifiesto

Cada `manifests/<run_id>.json` debe incluir `run_id`, `experiment_id`,
`level_id`, `algorithm`, `environment_version`, `git_commit`,
`config_sha256`, `model_uri`, `model_sha256`, `normalization_uri`,
`obs_spec`, `action_spec`, `runtime_ref`, `evaluation_suite_id`, `seed`,
`budget_timesteps`, `parent_run_id`, `status` y `metrics`. Los estados válidos
son `completed`, `failed`, `interrupted` y `rejected`.

## Catálogo

`catalog/catalog.json` se genera desde los manifiestos. Contiene la lista de
runs con métricas y estado, un `recommended_run_id` por nivel y
`served_version`. No se sobrescriben artefactos silenciosamente.

## API

| Ruta | Contrato |
|---|---|
| `GET /health` | Estado del servicio |
| `GET /version` | Commit, release y versión del ambiente |
| `GET /catalog` | Catálogo de runs |
| `GET /runs/{run_id}` | Manifiesto del run |
| `POST /evaluate` | `{run_id, level_id, seeds}`; devuelve métricas, casos y cuadros |
| `POST /sim/reset` | Crea una sesión de simulación |
| `POST /sim/step` | Ejecuta una acción manual o por regla en una sesión |

## Cuadro de episodio

Cada cuadro mantiene el formato consumido por la vista 3D:

```text
[x, y, z, qw, qx, qy, qz, etapa, bateria, accion, recompensa, choque, [9 rayos]]
```
