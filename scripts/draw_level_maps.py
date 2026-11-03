"""Dibuja el mapa de cada nivel (N1, N2, N3) desde las constantes del ambiente.

    python scripts/draw_level_maps.py        # -> docs/mapas/mapa-n1.svg, mapa-n2.svg, mapa-n3.svg

Los mapas salen del codigo (no a mano): si cambia el ambiente, se regeneran.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from robot_expedition.envs.beacon_expedition import (  # noqa: E402
    BASE, BEACONS, BLOCK, CRACK, DUNES, MAP_H, MAP_W, RAY_ANGLES, ROCKS, SAND, VISIT_RADIUS,
    load_level_config,
)

SCALE, PAD_X, PAD_Y = 50, 60, 70
W, H = int(MAP_W * SCALE + 2 * PAD_X), int(MAP_H * SCALE + PAD_Y + 150)


def px(x: float) -> float:
    return PAD_X + x * SCALE


def py(y: float) -> float:
    return PAD_Y + (MAP_H / 2 - y) * SCALE


def rect(cx, cy, hx, hy, **attrs) -> str:
    extra = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return (f'<rect x="{px(cx - hx):.1f}" y="{py(cy + hy):.1f}" width="{2 * hx * SCALE:.1f}" '
            f'height="{2 * hy * SCALE:.1f}" {extra}/>')


def text(x, y, body, size=13, anchor="middle", weight="normal", fill="#2b2118") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
            f'font-weight="{weight}" fill="{fill}">{body}</text>')


def draw(level_id: str) -> str:
    level = load_level_config(level_id)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        'font-family="DejaVu Sans, Arial, sans-serif">',
        f'<!-- Generado por scripts/draw_level_maps.py desde robot_expedition/envs/beacon_expedition.py '
        f'y configs/levels/{level_id}.yaml. Escala: 1 m = {SCALE} px. -->',
        '<defs><pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">'
        '<path d="M 50 0 L 0 0 0 50" fill="none" stroke="#c9a77a" stroke-width="0.6"/></pattern>'
        '<pattern id="sand" width="8" height="8" patternUnits="userSpaceOnUse">'
        '<circle cx="2" cy="2" r="1.1" fill="#a8743a"/><circle cx="6" cy="6" r="1.1" fill="#a8743a"/></pattern>'
        '<radialGradient id="dune"><stop offset="0" stop-color="#b9763f" stop-opacity=".75"/>'
        '<stop offset="1" stop-color="#b9763f" stop-opacity="0"/></radialGradient></defs>',
        f'<rect width="{W}" height="{H}" fill="#fbf6ef"/>',
        text(W / 2, 26, f"Robot Expedition · nivel {level_id.upper()}", size=17, weight="bold"),
        text(W / 2, 48, level.get("description", ""), size=13),
        rect(MAP_W / 2, 0, MAP_W / 2, MAP_H / 2, fill="#e6c49c"),
        rect(MAP_W / 2, 0, MAP_W / 2, MAP_H / 2, fill="url(#grid)", stroke="#6b6b70", stroke_width=6),
    ]
    if level["dunes"]:
        for cx, cy, amp, sigma in DUNES:
            parts.append(f'<circle cx="{px(cx):.1f}" cy="{py(cy):.1f}" r="{2 * sigma * SCALE:.1f}" fill="url(#dune)"/>')
            parts.append(text(px(cx), py(cy) + 4, f"duna {amp:.2f} m", size=11, fill="#6d3f17"))
    parts.append(rect(*SAND, fill="url(#sand)", stroke="#a8743a", stroke_dasharray="4 3"))
    parts.append(text(px(SAND[0]), py(SAND[1] - SAND[3]) + 14, "arena (arrastre)", size=11))
    parts.append(rect(*CRACK, fill="#2b1d14"))
    parts.append(text(px(CRACK[0]), py(CRACK[1] + CRACK[3]) - 6, "grieta (0.5 m)", size=11))
    parts.append(rect(*BASE, fill="#9fd3a8", fill_opacity=".6", stroke="#2f7d3c", stroke_width=2))
    parts.append(text(px(BASE[0]), py(BASE[1] - BASE[3]) + 16, "BASE", weight="bold", fill="#2f7d3c"))
    for name, cx, cy, hx, hy, h in ROCKS[:level["active_rocks"]]:
        parts.append(rect(cx, cy, hx, hy, fill="#8c8c92", stroke="#55555a", stroke_width=2))
        parts.append(text(px(cx), py(cy) + 4, name, weight="bold", fill="#fff"))
    for name, cx, cy, hx, hy, h in ROCKS[level["active_rocks"]:]:
        parts.append(rect(cx, cy, hx, hy, fill="none", stroke="#8c8c92", stroke_dasharray="3 4"))
    if level["blocking"]:
        _, cx, cy, hx, hy, h = BLOCK
        parts.append(rect(cx, cy, hx, hy, fill="#ef5b4c", stroke="#9b2318", stroke_width=2))
        parts.append(text(px(cx), py(cy + hy) - 6, "bloqueo (aparece al visitar B1)", size=11, fill="#9b2318"))
    for i, (bx, by) in enumerate(BEACONS[:level["beacons"]], start=1):
        parts.append(f'<circle cx="{px(bx):.1f}" cy="{py(by):.1f}" r="{VISIT_RADIUS * SCALE:.1f}" '
                     'fill="#ffd34d" fill-opacity=".5" stroke="#b07b00" stroke-width="2"/>')
        parts.append(text(px(bx), py(by) + 5, f"B{i}", weight="bold"))
    # Rover en la posicion inicial con sus 9 rayos (el rayo muerto, en rojo).
    sx, sy = BASE[0], BASE[1]
    for i, angle in enumerate(RAY_ANGLES):
        ex, ey = sx + 1.2 * math.cos(angle), sy + 1.2 * math.sin(angle)
        dead = level.get("dead_ray") is not None and int(level["dead_ray"]) == i
        parts.append(f'<line x1="{px(sx):.1f}" y1="{py(sy):.1f}" x2="{px(ex):.1f}" y2="{py(ey):.1f}" '
                     f'stroke="{"#d22" if dead else "#3a6ea5"}" stroke-width="{2.5 if dead else 1}" '
                     f'{"stroke-dasharray=\"4 3\"" if dead else ""}/>')
    parts.append(rect(sx, sy, 0.25, 0.16, fill="#f4f1ea", stroke="#333", stroke_width=1.5))
    # Ruta de referencia (centro a centro).
    stops = [BASE[:2], *BEACONS[:level["beacons"]], BASE[:2]]
    path = " ".join(f"{'M' if i == 0 else 'L'} {px(x):.1f} {py(y):.1f}" for i, (x, y) in enumerate(stops))
    parts.append(f'<path d="{path}" fill="none" stroke="#3a6ea5" stroke-width="1.5" stroke-dasharray="7 5" opacity=".7"/>')

    legend_y = py(-MAP_H / 2) + 34
    noise = f"ruido de rayos σ = {level['ray_noise']} m"
    dead = f"rayo {level['dead_ray']} (frontal) muerto: siempre 5 m" if level.get("dead_ray") is not None else "todos los rayos sanos"
    lines = [
        f"Balizas: {level['beacons']} · rocas activas: {level['active_rocks']} de {len(ROCKS)} "
        f"(punteadas = inactivas) · dunas: {'sí' if level['dunes'] else 'no'} · "
        f"bloqueo: {'sí' if level['blocking'] else 'no'}",
        f"Sensores: {noise} · {dead}",
        "Línea azul punteada: ruta de referencia de centro a centro.",
        "x ∈ [0, 12] m, y ∈ [-6, 6] m; el rover sale del centro de la base mirando a +x.",
    ]
    for i, line in enumerate(lines):
        parts.append(text(PAD_X, legend_y + i * 20, line, size=13, anchor="start"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    out_dir = ROOT / "docs" / "mapas"
    out_dir.mkdir(parents=True, exist_ok=True)
    for level_id in ("n1", "n2", "n3"):
        path = out_dir / f"mapa-{level_id}.svg"
        path.write_text(draw(level_id), encoding="utf-8")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
