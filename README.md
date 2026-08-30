# 🏈 Fantasy Tool

Herramienta para seguir la NFL en fantasy: **un ranking de jugadores del mejor
al peor** y **las noticias de cada jugador**, en una sola pantalla.

Los datos vienen de la API pública de [Sleeper](https://docs.sleeper.com) y de
las principales fuentes de noticias (ESPN, CBS, Yahoo, Fox Sports). **No hace
falta ninguna llave para empezar**: la API de lectura de Sleeper es abierta.

---

## Qué hace

**Ranking**
- Ordena a todos los jugadores relevantes para fantasy del mejor al peor, con
  una nota de 0 a 100 y agrupados en *tiers*.
- Tres formatos de puntuación: PPR, media PPR y estándar, más modo *superflex*.
- Filtros por posición, equipo, edad y estado de lesión, y buscador.
- Cada jugador explica su nota: nunca es una caja negra.

**Noticias**
- Agrega varias fuentes, quita duplicados y las ordena por fecha.
- Reconoce **qué jugador aparece en cada noticia** y las enlaza con el ranking.
- Desde la ficha de un jugador ves solo sus noticias.

**Draft en vivo**
- Se conecta al draft de tu liga en Sleeper y va **tachando solos** a los
  jugadores que van saliendo.
- Dice a quién coger, que no es el mejor disponible a secas sino **el mejor para
  ti**: pesa los huecos titulares que te faltan y los tiers que se están
  vaciando antes de tu próximo turno.
- Avisa de las rachas: cuando la sala lleva cinco corredores en diez picks, los
  que quedan se evaporan.
- Marca cuándo te toca elegir y cuántos picks faltan, y se refresca solo cada
  12 segundos mientras el draft está en marcha.

**Tendencias jornada a jornada**
- Quién sube y quién baja **antes de que se note en los puntos**.
- La señal es el volumen: objetivos, acarreos y cuota de snaps. Cuando a alguien
  empiezan a tirarle más la bola, los puntos llegan una o dos jornadas después.
- Minigráfico de la serie semanal y frases del tipo *"le tiran más la bola:
  4,8 → 6,5 objetivos por partido"* o *"cuota de snaps: 62 % → 89 %"*.
- Avisa de los dos casos que más dinero mueven: el volumen sube pero los puntos
  todavía no (comprar), y los puntos aguantan pero el volumen cae (vender).

**Mi equipo contra la liga**
- Cada posición de tu plantilla comparada con la media de los demás equipos:
  dónde estás flojo, dónde vas sobrado y en qué puesto de la liga caes.
- El valor parado en tu banquillo: suplentes tuyos que serían titulares en otro
  equipo, que es la moneda con la que se paga un intercambio.
- **Intercambios que mejoran a las dos partes**, recalculando las dos
  alineaciones con el cambio hecho. Si solo ganas tú, no aparece.

**Tendencia de las apuestas**
- Lo que el mercado espera de cada ataque esta jornada, que es información
  independiente del consenso de fantasy.
- Ordena los 32 ataques por **puntos implícitos**, el número que de verdad
  importa.
- Con una llave gratuita, añade las líneas por jugador.

**Comparar con otros rankings**
- Importa la lista de cualquier analista pegándola en un archivo de texto en
  [`data/rankings/`](data/rankings/) y aparece como una columna más.
- No sustituye al ranking propio: lo pone al lado y marca **dónde discrepáis**,
  que es lo único que hay que decidir. Si dos listas coinciden en que alguien es
  el número tres, no hay nada que pensar; si una lo pone quince puestos por
  delante, ahí hay una opinión que mirar.
- El formato es indulgente: acepta lo que copies de un vídeo o una web, con o
  sin numeración, con la posición y el equipo pegados al nombre, y reconoce a
  los jugadores aunque estén escritos sin apóstrofos ("JaMarr Chase").
- Los nombres que no reconozca los dice, en lugar de descartarlos en silencio.

**Ficha del jugador**
- Puesto general y por posición, nota, tier y desglose de los seis componentes.
- Su tendencia de las últimas jornadas y lo que dice el mercado de su partido.
- Producción de la temporada, proyección, tendencias de altas/bajas, lesión.
- Sus últimas noticias.

---

## Cómo se calcula la nota

La nota final combina seis componentes, cada uno de 0 a 100:

| Componente | Peso | Qué mide |
|---|---|---|
| **Consenso** | 34 % | Dónde coloca el mercado al jugador (`search_rank` de Sleeper). |
| **Producción** | 26 % | Puntos fantasy por partido; si aún no hay partidos, la proyección. |
| **Oportunidad** | 14 % | Puesto en el *depth chart* y si tiene equipo. |
| **Disponibilidad** | 11 % | Estado y parte de lesión. |
| **Momentum** | 8 % | Altas y bajas recientes en las ligas de Sleeper. |
| **Edad** | 7 % | Curva de rendimiento por edad, distinta en cada posición. |

Sobre esa suma se aplican dos ajustes:

- **Valor posicional**: un QB en liga de 1 QB vale menos que un RB con los
  mismos puntos; en PPR los receptores suben y en estándar bajan; en superflex
  los QB se disparan.
- **Castigo por lesión**: quien está en IR, *out* o suspendido cae de golpe,
  por bueno que sea.

Todo esto vive en [`app/ranking.py`](app/ranking.py), con las constantes
agrupadas arriba del archivo por si quieres cambiar los pesos a tu gusto.

---

## Cómo recomienda en el draft

El ranking dice quién es el mejor jugador. El draft pregunta otra cosa: **quién
te conviene a ti, ahora**. Sobre la nota del ranking se aplican tres ajustes:

| Ajuste | Efecto |
|---|---|
| Hueco titular sin cubrir | ×1,25 (urgente) · ×1,10 (medio) · ×0,88 (ya cubierto) |
| Cada hueco extra en la misma posición | +7 % más |
| El tier se vacía antes de tu turno | ×1,15 |
| Racha de esa posición en los últimos 10 picks | ×1,08 |

Por eso un corredor con nota 62 puede adelantar a un receptor con nota 78 si te
faltan dos corredores titulares y la sala lleva cinco seguidos. Cada
recomendación viene con sus motivos escritos, así que la decisión sigue siendo
tuya.

Antes de que empiece el draft la pestaña funciona igual, como chuleta: el
ranking completo con sus tiers y tu puesto en el orden de elección.

---

## Cómo se calcula la tendencia

El ranking dice quién es bueno; la tendencia dice **hacia dónde va**. Y para eso
los puntos llegan tarde: un receptor que pasa de 5 a 10 objetivos ya es otro
jugador aunque esa semana no anotara. Por eso la tendencia pesa así:

| Métrica | Peso |
|---|---|
| Oportunidades (acarreos + objetivos) | 34 % |
| Cuota de snaps | 24 % |
| Objetivos | 22 % |
| Puntos | 20 % |

Se comparan las **dos últimas jornadas contra las tres anteriores** y se mide la
pendiente de la serie completa. El resultado va de −100 a +100.

Dos detalles que evitan falsos positivos:

- Las jornadas que un jugador no juega **no cuentan como bajón**: se saltan.
- Los pateadores y las defensas no tienen métricas de volumen, así que su
  tendencia sale solo de los puntos, que rebotan mucho. Su nota se rebaja a la
  mitad y la vista los oculta por defecto.

---

## Cómo se analiza tu equipo

Todo cuelga de una sola medida: **el valor de tu alineación titular óptima**. Se
colocan tus mejores jugadores en los huecos que exige tu liga (leídos de la
propia configuración de Sleeper, incluidos FLEX y superflex) y se suman sus
notas. Con eso:

- Una posición es **débil** si tus titulares valen menos que la media de la liga
  y **fuerte** si valen más. Cada barra va a su propia escala: comparar tus dos
  receptores titulares con tu único quarterback en el mismo eje no dice nada.
- Solo se juzgan las posiciones que tu liga **alinea de verdad**. Si no hay hueco
  de pateador, tus pateadores no cuentan.
- Un intercambio se propone únicamente si, recalculando las dos alineaciones,
  **sube la de los dos**. Un cambio que solo te mejora a ti no es una propuesta.

---

## Cómo se leen las apuestas

De dos números públicos —el *spread* y el *total*— sale el que importa:

```
puntos implícitos del favorito     = (total + |spread|) / 2
puntos implícitos del no favorito  = (total - |spread|) / 2
```

Un ataque con 28 puntos implícitos reparte muchos más puntos de fantasy que uno
con 17, y eso no depende de lo bueno que sea el jugador. Por eso la vista ordena
los 32 ataques por ese número.

**Las cuotas no se mezclan con la nota del ranking a escondidas.** Van en su
propia pestaña y en la ficha del jugador, como segunda opinión, que es
exactamente lo que son.

---

## Puesta en marcha

Requiere **Python 3.10 o superior**.

> **Aviso para macOS:** el Python que trae el sistema (el de las herramientas de
> Xcode) es la versión 3.9 y **no sirve**. Si al arrancar ves un error del tipo
> `unsupported operand type(s) for |`, es exactamente eso. `run.sh` lo detecta y
> te dice cómo instalar uno nuevo; la vía más sencilla es el instalador oficial
> de <https://www.python.org/downloads/macos/>.
>
> Comprueba tu versión con `python3 --version`.

```bash
git clone https://github.com/Calvidev/fantasy-tool.git
cd fantasy-tool
./run.sh
```

> El repositorio todavía se llama `gmail-cleaner` en GitHub. El cambio de
> nombre se hace desde *Settings → Repository name*; hasta entonces, clona
> desde `https://github.com/Calvidev/gmail-cleaner.git`.

Y abre <http://127.0.0.1:8000>.

`run.sh` se encarga de todo: busca un Python válido, crea el entorno virtual,
instala las dependencias y arranca el servidor. Si ya había un entorno creado
con una versión demasiado antigua, lo rehace solo.

<details>
<summary>Instalación manual (sin el script, o en Windows)</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

En Windows, `run.sh` no funciona directamente porque es un script de bash. Usa
los comandos de arriba en PowerShell, con `python` en lugar de `python3`.
</details>

### Probarla sin conexión

Hay un modo demo con datos de ejemplo incluidos, útil para ver la interfaz sin
depender de internet:

```bash
FANTASY_DEMO=1 ./run.sh
```

> Los datos de `data/demo/` son **inventados**: nombres reales de la NFL con
> estadísticas y noticias de ejemplo. No sirven para tomar decisiones.

---

## La liga de Sleeper

La configuración vive en dos archivos que se leen en este orden:

| Archivo | Qué lleva | ¿Va a git? |
|---|---|---|
| `.env.defaults` | Valores no secretos: la liga y el usuario | Sí |
| `.env` | Tus llaves y cualquier cambio; manda sobre el anterior | No |

La liga ya viene configurada en [`.env.defaults`](.env.defaults), así que las
funciones de liga (tu roster, el filtro de agentes libres y la pestaña **Mi
equipo**) están activas desde el primer arranque.

**Sobre las llaves:** la API de lectura de Sleeper no pide autenticación, así
que para esto **no hay ninguna llave que pegar**, solo el id de la liga, que es
público: aparece en la URL `https://sleeper.com/leagues/<ID>/team`. Por eso
puede ir versionado sin problema.

### Apuntar a otra liga

Crea un `.env` (git lo ignora) con lo que quieras cambiar:

```ini
SLEEPER_LEAGUE_ID=otro_id
SLEEPER_USERNAME=otro_usuario
```

### Si no encuentra tu equipo

La herramienta te localiza dentro de la liga por tres vías, de más a menos
fiable:

1. `SLEEPER_USER_ID`, si lo pones.
2. Traduciendo tu `SLEEPER_USERNAME` a id preguntándole a Sleeper.
3. Comparando el nombre con el de los mánagers de la liga, tanto el visible
   (`display_name`) como el de la cuenta (`username`), sin distinguir mayúsculas.

Si aun así no te encuentra, la pestaña **Mi equipo** lista los mánagers que sí ve
para que puedas ver el desajuste. El arreglo definitivo es poner tu id numérico,
que sale de `https://api.sleeper.app/v1/user/TU_USUARIO`:

```ini
SLEEPER_USER_ID=987654321098765432
```

---

## API

La aplicación expone su propia API REST. Documentación interactiva en
<http://127.0.0.1:8000/docs>.

| Método | Ruta | Qué devuelve |
|---|---|---|
| `GET` | `/api/rankings` | Ranking con filtros y paginación. |
| `GET` | `/api/draft` | Tablero del draft: disponibles, huecos y recomendación. |
| `GET` | `/api/trends` | Quién sube y quién baja jornada a jornada. |
| `GET` | `/api/players/{id}/trend` | Tendencia de un jugador. |
| `GET` | `/api/odds` | Spread, total y puntos implícitos por equipo. |
| `GET` | `/api/external` | Rankings importados y nombres sin emparejar. |
| `GET` | `/api/league/analysis` | Tu equipo vs la liga + intercambios. |
| `GET` | `/api/players/{id}` | Ficha completa: ranking + noticias. |
| `GET` | `/api/players/{id}/news` | Solo las noticias de ese jugador. |
| `GET` | `/api/news` | Noticias agregadas, con jugadores identificados. |
| `GET` | `/api/compare?ids=a,b,c` | Compara varios jugadores. |
| `GET` | `/api/meta` | Temporada, semana, equipos y avisos. |
| `GET` | `/api/league` | Tu liga (necesita `SLEEPER_LEAGUE_ID`). |
| `POST` | `/api/refresh` | Vacía la caché y vuelve a descargar. |

Parámetros de `/api/rankings`: `scoring` (`ppr`, `half_ppr`, `standard`),
`superflex`, `position`, `team`, `search`, `hide_injured`, `injured_only`,
`max_age`, `free_agents_only`, `limit`, `offset`.

Parámetros de `/api/trends`: `direction` (`alza`, `baja`, `estable`), `weeks`
(3-12), `position`, `team`, `search`, `min_games`, `usage_only`,
`free_agents_only`.

```bash
# Los 10 mejores corredores en media PPR
curl "http://127.0.0.1:8000/api/rankings?position=RB&scoring=half_ppr&limit=10"

# Receptores que están subiendo en las últimas 6 jornadas
curl "http://127.0.0.1:8000/api/trends?direction=alza&position=WR&weeks=6"

# Los ataques que mejor ve el mercado esta jornada
curl "http://127.0.0.1:8000/api/odds"

# Noticias de Ja'Marr Chase
curl "http://127.0.0.1:8000/api/players/6794/news"
```

---

## Estructura del proyecto

```
app/
  main.py            Aplicación FastAPI y arranque
  config.py          Configuración por variables de entorno
  models.py          Modelos de datos (Player, NewsItem, RankedPlayer…)
  ranking.py         Motor de ranking: notas, tiers y filtros
  draft.py           Tablero de draft: disponibles, huecos y recomendación
  trends.py          Tendencias por uso: quién sube y quién baja
  league_analysis.py Tu equipo vs la liga e intercambios
  external_rankings.py Importar rankings de otros analistas
  matching.py        Reconocer nombres de jugador dentro de una noticia
  cache.py           Caché con TTL en memoria y disco
  service.py         Orquesta proveedores y ranking
  providers/
    sleeper.py       Cliente de la API de Sleeper
    news.py          Agregador de noticias (ESPN + RSS)
    odds.py          Cuotas de apuestas (ESPN + The Odds API)
    demo.py          Datos locales para el modo demo
  api/routes.py      Endpoints REST
web/                 Interfaz (HTML, CSS y JS, sin paso de compilación)
data/demo/           Datos de ejemplo del modo demo
data/rankings/       Rankings importados de otras fuentes (uno por archivo)
tests/               376 tests
```

La caché guarda el catálogo de jugadores en `.cache/` (pesa unos MB y cambia
poco), así que solo el primer arranque tarda. Si una fuente se cae, se sirven
los últimos datos buenos en lugar de una pantalla en blanco.

---

## Desarrollo

```bash
pip install -r requirements-dev.txt
pytest                    # los 376 tests, sin tocar la red
pytest --cov=app          # con cobertura (requiere pytest-cov)
```

Los tests corren contra el mismo camino de código que producción: el modo demo
solo cambia el transporte HTTP, no la lógica.

---

## Conectar las apuestas por jugador (opcional)

La pestaña de Apuestas funciona sin configurar nada: el spread y el total salen
de ESPN. Para añadir las **líneas por jugador** hace falta una llave gratuita:

1. Regístrate en [the-odds-api.com](https://the-odds-api.com) (el plan gratuito
   da 500 peticiones al mes, de sobra para consultar una vez al día).
2. Añade la llave a tu `.env`:

```ini
ODDS_API_KEY=tu_llave
```

Con eso, la ficha de cada jugador muestra sus líneas de yardas, recepciones y
touchdowns junto al resto de su información.

---

## Publicarla en internet

La herramienta va bien en local, pero también se puede dejar corriendo en un
servidor con tu propio dominio. Dos cosas cambian respecto al uso local:

| En local | Publicada |
|---|---|
| CORS abierto a cualquier origen | Solo tu dominio (`CORS_ORIGINS`) |
| Vaciar la caché está abierto | Protegido con `ADMIN_TOKEN` |

Lo segundo importa: sin protección, cualquiera podría llamar a `/api/refresh` en
bucle y forzar la descarga del catálogo entero una y otra vez, hasta que Sleeper
limitara la IP del servidor. El resto de la API es de solo lectura y puede
quedarse abierta.

### Con Fly.io (sin servidor que mantener)

Es la vía más corta si no tienes ya un servidor: despliega el `Dockerfile` de
este repositorio, da HTTPS gratis en tu dominio y la máquina se apaga sola
cuando no la usas.

```bash
# 1. Instalar la herramienta de Fly y crear la cuenta
brew install flyctl          # Linux: curl -L https://fly.io/install.sh | sh
fly auth signup              # o `fly auth login` si ya tienes cuenta

# 2. Crear la aplicación. El nombre de fly.toml tiene que ser único en todo
#    Fly; si te lo rechaza, cámbialo en el archivo y repite.
fly apps create fantasy-tool-calvi

# 3. El disco donde vive la caché del catálogo de jugadores
fly volumes create fantasy_cache --size 1 --region mad --yes

# 4. La clave para poder vaciar la caché desde fuera
fly secrets set ADMIN_TOKEN="$(openssl rand -hex 24)"

# 5. Desplegar
fly deploy

# 6. Tu dominio. Fly te dirá qué registros DNS añadir.
fly certs add fantasy.calvi.dev
```

El paso 6 te pedirá crear en tu DNS un registro **CNAME** de `fantasy` que
apunte a `fantasy-tool-calvi.fly.dev` (o un par de registros A/AAAA, según lo
que te indique). En cuanto propague, Fly emite el certificado solo.

Comprueba que va con `fly logs` y `fly status`.

> **Región:** `mad` es Madrid. Cámbiala en `fly.toml` y en el paso 3 por la más
> cercana a ti: `cdg` París, `iad` Virginia, `qro` Querétaro, `gru` São Paulo,
> `bog` Bogotá, `scl` Santiago.

### Con Docker en tu propio servidor

```bash
# 1. En el servidor, con el repositorio clonado
echo "ADMIN_TOKEN=$(openssl rand -hex 24)" > .env

# 2. Arrancar
docker compose up -d
```

Escucha en `127.0.0.1:8000`; quien da la cara a internet es un proxy. Con
[Caddy](https://caddyserver.com) el HTTPS es automático:

```caddy
fantasy.calvi.dev {
    reverse_proxy 127.0.0.1:8000
}
```

Hay un ejemplo más completo en [`deploy/Caddyfile.example`](deploy/Caddyfile.example).
Antes de nada, haz que `fantasy.calvi.dev` apunte con un registro **A** a la IP
del servidor.

El contenedor arranca como root solo el tiempo justo de ceder el disco de caché
al usuario de la aplicación, y baja de privilegios antes de ejecutar nada. Eso
lo hace [`docker-entrypoint.sh`](docker-entrypoint.sh), porque los volúmenes se
montan siempre como root y si no la caché se quedaría sin poder escribirse.

### Sin Docker

```bash
sudo git clone -b <rama> <repositorio> /opt/fantasy-tool
cd /opt/fantasy-tool
sudo python3 -m venv .venv && sudo .venv/bin/pip install -r requirements.txt
sudo useradd --system --home /opt/fantasy-tool fantasy
sudo chown -R fantasy:fantasy /opt/fantasy-tool

sudo cp deploy/fantasy-tool.service /etc/systemd/system/
sudo systemctl enable --now fantasy-tool
```

El archivo de servicio está en [`deploy/fantasy-tool.service`](deploy/fantasy-tool.service).

### Cosas a tener en cuenta

- **La caché en disco vale oro.** El catálogo de jugadores pesa unos 7 MB; si se
  pierde en cada reinicio, cada arranque vuelve a descargarlo. De eso se encargan
  el volumen `fantasy-cache` (Docker) o `fantasy_cache` (Fly). Si por lo que sea
  no se puede escribir, la aplicación sigue funcionando con la caché en memoria
  y lo avisa en los logs.
- **Memoria:** medido con el catálogo completo, el proceso llega a unos 100 MB de
  pico. Con 512 MB va sobrado y hasta 256 MB debería bastar.
- **Servidores sin disco persistente** (algunas plataformas *serverless*) pueden
  funcionar, pero cada arranque en frío tarda más porque rehacen esa descarga.
- **No hay usuarios ni contraseñas.** Todo lo que muestra es información pública
  de Sleeper; si publicas la URL, cualquiera que la conozca verá tu liga.
- **Consumo de la API de Sleeper**: con las cachés por defecto, una instalación
  normal hace unas pocas decenas de llamadas por hora, muy por debajo de lo que
  Sleeper pide (menos de 1000 por minuto).

---

## Qué sirve en cada momento de la temporada

| Momento | Lo que te sirve |
|---|---|
| Antes del draft | **Ranking** y **Draft** (como chuleta, con tiers) |
| Durante el draft | **Draft**, que se actualiza solo con cada pick |
| Semanas 1-3 | **Ranking**, **Noticias** y **Apuestas**; **Mi equipo** ya funciona |
| Semana 4 en adelante | Todo, incluidas las **Tendencias**, que ya tienen jornadas suficientes |

Las pestañas que aún no tienen datos lo dicen y te mandan a la que sí los tiene,
en vez de enseñarte una pantalla vacía.

---

## Límites conocidos

- Las estadísticas y proyecciones salen de endpoints de Sleeper que no están
  documentados oficialmente; si dejan de responder, el ranking sigue
  funcionando con el resto de componentes.
- La cuota de objetivos se calcula sumando los de cada equipo jornada a jornada.
  Si un jugador cambió de equipo a mitad de temporada, sus jornadas antiguas se
  reparten con el equipo actual: la cuota de esas semanas queda algo desviada.
- Las tendencias necesitan al menos tres jornadas jugadas; en pretemporada y en
  la primera semana la pestaña sale vacía, y lo dice.
- Los intercambios que se proponen son de uno por uno. Los paquetes de dos por
  uno todavía no se calculan.
- El tablero de draft lee los picks de Sleeper, no los envía: para elegir sigues
  usando la app de Sleeper. Esto es el copiloto, no el volante.
- Los drafts de subasta se leen, pero la recomendación no tiene en cuenta el
  presupuesto restante.
- El emparejamiento de noticias por nombre acierta casi siempre, pero con dos
  jugadores homónimos se queda con el más conocido.
- No hay datos de calendario ni de rivales, así que el ranking es de temporada
  completa, no semanal ajustado por *matchup*.

## Aviso

Proyecto personal sin relación con la NFL, Sleeper ni ESPN. El ranking es una
herramienta de apoyo, no un oráculo: contrástalo con tu propio criterio.
