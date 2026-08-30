"""Punto de entrada de Fantasy Tool.

Arranque:
    uvicorn app.main:app --reload
o bien:
    python -m app.main
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router as api_router
from app.config import ROOT_DIR, get_settings
from app.service import build_service

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s"
)
logger = logging.getLogger("fantasy-tool")

WEB_DIR: Path = ROOT_DIR / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.service = build_service(settings)
    logger.info("Fantasy Tool %s lista en http://%s:%s", __version__, settings.host, settings.port)
    if not settings.league_configured:
        logger.info(
            "Sin liga de Sleeper configurada: el ranking y las noticias funcionan igual; "
            "añade SLEEPER_LEAGUE_ID en .env para las funciones de liga."
        )
    try:
        yield
    finally:
        await app.state.service.aclose()


app = FastAPI(
    title="Fantasy Tool",
    description=(
        "Noticias por jugador y ranking de la NFL del mejor al peor, "
        "con datos de Sleeper y de las principales fuentes de noticias."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", include_in_schema=False, response_model=None)
async def index() -> FileResponse | JSONResponse:
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse(
        {"app": "Fantasy Tool", "version": __version__, "docs": "/docs"}
    )


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
