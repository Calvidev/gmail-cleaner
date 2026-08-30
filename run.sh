#!/usr/bin/env bash
# Arranca Fantasy Tool. Crea el entorno virtual la primera vez.
#
# Hace falta Python 3.10 o superior. macOS trae de serie el 3.9 de Xcode, que
# no sirve, así que el script busca uno válido antes de nada.
set -euo pipefail
cd "$(dirname "$0")"

VERSION_MINIMA_MAYOR=3
VERSION_MINIMA_MENOR=10

# ¿Sirve este intérprete?
es_valido() {
  "$1" -c "import sys; sys.exit(0 if sys.version_info >= ($VERSION_MINIMA_MAYOR, $VERSION_MINIMA_MENOR) else 1)" 2>/dev/null
}

version_de() {
  "$1" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || echo "?"
}

# Se busca de la más nueva a la más vieja; `python3` a secas va al final porque
# en macOS suele ser justo el que no sirve.
buscar_python() {
  local candidato
  for candidato in python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidato" >/dev/null 2>&1 && es_valido "$candidato"; then
      command -v "$candidato"
      return 0
    fi
  done
  return 1
}

explicar_como_instalar() {
  local encontrada
  encontrada="$(version_de python3)"
  cat >&2 <<MENSAJE

  ✗ Fantasy Tool necesita Python ${VERSION_MINIMA_MAYOR}.${VERSION_MINIMA_MENOR} o superior.
    En este equipo la versión disponible es la ${encontrada}.

    macOS trae de serie el Python 3.9 de las herramientas de Xcode, que ya no
    sirve para esta aplicación. Instala uno más nuevo de cualquiera de estas dos
    formas:

      1) Instalador oficial (lo más sencillo, sin terminal):
         https://www.python.org/downloads/macos/
         Descarga la última versión, ábrela y sigue los pasos.

      2) Con Homebrew, si ya lo tienes:
         brew install python@3.12

    Linux (Debian o Ubuntu):
         sudo apt install python3.12 python3.12-venv

    Cuando termines, vuelve a ejecutar ./run.sh

MENSAJE
}

if ! PYTHON="$(buscar_python)"; then
  explicar_como_instalar
  exit 1
fi

# Si ya hay un entorno virtual pero se creó con una versión que no sirve, hay
# que rehacerlo: reutilizarlo daría exactamente el mismo error otra vez.
if [ -d .venv ] && ! es_valido ./.venv/bin/python; then
  echo "El entorno virtual se creó con Python $(version_de ./.venv/bin/python), que no sirve."
  echo "Rehaciéndolo con Python $(version_de "$PYTHON")…"
  rm -rf .venv
fi

if [ ! -d .venv ]; then
  echo "Creando el entorno virtual con Python $(version_de "$PYTHON")…"
  "$PYTHON" -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  echo "Instalando dependencias…"
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

PORT="${PORT:-8000}"
echo
echo "  Fantasy Tool lista en http://127.0.0.1:${PORT}"
echo "  (para parar, Ctrl+C)"
echo
exec ./.venv/bin/python -m uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT}" "$@"
