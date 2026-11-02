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
