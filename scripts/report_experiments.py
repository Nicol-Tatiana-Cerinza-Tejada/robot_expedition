"""Genera las tablas y graficas de docs/experimentos.md desde catalog/catalog.json.

    python scripts/report_experiments.py

Escribe docs/resultados/experimentos-tablas.md (incluido en docs/experimentos.md)
y las graficas docs/resultados/curvas-entrenamiento.png y evaluacion-por-nivel.png.
Ningun numero se copia a mano: todo sale del catalogo publicado y de
catalog/results/.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

LEVELS = ("n1", "n2", "n3")
OUT = ROOT / "docs" / "resultados"
CAUSES = ("grieta", "volco", "bateria", "tiempo")


def mean_std(values: list[float], pct=False, digits=1) -> str:
    values = [v for v in values if v is not None]
    if not values:
        return "—"
    scale = 100 if pct else 1
    mean = statistics.fmean(values) * scale
    if len(values) == 1:
        return f"{mean:.{digits}f}{' %' if pct else ''}"
    std = statistics.stdev(values) * scale
    return f"{mean:.{digits}f} ± {std:.{digits}f}{' %' if pct else ''}"


def main() -> None:
    catalog = json.loads((ROOT / "catalog" / "catalog.json").read_text(encoding="utf-8"))
    runs = [r for r in catalog["runs"] if r["status"] != "baseline"]
    baselines = [r for r in catalog["runs"] if r["status"] == "baseline"]
    by_exp: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        by_exp[run["experiment_id"]].append(run)

    lines = [f"<!-- Generado por scripts/report_experiments.py desde {catalog['served_version']} "
             f"({catalog['published_at']}). No editar a mano. -->", ""]

    # 1) Resumen por experimento y nivel (media ± d.e. entre semillas)
    lines += ["### Éxito por experimento y nivel (suite fija, 50 episodios; media ± d.e. entre semillas)", "",
              "| Experimento | Algoritmo | Entrenado en | Semillas | Pasos | Tiempo (min) | Éxito N1 | Éxito N2 | Éxito N3 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for exp_id in sorted(by_exp):
        group = by_exp[exp_id]
        row = [exp_id, group[0]["algorithm"].upper(), group[0]["level_id"].upper(),
               ", ".join(str(r["seed"]) for r in sorted(group, key=lambda r: r["seed"] or 0)),
               mean_std([r.get("effective_budget_timesteps") for r in group], digits=0),
               mean_std([(r.get("training_time_s") or 0) / 60 for r in group if r.get("training_time_s")], digits=1)]
        for level in LEVELS:
            row.append(mean_std([r["metrics_by_level"].get(level, {}).get("success_rate") for r in group], pct=True, digits=0))
        lines.append("| " + " | ".join(row) + " |")
    for b in baselines:
        lines.append("| " + " | ".join([b["run_id"], b["algorithm"], "—", "—", "—", "—", *(
            mean_std([b["metrics_by_level"].get(level, {}).get("success_rate")], pct=True, digits=0) for level in LEVELS)]) + " |")

    # 2) Detalle por run en su nivel de entrenamiento y en los demas
    for level in LEVELS:
        lines += ["", f"### Detalle por run en la suite {level.upper()} (`suite-{level}-v1`)", "",
                  "| Run | Experimento | Semilla | Éxito | Fallos por causa | Pasos | Choques/ep. | Batería final (éxitos) | Latencia media / p95 (ms) | Estado |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for run in sorted(runs, key=lambda r: (r["experiment_id"], r["seed"] or 0)):
            m = run["metrics_by_level"].get(level)
            if not m:
                lines.append(f"| `{run['run_id'][:8]}` | {run['experiment_id']} | {run['seed']} | — | sin evaluar | — | — | — | — | {run['status']} |")
                continue
            fails = ", ".join(f"{c} {m['failures_by_cause'][c]}" for c in CAUSES if m["failures_by_cause"].get(c)) or "—"
            battery = "—" if m.get("final_battery_success") is None else f"{m['final_battery_success']:.1f} %"
            lines.append(f"| `{run['run_id'][:8]}` | {run['experiment_id']} | {run['seed']} | **{m['success_rate']:.0%}** | {fails} | "
                         f"{m['steps_mean']:.1f} | {m['collisions_per_episode']:.2f} | {battery} | "
                         f"{m['latency_ms_mean']:.2f} / {m['latency_ms_p95']:.2f} | {run['status']} |")
        for b in baselines:
            m = b["metrics_by_level"].get(level)
            if m:
                fails = ", ".join(f"{c} {m['failures_by_cause'][c]}" for c in CAUSES if m["failures_by_cause"].get(c)) or "—"
                battery = "—" if m.get("final_battery_success") is None else f"{m['final_battery_success']:.1f} %"
                lines.append(f"| {b['run_id']} | referencia | — | **{m['success_rate']:.0%}** | {fails} | {m['steps_mean']:.1f} | "
                             f"{m['collisions_per_episode']:.2f} | {battery} | {m['latency_ms_mean']:.2f} / {m['latency_ms_p95']:.2f} | referencia |")

    # 3) Decisiones del catalogo
    lines += ["", f"### Decisiones de selección (`configs/selection.yaml` v{catalog['selection_criteria']['version']})", "",
              "| Nivel | Recomendado | Decisiones |", "|---|---|---|"]
    names = {r["run_id"]: f"{r['experiment_id']} s{r['seed']}" for r in runs}
    for level in LEVELS:
        rec = catalog["recommended_run_id"].get(level)
        notes = "<br>".join(f"{names.get(d['run_id'], d['run_id'])}: {d['decision']} — {d['reason']}"
                            for d in catalog["decisions"].get(level, []) if d["decision"] != "no elegible")
        lines.append(f"| {level.upper()} | {names.get(rec, rec)} (`{(rec or '—')[:8]}`) | {notes} |")
    (OUT / "experimentos-tablas.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Graficas: curvas de entrenamiento (training/*) separadas de la evaluacion (suite fija)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for i, exp_id in enumerate(sorted(by_exp)):
        for j, run in enumerate(sorted(by_exp[exp_id], key=lambda r: r["seed"] or 0)):
            for ax, key in zip(axes, ("training_success_rate", "training_reward")):
                curve = run.get("curves", {}).get(key) or []
                if curve:
                    xs, ys = zip(*curve)
                    offset = 150_000 if exp_id == "exp-003" else 0       # el curriculo continua tras 150k en N1
                    ax.plot([x + offset for x in xs], ys, color=colors[i % len(colors)], alpha=0.85,
                            label=exp_id if j == 0 else None, linewidth=1.6)
    axes[0].set_title("Éxito en entrenamiento (con exploración)")
    axes[1].set_title("Recompensa por episodio en entrenamiento")
    for ax in axes:
        ax.set_xlabel("pasos de entrenamiento")
        ax.grid(alpha=0.3)
    axes[0].set_ylim(-0.02, 1.02)
    axes[0].legend(fontsize=8)
    fig.suptitle("Curvas de entrenamiento (MLflow training/*); una línea por semilla")
    fig.tight_layout()
    fig.savefig(OUT / "curvas-entrenamiento.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4.2))
    groups = [*sorted(by_exp), *(b["run_id"] for b in baselines)]
    width = 0.26
    for k, level in enumerate(LEVELS):
        means, errs = [], []
        for g in groups:
            members = by_exp.get(g) or [b for b in baselines if b["run_id"] == g]
            values = [r["metrics_by_level"].get(level, {}).get("success_rate") for r in members]
            values = [v for v in values if v is not None]
            means.append(statistics.fmean(values) if values else 0)
            errs.append(statistics.stdev(values) if len(values) > 1 else 0)
        ax.bar([x + (k - 1) * width for x in range(len(groups))], means, width, yerr=errs, capsize=3, label=level.upper())
    ax.set_xticks(range(len(groups)), groups, rotation=20)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("tasa de éxito (suite fija)")
    ax.set_title("Evaluación determinista por nivel (media ± d.e. entre semillas)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "evaluacion-por-nivel.png", dpi=120)
    plt.close(fig)
    print("docs/resultados/experimentos-tablas.md, curvas-entrenamiento.png, evaluacion-por-nivel.png")


if __name__ == "__main__":
    main()
