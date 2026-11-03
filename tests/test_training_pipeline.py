import hashlib

from pipelines.train import _manifest, read_config, sha256_file, sha256_json


def test_experiment_config_and_hash_are_reproducible(tmp_path):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        "experiment_id: exp-test\n"
        "hypothesis: baseline\n"
        "level_id: n2\n"
        "algorithm: qlearning\n"
        "budget_timesteps: 8\n"
        "seeds: [1]\n",
        encoding="utf-8",
    )

    expected_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    assert sha256_file(config_path) == expected_hash
    assert sha256_file(config_path) == expected_hash
    assert read_config(config_path)["environment"]["max_steps"] == 400
    assert sha256_json({"seed": 1}) == sha256_json({"seed": 1})


def test_manifest_contains_effective_budget_and_failure_diagnosis(tmp_path):
    config = {
        "experiment_id": "exp-test",
        "level_id": "n2",
        "algorithm": "qlearning",
    }

    manifest = _manifest(
        run_id="run-test",
        config=config,
        config_path=tmp_path / "experiment.yaml",
        config_hash="a" * 64,
        source_config_hash="c" * 64,
        seed=1,
        git_commit="b" * 40,
        origin="https://example.test/robot-expedition.git",
        budget=8,
        effective_budget=8,
        parent_run_id=None,
        status="failed",
        diagnosis="RuntimeError: test; sin checkpoint disponible",
        model_uri=None,
        model_hash=None,
        normalization_uri=None,
        metrics={},
        checkpoint_uri=None,
    )

    assert manifest["config_sha256"] == "a" * 64
    assert manifest["source_config_sha256"] == "c" * 64
    assert manifest["effective_budget_timesteps"] == 8
    assert manifest["status"] == "failed"
    assert "sin checkpoint disponible" in manifest["diagnosis"]


def _experiment(tmp_path, level_id, extra=""):
    path = tmp_path / f"exp-{level_id}.yaml"
    path.write_text(
        "experiment_id: exp-test\n"
        "hypothesis: niveles\n"
        f"level_id: {level_id}\n"
        "algorithm: qlearning\n"
        "budget_timesteps: 8\n"
        "seeds: [1]\n" + extra,
        encoding="utf-8",
    )
    return path


def test_training_uses_the_level_config(tmp_path):
    from pipelines.train import build_env, evaluation_suite

    for level_id, noise, beacons in (("n1", 0.02, 1), ("n2", 0.02, 2), ("n3", 0.08, 2)):
        config = read_config(_experiment(tmp_path, level_id))
        env = build_env(config)
        assert env.ray_noise == noise and env.beacon_count == beacons
        assert evaluation_suite(level_id) == f"suite-{level_id}-v1"
    # environment solo sobrescribe si se pide explicitamente
    config = read_config(_experiment(tmp_path, "n3", "environment:\n  ray_noise: 0.0\n"))
    assert build_env(config).ray_noise == 0.0


def test_unknown_level_is_rejected(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        read_config(_experiment(tmp_path, "n9"))


def test_final_evaluation_uses_the_fixed_suite(tmp_path):
    import numpy as np

    from pipelines.train import _evaluate
    from robot_expedition.qlearning import STATE_SHAPE

    model = tmp_path / "qlearning.npz"
    np.savez_compressed(model, q=np.zeros((*STATE_SHAPE, 5), dtype=np.float32),
                        visits=np.zeros(STATE_SHAPE), epsilon=0.0)
    config = read_config(_experiment(tmp_path, "n1"))
    result = _evaluate(config, model, None, episodes=2)
    assert result["suite_id"] == "suite-n1-v1" and result["partial"]
    assert result["policy"]["model_sha256"] and len(result["cases"]) == 2
