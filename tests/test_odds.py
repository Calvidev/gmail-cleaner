"""Cuotas de apuestas: totales implícitos, parsers y props."""

import httpx
import pytest

from app.cache import TTLCache
from app.config import Settings
from app.models import GameOdds
from app.providers.odds import (
    OddsProvider,
    build_team_odds,
    implied_totals,
    normalize_team,
    parse_espn_scoreboard,
    parse_odds_api_games,
    parse_props,
)


class TestNormalizeTeam:
    def test_traduce_las_abreviaturas_que_no_coinciden(self):
        assert normalize_team("WSH") == "WAS"
        assert normalize_team("JAC") == "JAX"

    def test_deja_igual_las_que_ya_coinciden(self):
        assert normalize_team("KC") == "KC"
        assert normalize_team("kc") == "KC"

    def test_sin_valor(self):
        assert normalize_team(None) is None


class TestImpliedTotals:
    def test_el_favorito_local_se_lleva_mas_puntos(self):
        local, visitante = implied_totals(total=51.5, spread=-3.5)
        assert local == 27.5 and visitante == 24.0
        assert local + visitante == pytest.approx(51.5)

    def test_el_favorito_visitante_se_lleva_mas_puntos(self):
        local, visitante = implied_totals(total=47.5, spread=2.5)
        assert visitante > local
        assert local + visitante == pytest.approx(47.5)

    def test_partido_igualado(self):
        assert implied_totals(44.0, 0.0) == (22.0, 22.0)

    def test_sin_linea_no_hay_implicitos(self):
        assert implied_totals(None, -3.5) == (None, None)
        assert implied_totals(45.0, None) == (None, None)


class TestParseEspnScoreboard:
    PAYLOAD = {
        "events": [{
            "id": "401600001",
            "date": "2025-11-16T18:00:00Z",
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "BAL"}},
                    {"homeAway": "away", "team": {"abbreviation": "CIN"}},
                ],
                "odds": [{
                    "provider": {"name": "ESPN BET"},
                    "details": "BAL -3.5",
                    "overUnder": 51.5,
                    "spread": -3.5,
                }],
            }],
        }]
    }

    def test_normaliza_un_partido(self):
        (juego,) = parse_espn_scoreboard(self.PAYLOAD)
        assert juego.home == "BAL" and juego.away == "CIN"
        assert juego.total == 51.5 and juego.spread == -3.5
        assert juego.home_implied == 27.5 and juego.away_implied == 24.0
        assert juego.favorite == "BAL"
        assert juego.bookmaker == "ESPN BET"
        assert juego.kickoff.year == 2025

    def test_deduce_el_spread_del_texto_si_falta(self):
        payload = {"events": [{
            "id": "1",
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "KC"}},
                    {"homeAway": "away", "team": {"abbreviation": "BUF"}},
                ],
                "odds": [{"details": "BUF -2.5", "overUnder": 47.5}],
            }],
        }]}
        (juego,) = parse_espn_scoreboard(payload)
        # El visitante es favorito: el spread relativo al local es positivo.
        assert juego.spread == 2.5
        assert juego.favorite == "BUF"
        assert juego.away_implied > juego.home_implied

    def test_un_partido_sin_cuotas_sigue_apareciendo(self):
        payload = {"events": [{
            "id": "1",
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"abbreviation": "NYJ"}},
                    {"homeAway": "away", "team": {"abbreviation": "MIA"}},
                ],
            }],
        }]}
        (juego,) = parse_espn_scoreboard(payload)
        assert juego.total is None and juego.home_implied is None

    def test_respuesta_vacia(self):
        assert parse_espn_scoreboard({}) == []
        assert parse_espn_scoreboard(None) == []


class TestParseOddsApi:
    def test_normaliza_spread_y_total(self):
        payload = [{
            "id": "abc",
            "commence_time": "2025-11-16T18:00:00Z",
            "home_team": "Baltimore Ravens",
            "away_team": "Cincinnati Bengals",
            "bookmakers": [{
                "title": "DraftKings",
                "markets": [
                    {"key": "spreads", "outcomes": [
                        {"name": "Baltimore Ravens", "point": -3.5},
                        {"name": "Cincinnati Bengals", "point": 3.5},
                    ]},
                    {"key": "totals", "outcomes": [{"name": "Over", "point": 51.5}]},
                ],
            }],
        }]
        (juego,) = parse_odds_api_games(payload)
        assert juego.spread == -3.5 and juego.total == 51.5
        assert juego.home_implied == 27.5
        assert juego.bookmaker == "DraftKings"
        assert juego.source == "The Odds API"

    def test_respuesta_vacia(self):
        assert parse_odds_api_games([]) == []
        assert parse_odds_api_games(None) == []


class TestParseProps:
    def test_asocia_las_lineas_con_los_jugadores(self, sample_players):
        payload = [{
            "bookmakers": [{
                "title": "FanDuel",
                "markets": [{
                    "key": "player_reception_yds",
                    "outcomes": [
                        {"name": "Over", "description": "Ja'Marr Chase", "point": 82.5, "price": -114},
                        {"name": "Under", "description": "Ja'Marr Chase", "point": 82.5, "price": -106},
                    ],
                }],
            }]
        }]
        props = parse_props(payload, sample_players)
        assert "1" in props  # Ja'Marr Chase
        (prop,) = props["1"]
        assert prop.line == 82.5
        assert prop.label == "Yardas de recepción"
        assert prop.over_price == -114 and prop.under_price == -106
        assert prop.bookmaker == "FanDuel"

    def test_ignora_los_mercados_que_no_interesan(self, sample_players):
        payload = [{"bookmakers": [{"title": "X", "markets": [
            {"key": "h2h", "outcomes": [{"description": "Ja'Marr Chase", "point": 1}]}
        ]}]}]
        assert parse_props(payload, sample_players) == {}

    def test_un_nombre_desconocido_no_rompe(self, sample_players):
        payload = [{"bookmakers": [{"title": "X", "markets": [
            {"key": "player_receptions",
             "outcomes": [{"name": "Over", "description": "Jugador Inventado", "point": 5.5}]}
        ]}]}]
        assert parse_props(payload, sample_players) == {}


class TestBuildTeamOdds:
    def test_convierte_partidos_en_filas_por_equipo(self):
        juegos = [
            GameOdds(game_id="1", home="BAL", away="CIN", spread=-3.5, total=51.5,
                     home_implied=27.5, away_implied=24.0),
            GameOdds(game_id="2", home="NYJ", away="MIA", spread=1.5, total=41.5,
                     home_implied=20.0, away_implied=21.5),
        ]
        equipos = build_team_odds(juegos)
        assert len(equipos) == 4
        por_equipo = {t.team: t for t in equipos}
        assert por_equipo["BAL"].implied_rank == 1
        assert por_equipo["BAL"].is_home is True
        assert por_equipo["CIN"].is_home is False
        # El spread del visitante es el del local con el signo cambiado.
        assert por_equipo["CIN"].spread == 3.5
        assert por_equipo["NYJ"].implied_rank == 4

    def test_pone_veredicto_a_cada_ataque(self):
        juegos = [GameOdds(game_id="1", home="BAL", away="CIN", total=51.5, spread=-3.5,
                           home_implied=27.5, away_implied=24.0)]
        por_equipo = {t.team: t for t in build_team_odds(juegos)}
        assert "muy valorado" in por_equipo["BAL"].verdict

    def test_sin_partidos(self):
        assert build_team_odds([]) == []


class TestOddsProvider:
    async def test_descarga_las_cuotas_de_ejemplo(self, odds_provider):
        juegos = await odds_provider.get_games(11)
        assert len(juegos) == 13
        assert all(j.total for j in juegos)

    async def test_construye_la_tabla_por_equipo(self, odds_provider):
        equipos = await odds_provider.get_team_odds(11)
        assert len(equipos) == 26
        mejor = min(equipos.values(), key=lambda t: t.implied_rank or 99)
        assert mejor.implied_total == max(t.implied_total for t in equipos.values())

    async def test_sin_llave_no_hay_props(self, odds_provider):
        assert odds_provider.has_api_key is False
        assert await odds_provider.get_props({}) == {}

    async def test_si_la_fuente_se_cae_devuelve_vacio_y_avisa(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(500))
        proveedor = OddsProvider(settings, cache, httpx.AsyncClient(transport=transporte))
        assert await proveedor.get_games(11) == []
        assert proveedor.last_errors

    async def test_con_llave_se_intenta_the_odds_api_primero(self, cache):
        llamadas: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            llamadas.append(request.url.host)
            if request.url.host == "api.the-odds-api.com":
                return httpx.Response(500)  # falla: debe caer a ESPN
            from app.providers.demo import demo_handler

            return demo_handler(request)

        ajustes = Settings(fantasy_demo=True, odds_api_key="llave-de-prueba")
        proveedor = OddsProvider(
            ajustes, cache, httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        juegos = await proveedor.get_games(11)
        assert "api.the-odds-api.com" in llamadas  # se intentó primero
        assert juegos  # y ESPN salvó la jugada
        assert proveedor.last_errors
