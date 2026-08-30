"""Importar rankings de otros analistas y compararlos con el propio.

La idea no es sustituir el ranking de la herramienta, sino ponerlo al lado de
otro y ver **dónde discrepan**, que es justo donde hay algo que decidir. Si dos
listas coinciden en que alguien es el número tres, no hay nada que pensar; si
una lo pone doce puestos por delante, ahí hay una opinión que merece mirarse.

Formato de los archivos: uno por línea, en orden. Se acepta prácticamente
cualquier cosa que se copie de un vídeo, una web o una hoja de cálculo:

    1. Ja'Marr Chase
    2  Bijan Robinson RB ATL
    3, Justin Jefferson, WR, MIN
    Amon-Ra St. Brown

El número de delante es opcional: si no está, manda el orden de las líneas. Las
líneas vacías y las que empiezan por `#` se ignoran, así que se pueden dejar
comentarios y encabezados.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app.matching import (
    build_name_index,
    collapse_name,
    match_players,
    normalize_name,
)
from app.models import ExternalRanking, ExternalRankingEntry, Player

logger = logging.getLogger("fantasy-tool.rankings")

# "12." / "12)" / "12 -" / "12," al principio de la línea.
_NUMERO_INICIAL = re.compile(r"^\s*(\d{1,3})\s*[.)\-,:]?\s+")
# Restos habituales al final: "WR CIN", "(RB - ATL)", "- QB", "WR1"...
_COLA_POSICION = re.compile(
    r"[\s,(\-–|]+(?:QB|RB|WR|TE|K|DEF|DST|D/ST|PK|FLEX)\s*\d*"   # posición y su número
    r"(?:[\s,\-–/|]*[A-Z]{2,3})?"                                  # equipo, si viene
    r"\s*\)?\s*$",
    re.IGNORECASE,
)


def parse_ranking_text(texto: str) -> list[tuple[int, str]]:
    """Convierte el texto de una lista en `[(puesto, nombre)]`."""
    entradas: list[tuple[int, str]] = []
    for linea in (texto or "").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue

        puesto: int | None = None
        coincidencia = _NUMERO_INICIAL.match(linea)
        if coincidencia:
            puesto = int(coincidencia.group(1))
            linea = linea[coincidencia.end() :]

        # Se quita la posición y el equipo si vienen pegados al nombre.
        nombre = _COLA_POSICION.sub("", linea).strip()
        nombre = nombre.strip(" ,;|-–()").strip()
        if not nombre or not normalize_name(nombre):
            continue

        entradas.append((puesto or len(entradas) + 1, nombre))

    # Si los números venían mal o repetidos, manda el orden de aparición.
    puestos = [p for p, _ in entradas]
    if len(set(puestos)) != len(puestos):
        entradas = [(i, nombre) for i, (_, nombre) in enumerate(entradas, start=1)]
    return entradas


def build_external_ranking(
    source: str,
    texto: str,
    players: dict[str, Player],
    *,
    description: str | None = None,
) -> ExternalRanking:
    """Empareja una lista con el catálogo de jugadores.

    Los nombres que no se reconozcan se devuelven aparte: es la información que
    hace falta para corregir el archivo, y callársela sería peor que no importar
    nada.
    """
    indice = build_name_index(players.values())
    # Las defensas suelen aparecer como "SF DEF" o "SF", que al quitar la
    # posición se queda en una sola palabra y no casa por nombre.
    defensas = {
        (p.team or "").upper(): pid
        for pid, p in players.items()
        if p.position == "DEF" and p.team
    }
    entradas: list[ExternalRankingEntry] = []
    sin_reconocer: list[str] = []
    vistos: set[str] = set()

    for puesto, nombre in parse_ranking_text(texto):
        # Se busca el nombre tal cual; `match_players` ya tolera acentos,
        # sufijos y abreviaturas.
        candidatos = match_players(nombre, indice)
        pid = candidatos[0] if candidatos else indice.get(normalize_name(nombre))
        if not pid:
            pid = indice.get(collapse_name(nombre))
        if not pid:
            pid = defensas.get(nombre.strip().upper())

        if not pid or pid in vistos:
            if not pid:
                sin_reconocer.append(nombre)
            continue

        vistos.add(pid)
        entradas.append(
            ExternalRankingEntry(
                rank=puesto,
                player_id=pid,
                name=players[pid].name,
                source_name=nombre,
            )
        )

    entradas.sort(key=lambda e: e.rank)
    # Se renumera para que no haya huecos por los nombres descartados.
    for posicion, entrada in enumerate(entradas, start=1):
        entrada.rank = posicion

    if sin_reconocer:
        logger.warning(
            "Ranking «%s»: no reconocí %d nombres (%s%s)",
            source,
            len(sin_reconocer),
            ", ".join(sin_reconocer[:5]),
            "…" if len(sin_reconocer) > 5 else "",
        )

    return ExternalRanking(
        source=source,
        description=description,
        entries=entradas,
        unmatched=sin_reconocer,
        total=len(entradas),
    )


def load_ranking_files(
    directory: Path, players: dict[str, Player]
) -> list[ExternalRanking]:
    """Carga todos los rankings de un directorio.

    El nombre del archivo es el nombre de la fuente: `mi-analista.txt` ->
    "mi analista". Si la primera línea es un comentario `# ...`, se usa como
    descripción.
    """
    rankings: list[ExternalRanking] = []
    if not directory.is_dir():
        return rankings

    for archivo in sorted(directory.glob("*.txt")) + sorted(directory.glob("*.csv")):
        try:
            texto = archivo.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("No se pudo leer %s: %s", archivo, exc)
            continue

        descripcion = None
        primera = texto.lstrip().splitlines()[0] if texto.strip() else ""
        if primera.startswith("#"):
            descripcion = primera.lstrip("# ").strip() or None

        nombre = archivo.stem.replace("-", " ").replace("_", " ").strip()
        ranking = build_external_ranking(nombre, texto, players, description=descripcion)
        if ranking.entries:
            rankings.append(ranking)
        else:
            logger.warning("El ranking «%s» se quedó sin ninguna entrada válida", nombre)
    return rankings


def index_by_player(rankings: list[ExternalRanking]) -> dict[str, dict[str, int]]:
    """`{player_id: {fuente: puesto}}`, para colgarlo de cada jugador."""
    indice: dict[str, dict[str, int]] = {}
    for ranking in rankings:
        for entrada in ranking.entries:
            indice.setdefault(entrada.player_id, {})[ranking.source] = entrada.rank
    return indice
