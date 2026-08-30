"""Caché con TTL: expiración, disco y plan B cuando falla la red."""

import asyncio

import pytest

from app.cache import TTLCache


class TestMemoria:
    def test_guarda_y_devuelve(self):
        cache = TTLCache(None)
        cache.set("k", {"a": 1})
        assert cache.get("k", ttl=60) == {"a": 1}

    def test_una_clave_que_no_existe(self):
        assert TTLCache(None).get("nada", ttl=60) is None

    def test_expira(self):
        cache = TTLCache(None)
        cache.set("k", 1)
        assert cache.get("k", ttl=0) is None  # TTL de cero: siempre caducado

    def test_get_stale_devuelve_lo_caducado(self):
        cache = TTLCache(None)
        cache.set("k", 1)
        assert cache.get("k", ttl=0) is None
        assert cache.get_stale("k") == 1

    def test_invalidar_una_clave(self):
        cache = TTLCache(None)
        cache.set("k", 1)
        cache.invalidate("k")
        assert cache.get("k", ttl=60) is None

    def test_invalidar_todo(self):
        cache = TTLCache(None)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.invalidate()
        assert cache.get("a", ttl=60) is None and cache.get("b", ttl=60) is None


class TestDisco:
    def test_sobrevive_a_una_instancia_nueva(self, tmp_path):
        TTLCache(tmp_path).set("k", {"grande": [1, 2, 3]}, use_disk=True)
        assert TTLCache(tmp_path).get("k", ttl=60, use_disk=True) == {"grande": [1, 2, 3]}

    def test_no_se_lee_si_ya_caducó(self, tmp_path):
        TTLCache(tmp_path).set("k", 1, use_disk=True)
        assert TTLCache(tmp_path).get("k", ttl=0, use_disk=True) is None

    def test_un_archivo_corrupto_no_rompe(self, tmp_path):
        TTLCache(tmp_path).set("k", 1, use_disk=True)
        for archivo in tmp_path.iterdir():
            archivo.write_bytes(b"basura")
        # Instancia nueva: sin memoria, tiene que leer el archivo roto.
        assert TTLCache(tmp_path).get("k", ttl=60, use_disk=True) is None

    def test_un_valor_no_serializable_no_lanza_excepcion(self, tmp_path):
        cache = TTLCache(tmp_path)
        cache.set("k", {1, 2, 3}, use_disk=True)  # los sets no son JSON
        assert cache.get("k", ttl=60) == {1, 2, 3}  # en memoria sí queda


class TestGetOrSet:
    async def test_solo_llama_a_la_factoria_una_vez(self):
        cache = TTLCache(None)
        llamadas = {"n": 0}

        async def factory():
            llamadas["n"] += 1
            return "valor"

        assert await cache.get_or_set("k", 60, factory) == "valor"
        assert await cache.get_or_set("k", 60, factory) == "valor"
        assert llamadas["n"] == 1

    async def test_varias_corrutinas_a_la_vez_solo_descargan_una_vez(self):
        cache = TTLCache(None)
        llamadas = {"n": 0}

        async def factory():
            llamadas["n"] += 1
            await asyncio.sleep(0.01)
            return "valor"

        resultados = await asyncio.gather(*[cache.get_or_set("k", 60, factory) for _ in range(5)])
        assert resultados == ["valor"] * 5
        assert llamadas["n"] == 1

    async def test_si_la_factoria_falla_se_usa_el_valor_viejo(self):
        cache = TTLCache(None)
        cache.set("k", "viejo")

        async def factory():
            raise RuntimeError("red caída")

        assert await cache.get_or_set("k", 0, factory) == "viejo"

    async def test_sin_valor_viejo_el_error_se_propaga(self):
        cache = TTLCache(None)

        async def factory():
            raise RuntimeError("red caída")

        with pytest.raises(RuntimeError):
            await cache.get_or_set("k", 60, factory)


class TestDirectorioNoEscribible:
    """En un contenedor con disco persistente, el volumen se monta como root.
    Si la aplicación corre con otro usuario, no podría escribir la caché."""

    def test_si_no_se_puede_escribir_avisa_y_sigue_en_memoria(
        self, tmp_path, caplog, monkeypatch
    ):
        import logging
        from pathlib import Path

        # Se simula el fallo de escritura en vez de usar permisos: los tests
        # también se ejecutan como root, y root escribe en cualquier sitio.
        def sin_permiso(self, *args, **kwargs):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(Path, "write_bytes", sin_permiso)

        with caplog.at_level(logging.WARNING):
            cache = TTLCache(tmp_path)

        assert any("solo en memoria" in r.getMessage() for r in caplog.records)

        # Y aun así la aplicación funciona: la caché se queda en memoria.
        monkeypatch.undo()
        cache.set("k", {"a": 1}, use_disk=True)
        assert cache.get("k", ttl=60) == {"a": 1}
        assert list(tmp_path.iterdir()) == []  # no ha tocado el disco

    def test_un_directorio_escribible_si_usa_el_disco(self, tmp_path):
        cache = TTLCache(tmp_path)
        cache.set("k", {"a": 1}, use_disk=True)
        # Una instancia nueva, sin memoria, tiene que encontrarlo en disco.
        assert TTLCache(tmp_path).get("k", ttl=60, use_disk=True) == {"a": 1}

    def test_el_directorio_se_crea_si_no_existe(self, tmp_path):
        destino = tmp_path / "nuevo" / "anidado"
        TTLCache(destino)
        assert destino.is_dir()

    def test_no_deja_rastro_de_la_comprobacion(self, tmp_path):
        TTLCache(tmp_path)
        assert list(tmp_path.iterdir()) == []
