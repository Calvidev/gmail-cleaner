"""Cliente de la API de Sleeper.

La API de lectura de Sleeper es pública y no pide autenticación, así que la
herramienta funciona desde el primer arranque. Cuando pases tu usuario o el id
de tu liga, se activan además las funciones personalizadas (roster, waivers).

Endpoints usados:
  GET /state/nfl                                  -> temporada y semana actual
  GET /players/nfl                                -> catálogo completo (~5 MB)
  GET /players/nfl/trending/{add|drop}            -> altas/bajas recientes
  GET /stats/nfl/{type}/{season}[/{week}]         -> estadísticas (temporada o semana)
  GET /projections/nfl/{type}/{season}[/{week}]   -> proyecciones
  GET /user/{username}                            -> perfil (necesita usuario)
  GET /league/{league_id}                         -> liga (necesita id de liga)
  GET /league/{league_id}/rosters                 -> rosters de la liga
  GET /league/{league_id}/users                   -> managers de la liga
"""

from __future__ import annotations

from typing import Any

import httpx

from app.cache import TTLCache
from app.config import Settings
from app.models import Player

HEADSHOT_URL = "https://sleepercdn.com/content/nfl/players/thumb/{player_id}.jpg"
TEAM_LOGO_URL = "https://sleepercdn.com/images/team_logos/nfl/{team}.png"


class SleeperError(RuntimeError):
    """Fallo al hablar con la API de Sleeper."""


class SleeperClient:
    """Acceso cacheado a la API de Sleeper."""

    def __init__(
        self,
        settings: Settings,
        cache: TTLCache,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self._client = client
        self._owns_client = client is None

    # -- infraestructura -----------------------------------------------------

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"User-Agent": self.settings.user_agent}
            if self.settings.sleeper_api_key:
                # Hoy no hace falta, pero si algún día usas un endpoint
                # autenticado o un proveedor de pago, la llave viaja aquí.
                headers["Authorization"] = f"Bearer {self.settings.sleeper_api_key}"
            self._client = httpx.AsyncClient(
                timeout=self.settings.http_timeout,
                headers=headers,
                follow_redirects=True,
            )
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str) -> Any:
        url = f"{self.settings.sleeper_base_url}{path}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise SleeperError(
                f"Sleeper devolvió {exc.response.status_code} en {path}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SleeperError(f"No se pudo conectar con Sleeper ({path}): {exc}") from exc
        except ValueError as exc:
            raise SleeperError(f"Sleeper devolvió una respuesta no válida en {path}") from exc

    # -- estado de la temporada ---------------------------------------------

    async def get_state(self) -> dict[str, Any]:
        """Temporada, semana y tipo de temporada en curso."""
        return await self.cache.get_or_set(
            "sleeper:state",
            self.settings.cache_ttl_state,
            lambda: self._get("/state/nfl"),
        )

    async def current_season(self) -> str:
        if self.settings.sleeper_season:
            return self.settings.sleeper_season
        try:
            state = await self.get_state()
        except SleeperError:
            from datetime import date

            today = date.today()
            # La temporada NFL arranca en septiembre: antes de marzo seguimos
            # hablando de la temporada del año anterior.
            return str(today.year if today.month >= 3 else today.year - 1)
        return str(state.get("season") or state.get("league_season") or "")

    async def current_week(self) -> int | None:
        try:
            state = await self.get_state()
        except SleeperError:
            return None
        week = state.get("week") or state.get("display_week")
        return int(week) if week else None

    # -- catálogo de jugadores ----------------------------------------------

    async def get_players_raw(self) -> dict[str, Any]:
        """Catálogo completo tal cual lo devuelve Sleeper (cacheado en disco)."""
        return await self.cache.get_or_set(
            "sleeper:players",
            self.settings.cache_ttl_players,
            lambda: self._get("/players/nfl"),
            use_disk=True,
        )

    async def get_players(self) -> dict[str, Player]:
        """Catálogo normalizado a objetos `Player`, solo posiciones de fantasy."""
        raw = await self.get_players_raw()
        return parse_players(raw)

    # -- tendencias ----------------------------------------------------------

    async def get_trending(
        self, kind: str = "add", *, lookback_hours: int = 24, limit: int = 200
    ) -> dict[str, int]:
        """Jugadores más añadidos (o cortados) en las últimas horas."""
        if kind not in ("add", "drop"):
            raise ValueError("kind debe ser 'add' o 'drop'")
        key = f"sleeper:trending:{kind}:{lookback_hours}:{limit}"
        path = (
            f"/players/nfl/trending/{kind}"
            f"?lookback_hours={lookback_hours}&limit={limit}"
        )
        try:
            data = await self.cache.get_or_set(
                key, self.settings.cache_ttl_trending, lambda: self._get(path)
            )
        except SleeperError:
            return {}
        return parse_trending(data)

    # -- estadísticas y proyecciones ----------------------------------------

    async def get_season_stats(self, season: str | None = None) -> dict[str, dict[str, Any]]:
        """Estadísticas acumuladas de la temporada, por `player_id`."""
        season = season or await self.current_season()
        if not season:
            return {}
        season_type = self.settings.sleeper_season_type
        key = f"sleeper:stats:{season_type}:{season}"
        path = f"/stats/nfl/{season_type}/{season}"
        try:
            data = await self.cache.get_or_set(
                key, self.settings.cache_ttl_stats, lambda: self._get(path), use_disk=True
            )
        except SleeperError:
            return {}
        return data if isinstance(data, dict) else {}

    async def get_week_stats(
        self, season: str, week: int
    ) -> dict[str, dict[str, Any]]:
        """Estadísticas de UNA jornada, por `player_id`.

        Es la base de las tendencias: comparando semanas se ve si a un jugador
        le están dando más balón antes de que eso aparezca en los puntos.
        """
        season_type = self.settings.sleeper_season_type
        key = f"sleeper:stats:{season_type}:{season}:w{week}"
        path = f"/stats/nfl/{season_type}/{season}/{week}"
        try:
            data = await self.cache.get_or_set(
                key,
                # Una jornada cerrada ya no cambia: se puede cachear mucho más.
                self.settings.cache_ttl_week_stats,
                lambda: self._get(path),
                use_disk=True,
            )
        except SleeperError:
            return {}
        return data if isinstance(data, dict) else {}

    async def get_recent_weeks(
        self, season: str, until_week: int, count: int = 6
    ) -> dict[int, dict[str, dict[str, Any]]]:
        """Las últimas `count` jornadas disponibles, descargadas en paralelo."""
        import asyncio

        weeks = [w for w in range(max(1, until_week - count + 1), until_week + 1)]
        if not weeks:
            return {}
        results = await asyncio.gather(
            *(self.get_week_stats(season, w) for w in weeks), return_exceptions=True
        )
        return {
            week: result
            for week, result in zip(weeks, results)
            if isinstance(result, dict) and result
        }

    async def get_season_projections(
        self, season: str | None = None
    ) -> dict[str, dict[str, Any]]:
        """Proyecciones de la temporada, por `player_id`."""
        season = season or await self.current_season()
        if not season:
            return {}
        season_type = self.settings.sleeper_season_type
        key = f"sleeper:projections:{season_type}:{season}"
        path = f"/projections/nfl/{season_type}/{season}"
        try:
            data = await self.cache.get_or_set(
                key, self.settings.cache_ttl_stats, lambda: self._get(path), use_disk=True
            )
        except SleeperError:
            return {}
        return data if isinstance(data, dict) else {}

    # -- liga del usuario (requiere tus datos) -------------------------------

    async def get_user(self, username: str) -> dict[str, Any]:
        return await self.cache.get_or_set(
            f"sleeper:user:{username}",
            self.settings.cache_ttl_state,
            lambda: self._get(f"/user/{username}"),
        )

    async def resolve_user_id(self, username: str) -> str | None:
        """`user_id` a partir del nombre de usuario, o None si no se puede.

        Es la vía fiable para saber cuál de los equipos de la liga es el tuyo:
        el nombre que se ve en la liga (`display_name`) puede no coincidir con
        el del login, pero el `user_id` no falla.
        """
        if not username:
            return None
        try:
            user = await self.get_user(username)
        except SleeperError:
            return None
        user_id = (user or {}).get("user_id")
        return str(user_id) if user_id else None

    async def get_league(self, league_id: str) -> dict[str, Any]:
        return await self.cache.get_or_set(
            f"sleeper:league:{league_id}",
            self.settings.cache_ttl_state,
            lambda: self._get(f"/league/{league_id}"),
        )

    async def get_league_rosters(self, league_id: str) -> list[dict[str, Any]]:
        return await self.cache.get_or_set(
            f"sleeper:league:{league_id}:rosters",
            self.settings.cache_ttl_trending,
            lambda: self._get(f"/league/{league_id}/rosters"),
        )

    async def get_league_users(self, league_id: str) -> list[dict[str, Any]]:
        return await self.cache.get_or_set(
            f"sleeper:league:{league_id}:users",
            self.settings.cache_ttl_state,
            lambda: self._get(f"/league/{league_id}/users"),
        )

    async def get_rostered_player_ids(self, league_id: str) -> set[str]:
        """Ids de jugadores ya ocupados en la liga (para filtrar agentes libres)."""
        try:
            rosters = await self.get_league_rosters(league_id)
        except SleeperError:
            return set()
        owned: set[str] = set()
        for roster in rosters or []:
            for pid in roster.get("players") or []:
                owned.add(str(pid))
        return owned


# -- funciones puras de parseo (fáciles de testear) --------------------------


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_player(player_id: str, raw: dict[str, Any]) -> Player:
    """Convierte una entrada del catálogo de Sleeper en un `Player`."""
    first = raw.get("first_name") or ""
    last = raw.get("last_name") or ""
    name = (raw.get("full_name") or f"{first} {last}").strip()
    position = raw.get("position")
    team = raw.get("team")

    # Las defensas vienen sin nombre completo: el id es la abreviatura del equipo.
    if not name and position == "DEF":
        name = f"{team or player_id} D/ST"
    if not name:
        name = player_id

    headshot = None
    if position == "DEF" and team:
        headshot = TEAM_LOGO_URL.format(team=team.lower())
    elif player_id.isdigit():
        headshot = HEADSHOT_URL.format(player_id=player_id)

    return Player(
        player_id=str(player_id),
        name=name,
        first_name=first or None,
        last_name=last or None,
        position=position,
        fantasy_positions=list(raw.get("fantasy_positions") or []),
        team=team,
        number=_to_int(raw.get("number")),
        age=_to_int(raw.get("age")),
        years_exp=_to_int(raw.get("years_exp")),
        height=raw.get("height"),
        weight=raw.get("weight"),
        college=raw.get("college"),
        status=raw.get("status"),
        injury_status=raw.get("injury_status"),
        injury_body_part=raw.get("injury_body_part"),
        injury_notes=raw.get("injury_notes"),
        depth_chart_position=raw.get("depth_chart_position"),
        depth_chart_order=_to_int(raw.get("depth_chart_order")),
        search_rank=_to_int(raw.get("search_rank")),
        espn_id=str(raw["espn_id"]) if raw.get("espn_id") else None,
        yahoo_id=str(raw["yahoo_id"]) if raw.get("yahoo_id") else None,
        sportradar_id=raw.get("sportradar_id"),
        headshot_url=headshot,
    )


def parse_players(raw: dict[str, Any]) -> dict[str, Player]:
    """Normaliza el catálogo completo y descarta lo que no sirve para fantasy."""
    players: dict[str, Player] = {}
    for player_id, entry in (raw or {}).items():
        if not isinstance(entry, dict):
            continue
        player = parse_player(str(player_id), entry)
        if not player.is_fantasy_relevant:
            continue
        players[player.player_id] = player
    return players


def parse_trending(data: Any) -> dict[str, int]:
    """`[{'player_id': '123', 'count': 4000}]` -> `{'123': 4000}`."""
    result: dict[str, int] = {}
    for entry in data or []:
        if not isinstance(entry, dict):
            continue
        pid = entry.get("player_id")
        if pid is None:
            continue
        result[str(pid)] = _to_int(entry.get("count")) or 0
    return result
