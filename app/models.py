"""Modelos de datos compartidos por toda la aplicación."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# Posiciones que interesan en fantasy.
FANTASY_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")


class Player(BaseModel):
    """Un jugador de la NFL, normalizado desde el catálogo de Sleeper."""

    player_id: str
    name: str
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = None
    fantasy_positions: list[str] = Field(default_factory=list)
    team: str | None = None
    number: int | None = None
    age: int | None = None
    years_exp: int | None = None
    height: str | None = None
    weight: str | None = None
    college: str | None = None
    status: str | None = None  # Active, Inactive, Injured Reserve...
    injury_status: str | None = None  # Questionable, Out, IR, Doubtful...
    injury_body_part: str | None = None
    injury_notes: str | None = None
    depth_chart_position: str | None = None
    depth_chart_order: int | None = None
    search_rank: int | None = None  # ranking de consenso de Sleeper (menor = mejor)
    espn_id: str | None = None
    yahoo_id: str | None = None
    sportradar_id: str | None = None
    headshot_url: str | None = None

    @property
    def is_fantasy_relevant(self) -> bool:
        positions = set(self.fantasy_positions) | ({self.position} if self.position else set())
        return bool(positions & set(FANTASY_POSITIONS))


class ScoreBreakdown(BaseModel):
    """Desglose de la nota de un jugador, para que el ranking sea explicable."""

    consensus: float = 0.0
    opportunity: float = 0.0
    production: float = 0.0
    momentum: float = 0.0
    availability: float = 0.0
    age_curve: float = 0.0

    def total_components(self) -> dict[str, float]:
        return self.model_dump()


class RankedPlayer(BaseModel):
    """Un jugador con su puntuación y su posición en el ranking."""

    rank: int
    position_rank: int | None = None
    tier: int | None = None
    score: float
    player: Player
    breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    reasons: list[str] = Field(default_factory=list)
    trend_adds: int | None = None
    trend_drops: int | None = None
    points: float | None = None  # puntos fantasy de la temporada, si hay datos
    points_per_game: float | None = None
    games: int | None = None
    projected_points: float | None = None


class NewsItem(BaseModel):
    """Una noticia normalizada, venga de la API de ESPN o de un RSS."""

    id: str
    title: str
    summary: str | None = None
    url: str | None = None
    source: str
    published: datetime | None = None
    image_url: str | None = None
    player_ids: list[str] = Field(default_factory=list)
    player_names: list[str] = Field(default_factory=list)


class RankingResponse(BaseModel):
    """Respuesta del endpoint de ranking."""

    season: str | None = None
    week: int | None = None
    scoring: str = "ppr"
    total: int
    count: int
    offset: int = 0
    generated_at: datetime
    players: list[RankedPlayer]


class PlayerDetail(BaseModel):
    """Ficha completa de un jugador: ranking + noticias."""

    ranked: RankedPlayer
    news: list[NewsItem] = Field(default_factory=list)


class Meta(BaseModel):
    """Metadatos para que la interfaz pinte filtros y avisos."""

    season: str | None = None
    season_type: str | None = None
    week: int | None = None
    positions: list[str] = list(FANTASY_POSITIONS)
    teams: list[str] = Field(default_factory=list)
    scoring_formats: list[str] = ["ppr", "half_ppr", "standard"]
    league_configured: bool = False
    league_id: str | None = None
    player_count: int = 0
    news_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
