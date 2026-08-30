"""Reconocimiento de nombres de jugador dentro del texto de una noticia."""

from app.matching import (
    build_name_index,
    candidate_names,
    match_players,
    name_variants,
    normalize_name,
    strip_html,
)
from app.models import Player


class TestNormalizeName:
    def test_quita_acentos_y_puntuacion(self):
        assert normalize_name("Amon-Ra St. Brown") == "amon ra st brown"
        assert normalize_name("Ja'Marr Chase") == "ja marr chase"
        assert normalize_name("D.K. Metcalf") == "d k metcalf"

    def test_quita_sufijos(self):
        assert normalize_name("Marvin Harrison Jr.") == "marvin harrison"
        assert normalize_name("Kenneth Walker III") == "kenneth walker"
        assert normalize_name("Odell Beckham Jr") == "odell beckham"

    def test_texto_vacio(self):
        assert normalize_name("") == ""
        assert normalize_name("   ") == ""


class TestNameVariants:
    def test_incluye_nombre_completo_e_inicial(self, sample_players):
        variants = name_variants(sample_players["3"])
        assert "patrick mahomes" in variants
        assert "p mahomes" in variants

    def test_descarta_variantes_de_una_sola_palabra(self, sample_players):
        for variant in name_variants(sample_players["1"]):
            assert len(variant.split()) >= 2


class TestBuildNameIndex:
    def test_ante_un_choque_gana_el_de_mejor_search_rank(self):
        estrella = Player(
            player_id="a", name="Josh Allen", first_name="Josh", last_name="Allen",
            position="QB", fantasy_positions=["QB"], search_rank=12,
        )
        homonimo = Player(
            player_id="b", name="Josh Allen", first_name="Josh", last_name="Allen",
            position="RB", fantasy_positions=["RB"], search_rank=800,
        )
        index = build_name_index([homonimo, estrella])
        assert index["josh allen"] == "a"


class TestCandidateNames:
    def test_extrae_nombres_propios(self):
        candidatos = candidate_names("Ja'Marr Chase lidera a los Bengals")
        assert "ja marr chase" in candidatos

    def test_ignora_frases_de_solo_palabras_vacias(self):
        candidatos = candidate_names("The Fantasy Football Report")
        assert "the fantasy" not in candidatos
        assert "fantasy football" not in candidatos

    def test_texto_vacio(self):
        assert candidate_names("") == set()


class TestMatchPlayers:
    def test_encuentra_a_varios_jugadores(self, sample_players):
        index = build_name_index(sample_players.values())
        texto = "Ja'Marr Chase y Amon-Ra St. Brown dominaron la jornada"
        assert set(match_players(texto, index)) == {"1", "2"}

    def test_no_inventa_coincidencias(self, sample_players):
        index = build_name_index(sample_players.values())
        assert match_players("Los Chiefs ganaron en la prórroga", index) == []

    def test_no_repite_al_mismo_jugador(self, sample_players):
        index = build_name_index(sample_players.values())
        texto = "Patrick Mahomes brilló. Mahomes lanzó tres pases de anotación. Patrick Mahomes."
        assert match_players(texto, index) == ["3"]


class TestStripHtml:
    def test_quita_etiquetas(self):
        assert "negrita" in strip_html("<p><b>negrita</b></p>")
        assert "<" not in strip_html("<p>hola</p>")
