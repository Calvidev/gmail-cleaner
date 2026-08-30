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
    """Ficha completa de un jugador: ranking, tendencia, mercado y noticias."""

    ranked: RankedPlayer
    news: list[NewsItem] = Field(default_factory=list)
    trend: "PlayerTrend | None" = None
    vegas: "TeamOdds | None" = None
    props: "list[PlayerProp]" = Field(default_factory=list)


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
    # "pre_draft", "drafting" o "complete": la interfaz cambia según esto.
    draft_status: str | None = None
    player_count: int = 0
    news_sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WeekUsage(BaseModel):
    """El uso que tuvo un jugador en una jornada concreta."""

    week: int
    snaps: int | None = None
    snap_share: float | None = None  # 0-1
    targets: int | None = None
    target_share: float | None = None  # 0-1
    carries: int | None = None
    receptions: int | None = None
    opportunities: int | None = None  # acarreos + objetivos: el volumen real
    yards: float | None = None
    touchdowns: float | None = None
    points: float | None = None


class MetricTrend(BaseModel):
    """Cómo evoluciona una métrica: media reciente contra la anterior."""

    metric: str
    label: str
    recent: float | None = None
    previous: float | None = None
    delta: float | None = None
    pct_change: float | None = None
    slope: float | None = None  # pendiente por jornada


class PlayerTrend(BaseModel):
    """Tendencia de un jugador jornada a jornada."""

    player: Player
    direction: str  # "alza", "baja", "estable" o "sin datos"
    trend_score: float  # de -100 (desplome) a +100 (despegue)
    weeks: list[WeekUsage] = Field(default_factory=list)
    metrics: dict[str, MetricTrend] = Field(default_factory=dict)
    signals: list[str] = Field(default_factory=list)
    games_tracked: int = 0
    # True cuando la tendencia se apoya en volumen (objetivos, snaps, acarreos)
    # y no solo en los puntos, que rebotan mucho de una jornada a otra.
    usage_based: bool = True
    rank: int | None = None
    score: float | None = None


class TrendsResponse(BaseModel):
    """Respuesta del endpoint de tendencias."""

    season: str | None = None
    week: int | None = None
    weeks_analyzed: list[int] = Field(default_factory=list)
    scoring: str = "ppr"
    total: int = 0
    generated_at: datetime
    players: list[PlayerTrend] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PositionStrength(BaseModel):
    """Cómo está un equipo en una posición, comparado con el resto de la liga."""

    position: str
    starters: list[RankedPlayer] = Field(default_factory=list)
    bench: list[RankedPlayer] = Field(default_factory=list)
    starter_score: float = 0.0  # suma de las notas de los titulares
    avg_score: float = 0.0
    league_avg: float = 0.0
    league_best: float = 0.0
    rank_in_league: int | None = None
    percentile: float = 0.0  # 0-100
    verdict: str = "medio"  # "débil", "medio" o "fuerte"
    gap_to_best: float = 0.0


class TeamAnalysis(BaseModel):
    """Radiografía de un equipo de la liga."""

    roster_id: int
    owner: str | None = None
    team_name: str | None = None
    is_me: bool = False
    total_score: float = 0.0  # valor de la alineación titular óptima
    rank_in_league: int | None = None
    positions: dict[str, PositionStrength] = Field(default_factory=dict)
    weaknesses: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    surplus: list[RankedPlayer] = Field(default_factory=list)
    lineup: list[RankedPlayer] = Field(default_factory=list)
    player_count: int = 0


class TradeIdea(BaseModel):
    """Un intercambio que mejora a las dos partes."""

    partner_roster_id: int
    partner_owner: str | None = None
    partner_team_name: str | None = None
    give: list[RankedPlayer] = Field(default_factory=list)
    get: list[RankedPlayer] = Field(default_factory=list)
    my_gain: float = 0.0  # cuánto sube mi alineación titular
    their_gain: float = 0.0  # cuánto sube la suya
    fairness: float = 0.0  # 0-100: cuanto más alto, más equilibrado
    rationale: list[str] = Field(default_factory=list)


class LeagueAnalysis(BaseModel):
    """Análisis completo de la liga."""

    league_id: str
    league_name: str | None = None
    season: str | None = None
    scoring: str = "ppr"
    roster_positions: list[str] = Field(default_factory=list)
    teams: list[TeamAnalysis] = Field(default_factory=list)
    me: TeamAnalysis | None = None
    trade_ideas: list[TradeIdea] = Field(default_factory=list)
    # True cuando la liga existe pero aún no se ha hecho el draft.
    pre_draft: bool = False
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class PlayerProp(BaseModel):
    """Una línea de apuesta sobre un jugador (yardas, recepciones, TD…)."""

    market: str  # p.ej. "player_reception_yds"
    label: str  # p.ej. "Yardas de recepción"
    line: float | None = None
    over_price: int | None = None
    under_price: int | None = None
    bookmaker: str | None = None


class TeamOdds(BaseModel):
    """Lo que las casas esperan de un equipo esta jornada."""

    team: str
    opponent: str | None = None
    is_home: bool | None = None
    spread: float | None = None  # negativo = favorito
    total: float | None = None  # puntos totales del partido
    implied_total: float | None = None  # puntos que se le suponen a este equipo
    implied_rank: int | None = None  # 1 = el ataque mejor visto de la jornada
    win_probability: float | None = None  # 0-1
    verdict: str | None = None
    kickoff: datetime | None = None
    source: str | None = None


class GameOdds(BaseModel):
    """Las cuotas de un partido."""

    game_id: str
    home: str
    away: str
    kickoff: datetime | None = None
    spread: float | None = None  # relativo al local: negativo = local favorito
    total: float | None = None
    home_implied: float | None = None
    away_implied: float | None = None
    favorite: str | None = None
    bookmaker: str | None = None
    source: str = "ESPN"


class OddsResponse(BaseModel):
    """Respuesta del endpoint de apuestas."""

    week: int | None = None
    season: str | None = None
    games: list[GameOdds] = Field(default_factory=list)
    teams: list[TeamOdds] = Field(default_factory=list)
    props_available: bool = False
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)


# `PlayerDetail` apunta a modelos definidos más abajo en este mismo archivo.
PlayerDetail.model_rebuild()


class DraftPick(BaseModel):
    """Un pick ya hecho en el draft."""

    pick_no: int
    round: int
    draft_slot: int | None = None
    roster_id: int | None = None
    picked_by: str | None = None
    picked_by_name: str | None = None
    is_mine: bool = False
    player: Player | None = None
    score: float | None = None
    rank: int | None = None


class DraftNeed(BaseModel):
    """Un hueco titular que todavía no tengo cubierto."""

    position: str
    required: int
    filled: int
    missing: int
    urgency: str = "media"  # "alta", "media" o "baja"


class TierSummary(BaseModel):
    """Cuántos jugadores quedan de cada tier en una posición."""

    position: str
    tier: int
    remaining: int
    best_available_rank: int | None = None
    cliff: bool = False  # quedan tan pocos que puede vaciarse antes de tu turno


class DraftSuggestion(BaseModel):
    """Un jugador recomendado, con el motivo."""

    player: Player
    rank: int
    score: float
    tier: int | None = None
    value: float  # nota ajustada por necesidad y escasez
    reasons: list[str] = Field(default_factory=list)


class DraftBoard(BaseModel):
    """Estado completo del draft: lo que queda, lo que necesito y qué hacer."""

    draft_id: str
    status: str  # "pre_draft", "drafting", "complete" o "paused"
    type: str | None = None  # snake, linear, auction
    rounds: int | None = None
    teams: int | None = None
    season: str | None = None
    scoring: str = "ppr"

    my_slot: int | None = None
    my_roster_id: int | None = None
    picks_made: int = 0
    total_picks: int | None = None
    current_round: int | None = None
    on_the_clock_slot: int | None = None
    is_my_turn: bool = False
    picks_until_my_turn: int | None = None
    my_next_pick_no: int | None = None

    my_roster: list[DraftPick] = Field(default_factory=list)
    recent_picks: list[DraftPick] = Field(default_factory=list)
    needs: list[DraftNeed] = Field(default_factory=list)
    suggestions: list[DraftSuggestion] = Field(default_factory=list)
    best_available: list[RankedPlayer] = Field(default_factory=list)
    by_position: dict[str, list[RankedPlayer]] = Field(default_factory=dict)
    tiers: list[TierSummary] = Field(default_factory=list)
    position_run: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime
    warnings: list[str] = Field(default_factory=list)
