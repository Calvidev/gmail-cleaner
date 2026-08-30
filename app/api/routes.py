"""Endpoints REST de Fantasy Tool."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models import (
    DraftBoard,
    LeagueAnalysis,
    Meta,
    NewsItem,
    OddsResponse,
    PlayerDetail,
    PlayerTrend,
    RankedPlayer,
    RankingResponse,
    TrendsResponse,
)
from app.ranking import SCORING_FORMATS, filter_ranked, utc_now
from app.trends import filter_trends
from app.service import FantasyService, LeagueNotConfigured, ServiceUnavailable

router = APIRouter(prefix="/api")


def get_service(request: Request) -> FantasyService:
    service = getattr(request.app.state, "service", None)
    if service is None:  # pragma: no cover - no debería ocurrir
        raise HTTPException(status_code=500, detail="Servicio no inicializado")
    return service


ServiceDep = Annotated[FantasyService, Depends(get_service)]


def _validate_scoring(scoring: str) -> str:
    if scoring not in SCORING_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"scoring debe ser uno de: {', '.join(SCORING_FORMATS)}",
        )
    return scoring


@router.get("/health", summary="Comprobación de vida")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta", response_model=Meta, summary="Temporada, equipos y avisos")
async def meta(service: ServiceDep) -> Meta:
    return await service.get_meta()


@router.get(
    "/rankings",
    response_model=RankingResponse,
    summary="Ranking de jugadores del mejor al peor",
)
async def rankings(
    service: ServiceDep,
    scoring: str = Query("ppr", description="ppr, half_ppr o standard"),
    superflex: bool = Query(False, description="Sube el valor de los QB"),
    position: str | None = Query(None, description="QB, RB, WR, TE, K, DEF o lista"),
    team: str | None = Query(None, description="Abreviatura del equipo, p.ej. KC"),
    search: str | None = Query(None, description="Busca por nombre, equipo o universidad"),
    free_agents_only: bool = Query(False, description="Solo libres en tu liga"),
    hide_injured: bool = Query(False, description="Oculta lesiones graves (IR, Out)"),
    injured_only: bool = Query(False, description="Solo jugadores con parte de lesión"),
    max_age: int | None = Query(None, ge=18, le=50),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> RankingResponse:
    scoring = _validate_scoring(scoring)
    try:
        ranked = await service.get_ranking(scoring, superflex)
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    available: set[str] | None = None
    if free_agents_only:
        rostered = await service.get_rostered_ids()
        if rostered is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Para filtrar agentes libres hace falta el id de tu liga. "
                    "Añade SLEEPER_LEAGUE_ID en el archivo .env."
                ),
            )
        available = rostered

    filtered = filter_ranked(
        ranked,
        position=position,
        team=team,
        search=search,
        available_only=available,
        max_age=max_age,
        injured_only=injured_only,
        hide_injured=hide_injured,
    )

    page = filtered[offset : offset + limit]
    meta_info = await service.get_meta()
    return RankingResponse(
        season=meta_info.season,
        week=meta_info.week,
        scoring=scoring,
        total=len(filtered),
        count=len(page),
        offset=offset,
        generated_at=utc_now(),
        players=page,
    )


@router.get(
    "/players/{player_id}",
    response_model=PlayerDetail,
    summary="Ficha de un jugador con sus noticias",
)
async def player_detail(
    service: ServiceDep,
    player_id: str,
    scoring: str = Query("ppr"),
    superflex: bool = Query(False),
    news_limit: int = Query(20, ge=0, le=100),
) -> PlayerDetail:
    scoring = _validate_scoring(scoring)
    try:
        ranked = await service.get_ranked_player(player_id, scoring, superflex)
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if ranked is None:
        raise HTTPException(status_code=404, detail=f"No existe el jugador {player_id}")

    news: list[NewsItem] = []
    if news_limit:
        news = await service.get_player_news(player_id, limit=news_limit)

    # Tendencia, cuotas y props son extras: si una fuente falla, la ficha sigue.
    trend = None
    try:
        trend = await service.get_player_trend(player_id, scoring)
    except Exception:  # noqa: BLE001 - un extra caído no puede tumbar la ficha
        trend = None

    vegas = None
    if ranked.player.team:
        try:
            vegas = (await service.get_team_odds()).get(ranked.player.team)
        except Exception:  # noqa: BLE001
            vegas = None

    try:
        props = await service.get_player_props(player_id)
    except Exception:  # noqa: BLE001
        props = []

    return PlayerDetail(ranked=ranked, news=news, trend=trend, vegas=vegas, props=props)


@router.get(
    "/players/{player_id}/news",
    response_model=list[NewsItem],
    summary="Noticias de un jugador",
)
async def player_news(
    service: ServiceDep,
    player_id: str,
    limit: int = Query(20, ge=1, le=100),
) -> list[NewsItem]:
    try:
        return await service.get_player_news(player_id, limit=limit)
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/news", response_model=list[NewsItem], summary="Noticias de la NFL")
async def news(
    service: ServiceDep,
    limit: int = Query(60, ge=1, le=200),
    q: str | None = Query(None, description="Filtra por texto"),
    player_id: str | None = Query(None, description="Solo noticias de este jugador"),
    only_players: bool = Query(False, description="Solo noticias con jugador identificado"),
) -> list[NewsItem]:
    try:
        items = await service.get_news(limit=service.settings.news_max_items)
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if player_id:
        items = [i for i in items if player_id in i.player_ids]
    if only_players:
        items = [i for i in items if i.player_ids]
    if q:
        needle = q.strip().lower()
        items = [
            i
            for i in items
            if needle in i.title.lower()
            or needle in (i.summary or "").lower()
            or any(needle in n.lower() for n in i.player_names)
        ]
    return items[:limit]


@router.get(
    "/trends",
    response_model=TrendsResponse,
    summary="Quién sube y quién baja jornada a jornada",
)
async def trends(
    service: ServiceDep,
    scoring: str = Query("ppr"),
    superflex: bool = Query(False),
    weeks: int = Query(6, ge=3, le=12, description="Jornadas a analizar"),
    direction: str | None = Query(None, description="alza, baja, estable o todos"),
    position: str | None = Query(None),
    team: str | None = Query(None),
    search: str | None = Query(None),
    min_games: int = Query(3, ge=1, le=17),
    usage_only: bool = Query(
        True, description="Solo jugadores con datos de volumen (no pateadores ni defensas)"
    ),
    free_agents_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
) -> TrendsResponse:
    scoring = _validate_scoring(scoring)
    try:
        todas = await service.get_trends(scoring, weeks, superflex)
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    available: set[str] | None = None
    if free_agents_only:
        rostered = await service.get_rostered_ids()
        if rostered is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Para filtrar agentes libres hace falta el id de tu liga. "
                    "Añade SLEEPER_LEAGUE_ID en el archivo .env."
                ),
            )
        available = rostered

    filtradas = filter_trends(
        todas,
        direction=direction,
        position=position,
        team=team,
        search=search,
        min_games=min_games,
        usage_only=usage_only,
        available_only=available,
    )

    # A la baja se ordena al revés: primero el que más cae.
    if direction and direction.lower() == "baja":
        filtradas = sorted(filtradas, key=lambda t: t.trend_score)

    meta_info = await service.get_meta()
    semanas = sorted({w.week for t in todas for w in t.weeks})
    return TrendsResponse(
        season=meta_info.season,
        week=meta_info.week,
        weeks_analyzed=semanas,
        scoring=scoring,
        total=len(filtradas),
        generated_at=utc_now(),
        players=filtradas[:limit],
        warnings=[] if todas else [
            "Todavía no hay estadísticas por jornada de esta temporada: "
            "las tendencias aparecen cuando se juegan al menos tres jornadas."
        ],
    )


@router.get(
    "/players/{player_id}/trend",
    response_model=PlayerTrend,
    summary="Tendencia de un jugador",
)
async def player_trend(
    service: ServiceDep,
    player_id: str,
    scoring: str = Query("ppr"),
    weeks: int = Query(6, ge=3, le=12),
) -> PlayerTrend:
    scoring = _validate_scoring(scoring)
    trend = await service.get_player_trend(player_id, scoring, weeks)
    if trend is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay suficientes jornadas del jugador {player_id} para una tendencia",
        )
    return trend


@router.get(
    "/odds",
    response_model=OddsResponse,
    summary="Lo que dicen las casas de apuestas de cada partido",
)
async def odds(
    service: ServiceDep,
    week: int | None = Query(None, ge=1, le=22),
) -> OddsResponse:
    juegos = await service.get_odds_games(week)
    equipos = list((await service.get_team_odds(week)).values())
    meta_info = await service.get_meta()

    avisos = list(service.odds.last_errors)
    if not juegos:
        avisos.append(
            "No hay cuotas disponibles ahora mismo. ESPN solo las publica cuando "
            "hay jornada abierta."
        )
    if not service.odds.has_api_key:
        avisos.append(
            "Sin ODDS_API_KEY solo se ven spread y total por partido. Con una llave "
            "gratuita de the-odds-api.com se añaden las líneas por jugador."
        )

    return OddsResponse(
        week=week or meta_info.week,
        season=meta_info.season,
        games=juegos,
        teams=equipos,
        props_available=service.odds.has_api_key,
        generated_at=utc_now(),
        warnings=avisos,
    )


@router.get(
    "/draft",
    response_model=DraftBoard,
    summary="Tablero del draft: mejores disponibles, huecos y recomendación",
)
async def draft_board(
    service: ServiceDep,
    scoring: str = Query("ppr"),
    superflex: bool = Query(False),
    draft_id: str | None = Query(None, description="Por defecto, el draft de tu liga"),
    board_size: int = Query(60, ge=10, le=300),
) -> DraftBoard:
    scoring = _validate_scoring(scoring)
    try:
        board = await service.get_draft_board(scoring, superflex, draft_id)
    except LeagueNotConfigured as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    board.best_available = board.best_available[:board_size]
    return board


@router.get(
    "/league/analysis",
    response_model=LeagueAnalysis,
    summary="Tu equipo comparado con la liga, con ideas de intercambio",
)
async def league_analysis(
    service: ServiceDep,
    scoring: str = Query("ppr"),
    superflex: bool = Query(False),
    max_trade_ideas: int = Query(12, ge=1, le=40),
) -> LeagueAnalysis:
    scoring = _validate_scoring(scoring)
    try:
        return await service.get_league_analysis(scoring, superflex, max_trade_ideas)
    except LeagueNotConfigured as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/league", summary="Tu liga de Sleeper (requiere SLEEPER_LEAGUE_ID)")
async def league(service: ServiceDep) -> dict:
    try:
        return await service.get_league_info()
    except LeagueNotConfigured as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/refresh", summary="Vacía la caché y vuelve a descargar")
async def refresh(service: ServiceDep) -> dict[str, str]:
    service.refresh()
    return {"status": "cache vaciada"}


@router.get(
    "/compare",
    response_model=list[RankedPlayer],
    summary="Compara varios jugadores por id",
)
async def compare(
    service: ServiceDep,
    ids: str = Query(..., description="Ids separados por coma"),
    scoring: str = Query("ppr"),
    superflex: bool = Query(False),
) -> list[RankedPlayer]:
    scoring = _validate_scoring(scoring)
    wanted = [i.strip() for i in ids.split(",") if i.strip()][:8]
    try:
        ranked = await service.get_ranking(scoring, superflex)
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    index = {r.player.player_id: r for r in ranked}
    return [index[pid] for pid in wanted if pid in index]
