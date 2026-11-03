"""Pipeline de Robot Expedition con Prefect (paso 8 del plan).

Cada etapa es una task que deja estado y evidencia:

1. validar perfil, rutas, esquema y compatibilidad del ambiente;
2. correr pytest;
3. entrenar un candidato (o cargar un run existente compatible);
4. evaluarlo con la suite fija de cada nivel (resultados por caso);
5. verificar el registro: manifiesto, SHA-256, puntero DVC y run de MLflow;
6. aplicar los criterios de configs/selection.yaml;
7. publicar catalog/catalog.json (version nueva solo si el contenido cambia);
8. comprobar la version que sirve la API (/version y /catalog).

    python pipelines/flow.py --config configs/experiments/exp-005.yaml --seed 2
    python pipelines/flow.py --runs <run_id> [<run_id> ...]      # sin entrenar
    python pipelines/flow.py --rollback n2 --to <run_id> --reason "..."

La evidencia de cada ejecucion queda en docs/evidencia/pipeline/<fecha>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from prefect import flow, get_run_logger, task

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines import catalog as cat  # noqa: E402
from pipelines.policies import sha256_file, model_files  # noqa: E402
from robot_expedition.envs.beacon_expedition import ENVIRONMENT_VERSION, environment_hash  # noqa: E402

EVIDENCE_DIR = ROOT / "docs" / "evidencia" / "pipeline"


@task(name="1-validar")
def validate(config_path: str | None, run_ids: list[str]) -> dict:
    """Perfil (config), rutas, esquema de manifiestos y compatibilidad del ambiente."""
    from pipelines.train import read_config
    log = get_run_logger()
    paths = cat.Paths()
    checks = {}
    for rel in ("configs/levels", "configs/suites", "configs/selection.yaml", "manifests", "pipelines/train.py"):
        checks[rel] = (ROOT / rel).exists()
    criteria = cat.load_selection(paths)
    checks["selection_version"] = criteria["version"]
    config = None
    if config_path:
        config = read_config(Path(config_path))
        checks["config"] = {"experiment_id": config["experiment_id"], "level_id": config["level_id"],
                            "algorithm": config["algorithm"], "budget_timesteps": config["budget_timesteps"],
                            "environment_hash": environment_hash(config["level_id"])}
    manifests = cat.load_manifests(paths)
    required = {"run_id", "experiment_id", "level_id", "algorithm", "environment_version", "git_commit",
                "model_sha256", "status", "seed", "budget_timesteps"}
    bad = {rid: sorted(required - m.keys()) for rid, m in manifests.items() if required - m.keys()}
    checks["manifests"] = len(manifests)
    checks["manifests_with_missing_fields"] = bad
    for rid in run_ids:
        m = manifests.get(rid)
        if m is None:
            raise ValueError(f"no existe manifests/{rid}.json")
        if m["environment_version"].split("/")[0] != ENVIRONMENT_VERSION.split("/")[0]:
            raise ValueError(f"{rid} usa {m['environment_version']}, incompatible con {ENVIRONMENT_VERSION}")
    if not all(v for k, v in checks.items() if k in ("configs/levels", "configs/suites", "configs/selection.yaml")):
        raise FileNotFoundError(f"faltan rutas: {checks}")
    if bad:
        raise ValueError(f"manifiestos sin campos obligatorios: {bad}")
    log.info("validación OK: %s", checks)
    return checks


@task(name="2-pytest")
def run_tests(skip: bool) -> dict:
    if skip:
        return {"skipped": True}
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT,
                            capture_output=True, text=True)
    summary = (result.stdout.strip().splitlines() or ["(sin salida)"])[-1]
    get_run_logger().info("pytest: %s", summary)
    if result.returncode:
        raise RuntimeError(f"pytest falló: {summary}\n{result.stdout[-2000:]}")
    return {"skipped": False, "summary": summary}


@task(name="3-entrenar")
def train(config_path: str, seeds: list[int], budget: int | None) -> dict:
    """Entrena una semilla por subproceso. Un fallo deja su manifiesto (failed/interrupted) y no borra nada."""
    log = get_run_logger()
    done, failed = [], []
    for seed in seeds:
        before = {p.name for p in (ROOT / "manifests").glob("*.json")}
        cmd = [sys.executable, "pipelines/train.py", "--config", config_path, "--seed", str(seed)]
        if budget:
            cmd += ["--budget-timesteps", str(budget)]
        log.info("entrenando: %s", " ".join(cmd))
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        ids = re.findall(r"Run ([0-9a-f]{32}):", result.stdout)
        if result.returncode == 0 and ids:
            done += ids
            continue
        new = sorted({p.name for p in (ROOT / "manifests").glob("*.json")} - before)
        diagnosis = (result.stderr.strip().splitlines() or ["sin diagnóstico"])[-1]
        failed.append({"seed": seed, "manifests": new, "diagnosis": diagnosis})
        log.warning("semilla %s falló: %s (manifiestos: %s)", seed, diagnosis, new)
    return {"run_ids": done, "failed": failed}


@task(name="4-evaluar")
def evaluate_runs(run_ids: list[str]) -> dict:
    log = get_run_logger()
    report = cat.evaluate_all(cat.Paths(), [*cat.BASELINES, *run_ids], log=log.info)
    return report


@task(name="5-registro")
def verify_registry(run_ids: list[str]) -> dict:
    """Comprueba la procedencia: manifiesto, hash del modelo, puntero DVC y run en MLflow."""
    paths = cat.Paths()
    manifests = cat.load_manifests(paths)
    out = {}
    for rid in run_ids:
        m = manifests[rid]
        weights, _ = model_files(paths.models, m)
        info = cat.training_info(paths, rid)
        out[rid] = {
            "status": m["status"],
            "git_commit": m["git_commit"],
            "model_sha256_ok": weights.exists() and sha256_file(weights) == m["model_sha256"],
            "dvc_pointer": (paths.models / f"{rid}.dvc").exists(),
            "mlflow_run": bool(info),
            "training_time_s": info.get("training_time_s"),
        }
        if not out[rid]["model_sha256_ok"]:
            raise ValueError(f"{rid}: los pesos no coinciden con el manifiesto")
    get_run_logger().info("registro: %s", out)
    return out


@task(name="6-7-seleccionar-y-publicar")
def select_and_publish(reason: str) -> dict:
    paths = cat.Paths()
    result = cat.publish(paths, cat.build_catalog(paths), action="publish", reason=reason)
    catalog = cat.load_catalog(paths)
    get_run_logger().info("catálogo v%s (%s) · recomendados %s", catalog["catalog_version"],
                          "nuevo" if result["changed"] else "sin cambios", catalog["recommended_run_id"])
    return {**result, "recommended_run_id": catalog["recommended_run_id"], "decisions": catalog["decisions"]}


@task(name="rollback")
def do_rollback(level_id: str, run_id: str, reason: str) -> dict:
    return cat.rollback(cat.Paths(), level_id, run_id, reason)


@task(name="8-version-servida")
def check_served(api_url: str | None) -> dict:
    """Compara el catalogo local con lo que sirve la API desplegada."""
    local = cat.load_catalog(cat.Paths())
    if not api_url:
        return {"checked": False, "reason": "sin API_URL; despliega y vuelve a correr con --api-url"}

    def get(path: str) -> dict:
        with urllib.request.urlopen(f"{api_url.rstrip('/')}{path}", timeout=30) as response:
            return json.loads(response.read())

    try:
        version, served = get("/version"), get("/catalog")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"checked": False, "reason": f"la API no responde: {exc}"}
    same = served.get("content_sha256") == local.get("content_sha256")
    result = {"checked": True, "api_url": api_url, "api_git_commit": version.get("git_commit"),
              "served_version": version.get("served_version"), "local_version": local.get("served_version"),
              "served_recommended": version.get("recommended_run_id"),
              "local_recommended": local.get("recommended_run_id"), "in_sync": same}
    log = get_run_logger()
    (log.info if same else log.warning)("API %s sirve %s; catálogo local %s", api_url,
                                        result["served_version"], result["local_version"])
    return result


def _evidence(name: str, data: dict) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = EVIDENCE_DIR / f"{stamp}-{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return path


@flow(name="robot-expedition-pipeline")
def pipeline(config: str | None = None, seeds: list[int] | None = None, runs: list[str] | None = None,
             budget: int | None = None, skip_tests: bool = False, api_url: str | None = None,
             reason: str = "publicación del pipeline") -> dict:
    record = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "params": {"config": config, "seeds": seeds, "runs": runs, "budget": budget,
                         "skip_tests": skip_tests, "api_url": api_url}}
    run_ids = list(runs or [])
    record["1_validar"] = validate(config, run_ids)
    record["2_pytest"] = run_tests(skip_tests)
    if config:
        seeds = seeds or [int(s) for s in __import__("yaml").safe_load(Path(config).read_text())["seeds"]]
        trained = train(config, seeds, budget)
        record["3_entrenar"] = trained
        run_ids += trained["run_ids"]
    else:
        record["3_entrenar"] = {"skipped": True, "loaded_runs": run_ids}
    record["4_evaluar"] = evaluate_runs(run_ids)
    record["5_registro"] = verify_registry(run_ids)
    record["6_7_publicar"] = select_and_publish(reason)
    record["8_version_servida"] = check_served(api_url)
    record["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record["evidence"] = str(_evidence("pipeline", record).relative_to(ROOT))
    get_run_logger().info("evidencia: %s", record["evidence"])
    return record


@flow(name="robot-expedition-rollback")
def rollback_flow(level_id: str, to_run_id: str, reason: str, api_url: str | None = None) -> dict:
    record = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "level_id": level_id,
              "to_run_id": to_run_id, "reason": reason, "actor": cat.actor()}
    record["rollback"] = do_rollback(level_id, to_run_id, reason)
    record["4_evaluar"] = evaluate_runs([to_run_id])
    record["8_version_servida"] = check_served(api_url)
    record["evidence"] = str(_evidence(f"rollback-{level_id}", record).relative_to(ROOT))
    return record


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="configs/experiments/exp-XXX.yaml (entrena)")
    parser.add_argument("--seed", type=int, action="append", help="semilla(s); por defecto las del config")
    parser.add_argument("--runs", nargs="*", default=[], help="run_ids ya entrenados (no entrena)")
    parser.add_argument("--budget-timesteps", type=int)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--api-url", default=os.environ.get("API_URL"))
    parser.add_argument("--reason", default="publicación del pipeline")
    parser.add_argument("--rollback", choices=cat.LEVELS, help="nivel al que se le hace rollback")
    parser.add_argument("--to", help="run_id a restaurar (con --rollback)")
    args = parser.parse_args(argv)
    if args.rollback:
        if not args.to:
            parser.error("--rollback necesita --to <run_id>")
        result = rollback_flow(args.rollback, args.to, args.reason, args.api_url)
    else:
        result = pipeline(args.config, args.seed, args.runs, args.budget_timesteps, args.skip_tests,
                          args.api_url, args.reason)
    print(json.dumps({k: result[k] for k in ("evidence",) if k in result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
