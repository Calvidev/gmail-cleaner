"""Tablero de draft: qué queda, qué me falta y a quién coger.

Durante un draft en vivo Sleeper publica los picks conforme se hacen, así que
la herramienta puede ir tachando del ranking a los que ya han salido y decir en
todo momento quién es el mejor disponible **para ti**, que no es lo mismo que el
mejor disponible a secas: depende de los huecos que te queden por cubrir y de si
tu tier favorito se va a vaciar antes de que te vuelva a tocar.

Tres ideas gobiernan la recomendación:

* **Necesidad**: un hueco titular sin cubrir vale más que un suplente de lujo.
* **Escasez de tier**: si de un tier quedan tres jugadores y hasta tu próximo
  turno pasan quince picks, ese tier no llega. Coge ahora o quédate sin él.
* **Rachas**: cuando salen cinco corredores seguidos, el resto de la sala ya
  está reaccionando y los que quedan se van a evaporar.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.league_analysis import FLEX_SLOTS, starting_slots
from app.models import (
    DraftBoard,
    DraftNeed,
    DraftPick,
    DraftSuggestion,
    Player,
    RankedPlayer,
    TierSummary,
)
from app.ranking import primary_position

RUN_WINDOW = 10  # picks recientes que se miran para detectar una racha
RUN_THRESHOLD = 4  # cuántos de una posición hacen "racha"

NEED_MULTIPLIER = {"alta": 1.25, "media": 1.10, "baja": 0.88}

# Por cada hueco extra sin cubrir en la misma posición se sube un poco más:
# no es lo mismo que te falte un corredor que que te falten dos.
EXTRA_POR_HUECO = 0.07


# --- orden de picks ----------------------------------------------------------


def pick_number(slot: int, round_: int, teams: int, snake: bool = True) -> int:
    """Número absoluto de pick de un puesto en una ronda.

    En formato serpiente las rondas pares van al revés: el que elige el primero
    en la ronda 1 elige el último en la ronda 2.
    """
    if round_ % 2 == 0 and snake:
        return (round_ - 1) * teams + (teams - slot + 1)
    return (round_ - 1) * teams + slot


def my_pick_numbers(slot: int, teams: int, rounds: int, snake: bool = True) -> list[int]:
    """Todos los picks que te tocan, en orden."""
    if not slot or not teams or not rounds:
        return []
    return [pick_number(slot, r, teams, snake) for r in range(1, rounds + 1)]


def slot_on_the_clock(pick_no: int, teams: int, snake: bool = True) -> int | None:
    """A qué puesto le toca elegir en un número de pick dado."""
    if not teams or pick_no < 1:
        return None
    round_ = (pick_no - 1) // teams + 1
    posicion = (pick_no - 1) % teams + 1
    if round_ % 2 == 0 and snake:
        return teams - posicion + 1
    return posicion


# --- picks -------------------------------------------------------------------


def parse_picks(
    raw_picks: list[dict[str, Any]],
    ranked_by_id: dict[str, RankedPlayer],
    users_by_id: dict[str, dict[str, Any]],
    my_user_id: str | None = None,
) -> list[DraftPick]:
    """Normaliza los picks que devuelve Sleeper."""
    picks: list[DraftPick] = []
    for raw in raw_picks or []:
        if not isinstance(raw, dict):
            continue
        player_id = str(raw.get("player_id") or "")
        entry = ranked_by_id.get(player_id)
        picked_by = str(raw.get("picked_by") or "") or None
        user = users_by_id.get(picked_by or "")

        picks.append(
            DraftPick(
                pick_no=int(raw.get("pick_no") or 0),
                round=int(raw.get("round") or 0),
                draft_slot=raw.get("draft_slot"),
                roster_id=raw.get("roster_id"),
                picked_by=picked_by,
                picked_by_name=(user or {}).get("display_name") if user else None,
                is_mine=bool(my_user_id and picked_by == str(my_user_id)),
                player=entry.player if entry else _player_from_pick(raw, player_id),
                score=entry.score if entry else None,
                rank=entry.rank if entry else None,
            )
        )
    picks.sort(key=lambda p: p.pick_no)
    return picks


def _player_from_pick(raw: dict[str, Any], player_id: str) -> Player | None:
    """Jugador mínimo a partir de los metadatos del pick.

    Sirve para los que no están en nuestro catálogo (por ejemplo si Sleeper
    añade a alguien nuevo entre descarga y descarga).
    """
    meta = raw.get("metadata") or {}
    nombre = " ".join(
        p for p in (meta.get("first_name"), meta.get("last_name")) if p
    ).strip()
    if not nombre and not player_id:
        return None
    return Player(
        player_id=player_id or "?",
        name=nombre or player_id,
        first_name=meta.get("first_name"),
        last_name=meta.get("last_name"),
        position=meta.get("position"),
        fantasy_positions=[meta["position"]] if meta.get("position") else [],
        team=meta.get("team"),
    )


def position_runs(picks: list[DraftPick], window: int = RUN_WINDOW) -> dict[str, int]:
    """Cuántos jugadores de cada posición han salido en los últimos picks."""
    recientes = picks[-window:] if window else picks
    conteo: Counter[str] = Counter()
    for pick in recientes:
        if pick.player:
            conteo[primary_position(pick.player)] += 1
    return dict(conteo)


# --- necesidades -------------------------------------------------------------


def compute_needs(
    roster_positions: list[str] | None, my_players: list[Player], rounds_left: int = 99
) -> list[DraftNeed]:
    """Huecos titulares que todavía no tengo cubiertos."""
    slots = starting_slots(roster_positions)
    fijos: Counter[str] = Counter()
    flexibles: list[str] = []
    for slot in slots:
        if slot.upper() in FLEX_SLOTS:
            flexibles.append(slot.upper())
        else:
            fijos[slot.upper()] += 1

    tengo: Counter[str] = Counter(primary_position(p) for p in my_players)

    needs: list[DraftNeed] = []
    for posicion, requeridos in fijos.items():
        cubiertos = min(tengo.get(posicion, 0), requeridos)
        faltan = requeridos - cubiertos
        needs.append(
            DraftNeed(
                position=posicion,
                required=requeridos,
                filled=cubiertos,
                missing=faltan,
                urgency=_urgency(faltan, rounds_left),
            )
        )

    # Los huecos flexibles los cubre cualquier excedente de las posiciones que
    # admiten, así que se calculan al final, con lo que sobra.
    if flexibles:
        elegibles: set[str] = set()
        for slot in flexibles:
            elegibles.update(FLEX_SLOTS.get(slot, ()))
        excedente = sum(
            max(0, tengo.get(posicion, 0) - fijos.get(posicion, 0)) for posicion in elegibles
        )
        faltan = max(0, len(flexibles) - excedente)
        needs.append(
            DraftNeed(
                position="FLEX",
                required=len(flexibles),
                filled=len(flexibles) - faltan,
                missing=faltan,
                urgency=_urgency(faltan, rounds_left),
            )
        )

    needs.sort(key=lambda n: (-n.missing, n.position))
    return needs


def _urgency(missing: int, rounds_left: int) -> str:
    if missing <= 0:
        return "baja"
    if missing >= 2 or rounds_left <= missing + 1:
        return "alta"
    return "media"


def needed_positions(needs: list[DraftNeed]) -> dict[str, str]:
    """Posición -> urgencia, con el FLEX repartido entre quienes lo pueden ocupar."""
    mapa: dict[str, str] = {}
    for need in needs:
        if need.position == "FLEX":
            if need.missing > 0:
                for posicion in FLEX_SLOTS["FLEX"]:
                    mapa.setdefault(posicion, need.urgency)
            continue
        mapa[need.position] = need.urgency
    return mapa


# --- tiers y escasez ---------------------------------------------------------


def tier_summaries(
    available: list[RankedPlayer], picks_until_turn: int | None
) -> list[TierSummary]:
    """Cuántos quedan de cada tier y cuáles se van a vaciar antes de tu turno."""
    agrupado: dict[tuple[str, int], list[RankedPlayer]] = {}
    for entry in available:
        if entry.tier is None:
            continue
        agrupado.setdefault((primary_position(entry.player), entry.tier), []).append(entry)

    resumen: list[TierSummary] = []
    for (posicion, tier), jugadores in agrupado.items():
        # Cuanto más lejos quede tu turno, más probable es que el tier se agote.
        umbral = max(2, (picks_until_turn or 0) // 4)
        resumen.append(
            TierSummary(
                position=posicion,
                tier=tier,
                remaining=len(jugadores),
                best_available_rank=min(j.rank for j in jugadores),
                cliff=len(jugadores) <= umbral,
            )
        )
    resumen.sort(key=lambda t: (t.position, t.tier))
    return resumen


# --- recomendación -----------------------------------------------------------


def suggest_picks(
    available: list[RankedPlayer],
    needs: list[DraftNeed],
    runs: dict[str, int],
    tiers: list[TierSummary],
    picks_until_turn: int | None,
    *,
    limit: int = 6,
) -> list[DraftSuggestion]:
    """Ordena a los disponibles por lo que valen **para ti**, con el porqué."""
    urgencias = needed_positions(needs)
    por_tier = {(t.position, t.tier): t for t in tiers}

    sugerencias: list[DraftSuggestion] = []
    for entry in available[:60]:  # con los 60 mejores sobra
        posicion = primary_position(entry.player)
        urgencia = urgencias.get(posicion, "baja")
        razones: list[str] = []

        multiplicador = NEED_MULTIPLIER.get(urgencia, 1.0)
        need = next((n for n in needs if n.position == posicion), None)
        if need and need.missing > 1:
            multiplicador += EXTRA_POR_HUECO * (need.missing - 1)
        valor = entry.score * multiplicador

        if need and need.missing > 0:
            razones.append(
                f"Te falta{'n' if need.missing > 1 else ''} {need.missing} "
                f"{posicion} por cubrir en la alineación"
            )

        elif urgencia == "baja":
            razones.append(f"Ya tienes cubierto el {posicion} titular")

        resumen = por_tier.get((posicion, entry.tier)) if entry.tier else None
        if resumen and resumen.cliff:
            valor *= 1.15
            quedan = "queda" if resumen.remaining == 1 else "quedan"
            aviso = (
                f"Solo {quedan} {resumen.remaining} del tier {entry.tier} en {posicion}"
            )
            if picks_until_turn:
                pasan = "pasa" if picks_until_turn == 1 else "pasan"
                pick = "pick" if picks_until_turn == 1 else "picks"
                aviso += f" y hasta tu próximo turno {pasan} {picks_until_turn} {pick}"
            razones.append(aviso)

        racha = runs.get(posicion, 0)
        if racha >= RUN_THRESHOLD:
            valor *= 1.08
            razones.append(f"Racha de {posicion}: {racha} en los últimos {RUN_WINDOW} picks")

        razones.append(f"Nota {entry.score:.1f} · {posicion}{entry.position_rank} del ranking")

        sugerencias.append(
            DraftSuggestion(
                player=entry.player,
                rank=entry.rank,
                score=entry.score,
                tier=entry.tier,
                value=round(valor, 2),
                reasons=razones,
            )
        )

    sugerencias.sort(key=lambda s: -s.value)
    return sugerencias[:limit]


# --- configuración de huecos -------------------------------------------------

# Cómo se llaman en Sleeper los ajustes de huecos del draft.
SLOT_SETTINGS = [
    ("slots_qb", "QB"),
    ("slots_rb", "RB"),
    ("slots_wr", "WR"),
    ("slots_te", "TE"),
    ("slots_flex", "FLEX"),
    ("slots_wr_rb_flex", "WRRB_FLEX"),
    ("slots_wr_te_flex", "REC_FLEX"),
    ("slots_super_flex", "SUPER_FLEX"),
    ("slots_k", "K"),
    ("slots_def", "DEF"),
]


def roster_positions_from_draft(settings: dict[str, Any] | None) -> list[str]:
    """Deduce la alineación de la liga a partir de los ajustes del draft.

    El objeto del draft ya trae cuántos huecos hay de cada tipo, así que no
    hace falta pedir la liga entera solo para saber si se alinean dos
    corredores o tres receptores.
    """
    positions: list[str] = []
    for clave, nombre in SLOT_SETTINGS:
        cantidad = (settings or {}).get(clave)
        try:
            cantidad = int(cantidad or 0)
        except (TypeError, ValueError):
            cantidad = 0
        positions.extend([nombre] * max(0, cantidad))
    return positions


# --- tablero completo --------------------------------------------------------


def build_board(
    draft: dict[str, Any],
    raw_picks: list[dict[str, Any]],
    ranked: list[RankedPlayer],
    users: list[dict[str, Any]],
    *,
    my_user_id: str | None = None,
    league_roster_positions: list[str] | None = None,
    scoring: str = "ppr",
    board_size: int = 60,
) -> DraftBoard:
    """Monta el tablero completo a partir del draft y de los picks."""
    ranked_by_id = {entry.player.player_id: entry for entry in ranked}
    users_by_id = {str(u.get("user_id")): u for u in users or []}

    settings = draft.get("settings") or {}
    teams = int(settings.get("teams") or 0) or None
    rounds = int(settings.get("rounds") or 0) or None
    tipo = draft.get("type")
    snake = (tipo or "snake") == "snake"
    # La alineación de la liga: si no la tenemos, se deduce del propio draft.
    roster_positions = (
        league_roster_positions
        or draft.get("roster_positions")
        or roster_positions_from_draft(settings)
        or None
    )

    picks = parse_picks(raw_picks, ranked_by_id, users_by_id, my_user_id)
    tomados = {p.player.player_id for p in picks if p.player}

    # Mi puesto en el orden del draft.
    draft_order = draft.get("draft_order") or {}
    my_slot = None
    if my_user_id and isinstance(draft_order, dict):
        valor = draft_order.get(str(my_user_id))
        my_slot = int(valor) if valor else None

    slot_to_roster = draft.get("slot_to_roster_id") or {}
    my_roster_id = None
    if my_slot and isinstance(slot_to_roster, dict):
        valor = slot_to_roster.get(str(my_slot))
        my_roster_id = int(valor) if valor else None

    hechos = len(picks)
    pick_actual = hechos + 1
    total_picks = teams * rounds if teams and rounds else None
    ronda_actual = ((pick_actual - 1) // teams + 1) if teams else None
    en_turno = slot_on_the_clock(pick_actual, teams, snake) if teams else None

    mis_picks = my_pick_numbers(my_slot, teams, rounds, snake) if my_slot and teams and rounds else []
    siguiente = next((n for n in mis_picks if n >= pick_actual), None)
    faltan_para_mi = (siguiente - pick_actual) if siguiente else None

    # Disponibles: el ranking menos lo que ya ha salido.
    disponibles = [e for e in ranked if e.player.player_id not in tomados]

    mi_roster = [p for p in picks if p.is_mine]
    mis_jugadores = [p.player for p in mi_roster if p.player]
    rondas_restantes = (rounds - (ronda_actual or 1) + 1) if rounds else 99

    needs = compute_needs(roster_positions, mis_jugadores, rondas_restantes)
    runs = position_runs(picks)
    tiers = tier_summaries(disponibles, faltan_para_mi)
    sugerencias = suggest_picks(disponibles, needs, runs, tiers, faltan_para_mi)

    por_posicion: dict[str, list[RankedPlayer]] = {}
    for entry in disponibles:
        posicion = primary_position(entry.player)
        if len(por_posicion.setdefault(posicion, [])) < 15:
            por_posicion[posicion].append(entry)

    estado = draft.get("status") or "pre_draft"
    avisos: list[str] = []
    if my_slot is None:
        avisos.append(
            "No sé en qué puesto del orden eliges, así que no puedo decirte cuándo te toca "
            "ni qué te falta. Revisa SLEEPER_USERNAME o pon tu SLEEPER_USER_ID."
        )
    if estado == "pre_draft":
        avisos.append(
            "El draft aún no ha empezado: esto es tu chuleta. En cuanto arranque, los "
            "jugadores que vayan saliendo desaparecen solos del tablero."
        )
    elif estado == "complete":
        avisos.append("El draft ha terminado. Ya puedes usar la pestaña Mi equipo.")

    return DraftBoard(
        draft_id=str(draft.get("draft_id") or ""),
        status=estado,
        type=tipo,
        rounds=rounds,
        teams=teams,
        season=str(draft.get("season") or "") or None,
        scoring=scoring,
        my_slot=my_slot,
        my_roster_id=my_roster_id,
        picks_made=hechos,
        total_picks=total_picks,
        current_round=ronda_actual,
        on_the_clock_slot=en_turno,
        is_my_turn=bool(my_slot and en_turno == my_slot and estado == "drafting"),
        picks_until_my_turn=faltan_para_mi,
        my_next_pick_no=siguiente,
        my_roster=mi_roster,
        recent_picks=list(reversed(picks[-12:])),
        needs=needs,
        suggestions=sugerencias,
        best_available=disponibles[:board_size],
        by_position=por_posicion,
        tiers=[t for t in tiers if t.cliff][:12],
        position_run=runs,
        generated_at=datetime.now(timezone.utc),
        warnings=avisos,
    )
