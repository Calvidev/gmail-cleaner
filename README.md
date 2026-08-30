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

**Ficha del jugador**
- Puesto general y por posición, nota, tier y desglose de los seis componentes.
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

## Conectar tu liga de Sleeper

El ranking y las noticias funcionan sin configurar nada. Para las funciones de
liga —ver tu roster y filtrar **solo agentes libres**— hay que decirle cuál es
tu liga:

1. Copia el archivo de ejemplo: `cp .env.example .env`
2. Rellena estas dos líneas:

```ini
SLEEPER_USERNAME=tu_usuario
SLEEPER_LEAGUE_ID=123456789012345678
```

El **id de liga** está en la URL de la web de Sleeper cuando entras en ella:
`https://sleeper.com/leagues/`**`123456789012345678`**`/team`.

3. Reinicia el servidor.

Mientras no esté configurado, la interfaz avisa arriba y el filtro de agentes
libres aparece desactivado; nada más se resiente.

> **Sobre las llaves:** la API de lectura de Sleeper no pide autenticación, así
> que para esto **no hay ninguna llave que pegar**, solo el id de tu liga. El
> campo `SLEEPER_API_KEY` de `.env.example` está reservado por si más adelante
> se añade un proveedor de datos de pago.

---

## API

La aplicación expone su propia API REST. Documentación interactiva en
<http://127.0.0.1:8000/docs>.

| Método | Ruta | Qué devuelve |
|---|---|---|
| `GET` | `/api/rankings` | Ranking con filtros y paginación. |
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

```bash
# Los 10 mejores corredores en media PPR
curl "http://127.0.0.1:8000/api/rankings?position=RB&scoring=half_ppr&limit=10"

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
  matching.py        Reconocer nombres de jugador dentro de una noticia
  cache.py           Caché con TTL en memoria y disco
  service.py         Orquesta proveedores y ranking
  providers/
    sleeper.py       Cliente de la API de Sleeper
    news.py          Agregador de noticias (ESPN + RSS)
    demo.py          Datos locales para el modo demo
  api/routes.py      Endpoints REST
web/                 Interfaz (HTML, CSS y JS, sin paso de compilación)
data/demo/           Datos de ejemplo del modo demo
tests/               157 tests
```

La caché guarda el catálogo de jugadores en `.cache/` (pesa unos MB y cambia
poco), así que solo el primer arranque tarda. Si una fuente se cae, se sirven
los últimos datos buenos en lugar de una pantalla en blanco.

---

## Desarrollo

```bash
pip install -r requirements-dev.txt
pytest                    # los 157 tests, sin tocar la red
pytest --cov=app          # con cobertura (requiere pytest-cov)
```

Los tests corren contra el mismo camino de código que producción: el modo demo
solo cambia el transporte HTTP, no la lógica.

---

## Límites conocidos

- Las estadísticas y proyecciones salen de endpoints de Sleeper que no están
  documentados oficialmente; si dejan de responder, el ranking sigue
  funcionando con el resto de componentes.
- El emparejamiento de noticias por nombre acierta casi siempre, pero con dos
  jugadores homónimos se queda con el más conocido.
- No hay datos de calendario ni de rivales, así que el ranking es de temporada
  completa, no semanal ajustado por *matchup*.

## Aviso

Proyecto personal sin relación con la NFL, Sleeper ni ESPN. El ranking es una
herramienta de apoyo, no un oráculo: contrástalo con tu propio criterio.
