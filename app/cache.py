"""Caché sencilla con TTL: memoria + disco.

El catálogo de jugadores de Sleeper pesa varios MB, así que se guarda en disco
para no volver a descargarlo en cada arranque. Las noticias y tendencias viven
en memoria con un TTL corto.
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


class TTLCache:
    """Caché clave/valor con expiración y respaldo opcional en disco."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._memory: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._cache_dir = cache_dir
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)

    # -- utilidades internas -------------------------------------------------

    def _path_for(self, key: str) -> Path | None:
        if self._cache_dir is None:
            return None
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)[:40]
        return self._cache_dir / f"{safe}-{digest}.json.gz"

    def _lock_for(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    # -- API pública ---------------------------------------------------------

    def get(self, key: str, ttl: int, *, use_disk: bool = False) -> Any | None:
        """Devuelve el valor si sigue vigente; si no, None."""
        hit = self._memory.get(key)
        now = time.time()
        if hit is not None and now - hit[0] < ttl:
            return hit[1]

        if use_disk:
            path = self._path_for(key)
            if path is not None and path.exists():
                age = now - path.stat().st_mtime
                if age < ttl:
                    try:
                        with gzip.open(path, "rt", encoding="utf-8") as fh:
                            value = json.load(fh)
                    except (OSError, ValueError):
                        return None
                    self._memory[key] = (now - age, value)
                    return value
        return None

    def set(self, key: str, value: Any, *, use_disk: bool = False) -> None:
        """Guarda un valor en memoria (y en disco si se pide)."""
        self._memory[key] = (time.time(), value)
        if use_disk:
            path = self._path_for(key)
            if path is not None:
                try:
                    tmp = path.with_suffix(".tmp")
                    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
                        json.dump(value, fh)
                    tmp.replace(path)
                except (OSError, TypeError, ValueError):
                    # La caché en disco es un extra: si falla, seguimos con memoria.
                    pass

    def get_stale(self, key: str, *, use_disk: bool = False) -> Any | None:
        """Devuelve el valor aunque haya expirado (plan B si la red falla)."""
        return self.get(key, ttl=10**9, use_disk=use_disk)

    async def get_or_set(
        self,
        key: str,
        ttl: int,
        factory: Callable[[], Awaitable[T]],
        *,
        use_disk: bool = False,
        fallback_to_stale: bool = True,
    ) -> T:
        """Devuelve el valor cacheado o lo genera con `factory`.

        Si `factory` falla y hay un valor viejo guardado, se devuelve ese en
        lugar de propagar el error: mejor datos con retraso que una pantalla en
        blanco.
        """
        cached = self.get(key, ttl, use_disk=use_disk)
        if cached is not None:
            return cached

        async with self._lock_for(key):
            # Otro coroutine pudo haberlo rellenado mientras esperábamos.
            cached = self.get(key, ttl, use_disk=use_disk)
            if cached is not None:
                return cached
            try:
                value = await factory()
            except Exception:
                if fallback_to_stale:
                    stale = self.get_stale(key, use_disk=use_disk)
                    if stale is not None:
                        return stale
                raise
            self.set(key, value, use_disk=use_disk)
            return value

    def invalidate(self, key: str | None = None) -> None:
        """Borra una clave, o toda la caché en memoria si no se indica clave."""
        if key is None:
            self._memory.clear()
            return
        self._memory.pop(key, None)
        path = self._path_for(key)
        if path is not None and path.exists():
            try:
                path.unlink()
            except OSError:
                pass
