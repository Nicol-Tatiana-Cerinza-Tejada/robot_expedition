"""Pruebas de las reglas de la ficha docs/ambiente-v0.1.md (fisica 3D en MuJoCo)."""

import json
import math

import numpy as np
import pytest

from robot_expedition import BeaconExpeditionEnv
from robot_expedition.__main__ import main
from robot_expedition.envs.beacon_expedition import BEACONS, BLOCK, CRACK
from robot_expedition.qlearning import STATE_SHAPE, QLearningAgent, discretize

FORWARD, TURN_LEFT = 0, 3


def place(env, x, y, theta=0.0):
    env.set_pose(x, y, theta, speed=0.6)


@pytest.fixture
def env():
    e = BeaconExpeditionEnv(ray_noise=0.0)
    e.reset(seed=0)
    return e


def test_reset_observation(env):
    obs, info = env.reset(seed=3)
    assert obs.shape == (20,) and env.observation_space.contains(obs)
    assert info["stage"] == 1 and info["battery"] == 100.0
    assert all(0 <= s < n for s, n in zip(discretize(obs), STATE_SHAPE))


def test_qlearning_checkpoint_preserves_step_count_and_rng(tmp_path):
    state = (0, 0, 0, 0, 0, 0)
    agent = QLearningAgent(5, seed=13)
    agent.update(state, 0, 1.0, state, False)
    checkpoint = tmp_path / "checkpoint.npz"
    agent.save(checkpoint)
    expected_action = agent.choose(state, explore=True)

    resumed = QLearningAgent(5, seed=99).load(checkpoint)
    assert resumed.steps == 1
    assert resumed.choose(state, explore=True) == expected_action


def test_qlearning_deterministic_action_uses_first_tied_maximum():
    agent = QLearningAgent(5, seed=13)
    state = (0, 0, 0, 0, 0, 0)

    assert agent.choose(state, explore=False, deterministic=True) == 0


def test_same_seed_same_episode():
    a, b = BeaconExpeditionEnv(), BeaconExpeditionEnv()
    oa, _ = a.reset(seed=11); ob, _ = b.reset(seed=11)
    for _ in range(20):
        oa, ra, *_ = a.step(FORWARD); ob, rb, *_ = b.step(FORWARD)
    assert np.allclose(oa, ob) and ra == rb


def test_b1_bonus_once_and_in_order(env):
    # B2 antes que B1 no cuenta.
    place(env, BEACONS[1][0] - 0.7, BEACONS[1][1])
    _, reward, *_ , info = env.step(FORWARD)
    assert info["stage"] == 1 and info["event"] is None and reward < 5
    # B1 da +10 una sola vez.
    place(env, BEACONS[0][0] - 0.7, BEACONS[0][1])
    _, reward, *_, info = env.step(FORWARD)
    assert info["event"] == "visita B1" and info["stage"] == 2 and reward > 9
    place(env, BEACONS[0][0] - 0.7, BEACONS[0][1])
    _, reward, *_, info = env.step(FORWARD)
    assert info["event"] is None and reward < 1


def test_base_without_beacons_is_not_success(env):
    _, _, terminated, _, info = env.step(TURN_LEFT)   # sigue dentro de la base
    assert not terminated and not info["success"]


def test_full_mission_success(env):
    env.stage, env.visited = 3, [True, True]
    place(env, 2.7, 0.0, math.pi)                     # la base llega hasta x = 2.5
    _, reward, terminated, _, info = env.step(FORWARD)
    assert terminated and info["success"] and reward > 50


def test_collision_is_penalized(env):
    place(env, 4.2, 1.5)                               # R1 empieza en x = 4.5
    _, reward, terminated, _, info = env.step(FORWARD)
    assert info["collision"] and reward < -0.4 and not terminated
    assert env.x < 4.5 - 0.2                           # no atraviesa la roca


def test_crack_ends_episode(env):
    place(env, CRACK[0] - CRACK[2] - 0.1, CRACK[1])
    _, reward, terminated, _, info = env.step(FORWARD)
    assert terminated and info["end"] == "grieta" and reward <= -49


def test_battery_depletion(env):
    env.battery = 0.2
    _, reward, terminated, _, info = env.step(FORWARD)
    assert terminated and info["end"] == "bateria" and reward <= -49


def test_time_limit_truncates():
    e = BeaconExpeditionEnv(max_steps=5); e.reset(seed=0)
    for _ in range(5):
        _, _, terminated, truncated, info = e.step(TURN_LEFT)
    assert truncated and not terminated and info["end"] == "tiempo"


def test_spinning_in_place_does_not_pay(env):
    total = sum(env.step(TURN_LEFT)[1] for _ in range(100))
    assert total < 0


def test_perturbation_blocks_after_b1():
    e = BeaconExpeditionEnv(perturbation=True, ray_noise=0.0); e.reset(seed=0)
    assert BLOCK[1:] not in e.obstacles()
    place(e, BEACONS[0][0] - 0.7, BEACONS[0][1])
    e.step(FORWARD)
    assert BLOCK[1:] in e.obstacles() and e._route_exists()
    assert e.model.geom_pos[e._block_id][2] > 0         # la roca fisica aparece en MuJoCo


def test_dune_lifts_and_tilts_rover(env):
    env.set_pose(5.9, -2.2, 0.0)                       # al pie de la duna sur
    pitches = []
    for _ in range(3):
        obs, *_ = env.step(FORWARD)
        pitches.append(abs(obs[18]))
    assert env.z > 0.05 and max(pitches) > 0.1


def test_rays_see_rock_in_3d(env):
    env.set_pose(3.5, 1.5, 0.0)                        # R1 empieza 1 m adelante
    rays = env.rays()
    assert 0.6 < rays[4] < 1.0 and rays[0] > 1.0


def test_rock_jitter_keeps_route():
    e = BeaconExpeditionEnv(rock_jitter=0.5)
    for seed in range(10):
        e.reset(seed=seed)
        assert e._route_exists()


def test_cli_train_and_evaluate(tmp_path, capsys):
    logs, model = tmp_path / "logs", tmp_path / "m.npz"
    main(["train", "--episodes", "20", "--record-every", "10", "--report-every", "10",
          "--logs", str(logs), "--model", str(model)])
    main(["evaluate", "--episodes", "3", "--logs", str(logs), "--model", str(model)])
    replays = json.loads((logs / "expedition_replays.json").read_text())
    assert {"entrenamiento", "evaluación"} <= {e["mode"] for e in replays["episodes"]}
    assert (logs / "expedition_history.csv").exists() and model.exists()
    assert "tasa de exito" in capsys.readouterr().out
