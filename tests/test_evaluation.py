"""Pruebas de la suite de evaluacion y de las politicas (paso 2 del plan)."""

import json
import subprocess

import numpy as np
import pytest

from pipelines.evaluate import ROOT, evaluate, load_suite, reference_route, save_result
from pipelines.policies import QTablePolicy, RandomPolicy, RulePolicy
from robot_expedition import BeaconExpeditionEnv
from robot_expedition.qlearning import STATE_SHAPE

CASE_FIELDS = {"seed", "success", "end", "terminated", "truncated", "steps", "visited", "battery",
               "collisions", "path_length", "return", "latency_ms_mean", "latency_ms_max"}
METRIC_FIELDS = {"episodes", "success_rate", "failures_by_cause", "end_counts", "route_efficiency",
                 "collisions_per_episode", "final_battery_success", "beacons_visited_mean",
                 "steps_mean", "return_mean", "return_std", "latency_ms_mean", "latency_ms_p95"}


def test_suites_are_fixed_and_do_not_overlap():
    seeds = {lvl: load_suite(f"suite-{lvl}-v1")["seeds"] for lvl in ("n1", "n2", "n3")}
    assert all(len(s) == 50 for s in seeds.values())
    assert load_suite("suite-n2-v1")["seeds"] == seeds["n2"]                # reproducible
    assert not set(seeds["n1"]) & set(seeds["n2"]) and not set(seeds["n2"]) & set(seeds["n3"])
    assert min(min(s) for s in seeds.values()) >= 100000                    # fuera de las semillas de entrenamiento


def test_same_policy_and_suite_give_same_result():
    a = evaluate(RandomPolicy(), "n1", episodes=3)
    b = evaluate(RandomPolicy(), "n1", episodes=3)
    strip = lambda r: [{k: v for k, v in c.items() if not k.startswith("latency")} for c in r["cases"]]
    assert strip(a) == strip(b)


def test_result_has_all_fields_and_round_trips(tmp_path):
    result = evaluate(RulePolicy(), "n2", episodes=2)
    assert result["partial"] and result["level_id"] == "n2" and result["suite_id"] == "suite-n2-v1"
    assert result["environment_version"] and len(result["environment_hash"]) == 64
    assert METRIC_FIELDS <= result["metrics"].keys()
    assert all(CASE_FIELDS <= case.keys() for case in result["cases"])
    path = save_result(result, tmp_path / "r.json")
    assert json.loads(path.read_text(encoding="utf-8"))["metrics"] == result["metrics"]


def test_suite_level_must_match():
    with pytest.raises(ValueError):
        evaluate(RulePolicy(), "n1", "suite-n2-v1", episodes=1)


def test_reserved_test_needs_private_seeds(monkeypatch):
    monkeypatch.delenv("EXPEDITION_TEST_SEEDS", raising=False)
    if not (ROOT / "configs" / "suites" / "test-final.local.yaml").exists():
        with pytest.raises(RuntimeError):
            load_suite("test-final")
    monkeypatch.setenv("EXPEDITION_TEST_SEEDS", "7, 8")
    result = evaluate(RulePolicy(), "n1", "test-final")
    assert result["metrics"]["episodes"] == 2
    assert all(case["seed"] == "reservada" for case in result["cases"])   # no se publican


def test_reserved_seed_files_are_ignored_by_git():
    out = subprocess.run(["git", "check-ignore", "configs/suites/test-final.local.yaml"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0


def test_rule_policy_turns_toward_target_and_avoids_front():
    obs = np.zeros(20, dtype=np.float32)
    obs[:9] = 5.0
    obs[10], obs[11] = np.sin(1.0), np.cos(1.0)          # objetivo a la izquierda
    assert RulePolicy()(obs) == 1                          # avanzar + izq
    obs[3:6] = 0.3
    obs[0:3] = 4.0; obs[6:9] = 0.5
    assert RulePolicy()(obs) == 4                          # frente bloqueado, mas espacio a la derecha


def test_qtable_adapter(tmp_path):
    q = np.zeros((*STATE_SHAPE, 5), dtype=np.float32)
    q[..., 2] = 1.0
    path = tmp_path / "q.npz"
    np.savez_compressed(path, q=q, visits=np.zeros(STATE_SHAPE), epsilon=0.0)
    obs, _ = BeaconExpeditionEnv(level="n1").reset(seed=1)
    assert QTablePolicy(path)(obs) == 2


def test_ppo_adapter_matches_vecnormalize(tmp_path):
    sb3 = pytest.importorskip("stable_baselines3")
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from pipelines.policies import PPOPolicy

    venv = VecNormalize(DummyVecEnv([lambda: BeaconExpeditionEnv(level="n1")]), norm_reward=False)
    model = sb3.PPO("MlpPolicy", venv, n_steps=16, batch_size=8, n_epochs=1, seed=0, device="cpu")
    model.learn(16)
    model.save(tmp_path / "model.zip"); venv.save(tmp_path / "vecnormalize.pkl")
    policy = PPOPolicy(tmp_path / "model.zip", tmp_path / "vecnormalize.pkl")
    obs, _ = BeaconExpeditionEnv(level="n1").reset(seed=3)
    expected, _ = model.predict(venv.normalize_obs(obs), deterministic=True)
    assert policy(obs) == int(expected)


def test_reference_routes():
    assert reference_route(1) == pytest.approx(17.46, abs=0.01)
    assert reference_route(2) == pytest.approx(24.46, abs=0.01)
