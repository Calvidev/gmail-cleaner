"""Agregador de noticias: parsers, deduplicado y etiquetado de jugadores."""

from datetime import datetime, timedelta, timezone

import httpx

from app.models import NewsItem
from app.providers.news import (
    NewsProvider,
    annotate_players,
    dedupe,
    parse_espn_news,
    parse_rss,
    sort_by_recency,
)


class TestParseEspnNews:
    def test_normaliza_un_articulo(self):
        payload = {"articles": [{
            "headline": "Chase domina",
            "description": "<p>11 recepciones</p>",
            "published": "2025-11-10T12:00:00Z",
            "links": {"web": {"href": "https://espn.com/a"}},
            "images": [{"url": "https://espn.com/a.jpg"}],
            "categories": [{"type": "athlete", "athlete": {"id": 4362628}}],
        }]}
        (item,) = parse_espn_news(payload)
        assert item.title == "Chase domina"
        assert item.summary == "11 recepciones"  # sin HTML
        assert item.url == "https://espn.com/a"
        assert item.image_url == "https://espn.com/a.jpg"
        assert item.source == "ESPN"
        assert item.published.year == 2025
        assert item.player_names == ["4362628"]  # id de ESPN, aún sin traducir

    def test_descarta_articulos_sin_titular(self):
        assert parse_espn_news({"articles": [{"description": "vacío"}]}) == []

    def test_respuesta_vacia(self):
        assert parse_espn_news({}) == []
        assert parse_espn_news(None) == []


class TestParseRss:
    RSS = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <title>Demo Wire</title>
      <item>
        <title>Bijan Robinson corre 137 yardas</title>
        <link>https://demo.local/1</link>
        <description>Gran partido</description>
        <pubDate>Mon, 10 Nov 2025 12:00:00 +0000</pubDate>
      </item>
    </channel></rss>"""

    def test_normaliza_un_feed(self):
        (item,) = parse_rss(self.RSS, "https://demo.local/rss")
        assert item.title == "Bijan Robinson corre 137 yardas"
        assert item.source == "Demo Wire"
        assert item.url == "https://demo.local/1"
        assert item.published.year == 2025

    def test_un_feed_roto_no_lanza_excepcion(self):
        assert parse_rss(b"no soy xml", "https://demo.local/rss") == []


class TestDedupe:
    def test_quita_la_misma_url(self):
        items = [
            NewsItem(id="1", title="A", url="https://x.com/a", source="ESPN"),
            NewsItem(id="2", title="B", url="https://x.com/a/", source="CBS"),
        ]
        assert len(dedupe(items)) == 1

    def test_quita_el_mismo_titular(self):
        items = [
            NewsItem(id="1", title="Chase domina", source="ESPN"),
            NewsItem(id="2", title="chase domina", source="CBS"),
        ]
        assert len(dedupe(items)) == 1

    def test_conserva_las_distintas(self):
        items = [
            NewsItem(id="1", title="A", url="https://x.com/a", source="ESPN"),
            NewsItem(id="2", title="B", url="https://x.com/b", source="ESPN"),
        ]
        assert len(dedupe(items)) == 2


class TestSortByRecency:
    def test_lo_mas_nuevo_primero(self):
        ahora = datetime.now(timezone.utc)
        items = [
            NewsItem(id="1", title="vieja", source="A", published=ahora - timedelta(days=2)),
            NewsItem(id="2", title="nueva", source="A", published=ahora),
        ]
        assert [i.title for i in sort_by_recency(items)] == ["nueva", "vieja"]

    def test_las_que_no_tienen_fecha_van_al_final(self):
        ahora = datetime.now(timezone.utc)
        items = [
            NewsItem(id="1", title="sin fecha", source="A"),
            NewsItem(id="2", title="con fecha", source="A", published=ahora),
        ]
        assert [i.title for i in sort_by_recency(items)] == ["con fecha", "sin fecha"]


class TestAnnotatePlayers:
    def test_empareja_por_el_id_de_espn(self, sample_players):
        items = [NewsItem(id="1", title="Noticia", source="ESPN", player_names=["3139477"])]
        (item,) = annotate_players(items, sample_players)
        assert item.player_ids == ["3"]
        assert item.player_names == ["Patrick Mahomes"]

    def test_empareja_por_el_nombre_del_texto(self, sample_players):
        items = [NewsItem(id="1", title="Ja'Marr Chase supera las 150 yardas", source="CBS")]
        (item,) = annotate_players(items, sample_players)
        assert item.player_ids == ["1"]

    def test_busca_tambien_en_el_resumen(self, sample_players):
        items = [NewsItem(id="1", title="Jornada 11", summary="Amon-Ra St. Brown sumó 9 recepciones", source="CBS")]
        (item,) = annotate_players(items, sample_players)
        assert item.player_ids == ["2"]

    def test_sin_jugadores_reconocidos_queda_vacio(self, sample_players):
        items = [NewsItem(id="1", title="Los Chiefs ganan en la prórroga", source="CBS")]
        (item,) = annotate_players(items, sample_players)
        assert item.player_ids == []


class TestNewsProvider:
    async def test_descarga_y_agrega_todas_las_fuentes(self, news_provider):
        items = await news_provider.get_news()
        assert len(items) > 10
        assert {i.source for i in items} >= {"ESPN", "Demo NFL Wire"}

    async def test_etiqueta_a_los_jugadores(self, news_provider, sleeper):
        jugadores = await sleeper.get_players()
        items = await news_provider.get_news(jugadores)
        con_jugador = [i for i in items if i.player_ids]
        assert len(con_jugador) >= 10

    async def test_filtra_por_jugador(self, news_provider, sleeper):
        jugadores = await sleeper.get_players()
        # 6794 es Ja'Marr Chase en los datos de demo.
        items = await news_provider.get_player_news("6794", jugadores)
        assert items and all("6794" in i.player_ids for i in items)

    async def test_una_fuente_caida_no_tumba_al_resto(self, settings, cache):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "site.api.espn.com":
                return httpx.Response(500)
            from app.providers.demo import demo_handler

            return demo_handler(request)

        proveedor = NewsProvider(
            settings, cache, httpx.AsyncClient(transport=httpx.MockTransport(handler))
        )
        items = await proveedor.get_news()
        assert items  # siguen llegando las de RSS
        assert proveedor.last_errors  # y el fallo queda registrado

    async def test_si_todo_falla_devuelve_lista_vacia(self, settings, cache):
        transporte = httpx.MockTransport(lambda r: httpx.Response(500))
        proveedor = NewsProvider(settings, cache, httpx.AsyncClient(transport=transporte))
        assert await proveedor.get_news() == []
