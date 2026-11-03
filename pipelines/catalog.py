"""Catalogo versionado de modelos: evaluacion por nivel, seleccion, publicacion y rollback.

Es la logica pura que usan el flow de Prefect (pipelines/flow.py) y la linea de
comandos. Contratos: docs/contratos.md (seccion catalogo).

    python pipelines/catalog.py build                     # evalua lo pendiente, selecciona y publica
    python pipelines/catalog.py rollback --level n2 --to <run_id> --reason "..."
    python pipelines/catalog.py unpin --level n2 --reason "..."
    python pipelines/catalog.py history

Reglas:
- Cada modelo se evalua con la suite fija de cada nivel; los resultados por
  caso quedan en catalog/results/<run_id>/<nivel>.json y se reutilizan solo si
  coinciden el SHA-256 del modelo, de la suite y el hash del ambiente.
- La seleccion aplica configs/selection.yaml (criterios fijados antes).
- Publicar el mismo contenido no crea version nueva; un contenido distinto crea
  catalog_version + 1 y una linea en catalog/history.jsonl. Nunca se
  sobrescribe en silencio.
- Un rollback fija (pin) el run elegido en ese nivel hasta que se quite el pin,
  para que la siguiente publicacion no lo deshaga sin una decision explicita.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.evaluate import evaluate, load_suite  # noqa: E402
from pipelines.policies import (  # noqa: E402
    ModelIntegrityError, ModelUnavailable, RandomPolicy, RulePolicy, verified_policy,
)
from robot_expedition.envs.beacon_expedition import ENVIRONMENT_VERSION, environment_hash  # noqa: E402

LEVELS = ("n1", "n2", "n3")
BASELINES = {"baseline-rule": RulePolicy, "baseline-random": RandomPolicy}
VOLATILE_KEYS = ("catalog_version", "served_version", "published_at", "published_by", "git_commit",
                 "content_sha256", "previous_version")


class Paths:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.manifests = self.root / "manifests"
        self.models = self.root / "models"
        self.catalog_dir = self.root / "catalog"
        self.results = self.catalog_dir / "results"
        self.catalog = self.catalog_dir / "catalog.json"
        self.history = self.catalog_dir / "history.jsonl"
        self.selection = self.root / "configs" / "selection.yaml"


# ------------------------------------------------------------------ utilidades
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _sha(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(_json(data), encoding="utf-8")
    tmp.replace(path)


def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def actor(root: Path = ROOT) -> str:
    return os.environ.get("CATALOG_ACTOR") or _git(root, "config", "user.name") or getpass.getuser()


def commit_url(repository: str | None, commit: str | None) -> str | None:
    if not repository or not commit or "github.com" not in repository:
        return None
    base = repository.removesuffix(".git").replace("git@github.com:", "https://github.com/")
    return f"{base}/commit/{commit}"


def load_manifests(paths: Paths) -> dict[str, dict]:
    """Manifiestos publicables (manifests/smoke queda fuera)."""
    out = {}
    for path in sorted(paths.manifests.glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        out[manifest["run_id"]] = manifest
    return out


def load_selection(paths: Paths) -> dict:
    criteria = yaml.safe_load(paths.selection.read_text(encoding="utf-8"))
    criteria["sha256"] = hashlib.sha256(paths.selection.read_bytes()).hexdigest()
    return criteria


def load_catalog(paths: Paths) -> dict | None:
    return json.loads(paths.catalog.read_text(encoding="utf-8")) if paths.catalog.exists() else None


# ------------------------------------------------------------------ evaluacion
def _fresh(result_path: Path, model_sha: str | None, level_id: str) -> bool:
    if not result_path.exists():
        return False
    result = json.loads(result_path.read_text(encoding="utf-8"))
    suite = load_suite(f"suite-{level_id}-v1")
    return (result.get("partial") is False
            and result.get("suite_sha256") == suite["suite_sha256"]
            and result.get("environment_hash") == environment_hash(level_id)
            and result.get("policy", {}).get("model_sha256") == model_sha)


def evaluate_run(paths: Paths, run_id: str, manifest: dict | None, levels=LEVELS, force=False) -> dict:
    """Evalua un run (o un baseline) en cada nivel con la suite fija; devuelve {nivel: ruta | error}."""
    out: dict[str, str] = {}
    policy = None
    for level_id in levels:
        result_path = paths.results / run_id / f"{level_id}.json"
        model_sha = manifest.get("model_sha256") if manifest else None
        if not force and _fresh(result_path, model_sha, level_id):
            out[level_id] = str(result_path.relative_to(paths.root))
            continue
        try:
            if policy is None:
                policy = BASELINES[run_id]() if manifest is None else verified_policy(paths.models, manifest)
        except (ModelUnavailable, ModelIntegrityError) as exc:
            return {level: f"error: {exc}" for level in levels}
        info = policy.describe() | {"run_id": run_id}
        result = evaluate(policy, level_id, f"suite-{level_id}-v1", policy_info=info)
        _write(result_path, result)
        out[level_id] = str(result_path.relative_to(paths.root))
    return out


def evaluate_all(paths: Paths, run_ids: list[str] | None = None, force=False, log=print) -> dict:
    manifests = load_manifests(paths)
    targets = run_ids or [*BASELINES, *(r for r, m in manifests.items() if m.get("status") == "completed")]
    report = {}
    for run_id in targets:
        report[run_id] = evaluate_run(paths, run_id, manifests.get(run_id), force=force)
        log(f"evaluado {run_id}: {report[run_id]}")
    return report


def level_metrics(paths: Paths, run_id: str) -> dict[str, dict]:
    out = {}
    for level_id in LEVELS:
        path = paths.results / run_id / f"{level_id}.json"
        if not path.exists():
            continue
        result = json.loads(path.read_text(encoding="utf-8"))
        m = result["metrics"]
        out[level_id] = {
            "success_rate": m["success_rate"], "failures_by_cause": m["failures_by_cause"],
            "beacons_visited_mean": m.get("beacons_visited_mean"), "steps_mean": m["steps_mean"],
            "collisions_per_episode": m["collisions_per_episode"],
            "final_battery_success": m.get("final_battery_success"), "route_efficiency": m.get("route_efficiency"),
            "return_mean": m["return_mean"], "latency_ms_mean": m["latency_ms_mean"],
            "latency_ms_p95": m["latency_ms_p95"], "episodes": m["episodes"],
            "suite_id": result["suite_id"], "suite_sha256": result["suite_sha256"],
            "environment_hash": result["environment_hash"], "partial": result["partial"],
            "evaluated_at": result.get("created_at"), "evaluation_commit": result.get("git_commit"),
            "results_path": str(path.relative_to(paths.root)),
        }
    return out


# ------------------------------------------------------------------ MLflow
def training_info(paths: Paths, run_id: str) -> dict:
    """Duracion y curvas de entrenamiento (resumidas) desde MLflow; se guardan en catalog/results."""
    cache = paths.results / run_id / "training.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{paths.root / 'mlflow.db'}"))
        client = MlflowClient()
        run = client.get_run(run_id)
    except Exception:                                   # sin MLflow local: el catalogo sigue sin curvas
        return {}
    if run.info.end_time is None:
        return {}

    def curve(key: str, bins: int = 30) -> list[list[float]]:
        history = sorted(client.get_metric_history(run_id, key), key=lambda m: m.step)
        if not history:
            return []
        top = max(m.step for m in history) or 1
        buckets: dict[int, list[float]] = {}
        for m in history:
            buckets.setdefault(min(bins - 1, int(m.step / top * bins)), []).append(m.value)
        return [[round((b + 1) / bins * top), round(sum(v) / len(v), 4)] for b, v in sorted(buckets.items())]

    info = {
        "mlflow_run_id": run_id, "mlflow_experiment_id": run.info.experiment_id,
        "run_name": run.info.run_name, "mlflow_status": run.info.status,
        "started_at": datetime.fromtimestamp(run.info.start_time / 1000, timezone.utc).isoformat(timespec="seconds"),
        "training_time_s": round((run.info.end_time - run.info.start_time) / 1000, 1),
        "curves": {"training_success_rate": curve("training/success_rate"),
                   "training_reward": curve("training/reward")},
    }
    _write(cache, info)
    return info


# ------------------------------------------------------------------ seleccion
def _eligible(entry: dict, level_id: str, criteria: dict) -> str | None:
    """None si el run puede competir en el nivel; si no, el motivo."""
    rules = criteria["eligible"]
    if entry["status"] != rules["status"]:
        return f"estado {entry['status']}"
    if not str(entry.get("environment_version", "")).startswith(rules["environment_family"]):
        return f"ambiente incompatible {entry.get('environment_version')}"
    m = entry.get("metrics_by_level", {}).get(level_id)
    if m is None:
        return "sin evaluación en este nivel"
    if rules.get("full_suite") and m["partial"]:
        return "evaluación parcial"
    if m["latency_ms_p95"] > rules["max_latency_ms_p95"]:
        return f"latencia p95 {m['latency_ms_p95']} ms > {rules['max_latency_ms_p95']} ms"
    return None


def _rank_key(m: dict, criteria: dict):
    key = []
    for rule in criteria["tie_break"]:
        (metric, order), = rule.items()
        value = m.get(metric) or 0.0
        key.append(-value if order == "desc" else value)
    return tuple(key)


def select(entries: list[dict], current: dict, pins: dict, criteria: dict) -> tuple[dict, dict]:
    """Aplica los criterios por nivel. Devuelve (recomendados, decisiones con motivo)."""
    recommended, decisions = {}, {}
    by_id = {e["run_id"]: e for e in entries}
    for level_id in criteria["levels"]:
        notes = []
        candidates = []
        for entry in entries:
            if entry.get("status") == "baseline" and not criteria.get("recommend_baselines"):
                continue
            reason = _eligible(entry, level_id, criteria)
            if reason:
                notes.append({"run_id": entry["run_id"], "decision": "no elegible", "reason": reason})
            else:
                candidates.append(entry)
        candidates.sort(key=lambda e: _rank_key(e["metrics_by_level"][level_id], criteria))
        incumbent = current.get(level_id)
        if level_id in pins:
            recommended[level_id] = pins[level_id]["run_id"]
            notes.append({"run_id": pins[level_id]["run_id"], "decision": "fijado por rollback",
                          "reason": pins[level_id]["reason"]})
            decisions[level_id] = notes
            continue
        best = candidates[0] if candidates else None
        if best is None:
            recommended[level_id] = incumbent
            notes.append({"run_id": incumbent, "decision": "sin candidatos", "reason": "ningún run elegible"})
        elif incumbent is None or incumbent not in by_id or _eligible(by_id[incumbent], level_id, criteria):
            bm = best["metrics_by_level"][level_id]
            if bm["success_rate"] >= criteria["first_recommendation"]["min_success_rate"]:
                recommended[level_id] = best["run_id"]
                notes.append({"run_id": best["run_id"], "decision": "recomendado",
                              "reason": f"primer recomendado: éxito {bm['success_rate']:.0%} ≥ "
                                        f"{criteria['first_recommendation']['min_success_rate']:.0%}"})
            else:
                recommended[level_id] = None
                notes.append({"run_id": best["run_id"], "decision": "rechazado",
                              "reason": f"éxito {bm['success_rate']:.0%} < mínimo "
                                        f"{criteria['first_recommendation']['min_success_rate']:.0%}"})
        else:
            recommended[level_id] = incumbent
            im = by_id[incumbent]["metrics_by_level"][level_id]
            rules = criteria["replace_recommended"]
            for cand in candidates:
                if cand["run_id"] == incumbent:
                    continue
                cm = cand["metrics_by_level"][level_id]
                gain = cm["success_rate"] - im["success_rate"]
                extra_roll = cm["failures_by_cause"].get("volco", 0) - im["failures_by_cause"].get("volco", 0)
                extra_crack = cm["failures_by_cause"].get("grieta", 0) - im["failures_by_cause"].get("grieta", 0)
                if gain + 1e-9 < rules["min_improvement"]:
                    why = f"mejora {gain:+.0%} < +{rules['min_improvement']:.0%} sobre {incumbent[:8]}"
                elif extra_roll > rules["max_extra_rollovers"]:
                    why = f"{extra_roll} vuelcos más que {incumbent[:8]}"
                elif extra_crack > rules["max_extra_crack"]:
                    why = f"{extra_crack} caídas en la grieta más que {incumbent[:8]}"
                else:
                    recommended[level_id] = cand["run_id"]
                    notes.append({"run_id": cand["run_id"], "decision": "recomendado",
                                  "reason": f"reemplaza a {incumbent[:8]}: éxito {gain:+.0%}"})
                    break
                notes.append({"run_id": cand["run_id"], "decision": "rechazado", "reason": why})
            if recommended[level_id] == incumbent:
                notes.append({"run_id": incumbent, "decision": "se mantiene",
                              "reason": "ningún candidato cumple los criterios de reemplazo"})
        decisions[level_id] = notes
    return recommended, decisions


# ------------------------------------------------------------------ catalogo
def _read_config(paths: Paths, manifest: dict) -> dict:
    config_path = (manifest.get("origin") or {}).get("config_path")
    if config_path and (paths.root / config_path).exists():
        return yaml.safe_load((paths.root / config_path).read_text(encoding="utf-8")) or {}
    return {}


def run_entry(paths: Paths, manifest: dict) -> dict:
    config = _read_config(paths, manifest)
    training = training_info(paths, manifest["run_id"]) if manifest.get("status") != "failed" else {}
    by_level = level_metrics(paths, manifest["run_id"])
    trained_level = manifest["level_id"]
    repository = (manifest.get("origin") or {}).get("repository")
    return {
        "run_id": manifest["run_id"],
        "experiment_id": manifest["experiment_id"],
        "model_name": f"{manifest['algorithm'].upper()} · {manifest['experiment_id']} · semilla {manifest.get('seed')}",
        "algorithm": manifest["algorithm"],
        "level_id": trained_level,
        "status": manifest["status"],
        "diagnosis": manifest.get("diagnosis"),
        "hypothesis": config.get("hypothesis"),
        "change": config.get("change"),
        "reference": config.get("reference"),
        "seed": manifest.get("seed"),
        "budget_timesteps": manifest.get("budget_timesteps"),
        "effective_budget_timesteps": manifest.get("effective_budget_timesteps"),
        "training_time_s": training.get("training_time_s"),
        "parent_run_id": manifest.get("parent_run_id"),
        "environment_version": manifest.get("environment_version"),
        "environment_hash": manifest.get("environment_hash"),
        "git_commit": manifest.get("git_commit"),
        "commit_url": commit_url(repository, manifest.get("git_commit")),
        "config_path": (manifest.get("origin") or {}).get("config_path"),
        "config_sha256": manifest.get("config_sha256"),
        "model_uri": manifest.get("model_uri"),
        "model_sha256": manifest.get("model_sha256"),
        "normalization_uri": manifest.get("normalization_uri"),
        "mlflow_run_id": training.get("mlflow_run_id") or manifest["run_id"],
        "mlflow_run_name": training.get("run_name"),
        "evaluation_suite_id": manifest.get("evaluation_suite_id"),
        "metrics": {"success_rate": by_level.get(trained_level, {}).get("success_rate",
                                                                        (manifest.get("metrics") or {}).get("success_rate"))},
        "metrics_by_level": by_level,
        "curves": training.get("curves", {}),
    }


def baseline_entry(paths: Paths, run_id: str) -> dict:
    names = {"baseline-rule": ("rule", "Regla (referencia)", "Girar hacia el objetivo y esquivar con los rayos"),
             "baseline-random": ("random", "Aleatoria (referencia)", "Acción uniforme: cota inferior")}
    algorithm, name, hypothesis = names[run_id]
    return {"run_id": run_id, "experiment_id": "baseline", "model_name": name, "algorithm": algorithm,
            "level_id": "todos", "status": "baseline", "hypothesis": hypothesis, "change": "sin entrenamiento",
            "environment_version": ENVIRONMENT_VERSION, "metrics": {}, "metrics_by_level": level_metrics(paths, run_id),
            "curves": {}}


def build_catalog(paths: Paths) -> dict:
    criteria = load_selection(paths)
    previous = load_catalog(paths) or {}
    manifests = load_manifests(paths)
    runs = [run_entry(paths, m) for m in manifests.values()]
    runs.sort(key=lambda r: (r["experiment_id"], r.get("seed") or 0, r["run_id"]))
    baselines = [baseline_entry(paths, b) for b in BASELINES]
    pins = previous.get("pins", {})
    recommended, decisions = select([*runs, *baselines], previous.get("recommended_run_id") or {}, pins, criteria)
    return {
        "schema": "robot-expedition-catalog/1",
        "environment_version": ENVIRONMENT_VERSION,
        "environment_hashes": {level: environment_hash(level) for level in LEVELS},
        "selection_criteria": {"path": "configs/selection.yaml", "version": criteria["version"],
                               "fixed_at": criteria["fixed_at"], "sha256": criteria["sha256"]},
        "recommended_run_id": recommended,
        "pins": pins,
        "decisions": decisions,
        "runs": [*runs, *baselines],
    }


def publish(paths: Paths, catalog: dict, *, action: str, reason: str, who: str | None = None) -> dict:
    """Publica catalog/catalog.json. Mismo contenido = misma version; distinto = version nueva + historial."""
    previous = load_catalog(paths)
    content_sha = _sha({k: v for k, v in catalog.items() if k not in VOLATILE_KEYS})
    if previous and previous.get("content_sha256") == content_sha:
        return {"changed": False, "catalog_version": previous["catalog_version"], "content_sha256": content_sha}
    version = (previous or {}).get("catalog_version", 0) + 1
    entry = {
        "catalog_version": version, "action": action, "at": _now(), "actor": who or actor(paths.root),
        "git_commit": _git(paths.root, "rev-parse", "HEAD"), "reason": reason,
        "recommended_before": (previous or {}).get("recommended_run_id"),
        "recommended_after": catalog["recommended_run_id"], "content_sha256": content_sha,
    }
    published = {
        "catalog_version": version, "served_version": f"catalog-v{version}",
        "previous_version": (previous or {}).get("catalog_version"),
        "published_at": entry["at"], "published_by": entry["actor"], "git_commit": entry["git_commit"],
        "content_sha256": content_sha, **catalog,
    }
    _write(paths.catalog, published)
    paths.history.parent.mkdir(parents=True, exist_ok=True)
    with paths.history.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"changed": True, **entry}


def rollback(paths: Paths, level_id: str, to_run_id: str, reason: str, who: str | None = None) -> dict:
    """Restaura como recomendado de un nivel un run anterior identificado y lo fija (pin)."""
    current = load_catalog(paths)
    if current is None:
        raise FileNotFoundError("no hay catálogo publicado; corre primero `catalog.py build`")
    entry = next((r for r in current["runs"] if r["run_id"] == to_run_id), None)
    if entry is None:
        raise KeyError(f"el run {to_run_id} no está en el catálogo")
    problem = _eligible(entry, level_id, load_selection(paths))
    if problem:
        raise ValueError(f"no se puede servir {to_run_id} en {level_id}: {problem}")
    catalog = {k: v for k, v in current.items() if k not in VOLATILE_KEYS}
    before = (catalog.get("recommended_run_id") or {}).get(level_id)
    catalog["recommended_run_id"] = {**catalog["recommended_run_id"], level_id: to_run_id}
    catalog["pins"] = {**catalog.get("pins", {}), level_id: {"run_id": to_run_id, "reason": reason,
                                                             "from_run_id": before, "at": _now()}}
    catalog["decisions"] = {**catalog.get("decisions", {}), level_id: [
        {"run_id": to_run_id, "decision": "rollback", "reason": f"{reason} (antes: {before})"}]}
    return publish(paths, catalog, action="rollback", reason=f"{level_id}: {before} -> {to_run_id}. {reason}", who=who)


def unpin(paths: Paths, level_id: str, reason: str, who: str | None = None) -> dict:
    current = load_catalog(paths)
    catalog = {k: v for k, v in current.items() if k not in VOLATILE_KEYS}
    pins = dict(catalog.get("pins", {}))
    if pins.pop(level_id, None) is None:
        return {"changed": False, "catalog_version": current["catalog_version"]}
    catalog["pins"] = pins
    return publish(paths, catalog, action="unpin", reason=f"{level_id}: {reason}", who=who)


def history(paths: Paths) -> list[dict]:
    if not paths.history.exists():
        return []
    return [json.loads(line) for line in paths.history.read_text(encoding="utf-8").splitlines() if line.strip()]


# ------------------------------------------------------------------ CLI
def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Catálogo versionado de Robot Expedition")
    sub = parser.add_subparsers(dest="cmd", required=True)
    build = sub.add_parser("build", help="evalúa lo pendiente, aplica la selección y publica")
    build.add_argument("--skip-eval", action="store_true")
    build.add_argument("--force-eval", action="store_true")
    build.add_argument("--reason", default="publicación del pipeline")
    rb = sub.add_parser("rollback", help="restaura un run anterior como recomendado de un nivel")
    rb.add_argument("--level", choices=LEVELS, required=True)
    rb.add_argument("--to", required=True, help="run_id a servir")
    rb.add_argument("--reason", required=True)
    up = sub.add_parser("unpin", help="quita el pin de un rollback y vuelve a la selección automática")
    up.add_argument("--level", choices=LEVELS, required=True)
    up.add_argument("--reason", required=True)
    sub.add_parser("history", help="muestra el historial de publicaciones")
    args = parser.parse_args(argv)
    paths = Paths()

    if args.cmd == "build":
        if not args.skip_eval:
            evaluate_all(paths, force=args.force_eval)
        result = publish(paths, build_catalog(paths), action="publish", reason=args.reason)
    elif args.cmd == "rollback":
        result = rollback(paths, args.level, args.to, args.reason)
    elif args.cmd == "unpin":
        result = unpin(paths, args.level, args.reason)
    else:
        for entry in history(paths):
            print(f"v{entry['catalog_version']:<3} {entry['at']} {entry['action']:<8} {entry['actor']:<12} "
                  f"{entry['recommended_after']}  ·  {entry['reason']}")
        return
    print(json.dumps(result, indent=2, ensure_ascii=False))
    catalog = load_catalog(paths)
    print("recomendados:", catalog["recommended_run_id"], "· versión servida:", catalog["served_version"])


if __name__ == "__main__":
    main()
