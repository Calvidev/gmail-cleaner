"""Motor de ranking: ordena a los jugadores del mejor al peor.

La nota final va de 0 a 100 y se compone de seis piezas, todas visibles en la
interfaz para que el ranking se pueda discutir en vez de creer a ciegas:

  consenso      Dónde lo coloca el mercado (`search_rank` de Sleeper).
  producción    Puntos fantasy por partido; si aún no hay partidos, proyección.
  oportunidad   Puesto en el depth chart y si tiene equipo.
  momentum      Altas y bajas recientes en las ligas de Sleeper.
  disponibilidad Estado y parte de lesión.
  edad          Curva de rendimiento por edad y posición.

Además se aplica un multiplicador de valor posicional (un QB en liga de 1 QB
vale menos que un RB con los mismos puntos) y un castigo duro si el jugador
está fuera (IR, suspendido, sin equipo).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from app.models import Player, RankedPlayer, ScoreBreakdown

# --- Constantes de configuración del modelo ---------------------------------

SCORING_FORMATS = {"ppr": 1.0, "half_ppr": 0.5, "standard": 0.0}

DEFAULT_WEIGHTS = {
    "consensus": 0.34,
    "production": 0.26,
    "opportunity": 0.14,
    "momentum": 0.08,
    "availability": 0.11,
    "age_curve": 0.07,
}

# Cuánto vale cada posición en una liga estándar de 1 QB.
POSITION_VALUE = {
    "QB": 0.88,
    "RB": 1.00,
    "WR": 0.99,
    "TE": 0.90,
    "K": 0.55,
    "DEF": 0.58,
}

# Ajuste por formato: en PPR los receptores suben, en estándar bajan.
SCORING_ADJUST = {
    "ppr": {"WR": 1.03, "TE": 1.03, "RB": 0.98},
    "half_ppr": {},
    "standard": {"WR": 0.96, "TE": 0.96, "RB": 1.04},
}

# Edad de máximo rendimiento y cuánto castiga alejarse de ella.
AGE_CURVES = {
    "QB": (29.0, 0.055),
    "RB": (25.0, 0.115),
    "WR": (26.5, 0.075),
    "TE": (27.5, 0.070),
    "K": (30.0, 0.030),
    "DEF": (28.0, 0.010),
}

# Multiplicador final por estado de lesión.
INJURY_MULTIPLIER = {
    "ir": 0.35,
    "injured reserve": 0.35,
    "pup": 0.40,
    "nfi": 0.40,
    "sus": 0.45,
    "suspended": 0.45,
    "out": 0.55,
    "doubtful": 0.70,
    "questionable": 0.90,
    "probable": 0.97,
    "dtd": 0.92,
    "day-to-day": 0.92,
}

INACTIVE_STATUSES = {
    "inactive": 0.45,
    "injured reserve": 0.35,
    "physically unable to perform": 0.40,
    "non football injury": 0.40,
    "practice squad": 0.55,
    "suspended": 0.45,
    "retired": 0.05,
}

# `search_rank` por encima de esto ya es ruido (jugadores irrelevantes).
MAX_SEARCH_RANK = 900

TIER_BREAK = 3.5  # caída de nota que abre un nuevo tier


# --- Utilidades --------------------------------------------------------------


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _percentile_scale(value: float, reference: float) -> float:
    """Escala un valor a 0-100 tomando `reference` como el tope (100)."""
    if reference <= 0:
        return 0.0
    return _clamp(100.0 * value / reference)


def fantasy_points(stats: dict | None, scoring: str = "ppr") -> float:
    """Puntos fantasy de un bloque de estadísticas de Sleeper.

    Sleeper ya devuelve `pts_ppr` / `pts_half_ppr` / `pts_std`. Si faltan, se
    calculan a mano con las estadísticas básicas.
    """
    if not stats:
        return 0.0
    key = {"ppr": "pts_ppr", "half_ppr": "pts_half_ppr", "standard": "pts_std"}.get(
        scoring, "pts_ppr"
    )
    for candidate in (key, "pts_ppr", "pts_half_ppr", "pts_std"):
        value = stats.get(candidate)
        if isinstance(value, (int, float)):
            return float(value)

    reception_value = SCORING_FORMATS.get(scoring, 1.0)
    points = 0.0
    points += float(stats.get("pass_yd") or 0) * 0.04
    points += float(stats.get("pass_td") or 0) * 4
    points -= float(stats.get("pass_int") or 0) * 1
    points += float(stats.get("rush_yd") or 0) * 0.1
    points += float(stats.get("rush_td") or 0) * 6
    points += float(stats.get("rec") or 0) * reception_value
    points += float(stats.get("rec_yd") or 0) * 0.1
    points += float(stats.get("rec_td") or 0) * 6
    points -= float(stats.get("fum_lost") or 0) * 2
    points += float(stats.get("pass_2pt") or 0) * 2
    points += float(stats.get("rush_2pt") or 0) * 2
    points += float(stats.get("rec_2pt") or 0) * 2
    return round(points, 2)


def games_played(stats: dict | None) -> int:
    if not stats:
        return 0
    for key in ("gp", "gms_active", "gs"):
        value = stats.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    return 0


def primary_position(player: Player) -> str:
    """Posición con la que se rankea al jugador."""
    if player.position in POSITION_VALUE:
        return player.position
    for pos in player.fantasy_positions:
        if pos in POSITION_VALUE:
            return pos
    return player.position or "UNK"


# --- Componentes de la nota --------------------------------------------------


def consensus_score(player: Player) -> float:
    """Nota por el ranking de consenso de Sleeper (menor rank = mejor)."""
    rank = player.search_rank
    if rank is None or rank <= 0 or rank > 10 * MAX_SEARCH_RANK:
        return 12.0  # desconocido: nota baja pero no cero
    rank = min(rank, MAX_SEARCH_RANK)
    # Curva logarítmica: la diferencia entre el 1 y el 10 pesa mucho más que
    # la que hay entre el 300 y el 310.
    return _clamp(100.0 * (1.0 - math.log(rank) / math.log(MAX_SEARCH_RANK)))


def opportunity_score(player: Player) -> float:
    """Nota por volumen esperado: puesto en el depth chart y equipo."""
    if not player.team:
        return 5.0  # agente libre sin equipo: no juega
    order = player.depth_chart_order
    position = primary_position(player)
    if order is None:
        return 45.0
    if position in ("K", "DEF"):
        return 90.0 if order <= 1 else 30.0
    if position == "WR":
        table = {1: 96.0, 2: 86.0, 3: 66.0, 4: 38.0, 5: 20.0}
    elif position == "RB":
        table = {1: 97.0, 2: 62.0, 3: 30.0, 4: 15.0, 5: 8.0}
    elif position == "TE":
        table = {1: 92.0, 2: 42.0, 3: 18.0, 4: 10.0}
    else:  # QB
        table = {1: 98.0, 2: 22.0, 3: 8.0}
    return table.get(order, 6.0)


def momentum_score(adds: int, drops: int, max_adds: int) -> float:
    """Nota por interés reciente: altas menos bajas, en escala logarítmica."""
    if max_adds <= 0:
        return 50.0
    net = adds - 0.6 * drops
    if net <= 0:
        # Más cortes que altas: por debajo de la media.
        penalty = min(30.0, math.log1p(abs(net)) * 6.0)
        return _clamp(50.0 - penalty)
    scaled = math.log1p(net) / math.log1p(max_adds)
    return _clamp(50.0 + 50.0 * scaled)


def availability_score(player: Player) -> float:
    """Nota por disponibilidad (100 = sano y activo)."""
    score = 100.0
    injury = (player.injury_status or "").strip().lower()
    if injury:
        score *= INJURY_MULTIPLIER.get(injury, 0.85)
    status = (player.status or "").strip().lower()
    if status and status != "active":
        score *= INACTIVE_STATUSES.get(status, 0.80)
    if not player.team:
        score *= 0.30
    return _clamp(score)


def age_score(player: Player) -> float:
    """Nota por curva de edad, específica de cada posición."""
    if player.age is None:
        # Sin edad: los novatos suelen ser los que faltan, nota neutra-alta.
        return 60.0
    position = primary_position(player)
    peak, decay = AGE_CURVES.get(position, (27.0, 0.07))
    distance = player.age - peak
    # Envejecer castiga más que ser joven (un rookie aún puede explotar).
    penalty = decay * (distance**2) if distance > 0 else decay * 0.55 * (distance**2)
    return _clamp(100.0 - penalty * 10.0)


def production_score(
    ppg_actual: float,
    games: int,
    ppg_projected: float,
    reference_ppg: float,
) -> float:
    """Nota por producción: real si ya hay partidos, proyectada si no."""
    actual = _percentile_scale(ppg_actual, reference_ppg)
    projected = _percentile_scale(ppg_projected, reference_ppg)

    if games >= 4:
        return actual
    if games >= 1:
        # Muestra corta: se mezcla con la proyección para no sobrerreaccionar.
        weight = games / 4.0
        return actual * weight + projected * (1 - weight)
    return projected


def position_multiplier(position: str, scoring: str, superflex: bool = False) -> float:
    """Cuánto vale la posición en el formato elegido."""
    base = POSITION_VALUE.get(position, 0.6)
    base *= SCORING_ADJUST.get(scoring, {}).get(position, 1.0)
    if superflex and position == "QB":
        base = 1.06
    return base


def injury_multiplier(player: Player) -> float:
    """Castigo duro y directo por lesión grave o inactividad."""
    multiplier = 1.0
    injury = (player.injury_status or "").strip().lower()
    if injury in ("ir", "injured reserve", "out", "pup", "nfi", "sus", "suspended"):
        multiplier *= 0.62
    status = (player.status or "").strip().lower()
    if status in ("injured reserve", "inactive", "retired", "suspended"):
        multiplier *= 0.60
    if not player.team:
        multiplier *= 0.45
    return multiplier


# --- Explicaciones legibles --------------------------------------------------


def build_reasons(
    player: Player,
    ppg: float,
    games: int,
    projected: float,
    adds: int,
    drops: int,
) -> list[str]:
    """Frases cortas que explican por qué el jugador está donde está."""
    reasons: list[str] = []
    position = primary_position(player)

    if player.search_rank and player.search_rank <= 50:
        reasons.append(f"Top {player.search_rank} del consenso de Sleeper")

    if games and ppg:
        reasons.append(f"{ppg:.1f} pts/partido en {games} {'partido' if games == 1 else 'partidos'}")
    elif projected:
        reasons.append(f"Proyección de {projected:.1f} pts/partido")

    if player.team and player.depth_chart_order:
        reasons.append(f"{position}{player.depth_chart_order} en el depth chart de {player.team}")
    elif not player.team:
        reasons.append("Sin equipo: agente libre")

    if player.injury_status:
        note = player.injury_status
        if player.injury_body_part:
            note += f" ({player.injury_body_part})"
        reasons.append(f"Lesión: {note}")
    elif player.status and player.status.lower() != "active":
        reasons.append(f"Estado: {player.status}")

    if adds >= 1000:
        reasons.append(f"Tendencia: +{adds:,} altas en 24 h".replace(",", "."))
    elif drops >= 1000:
        reasons.append(f"Tendencia: -{drops:,} bajas en 24 h".replace(",", "."))

    if player.years_exp == 0:
        reasons.append("Rookie")

    return reasons


# --- Motor -------------------------------------------------------------------


def assign_tiers(ranked: list[RankedPlayer], gap: float = TIER_BREAK) -> None:
    """Agrupa en tiers: se abre uno nuevo cuando la nota da un salto grande."""
    tier = 1
    previous: float | None = None
    for entry in ranked:
        if previous is not None and (previous - entry.score) >= gap:
            tier += 1
        entry.tier = tier
        previous = entry.score


def rank_players(
    players: dict[str, Player],
    *,
    stats: dict[str, dict] | None = None,
    projections: dict[str, dict] | None = None,
    trending_add: dict[str, int] | None = None,
    trending_drop: dict[str, int] | None = None,
    scoring: str = "ppr",
    superflex: bool = False,
    weights: dict[str, float] | None = None,
) -> list[RankedPlayer]:
    """Devuelve todos los jugadores ordenados del mejor al peor."""
    stats = stats or {}
    projections = projections or {}
    trending_add = trending_add or {}
    trending_drop = trending_drop or {}
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    if scoring not in SCORING_FORMATS:
        scoring = "ppr"

    max_adds = max(trending_add.values(), default=0)

    # Paso 1: métricas crudas por jugador.
    metrics: dict[str, dict[str, float]] = {}
    for pid, player in players.items():
        player_stats = stats.get(pid)
        player_proj = projections.get(pid)
        games = games_played(player_stats)
        points = fantasy_points(player_stats, scoring)
        ppg = points / games if games else 0.0
        proj_points = fantasy_points(player_proj, scoring)
        # Las proyecciones de temporada de Sleeper vienen en total; 17 partidos.
        proj_ppg = proj_points / 17 if proj_points > 40 else proj_points
        metrics[pid] = {
            "games": games,
            "points": points,
            "ppg": ppg,
            "proj_points": proj_points,
            "proj_ppg": proj_ppg,
        }

    # Paso 2: referencia de producción por posición (percentil 95 aprox.).
    references: dict[str, float] = {}
    by_position: dict[str, list[float]] = {}
    for pid, player in players.items():
        position = primary_position(player)
        value = max(metrics[pid]["ppg"], metrics[pid]["proj_ppg"])
        if value > 0:
            by_position.setdefault(position, []).append(value)
    for position, values in by_position.items():
        values.sort(reverse=True)
        index = max(0, min(len(values) - 1, int(len(values) * 0.05)))
        references[position] = values[index] or 1.0

    # Paso 3: nota de cada jugador.
    ranked: list[RankedPlayer] = []
    for pid, player in players.items():
        position = primary_position(player)
        m = metrics[pid]
        adds = trending_add.get(pid, 0)
        drops = trending_drop.get(pid, 0)

        breakdown = ScoreBreakdown(
            consensus=round(consensus_score(player), 2),
            production=round(
                production_score(
                    m["ppg"], int(m["games"]), m["proj_ppg"], references.get(position, 1.0)
                ),
                2,
            ),
            opportunity=round(opportunity_score(player), 2),
            momentum=round(momentum_score(adds, drops, max_adds), 2),
            availability=round(availability_score(player), 2),
            age_curve=round(age_score(player), 2),
        )

        raw = sum(
            getattr(breakdown, component) * weight for component, weight in weights.items()
        )
        score = raw * position_multiplier(position, scoring, superflex)
        score *= injury_multiplier(player)

        ranked.append(
            RankedPlayer(
                rank=0,
                score=round(_clamp(score), 2),
                player=player,
                breakdown=breakdown,
                reasons=build_reasons(
                    player, m["ppg"], int(m["games"]), m["proj_ppg"], adds, drops
                ),
                trend_adds=adds or None,
                trend_drops=drops or None,
                points=round(m["points"], 2) or None,
                points_per_game=round(m["ppg"], 2) or None,
                games=int(m["games"]) or None,
                projected_points=round(m["proj_points"], 2) or None,
            )
        )

    # Paso 4: ordenar y numerar. El desempate por `search_rank` mantiene el
    # orden estable entre jugadores con la misma nota.
    ranked.sort(
        key=lambda r: (-r.score, r.player.search_rank or 10**6, r.player.name)
    )
    position_counters: dict[str, int] = {}
    for index, entry in enumerate(ranked, start=1):
        entry.rank = index
        position = primary_position(entry.player)
        position_counters[position] = position_counters.get(position, 0) + 1
        entry.position_rank = position_counters[position]

    assign_tiers(ranked)
    return ranked


def filter_ranked(
    ranked: list[RankedPlayer],
    *,
    position: str | None = None,
    team: str | None = None,
    search: str | None = None,
    available_only: set[str] | None = None,
    max_age: int | None = None,
    injured_only: bool = False,
    hide_injured: bool = False,
) -> list[RankedPlayer]:
    """Aplica los filtros de la interfaz sin recalcular el ranking."""
    result = ranked

    if position and position.upper() != "ALL":
        wanted = {p.strip().upper() for p in position.split(",") if p.strip()}
        result = [
            r
            for r in result
            if primary_position(r.player) in wanted
            or wanted & set(r.player.fantasy_positions)
        ]

    if team and team.upper() != "ALL":
        wanted_teams = {t.strip().upper() for t in team.split(",") if t.strip()}
        result = [r for r in result if (r.player.team or "").upper() in wanted_teams]

    if search:
        needle = search.strip().lower()
        result = [
            r
            for r in result
            if needle in r.player.name.lower()
            or needle in (r.player.team or "").lower()
            or needle in (r.player.college or "").lower()
        ]

    if available_only is not None:
        result = [r for r in result if r.player.player_id not in available_only]

    if max_age is not None:
        result = [r for r in result if r.player.age is None or r.player.age <= max_age]

    if injured_only:
        result = [r for r in result if r.player.injury_status]
    elif hide_injured:
        result = [
            r
            for r in result
            if (r.player.injury_status or "").lower() not in ("ir", "out", "pup", "nfi", "sus")
        ]

    return result


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
