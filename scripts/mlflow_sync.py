"""Copia los runs del MLflow local (mlflow.db + mlruns/) a un MLflow remoto con UI publica (DagsHub).

    export MLFLOW_TRACKING_USERNAME=<usuario DagsHub>
    export MLFLOW_TRACKING_PASSWORD=<token DagsHub>
    python scripts/mlflow_sync.py --remote https://dagshub.com/tomas-gonzalez2006/robot_expedition.mlflow

Por cada run copia nombre, tags, parametros, la historia completa de metricas
y los artefactos, y agrega el tag source_run_id con el run_id local (el que
citan los manifiestos). Escribe catalog/mlflow-remote.json con el enlace de
cada run; `pipelines/catalog.py build` lo usa como enlace MLflow en la web.
Es idempotente: los runs ya copiados se saltan.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "catalog" / "mlflow-remote.json"
EXPERIMENTS = ("robot-expedition", "robot-expedition-incidentes")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remote", required=True, help="URI de tracking remoto (DagsHub: https://dagshub.com/<u>/<repo>.mlflow)")
    parser.add_argument("--source", default=f"sqlite:///{ROOT / 'mlflow.db'}")
    args = parser.parse_args()

    from mlflow.entities import Metric, Param, RunTag
    from mlflow.tracking import MlflowClient

    src, dst = MlflowClient(tracking_uri=args.source), MlflowClient(tracking_uri=args.remote)
    mapping = json.loads(MAPPING.read_text(encoding="utf-8")) if MAPPING.exists() else {}
    for name in EXPERIMENTS:
        experiment = src.get_experiment_by_name(name)
        if experiment is None:
            continue
        remote = dst.get_experiment_by_name(name)
        remote_id = remote.experiment_id if remote else dst.create_experiment(name)
        for run in src.search_runs([experiment.experiment_id], max_results=1000):
            local_id = run.info.run_id
            if local_id in mapping or run.info.status == "RUNNING":
                continue
            tags = {**run.data.tags, "source_run_id": local_id, "source_tracking": "mlflow.db local del equipo"}
            created = dst.create_run(remote_id, start_time=run.info.start_time, run_name=run.info.run_name,
                                     tags={k: v for k, v in tags.items() if not k.startswith("mlflow.log-model")})
            rid = created.info.run_id
            params = [Param(k, v) for k, v in run.data.params.items()]
            for i in range(0, len(params), 100):
                dst.log_batch(rid, params=params[i:i + 100])
            metrics = [m for key in run.data.metrics for m in src.get_metric_history(local_id, key)]
            metrics = [Metric(m.key, m.value, m.timestamp, m.step) for m in metrics]
            for i in range(0, len(metrics), 1000):
                dst.log_batch(rid, metrics=metrics[i:i + 1000])
            with tempfile.TemporaryDirectory() as tmp:
                local_dir = src.download_artifacts(local_id, "", tmp)
                if any(Path(local_dir).iterdir()):
                    dst.log_artifacts(rid, local_dir)
            dst.set_terminated(rid, status=run.info.status, end_time=run.info.end_time)
            base = args.remote.rstrip("/")
            mapping[local_id] = {"remote_run_id": rid, "experiment_id": remote_id,
                                 "url": f"{base}/#/experiments/{remote_id}/runs/{rid}"}
            MAPPING.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
            print(f"{run.info.run_name}: {local_id[:8]} -> {rid[:8]}")
    print(f"{len(mapping)} runs enlazados en {MAPPING.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
