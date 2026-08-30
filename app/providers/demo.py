"""Modo demo: sirve datos locales como si vinieran de Sleeper y de ESPN.

Sirve para dos cosas:

* Probar la interfaz sin conexión (o cuando la red del entorno bloquea las
  APIs), arrancando con `FANTASY_DEMO=1`.
* Ejecutar los tests sobre el mismo camino de código que usa producción.

Los datos de `data/demo/` son **inventados**: nombres reales de la NFL con
estadísticas y noticias de ejemplo. No sirven para tomar decisiones.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from app.config import ROOT_DIR

DEMO_DIR: Path = ROOT_DIR / "data" / "demo"


def _load_json(name: str):
    return json.loads((DEMO_DIR / name).read_text(encoding="utf-8"))


def demo_handler(request: httpx.Request) -> httpx.Response:
    """Enruta una petición a su archivo de ejemplo."""
    path = request.url.path
    host = request.url.host

    if host == "api.sleeper.app":
        if path.endswith("/state/nfl"):
            return httpx.Response(200, json=_load_json("state.json"))
        if path.endswith("/players/nfl"):
            return httpx.Response(200, json=_load_json("players.json"))
        if "/trending/add" in path:
            return httpx.Response(200, json=_load_json("trending_add.json"))
        if "/trending/drop" in path:
            return httpx.Response(200, json=_load_json("trending_drop.json"))
        if path.startswith("/v1/stats/"):
            return httpx.Response(200, json=_load_json("stats.json"))
        if path.startswith("/v1/projections/"):
            return httpx.Response(200, json=_load_json("projections.json"))
        # Ligas y usuarios no están en el modo demo.
        return httpx.Response(404, json={"error": "no disponible en modo demo"})

    if host == "site.api.espn.com":
        return httpx.Response(200, json=_load_json("news_espn.json"))

    # Cualquier otro feed RSS recibe el mismo archivo de ejemplo.
    return httpx.Response(
        200,
        content=(DEMO_DIR / "news_rss.xml").read_bytes(),
        headers={"Content-Type": "application/rss+xml"},
    )


def demo_transport() -> httpx.MockTransport:
    """Transporte httpx que responde con los archivos de `data/demo`."""
    return httpx.MockTransport(demo_handler)
