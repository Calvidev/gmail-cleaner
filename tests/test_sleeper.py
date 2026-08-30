"""Cliente y parsers de Sleeper (contra el transporte de demo)."""

import httpx
import pytest

from app.cache import TTLCache
from app.providers.sleeper import (
    SleeperClient,
    SleeperError,
    parse_player,
    parse_players,
    parse_trending,
)


class TestParsePlayer:
    def test_normaliza_una_entrada_completa(self):
        p = parse_player("4046", {
            "first_name": "Patrick", "last_name": "Mahomes", "full_name": "Patrick Mahomes",
            "position": "QB", "fantasy_positions": ["QB"], "team": "KC", "age": 30,
            "years_exp": 9, "search_rank": 22, "depth_chart_order": 1, "espn_id": 3139477,
            "status": "Active",
        })
        assert p.name == "Patrick Mahomes"
        assert p.position == "QB"
        assert p.espn_id == "3139477"  # se guarda como texto
        assert p.headshot_url and p.headshot_url.endswith("4046.jpg")

    def test_construye_el_nombre_si_falta_el_completo(self):
        p = parse_player("1", {"first_name": "Bijan", "last_name": "Robinson", "position": "RB"})
        assert p.name == "Bijan Robinson"

    def test_las_defensas_reciben_nombre_y_escudo(self):
        p = parse_player("DEN", {"position": "DEF", "team": "DEN", "fantasy_positions": ["DEF"]})
        assert p.name == "DEN D/ST"
        assert p.headshot_url and "den" in p.headshot_url

    def test_los_numeros_invalidos_no_rompen_nada(self):
        p = parse_player("1", {"first_name": "A", "last_name": "B", "age": "", "number": "x"})
        assert p.age is None and p.number is None

    def test_sin_nombre_usa_el_id(self):
        assert parse_player("9999", {}).name == "9999"


class TestParsePlayers:
    def test_descarta_a_quien_no_sirve_para_fantasy(self):
        crudo = {
            "1": {"first_name": "A", "last_name": "B", "position": "WR", "fantasy_positions": ["WR"]},
            "2": {"first_name": "C", "last_name": "D", "position": "OL", "fantasy_positions": ["OL"]},
            "3": {"first_name": "E", "last_name": "F", "position": "CB"},
        }
        salida = parse_players(crudo)
        assert set(salida) == {"1"}

    def test_ignora_entradas_corruptas(self):
        assert parse_players({"1": "no soy un diccionario", "2": None}) == {}

    def test_catalogo_vacio(self):
        assert parse_players({}) == {}
        assert parse_players(None) == {}


class TestParseTrending:
    def test_convierte_la_lista_en_diccionario(self):
        assert parse_trending([{"player_id": "1", "count": 400}]) == {"1": 400}

    def test_tolera_basura(self):
        assert parse_trending([{"count": 5}, "texto", None]) == {}

    def test_lista_vacia(self):
        assert parse_trending([]) == {}
        assert parse_trending(None) == {}


class TestSleeperClient:
    async def test_lee_el_estado_de_la_temporada(self, sleeper):
        estado = await sleeper.get_state()
        assert estado["season"] == "2025"
        assert await sleeper.current_week() == 11

    async def test_descarga_y_normaliza_el_catalogo(self, sleeper):
        jugadores = await sleeper.get_players()
        assert len(jugadores) > 40
        assert all(p.is_fantasy_relevant for p in jugadores.values())

    async def test_lee_las_tendencias(self, sleeper):
        altas = await sleeper.get_trending("add")
        assert altas["12507"] == 48213

    def test_rechaza_un_tipo_de_tendencia_invalido(self, sleeper):
        with pytest.raises(ValueError):
            import asyncio

            asyncio.run(sleeper.get_trending("cualquiera"))

    async def test_lee_estadisticas_y_proyecciones(self, sleeper):
        assert await sleeper.get_season_stats("2025")
        assert await sleeper.get_season_projections("2025")

    async def test_cachea_la_segunda_llamada(self, sleeper):
        llamadas = {"n": 0}
        original = sleeper._get

        async def contando(path):
            llamadas["n"] += 1
            return await original(path)

        sleeper._get = contando
        await sleeper.get_state()
        await sleeper.get_state()
        assert llamadas["n"] == 1

    async def test_un_error_http_se_convierte_en_SleeperError(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(500, text="boom"))
        cliente = SleeperClient(settings, cache, httpx.AsyncClient(transport=transporte))
        with pytest.raises(SleeperError):
            await cliente.get_state()

    async def test_si_falla_la_red_se_estima_la_temporada(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(503))
        cliente = SleeperClient(settings, cache, httpx.AsyncClient(transport=transporte))
        temporada = await cliente.current_season()
        assert temporada.isdigit() and len(temporada) == 4

    async def test_las_tendencias_caidas_no_rompen_nada(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(500))
        cliente = SleeperClient(settings, cache, httpx.AsyncClient(transport=transporte))
        assert await cliente.get_trending("add") == {}
        assert await cliente.get_season_stats("2025") == {}

    async def test_devuelve_los_jugadores_ya_fichados_en_la_liga(self, sleeper):
        ocupados = await sleeper.get_rostered_player_ids("999888777666555444")
        assert len(ocupados) > 40
        assert all(isinstance(pid, str) for pid in ocupados)

    async def test_si_la_liga_falla_devuelve_conjunto_vacio(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(404))
        cliente = SleeperClient(settings, cache, httpx.AsyncClient(transport=transporte))
        assert await cliente.get_rostered_player_ids("123") == set()


class TestResolveUserId:
    """Traducir el nombre de usuario a `user_id`, que es lo que identifica
    de verdad a un equipo dentro de una liga."""

    async def test_traduce_el_nombre_a_id(self, sleeper):
        assert await sleeper.resolve_user_id("calvidev") == "100001"

    async def test_un_usuario_que_no_existe_devuelve_None(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(404))
        cliente = SleeperClient(settings, cache, httpx.AsyncClient(transport=transporte))
        assert await cliente.resolve_user_id("nadie") is None

    async def test_si_la_red_falla_devuelve_None(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(500))
        cliente = SleeperClient(settings, cache, httpx.AsyncClient(transport=transporte))
        assert await cliente.resolve_user_id("calvidev") is None

    async def test_nombre_vacio(self, sleeper):
        assert await sleeper.resolve_user_id("") is None

    async def test_una_respuesta_sin_user_id_devuelve_None(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(200, json={"username": "x"}))
        cliente = SleeperClient(settings, cache, httpx.AsyncClient(transport=transporte))
        assert await cliente.resolve_user_id("x") is None
