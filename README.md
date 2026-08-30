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

Requiere Python 3.11 o superior.

```bash
git clone https://github.com/Calvidev/fantasy-tool.git
cd fantasy-tool
./run.sh
```

> El repositorio todavía se llama `gmail-cleaner` en GitHub. El cambio de
> nombre se hace desde *Settings → Repository name*; hasta entonces, clona
> desde `https://github.com/Calvidev/gmail-cleaner.git`.

Y abre <http://127.0.0.1:8000>.

<details>
<summary>Instalación manual (sin el script)</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
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
| `GET` | `/api/trends` | Quién sube y quién baja jornada a jornada. |
| `GET` | `/api/players/{id}/trend` | Tendencia de un jugador. |
| `GET` | `/api/odds` | Spread, total y puntos implícitos por equipo. |
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
  trends.py          Tendencias por uso: quién sube y quién baja
  league_analysis.py Tu equipo vs la liga e intercambios
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
tests/               269 tests
```

La caché guarda el catálogo de jugadores en `.cache/` (pesa unos MB y cambia
poco), así que solo el primer arranque tarda. Si una fuente se cae, se sirven
los últimos datos buenos en lugar de una pantalla en blanco.

---

## Desarrollo

```bash
pip install -r requirements-dev.txt
pytest                    # los 269 tests, sin tocar la red
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
- El emparejamiento de noticias por nombre acierta casi siempre, pero con dos
  jugadores homónimos se queda con el más conocido.
- No hay datos de calendario ni de rivales, así que el ranking es de temporada
  completa, no semanal ajustado por *matchup*.

## Aviso

Proyecto personal sin relación con la NFL, Sleeper ni ESPN. El ranking es una
herramienta de apoyo, no un oráculo: contrástalo con tu propio criterio.
