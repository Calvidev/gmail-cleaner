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
./ios/build.sh              # ¿compila? (rápido, sin firmar ni simulador)
./ios/build.sh actualizar   # trae los cambios de git sin pelearse por la firma
./ios/build.sh equipo ABC   # guarda tu Team ID (una vez y para siempre)
./ios/build.sh iphone       # compila, firma e instala en el iPhone conectado
./ios/build.sh sim          # compila para el simulador
./ios/build.sh runtime      # descarga el simulador de iOS que falte
./ios/build.sh abrir        # abre el proyecto en Xcode
```

**Por qué existe `actualizar`**: Xcode escribe tu equipo de firma dentro del
`project.pbxproj`, que está versionado, así que cada `git pull` choca con él.
`actualizar` rescata ese Team ID a `ios/.team` (que git ignora), descarta el
cambio y hace el pull. A partir de ahí `iphone` firma con lo que haya en
`.team` y ya nadie se pisa.

Por pantalla salen solo los errores y el resultado; el log entero queda en
`/tmp/sleeperscore-build.log`.

`iphone` es el atajo a ⌘R: compila firmando con la cuenta que elegiste en Xcode,
instala en el primer iPhone conectado y la abre. El iPhone tiene que estar
desbloqueado y haber dado a "Confiar". Si nunca abriste el proyecto en Xcode, no
sabrá con qué cuenta firmar; entonces pásale el equipo a mano:

```bash
./ios/build.sh equipo TU_TEAM_ID     # se guarda y no vuelve a preguntar
```

El Team ID está en Xcode > Settings > Accounts (columna *Team ID*) o en
developer.apple.com/account.

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
| App | Marcador, **probabilidad de ganar**, proyección, puntos dejados en el banquillo, últimas anotaciones y la alineación con foto y puntos |
| Clasificación | La tabla de la liga con récord y puntos a favor y en contra |
| Mi temporada | Puntos por jornada en gráfica, récord, media, mejor y peor semana |
| Noticias | Las de tus jugadores, cruzadas por id de ESPN, con aviso |
| Compartir | Una imagen del marcador para el grupo de la liga |
| Cuentas | Sleeper y Yahoo conectables; ESPN y NFL.com apagadas hasta que se integren |
| Ajustes de Sleeper | Entrar con tu usuario, tus ligas, equipos con avatar |
| Live Activity | Marcador en la pantalla de bloqueo y en la Dynamic Island, con la última anotación: foto, nombre, línea estadística ("6 rec · 88 yds · 1 TD") y puntos |
| Widget pequeño | Los dos equipos con avatar, puntos y barra |
| Widget mediano | Lo mismo del widget original: cabecera, dos columnas, diferencia, barra y pie |
| Widget grande | El mediano + los primeros huecos de la alineación con nombres abreviados |
| Bloqueo (rectangular / línea) | Jornada y marcador |

La app se refresca sola cada minuto mientras la tienes abierta, y al tirar hacia
abajo. El widget pide refresco cada 10 minutos si hay partido en marcha y cada
hora si no; **quien decide de verdad cuándo refrescar es iOS**, así que en pleno
domingo puede tardar más de 10 minutos en moverse.

## Cuentas: qué está conectado y qué no

El menú de cuentas (el engranaje) ofrece cuatro plataformas:

| | Estado | Qué hace falta |
| --- | --- | --- |
| **Sleeper** | Funciona | Tu nombre de usuario. Nada más: su API de lectura es pública |
| **Yahoo** | Inicia sesión | Registrar una app en developer.yahoo.com y pegar el client id y el secreto |
| **ESPN** | Apagada | Su API no es pública; las ligas privadas piden las cookies de sesión |
| **NFL.com** | Apagada | Su API tampoco es pública |

Las dos últimas salen en gris y no se pueden tocar. Están para decir "esto
viene después", no para aparentar que ya funcionan.

**Sobre Yahoo, con todas las letras**: hoy el botón *inicia sesión y guarda el
token en el llavero*, nada más. Leer tus ligas de Yahoo y pintar su marcador es
el paso siguiente y **no está hecho**: el marcador sigue saliendo de Sleeper. El
client id y el secreto no vienen en el código a propósito —un secreto dentro de
una app de iPhone lo extrae cualquiera del binario— así que se piden una vez y
se guardan en el llavero de tu teléfono. La dirección de vuelta por defecto es
`sleeperscore://yahoo`; si Yahoo rechaza los esquemas propios y exige una `https`,
hay que cambiarla en la misma pantalla y en el registro de la app.

## Live Activity: el marcador en la pantalla de bloqueo

Botón **"Seguir en la pantalla de bloqueo"** bajo el marcador. Enciende una Live
Activity con los dos equipos, la barra, la diferencia y —cuando alguien anota— la
foto, el nombre y los puntos de la jugada, tanto en la pantalla de bloqueo como
en la Dynamic Island. Además suena una notificación por cada anotación (hasta
tres por refresco, para no convertirlo en una metralleta).

Las anotaciones se deducen restando: Sleeper no avisa de las jugadas, da los
puntos acumulados de cada titular, y `ScoringDetector` compara la lectura nueva
con la anterior. Diferencias menores de 0,1 puntos se ignoran, que son las
correcciones de estadísticas.

**La limitación importante**: una Live Activity no se refresca sola como un
widget. Se actualiza cuando la app puede hacerlo (abierta, o en los ratos de
segundo plano que conceda iOS) o por push, y el push necesita la capacidad de
notificaciones remotas, que **pide cuenta de desarrollador de pago**. Con cuenta
gratuita funciona, pero se queda quieta mientras no abras la app. Cuando pases a
cuenta de pago, añadir el push son unas pocas líneas: `Activity.request` ya está
preparado para recibir un `pushType`.

## La probabilidad de ganar

Es el número que convierte un marcador en una historia: "vas ganando de 10, pero
tienes un 38 % de ganar" dice mucho más que el marcador solo.

El método, sin misterio (`Shared/WinProbability.swift`): a cada titular le queda
por anotar la diferencia entre su proyección y lo que lleva, nunca negativa.
Sumando sale el resultado final esperado de cada lado. La incertidumbre crece
con lo que queda por jugar —60 % de dispersión por punto pendiente—, así que un
partido con todos los jugadores terminados es casi determinista y uno con cuatro
por jugar puede darse la vuelta.

Es una estimación, no un oráculo: no sabe de lesiones en directo ni de reparto
de balón, y usa proyecciones PPR aunque tu liga puntúe distinto. Para lo que
sirve —saber si hay que seguir mirando— aguanta bien.

## Probar sin esperar al domingo

En compilaciones de depuración (las que hace `./ios/build.sh iphone`), el menú
de cuentas tiene una sección **Pruebas**:

| Botón | Qué hace |
| --- | --- |
| Anota tu jugador (+6) | Suma un touchdown a un titular tuyo al azar |
| Anota el rival (+6) | Lo mismo para el otro equipo |
| Field goal (+3) | Una jugada más pequeña |
| Partido simulado | Alguien anota cada 12 segundos hasta que lo pares |

Las jugadas sueltas tardan **2 segundos** a propósito: da tiempo a cerrar la app
y ver llegar la notificación y la Live Activity, que es donde se aprecian. El
trabajo pide una prórroga al sistema, así que la anotación llega aunque ya hayas
salido de la app.

No falsea la interfaz: fabrica un marcador con los puntos sumados y lo mete por
la misma puerta que los datos reales, así que lo que se prueba es el
`ScoringDetector`, la Live Activity y las notificaciones de verdad. Mientras el
partido simulado esté en marcha se pausa la descarga de puntos reales, que si no
borraría lo simulado en el siguiente refresco.

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
| `GET /stats/nfl/regular/{año}/{jornada}` | yardas, recepciones y touchdowns de la jornada |
| `GET /projections/nfl/regular/{año}/{jornada}` | lo que se espera que anote cada jugador |

Y una de ESPN para las noticias
(`site.api.espn.com/apis/site/v2/sports/football/nfl/news`), que etiqueta cada
artículo con los atletas que aparecen: cruzando ese id con el `espn_id` del
catálogo de Sleeper, el emparejamiento noticia-jugador es exacto y no hay que
buscar nombres dentro del texto.

Y dos del CDN, cacheadas en el grupo de apps: `sleepercdn.com/avatars/thumbs/…`
para los managers y `sleepercdn.com/content/nfl/players/thumb/…` para las caras
de los jugadores (las defensas usan el escudo del equipo). El widget y la Live
Activity **solo leen esos archivos**: no pueden salir a la red mientras pintan.

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
El equipo de firma que hayas puesto en Xcode **se conserva**: el generador lo lee
del proyecto anterior y lo vuelve a escribir.

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
