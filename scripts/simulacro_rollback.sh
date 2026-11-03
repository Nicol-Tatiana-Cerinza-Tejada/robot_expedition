#!/usr/bin/env bash
# Simulacro de promocion erronea + rollback contra la API (API=http://... ; por defecto local). Deja todo en docs/evidencia/rollback-log.txt
set -euo pipefail
cd "$(dirname "$0")/.."
API=${API:-http://127.0.0.1:8000}

PY=${PYTHON:-python}
export MLFLOW_TRACKING_URI=http://127.0.0.1:5055 CATALOG_ACTOR=nicol OMP_NUM_THREADS=1
GOOD=92cdc692fdca465b917fa7c5e8a9902d     # exp-004 s1: recomendado de N2 en catalog-v2
BAD=4b9b4353fd4f41c4b99a2d43ce290095      # exp-005 s1: entrenado en N3, 16 % en N2
version() { curl -s $API/version | $PY -c "import json,sys;v=json.load(sys.stdin);print('  /version ->', v['served_version'], '· n2 =', v['recommended_run_id']['n2'], '· commit', v['git_commit'][:10])"; }
evaluate() { curl -s -X POST $API/evaluate -H 'Content-Type: application/json' \
  -d "{\"run_id\":\"$1\",\"level_id\":\"n2\",\"suite_id\":\"suite-n2-v1\",\"episodes\":50}" | $PY -c "
import json,sys;r=json.load(sys.stdin);m=r['metrics']
print(f\"  /evaluate {r['run_id'][:8]} en N2 (suite-n2-v1, {m['episodes']} episodios): éxito {m['success_rate']:.0%}, fallos {m['failures_by_cause']}, choques/ep {m['collisions_per_episode']}, modelo sha {r['model_sha256'][:12]}\")"; }
echo "== $(date -u +%FT%TZ) · 0. Estado inicial"; version; evaluate $GOOD
echo; echo "== $(date -u +%FT%TZ) · 1. Promoción manual errónea (simulacro)"
$PY pipelines/catalog.py promote --level n2 --to $BAD --reason "SIMULACRO: promoción manual de exp-005 s1 a N2 sin pasar los criterios" | tail -1
version
echo; echo "== $(date -u +%FT%TZ) · 2. Detección: el recomendado servido en N2 se degrada"
evaluate $BAD
echo; echo "== $(date -u +%FT%TZ) · 3. Rollback con el flow de Prefect a la versión anterior identificada (catalog-v2: $GOOD)"
$PY pipelines/flow.py --rollback n2 --to $GOOD --api-url $API --reason "el modelo promovido cae a 16 % en N2 (paso 2 del simulacro); se restaura el recomendado de catalog-v2" 2>&1 | grep -E "Finished in state|evidence" | sed 's/^/  /'
version
echo; echo "== $(date -u +%FT%TZ) · 4. Comprobación: el modelo restaurado funciona"
evaluate $GOOD
echo; echo "== Historial del catálogo"
$PY pipelines/catalog.py history | sed 's/^/  /'
