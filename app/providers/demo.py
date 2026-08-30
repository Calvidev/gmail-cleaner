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
import re
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
            # /v1/stats/nfl/regular/2025/7 -> estadísticas de esa jornada
            match = re.search(r"/stats/\w+/\w+/\d{4}/(\d+)$", path)
            if match:
                archivo = DEMO_DIR / f"stats_week_{match.group(1)}.json"
                if archivo.exists():
                    return httpx.Response(200, json=json.loads(archivo.read_text()))
                return httpx.Response(404, json={"error": "jornada sin datos"})
            return httpx.Response(200, json=_load_json("stats.json"))
        if path.startswith("/v1/projections/"):
            return httpx.Response(200, json=_load_json("projections.json"))
        if path.startswith("/v1/league/"):
            if path.endswith("/rosters"):
                return httpx.Response(200, json=_load_json("league_rosters.json"))
            if path.endswith("/users"):
                return httpx.Response(200, json=_load_json("league_users.json"))
            return httpx.Response(200, json=_load_json("league.json"))
        if path.startswith("/v1/user/"):
            return httpx.Response(200, json=_load_json("user.json"))
        return httpx.Response(404, json={"error": "no disponible en modo demo"})

    if host == "site.api.espn.com":
        if "scoreboard" in path:
            return httpx.Response(200, json=_load_json("odds_scoreboard.json"))
        return httpx.Response(200, json=_load_json("news_espn.json"))

    if host == "api.the-odds-api.com":
        # El modo demo no simula The Odds API: sin llave no se usa.
        return httpx.Response(401, json={"message": "sin llave en modo demo"})

    # Cualquier otro feed RSS recibe el mismo archivo de ejemplo.
    return httpx.Response(
        200,
        content=(DEMO_DIR / "news_rss.xml").read_bytes(),
        headers={"Content-Type": "application/rss+xml"},
    )


def demo_transport() -> httpx.MockTransport:
    """Transporte httpx que responde con los archivos de `data/demo`."""
    return httpx.MockTransport(demo_handler)
