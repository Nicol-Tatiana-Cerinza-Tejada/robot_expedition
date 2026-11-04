"""Exporta cada PPO del catalogo a un adaptador numpy y valida su compatibilidad.

    python scripts/export_numpy_policies.py

Para servir la API sin torch (por ejemplo en un plan gratuito con 512 MB),
cada PPO se exporta a catalog/adapters/<run_id>.npz. La validacion corre las
suites fijas de N1, N2 y N3 con el adaptador y exige que los casos coincidan
uno a uno con catalog/results/<run_id>/<nivel>.json (evaluados con el modelo
original de Stable-Baselines3). El resumen queda en
docs/evidencia/adaptador-numpy.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines import catalog as cat  # noqa: E402
from pipelines.evaluate import evaluate  # noqa: E402
from pipelines.policies import NumpyPPOPolicy, adapter_path, export_ppo_numpy, model_files, sha256_file  # noqa: E402


def strip(cases: list[dict]) -> list[dict]:
    return [{k: v for k, v in c.items() if not k.startswith("latency")} for c in cases]


def main() -> None:
    paths = cat.Paths()
    report = {}
    for run_id, manifest in cat.load_manifests(paths).items():
        if manifest["algorithm"] != "ppo" or manifest.get("status") != "completed":
            continue
        weights, normalization = model_files(paths.models, manifest)
        if sha256_file(weights) != manifest["model_sha256"]:
            raise SystemExit(f"{run_id}: los pesos no coinciden con el manifiesto")
        out = export_ppo_numpy(weights, normalization, adapter_path(paths.models, run_id))
        policy = NumpyPPOPolicy(out)
        levels = {}
        for level_id in cat.LEVELS:
            reference = json.loads((paths.results / run_id / f"{level_id}.json").read_text(encoding="utf-8"))
            result = evaluate(policy, level_id, f"suite-{level_id}-v1")
            same = strip(result["cases"]) == strip(reference["cases"])
            levels[level_id] = {"identical_cases": same, "episodes": len(result["cases"]),
                                "success_rate": result["metrics"]["success_rate"],
                                "latency_ms_mean": result["metrics"]["latency_ms_mean"]}
            if not same:
                raise SystemExit(f"{run_id} {level_id}: el adaptador NO reproduce los casos del modelo original")
        report[run_id] = {"experiment_id": manifest["experiment_id"], "seed": manifest["seed"],
                          "model_sha256": manifest["model_sha256"], "adapter": str(out.relative_to(ROOT)),
                          "adapter_sha256": sha256_file(out), "levels": levels}
        print(f"{run_id[:8]} {manifest['experiment_id']} s{manifest['seed']}: "
              + ", ".join(f"{k} {v['success_rate']:.0%} idéntico" for k, v in levels.items()))
    evidence = ROOT / "docs" / "evidencia" / "adaptador-numpy.json"
    evidence.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(report)} adaptadores validados -> {evidence.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
