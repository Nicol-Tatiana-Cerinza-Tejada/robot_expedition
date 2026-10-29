"""Q-learning tabular para BeaconExpeditionEnv.

El estado discreto se arma solo con lo que observa el agente (no usa x, y):
etapa, distancia y angulo al objetivo, y que tan cerca hay obstaculos a la
derecha, al frente y a la izquierda segun los 9 rayos.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np


DIST_BINS = [1.0, 2.5, 5.0]          # m
ANGLE_SECTORS = 8                     # sectores de 45 grados
FRONT_BINS = [0.6, 1.2]               # m
SIDE_BINS = [0.5, 1.0]                # m


def discretize(obs):
    rays = obs[:9]
    dist, sin_rel, cos_rel = obs[9], obs[10], obs[11]
    stage = int(np.argmax(obs[15:18]))
    angle = math.atan2(sin_rel, cos_rel)
    sector = int(((angle + math.pi / ANGLE_SECTORS) % (2 * math.pi)) // (2 * math.pi / ANGLE_SECTORS))
    right, front, left = rays[0:3].min(), rays[3:6].min(), rays[6:9].min()
    return (stage, int(np.digitize(dist, DIST_BINS)), sector,
            int(np.digitize(right, SIDE_BINS)), int(np.digitize(front, FRONT_BINS)),
            int(np.digitize(left, SIDE_BINS)))


STATE_SHAPE = (3, len(DIST_BINS) + 1, ANGLE_SECTORS, len(SIDE_BINS) + 1,
               len(FRONT_BINS) + 1, len(SIDE_BINS) + 1)


class QLearningAgent:
    """Q-learning epsilon-greedy con tabla densa."""

    def __init__(self, n_actions, alpha=0.2, gamma=0.98, epsilon=1.0, seed=0):
        self.alpha, self.gamma, self.epsilon = alpha, gamma, epsilon
        self.rng = np.random.default_rng(seed)
        self.q = np.zeros((*STATE_SHAPE, n_actions), dtype=np.float32)
        self.visits = np.zeros(STATE_SHAPE, dtype=np.int32)

    def choose(self, state, explore=True):
        if explore and self.rng.random() < self.epsilon:
            return int(self.rng.integers(self.q.shape[-1]))
        values = self.q[state]
        # Desempate al azar para no sesgar hacia la accion 0.
        return int(self.rng.choice(np.flatnonzero(values == values.max())))

    def update(self, state, action, reward, next_state, terminated):
        target = reward if terminated else reward + self.gamma * self.q[next_state].max()
        self.q[state][action] += self.alpha * (target - self.q[state][action])
        self.visits[state] += 1

    @property
    def known_states(self):
        return int(np.count_nonzero(self.visits))

    def save(self, path):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, q=self.q, visits=self.visits, epsilon=self.epsilon)

    def load(self, path):
        data = np.load(path)
        self.q, self.visits, self.epsilon = data["q"], data["visits"], float(data["epsilon"])
        return self
