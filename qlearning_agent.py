"""Q-learning tabular para RobotExpeditionEnv.

El entorno fisico es continuo. Para hacer visible el aprendizaje, este agente
discretiza una pequena parte de la observacion y usa acciones motoras
predefinidas (incluido un control de estabilizacion sencillo).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from robot_expedition import RobotExpeditionEnv


class QLearningAgent:
    """Q-learning epsilon-greedy con estados discretizados."""

    # Acciones: reposo, avance suave/fuerte, correcciones laterales y balanceo.
    ACTIONS = np.array([
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, .45, -.35, -.15, 0, 0, .45, -.35, -.15, 0],
        [0, .85, -.65, -.25, 0, 0, .85, -.65, -.25, 0],
        [.35, .35, -.25, 0, -.15, -.35, .35, -.25, 0, .15],
        [-.35, .35, -.25, 0, .15, .35, .35, -.25, 0, -.15],
        [.45, 0, 0, .25, -.2, -.45, 0, 0, .25, .2],
        [-.45, 0, 0, -.25, .2, .45, 0, 0, -.25, -.2],
        [0, -.35, .3, .2, 0, 0, -.35, .3, .2, 0],
    ], dtype=np.float32)

    def __init__(self, alpha=.15, gamma=.98, epsilon=.25, seed=0):
        self.alpha, self.gamma, self.epsilon = alpha, gamma, epsilon
        self.rng = np.random.default_rng(seed)
        self.q = {}

    @staticmethod
    def state(obs):
        # qpos: x=0,z=2; qvel: x velocity=7; sensor starts at 33;
        # lidar starts at 41; final entries are battery and mission signal.
        values = [obs[0], obs[2], obs[7], obs[33], obs[41], obs[59], obs[60]]
        bins = ([0, 1, 3, 6, 10, 15], [0.85, 1.15, 1.7, 2.5],
                [-1, -.2, .2, 1, 3], [-.8, -.2, .2, .6, 1],
                [1, 3, 6, 10], [.15, .4, .7, .9], [0, .25, .6, .9, 1.1])
        return tuple(int(np.digitize(v, b)) for v, b in zip(values, bins))

    def values(self, state):
        return self.q.setdefault(state, np.zeros(len(self.ACTIONS), dtype=np.float32))

    def choose(self, state, explore=True):
        values = self.values(state)
        if explore and self.rng.random() < self.epsilon:
            return int(self.rng.integers(len(self.ACTIONS)))
        return int(np.argmax(values))

    def update(self, state, action, reward, next_state, done):
        current = self.values(state)
        target = reward if done else reward + self.gamma * np.max(self.values(next_state))
        current[action] += self.alpha * (target - current[action])

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, states=np.array(list(self.q.keys()), dtype=np.int16),
                            values=np.array(list(self.q.values()), dtype=np.float32),
                            epsilon=self.epsilon)

    def load(self, path):
        data = np.load(path, allow_pickle=False)
        self.q = {tuple(row): values.copy() for row, values in zip(data["states"], data["values"])}
        self.epsilon = float(data["epsilon"])


def run_episode(env, agent, seed, train=True):
    obs, _ = env.reset(seed=seed)
    state, total, steps, info = agent.state(obs), 0.0, 0, {}
    while True:
        action = agent.choose(state, explore=train)
        next_obs, reward, terminated, truncated, info = env.step(agent.ACTIONS[action])
        next_state = agent.state(next_obs)
        if train:
            agent.update(state, action, reward, next_state, terminated or truncated)
        total += reward; steps += 1; state = next_state
        if terminated or truncated:
            return total, steps, bool(info.get("success", False)), float(info.get("mission_progress", 0))


def ascii_bar(value, width=24, scale=10.0):
    """Barra compacta para seguir el aprendizaje directamente en terminal."""
    size = max(0, min(width, int(abs(value) / scale * width)))
    mark = "#" * size + "." * (width - size)
    return ("-" if value < 0 else "+") + "[" + mark + "]"


def train(args):
    env = RobotExpeditionEnv(max_steps=args.max_steps, mission_distance=args.distance)
    agent = QLearningAgent(args.alpha, args.gamma, args.epsilon, args.seed)
    rows = []
    for episode in range(1, args.episodes + 1):
        result = run_episode(env, agent, args.seed + episode, train=True)
        rows.append((episode, *result, agent.epsilon, len(agent.q)))
        agent.epsilon = max(args.epsilon_min, agent.epsilon * args.epsilon_decay)
        live_path = Path(args.live); live_path.parent.mkdir(parents=True, exist_ok=True)
        live_path.write_text(json.dumps({
            "episode": episode, "total_episodes": args.episodes,
            "reward": result[0], "steps": result[1], "success": result[2],
            "progress": result[3], "epsilon": agent.epsilon,
            "states": len(agent.q), "status": "META" if result[2] else ("avanza" if result[3] > 0.02 else "cae/repite")
        }), encoding="utf-8")
        if episode == 1 or episode % args.report_every == 0 or episode == args.episodes:
            recent = rows[-args.report_every:]
            avg_reward = np.mean([r[1] for r in recent]); avg_progress = np.mean([r[4] for r in recent])
            success_count = sum(r[3] for r in recent)
            status = "META" if success_count else ("avanza" if avg_progress > 0.02 else "cae/repite")
            print(f"episodio {episode:4d} | recompensa media {avg_reward:8.2f} "
                  f"| progreso medio {np.mean([r[4] for r in recent]):.2f} "
                  f"| exitos {success_count}/{len(recent)} "
                  f"| estados Q {len(agent.q)} | epsilon {agent.epsilon:.3f} | {status}\n"
                  f"             recompensa {ascii_bar(avg_reward)} progreso {ascii_bar(avg_progress, scale=1)}")
    env.close(); agent.save(args.model)
    history_path = Path(args.history); history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w", newline="") as file:
        writer = csv.writer(file); writer.writerow(["episode", "reward", "steps", "success", "progress", "epsilon", "states"]); writer.writerows(rows)
    print(f"modelo guardado en {args.model}; historial en {args.history}")


def evaluate(args):
    env = RobotExpeditionEnv(render_mode="human" if args.render else None, max_steps=args.max_steps, mission_distance=args.distance)
    agent = QLearningAgent(); agent.load(args.model); results = [run_episode(env, agent, args.seed + i, train=False) for i in range(args.episodes)]
    env.close(); print(f"evaluacion: recompensa media {np.mean([r[0] for r in results]):.2f}, progreso medio {np.mean([r[3] for r in results]):.2f}, exitos {sum(r[2] for r in results)}/{len(results)}")


def plot(args):
    import matplotlib.pyplot as plt
    data = np.genfromtxt(args.history, delimiter=",", names=True)
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(data["episode"], data["reward"], alpha=.25, label="episodio")
    window = min(25, len(data)); rolling = np.convolve(data["reward"], np.ones(window)/window, mode="valid")
    axes[0].plot(data["episode"][window - 1:], rolling, label=f"media {window}")
    axes[0].set_ylabel("recompensa"); axes[0].legend(); axes[0].grid(alpha=.2)
    axes[1].plot(data["episode"], data["progress"], label="progreso")
    axes[1].plot(data["episode"], data["success"], label="exito (0/1)", alpha=.7)
    axes[1].set(xlabel="episodio", ylabel="avance / exito"); axes[1].legend(); axes[1].grid(alpha=.2)
    fig.tight_layout(); fig.savefig(args.output, dpi=140); print(f"grafica guardada en {args.output}")


def main():
    parser = argparse.ArgumentParser(description="Q-learning visible para el robot de Marte")
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--episodes", type=int, default=1000); common.add_argument("--max-steps", type=int, default=500)
    common.add_argument("--distance", type=float, default=15.0); common.add_argument("--seed", type=int, default=7)
    common.add_argument("--model", default="models/qlearning_robot.npz")
    p = sub.add_parser("train", parents=[common]); p.add_argument("--alpha", type=float, default=.15); p.add_argument("--gamma", type=float, default=.98); p.add_argument("--epsilon", type=float, default=.25); p.add_argument("--epsilon-min", type=float, default=.03); p.add_argument("--epsilon-decay", type=float, default=.97); p.add_argument("--report-every", type=int, default=10); p.add_argument("--history", default="logs/qlearning_history.csv"); p.add_argument("--live", default="logs/qlearning_live.json"); p.set_defaults(func=train)
    p = sub.add_parser("evaluate", parents=[common]); p.add_argument("--render", action="store_true"); p.set_defaults(func=evaluate)
    p = sub.add_parser("plot"); p.add_argument("--history", default="logs/qlearning_history.csv"); p.add_argument("--output", default="logs/qlearning_learning.png"); p.set_defaults(func=plot)
    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()
