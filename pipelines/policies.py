"""Politicas evaluables con la interfaz comun policy(obs) -> accion.

- RandomPolicy: referencia aleatoria (semilla por caso, reproducible).
- RulePolicy: referencia de regla (gira hacia el objetivo y esquiva).
- QTablePolicy: adaptador del Q-learning tabular (archivo .npz).
- PPOPolicy: adaptador de Stable-Baselines3 PPO (+ VecNormalize opcional).

Indices de la observacion (docs/contratos.md): 0-8 rayos de -90 a +90 grados
(derecha a izquierda), 9 distancia al objetivo, 10-11 sen/cos del angulo
relativo, 12 v, 13 w, 14 bateria, 15-17 etapa, 18-19 cabeceo y alabeo.
Acciones: 0 avanzar, 1 avanzar+izq, 2 avanzar+der, 3 girar izq, 4 girar der.
"""

from __future__ import annotations

import hashlib
import math
import pickle
from pathlib import Path

import numpy as np

FORWARD, FORWARD_LEFT, FORWARD_RIGHT, TURN_LEFT, TURN_RIGHT = range(5)


def sha256_file(path: Path | None) -> str | None:
    if path is None:
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class RandomPolicy:
    """Accion uniforme; reset(seed) la hace reproducible por caso."""

    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = np.random.default_rng(seed)

    def reset(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    def __call__(self, obs) -> int:
        return int(self.rng.integers(5))

    def describe(self) -> dict:
        return {"policy": self.name, "kind": "referencia aleatoria"}


class RulePolicy:
    """Regla fija: si el frente esta bloqueado, gira hacia el lado con mas
    espacio; si un costado esta muy cerca, se aparta; si no, apunta al
    objetivo. No aprende ni usa la posicion absoluta."""

    name = "rule"

    def __init__(self, front_clearance: float = 0.8, side_clearance: float = 0.6,
                 aligned: float = 0.35, sharp: float = 1.2):
        self.front_clearance, self.side_clearance = front_clearance, side_clearance
        self.aligned, self.sharp = aligned, sharp

    def __call__(self, obs) -> int:
        rays = np.asarray(obs[:9])
        angle = math.atan2(float(obs[10]), float(obs[11]))      # + = objetivo a la izquierda
        if rays[3:6].min() < self.front_clearance:
            return TURN_LEFT if rays[6:9].min() > rays[0:3].min() else TURN_RIGHT
        # Sin esta separacion lateral la regla raspa las rocas (72 choques/ep. en N1).
        if rays[0:3].min() < self.side_clearance:
            return FORWARD_LEFT
        if rays[6:9].min() < self.side_clearance:
            return FORWARD_RIGHT
        if abs(angle) < self.aligned:
            return FORWARD
        if angle > 0:
            return TURN_LEFT if angle > self.sharp else FORWARD_LEFT
        return TURN_RIGHT if -angle > self.sharp else FORWARD_RIGHT

    def describe(self) -> dict:
        return {"policy": self.name, "kind": "referencia de regla",
                "params": {"front_clearance_m": self.front_clearance, "side_clearance_m": self.side_clearance,
                           "aligned_rad": self.aligned, "sharp_rad": self.sharp}}


class QTablePolicy:
    """Q-learning tabular congelado: argmax de la tabla (primer maximo)."""

    name = "qlearning"

    def __init__(self, model_path: str | Path):
        from robot_expedition.qlearning import discretize
        self.model_path = Path(model_path)
        self._discretize = discretize
        self.q = np.load(self.model_path)["q"]

    def __call__(self, obs) -> int:
        return int(np.argmax(self.q[self._discretize(obs)]))

    def describe(self) -> dict:
        return {"policy": self.name, "kind": "modelo aprendido", "model_path": str(self.model_path),
                "model_sha256": sha256_file(self.model_path),
                "discretization": "etapa x distancia x angulo x 3 sectores de rayos (2592 estados)"}


class PPOPolicy:
    """PPO de Stable-Baselines3 en modo determinista. Si hay VecNormalize,
    aplica exactamente la misma normalizacion de observaciones del entrenamiento."""

    name = "ppo"

    def __init__(self, model_path: str | Path, vecnormalize_path: str | Path | None = None):
        from stable_baselines3 import PPO
        self.model_path = Path(model_path)
        self.vecnormalize_path = Path(vecnormalize_path) if vecnormalize_path else None
        self.model = PPO.load(self.model_path, device="cpu")
        self.normalizer = None
        if self.vecnormalize_path:
            with open(self.vecnormalize_path, "rb") as fh:          # artefacto propio del equipo
                self.normalizer = pickle.load(fh)

    def __call__(self, obs) -> int:
        obs = np.asarray(obs, dtype=np.float32)
        if self.normalizer is not None and self.normalizer.norm_obs:
            obs = self.normalizer.normalize_obs(obs)
        action, _ = self.model.predict(obs, deterministic=True)
        return int(action)

    def describe(self) -> dict:
        return {"policy": self.name, "kind": "modelo aprendido", "model_path": str(self.model_path),
                "model_sha256": sha256_file(self.model_path),
                "vecnormalize_path": str(self.vecnormalize_path) if self.vecnormalize_path else None,
                "vecnormalize_sha256": sha256_file(self.vecnormalize_path)}


def make_policy(name: str, model: str | None = None, vecnormalize: str | None = None):
    if name == "random":
        return RandomPolicy()
    if name == "rule":
        return RulePolicy()
    if name in ("qlearning", "qtable"):
        if not model:
            raise ValueError("--model es obligatorio para qlearning (.npz)")
        return QTablePolicy(model)
    if name == "ppo":
        if not model:
            raise ValueError("--model es obligatorio para ppo (.zip)")
        return PPOPolicy(model, vecnormalize)
    raise ValueError(f"politica desconocida: {name}")
