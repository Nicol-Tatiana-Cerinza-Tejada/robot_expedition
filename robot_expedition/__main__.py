"""CLI de Robot Expedition: python -m robot_expedition <comando>.

Comandos: train, evaluate, demo, transitions, plot, serve.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

from .envs.beacon_expedition import ACTIONS, REFERENCE_ROUTE, BeaconExpeditionEnv
from .qlearning import QLearningAgent, discretize


def ascii_bar(value, width=20):
    size = max(0, min(width, int(round(value * width))))
    return "[" + "#" * size + "." * (width - size) + "]"


def make_env(args, perturbation=False):
    return BeaconExpeditionEnv(max_steps=args.max_steps, ray_noise=args.ray_noise,
                               rock_jitter=args.jitter, perturbation=perturbation)


def frame(env, action, reward, collision):
    return [round(env.x, 3), round(env.y, 3), round(env.theta, 3), env.stage,
            round(env.battery, 2), action, round(reward, 3), int(collision),
            [round(float(r), 2) for r in env.last_rays]]


def run_episode(env, agent, seed, train, record=False):
    obs, info = env.reset(seed=seed)
    state, total = discretize(obs), 0.0
    frames = [frame(env, -1, 0.0, False)] if record else None
    while True:
        action = agent.choose(state, explore=train)
        obs, reward, terminated, truncated, info = env.step(action)
        next_state = discretize(obs)
        if train:
            agent.update(state, action, reward, next_state, terminated)
        state, total = next_state, total + reward
        if record:
            frames.append(frame(env, action, reward, info["collision"]))
        if terminated or truncated:
            break
    result = {"reward": round(total, 3), "steps": env.steps, "success": info["success"],
              "visited": sum(info["visited"]), "end": info["end"],
              "battery": round(info["battery"], 2), "collisions": info["collisions"],
              "path_length": round(info["path_length"], 2)}
    if record:
        result["frames"] = frames
        result["rocks"] = [list(r) for r in env.rocks]
        result["block"] = env.perturbation
    return result


def load_replays(path, env):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"map": env.map_spec(), "episodes": []}


def save_json(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)  # escritura atomica: la pagina 3D nunca lee un archivo a medias


# ------------------------------------------------------------------ comandos
def train(args):
    env = make_env(args)
    agent = QLearningAgent(env.action_space.n, args.alpha, args.gamma, 1.0, args.seed)
    # epsilon baja de 1 a epsilon_min durante el 70 % de los episodios.
    decay = args.epsilon_min ** (1 / max(1, 0.7 * args.episodes))
    replays = {"map": env.map_spec(), "episodes": []}
    history = []
    print(f"Entrenando Q-learning: {args.episodes} episodios, tabla de "
          f"{agent.q.size} valores, acciones: {', '.join(a[0] for a in ACTIONS)}")
    start = time.time()
    for episode in range(1, args.episodes + 1):
        record = episode == 1 or episode % args.record_every == 0 or episode == args.episodes
        live = args.live_every and episode % args.live_every == 0
        result = run_episode(env, agent, args.seed * 100_000 + episode, True, record or live)
        row = {"episode": episode, **{k: v for k, v in result.items() if k not in ("frames", "rocks", "block")},
               "epsilon": round(agent.epsilon, 4), "states": agent.known_states}
        history.append(row)
        if record or live:
            entry = {"id": f"train-{episode}", "mode": "entrenamiento", "episode": episode,
                     "epsilon": row["epsilon"], **result}
            if record:
                replays["episodes"].append(entry)
            save_json(Path(args.logs) / "expedition_live.json",
                      {"total_episodes": args.episodes, "history_tail": history[-200:], **entry})
            if args.live_delay:
                time.sleep(args.live_delay)
        agent.epsilon = max(args.epsilon_min, agent.epsilon * decay)

        if episode % args.report_every == 0 or episode == args.episodes:
            recent = history[-args.report_every:]
            success = np.mean([r["success"] for r in recent])
            ends = Counter(r["end"] for r in recent)
            print(f"ep {episode:5d} | recompensa {np.mean([r['reward'] for r in recent]):7.1f} "
                  f"| exito {ascii_bar(success)} {success:4.0%} "
                  f"| balizas {np.mean([r['visited'] for r in recent]):.2f}/2 "
                  f"| pasos {np.mean([r['steps'] for r in recent]):5.1f} "
                  f"| eps {agent.epsilon:.3f} | estados {agent.known_states:4d} "
                  f"| fin {dict(ends.most_common(3))}")

    agent.save(args.model)
    save_json(Path(args.logs) / "expedition_replays.json", replays)
    with open(Path(args.logs) / "expedition_history.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(history[0].keys()))
        writer.writeheader(); writer.writerows(history)
    print(f"\nListo en {time.time() - start:.1f} s. Modelo: {args.model}")
    print(f"Historial: {args.logs}/expedition_history.csv · Repeticiones 3D: "
          f"{args.logs}/expedition_replays.json ({len(replays['episodes'])} episodios)")


def evaluate(args):
    env = make_env(args, perturbation=args.perturbation)
    agent = QLearningAgent(env.action_space.n).load(args.model)
    mode = "evaluación + bloqueo" if args.perturbation else "evaluación"
    results = []
    for i in range(args.episodes):
        results.append(run_episode(env, agent, 1_000_000 + args.seed * 1000 + i, False, i < args.record))
    ok = [r for r in results if r["success"]]
    print(f"\n{mode}: {args.episodes} episodios (semillas no usadas en entrenamiento)")
    print(f"  1. tasa de exito         {len(ok) / len(results):6.1%}")
    eff = np.mean([REFERENCE_ROUTE / r["path_length"] for r in ok]) if ok else float("nan")
    path = np.mean([r["path_length"] for r in ok]) if ok else float("nan")
    print(f"  2. eficiencia de ruta    {eff:6.2f}   (ruta de referencia {REFERENCE_ROUTE} m / recorrido de {path:.1f} m)")
    print(f"  3. choques por episodio  {np.mean([r['collisions'] for r in results]):6.2f}")
    print(f"  balizas visitadas        {np.mean([r['visited'] for r in results]):6.2f} / 2")
    print(f"  bateria final (exitos)   {np.mean([r['battery'] for r in ok]) if ok else float('nan'):6.1f} %")
    print(f"  pasos medios             {np.mean([r['steps'] for r in results]):6.1f}")
    print(f"  causa de fin             {dict(Counter(r['end'] for r in results))}")

    path = Path(args.logs) / "expedition_replays.json"
    replays = load_replays(path, env)
    replays["episodes"] = [e for e in replays["episodes"] if e["mode"] != mode]
    for i, r in enumerate(results[:args.record]):
        replays["episodes"].append({"id": f"{mode}-{i + 1}", "mode": mode, "episode": i + 1,
                                    "epsilon": 0.0, **r})
    save_json(path, replays)
    print(f"  {min(args.record, len(results))} episodios guardados para verlos en 3D")


def demo(args):
    env = make_env(args, perturbation=args.perturbation)
    agent = QLearningAgent(env.action_space.n)
    if Path(args.model).exists():
        agent.load(args.model)
    else:
        print(f"No existe {args.model}; el robot actuara al azar. Ejecuta primero 'train'.")
        agent.epsilon = 1.0
    obs, info = env.reset(seed=args.seed)
    state, total = discretize(obs), 0.0
    while True:
        action = agent.choose(state, explore=not Path(args.model).exists())
        obs, reward, terminated, truncated, info = env.step(action)
        state, total = discretize(obs), total + reward
        sys.stdout.write("\033[H\033[J" if args.fps > 0 else "\n")
        print(env.render())
        print(f"paso {env.steps:3d} | accion {ACTIONS[action][0]:14s} | recompensa {reward:+7.2f} "
              f"| total {total:7.1f}\netapa {('B1', 'B2', 'base')[env.stage - 1]:4s} | bateria "
              f"{ascii_bar(info['battery'] / 100)} {info['battery']:5.1f}% | choques {info['collisions']}"
              + (f" | {info['event']}" if info["event"] else ""))
        if terminated or truncated:
            print(f"\nFin: {info['end']}  (exito: {info['success']})")
            return
        if args.fps > 0:
            time.sleep(1 / args.fps)


def transitions(args):
    """Imprime transiciones reales en formato de tabla Markdown para la ficha."""
    env = make_env(args, perturbation=args.perturbation)
    agent = QLearningAgent(env.action_space.n).load(args.model)
    obs, _ = env.reset(seed=args.seed)
    rows, prev = [], obs
    while True:
        state = discretize(prev)
        action = agent.choose(state, explore=False)
        before = (env.steps, env.x, env.y, env.stage, env.battery, prev)
        obs, reward, terminated, truncated, info = env.step(action)
        rows.append((before, action, info, reward, terminated, truncated))
        prev = obs
        if terminated or truncated:
            break
    picks = {0}
    picks |= {i for i, r in enumerate(rows) if r[2]["event"]}
    first_hit = next((i for i, r in enumerate(rows) if r[2]["collision"]), None)
    if first_hit is not None:
        picks.add(first_hit)  # solo el primer choque, para no llenar la tabla
    picks.add(len(rows) - 1)
    print("| t | Observación (resumen) | Acción | Nuevo estado | Recompensa | ¿Fin? |")
    print("|---|---|---|---|---|---|")
    for i in sorted(picks):
        (t, x, y, stage, battery, o), action, info, reward, term, trunc = rows[i]
        rel = math.degrees(math.atan2(o[10], o[11]))
        obs_txt = (f"etapa {('B1', 'B2', 'base')[stage - 1]}; objetivo a {o[9]:.2f} m y {rel:+.0f}°; "
                   f"rayo frontal {o[4]:.2f} m; batería {battery:.1f} %")
        new_txt = (f"({info['x']:.2f}, {info['y']:.2f}); etapa {('B1', 'B2', 'base')[info['stage'] - 1]}; "
                   f"batería {info['battery']:.1f} %" + (f"; **{info['event']}**" if info["event"] else "")
                   + ("; choque" if info["collision"] else ""))
        end = f"Sí ({info['end']})" if term or trunc else "No"
        print(f"| {t} | {obs_txt} | {ACTIONS[action][0]} | {new_txt} | {reward:+.3f} | {end} |")


def plot(args):
    import matplotlib.pyplot as plt
    with open(Path(args.logs) / "expedition_history.csv") as f:
        rows = list(csv.DictReader(f))
    ep = np.array([int(r["episode"]) for r in rows])
    reward = np.array([float(r["reward"]) for r in rows])
    success = np.array([r["success"] == "True" for r in rows], dtype=float)
    w = max(1, min(50, len(rows) // 10))
    smooth = lambda v: np.convolve(v, np.ones(w) / w, mode="valid")
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(ep, reward, alpha=.25, label="episodio")
    axes[0].plot(ep[w - 1:], smooth(reward), label=f"media móvil {w}")
    axes[0].set_ylabel("recompensa"); axes[0].legend(); axes[0].grid(alpha=.2)
    axes[1].plot(ep[w - 1:], smooth(success), label="tasa de éxito")
    axes[1].plot(ep, [float(r["epsilon"]) for r in rows], label="epsilon", alpha=.7)
    axes[1].set(xlabel="episodio", ylim=(0, 1.05)); axes[1].legend(); axes[1].grid(alpha=.2)
    fig.tight_layout(); out = Path(args.logs) / "expedition_learning.png"; fig.savefig(out, dpi=140)
    print(f"Gráfica guardada en {out}")


def serve(args):
    import functools
    import http.server
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(Path.cwd()))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"Vista 3D en http://localhost:{args.port}/expedicion_3d.html  (Ctrl+C para salir)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m robot_expedition",
                                     description="Robot Expedition: Q-learning visible en terminal y en 3D")
    sub = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--seed", type=int, default=7)
    common.add_argument("--max-steps", type=int, default=400)
    common.add_argument("--ray-noise", type=float, default=0.02, help="desv. estándar de los rayos (m)")
    common.add_argument("--jitter", type=float, default=0.0, help="movimiento aleatorio de rocas (m)")
    common.add_argument("--model", default="models/qlearning_balizas.npz")
    common.add_argument("--logs", default="logs")

    p = sub.add_parser("train", parents=[common], help="entrena el agente Q-learning")
    p.add_argument("--episodes", type=int, default=2000)
    p.add_argument("--alpha", type=float, default=0.2)
    p.add_argument("--gamma", type=float, default=0.98)
    p.add_argument("--epsilon-min", type=float, default=0.05)
    p.add_argument("--report-every", type=int, default=100)
    p.add_argument("--record-every", type=int, default=50, help="guarda la trayectoria cada N episodios")
    p.add_argument("--live-every", type=int, default=5, help="actualiza la vista en vivo cada N episodios")
    p.add_argument("--live-delay", type=float, default=0.0, help="pausa (s) tras cada actualización en vivo")
    p.set_defaults(func=train)

    p = sub.add_parser("evaluate", parents=[common], help="mide las 3 métricas de la ficha")
    p.add_argument("--episodes", type=int, default=50)
    p.add_argument("--perturbation", action="store_true", help="activa el corredor bloqueado")
    p.add_argument("--record", type=int, default=5, help="episodios a guardar para la vista 3D")
    p.set_defaults(func=evaluate)

    p = sub.add_parser("demo", parents=[common], help="un episodio animado en la terminal")
    p.add_argument("--fps", type=float, default=8)
    p.add_argument("--perturbation", action="store_true")
    p.set_defaults(func=demo)

    p = sub.add_parser("transitions", parents=[common], help="transiciones reales para la ficha")
    p.add_argument("--perturbation", action="store_true")
    p.set_defaults(func=transitions)

    p = sub.add_parser("plot", parents=[common], help="gráfica de aprendizaje (PNG)")
    p.set_defaults(func=plot)

    p = sub.add_parser("serve", help="sirve la vista 3D en localhost")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=serve)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
