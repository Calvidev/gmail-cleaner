"""Capa de servicio: junta Sleeper, noticias y ranking.

Los endpoints hablan solo con esta clase, así que la lógica se puede probar sin
levantar el servidor.
"""

from __future__ import annotations

import asyncio

import httpx

from app.cache import TTLCache
from app.config import Settings, get_settings
from app.draft import build_board
from app.external_rankings import index_by_player, load_ranking_files
from app.league_analysis import analyze_league
from app.models import (
    FANTASY_POSITIONS,
    DraftBoard,
    ExternalRanking,
    GameOdds,
    LeagueAnalysis,
    Meta,
    NewsItem,
    Player,
    PlayerProp,
    PlayerTrend,
    RankedPlayer,
    TeamOdds,
)
from app.providers.news import NewsProvider
from app.providers.odds import OddsProvider
from app.providers.sleeper import SleeperClient, SleeperError
from app.trends import compute_trends
from app.ranking import primary_position, rank_players


class FantasyService:
    """Fachada única para todo lo que necesita la interfaz."""

    def __init__(
        self,
        settings: Settings | None = None,
        cache: TTLCache | None = None,
        sleeper: SleeperClient | None = None,
        news: NewsProvider | None = None,
        odds: OddsProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.cache = cache or TTLCache(self.settings.cache_dir)
        self.sleeper = sleeper or SleeperClient(self.settings, self.cache)
        self.news = news or NewsProvider(self.settings, self.cache)
        self.odds = odds or OddsProvider(self.settings, self.cache)
        self._shared_client: httpx.AsyncClient | None = None
        self._ranking_cache: dict[str, list[RankedPlayer]] = {}
        self._ranking_lock = asyncio.Lock()
        self._trends_cache: dict[str, list[PlayerTrend]] = {}
        self._trends_lock = asyncio.Lock()
        self._external: list[ExternalRanking] | None = None
        self.warnings: list[str] = []

    async def aclose(self) -> None:
        await asyncio.gather(
            self.sleeper.aclose(),
            self.news.aclose(),
            self.odds.aclose(),
            return_exceptions=True,
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

    # -- rankings importados de otras fuentes ---------------------------------

    async def get_external_rankings(self) -> list[ExternalRanking]:
        """Rankings de otros analistas, leídos de `data/rankings/`."""
        if self._external is None:
            players = await self.get_players()
            self._external = load_ranking_files(self.settings.rankings_dir, players)
        return self._external

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

            # Se cuelga de cada jugador su puesto en los rankings importados y
            # la diferencia con el nuestro, que es lo que hay que mirar.
            externos = index_by_player(await self.get_external_rankings())
            if externos:
                for entrada in ranked:
                    puestos = externos.get(entrada.player.player_id)
                    if not puestos:
                        continue
                    entrada.external_ranks = puestos
                    medio = sum(puestos.values()) / len(puestos)
                    entrada.external_delta = int(round(entrada.rank - medio))
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

    # -- tendencias ----------------------------------------------------------

    async def get_trends(
        self, scoring: str = "ppr", weeks: int = 6, superflex: bool = False
    ) -> list[PlayerTrend]:
        """Tendencia de cada jugador en las últimas jornadas."""
        weeks = max(3, min(weeks, 12))
        key = f"trends:{scoring}:{weeks}:{int(superflex)}"
        if key in self._trends_cache and self.cache.get(key, self.settings.cache_ttl_week_stats):
            return self._trends_cache[key]

        async with self._trends_lock:
            if key in self._trends_cache and self.cache.get(
                key, self.settings.cache_ttl_week_stats
            ):
                return self._trends_cache[key]

            players = await self.get_players()
            season = await self.sleeper.current_season()
            week = await self.sleeper.current_week() or 18

            weekly = await self.sleeper.get_recent_weeks(season, week, count=weeks)
            trends = compute_trends(players, weekly, scoring=scoring)

            # Se cuelga el puesto y la nota del ranking, para poder ordenar por
            # "sube y además es bueno".
            ranked = {r.player.player_id: r for r in await self.get_ranking(scoring, superflex)}
            for trend in trends:
                entry = ranked.get(trend.player.player_id)
                if entry is not None:
                    trend.rank = entry.rank
                    trend.score = entry.score

            self._trends_cache[key] = trends
            self.cache.set(key, True)
            return trends

    async def get_player_trend(
        self, player_id: str, scoring: str = "ppr", weeks: int = 6
    ) -> PlayerTrend | None:
        for trend in await self.get_trends(scoring, weeks):
            if trend.player.player_id == player_id:
                return trend
        return None

    # -- apuestas ------------------------------------------------------------

    async def get_odds_games(self, week: int | None = None) -> list[GameOdds]:
        if week is None:
            week = await self.sleeper.current_week()
        return await self.odds.get_games(week)

    async def get_team_odds(self, week: int | None = None) -> dict[str, TeamOdds]:
        if week is None:
            week = await self.sleeper.current_week()
        return await self.odds.get_team_odds(week)

    async def get_player_props(self, player_id: str) -> list[PlayerProp]:
        if not self.odds.has_api_key:
            return []
        players = await self.get_players()
        return (await self.odds.get_props(players)).get(player_id, [])

    # -- análisis de liga ----------------------------------------------------

    async def get_league_analysis(
        self, scoring: str = "ppr", superflex: bool = False, max_trade_ideas: int = 12
    ) -> LeagueAnalysis:
        """Compara tu equipo con el resto de la liga y propone intercambios."""
        info = await self.get_league_info()  # lanza LeagueNotConfigured si falta
        ranked = await self.get_ranking(scoring, superflex)

        # El id de usuario es la vía fiable para saber cuál es tu equipo. Si
        # solo hay nombre de usuario, se traduce a id preguntando a Sleeper; si
        # eso falla, `analyze_league` aún puede emparejarte por el nombre.
        my_user_id = self.settings.sleeper_user_id
        if not my_user_id and self.settings.sleeper_username:
            my_user_id = await self.sleeper.resolve_user_id(self.settings.sleeper_username)

        return analyze_league(
            info["league"],
            info["rosters"],
            info["users"],
            ranked,
            my_user_id=my_user_id,
            my_username=self.settings.sleeper_username,
            scoring=scoring,
            max_trade_ideas=max_trade_ideas,
        )

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
        try:
            league, rosters, users = await asyncio.gather(
                self.sleeper.get_league(league_id),
                self.sleeper.get_league_rosters(league_id),
                self.sleeper.get_league_users(league_id),
            )
        except SleeperError as exc:
            # Un 404 significa que ese id no existe; cualquier otro fallo es de
            # conexión. Merece la pena distinguirlo: el remedio no es el mismo.
            if "404" in str(exc):
                raise ServiceUnavailable(
                    f"Sleeper no encuentra la liga {league_id}. Comprueba el número: "
                    "es el que aparece en la URL de tu liga, en "
                    "sleeper.com/leagues/<NÚMERO>/team."
                ) from exc
            raise ServiceUnavailable(
                f"No se pudo consultar tu liga en Sleeper. Detalle: {exc}"
            ) from exc

        if not rosters:
            raise ServiceUnavailable(
                f"La liga {league_id} existe pero no tiene equipos todavía."
            )
        return {"league": league, "rosters": rosters, "users": users}

    # -- draft ---------------------------------------------------------------

    async def resolve_my_user_id(self) -> str | None:
        """Mi `user_id`, preguntándoselo a Sleeper si solo tengo el nombre."""
        if self.settings.sleeper_user_id:
            return self.settings.sleeper_user_id
        if self.settings.sleeper_username:
            return await self.sleeper.resolve_user_id(self.settings.sleeper_username)
        return None

    async def get_draft_board(
        self,
        scoring: str = "ppr",
        superflex: bool = False,
        draft_id: str | None = None,
    ) -> DraftBoard:
        """Tablero del draft: mejores disponibles, huecos y recomendación."""
        league_id = self.settings.sleeper_league_id
        if not draft_id and not league_id:
            raise LeagueNotConfigured(
                "Falta SLEEPER_LEAGUE_ID en el archivo .env para encontrar tu draft."
            )

        if not draft_id:
            drafts = await self.sleeper.get_league_drafts(league_id)
            if not drafts:
                raise ServiceUnavailable(
                    f"La liga {league_id} no tiene ningún draft creado todavía."
                )
            # El primero es el más reciente.
            draft_id = str(drafts[0].get("draft_id") or "")
            if not draft_id:
                raise ServiceUnavailable("Sleeper devolvió un draft sin identificador.")

        try:
            draft = await self.sleeper.get_draft(draft_id)
        except SleeperError as exc:
            raise ServiceUnavailable(
                f"No se pudo leer el draft {draft_id}. Detalle: {exc}"
            ) from exc

        picks = await self.sleeper.get_draft_picks(draft_id)
        ranked = await self.get_ranking(scoring, superflex)
        my_user_id = await self.resolve_my_user_id()

        # Los nombres de los mánagers y la alineación exacta salen de la liga,
        # pero son un extra: sin ellos el tablero funciona igual.
        users: list[dict] = []
        roster_positions = None
        if league_id:
            try:
                info = await self.get_league_info()
                users = info["users"]
                roster_positions = info["league"].get("roster_positions")
            except (ServiceUnavailable, LeagueNotConfigured):
                pass

        return build_board(
            draft,
            picks,
            ranked,
            users,
            my_user_id=my_user_id,
            league_roster_positions=roster_positions,
            scoring=scoring,
        )

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

        draft_status = None
        if self.settings.sleeper_league_id:
            try:
                drafts = await self.sleeper.get_league_drafts(self.settings.sleeper_league_id)
                if drafts:
                    draft_status = drafts[0].get("status")
            except SleeperError:
                draft_status = None

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
            draft_status=draft_status,
            player_count=len(players),
            news_sources=["ESPN"] + [u for u in self.settings.news_feeds],
            external_rankings=[r.source for r in await self.get_external_rankings()]
            if players
            else [],
            warnings=warnings,
        )

    # -- mantenimiento -------------------------------------------------------

    def refresh(self) -> None:
        """Vacía las cachés para forzar una descarga nueva."""
        self.cache.invalidate()
        self._ranking_cache.clear()
        self._trends_cache.clear()
        self._external = None


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
        odds=OddsProvider(settings, cache, client),
    )
    # Sleeper y las noticias comparten un solo cliente HTTP; lo cierra el servicio.
    service._shared_client = client
    return service
