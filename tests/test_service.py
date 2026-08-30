"""La capa de servicio: orquestación, caché de ranking y errores controlados."""

import httpx
import pytest

from app.cache import TTLCache
from app.config import Settings
from app.providers.news import NewsProvider
from app.providers.sleeper import SleeperClient
from app.service import FantasyService, LeagueNotConfigured, ServiceUnavailable, build_service


class TestRanking:
    async def test_construye_el_ranking_completo(self, service):
        ranked = await service.get_ranking()
        assert len(ranked) > 40
        assert ranked[0].rank == 1
        assert ranked[0].score >= ranked[-1].score

    async def test_reutiliza_el_ranking_cacheado(self, service):
        primero = await service.get_ranking()
        segundo = await service.get_ranking()
        assert primero is segundo  # misma lista, no se recalcula

    async def test_cada_formato_tiene_su_propio_ranking(self, service):
        ppr = await service.get_ranking("ppr")
        estandar = await service.get_ranking("standard")
        assert ppr is not estandar

    async def test_busca_a_un_jugador_por_id(self, service):
        entrada = await service.get_ranked_player("6794")
        assert entrada and entrada.player.name == "Ja'Marr Chase"

    async def test_un_id_inexistente_devuelve_None(self, service):
        assert await service.get_ranked_player("000000") is None


class TestNoticias:
    async def test_devuelve_noticias_etiquetadas(self, service):
        noticias = await service.get_news(limit=5)
        assert len(noticias) == 5

    async def test_noticias_de_un_jugador(self, service):
        noticias = await service.get_player_news("6794")
        assert noticias and all("6794" in n.player_ids for n in noticias)


class TestMeta:
    async def test_incluye_temporada_equipos_y_avisos(self, service):
        meta = await service.get_meta()
        assert meta.season == "2025"
        assert meta.teams and meta.positions
        assert meta.league_configured is False
        assert meta.warnings


class TestLiga:
    async def test_sin_liga_no_hay_jugadores_ocupados(self, service):
        assert await service.get_rostered_ids() is None

    async def test_pedir_la_liga_sin_configurarla_falla_claro(self, service):
        with pytest.raises(LeagueNotConfigured):
            await service.get_league_info()

    async def test_con_liga_configurada_se_consulta(self, league_service):
        ocupados = await league_service.get_rostered_ids()
        assert ocupados and len(ocupados) > 40


class TestErrores:
    async def test_si_sleeper_se_cae_el_error_es_explicito(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(500))
        cliente = httpx.AsyncClient(transport=transporte)
        servicio = FantasyService(
            settings=settings,
            cache=cache,
            sleeper=SleeperClient(settings, cache, cliente),
            news=NewsProvider(settings, cache, cliente),
        )
        with pytest.raises(ServiceUnavailable):
            await servicio.get_ranking()

    async def test_meta_sobrevive_a_una_caida(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(500))
        cliente = httpx.AsyncClient(transport=transporte)
        servicio = FantasyService(
            settings=settings,
            cache=cache,
            sleeper=SleeperClient(settings, cache, cliente),
            news=NewsProvider(settings, cache, cliente),
        )
        meta = await servicio.get_meta()
        assert meta.player_count == 0
        assert meta.warnings  # explica qué ha pasado


class TestRefresh:
    async def test_vacia_las_caches(self, service):
        primero = await service.get_ranking()
        service.refresh()
        segundo = await service.get_ranking()
        assert primero is not segundo


class TestBuildService:
    def test_el_modo_demo_no_toca_la_red(self):
        servicio = build_service(Settings(fantasy_demo=True))
        assert isinstance(servicio._shared_client._transport, httpx.MockTransport)

    def test_fuera_del_modo_demo_usa_la_red(self):
        servicio = build_service(Settings(fantasy_demo=False))
        assert not isinstance(servicio._shared_client._transport, httpx.MockTransport)


class TestErroresDeLiga:
    """La liga es lo único que depende de datos que el usuario teclea a mano,
    así que sus fallos tienen que explicarse bien."""

    def _servicio(self, cache, handler, **extra):
        from app.providers.news import NewsProvider
        from app.providers.odds import OddsProvider

        ajustes = Settings(
            fantasy_demo=True, sleeper_league_id="123456789", **extra
        )
        cliente = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return FantasyService(
            settings=ajustes,
            cache=cache,
            sleeper=SleeperClient(ajustes, cache, cliente),
            news=NewsProvider(ajustes, cache, cliente),
            odds=OddsProvider(ajustes, cache, cliente),
        )

    async def test_un_id_de_liga_que_no_existe_lo_dice_claro(self, cache):
        servicio = self._servicio(cache, lambda r: httpx.Response(404))
        with pytest.raises(ServiceUnavailable) as error:
            await servicio.get_league_info()
        assert "no encuentra la liga" in str(error.value)
        assert "sleeper.com/leagues" in str(error.value)  # dónde mirar el número

    async def test_si_sleeper_no_responde_se_distingue_del_id_erroneo(self, cache):
        servicio = self._servicio(cache, lambda r: httpx.Response(503))
        with pytest.raises(ServiceUnavailable) as error:
            await servicio.get_league_info()
        assert "no encuentra la liga" not in str(error.value)
        assert "No se pudo consultar tu liga" in str(error.value)

    async def test_una_liga_sin_equipos_lo_dice(self, cache):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/rosters"):
                return httpx.Response(200, json=[])
            return httpx.Response(200, json={"league_id": "123456789", "name": "Vacía"})

        servicio = self._servicio(cache, handler)
        with pytest.raises(ServiceUnavailable) as error:
            await servicio.get_league_info()
        assert "no tiene equipos" in str(error.value)

    async def test_el_analisis_no_revienta_si_sleeper_esta_caido(self, cache):
        servicio = self._servicio(cache, lambda r: httpx.Response(503))
        with pytest.raises(ServiceUnavailable):
            await servicio.get_league_analysis()
