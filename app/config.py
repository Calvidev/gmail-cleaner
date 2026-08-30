"""Configuración de Fantasy Tool.

Todo se lee de variables de entorno (o de un archivo `.env` en la raíz).
Copia `.env.example` a `.env` y ajusta lo que necesites.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Ajustes de la aplicación."""

    # Se leen dos archivos, en este orden:
    #   .env.defaults  valores versionados y no secretos (la liga, por ejemplo)
    #   .env           tus llaves y tus cambios; manda sobre el anterior
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env.defaults"), str(ROOT_DIR / ".env")),
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # --- Servidor ---
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # Modo demo: usa los datos de `data/demo/` en vez de salir a internet.
    # Útil para probar la interfaz sin conexión (FANTASY_DEMO=1).
    fantasy_demo: bool = False

    # --- Sleeper (API pública: no requiere llave para lectura) ---
    sleeper_base_url: str = "https://api.sleeper.app/v1"
    sleeper_season: str | None = None  # None => se detecta con /state/nfl
    sleeper_season_type: str = "regular"

    # --- Sleeper: datos de tu liga (los rellenas cuando me pases tus datos) ---
    sleeper_username: str | None = None
    sleeper_user_id: str | None = None
    sleeper_league_id: str | None = None
    # Hueco para una llave/token si algún día usas un endpoint autenticado
    # o un proveedor de datos de pago. Hoy la API de lectura de Sleeper es abierta.
    sleeper_api_key: str | None = None

    # --- Noticias ---
    espn_news_url: str = (
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news"
    )
    news_feeds: list[str] = Field(
        default_factory=lambda: [
            "https://www.espn.com/espn/rss/nfl/news",
            "https://api.foxsports.com/v1/rss?partnerKey=zBaFxRyGKCfxBagJG9b8pqLyndmvo7UU&tag=nfl",
            "https://www.cbssports.com/rss/headlines/nfl/",
            "https://sports.yahoo.com/nfl/rss.xml",
        ]
    )
    news_max_items: int = 200

    # --- Apuestas ---
    # ESPN da spread y total sin pedir llave: es la fuente por defecto.
    espn_scoreboard_url: str = (
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    )
    # The Odds API (opcional, tiene plan gratuito): añade props de jugador.
    # Consigue una llave en https://the-odds-api.com y ponla en .env
    odds_api_key: str | None = None
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"

    # --- Caché ---
    cache_dir: Path = ROOT_DIR / ".cache"
    cache_ttl_players: int = 60 * 60 * 12  # catálogo de jugadores: 12 h
    cache_ttl_trending: int = 60 * 15  # tendencias: 15 min
    cache_ttl_news: int = 60 * 10  # noticias: 10 min
    cache_ttl_stats: int = 60 * 60 * 3  # stats/proyecciones: 3 h
    cache_ttl_week_stats: int = 60 * 60 * 6  # jornadas cerradas: 6 h
    cache_ttl_state: int = 60 * 30  # estado de la temporada: 30 min
    cache_ttl_odds: int = 60 * 20  # cuotas: 20 min
    cache_ttl_draft: int = 60 * 5  # configuración del draft: 5 min
    cache_ttl_draft_picks: int = 10  # picks en vivo: 10 s

    # --- Red ---
    http_timeout: float = 20.0
    user_agent: str = "FantasyTool/0.1 (+https://github.com/Calvidev/fantasy-tool)"

    @property
    def league_configured(self) -> bool:
        """True cuando ya hay datos de liga para las funciones personalizadas."""
        return bool(self.sleeper_league_id or self.sleeper_username or self.sleeper_user_id)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Settings cacheados (una sola instancia por proceso)."""
    return Settings()
