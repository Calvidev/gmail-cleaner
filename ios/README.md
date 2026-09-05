# Marcador Sleeper — app de iOS

El widget de Scriptable (`scriptable/sleeper-score-widget.js`), convertido en una
app de iPhone de verdad: **SwiftUI + WidgetKit**, sin Scriptable de por medio.

Hace lo mismo que el widget —tu enfrentamiento de la jornada con avatares,
barra de reparto y diferencia— y añade lo que un widget no puede: la alineación
titular jugador a jugador, elegir la liga y el equipo desde una pantalla de
ajustes, y widgets también en la pantalla de bloqueo.

```
ios/
├── Shared/            código que comparten la app y el widget
├── SleeperScore/      la app (pantallas)
├── ScoreWidget/       la extensión de widget
├── SleeperScore.xcodeproj
├── project.yml        la misma estructura, en legible (XcodeGen)
├── tools/             generador y validador del .xcodeproj
└── scriptable/        el widget original, tal cual
```

## Qué hace falta

- Un Mac con **Xcode 16** o superior.
- Un iPhone con **iOS 17** o superior (el simulador vale para la app; los
  widgets se ven mucho mejor en el teléfono).
- Una cuenta de Apple. Con la gratuita se instala en tu propio iPhone y hay que
  volver a firmar cada 7 días; lee más abajo lo del *App Group*.

## El atajo: `build.sh`

Para no pelearse con `xcodebuild`:

```bash
./ios/build.sh            # ¿compila? (rápido, sin firmar ni simulador)
./ios/build.sh sim        # compila para el simulador
./ios/build.sh runtime    # descarga el simulador de iOS que falte
./ios/build.sh abrir      # abre el proyecto en Xcode
```

Por pantalla salen solo los errores y el resultado; el log entero queda en
`/tmp/sleeperscore-build.log`.

## Cómo arrancarla (5 minutos)

1. **Abre el proyecto**: `open ios/SleeperScore.xcodeproj`.
2. **Firma**: selecciona el objetivo `SleeperScore` > *Signing & Capabilities* >
   *Team*, y elige tu cuenta. Repite en el objetivo `ScoreWidgetExtension`.
3. **Identificadores**: si Xcode se queja de que `dev.calvi.sleeperscore` está
   cogido, cambia los dos identificadores (app y widget) por los tuyos. El del
   widget tiene que empezar por el de la app y acabar en algo: `tuid.app` y
   `tuid.app.widget`.
4. **App Group** (lo que hace que el widget vea la liga que eliges en la app):
   en *Signing & Capabilities* de los dos objetivos hay un App Group llamado
   `group.dev.calvi.sleeperscore`. Si lo cambias, cámbialo en los tres sitios:
   los dos `.entitlements` y `AppConfig.appGroupID`.
5. **Ejecuta** (⌘R) con el iPhone conectado. Para poner el widget: mantén pulsada
   la pantalla de inicio > **+** > busca *Marcador*. En la de bloqueo, edítala y
   añade el widget rectangular o el de una línea.

La app arranca ya apuntando a tu liga (`1263745758830530560`, equipo 1): son los
valores del widget original, escritos en `Shared/AppConfig.swift`. Para cambiarla,
toca el engranaje y **escribe tu usuario de Sleeper**: salen todas tus ligas de la
temporada y, al elegir una, la app reconoce sola cuál es tu equipo. No hace falta
contraseña (la API de Sleeper es pública y de solo lectura) ni buscar ningún id.

### Si el App Group no te deja

Las cuentas gratuitas de Apple a veces no permiten activar App Groups. No pasa
nada: la app funciona igual y el widget también, pero el widget se queda con la
liga por defecto del código en vez de con la que elijas en Ajustes. La propia
pantalla de Ajustes te dice en qué caso estás. Para arreglarlo sin cuenta de
pago, cambia `defaultLeagueID` y `defaultRosterID` en `Shared/AppConfig.swift`.

## Qué se ve

| Pantalla / tamaño | Qué enseña |
| --- | --- |
| App | Marcador grande, diferencia, barra, y la alineación hueco a hueco con los puntos de cada titular |
| Ajustes | Entrar con tu usuario, tus ligas, equipos con avatar, estado del App Group, catálogo de jugadores |
| Widget pequeño | Los dos equipos con avatar, puntos y barra |
| Widget mediano | Lo mismo del widget original: cabecera, dos columnas, diferencia, barra y pie |
| Widget grande | El mediano + los primeros huecos de la alineación con nombres abreviados |
| Bloqueo (rectangular / línea) | Jornada y marcador |

La app se refresca sola cada minuto mientras la tienes abierta, y al tirar hacia
abajo. El widget pide refresco cada 10 minutos si hay partido en marcha y cada
hora si no; **quien decide de verdad cuándo refrescar es iOS**, así que en pleno
domingo puede tardar más de 10 minutos en moverse.

## Cómo está montado

Las mismas cinco llamadas que hacía el widget de Scriptable, en
`Shared/MatchupService.swift`:

| Llamada | Para qué |
| --- | --- |
| `GET /state/nfl` | la jornada y la temporada en curso |
| `GET /user/{usuario}` | tu `user_id` a partir del nombre de usuario |
| `GET /user/{user_id}/leagues/nfl/{año}` | tus ligas de la temporada |
| `GET /league/{id}` | nombre de la liga y huecos de la alineación |
| `GET /league/{id}/users` | nombres de equipo y avatares |
| `GET /league/{id}/rosters` | qué manager lleva cada roster, y su récord |
| `GET /league/{id}/matchups/{semana}` | los puntos, titular a titular |
| `GET /players/nfl` | los nombres de los jugadores (5 MB, una vez al día, solo desde la app) |

Todo lo que se pinta cabe en un `MatchupSnapshot`, que se guarda entero en el
App Group. De ahí salen dos cosas importantes: el widget no repite el trabajo de
la app, y si no hay red se enseña el último marcador conocido con el aviso
"Datos guardados" en vez de un hueco vacío.

El catálogo de jugadores lo descarga **solo la app**, recortado a nombre,
posición y equipo. El widget nunca baja esos 5 MB: si el archivo está, pone los
nombres; si no, enseña el marcador sin la alineación.

## Regenerar el .xcodeproj

El proyecto está generado con un script para que no haya que escribir un
`.pbxproj` a mano. Si añades archivos Swift, lo normal es arrastrarlos en Xcode
(acuérdate de marcar **los dos objetivos** si el archivo va en `Shared/`). Si
prefieres regenerarlo entero:

```bash
cd ios
python3 tools/generate_xcodeproj.py   # reescribe el .pbxproj y el esquema
python3 tools/check_pbxproj.py        # lo relee y comprueba que cuadra
```

Los archivos nuevos hay que añadirlos a las listas de `tools/generate_xcodeproj.py`.
Ojo: regenerar **borra el equipo de firma** que hayas puesto en Xcode; hay que
volver a elegirlo (paso 2).

Como plan B está `project.yml`, la misma estructura para
[XcodeGen](https://github.com/yonaskolb/XcodeGen): `brew install xcodegen && cd ios && xcodegen generate`.

## Lo que aún no está probado

El proyecto se escribió en Linux, donde no hay Xcode: **no se ha compilado ni
ejecutado**. La estructura del `.pbxproj` sí está verificada
(`tools/check_pbxproj.py` lo relee entero y comprueba que cada archivo declarado
existe), pero un error de compilación de Swift solo aparece al abrirlo en el Mac.
Si sale alguno, dímelo con el mensaje y lo arreglo.

Tampoco hay tests: los del repo (`pytest`) son de la herramienta web en Python y
no tocan esta carpeta.
