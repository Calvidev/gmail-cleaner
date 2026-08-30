"""Noticias de la NFL: API pública de ESPN + feeds RSS.

Ninguna de las dos fuentes pide llave. Se descargan en paralelo, se normalizan a
`NewsItem`, se quitan duplicados y se etiqueta cada noticia con los jugadores
que menciona.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx

from app.cache import TTLCache
from app.config import Settings
from app.matching import build_espn_index, build_name_index, match_players, strip_html
from app.models import NewsItem, Player


def _hash_id(*parts: str) -> str:
    return hashlib.sha1("|".join(p for p in parts if p).encode("utf-8")).hexdigest()[:16]


def _parse_datetime(value: Any) -> datetime | None:
    """Acepta ISO-8601 (ESPN) o un struct_time (feedparser)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    # struct_time de feedparser
    try:
        return datetime(*value[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _source_from_url(url: str | None, fallback: str = "RSS") -> str:
    if not url:
        return fallback
    host = urlparse(url).netloc.lower()
    host = host.removeprefix("www.").removeprefix("api.")
    return host.split(".")[0].upper() if host else fallback


def parse_espn_news(payload: dict[str, Any]) -> list[NewsItem]:
    """Normaliza la respuesta de `site.api.espn.com/.../nfl/news`."""
    items: list[NewsItem] = []
    for article in (payload or {}).get("articles") or []:
        if not isinstance(article, dict):
            continue
        headline = (article.get("headline") or article.get("title") or "").strip()
        if not headline:
            continue
        links = article.get("links") or {}
        web = links.get("web") if isinstance(links, dict) else None
        url = web.get("href") if isinstance(web, dict) else None

        images = article.get("images") or []
        image_url = None
        if images and isinstance(images[0], dict):
            image_url = images[0].get("url")

        # ESPN etiqueta las noticias con los atletas que aparecen: eso da un
        # emparejamiento exacto, sin depender del texto.
        espn_ids: list[str] = []
        for category in article.get("categories") or []:
            if not isinstance(category, dict):
                continue
            athlete = category.get("athlete")
            if isinstance(athlete, dict) and athlete.get("id") is not None:
                espn_ids.append(str(athlete["id"]))

        items.append(
            NewsItem(
                id=_hash_id("espn", url or headline),
                title=headline,
                summary=strip_html(article.get("description") or "").strip() or None,
                url=url,
                source="ESPN",
                published=_parse_datetime(article.get("published") or article.get("lastModified")),
                image_url=image_url,
                player_names=espn_ids,  # se traduce a player_ids más abajo
            )
        )
    return items


def parse_rss(content: bytes | str, feed_url: str) -> list[NewsItem]:
    """Normaliza un feed RSS/Atom con feedparser."""
    parsed = feedparser.parse(content)
    source = (
        (parsed.feed.get("title") if hasattr(parsed, "feed") else None)
        or _source_from_url(feed_url)
    )
    source = str(source).replace(" - RSS", "").strip()[:40]

    items: list[NewsItem] = []
    for entry in parsed.entries or []:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        link = entry.get("link")
        summary = strip_html(entry.get("summary") or entry.get("description") or "").strip()
        image_url = None
        for media in entry.get("media_content") or []:
            if isinstance(media, dict) and media.get("url"):
                image_url = media["url"]
                break
        if not image_url:
            for link_info in entry.get("links") or []:
                if isinstance(link_info, dict) and str(
                    link_info.get("type", "")
                ).startswith("image/"):
                    image_url = link_info.get("href")
                    break

        items.append(
            NewsItem(
                id=_hash_id(source, link or title),
                title=title,
                summary=summary or None,
                url=link,
                source=source,
                published=_parse_datetime(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                ),
                image_url=image_url,
            )
        )
    return items


def dedupe(items: list[NewsItem]) -> list[NewsItem]:
    """Quita noticias repetidas (misma URL o mismo titular)."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[NewsItem] = []
    for item in items:
        url_key = (item.url or "").split("?")[0].rstrip("/").lower()
        title_key = item.title.strip().lower()
        if url_key and url_key in seen_urls:
            continue
        if title_key in seen_titles:
            continue
        if url_key:
            seen_urls.add(url_key)
        seen_titles.add(title_key)
        unique.append(item)
    return unique


def sort_by_recency(items: list[NewsItem]) -> list[NewsItem]:
    """Lo más reciente primero; lo que no tiene fecha, al final."""
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return sorted(items, key=lambda i: i.published or epoch, reverse=True)


def annotate_players(
    items: list[NewsItem],
    players: dict[str, Player],
) -> list[NewsItem]:
    """Rellena `player_ids` y `player_names` de cada noticia."""
    name_index = build_name_index(players.values())
    espn_index = build_espn_index(players.values())

    for item in items:
        matched: list[str] = []
        # 1) Etiquetas de atleta de ESPN (exactas).
        for espn_id in item.player_names:
            pid = espn_index.get(str(espn_id))
            if pid and pid not in matched:
                matched.append(pid)
        # 2) Nombres reconocidos en titular + resumen.
        text = f"{item.title}. {item.summary or ''}"
        for pid in match_players(text, name_index):
            if pid not in matched:
                matched.append(pid)

        item.player_ids = matched
        item.player_names = [players[pid].name for pid in matched if pid in players]
    return items


class NewsProvider:
    """Descarga y cachea las noticias de todas las fuentes configuradas."""

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

    async def _fetch_espn(self) -> list[NewsItem]:
        response = await self.client.get(
            self.settings.espn_news_url, params={"limit": 50}
        )
        response.raise_for_status()
        return parse_espn_news(response.json())

    async def _fetch_feed(self, url: str) -> list[NewsItem]:
        response = await self.client.get(url)
        response.raise_for_status()
        return parse_rss(response.content, url)

    async def _fetch_all(self) -> list[dict[str, Any]]:
        tasks = [self._fetch_espn()] + [
            self._fetch_feed(url) for url in self.settings.news_feeds
        ]
        labels = ["ESPN API"] + list(self.settings.news_feeds)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        items: list[NewsItem] = []
        errors: list[str] = []
        for label, result in zip(labels, results):
            if isinstance(result, BaseException):
                errors.append(f"{_source_from_url(label, label)}: {result}")
                continue
            items.extend(result)

        self.last_errors = errors
        items = sort_by_recency(dedupe(items))[: self.settings.news_max_items]
        # Se cachea como JSON plano para poder guardarlo también en disco.
        return [item.model_dump(mode="json") for item in items]

    async def get_news(self, players: dict[str, Player] | None = None) -> list[NewsItem]:
        """Noticias agregadas, ya etiquetadas con los jugadores mencionados."""
        raw = await self.cache.get_or_set(
            "news:all",
            self.settings.cache_ttl_news,
            self._fetch_all,
            use_disk=True,
        )
        items = [NewsItem.model_validate(entry) for entry in raw]
        if players:
            items = annotate_players(items, players)
        return items

    async def get_player_news(
        self, player_id: str, players: dict[str, Player], limit: int = 20
    ) -> list[NewsItem]:
        """Noticias que mencionan a un jugador concreto."""
        items = await self.get_news(players)
        return [item for item in items if player_id in item.player_ids][:limit]
