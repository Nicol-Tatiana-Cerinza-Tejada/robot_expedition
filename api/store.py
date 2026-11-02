"""Catalogo de runs y carga verificada de modelos para la API.

Un run puede ser:
- un modelo entrenado, descrito por manifests/<run_id>.json (paso 3); sus pesos
  estan en models/<run_id>/ o se recuperan con `dvc pull` (API_DVC_PULL=1);
- un baseline sin pesos: baseline-random o baseline-rule (paso 2).

Antes de usar un modelo se comprueba su SHA-256 contra el manifiesto.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pipelines.policies import PPOPolicy, QTablePolicy, RandomPolicy, RulePolicy, sha256_file
from robot_expedition.envs.beacon_expedition import ENVIRONMENT_VERSION

LEVELS = ("n1", "n2", "n3")
BASELINES = {
    "baseline-random": {"algorithm": "random", "model_name": "Aleatoria (referencia)",
                        "hypothesis": "Referencia aleatoria: cota inferior del éxito"},
    "baseline-rule": {"algorithm": "rule", "model_name": "Regla (referencia)",
                      "hypothesis": "Referencia de regla: girar hacia el objetivo y esquivar"},
}


class RunNotFound(LookupError):
    pass


class ModelUnavailable(RuntimeError):
    """Los pesos no estan disponibles (ni locales ni en DVC)."""


class ModelIntegrityError(RuntimeError):
    """El SHA-256 de los pesos no coincide con el manifiesto."""


@dataclass
class Store:
    root: Path
    _policies: dict = field(default_factory=dict)

    @property
    def manifests_dir(self) -> Path:
        return self.root / "manifests"

    @property
    def models_dir(self) -> Path:
        return self.root / "models"

    @property
    def catalog_path(self) -> Path:
        return self.root / "catalog" / "catalog.json"

    # ------------------------------------------------------------ catalogo
    def manifests(self) -> dict[str, dict]:
        """Manifiestos de modelos candidatos (manifests/smoke no se publica)."""
        out = {}
        for path in sorted(self.manifests_dir.glob("*.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            out[manifest["run_id"]] = manifest
        return out

    def catalog(self) -> dict:
        """catalog/catalog.json si el pipeline lo publico; si no, se arma desde los manifiestos."""
        baselines = [{"run_id": run_id, "level_id": "todos", "status": "baseline",
                      "environment_version": ENVIRONMENT_VERSION, **info}
                     for run_id, info in BASELINES.items()]
        if self.catalog_path.exists():
            catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            known = {run["run_id"] for run in catalog.get("runs", [])}
            catalog["runs"] = [*catalog.get("runs", []), *(b for b in baselines if b["run_id"] not in known)]
            catalog.setdefault("source", "catalog/catalog.json")
            return catalog
        runs = []
        for manifest in self.manifests().values():
            runs.append({key: manifest.get(key) for key in (
                "run_id", "experiment_id", "level_id", "algorithm", "status", "environment_version",
                "git_commit", "seed", "budget_timesteps", "effective_budget_timesteps",
                "parent_run_id", "model_sha256", "evaluation_suite_id", "metrics", "diagnosis")}
                | {"model_name": f"{manifest.get('algorithm')} · {manifest.get('experiment_id')}"})
        return {"runs": [*runs, *baselines], "recommended_run_id": {}, "served_version": None,
                "source": "manifests (sin catálogo publicado)"}

    def run(self, run_id: str) -> dict:
        if run_id in BASELINES:
            return {"run_id": run_id, "status": "baseline", "environment_version": ENVIRONMENT_VERSION,
                    "level_id": "todos", **BASELINES[run_id]}
        manifest = self.manifests().get(run_id)
        if manifest is None:
            raise RunNotFound(run_id)
        return manifest

    # ------------------------------------------------------------- modelos
    def _model_files(self, manifest: dict) -> tuple[Path, Path | None]:
        model_dir = self.models_dir / manifest["run_id"]
        if manifest["algorithm"] == "qlearning":
            return model_dir / "qlearning.npz", None
        return model_dir / "ppo_model.zip", model_dir / "vecnormalize.pkl"

    def _dvc_pull(self, run_id: str) -> str | None:
        dvc_file = self.models_dir / f"{run_id}.dvc"
        if os.environ.get("API_DVC_PULL") != "1" or not dvc_file.exists() or not shutil.which("dvc"):
            return None
        result = subprocess.run(["dvc", "pull", str(dvc_file.relative_to(self.root))], cwd=self.root,
                                capture_output=True, text=True, timeout=300)
        return None if result.returncode == 0 else (result.stderr or result.stdout).strip()[-300:]

    def policy(self, run_id: str):
        """Politica lista para actuar; los modelos se verifican y se guardan en memoria."""
        if run_id == "baseline-random":
            return RandomPolicy()
        if run_id == "baseline-rule":
            return RulePolicy()
        manifest = self.run(run_id)
        if manifest.get("status") != "completed" or not manifest.get("model_sha256"):
            raise ModelUnavailable(f"el run {run_id} tiene estado {manifest.get('status')} y no tiene "
                                   f"checkpoint disponible ({manifest.get('diagnosis') or 'sin diagnóstico'})")
        cached = self._policies.get(run_id)
        if cached is not None:
            return cached
        weights, normalization = self._model_files(manifest)
        if not weights.exists():
            error = self._dvc_pull(run_id)
            if not weights.exists():
                raise ModelUnavailable(f"los pesos de {run_id} no están en models/{run_id}/ y no se pudieron "
                                       f"recuperar con DVC" + (f": {error}" if error else
                                       " (define API_DVC_PULL=1 y las credenciales del remoto)"))
        actual = sha256_file(weights)
        if actual != manifest["model_sha256"]:
            raise ModelIntegrityError(f"SHA-256 de {weights.name} = {actual[:12]}…, el manifiesto dice "
                                      f"{manifest['model_sha256'][:12]}…: el modelo no es el registrado")
        if manifest["algorithm"] == "qlearning":
            policy = QTablePolicy(weights)
        else:
            policy = PPOPolicy(weights, normalization if normalization and normalization.exists() else None)
        self._policies[run_id] = policy
        return policy
