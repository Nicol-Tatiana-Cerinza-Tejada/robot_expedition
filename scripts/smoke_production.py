#!/usr/bin/env python3
"""Comprueba la integración desplegada entre Vercel y la API de producción.

Solo usa la biblioteca estándar para que pueda ejecutarse desde un clon limpio.
El comando termina con código distinto de cero ante la primera comprobación
fallida y puede guardar una evidencia JSON resumida con ``--output``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_WEB_URL = "https://web-five-gules-83.vercel.app"
DEFAULT_API_URL = "https://robot-expedition-api.onrender.com"
RETRYABLE_STATUS = {502, 503, 504}


class SmokeFailure(RuntimeError):
    """Una comprobación de producción no cumplió su contrato."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def http_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float,
    attempts: int = 3,
) -> tuple[int, dict[str, str], bytes]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        request_headers["Content-Type"] = "application/json"

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.status, dict(response.headers.items()), response.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code not in RETRYABLE_STATUS or attempt == attempts:
                raise SmokeFailure(f"{method} {url} devolvió HTTP {exc.code}: {body}") from exc
            last_error = exc
        except (TimeoutError, URLError) as exc:
            if attempt == attempts:
                raise SmokeFailure(f"{method} {url} no respondió: {exc}") from exc
            last_error = exc
        time.sleep(attempt * 2)
    raise SmokeFailure(f"{method} {url} no respondió: {last_error}")


def get_text(url: str, *, timeout: float) -> tuple[dict[str, str], str]:
    status, headers, body = http_request(url, timeout=timeout)
    require(status == 200, f"GET {url} devolvió HTTP {status}")
    return headers, body.decode("utf-8", errors="replace")


def request_json(
    url: str,
    *,
    timeout: float,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    status, response_headers, body = http_request(
        url, method=method, payload=payload, headers=headers, timeout=timeout
    )
    require(status == 200, f"{method} {url} devolvió HTTP {status}")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"{method} {url} no devolvió JSON válido") from exc
    require(isinstance(parsed, dict), f"{method} {url} no devolvió un objeto JSON")
    return response_headers, parsed


def valid_frame(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 13
        and isinstance(value[12], list)
        and len(value[12]) == 9
    )


def normalized_origin(url: str) -> str:
    parsed = urlparse(url)
    require(parsed.scheme == "https" and parsed.netloc, f"la URL debe usar HTTPS: {url}")
    return f"{parsed.scheme}://{parsed.netloc}"


def run_smoke(web_url: str, api_url: str, timeout: float) -> dict[str, Any]:
    web_url = web_url.rstrip("/")
    api_url = api_url.rstrip("/")
    web_origin = normalized_origin(web_url)
    normalized_origin(api_url)
    checks: list[dict[str, str]] = []

    def passed(name: str, detail: str) -> None:
        checks.append({"name": name, "status": "pass", "detail": detail})
        print(f"PASS  {name}: {detail}")

    _, html = get_text(f"{web_url}/", timeout=timeout)
    require("Robot Expedition" in html, "la portada no contiene Robot Expedition")
    asset_match = re.search(r'<script[^>]+src=["\']([^"\']+\.js)["\']', html, re.IGNORECASE)
    require(asset_match is not None, "la portada no referencia el JavaScript compilado")
    asset_url = urljoin(f"{web_url}/", asset_match.group(1))
    _, javascript = get_text(asset_url, timeout=timeout)
    require(api_url in javascript, "el bundle de Vercel no contiene la URL de la API configurada")
    require(
        re.search(r"https?://(?:localhost|127\.0\.0\.1)(?::\d+)?", javascript, re.IGNORECASE) is None,
        "el bundle de producción contiene una URL de localhost",
    )
    passed("web", f"portada y bundle {asset_url.removeprefix(web_origin)}")

    _, health = request_json(f"{api_url}/health", timeout=timeout)
    require(health.get("status") == "ok", "/health no informó status=ok")
    passed("health", "API disponible por HTTPS")

    _, version = request_json(f"{api_url}/version", timeout=timeout)
    for field in ("git_commit", "release", "served_version", "environment_version"):
        require(version.get(field), f"/version no informó {field}")
    require(isinstance(version.get("recommended_run_id"), dict), "/version no informó recomendaciones por nivel")
    passed(
        "version",
        f"{version['release']} · {str(version['git_commit'])[:8]} · {version['served_version']}",
    )

    catalog_headers, catalog = request_json(
        f"{api_url}/catalog", timeout=timeout, headers={"Origin": web_origin}
    )
    allow_origin = next(
        (value for key, value in catalog_headers.items() if key.lower() == "access-control-allow-origin"),
        None,
    )
    require(allow_origin == web_origin, f"CORS devolvió {allow_origin!r} en vez de {web_origin!r}")
    runs = catalog.get("runs")
    require(isinstance(runs, list) and runs, "/catalog no contiene runs")
    run_ids = {run.get("run_id") for run in runs if isinstance(run, dict)}
    recommended = catalog.get("recommended_run_id")
    recommended_n2 = recommended.get("n2") if isinstance(recommended, dict) else None
    evaluation_run = recommended_n2 if recommended_n2 in run_ids else "baseline-rule"
    require(evaluation_run in run_ids, "el catálogo no contiene un run evaluable")
    passed("catalog-cors", f"{len(runs)} runs; origen permitido {web_origin}")

    _, evaluation = request_json(
        f"{api_url}/evaluate",
        timeout=timeout,
        method="POST",
        payload={"run_id": evaluation_run, "level_id": "n2", "seeds": [7]},
        headers={"Origin": web_origin},
    )
    cases = evaluation.get("cases")
    episode = evaluation.get("episode")
    require(isinstance(cases, list) and len(cases) == 1, "/evaluate no devolvió el caso solicitado")
    require(isinstance(episode, dict), "/evaluate no devolvió episodio")
    frames = episode.get("frames")
    require(isinstance(frames, list) and frames and valid_frame(frames[0]), "el episodio no contiene cuadros válidos")
    metrics = evaluation.get("metrics")
    require(isinstance(metrics, dict) and metrics.get("episodes") == 1, "las métricas no corresponden a un episodio")
    passed("evaluate", f"run {evaluation_run[:12]} · {len(frames)} cuadros")

    _, reset = request_json(
        f"{api_url}/sim/reset",
        timeout=timeout,
        method="POST",
        payload={"level_id": "n1", "seed": 7},
        headers={"Origin": web_origin},
    )
    session_id = reset.get("session_id")
    require(isinstance(session_id, str) and session_id, "/sim/reset no devolvió session_id")
    require(reset.get("mode") == "manual" and valid_frame(reset.get("frame")), "/sim/reset no inició un cuadro manual válido")
    _, step = request_json(
        f"{api_url}/sim/step",
        timeout=timeout,
        method="POST",
        payload={"session_id": session_id, "action": 1},
        headers={"Origin": web_origin},
    )
    require(valid_frame(step.get("frame")), "/sim/step no devolvió un cuadro válido")
    passed("manual", "reset y una acción de flecha completados")

    deep_link = f"{web_url}/run/{quote(evaluation_run, safe='')}"
    _, deep_html = get_text(deep_link, timeout=timeout)
    require("Robot Expedition" in deep_html, "el enlace directo del run no carga la aplicación")
    passed("deep-link", f"/run/{evaluation_run}")

    return {
        "schema": "robot-expedition-production-smoke/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "pass",
        "web_url": web_url,
        "api_url": api_url,
        "checks": checks,
        "production": {
            "web_asset": asset_url,
            "api_version": version.get("api_version"),
            "git_commit": version.get("git_commit"),
            "release": version.get("release"),
            "served_version": version.get("served_version"),
            "environment_version": version.get("environment_version"),
            "recommended_run_id": version.get("recommended_run_id"),
            "catalog_runs": len(runs),
            "evaluated_run_id": evaluation_run,
            "evaluation_frames": len(frames),
            "evaluation_success_rate": metrics.get("success_rate"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-url", default=DEFAULT_WEB_URL)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--timeout", type=float, default=180.0, help="segundos por solicitud")
    parser.add_argument("--output", type=Path, help="ruta opcional para la evidencia JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        evidence = run_smoke(args.web_url, args.api_url, args.timeout)
    except SmokeFailure as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Evidencia: {args.output}")
    print(f"PASS  integración de producción ({len(evidence['checks'])} comprobaciones)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
