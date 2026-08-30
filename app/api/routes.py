"""Endpoints REST de Fantasy Tool."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models import (
    Meta,
    NewsItem,
    PlayerDetail,
    RankedPlayer,
    RankingResponse,
)
from app.ranking import SCORING_FORMATS, filter_ranked, utc_now
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
    return PlayerDetail(ranked=ranked, news=news)


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
