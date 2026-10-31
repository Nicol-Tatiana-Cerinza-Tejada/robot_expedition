"""Q-learning sencillo y observable: un cuadrado aprende una ruta 2D."""
from pathlib import Path
import json
import numpy as np

W, H = 12, 8
START, GOAL = (1, 6), (10, 1)
WALLS = {(4, y) for y in range(1, 6)} | {(7, y) for y in range(2, 7)}
MOVES = [(0, -1), (0, 1), (-1, 0), (1, 0)]

def run(episodes=10000, seed=7):
    rng = np.random.default_rng(seed); q = np.zeros((W, H, 4), dtype=np.float32); live = Path("logs/qlearning_live.json"); live.parent.mkdir(exist_ok=True)
    alpha, gamma, epsilon = .2, .95, 1.0; history=[]
    for ep in range(1, episodes + 1):
        pos = START; total = 0.; success = False; path = [pos]
        for step in range(250):
            x, y = pos
            action = int(rng.integers(4)) if rng.random() < epsilon else int(np.argmax(q[x, y]))
            nx, ny = x + MOVES[action][0], y + MOVES[action][1]
            valid = 0 <= nx < W and 0 <= ny < H and (nx, ny) not in WALLS
            nxt = (nx, ny) if valid else pos
            reward = 100. if nxt == GOAL else (-2. if not valid else -0.1)
            q[x, y, action] += alpha * (reward + (0 if nxt == GOAL else gamma * np.max(q[nxt[0], nxt[1]])) - q[x, y, action])
            pos = nxt; path.append(pos); total += reward
            if pos == GOAL: success = True; break
        epsilon = max(.03, epsilon * .9993)
        row = {"episode": ep, "total_episodes": episodes, "reward": total, "steps": step + 1, "success": success, "progress": 1.0 if success else 1 - (abs(pos[0]-GOAL[0])+abs(pos[1]-GOAL[1])) / 18, "epsilon": epsilon, "states": int(np.count_nonzero(np.any(q, axis=2))), "status": "META" if success else "buscando ruta", "x": pos[0], "y": pos[1], "goal_x": GOAL[0], "goal_y": GOAL[1], "path": path}
        live.write_text(json.dumps(row), encoding="utf-8"); history.append(row)
        if ep == 1 or ep % 1000 == 0: print(f"epoca {ep:5d}/{episodes} | premio {total:7.2f} | pasos {step+1:3d} | meta {success} | epsilon {epsilon:.3f}")
    Path("logs/grid_qlearning_history.json").write_text(json.dumps(history), encoding="utf-8"); Path("models").mkdir(exist_ok=True); np.savez_compressed("models/grid_qlearning.npz", q=q); print("modelo guardado en models/grid_qlearning.npz")

if __name__ == "__main__": run()
