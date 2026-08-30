"""Importar rankings de otras fuentes."""

import pytest

from app.external_rankings import (
    build_external_ranking,
    index_by_player,
    load_ranking_files,
    parse_ranking_text,
)


class TestParseRankingText:
    def test_lista_numerada_simple(self):
        assert parse_ranking_text("1. Uno\n2. Dos") == [(1, "Uno"), (2, "Dos")]

    def test_acepta_separadores_variados(self):
        texto = "1. Uno\n2) Dos\n3 - Tres\n4, Cuatro\n5: Cinco"
        assert [n for _, n in parse_ranking_text(texto)] == [
            "Uno", "Dos", "Tres", "Cuatro", "Cinco"
        ]

    def test_sin_numeros_manda_el_orden(self):
        assert parse_ranking_text("Uno\nDos\nTres") == [(1, "Uno"), (2, "Dos"), (3, "Tres")]

    def test_quita_posicion_y_equipo(self):
        casos = {
            "1. Bijan Robinson RB ATL": "Bijan Robinson",
            "2, Justin Jefferson, WR, MIN": "Justin Jefferson",
            "3) Amon-Ra St. Brown (WR - DET)": "Amon-Ra St. Brown",
            "4. Brock Bowers TE1": "Brock Bowers",
            "5. Travis Kelce - TE": "Travis Kelce",
            "6. De'Von Achane | RB | MIA": "De'Von Achane",
        }
        for linea, esperado in casos.items():
            assert parse_ranking_text(linea)[0][1] == esperado

    def test_no_se_come_los_sufijos_del_nombre(self):
        # "III" no es una posición: tiene que sobrevivir.
        assert parse_ranking_text("1. Kenneth Walker III")[0][1] == "Kenneth Walker III"
        assert parse_ranking_text("2. Marvin Harrison Jr.")[0][1] == "Marvin Harrison Jr."

    def test_ignora_comentarios_y_lineas_vacias(self):
        texto = "# Encabezado\n\n1. Uno\n\n# otro comentario\n2. Dos\n"
        assert parse_ranking_text(texto) == [(1, "Uno"), (2, "Dos")]

    def test_si_los_numeros_se_repiten_manda_el_orden(self):
        assert parse_ranking_text("1. Uno\n1. Dos\n1. Tres") == [
            (1, "Uno"), (2, "Dos"), (3, "Tres")
        ]

    def test_respeta_los_huecos_de_numeracion(self):
        # Una lista que empieza en el 20 debe conservar sus números.
        assert parse_ranking_text("20. Uno\n21. Dos") == [(20, "Uno"), (21, "Dos")]

    def test_texto_vacio(self):
        assert parse_ranking_text("") == []
        assert parse_ranking_text("\n\n  \n") == []


class TestBuildExternalRanking:
    def test_empareja_los_nombres_con_el_catalogo(self, sample_players):
        texto = "1. Ja'Marr Chase\n2. Patrick Mahomes"
        ranking = build_external_ranking("prueba", texto, sample_players)
        assert [e.player_id for e in ranking.entries] == ["1", "3"]
        assert ranking.entries[0].name == "Ja'Marr Chase"
        assert ranking.total == 2

    def test_tolera_acentos_y_sufijos(self, sample_players):
        ranking = build_external_ranking(
            "prueba", "1. Amon-Ra St.Brown\n2. JaMarr Chase", sample_players
        )
        assert {e.player_id for e in ranking.entries} == {"1", "2"}

    def test_avisa_de_los_nombres_que_no_reconoce(self, sample_players):
        ranking = build_external_ranking(
            "prueba", "1. Ja'Marr Chase\n2. Jugador Inventado", sample_players
        )
        assert ranking.unmatched == ["Jugador Inventado"]
        assert len(ranking.entries) == 1

    def test_renumera_sin_huecos(self, sample_players):
        texto = "1. Ja'Marr Chase\n2. Jugador Inventado\n3. Patrick Mahomes"
        ranking = build_external_ranking("prueba", texto, sample_players)
        assert [e.rank for e in ranking.entries] == [1, 2]

    def test_no_repite_al_mismo_jugador(self, sample_players):
        texto = "1. Ja'Marr Chase\n2. JaMarr Chase"
        ranking = build_external_ranking("prueba", texto, sample_players)
        assert len(ranking.entries) == 1

    def test_guarda_el_nombre_original(self, sample_players):
        ranking = build_external_ranking("prueba", "1. JaMarr Chase", sample_players)
        assert ranking.entries[0].source_name == "JaMarr Chase"
        assert ranking.entries[0].name == "Ja'Marr Chase"

    def test_lista_vacia(self, sample_players):
        ranking = build_external_ranking("prueba", "", sample_players)
        assert ranking.entries == [] and ranking.total == 0


class TestDefensas:
    async def test_reconoce_una_defensa_por_su_equipo(self, sleeper):
        jugadores = await sleeper.get_players()
        ranking = build_external_ranking("prueba", "1. DEN DEF\n2. BAL", jugadores)
        assert [e.player_id for e in ranking.entries] == ["DEN", "BAL"]


class TestLoadRankingFiles:
    def test_carga_los_archivos_del_directorio(self, tmp_path, sample_players):
        (tmp_path / "un-analista.txt").write_text(
            "# Su top de pretemporada\n1. Ja'Marr Chase\n2. Patrick Mahomes",
            encoding="utf-8",
        )
        (rankings := load_ranking_files(tmp_path, sample_players))
        assert len(rankings) == 1
        assert rankings[0].source == "un analista"  # el guion se convierte en espacio
        assert rankings[0].description == "Su top de pretemporada"

    def test_carga_varias_fuentes(self, tmp_path, sample_players):
        (tmp_path / "a.txt").write_text("1. Ja'Marr Chase", encoding="utf-8")
        (tmp_path / "b.txt").write_text("1. Patrick Mahomes", encoding="utf-8")
        assert {r.source for r in load_ranking_files(tmp_path, sample_players)} == {"a", "b"}

    def test_descarta_los_archivos_sin_nada_reconocible(self, tmp_path, sample_players):
        (tmp_path / "vacio.txt").write_text("# solo comentarios\n", encoding="utf-8")
        assert load_ranking_files(tmp_path, sample_players) == []

    def test_un_directorio_que_no_existe(self, tmp_path, sample_players):
        assert load_ranking_files(tmp_path / "no-existe", sample_players) == []


class TestIndexByPlayer:
    def test_agrupa_los_puestos_por_jugador(self, sample_players):
        a = build_external_ranking("a", "1. Ja'Marr Chase\n2. Patrick Mahomes", sample_players)
        b = build_external_ranking("b", "1. Patrick Mahomes", sample_players)
        indice = index_by_player([a, b])
        assert indice["3"] == {"a": 2, "b": 1}
        assert indice["1"] == {"a": 1}

    def test_sin_rankings(self):
        assert index_by_player([]) == {}


class TestIntegracionConElRanking:
    async def test_el_ranking_propio_incluye_los_puestos_externos(
        self, service, tmp_path, monkeypatch
    ):
        (tmp_path / "fuente.txt").write_text(
            "1. Bijan Robinson\n2. Ja'Marr Chase", encoding="utf-8"
        )
        monkeypatch.setattr(service.settings, "rankings_dir", tmp_path)

        ranked = await service.get_ranking()
        por_id = {r.player.player_id: r for r in ranked}
        chase = por_id["6794"]
        assert chase.external_ranks == {"fuente": 2}
        # Nosotros lo tenemos el 1 y la fuente el 2: la diferencia es -1.
        assert chase.external_delta == -1

    async def test_sin_archivos_no_cambia_nada(self, service):
        ranked = await service.get_ranking()
        assert all(not r.external_ranks for r in ranked)


class TestSignoDeLaDiferencia:
    """El signo del delta se lee en la interfaz: invertirlo haría leer la
    columna al revés, que es peor que no tenerla."""

    async def test_positivo_cuando_fuera_lo_ponen_por_delante(self, service, tmp_path, monkeypatch):
        # Ja'Marr Chase es nuestro número 1; la fuente lo pone el 5.
        (tmp_path / "fuente.txt").write_text(
            "1. Bijan Robinson\n2. Justin Jefferson\n3. CeeDee Lamb\n"
            "4. Jahmyr Gibbs\n5. Ja'Marr Chase",
            encoding="utf-8",
        )
        monkeypatch.setattr(service.settings, "rankings_dir", tmp_path)
        por_id = {r.player.player_id: r for r in await service.get_ranking()}

        chase = por_id["6794"]
        assert chase.rank == 1 and chase.external_ranks == {"fuente": 5}
        # Nosotros el 1, ellos el 5: nos gusta más a nosotros -> negativo.
        assert chase.external_delta == -4

        bijan = por_id["9509"]
        # A Bijan lo ponen ellos por delante de donde lo tenemos -> positivo.
        assert bijan.external_delta > 0
