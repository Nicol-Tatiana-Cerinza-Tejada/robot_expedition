# Checklist de entrega

> Secciones 16 y 17 del enunciado. Se marca ✅ solo lo comprobado, con su
> evidencia. ⏳ es un paso pendiente de una persona del equipo; dice qué falta
> y quién lo hace.

## Comprobaciones obligatorias (sección 16)

| # | Comprobación | Estado | Evidencia o pendiente |
|---|---|---|---|
| 1 | La URL abre y permite acceder al nivel y al experimento seleccionado | ✅ local · ⏳ Vercel | Recorrido en Chrome headless contra la API local: catálogo filtrable por nivel, detalle, enlace `/run/<id>` que sobrevive a la recarga, evaluación y monitoreo, sin errores de consola. Falta repetirlo en `https://web-five-gules-83.vercel.app` cuando la API esté publicada |
| 2 | La API usa HTTPS y admite el origen del frontend con CORS apropiado | ✅ código · ⏳ despliegue | `test_cors_allows_the_vercel_origin_only`. La imagen del Space fija `ALLOWED_ORIGINS` solo a la URL de Vercel (`scripts/build_space.py`). HTTPS lo da Hugging Face Spaces. **Pendiente:** publicar el Space (Nicol, ver README → Despliegue) |
| 3 | Las rutas de producción no apuntan a `localhost` ni a `127.0.0.1` | ✅ | `web/src/api.ts` rechaza en producción una API en localhost o sin HTTPS. **Pendiente:** `VITE_API_BASE_URL` en Vercel = URL del Space (Natalia) |
| 4 | Los modelos y escenarios se recuperan sin depender de carpetas personales | ✅ | Release `models-v2` (ZIP público con `SHA256SUMS.txt`), DVC (DagsHub) y pesos dentro de la imagen del Space. Prueba de reconstrucción en un clon limpio: [rollback.md §3](evidencia/rollback.md#3-reconstrucción-desde-un-clon-limpio) |
| 5 | Se puede evaluar un modelo antiguo y el recomendado, con sus contratos correctos | ✅ | La API verifica el SHA-256 de cada modelo contra su manifiesto (409 si no coincide) y la versión del ambiente. La web avisa cuando un modelo se evalúa en un nivel distinto al de entrenamiento. Probado con `4d91d98f` (Q-learning, primer run) y `92cdc692` (recomendado de N2) |
| 6 | Un error de servicio se muestra como error; un replay se identifica como replay | ✅ | Avisos de la web para `ApiError` (404, 409, 422 y 503, y más de 12 s). El modo `REPLAY` se rotula en la insignia y en el aviso. Pruebas `test_evaluate_errors`, `test_tampered_model_is_rejected` y `test_missing_weights_is_a_clear_error` |
| 7 | La release y el deployment identifican el código entregado | ⏳ | `/version` devuelve `git_commit`, `release`, `served_version` y los hashes del ambiente (`build_space.py` los fija en la imagen). **Pendiente:** tag `v1.0` en `main` tras los merges y redesplegar el Space con `--release v1.0` |

## Paquete final (sección 17)

| Entregable | Estado | Dónde |
|---|---|---|
| URL de Vercel y repositorio con release o tag identificable | ⏳ | Web: `https://web-five-gules-83.vercel.app`. Tag `v1.0` pendiente del merge a `main` |
| README con instalación, ejecución, variables, arquitectura y reproducción | ✅ | [README.md](../README.md) |
| Ficha del ambiente y tres niveles documentados | ✅ | [ambiente-v1.md](ambiente-v1.md) y [mapas/](mapas) |
| Cuatro configuraciones con hipótesis y sus runs y estados en MLflow | ✅ | 5 configuraciones en `configs/experiments/`, 12 runs `completed` y 16 de humo (3 `failed`). MLflow: `mlflow.db` en la release `models-v2`. **Pendiente opcional:** copiarlo al MLflow de DagsHub con `scripts/mlflow_sync.py` (Tomás) para tener el enlace en la web |
| Modelos finales recuperables, normalización, manifiestos y referencias de artefactos | ✅ | `manifests/*.json` (SHA-256, `model_uri`, `normalization_uri`), punteros `models/*.dvc`, release `models-v2` |
| Evaluaciones por caso, comparación de finalistas y presupuesto | ✅ | `catalog/results/`, [experimentos.md](experimentos.md), `docs/resultados/test-final/` |
| Pipeline, evidencia de degradación e intervención, y prueba de rollback | ✅ | `pipelines/flow.py`, [evidencia/pipeline/](evidencia/pipeline), [incidente.md](incidente.md), [evidencia/rollback.md](evidencia/rollback.md) |
| Informe breve y presentación | ✅ | [informe.md](informe.md), [guion-defensa.md](guion-defensa.md) |

## Antes de la sustentación

- [ ] Merge de los PR a `main` y tag `v1.0`.
- [ ] Publicar el Space y comprobar `/health` y `/version` por HTTPS.
- [ ] `VITE_API_BASE_URL` en Vercel y redeploy; repetir el recorrido desde otra ventana.
- [ ] Mantener el Space activo durante la revisión. Los Spaces gratuitos se
      duermen tras 48 h sin uso: abrir `/health` antes de la demo.
- [ ] Cada integrante practica las preguntas de [guion-defensa.md](guion-defensa.md).
