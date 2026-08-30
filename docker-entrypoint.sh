#!/bin/sh
# Arranque del contenedor.
#
# Los discos persistentes (el volumen de Fly.io, el de Docker, el de Kubernetes)
# se montan siempre como root. Como la aplicación corre con un usuario sin
# privilegios, sin este paso no podría escribir la caché y volvería a descargar
# el catálogo de jugadores en cada arranque.
#
# Todo está escrito para que nunca impida arrancar: si algún paso no se puede
# dar, se avisa y se sigue adelante. Un contenedor que no levanta es mucho peor
# que uno que corre con más permisos de los deseables.
set -e

USUARIO=fantasy

if [ "$(id -u)" = "0" ]; then
  # 1. Cederle el directorio de caché al usuario de la aplicación.
  chown -R "$USUARIO" /app/.cache 2>/dev/null || \
    echo "aviso: no se pudo ceder /app/.cache a $USUARIO; la caché irá solo en memoria" >&2

  # 2. Bajar de privilegios. Se prueba primero en seco: si setpriv no está o el
  #    usuario no existe, es preferible seguir como root que no arrancar.
  if command -v setpriv >/dev/null 2>&1 &&
     setpriv --reuid="$USUARIO" --regid="$USUARIO" --init-groups true 2>/dev/null; then
    exec setpriv --reuid="$USUARIO" --regid="$USUARIO" --init-groups "$@"
  fi
  echo "aviso: no se pudo bajar de privilegios; la aplicación correrá como root" >&2
fi

exec "$@"
