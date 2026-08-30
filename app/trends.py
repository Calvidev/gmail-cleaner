"""Tendencias jornada a jornada: quién sube y quién baja, antes que el marcador.

La idea de fondo: **los puntos van por detrás del uso**. Cuando a un receptor
empiezan a tirarle más balones o un corredor sube su cuota de snaps, los puntos
llegan una o dos jornadas después. Así que la tendencia se calcula sobre todo
con volumen —objetivos, acarreos, snaps— y solo en parte con los puntos ya
anotados.

Para cada jugador se mira su serie de las últimas jornadas y se comparan las
dos más recientes contra las tres anteriores, además de la pendiente de la
recta que mejor ajusta la serie completa.
"""

from __future__ import annotations

from typing import Any

from app.models import MetricTrend, Player, PlayerTrend, WeekUsage
from app.ranking import fantasy_points, primary_position

# Métricas que se siguen, con su etiqueta y su peso en la nota de tendencia.
# El uso pesa el triple que los puntos: es lo que se adelanta.
TRACKED_METRICS: dict[str, tuple[str, float]] = {
    "opportunities": ("Oportunidades", 0.34),
    "targets": ("Objetivos", 0.22),
    "snap_share": ("Cuota de snaps", 0.24),
    "points": ("Puntos", 0.20),
}

# Métricas de volumen: sin ninguna de ellas la tendencia es solo ruido de puntos.
USAGE_METRICS = ("opportunities", "targets", "snap_share", "carries")

# Cuánto se rebaja la tendencia de quien no tiene datos de volumen (pateadores
# y defensas): sus puntos saltan de una jornada a otra sin que eso signifique
# nada sobre la siguiente.
NO_USAGE_DAMPING = 0.5

RECENT_WEEKS = 2  # jornadas que forman la "foto reciente"
MIN_WEEKS = 3  # menos de esto no da para hablar de tendencia
RISING_THRESHOLD = 12.0
FALLING_THRESHOLD = -12.0


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def linear_slope(values: list[float]) -> float:
    """Pendiente de la recta de mínimos cuadrados de una serie."""
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    numerator = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    denominator = sum((i - mean_x) ** 2 for i in range(n))
    return numerator / denominator if denominator else 0.0


def split_means(values: list[float], recent: int = RECENT_WEEKS) -> tuple[float | None, float | None]:
    """Media de las últimas `recent` jornadas y media de las anteriores."""
    if len(values) < 2:
        return (values[0] if values else None), None
    recent = min(recent, len(values) - 1)
    tail = values[-recent:]
    head = values[:-recent]
    return sum(tail) / len(tail), (sum(head) / len(head) if head else None)


def team_target_totals(
    week_stats: dict[str, dict[str, Any]], players: dict[str, Player]
) -> dict[str, float]:
    """Objetivos totales de cada equipo en una jornada.

    Sleeper no da la cuota de objetivos, así que se suma la de sus jugadores.
    """
    totals: dict[str, float] = {}
    for pid, stats in week_stats.items():
        player = players.get(pid)
        if player is None or not player.team:
            continue
        targets = _num(stats.get("rec_tgt"))
        if targets:
            totals[player.team] = totals.get(player.team, 0.0) + targets
    return totals


def build_week_usage(
    week: int,
    stats: dict[str, Any],
    team_targets: float | None,
    scoring: str = "ppr",
) -> WeekUsage:
    """Normaliza las estadísticas de una jornada a métricas de uso."""
    targets = _num(stats.get("rec_tgt"))
    carries = _num(stats.get("rush_att"))
    receptions = _num(stats.get("rec"))
    snaps = _num(stats.get("off_snp"))
    team_snaps = _num(stats.get("tm_off_snp"))

    opportunities = None
    if targets is not None or carries is not None:
        opportunities = (targets or 0.0) + (carries or 0.0)

    snap_share = None
    if snaps is not None and team_snaps:
        snap_share = round(min(1.0, snaps / team_snaps), 4)

    target_share = None
    if targets is not None and team_targets:
        target_share = round(min(1.0, targets / team_targets), 4)

    yards = (_num(stats.get("rec_yd")) or 0.0) + (_num(stats.get("rush_yd")) or 0.0)
    yards += _num(stats.get("pass_yd")) or 0.0
    touchdowns = (
        (_num(stats.get("rec_td")) or 0.0)
        + (_num(stats.get("rush_td")) or 0.0)
        + (_num(stats.get("pass_td")) or 0.0)
    )

    return WeekUsage(
        week=week,
        snaps=int(snaps) if snaps is not None else None,
        snap_share=snap_share,
        targets=int(targets) if targets is not None else None,
        target_share=target_share,
        carries=int(carries) if carries is not None else None,
        receptions=int(receptions) if receptions is not None else None,
        opportunities=int(opportunities) if opportunities is not None else None,
        yards=round(yards, 1) or None,
        touchdowns=touchdowns or None,
        points=round(fantasy_points(stats, scoring), 2),
    )


def _series(weeks: list[WeekUsage], metric: str) -> list[float]:
    """Valores de una métrica, saltándose las jornadas sin dato."""
    values: list[float] = []
    for week in weeks:
        value = getattr(week, metric, None)
        if value is not None:
            values.append(float(value))
    return values


def metric_trend(weeks: list[WeekUsage], metric: str, label: str) -> MetricTrend | None:
    """Evolución de una métrica concreta a lo largo de las jornadas."""
    values = _series(weeks, metric)
    if len(values) < 2:
        return None
    recent, previous = split_means(values)
    delta = None
    pct = None
    if recent is not None and previous is not None:
        delta = recent - previous
        pct = (delta / previous * 100.0) if previous else None
    return MetricTrend(
        metric=metric,
        label=label,
        recent=round(recent, 3) if recent is not None else None,
        previous=round(previous, 3) if previous is not None else None,
        delta=round(delta, 3) if delta is not None else None,
        pct_change=round(pct, 1) if pct is not None else None,
        slope=round(linear_slope(values), 4),
    )


def _normalized_change(trend: MetricTrend) -> float:
    """Cambio relativo de una métrica, acotado a [-1, 1]."""
    if trend.previous is None or trend.recent is None:
        return 0.0
    if trend.previous == 0:
        # Pasar de cero a algo es la señal más fuerte que hay.
        return 1.0 if trend.recent > 0 else 0.0
    change = (trend.recent - trend.previous) / abs(trend.previous)
    return max(-1.0, min(1.0, change))


def has_usage_data(metrics: dict[str, MetricTrend]) -> bool:
    """¿Hay datos de volumen, o solo puntos?"""
    return any(metric in metrics for metric in USAGE_METRICS)


def trend_score(metrics: dict[str, MetricTrend]) -> float:
    """Nota de tendencia de -100 (desplome) a +100 (despegue)."""
    total = 0.0
    weight_used = 0.0
    for metric, (_, weight) in TRACKED_METRICS.items():
        trend = metrics.get(metric)
        if trend is None:
            continue
        total += _normalized_change(trend) * weight
        weight_used += weight
    if weight_used == 0:
        return 0.0
    score = total / weight_used * 100.0
    if not has_usage_data(metrics):
        score *= NO_USAGE_DAMPING
    return round(max(-100.0, min(100.0, score)), 2)


def _format_share(value: float | None) -> str:
    return f"{value * 100:.0f} %" if value is not None else "—"


def build_signals(
    player: Player, weeks: list[WeekUsage], metrics: dict[str, MetricTrend]
) -> list[str]:
    """Frases que explican la tendencia en lenguaje llano."""
    signals: list[str] = []
    position = primary_position(player)

    targets = metrics.get("targets")
    if targets and targets.previous is not None and targets.recent is not None:
        if targets.delta and abs(targets.delta) >= 1.5:
            verbo = "más" if targets.delta > 0 else "menos"
            signals.append(
                f"Le tiran {verbo} la bola: {targets.previous:.1f} → "
                f"{targets.recent:.1f} objetivos por partido"
            )

    snaps = metrics.get("snap_share")
    if snaps and snaps.previous is not None and snaps.recent is not None:
        if snaps.delta and abs(snaps.delta) >= 0.06:
            signals.append(
                f"Cuota de snaps: {_format_share(snaps.previous)} → "
                f"{_format_share(snaps.recent)}"
            )

    opportunities = metrics.get("opportunities")
    if opportunities and opportunities.delta and abs(opportunities.delta) >= 2:
        verbo = "Más" if opportunities.delta > 0 else "Menos"
        signals.append(
            f"{verbo} volumen: {opportunities.previous:.1f} → "
            f"{opportunities.recent:.1f} oportunidades por partido"
        )

    points = metrics.get("points")
    if points and points.recent is not None and points.previous is not None:
        signals.append(
            f"Puntos: {points.previous:.1f} → {points.recent:.1f} por partido"
        )

    # Aviso útil: el uso sube pero los puntos aún no. Ahí está la ganga.
    if opportunities and points:
        subiendo = _normalized_change(opportunities) > 0.15
        sin_premio = _normalized_change(points) < 0.05
        if subiendo and sin_premio:
            signals.append(
                "El volumen sube pero los puntos todavía no: suele adelantarse a la explosión"
            )
        bajando = _normalized_change(opportunities) < -0.15
        con_premio = _normalized_change(points) > 0.05
        if bajando and con_premio:
            signals.append(
                "Los puntos aguantan pero el volumen cae: ojo, puede ser humo de touchdowns"
            )

    if position == "RB" and metrics.get("carries"):
        pass  # los acarreos ya entran en oportunidades

    return signals


def direction_of(score: float, games: int) -> str:
    if games < MIN_WEEKS:
        return "sin datos"
    if score >= RISING_THRESHOLD:
        return "alza"
    if score <= FALLING_THRESHOLD:
        return "baja"
    return "estable"


def compute_trends(
    players: dict[str, Player],
    weekly_stats: dict[int, dict[str, dict[str, Any]]],
    *,
    scoring: str = "ppr",
    min_weeks: int = MIN_WEEKS,
) -> list[PlayerTrend]:
    """Calcula la tendencia de cada jugador con las jornadas disponibles.

    `weekly_stats` es `{jornada: {player_id: estadísticas}}`.
    """
    if not weekly_stats:
        return []

    ordered_weeks = sorted(weekly_stats)
    # La cuota de objetivos necesita el total de cada equipo en cada jornada.
    team_totals = {
        week: team_target_totals(weekly_stats[week], players) for week in ordered_weeks
    }

    trends: list[PlayerTrend] = []
    for pid, player in players.items():
        weeks: list[WeekUsage] = []
        for week in ordered_weeks:
            stats = weekly_stats[week].get(pid)
            if not stats:
                continue  # descanso, lesión o no jugó: no cuenta como bajón
            usage = build_week_usage(
                week,
                stats,
                team_totals[week].get(player.team) if player.team else None,
                scoring,
            )
            # Una jornada sin ninguna participación no aporta información.
            if not any(
                (usage.snaps, usage.opportunities, usage.points, usage.receptions)
            ):
                continue
            weeks.append(usage)

        if len(weeks) < min_weeks:
            continue

        metrics: dict[str, MetricTrend] = {}
        for metric, (label, _) in TRACKED_METRICS.items():
            trend = metric_trend(weeks, metric, label)
            if trend is not None:
                metrics[metric] = trend
        for metric, label in (("carries", "Acarreos"), ("target_share", "Cuota de objetivos")):
            trend = metric_trend(weeks, metric, label)
            if trend is not None:
                metrics[metric] = trend

        score = trend_score(metrics)
        usage_based = has_usage_data(metrics)
        signals = build_signals(player, weeks, metrics)
        if not usage_based:
            signals.append(
                "Sin datos de volumen: la tendencia sale solo de los puntos, que rebotan mucho"
            )
        trends.append(
            PlayerTrend(
                player=player,
                direction=direction_of(score, len(weeks)),
                trend_score=score,
                weeks=weeks,
                metrics=metrics,
                signals=signals,
                games_tracked=len(weeks),
                usage_based=usage_based,
            )
        )

    trends.sort(key=lambda t: -t.trend_score)
    return trends


def filter_trends(
    trends: list[PlayerTrend],
    *,
    direction: str | None = None,
    position: str | None = None,
    team: str | None = None,
    search: str | None = None,
    min_games: int | None = None,
    usage_only: bool = False,
    available_only: set[str] | None = None,
) -> list[PlayerTrend]:
    """Filtros de la vista de tendencias."""
    result = trends

    if usage_only:
        result = [t for t in result if t.usage_based]

    if direction and direction.lower() not in ("all", "todos"):
        wanted = direction.lower()
        result = [t for t in result if t.direction == wanted]

    if position and position.upper() != "ALL":
        wanted_positions = {p.strip().upper() for p in position.split(",") if p.strip()}
        result = [
            t
            for t in result
            if primary_position(t.player) in wanted_positions
            or wanted_positions & set(t.player.fantasy_positions)
        ]

    if team and team.upper() != "ALL":
        wanted_teams = {t.strip().upper() for t in team.split(",") if t.strip()}
        result = [t for t in result if (t.player.team or "").upper() in wanted_teams]

    if search:
        needle = search.strip().lower()
        result = [t for t in result if needle in t.player.name.lower()]

    if min_games is not None:
        result = [t for t in result if t.games_tracked >= min_games]

    if available_only is not None:
        result = [t for t in result if t.player.player_id not in available_only]

    return result
