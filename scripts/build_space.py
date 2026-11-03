"""Arma la carpeta de despliegue de la API para Hugging Face Spaces (SDK docker).

    python scripts/build_space.py --out /tmp/space [--release v1.0]

Copia solo lo que la API necesita (api/, pipelines/, robot_expedition/,
configs/, catalog/, manifests/ y los pesos verificados de los modelos del
catalogo), agrega el encabezado YAML que pide Hugging Face y fija en el
Dockerfile el commit y la release servidos (los muestra /version).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.policies import model_files, sha256_file  # noqa: E402

COPY = ["api", "pipelines", "robot_expedition", "configs", "catalog", "manifests", "requirements.txt"]
VERCEL = "https://web-five-gules-83.vercel.app"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--release", default=None)
    parser.add_argument("--origins", default=VERCEL, help="ALLOWED_ORIGINS de producción")
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    release = args.release or subprocess.check_output(["git", "describe", "--tags", "--always"], cwd=ROOT, text=True).strip()
    out = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.local.yaml", "smoke")
    for item in COPY:
        src = ROOT / item
        (shutil.copytree(src, out / item, ignore=ignore) if src.is_dir() else shutil.copy2(src, out / item))
    # Pesos verificados de cada run del catalogo.
    copied = 0
    for manifest_path in sorted((ROOT / "manifests").glob("*.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        weights, normalization = model_files(ROOT / "models", manifest)
        if manifest.get("status") != "completed" or not weights.exists() or sha256_file(weights) != manifest["model_sha256"]:
            continue
        for path in (weights, normalization):
            if path and path.exists():
                target = out / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        copied += 1
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerfile = dockerfile.replace("ARG GIT_COMMIT=desconocido", f"ARG GIT_COMMIT={commit}")
    dockerfile = dockerfile.replace("ARG RELEASE=sin-release", f"ARG RELEASE={release}")
    dockerfile = dockerfile.replace("ENV GIT_COMMIT=$GIT_COMMIT", f"ENV ALLOWED_ORIGINS={args.origins} GIT_COMMIT=$GIT_COMMIT")
    (out / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    (out / ".dockerignore").write_text("**/__pycache__\n*.pyc\n", encoding="utf-8")
    (out / "README.md").write_text(f"""---
title: Robot Expedition API
emoji: 🤖
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# Robot Expedition · API

API de simulación y evaluación (FastAPI + MuJoCo) del proyecto final de MLOps.
Código: https://github.com/Nicol-Tatiana-Cerinza-Tejada/robot_expedition
(commit `{commit}`, release `{release}`). Rutas: `/health`, `/version`,
`/catalog`, `/runs/{{run_id}}`, `/evaluate`, `/sim/reset`, `/sim/step`, `/monitor`.
Web: {args.origins}
""", encoding="utf-8")
    print(f"{out}: commit {commit[:10]}, release {release}, {copied} modelos verificados")


if __name__ == "__main__":
    main()
