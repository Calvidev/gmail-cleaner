"""Analiza tu equipo contra el resto de la liga y busca intercambios.

Todo se apoya en una sola idea medible: **el valor de tu alineación titular
óptima**. Para cada equipo se coloca a sus mejores jugadores en los huecos que
exige la liga (QB, RB, WR, TE, FLEX…) y se suman sus notas. A partir de ahí:

* Una posición es *débil* si tus titulares en ella valen menos que la media de
  la liga; *fuerte* si valen más.
* Tienes *excedente* en una posición cuando un suplente tuyo sería titular en
  otros equipos: valor parado en el banquillo.
* Un intercambio es interesante cuando **sube la alineación titular de las dos
  partes**. Si solo mejora una, el otro no lo va a aceptar.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import (
    LeagueAnalysis,
    PositionStrength,
    RankedPlayer,
    TeamAnalysis,
    TradeIdea,
)
from app.ranking import primary_position

# Qué posiciones admite cada tipo de hueco flexible de Sleeper.
FLEX_SLOTS: dict[str, tuple[str, ...]] = {
    "FLEX": ("RB", "WR", "TE"),
    "WRRB_FLEX": ("RB", "WR"),
    "WRRB-FLEX": ("RB", "WR"),
    "REC_FLEX": ("WR", "TE"),
    "SUPER_FLEX": ("QB", "RB", "WR", "TE"),
    "SUPERFLEX": ("QB", "RB", "WR", "TE"),
    "IDP_FLEX": (),
}

# Huecos que no forman alineación (banquillo, lesionados, filial).
NON_STARTING_SLOTS = {"BN", "IR", "TAXI"}

DEFAULT_ROSTER_POSITIONS = [
    "QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF",
]

WEAK_PERCENTILE = 35.0
STRONG_PERCENTILE = 70.0


def starting_slots(roster_positions: list[str] | None) -> list[str]:
    """Huecos titulares de la liga, sin banquillo ni lesionados."""
    positions = roster_positions or DEFAULT_ROSTER_POSITIONS
    return [slot for slot in positions if slot.upper() not in NON_STARTING_SLOTS]


def startable_positions(roster_positions: list[str] | None) -> set[str]:
    """Posiciones que esta liga llega a alinear.

    Si la liga no tiene hueco de pateador, no tiene sentido juzgar a nadie por
    sus pateadores: son banquillo puro y contarlos ensucia el análisis.
    """
    positions: set[str] = set()
    for slot in starting_slots(roster_positions):
        slot = slot.upper()
        if slot in FLEX_SLOTS:
            positions.update(FLEX_SLOTS[slot])
        else:
            positions.add(slot)
    return positions


def slot_accepts(slot: str, position: str) -> bool:
    """¿Puede este jugador ocupar este hueco?"""
    slot = slot.upper()
    if slot in FLEX_SLOTS:
        return position in FLEX_SLOTS[slot]
    return slot == position


def optimal_lineup(
    players: list[RankedPlayer], roster_positions: list[str] | None
) -> tuple[list[RankedPlayer], list[RankedPlayer], float]:
    """Coloca a los mejores en los huecos titulares.

    Devuelve `(titulares, banquillo, valor total)`. Los huecos se rellenan de
    los más exigentes a los más flexibles, para no gastar al mejor receptor en
    un FLEX cuando hace falta en WR.
    """
    slots = starting_slots(roster_positions)
    # Primero los huecos fijos, después los flexibles: un hueco fijo solo lo
    # puede ocupar esa posición, así que tiene prioridad.
    ordered = sorted(slots, key=lambda s: (s.upper() in FLEX_SLOTS, s))

    available = sorted(players, key=lambda r: -r.score)
    used: set[str] = set()
    starters: list[RankedPlayer] = []

    for slot in ordered:
        for candidate in available:
            pid = candidate.player.player_id
            if pid in used:
                continue
            if slot_accepts(slot, primary_position(candidate.player)):
                starters.append(candidate)
                used.add(pid)
                break

    bench = [p for p in available if p.player.player_id not in used]
    total = round(sum(s.score for s in starters), 2)
    return starters, bench, total


def lineup_value(players: list[RankedPlayer], roster_positions: list[str] | None) -> float:
    """Valor de la alineación titular óptima de un conjunto de jugadores."""
    return optimal_lineup(players, roster_positions)[2]


def _percentile(value: float, population: list[float]) -> float:
    """Percentil de un valor dentro de una población (0-100)."""
    if not population:
        return 50.0
    below = sum(1 for other in population if other < value)
    equal = sum(1 for other in population if other == value)
    return round((below + equal / 2) / len(population) * 100.0, 1)


def analyze_team(
    roster: dict[str, Any],
    ranked_by_id: dict[str, RankedPlayer],
    roster_positions: list[str] | None,
    users_by_id: dict[str, dict[str, Any]],
) -> TeamAnalysis:
    """Radiografía de un equipo: titulares, banquillo y notas por posición."""
    player_ids = [str(pid) for pid in (roster.get("players") or [])]
    entries = [ranked_by_id[pid] for pid in player_ids if pid in ranked_by_id]

    starters, bench, total = optimal_lineup(entries, roster_positions)
    starter_ids = {s.player.player_id for s in starters}

    owner_id = roster.get("owner_id")
    user = users_by_id.get(str(owner_id)) if owner_id else None
    owner = (user or {}).get("display_name")
    team_name = ((user or {}).get("metadata") or {}).get("team_name")

    relevantes = startable_positions(roster_positions)
    positions: dict[str, PositionStrength] = {}
    for entry in entries:
        position = primary_position(entry.player)
        if position not in relevantes:
            continue  # posición que esta liga ni siquiera alinea
        block = positions.setdefault(position, PositionStrength(position=position))
        if entry.player.player_id in starter_ids:
            block.starters.append(entry)
        else:
            block.bench.append(entry)

    for block in positions.values():
        block.starters.sort(key=lambda r: -r.score)
        block.bench.sort(key=lambda r: -r.score)
        block.starter_score = round(sum(s.score for s in block.starters), 2)
        block.avg_score = round(
            block.starter_score / len(block.starters), 2
        ) if block.starters else 0.0

    return TeamAnalysis(
        roster_id=int(roster.get("roster_id") or 0),
        owner=owner,
        team_name=team_name,
        total_score=total,
        positions=positions,
        lineup=starters,
        player_count=len(entries),
    )


def add_league_context(
    teams: list[TeamAnalysis], roster_positions: list[str] | None = None
) -> None:
    """Compara cada posición con el resto de la liga y reparte veredictos."""
    all_positions = {p for team in teams for p in team.positions}
    if roster_positions is not None:
        all_positions &= startable_positions(roster_positions)

    for position in all_positions:
        scores = [
            team.positions[position].starter_score
            for team in teams
            if position in team.positions
        ]
        # Un equipo sin nadie en esa posición cuenta como cero: es real, le falta.
        scores += [0.0] * (len(teams) - len(scores))
        league_avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        league_best = round(max(scores), 2) if scores else 0.0

        ordenados = sorted(scores, reverse=True)
        for team in teams:
            block = team.positions.get(position)
            if block is None:
                block = PositionStrength(position=position)
                team.positions[position] = block
            block.league_avg = league_avg
            block.league_best = league_best
            block.gap_to_best = round(league_best - block.starter_score, 2)
            block.percentile = _percentile(block.starter_score, scores)
            block.rank_in_league = ordenados.index(block.starter_score) + 1
            if block.percentile <= WEAK_PERCENTILE:
                block.verdict = "débil"
            elif block.percentile >= STRONG_PERCENTILE:
                block.verdict = "fuerte"
            else:
                block.verdict = "medio"

    totals = sorted((team.total_score for team in teams), reverse=True)
    for team in teams:
        team.rank_in_league = totals.index(team.total_score) + 1
        team.weaknesses = sorted(
            (p for p, b in team.positions.items() if b.verdict == "débil"),
            key=lambda p: team.positions[p].percentile,
        )
        team.strengths = sorted(
            (p for p, b in team.positions.items() if b.verdict == "fuerte"),
            key=lambda p: -team.positions[p].percentile,
        )


def find_surplus(team: TeamAnalysis, teams: list[TeamAnalysis]) -> list[RankedPlayer]:
    """Suplentes tuyos que serían titulares en otro equipo: valor parado."""
    surplus: list[RankedPlayer] = []
    for position, block in team.positions.items():
        # Nota del peor titular de cada equipo en esa posición.
        peores_titulares = [
            min((s.score for s in other.positions[position].starters), default=None)
            for other in teams
            if other.roster_id != team.roster_id and position in other.positions
        ]
        umbrales = [u for u in peores_titulares if u is not None]
        if not umbrales:
            continue
        umbral = sorted(umbrales)[len(umbrales) // 2]  # mediana
        for suplente in block.bench:
            if suplente.score > umbral:
                surplus.append(suplente)
    surplus.sort(key=lambda r: -r.score)
    return surplus


def _team_entries(team: TeamAnalysis) -> list[RankedPlayer]:
    """Todos los jugadores de un equipo, titulares y suplentes."""
    entries: list[RankedPlayer] = []
    for block in team.positions.values():
        entries.extend(block.starters)
        entries.extend(block.bench)
    return entries


def find_trades(
    me: TeamAnalysis,
    teams: list[TeamAnalysis],
    roster_positions: list[str] | None,
    *,
    max_ideas: int = 12,
    min_gain: float = 0.5,
) -> list[TradeIdea]:
    """Intercambios uno por uno que mejoran la alineación de las dos partes.

    Se recorren mis posiciones débiles, se busca a quién le sobra ahí, y se
    comprueba de verdad —recalculando las dos alineaciones— que el cambio suma
    para los dos. Si solo gana uno, no es una propuesta, es un favor.
    """
    if not me.weaknesses:
        return []

    mis_jugadores = _team_entries(me)
    mis_ids = {e.player.player_id for e in mis_jugadores}
    base_mia = lineup_value(mis_jugadores, roster_positions)

    ideas: list[TradeIdea] = []

    for otro in teams:
        if otro.roster_id == me.roster_id:
            continue
        sus_jugadores = _team_entries(otro)
        base_suya = lineup_value(sus_jugadores, roster_positions)

        # Lo que puedo pedir: jugadores suyos en mis posiciones débiles.
        candidatos = [
            e
            for e in sus_jugadores
            if primary_position(e.player) in me.weaknesses
            and e.player.player_id not in mis_ids
        ]
        # Lo que puedo ofrecer: mis excedentes y mis posiciones fuertes.
        ofertas = [
            e
            for e in mis_jugadores
            if primary_position(e.player) in me.strengths or e in me.surplus
        ]
        if not candidatos or not ofertas:
            continue

        for pedido in sorted(candidatos, key=lambda r: -r.score)[:6]:
            for oferta in sorted(ofertas, key=lambda r: -r.score)[:6]:
                if primary_position(oferta.player) == primary_position(pedido.player):
                    continue  # cambiar un WR por otro WR no arregla nada

                nueva_mia = [e for e in mis_jugadores if e is not oferta] + [pedido]
                nueva_suya = [e for e in sus_jugadores if e is not pedido] + [oferta]

                mi_ganancia = round(lineup_value(nueva_mia, roster_positions) - base_mia, 2)
                su_ganancia = round(lineup_value(nueva_suya, roster_positions) - base_suya, 2)

                if mi_ganancia < min_gain or su_ganancia < min_gain:
                    continue

                diferencia = abs(pedido.score - oferta.score)
                fairness = round(max(0.0, 100.0 - diferencia * 4), 1)

                ideas.append(
                    TradeIdea(
                        partner_roster_id=otro.roster_id,
                        partner_owner=otro.owner,
                        partner_team_name=otro.team_name,
                        give=[oferta],
                        get=[pedido],
                        my_gain=mi_ganancia,
                        their_gain=su_ganancia,
                        fairness=fairness,
                        rationale=[
                            f"Tapas tu hueco en {primary_position(pedido.player)}: "
                            f"+{mi_ganancia:.1f} en tu alineación",
                            f"A {otro.team_name or otro.owner or 'ese equipo'} le sobra "
                            f"{primary_position(pedido.player)} y le falta "
                            f"{primary_position(oferta.player)}: +{su_ganancia:.1f} para él",
                            f"Notas: das {oferta.score:.1f}, recibes {pedido.score:.1f}",
                        ],
                    )
                )

    # Mejor primero lo que más me da, sin proponer dos veces al mismo jugador.
    ideas.sort(key=lambda i: (-(i.my_gain + i.their_gain), -i.fairness))
    vistas: set[tuple[str, str]] = set()
    unicas: list[TradeIdea] = []
    for idea in ideas:
        clave = (idea.give[0].player.player_id, idea.get[0].player.player_id)
        if clave in vistas:
            continue
        vistas.add(clave)
        unicas.append(idea)
        if len(unicas) >= max_ideas:
            break
    return unicas


def analyze_league(
    league: dict[str, Any],
    rosters: list[dict[str, Any]],
    users: list[dict[str, Any]],
    ranked: list[RankedPlayer],
    *,
    my_user_id: str | None = None,
    my_username: str | None = None,
    scoring: str = "ppr",
    max_trade_ideas: int = 12,
) -> LeagueAnalysis:
    """Análisis completo: equipos, puntos débiles e ideas de intercambio."""
    ranked_by_id = {entry.player.player_id: entry for entry in ranked}
    roster_positions = league.get("roster_positions") or DEFAULT_ROSTER_POSITIONS
    users_by_id = {str(u.get("user_id")): u for u in users or []}

    warnings: list[str] = []
    # ¿Se ha pedido identificar a alguien? Distinguirlo de "no encontrado" es lo
    # que permite dar el aviso correcto más abajo.
    identidad_pedida = bool(my_user_id or (my_username or "").strip())

    # Si no me dan el id de usuario, se deduce del nombre. Se comparan tanto
    # el nombre visible en la liga como el del login: no siempre coinciden.
    if not my_user_id and my_username:
        buscado = my_username.strip().lower()
        for user in users or []:
            nombres = {
                str(user.get(campo, "")).strip().lower()
                for campo in ("display_name", "username")
            }
            if buscado in nombres and buscado:
                my_user_id = str(user.get("user_id"))
                break

    teams = [
        analyze_team(roster, ranked_by_id, roster_positions, users_by_id)
        for roster in rosters or []
    ]
    add_league_context(teams, roster_positions)
    for team in teams:
        team.surplus = find_surplus(team, teams)

    me: TeamAnalysis | None = None
    if my_user_id:
        for roster, team in zip(rosters or [], teams):
            if str(roster.get("owner_id")) == str(my_user_id):
                team.is_me = True
                me = team
                break

    if me is None:
        if identidad_pedida:
            # Se dio un usuario pero no aparece en la liga. Listar los mánagers
            # reales permite ver el fallo de un vistazo: casi siempre es que el
            # nombre visible en la liga no es el del login.
            managers = sorted(
                {
                    str(u.get("display_name") or u.get("username") or "?")
                    for u in users or []
                }
            )
            warnings.append(
                "No encontré tu equipo en esta liga. Los mánagers que veo son: "
                + (", ".join(managers) if managers else "ninguno")
                + ". Revisa SLEEPER_USERNAME, o pon directamente tu SLEEPER_USER_ID."
            )
        else:
            warnings.append(
                "Sin SLEEPER_USERNAME ni SLEEPER_USER_ID solo puedo mostrar la liga entera, "
                "no señalar cuál es tu equipo."
            )

    trade_ideas: list[TradeIdea] = []
    if me is not None:
        trade_ideas = find_trades(me, teams, roster_positions, max_ideas=max_trade_ideas)
        if not trade_ideas and me.weaknesses:
            warnings.append(
                "No hay intercambios uno por uno que mejoren a las dos partes ahora mismo: "
                "para tapar tus huecos toca el mercado de agentes libres."
            )

    teams.sort(key=lambda t: -t.total_score)

    return LeagueAnalysis(
        league_id=str(league.get("league_id") or ""),
        league_name=league.get("name"),
        season=str(league.get("season") or "") or None,
        scoring=scoring,
        roster_positions=list(roster_positions),
        teams=teams,
        me=me,
        trade_ideas=trade_ideas,
        generated_at=datetime.now(timezone.utc),
        warnings=warnings,
    )
