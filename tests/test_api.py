"""Endpoints HTTP, levantando la aplicación completa en modo demo."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FANTASY_DEMO", "1")
    monkeypatch.delenv("SLEEPER_LEAGUE_ID", raising=False)
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def league_client(monkeypatch):
    """Cliente con la liga de ejemplo ya conectada."""
    monkeypatch.setenv("FANTASY_DEMO", "1")
    monkeypatch.setenv("SLEEPER_LEAGUE_ID", "999888777666555444")
    monkeypatch.setenv("SLEEPER_USER_ID", "100001")
    monkeypatch.setenv("SLEEPER_USERNAME", "calvidev")
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


class TestHealth:
    def test_responde(self, client):
        assert client.get("/api/health").json() == {"status": "ok"}


class TestIndex:
    def test_sirve_la_interfaz(self, client):
        respuesta = client.get("/")
        assert respuesta.status_code == 200
        assert "Fantasy Tool" in respuesta.text

    def test_sirve_los_estáticos(self, client):
        assert client.get("/static/assets/app.js").status_code == 200
        assert client.get("/static/assets/styles.css").status_code == 200


class TestMeta:
    def test_devuelve_temporada_y_equipos(self, client):
        datos = client.get("/api/meta").json()
        assert datos["season"] == "2025"
        assert datos["week"] == 11
        assert datos["player_count"] > 40
        assert "CIN" in datos["teams"]

    def test_avisa_de_que_falta_la_liga(self, client):
        datos = client.get("/api/meta").json()
        assert datos["league_configured"] is False
        assert any("SLEEPER_LEAGUE_ID" in w for w in datos["warnings"])


class TestRankings:
    def test_devuelve_el_ranking_ordenado(self, client):
        datos = client.get("/api/rankings").json()
        assert datos["total"] > 40
        notas = [p["score"] for p in datos["players"]]
        assert notas == sorted(notas, reverse=True)
        assert datos["players"][0]["rank"] == 1

    def test_cada_jugador_trae_su_desglose(self, client):
        jugador = client.get("/api/rankings?limit=1").json()["players"][0]
        assert set(jugador["breakdown"]) == {
            "consensus", "production", "opportunity",
            "momentum", "availability", "age_curve",
        }
        assert jugador["reasons"]
        assert jugador["tier"] >= 1

    def test_filtra_por_posicion(self, client):
        datos = client.get("/api/rankings?position=QB").json()
        assert datos["total"] == 8
        assert all(p["player"]["position"] == "QB" for p in datos["players"])

    def test_filtra_por_equipo(self, client):
        datos = client.get("/api/rankings?team=KC").json()
        assert all(p["player"]["team"] == "KC" for p in datos["players"])

    def test_busca_por_nombre(self, client):
        datos = client.get("/api/rankings?search=mahomes").json()
        assert datos["total"] == 1

    def test_oculta_lesionados(self, client):
        datos = client.get("/api/rankings?hide_injured=true").json()
        assert all(p["player"]["injury_status"] != "IR" for p in datos["players"])

    def test_pagina(self, client):
        primera = client.get("/api/rankings?limit=5&offset=0").json()
        segunda = client.get("/api/rankings?limit=5&offset=5").json()
        assert primera["count"] == 5
        assert primera["players"][0]["rank"] != segunda["players"][0]["rank"]

    def test_superflex_cambia_el_orden(self, client):
        normal = client.get("/api/rankings?position=QB&limit=1").json()["players"][0]
        flex = client.get("/api/rankings?position=QB&superflex=true&limit=1").json()["players"][0]
        assert flex["score"] > normal["score"]

    def test_formato_de_puntuacion_invalido(self, client):
        assert client.get("/api/rankings?scoring=inventado").status_code == 400

    def test_agentes_libres_sin_liga_avisa(self, client):
        respuesta = client.get("/api/rankings?free_agents_only=true")
        assert respuesta.status_code == 409
        assert "SLEEPER_LEAGUE_ID" in respuesta.json()["detail"]


class TestPlayerDetail:
    def test_devuelve_la_ficha_con_noticias(self, client):
        datos = client.get("/api/players/6794").json()  # Ja'Marr Chase
        assert datos["ranked"]["player"]["name"] == "Ja'Marr Chase"
        assert datos["ranked"]["rank"] >= 1
        assert isinstance(datos["news"], list)

    def test_un_jugador_que_no_existe(self, client):
        assert client.get("/api/players/000000").status_code == 404

    def test_se_puede_pedir_sin_noticias(self, client):
        datos = client.get("/api/players/6794?news_limit=0").json()
        assert datos["news"] == []


class TestPlayerNews:
    def test_solo_devuelve_noticias_de_ese_jugador(self, client):
        noticias = client.get("/api/players/6794/news").json()
        assert noticias and all("6794" in n["player_ids"] for n in noticias)

    def test_un_jugador_sin_noticias_devuelve_lista_vacia(self, client):
        assert client.get("/api/players/2747/news").json() == []


class TestNews:
    def test_devuelve_noticias_ordenadas(self, client):
        noticias = client.get("/api/news").json()
        assert len(noticias) > 10
        fechas = [n["published"] for n in noticias if n["published"]]
        assert fechas == sorted(fechas, reverse=True)

    def test_filtra_por_texto(self, client):
        noticias = client.get("/api/news?q=Chase").json()
        assert noticias and all(
            "chase" in (n["title"] + (n["summary"] or "")).lower()
            or any("chase" in p.lower() for p in n["player_names"])
            for n in noticias
        )

    def test_solo_con_jugador_identificado(self, client):
        noticias = client.get("/api/news?only_players=true").json()
        assert all(n["player_ids"] for n in noticias)

    def test_respeta_el_limite(self, client):
        assert len(client.get("/api/news?limit=3").json()) == 3


class TestCompare:
    def test_compara_varios_jugadores(self, client):
        datos = client.get("/api/compare?ids=6794,4046").json()
        assert [d["player"]["player_id"] for d in datos] == ["6794", "4046"]

    def test_ignora_los_ids_que_no_existen(self, client):
        datos = client.get("/api/compare?ids=6794,inventado").json()
        assert len(datos) == 1


class TestLeague:
    def test_sin_liga_configurada_devuelve_409(self, client):
        respuesta = client.get("/api/league")
        assert respuesta.status_code == 409
        assert "SLEEPER_LEAGUE_ID" in respuesta.json()["detail"]


class TestRefresh:
    def test_vacia_la_cache(self, client):
        assert client.post("/api/refresh").status_code == 200
        # Y la aplicación sigue funcionando después.
        assert client.get("/api/rankings?limit=1").status_code == 200


class TestTrends:
    def test_devuelve_las_tendencias_ordenadas(self, client):
        datos = client.get("/api/trends").json()
        assert datos["players"]
        notas = [t["trend_score"] for t in datos["players"]]
        assert notas == sorted(notas, reverse=True)
        assert datos["weeks_analyzed"]

    def test_solo_los_que_suben(self, client):
        datos = client.get("/api/trends?direction=alza").json()
        assert datos["players"]
        assert all(t["direction"] == "alza" for t in datos["players"])

    def test_los_que_bajan_salen_del_peor_al_menos_malo(self, client):
        datos = client.get("/api/trends?direction=baja").json()
        notas = [t["trend_score"] for t in datos["players"]]
        assert notas == sorted(notas)  # el que más cae, primero

    def test_cada_tendencia_trae_serie_y_señales(self, client):
        jugador = client.get("/api/trends?limit=1").json()["players"][0]
        assert jugador["weeks"]
        assert jugador["signals"]
        assert "opportunities" in jugador["metrics"] or "points" in jugador["metrics"]

    def test_filtra_por_posicion(self, client):
        datos = client.get("/api/trends?position=WR&direction=").json()
        assert all(t["player"]["position"] == "WR" for t in datos["players"])

    def test_excluye_a_quien_no_tiene_datos_de_volumen(self, client):
        datos = client.get("/api/trends?usage_only=true&direction=").json()
        assert all(t["usage_based"] for t in datos["players"])

    def test_se_puede_pedir_menos_jornadas(self, client):
        datos = client.get("/api/trends?weeks=4&direction=").json()
        assert len(datos["weeks_analyzed"]) <= 4

    def test_agentes_libres_sin_liga_avisa(self, client):
        assert client.get("/api/trends?free_agents_only=true").status_code == 409

    def test_tendencia_de_un_jugador(self, client):
        datos = client.get("/api/players/12507/trend").json()
        assert datos["player"]["name"] == "Tyrone Tracy Jr."
        assert datos["direction"] == "alza"

    def test_un_jugador_sin_jornadas_suficientes(self, client):
        assert client.get("/api/players/000000/trend").status_code == 404


class TestOdds:
    def test_devuelve_partidos_y_equipos(self, client):
        datos = client.get("/api/odds").json()
        assert len(datos["games"]) == 13
        assert len(datos["teams"]) == 26

    def test_los_equipos_van_ordenados_por_ataque(self, client):
        equipos = client.get("/api/odds").json()["teams"]
        implicitos = [t["implied_total"] for t in equipos if t["implied_total"]]
        assert implicitos == sorted(implicitos, reverse=True)

    def test_los_implicitos_suman_el_total_del_partido(self, client):
        for juego in client.get("/api/odds").json()["games"]:
            if juego["total"] and juego["home_implied"]:
                assert juego["home_implied"] + juego["away_implied"] == pytest.approx(juego["total"])

    def test_avisa_de_que_no_hay_llave_para_props(self, client):
        datos = client.get("/api/odds").json()
        assert datos["props_available"] is False
        assert any("ODDS_API_KEY" in w for w in datos["warnings"])


class TestPlayerDetailAmpliado:
    def test_la_ficha_trae_tendencia_y_mercado(self, client):
        datos = client.get("/api/players/12507").json()
        assert datos["trend"]["direction"] == "alza"
        assert datos["vegas"]["team"] == "NYG"
        assert datos["vegas"]["implied_total"] is not None

    def test_sin_llave_no_hay_props(self, client):
        assert client.get("/api/players/12507").json()["props"] == []


class TestLeagueAnalysis:
    def test_sin_liga_configurada_explica_como_conectarla(self, client):
        respuesta = client.get("/api/league/analysis")
        assert respuesta.status_code == 409
        assert "SLEEPER_LEAGUE_ID" in respuesta.json()["detail"]

    def test_con_liga_analiza_mi_equipo(self, league_client):
        datos = league_client.get("/api/league/analysis").json()
        assert datos["league_name"] == "Liga de Demostración"
        assert len(datos["teams"]) == 4
        assert datos["me"]["team_name"] == "Los Fantasmas"
        assert datos["me"]["weaknesses"]

    def test_propone_intercambios(self, league_client):
        datos = league_client.get("/api/league/analysis").json()
        assert datos["trade_ideas"]
        for idea in datos["trade_ideas"]:
            assert idea["my_gain"] > 0 and idea["their_gain"] > 0

    def test_se_puede_limitar_el_numero_de_ideas(self, league_client):
        datos = league_client.get("/api/league/analysis?max_trade_ideas=2").json()
        assert len(datos["trade_ideas"]) <= 2

    def test_con_liga_se_pueden_filtrar_agentes_libres(self, league_client):
        respuesta = league_client.get("/api/rankings?free_agents_only=true")
        assert respuesta.status_code == 200
        # En la liga de ejemplo están todos fichados: no queda nadie libre.
        assert respuesta.json()["total"] == 0

    def test_la_meta_refleja_la_liga_conectada(self, league_client):
        datos = league_client.get("/api/meta").json()
        assert datos["league_configured"] is True
        assert datos["league_id"] == "999888777666555444"
