"""Emparejar noticias con jugadores por nombre.

Las noticias no traen el `player_id` de Sleeper, así que hay que reconocer los
nombres dentro del titular y del resumen. La idea:

1. Se construye un índice de nombres normalizados -> `player_id`.
2. De cada texto se extraen los n-gramas de palabras que empiezan por mayúscula
   (los nombres propios) y se buscan en el índice.

Normalizar significa: minúsculas, sin acentos, sin puntuación y sin sufijos
("Jr.", "III"), de modo que "Amon-Ra St. Brown" y "Amon-Ra St.Brown" acaben
siendo la misma clave.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from app.models import Player

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Palabras que empiezan por mayúscula pero nunca son un nombre de jugador.
_STOPWORDS = {
    "the", "a", "an", "in", "on", "of", "for", "to", "and", "with", "at", "is",
    "nfl", "espn", "week", "sunday", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "fantasy", "football", "report",
    "injury", "news", "update", "notes", "practice", "preseason", "playoff",
    "playoffs", "super", "bowl", "draft", "trade", "waiver", "wire", "start",
    "sit", "sleeper", "breakout", "bust", "rankings", "ranking", "roster",
}

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.\-]*")
_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Quita etiquetas HTML de los resúmenes de los RSS."""
    return _TAG_RE.sub(" ", text or "")


def normalize_name(name: str) -> str:
    """Clave canónica de un nombre: sin acentos, sin puntuación, sin sufijos."""
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_name = ascii_name.lower()
    ascii_name = re.sub(r"[^a-z0-9]+", " ", ascii_name)
    parts = [p for p in ascii_name.split() if p and p not in SUFFIXES]
    return " ".join(parts)


def name_variants(player: Player) -> set[str]:
    """Formas en que la prensa puede escribir el nombre de un jugador."""
    variants: set[str] = set()
    full = normalize_name(player.name)
    if full:
        variants.add(full)

    first = normalize_name(player.first_name or "")
    last = normalize_name(player.last_name or "")
    if first and last:
        variants.add(f"{first} {last}")
        # "P. Mahomes" y "PMahomes" -> "p mahomes"
        variants.add(f"{first[0]} {last}")

    if player.position == "DEF":
        # "SF D/ST" también aparece como "49ers defense": el nombre completo ya
        # cubre lo habitual; añadimos la abreviatura del equipo por si acaso.
        if player.team:
            variants.add(normalize_name(f"{player.team} defense"))
    return {v for v in variants if len(v.split()) >= 2}


def build_name_index(players: Iterable[Player]) -> dict[str, str]:
    """Índice nombre normalizado -> `player_id`.

    Ante un choque de nombres (hay dos "Josh Allen"), gana el jugador con mejor
    `search_rank`, que es casi siempre el que sale en las noticias de fantasy.
    """
    index: dict[str, str] = {}
    ranks: dict[str, int] = {}
    for player in players:
        rank = player.search_rank if player.search_rank is not None else 10**6
        for variant in name_variants(player):
            if variant not in index or rank < ranks.get(variant, 10**6):
                index[variant] = player.player_id
                ranks[variant] = rank
    return index


def build_espn_index(players: Iterable[Player]) -> dict[str, str]:
    """Índice `espn_id` -> `player_id`, para los enlaces directos de ESPN."""
    return {p.espn_id: p.player_id for p in players if p.espn_id}


def candidate_names(text: str, max_words: int = 4) -> set[str]:
    """N-gramas de palabras capitalizadas: los candidatos a nombre propio."""
    if not text:
        return set()
    tokens = _TOKEN_RE.findall(strip_html(text))
    capitalized: list[tuple[int, str]] = [
        (i, tok) for i, tok in enumerate(tokens) if tok[:1].isupper()
    ]
    candidates: set[str] = set()
    for pos, (idx, _) in enumerate(capitalized):
        run = [tokens[idx]]
        next_idx = idx
        for follow_pos in range(pos + 1, len(capitalized)):
            f_idx, f_tok = capitalized[follow_pos]
            if f_idx != next_idx + 1:
                break
            run.append(f_tok)
            next_idx = f_idx
            if len(run) > max_words:
                break
        for size in range(2, min(len(run), max_words) + 1):
            phrase = normalize_name(" ".join(run[:size]))
            if not phrase:
                continue
            words = phrase.split()
            if len(words) < 2 or all(w in _STOPWORDS for w in words):
                continue
            if words[-1] in _STOPWORDS:
                continue
            candidates.add(phrase)
    return candidates


def match_players(text: str, name_index: dict[str, str]) -> list[str]:
    """`player_id`s mencionados en el texto, sin repetir y en orden estable."""
    found: list[str] = []
    seen: set[str] = set()
    for candidate in sorted(candidate_names(text), key=lambda c: (-len(c), c)):
        pid = name_index.get(candidate)
        if pid and pid not in seen:
            seen.add(pid)
            found.append(pid)
    return found
