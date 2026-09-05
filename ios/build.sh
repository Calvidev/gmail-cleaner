#!/usr/bin/env bash
# Compila la app sin tener que acordarse del comando de xcodebuild.
#
#   ./ios/build.sh            comprueba que compila (rápido, sin firmar)
#   ./ios/build.sh iphone     compila, firma e instala en el iPhone conectado
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

# El Team ID sale de lo que pusiste en Xcode al elegir tu cuenta; si no está,
# se puede pasar a mano:  DEVELOPMENT_TEAM=ABCDE12345 ./ios/build.sh iphone
equipo_de_firma() {
  if [ -n "${DEVELOPMENT_TEAM:-}" ]; then
    echo "$DEVELOPMENT_TEAM"
    return 0
  fi
  grep -m1 -o 'DEVELOPMENT_TEAM = [A-Z0-9]*' "$PROYECTO/project.pbxproj" 2>/dev/null \
    | awk '{print $3}'
}

# El primer iPhone conectado (por cable o emparejado por red).
iphone_conectado() {
  local json="/tmp/sleeperscore-devices.json"
  xcrun devicectl list devices --json-output "$json" >/dev/null 2>&1 || return 1
  python3 - "$json" <<'PYTHON'
import json, sys
try:
    datos = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
for d in datos.get("result", {}).get("devices", []):
    propiedades = d.get("deviceProperties", {})
    hardware = d.get("hardwareProperties", {})
    if hardware.get("platform") != "iOS":
        continue
    estado = d.get("connectionProperties", {}).get("tunnelState")
    if estado == "unavailable":
        continue
    print(d.get("identifier", ""), propiedades.get("name", "iPhone"), sep="\t")
    break
PYTHON
}

instalar_en_iphone() {
  local equipo derivados app paquete dispositivo udid nombre
  equipo="$(equipo_de_firma)"
  if [ -z "$equipo" ]; then
    echo "✗ No sé con qué cuenta firmar."
    echo "  Abre el proyecto en Xcode una vez y elige tu Team en Signing & Capabilities,"
    echo "  o lánzalo así:  DEVELOPMENT_TEAM=TU_TEAM_ID ./ios/build.sh iphone"
    return 1
  fi

  dispositivo="$(iphone_conectado || true)"
  if [ -z "$dispositivo" ]; then
    echo "✗ No veo ningún iPhone. Conéctalo por cable y desbloquéalo (y dale a 'Confiar')."
    return 1
  fi
  udid="${dispositivo%%$'\t'*}"
  nombre="${dispositivo#*$'\t'}"

  derivados="$HOME/Library/Developer/Xcode/DerivedData/SleeperScore-cli"
  echo "▸ Compilando y firmando (equipo $equipo)"
  echo "  (log completo en $LOG)"
  xcodebuild -project "$PROYECTO" -scheme "$ESQUEMA" -configuration Debug \
    -destination "generic/platform=iOS" -derivedDataPath "$derivados" \
    DEVELOPMENT_TEAM="$equipo" -allowProvisioningUpdates build >"$LOG" 2>&1

  if ! grep -q "\*\* BUILD SUCCEEDED \*\*" "$LOG"; then
    echo "✗ Falló al compilar o firmar:"
    echo
    grep -E "error:" "$LOG" | sed 's/^/   /' | sort -u | head -25
    return 1
  fi

  app="$derivados/Build/Products/Debug-iphoneos/SleeperScore.app"
  if [ ! -d "$app" ]; then
    echo "✗ Compiló pero no encuentro $app"
    return 1
  fi

  echo "▸ Instalando en $nombre"
  xcrun devicectl device install app --device "$udid" "$app" || return 1

  paquete="$(plutil -extract CFBundleIdentifier raw "$app/Info.plist" 2>/dev/null)"
  if [ -n "$paquete" ]; then
    echo "▸ Abriendo la app"
    xcrun devicectl device process launch --device "$udid" "$paquete" >/dev/null 2>&1 \
      || echo "  (instalada; ábrela a mano si no se ha abierto sola)"
  fi
  echo "✓ Listo en $nombre"
}

case "$MODO" in
  check)
    # Contra el SDK de dispositivo: no necesita simulador instalado.
    compilar iphoneos "generic/platform=iOS" "Comprobando que compila (SDK de dispositivo, sin firmar)"
    ;;
  iphone)
    instalar_en_iphone
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
    echo "Uso: ./ios/build.sh [check|iphone|sim|runtime|abrir]"
    exit 2
    ;;
esac
