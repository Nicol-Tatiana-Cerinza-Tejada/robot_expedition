"""Empaqueta los modelos del catalogo para una release publica de GitHub.

    python scripts/package_models.py --tag models-v2              # -> dist/robot-expedition-models-v2.zip
    python scripts/package_models.py --tag models-v2 --mlflow     # + dist/robot-expedition-mlflow-v2.zip

El ZIP usa rutas POSIX (models/<run_id>/..., manifests/<run_id>.json) para que
se extraiga igual en Linux, macOS y Windows, e incluye SHA256SUMS.txt. Solo
entran los runs `completed` cuyo SHA-256 coincide con su manifiesto.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.policies import model_files, sha256_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", required=True, help="por ejemplo models-v2")
    parser.add_argument("--mlflow", action="store_true", help="empaqueta tambien mlflow.db y mlruns/")
    args = parser.parse_args()
    suffix = args.tag.split("-")[-1]
    out_dir = ROOT / "dist"
    out_dir.mkdir(exist_ok=True)
    target = out_dir / f"robot-expedition-models-{suffix}.zip"
    sums, skipped = [], []
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for manifest_path in sorted((ROOT / "manifests").glob("*.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            run_id = manifest["run_id"]
            weights, _ = model_files(ROOT / "models", manifest)
            if manifest.get("status") != "completed" or not weights.exists() \
                    or sha256_file(weights) != manifest.get("model_sha256"):
                skipped.append(run_id)
                continue
            files = [manifest_path, *(p for p in (ROOT / "models" / run_id).rglob("*") if p.is_file())]
            dvc = ROOT / "models" / f"{run_id}.dvc"
            if dvc.exists():
                files.append(dvc)
            for path in files:
                rel = path.relative_to(ROOT).as_posix()
                archive.write(path, rel)
                sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {rel}")
        archive.writestr("SHA256SUMS.txt", "\n".join(sums) + "\n")
    print(f"{target.relative_to(ROOT)}: {len(sums)} archivos; omitidos (sin pesos verificados): {skipped}")

    if args.mlflow:
        mlflow_zip = out_dir / f"robot-expedition-mlflow-{suffix}.zip"
        with zipfile.ZipFile(mlflow_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(ROOT / "mlflow.db", "mlflow.db")
            for path in sorted((ROOT / "mlruns").rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(ROOT).as_posix())
        print(f"{mlflow_zip.relative_to(ROOT)}: {mlflow_zip.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
