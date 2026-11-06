# Checklist de entrega

> Secciones 16 y 17 del enunciado. Se marca ✅ solo lo comprobado, con su
> evidencia. ⏳ es un paso pendiente de una persona del equipo; dice qué falta
> y quién lo hace.

## Comprobaciones obligatorias (sección 16)

| # | Comprobación | Estado | Evidencia o pendiente |
|---|---|---|---|
| 1 | La URL abre y permite acceder al nivel y al experimento seleccionado | ✅ | Prueba reproducible contra producción: portada, catálogo, evaluación del recomendado N2, 85 cuadros, control manual y recarga de `/run/<id>`. [Evidencia](evidencia/produccion-v1.json) |
| 2 | La API usa HTTPS y admite el origen del frontend con CORS apropiado | ✅ | `https://robot-expedition-api.onrender.com/health` respondió y `/catalog` devolvió `Access-Control-Allow-Origin: https://web-five-gules-83.vercel.app`. [Evidencia](evidencia/produccion-v1.json) |
| 3 | Las rutas de producción no apuntan a `localhost` ni a `127.0.0.1` | ✅ | El bundle desplegado contiene `https://robot-expedition-api.onrender.com` y la prueba rechaza cualquier URL local. `VITE_API_BASE_URL` quedó configurada en Vercel. [Evidencia](evidencia/produccion-v1.json) |
| 4 | Los modelos y escenarios se recuperan sin depender de carpetas personales | ✅ | Release `models-v2` (ZIP público con `SHA256SUMS.txt`), DVC (DagsHub) y la API los descarga de la release y verifica su SHA-256. Prueba de reconstrucción en un clon limpio: [rollback.md §3](evidencia/rollback.md#3-reconstrucción-desde-un-clon-limpio) |
| 5 | Se puede evaluar un modelo antiguo y el recomendado, con sus contratos correctos | ✅ | La API verifica el SHA-256 de cada modelo contra su manifiesto (409 si no coincide) y la versión del ambiente. La web avisa cuando un modelo se evalúa en un nivel distinto al de entrenamiento. Probado con `4d91d98f` (Q-learning, primer run) y `92cdc692` (recomendado de N2) |
| 6 | Un error de servicio se muestra como error; un replay se identifica como replay | ✅ | Avisos de la web para `ApiError` (404, 409, 422 y 503, y más de 12 s). El modo `REPLAY` se rotula en la insignia y en el aviso. Pruebas `test_evaluate_errors`, `test_tampered_model_is_rejected` y `test_missing_weights_is_a_clear_error` |
| 7 | La release y el deployment identifican el código entregado | ✅ release · ⏳ último commit | Producción informa `release=v1.0`, `git_commit=6504ddc1` y `served_version=catalog-v6`. El tag existe. **Pendiente:** Nicol debe desplegar el último commit de `main` en Render para incorporar los cambios posteriores al tag |

## Paquete final (sección 17)

| Entregable | Estado | Dónde |
|---|---|---|
| URL de Vercel y repositorio con release o tag identificable | ✅ | Web: `https://web-five-gules-83.vercel.app`. API: `https://robot-expedition-api.onrender.com`. Tag `v1.0` |
| README con instalación, ejecución, variables, arquitectura y reproducción | ✅ | [README.md](../README.md) |
| Ficha del ambiente y tres niveles documentados | ✅ | [ambiente-v1.md](ambiente-v1.md) y [mapas/](mapas) |
| Cuatro configuraciones con hipótesis y sus runs y estados en MLflow | ✅ | 5 configuraciones en `configs/experiments/`, 12 runs `completed` y 16 de humo (3 `failed`). MLflow: `mlflow.db` en la release `models-v2`. **Pendiente opcional:** copiarlo al MLflow de DagsHub con `scripts/mlflow_sync.py` (Tomás) para tener el enlace en la web |
| Modelos finales recuperables, normalización, manifiestos y referencias de artefactos | ✅ | `manifests/*.json` (SHA-256, `model_uri`, `normalization_uri`), punteros `models/*.dvc`, release `models-v2` |
| Evaluaciones por caso, comparación de finalistas y presupuesto | ✅ | `catalog/results/`, [experimentos.md](experimentos.md), `docs/resultados/test-final/` |
| Pipeline, evidencia de degradación e intervención, y prueba de rollback | ✅ | `pipelines/flow.py`, [evidencia/pipeline/](evidencia/pipeline), [incidente.md](incidente.md), [evidencia/rollback.md](evidencia/rollback.md) |
| Informe breve y presentación | ✅ | [informe.md](informe.md), [guion-defensa.md](guion-defensa.md) |

## Antes de la sustentación

- [x] Merge de la entrega y tag `v1.0`.
- [x] Crear el servicio en Render y comprobar `/health` y `/version` por HTTPS.
- [x] `VITE_API_BASE_URL` en Vercel y redeploy; comprobar portada, catálogo,
      evaluación, control manual y enlace directo con
      `python scripts/smoke_production.py`.
- [ ] Nicol: desplegar el último commit de `main` en Render y volver a ejecutar
      `python scripts/smoke_production.py --output docs/evidencia/produccion-v1.json`.
- [ ] Render gratuito se duerme tras 15 min sin tráfico: abrir `/health` un
      minuto antes de la demo.
- [ ] Cada integrante practica las preguntas de [guion-defensa.md](guion-defensa.md).
