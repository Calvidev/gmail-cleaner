"""Fixtures compartidas. Todo se ejecuta contra los datos de `data/demo`."""

from __future__ import annotations

import httpx
import pytest

from app.cache import TTLCache
from app.config import Settings
from app.models import Player
from app.providers.demo import demo_transport
from app.providers.news import NewsProvider
from app.providers.sleeper import SleeperClient
from app.service import FantasyService


@pytest.fixture
def settings() -> Settings:
    return Settings(fantasy_demo=True, sleeper_league_id=None, sleeper_username=None)


@pytest.fixture
def cache() -> TTLCache:
    # Sin directorio: caché solo en memoria, sin tocar el disco en los tests.
    return TTLCache(None)


@pytest.fixture
def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=demo_transport(), follow_redirects=True)


@pytest.fixture
def sleeper(settings, cache, http_client) -> SleeperClient:
    return SleeperClient(settings, cache, http_client)


@pytest.fixture
def news_provider(settings, cache, http_client) -> NewsProvider:
    return NewsProvider(settings, cache, http_client)


@pytest.fixture
def service(settings, cache, sleeper, news_provider) -> FantasyService:
    return FantasyService(settings=settings, cache=cache, sleeper=sleeper, news=news_provider)


@pytest.fixture
def sample_players() -> dict[str, Player]:
    """Un puñado de jugadores hechos a mano, con casos límite."""
    return {
        "1": Player(
            player_id="1", name="Ja'Marr Chase", first_name="Ja'Marr", last_name="Chase",
            position="WR", fantasy_positions=["WR"], team="CIN", age=25, years_exp=4,
            depth_chart_order=1, search_rank=1, status="Active",
        ),
        "2": Player(
            player_id="2", name="Amon-Ra St. Brown", first_name="Amon-Ra", last_name="St. Brown",
            position="WR", fantasy_positions=["WR"], team="DET", age=26, years_exp=4,
            depth_chart_order=1, search_rank=6, status="Active",
        ),
        "3": Player(
            player_id="3", name="Patrick Mahomes", first_name="Patrick", last_name="Mahomes",
            position="QB", fantasy_positions=["QB"], team="KC", age=29, years_exp=8,
            depth_chart_order=1, search_rank=22, status="Active", espn_id="3139477",
        ),
        "4": Player(
            player_id="4", name="Lesionado Grave", first_name="Lesionado", last_name="Grave",
            position="RB", fantasy_positions=["RB"], team="DAL", age=25, years_exp=3,
            depth_chart_order=1, search_rank=8, status="Active", injury_status="IR",
        ),
        "5": Player(
            player_id="5", name="Suplente Profundo", first_name="Suplente", last_name="Profundo",
            position="RB", fantasy_positions=["RB"], team="NYJ", age=29, years_exp=6,
            depth_chart_order=4, search_rank=420, status="Active",
        ),
        "6": Player(
            player_id="6", name="Sin Equipo", first_name="Sin", last_name="Equipo",
            position="WR", fantasy_positions=["WR"], team=None, age=32, years_exp=10,
            search_rank=700, status="Inactive",
        ),
    }


DEMO_LEAGUE_ID = "999888777666555444"
DEMO_USER_ID = "100001"  # el equipo "Los Fantasmas" de la liga de ejemplo


@pytest.fixture
def league_settings() -> Settings:
    """Ajustes con la liga de ejemplo ya conectada."""
    return Settings(
        fantasy_demo=True,
        sleeper_league_id=DEMO_LEAGUE_ID,
        sleeper_user_id=DEMO_USER_ID,
        sleeper_username="calvidev",
    )


@pytest.fixture
def league_service(league_settings, cache, http_client) -> FantasyService:
    from app.providers.odds import OddsProvider

    return FantasyService(
        settings=league_settings,
        cache=cache,
        sleeper=SleeperClient(league_settings, cache, http_client),
        news=NewsProvider(league_settings, cache, http_client),
        odds=OddsProvider(league_settings, cache, http_client),
    )


@pytest.fixture
def odds_provider(settings, cache, http_client):
    from app.providers.odds import OddsProvider

    return OddsProvider(settings, cache, http_client)
