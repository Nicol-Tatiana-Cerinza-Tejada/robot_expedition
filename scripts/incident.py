"""Incidente controlado (paso 10): degradacion del modelo recomendado por la perturbacion de N3.

    python scripts/incident.py                # usa el recomendado de N2 del catalogo publicado
    python scripts/incident.py --run <run_id>

Evalua el MISMO modelo con las MISMAS semillas (las de suite-n3-v1) en cuatro
condiciones, para separar las causas de la caida:

    n2           sin perturbacion (antes)
    bloqueo      N2 + bloqueo del corredor
    sensor       N2 + ruido 0.08 m y rayo frontal muerto
    n3           bloqueo + sensor (despues; es el nivel N3)

Guarda docs/resultados/incidente.json y registra un run de MLflow
(experimento robot-expedition-incidentes) con las metricas por condicion.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines import catalog as cat  # noqa: E402
from pipelines.evaluate import load_suite, run_case, summarize  # noqa: E402
from pipelines.policies import verified_policy  # noqa: E402
from robot_expedition.envs.beacon_expedition import (  # noqa: E402
    ENVIRONMENT_VERSION, BeaconExpeditionEnv, load_level_config,
)

N2 = load_level_config("n2")
N3 = load_level_config("n3")
CONDITIONS = {
    "n2": dict(N2),
    "bloqueo": {**N2, "blocking": True},
    "sensor": {**N2, "ray_noise": N3["ray_noise"], "dead_ray": N3["dead_ray"]},
    "n3": dict(N3),
}


def measure(policy, seeds: list[int]) -> dict:
    out = {}
    for name, level in CONDITIONS.items():
        env = BeaconExpeditionEnv(level_config=level, max_steps=400)
        cases = [run_case(env, policy, seed) for seed in seeds]
        env.close()
        out[name] = {"level": {k: level[k] for k in ("blocking", "ray_noise", "dead_ray")},
                     "metrics": summarize(cases, int(level["beacons"])), "cases": cases}
        m = out[name]["metrics"]
        print(f"{name:8s} éxito {m['success_rate']:.0%}  fallos {m['failures_by_cause']}  "
              f"choques/ep {m['collisions_per_episode']}")
    return out


def log_mlflow(run_id: str, manifest: dict, result: dict) -> str | None:
    try:
        import mlflow
        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{ROOT / 'mlflow.db'}"))
        mlflow.set_experiment("robot-expedition-incidentes")
        with mlflow.start_run(run_name=f"incidente-n3-{run_id[:8]}") as run:
            mlflow.set_tags({"model_run_id": run_id, "experiment_id": manifest["experiment_id"],
                             "environment_version": ENVIRONMENT_VERSION, "suite": "suite-n3-v1 (semillas)",
                             "tipo": "incidente controlado"})
            for name, data in result["conditions"].items():
                m = data["metrics"]
                mlflow.log_metrics({f"{name}/success_rate": m["success_rate"],
                                    f"{name}/collisions_per_episode": m["collisions_per_episode"],
                                    f"{name}/steps_mean": m["steps_mean"]})
                for cause, count in m["failures_by_cause"].items():
                    mlflow.log_metric(f"{name}/fail_{cause}", count)
            mlflow.log_artifact(str(ROOT / "docs" / "resultados" / "incidente.json"))
            return run.info.run_id
    except Exception as exc:                     # el incidente queda en el JSON aunque MLflow no este
        print(f"MLflow no disponible: {exc}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", help="run_id; por defecto el recomendado de N2 del catálogo")
    args = parser.parse_args()
    paths = cat.Paths()
    catalog = cat.load_catalog(paths)
    run_id = args.run or catalog["recommended_run_id"]["n2"]
    manifest = cat.load_manifests(paths)[run_id]
    policy = verified_policy(paths.models, manifest)
    suite = load_suite("suite-n3-v1")
    print(f"modelo {run_id} ({manifest['experiment_id']}, semilla {manifest['seed']}) · semillas de suite-n3-v1")
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_run_id": run_id, "experiment_id": manifest["experiment_id"], "model_seed": manifest["seed"],
        "model_sha256": manifest["model_sha256"], "environment_version": ENVIRONMENT_VERSION,
        "catalog_version": catalog["catalog_version"], "seeds_from": "suite-n3-v1",
        "suite_sha256": suite["suite_sha256"], "git_commit": cat._git(ROOT, "rev-parse", "HEAD"),
        "conditions": measure(policy, suite["seeds"]),
    }
    out = ROOT / "docs" / "resultados" / "incidente.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["mlflow_run_id"] = log_mlflow(run_id, manifest, result)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)} · MLflow {result['mlflow_run_id']}")


if __name__ == "__main__":
    main()
