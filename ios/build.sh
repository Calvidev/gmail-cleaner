#!/usr/bin/env bash
# Compila la app sin tener que acordarse del comando de xcodebuild.
#
#   ./ios/build.sh            comprueba que compila (rápido, sin firmar)
#   ./ios/build.sh sim        compila para el simulador
#   ./ios/build.sh runtime    descarga el simulador de iOS que falte
#   ./ios/build.sh abrir      abre el proyecto en Xcode
#
# El log entero queda en /tmp/sleeperscore-build.log; por pantalla solo salen
# los errores y el resultado.

set -uo pipefail
cd "$(dirname "$0")"

PROYECTO="SleeperScore.xcodeproj"
ESQUEMA="SleeperScore"
LOG="/tmp/sleeperscore-build.log"
MODO="${1:-check}"

if ! command -v xcodebuild >/dev/null 2>&1; then
  echo "✗ No encuentro xcodebuild. ¿Está Xcode instalado y seleccionado?"
  echo "  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
  exit 1
fi

compilar() {
  local sdk="$1" destino="$2" titulo="$3"
  echo "▸ $titulo"
  echo "  (log completo en $LOG)"
  xcodebuild -project "$PROYECTO" -scheme "$ESQUEMA" \
    -sdk "$sdk" -destination "$destino" -configuration Debug \
    CODE_SIGNING_ALLOWED=NO build >"$LOG" 2>&1
  local codigo=$?

  if grep -q "\*\* BUILD SUCCEEDED \*\*" "$LOG"; then
    local avisos
    avisos=$(grep -c "warning:" "$LOG")
    echo "✓ Compila. Avisos: $avisos"
    return 0
  fi

  echo "✗ Falló. Esto es lo que dice:"
  echo
  grep -E "error:" "$LOG" | sed 's/^/   /' | sort -u | head -25
  echo

  # El fallo más habitual tras actualizar Xcode: falta el simulador nuevo.
  if grep -q "No simulator runtime version" "$LOG"; then
    echo "   → Te falta el runtime del simulador de esta versión de Xcode."
    echo "     Arréglalo con:  ./ios/build.sh runtime"
  fi
  return "${codigo:-1}"
}

case "$MODO" in
  check)
    # Contra el SDK de dispositivo: no necesita simulador instalado.
    compilar iphoneos "generic/platform=iOS" "Comprobando que compila (SDK de dispositivo, sin firmar)"
    ;;
  sim)
    compilar iphonesimulator "generic/platform=iOS Simulator" "Compilando para el simulador"
    ;;
  runtime)
    echo "▸ Descargando el simulador de iOS que corresponde a tu Xcode (son varios GB)…"
    xcodebuild -downloadPlatform iOS
    ;;
  abrir)
    open "$PROYECTO"
    ;;
  *)
    echo "Uso: ./ios/build.sh [check|sim|runtime|abrir]"
    exit 2
    ;;
esac
