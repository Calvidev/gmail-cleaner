"""Capa de servicio: junta Sleeper, noticias y ranking.

Los endpoints hablan solo con esta clase, así que la lógica se puede probar sin
levantar el servidor.
"""

from __future__ import annotations

import asyncio

import httpx

from app.cache import TTLCache
from app.config import Settings, get_settings
from app.models import FANTASY_POSITIONS, Meta, NewsItem, Player, RankedPlayer
from app.providers.news import NewsProvider
from app.providers.sleeper import SleeperClient, SleeperError
from app.ranking import primary_position, rank_players


class FantasyService:
    """Fachada única para todo lo que necesita la interfaz."""

    def __init__(
        self,
        settings: Settings | None = None,
        cache: TTLCache | None = None,
        sleeper: SleeperClient | None = None,
        news: NewsProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.cache = cache or TTLCache(self.settings.cache_dir)
        self.sleeper = sleeper or SleeperClient(self.settings, self.cache)
        self.news = news or NewsProvider(self.settings, self.cache)
        self._shared_client: httpx.AsyncClient | None = None
        self._ranking_cache: dict[str, list[RankedPlayer]] = {}
        self._ranking_lock = asyncio.Lock()
        self.warnings: list[str] = []

    async def aclose(self) -> None:
        await asyncio.gather(
            self.sleeper.aclose(), self.news.aclose(), return_exceptions=True
        )
        if self._shared_client is not None:
            await self._shared_client.aclose()
            self._shared_client = None

    # -- jugadores -----------------------------------------------------------

    async def get_players(self) -> dict[str, Player]:
        try:
            return await self.sleeper.get_players()
        except SleeperError as exc:
            raise ServiceUnavailable(
                "No se pudo obtener el catálogo de jugadores de Sleeper. "
                f"Detalle: {exc}"
            ) from exc

    # -- ranking -------------------------------------------------------------

    def _ranking_key(self, scoring: str, superflex: bool) -> str:
        return f"ranking:{scoring}:{int(superflex)}"

    async def get_ranking(
        self, scoring: str = "ppr", superflex: bool = False
    ) -> list[RankedPlayer]:
        """Ranking completo (cacheado por formato de puntuación)."""
        key = self._ranking_key(scoring, superflex)
        cached = self.cache.get(key, self.settings.cache_ttl_trending)
        if cached is not None and key in self._ranking_cache:
            return self._ranking_cache[key]

        async with self._ranking_lock:
            cached = self.cache.get(key, self.settings.cache_ttl_trending)
            if cached is not None and key in self._ranking_cache:
                return self._ranking_cache[key]

            players = await self.get_players()
            season = await self.sleeper.current_season()

            stats, projections, adds, drops = await asyncio.gather(
                self.sleeper.get_season_stats(season),
                self.sleeper.get_season_projections(season),
                self.sleeper.get_trending("add"),
                self.sleeper.get_trending("drop"),
            )

            ranked = rank_players(
                players,
                stats=stats,
                projections=projections,
                trending_add=adds,
                trending_drop=drops,
                scoring=scoring,
                superflex=superflex,
            )
            self._ranking_cache[key] = ranked
            self.cache.set(key, True)
            return ranked

    async def get_ranked_player(
        self, player_id: str, scoring: str = "ppr", superflex: bool = False
    ) -> RankedPlayer | None:
        ranked = await self.get_ranking(scoring, superflex)
        for entry in ranked:
            if entry.player.player_id == player_id:
                return entry
        return None

    # -- noticias ------------------------------------------------------------

    async def get_news(self, limit: int = 60) -> list[NewsItem]:
        players = await self.get_players()
        items = await self.news.get_news(players)
        return items[:limit]

    async def get_player_news(self, player_id: str, limit: int = 20) -> list[NewsItem]:
        players = await self.get_players()
        return await self.news.get_player_news(player_id, players, limit=limit)

    # -- liga del usuario ----------------------------------------------------

    async def get_rostered_ids(self) -> set[str] | None:
        """Jugadores ya ocupados en tu liga (None si aún no la has configurado)."""
        league_id = self.settings.sleeper_league_id
        if not league_id:
            return None
        return await self.sleeper.get_rostered_player_ids(league_id)

    async def get_league_info(self) -> dict:
        league_id = self.settings.sleeper_league_id
        if not league_id:
            raise LeagueNotConfigured(
                "Falta SLEEPER_LEAGUE_ID en el archivo .env. "
                "Añade el id de tu liga de Sleeper para activar esta sección."
            )
        league, rosters, users = await asyncio.gather(
            self.sleeper.get_league(league_id),
            self.sleeper.get_league_rosters(league_id),
            self.sleeper.get_league_users(league_id),
        )
        return {"league": league, "rosters": rosters, "users": users}

    # -- metadatos -----------------------------------------------------------

    async def get_meta(self) -> Meta:
        warnings: list[str] = []
        players: dict[str, Player] = {}
        try:
            players = await self.get_players()
        except ServiceUnavailable as exc:
            warnings.append(str(exc))

        teams = sorted({p.team for p in players.values() if p.team})
        positions = sorted(
            {primary_position(p) for p in players.values() if primary_position(p) != "UNK"}
        )

        season = None
        week = None
        try:
            season = await self.sleeper.current_season()
            week = await self.sleeper.current_week()
        except SleeperError as exc:
            warnings.append(f"No se pudo leer el estado de la temporada: {exc}")

        if not self.settings.league_configured:
            warnings.append(
                "Liga de Sleeper sin configurar: añade SLEEPER_LEAGUE_ID (y opcionalmente "
                "SLEEPER_USERNAME) en .env para ver agentes libres y tu roster."
            )
        if self.news.last_errors:
            warnings.extend(f"Fuente de noticias caída — {e}" for e in self.news.last_errors)

        return Meta(
            season=season,
            season_type=self.settings.sleeper_season_type,
            week=week,
            positions=positions or list(FANTASY_POSITIONS),
            teams=teams,
            league_configured=self.settings.league_configured,
            league_id=self.settings.sleeper_league_id,
            player_count=len(players),
            news_sources=["ESPN"] + [u for u in self.settings.news_feeds],
            warnings=warnings,
        )

    # -- mantenimiento -------------------------------------------------------

    def refresh(self) -> None:
        """Vacía las cachés para forzar una descarga nueva."""
        self.cache.invalidate()
        self._ranking_cache.clear()


class ServiceUnavailable(RuntimeError):
    """No hay datos disponibles ahora mismo (red caída, API fuera)."""


class LeagueNotConfigured(RuntimeError):
    """Hace falta el id de liga de Sleeper para esta función."""


def build_service(settings: Settings | None = None) -> FantasyService:
    settings = settings or get_settings()
    # En modo demo la caché va solo en memoria: no queremos mezclar datos de
    # ejemplo con los reales en el disco.
    cache = TTLCache(None if settings.fantasy_demo else settings.cache_dir)

    transport = None
    if settings.fantasy_demo:
        from app.providers.demo import demo_transport

        transport = demo_transport()

    client = httpx.AsyncClient(
        timeout=settings.http_timeout,
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
        transport=transport,
    )
    service = FantasyService(
        settings=settings,
        cache=cache,
        sleeper=SleeperClient(settings, cache, client),
        news=NewsProvider(settings, cache, client),
    )
    # Sleeper y las noticias comparten un solo cliente HTTP; lo cierra el servicio.
    service._shared_client = client
    return service
