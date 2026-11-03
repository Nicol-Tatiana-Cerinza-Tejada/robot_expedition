"""Pruebas del catalogo versionado: seleccion, publicacion, rollback y descarga de la release."""

import io
import json
import zipfile

import pytest

from api.store import Store
from pipelines import catalog as cat


def metrics(success, volco=0, grieta=0, collisions=0.0, steps=100.0, p95=0.5, partial=False):
    fails = {k: v for k, v in (("volco", volco), ("grieta", grieta)) if v}
    return {"success_rate": success, "failures_by_cause": fails, "collisions_per_episode": collisions,
            "steps_mean": steps, "latency_ms_p95": p95, "partial": partial}


def run(run_id, status="completed", **levels):
    return {"run_id": run_id, "status": status, "environment_version": "robot-expedition-3d/1.0.0",
            "metrics_by_level": levels}


@pytest.fixture
def criteria(tmp_path):
    return cat.load_selection(cat.Paths())


def test_first_recommendation_needs_minimum_success(criteria):
    rec, decisions = cat.select([run("a", n2=metrics(0.4))], {}, {}, criteria)
    assert rec["n2"] is None and decisions["n2"][-1]["decision"] == "rechazado"
    rec, _ = cat.select([run("a", n2=metrics(0.4)), run("b", n2=metrics(0.9))], {}, {}, criteria)
    assert rec["n2"] == "b"


def test_replacement_needs_five_points_and_no_extra_rollovers(criteria):
    current = {"n2": "old"}
    entries = [run("old", n2=metrics(0.90)), run("small", n2=metrics(0.94))]
    rec, decisions = cat.select(entries, current, {}, criteria)
    assert rec["n2"] == "old"
    assert any(d["run_id"] == "small" and d["decision"] == "rechazado" for d in decisions["n2"])

    entries = [run("old", n2=metrics(0.80)), run("risky", n2=metrics(0.96, volco=3))]
    rec, _ = cat.select(entries, current, {}, criteria)
    assert rec["n2"] == "old"                                    # mejora, pero vuelca mas

    entries = [run("old", n2=metrics(0.80)), run("better", n2=metrics(0.90))]
    assert cat.select(entries, current, {}, criteria)[0]["n2"] == "better"


def test_failed_partial_and_slow_runs_are_not_eligible(criteria):
    entries = [run("f", status="failed", n2=metrics(1.0)), run("p", n2=metrics(1.0, partial=True)),
               run("s", n2=metrics(1.0, p95=50.0)), run("ok", n2=metrics(0.7))]
    rec, decisions = cat.select(entries, {}, {}, criteria)
    assert rec["n2"] == "ok"
    reasons = {d["run_id"]: d["reason"] for d in decisions["n2"] if d["decision"] == "no elegible"}
    assert set(reasons) == {"f", "p", "s"}


def test_baselines_are_references_not_recommendations(criteria):
    baseline = {**run("baseline-rule", n2=metrics(1.0)), "status": "baseline"}
    rec, _ = cat.select([baseline, run("m", n2=metrics(0.6))], {}, {}, criteria)
    assert rec["n2"] == "m"


def test_pins_win_over_selection(criteria):
    entries = [run("old", n2=metrics(0.5)), run("new", n2=metrics(1.0))]
    pins = {"n2": {"run_id": "old", "reason": "rollback"}}
    assert cat.select(entries, {"n2": "new"}, pins, criteria)[0]["n2"] == "old"


@pytest.fixture
def paths(tmp_path):
    p = cat.Paths(tmp_path)
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "selection.yaml").write_bytes(cat.Paths().selection.read_bytes())
    return p


def catalog_with(recommended):
    return {"schema": "test", "recommended_run_id": recommended, "pins": {}, "decisions": {},
            "runs": [run("old", n2=metrics(0.8)), run("new", n2=metrics(1.0))]}


def test_publish_is_idempotent_and_versioned(paths):
    first = cat.publish(paths, catalog_with({"n2": "old"}), action="publish", reason="r", who="test")
    again = cat.publish(paths, catalog_with({"n2": "old"}), action="publish", reason="r", who="test")
    assert first["changed"] and first["catalog_version"] == 1
    assert not again["changed"] and again["catalog_version"] == 1          # mismo artefacto
    second = cat.publish(paths, catalog_with({"n2": "new"}), action="publish", reason="r", who="test")
    assert second["catalog_version"] == 2
    published = cat.load_catalog(paths)
    assert published["served_version"] == "catalog-v2" and published["previous_version"] == 1
    assert [h["catalog_version"] for h in cat.history(paths)] == [1, 2]


def test_rollback_records_who_when_from_to_and_why(paths):
    cat.publish(paths, catalog_with({"n2": "new"}), action="publish", reason="r", who="test")
    result = cat.rollback(paths, "n2", "old", "el nuevo falla en la demo", who="nicol")
    published = cat.load_catalog(paths)
    assert published["recommended_run_id"]["n2"] == "old"
    assert published["pins"]["n2"]["from_run_id"] == "new"
    last = cat.history(paths)[-1]
    assert last["action"] == "rollback" and last["actor"] == "nicol" and last["at"]
    assert last["recommended_before"]["n2"] == "new" and "el nuevo falla" in last["reason"]
    assert result["catalog_version"] == 2
    with pytest.raises(KeyError):
        cat.rollback(paths, "n2", "no-existe", "x")
    unpinned = cat.unpin(paths, "n2", "volver a la seleccion", who="nicol")
    assert unpinned["changed"] and "n2" not in cat.load_catalog(paths)["pins"]


def test_release_pull_extracts_only_the_run_and_normalizes_windows_paths(tmp_path, monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("models\\abc\\qlearning.npz", b"pesos")          # ZIP armado en Windows
        archive.writestr("models/otro/qlearning.npz", b"otro")
        archive.writestr("models/abc/../../escape.txt", b"no")
    source = tmp_path / "release.zip"
    source.write_bytes(buffer.getvalue())
    monkeypatch.setenv("API_MODELS_URL", source.as_uri())
    store = Store(tmp_path / "repo")
    assert store._release_pull("abc") is None
    assert (tmp_path / "repo" / "models" / "abc" / "qlearning.npz").read_bytes() == b"pesos"
    assert not (tmp_path / "repo" / "models" / "otro").exists()
    assert not (tmp_path / "escape.txt").exists() and not (tmp_path / "repo" / "escape.txt").exists()


def test_published_catalog_feeds_the_api(paths, monkeypatch):
    import api.main as api_main
    from fastapi.testclient import TestClient
    cat.publish(paths, catalog_with({"n2": "new"}), action="publish", reason="r", who="test")
    monkeypatch.setattr(api_main, "store", Store(paths.root))
    client = TestClient(api_main.app)
    version = client.get("/version").json()
    assert version["served_version"] == "catalog-v1" and version["recommended_run_id"] == {"n2": "new"}
    runs = {r["run_id"] for r in client.get("/catalog").json()["runs"]}
    assert {"old", "new", "baseline-rule"} <= runs
    assert json.loads(paths.catalog.read_text())["content_sha256"] == client.get("/catalog").json()["content_sha256"]
