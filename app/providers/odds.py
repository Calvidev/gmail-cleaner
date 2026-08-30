"""Cuotas de las casas de apuestas: el mercado como segunda opinión.

Las casas mueven millones ajustando líneas, así que su lectura de un partido es
un punto de vista independiente del consenso de fantasy. Lo más útil no es el
ganador, sino el **total implícito** de cada equipo: cuántos puntos se le
suponen a un ataque esta jornada. Sale de dos números públicos:

    total implícito del favorito = (total + |spread|) / 2
    total implícito del no favorito = (total - |spread|) / 2

Un ataque con 28 puntos implícitos reparte muchos más puntos de fantasy que uno
con 17, y eso no depende de lo bueno que sea el jugador.

Fuentes:
* **ESPN** (sin llave): spread y total de cada partido. Es lo que se usa por
  defecto.
* **The Odds API** (opcional, con `ODDS_API_KEY`): añade props de jugador
  —yardas de recepción, recepciones, TD— que es donde el mercado se moja de
  verdad con nombres propios. Tiene plan gratuito.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from app.cache import TTLCache
from app.config import Settings
from app.matching import build_name_index, match_players
from app.models import GameOdds, Player, PlayerProp, TeamOdds

# ESPN y Sleeper no siempre usan la misma abreviatura.
TEAM_ALIASES = {
    "WSH": "WAS",
    "JAC": "JAX",
    "LA": "LAR",
    "SD": "LAC",
    "OAK": "LV",
    "STL": "LAR",
}

# Mercados de props que interesan en fantasy, con su etiqueta.
PROP_MARKETS = {
    "player_pass_yds": "Yardas de pase",
    "player_pass_tds": "Pases de anotación",
    "player_rush_yds": "Yardas terrestres",
    "player_reception_yds": "Yardas de recepción",
    "player_receptions": "Recepciones",
    "player_anytime_td": "Anota un touchdown",
}


def normalize_team(abbr: str | None) -> str | None:
    if not abbr:
        return None
    upper = abbr.strip().upper()
    return TEAM_ALIASES.get(upper, upper)


def implied_totals(total: float | None, spread: float | None) -> tuple[float | None, float | None]:
    """Puntos implícitos de (local, visitante) a partir de total y spread.

    `spread` es relativo al local: -3.5 significa que el local es favorito.
    """
    if total is None or spread is None:
        return None, None
    home = (total - spread) / 2
    away = (total + spread) / 2
    return round(home, 2), round(away, 2)


def parse_espn_scoreboard(payload: dict[str, Any]) -> list[GameOdds]:
    """Extrae las cuotas del marcador público de ESPN."""
    games: list[GameOdds] = []
    for event in (payload or {}).get("events") or []:
        if not isinstance(event, dict):
            continue
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        competition = competitions[0]

        home = away = None
        for competitor in competition.get("competitors") or []:
            abbr = normalize_team(((competitor.get("team") or {}).get("abbreviation")))
            if competitor.get("homeAway") == "home":
                home = abbr
            elif competitor.get("homeAway") == "away":
                away = abbr
        if not home or not away:
            continue

        spread = total = None
        favorite = bookmaker = None
        odds_list = competition.get("odds") or []
        if odds_list and isinstance(odds_list[0], dict):
            odds = odds_list[0]
            bookmaker = (odds.get("provider") or {}).get("name")
            total = _to_float(odds.get("overUnder"))
            spread = _to_float(odds.get("spread"))
            details = odds.get("details")  # p.ej. "KC -3.5"
            if spread is None and isinstance(details, str):
                match = re.search(r"([A-Z]{2,4})\s*(-?\d+(?:\.\d+)?)", details)
                if match:
                    equipo = normalize_team(match.group(1))
                    valor = float(match.group(2))
                    # El spread se guarda siempre relativo al local.
                    spread = valor if equipo == home else -valor
            if spread is not None:
                favorite = home if spread < 0 else away

        home_implied, away_implied = implied_totals(total, spread)
        games.append(
            GameOdds(
                game_id=str(event.get("id") or f"{away}@{home}"),
                home=home,
                away=away,
                kickoff=_parse_dt(event.get("date")),
                spread=spread,
                total=total,
                home_implied=home_implied,
                away_implied=away_implied,
                favorite=favorite,
                bookmaker=bookmaker,
                source="ESPN",
            )
        )
    return games


def parse_odds_api_games(payload: Any) -> list[GameOdds]:
    """Normaliza la respuesta de The Odds API (spreads y totales)."""
    games: list[GameOdds] = []
    for event in payload or []:
        if not isinstance(event, dict):
            continue
        home = normalize_team(_abbr(event.get("home_team")))
        away = normalize_team(_abbr(event.get("away_team")))
        if not home or not away:
            continue

        spread = total = None
        bookmaker = None
        for book in event.get("bookmakers") or []:
            bookmaker = bookmaker or book.get("title")
            for market in book.get("markets") or []:
                key = market.get("key")
                for outcome in market.get("outcomes") or []:
                    if key == "spreads" and _abbr(outcome.get("name")) == _abbr(event.get("home_team")):
                        spread = _to_float(outcome.get("point"))
                    elif key == "totals" and total is None:
                        total = _to_float(outcome.get("point"))
            if spread is not None and total is not None:
                break

        home_implied, away_implied = implied_totals(total, spread)
        games.append(
            GameOdds(
                game_id=str(event.get("id") or f"{away}@{home}"),
                home=home,
                away=away,
                kickoff=_parse_dt(event.get("commence_time")),
                spread=spread,
                total=total,
                home_implied=home_implied,
                away_implied=away_implied,
                favorite=(home if (spread or 0) < 0 else away) if spread is not None else None,
                bookmaker=bookmaker,
                source="The Odds API",
            )
        )
    return games


def parse_props(payload: Any, players: dict[str, Player]) -> dict[str, list[PlayerProp]]:
    """Asocia las líneas de props de The Odds API con los jugadores."""
    name_index = build_name_index(players.values())
    result: dict[str, list[PlayerProp]] = {}

    events = payload if isinstance(payload, list) else [payload]
    for event in events:
        if not isinstance(event, dict):
            continue
        for book in event.get("bookmakers") or []:
            book_name = book.get("title")
            for market in book.get("markets") or []:
                key = market.get("key")
                if key not in PROP_MARKETS:
                    continue
                por_jugador: dict[str, dict[str, Any]] = {}
                for outcome in market.get("outcomes") or []:
                    nombre = outcome.get("description") or outcome.get("name")
                    if not nombre:
                        continue
                    matches = match_players(str(nombre), name_index)
                    if not matches:
                        continue
                    pid = matches[0]
                    entrada = por_jugador.setdefault(pid, {"line": None, "over": None, "under": None})
                    if entrada["line"] is None:
                        entrada["line"] = _to_float(outcome.get("point"))
                    lado = str(outcome.get("name", "")).lower()
                    precio = outcome.get("price")
                    if "over" in lado or key == "player_anytime_td":
                        entrada["over"] = _to_int(precio)
                    elif "under" in lado:
                        entrada["under"] = _to_int(precio)

                for pid, entrada in por_jugador.items():
                    result.setdefault(pid, []).append(
                        PlayerProp(
                            market=key,
                            label=PROP_MARKETS[key],
                            line=entrada["line"],
                            over_price=entrada["over"],
                            under_price=entrada["under"],
                            bookmaker=book_name,
                        )
                    )
    return result


def build_team_odds(games: list[GameOdds]) -> list[TeamOdds]:
    """Convierte los partidos en una tabla por equipo, ordenada por ataque."""
    teams: list[TeamOdds] = []
    for game in games:
        teams.append(
            TeamOdds(
                team=game.home, opponent=game.away, is_home=True,
                spread=game.spread, total=game.total, implied_total=game.home_implied,
                kickoff=game.kickoff, source=game.source,
            )
        )
        teams.append(
            TeamOdds(
                team=game.away, opponent=game.home, is_home=False,
                spread=-game.spread if game.spread is not None else None,
                total=game.total, implied_total=game.away_implied,
                kickoff=game.kickoff, source=game.source,
            )
        )

    con_total = [t for t in teams if t.implied_total is not None]
    con_total.sort(key=lambda t: -(t.implied_total or 0))
    for posicion, equipo in enumerate(con_total, start=1):
        equipo.implied_rank = posicion

    for equipo in teams:
        equipo.verdict = _verdict(equipo)
    teams.sort(key=lambda t: (t.implied_rank or 999))
    return teams


def _verdict(team: TeamOdds) -> str | None:
    """Lectura en una línea de lo que dice el mercado sobre ese ataque."""
    if team.implied_total is None:
        return None
    if team.implied_total >= 27:
        return "Ataque muy valorado: entorno de muchos puntos"
    if team.implied_total >= 23:
        return "Entorno favorable"
    if team.implied_total >= 19:
        return "Partido normal"
    return "Entorno pobre: el mercado espera pocos puntos"


def _abbr(name: str | None) -> str | None:
    """De 'Kansas City Chiefs' saca algo comparable con una abreviatura."""
    if not name:
        return None
    return name.strip().upper()


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class OddsProvider:
    """Descarga y cachea las cuotas de la jornada."""

    def __init__(
        self,
        settings: Settings,
        cache: TTLCache,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self._client = client
        self._owns_client = client is None
        self.last_errors: list[str] = []

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.settings.http_timeout,
                headers={"User-Agent": self.settings.user_agent},
                follow_redirects=True,
            )
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    @property
    def has_api_key(self) -> bool:
        return bool(self.settings.odds_api_key)

    # -- descargas -----------------------------------------------------------

    async def _fetch_espn(self, week: int | None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if week:
            params = {"week": week, "seasontype": 2}
        response = await self.client.get(self.settings.espn_scoreboard_url, params=params)
        response.raise_for_status()
        return [game.model_dump(mode="json") for game in parse_espn_scoreboard(response.json())]

    async def _fetch_odds_api(self) -> list[dict[str, Any]]:
        response = await self.client.get(
            f"{self.settings.odds_api_base_url}/sports/americanfootball_nfl/odds",
            params={
                "regions": "us",
                "markets": "spreads,totals",
                "oddsFormat": "american",
                "apiKey": self.settings.odds_api_key,
            },
        )
        response.raise_for_status()
        return [game.model_dump(mode="json") for game in parse_odds_api_games(response.json())]

    async def get_games(self, week: int | None = None) -> list[GameOdds]:
        """Cuotas de los partidos de la jornada.

        Se prefiere The Odds API cuando hay llave (más casas y más fiable) y se
        cae a ESPN en cuanto falla o no hay llave.
        """
        self.last_errors = []
        key = f"odds:games:{week or 'actual'}"

        async def factory() -> list[dict[str, Any]]:
            if self.has_api_key:
                try:
                    juegos = await self._fetch_odds_api()
                    if juegos:
                        return juegos
                except httpx.HTTPError as exc:
                    self.last_errors.append(f"The Odds API no respondió: {exc}")
            return await self._fetch_espn(week)

        try:
            crudo = await self.cache.get_or_set(
                key, self.settings.cache_ttl_odds, factory, use_disk=True
            )
        except httpx.HTTPError as exc:
            self.last_errors.append(f"No se pudieron leer las cuotas: {exc}")
            return []
        return [GameOdds.model_validate(entry) for entry in crudo]

    async def get_team_odds(self, week: int | None = None) -> dict[str, TeamOdds]:
        """Tabla por equipo, indexada por abreviatura."""
        games = await self.get_games(week)
        return {team.team: team for team in build_team_odds(games) if team.team}

    async def get_props(self, players: dict[str, Player]) -> dict[str, list[PlayerProp]]:
        """Props de jugador. Devuelve vacío si no hay llave configurada."""
        if not self.has_api_key:
            return {}

        async def factory() -> dict[str, Any]:
            # Primero los partidos, después las props de cada uno.
            response = await self.client.get(
                f"{self.settings.odds_api_base_url}/sports/americanfootball_nfl/events",
                params={"apiKey": self.settings.odds_api_key},
            )
            response.raise_for_status()
            eventos = response.json() or []

            async def props_de(evento: dict[str, Any]) -> Any:
                r = await self.client.get(
                    f"{self.settings.odds_api_base_url}/sports/americanfootball_nfl/"
                    f"events/{evento.get('id')}/odds",
                    params={
                        "regions": "us",
                        "markets": ",".join(PROP_MARKETS),
                        "oddsFormat": "american",
                        "apiKey": self.settings.odds_api_key,
                    },
                )
                r.raise_for_status()
                return r.json()

            resultados = await asyncio.gather(
                *(props_de(e) for e in eventos[:16]), return_exceptions=True
            )
            validos = [r for r in resultados if not isinstance(r, BaseException)]
            return {
                pid: [p.model_dump(mode="json") for p in props]
                for pid, props in parse_props(validos, players).items()
            }

        try:
            crudo = await self.cache.get_or_set(
                "odds:props", self.settings.cache_ttl_odds, factory, use_disk=True
            )
        except httpx.HTTPError as exc:
            self.last_errors.append(f"No se pudieron leer las props: {exc}")
            return {}
        return {
            pid: [PlayerProp.model_validate(p) for p in props] for pid, props in crudo.items()
        }
