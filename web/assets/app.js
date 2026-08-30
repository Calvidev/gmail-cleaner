/* Fantasy Tool — interfaz. Sin frameworks ni paso de compilación. */

const PAGE_SIZE = 100;

const state = {
  view: "rankings",
  scoring: "ppr",
  superflex: false,
  position: "ALL",
  team: "ALL",
  search: "",
  hideInjured: false,
  freeAgents: false,
  offset: 0,
  total: 0,
  newsSearch: "",
  newsOnlyPlayers: true,
  newsCountByPlayer: {},
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

/* ----------------------------- utilidades ------------------------------- */

async function api(path, params) {
  const url = new URL(path, window.location.origin);
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "" && value !== false) {
      url.searchParams.set(key, value);
    }
  });
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch (_) { /* respuesta sin JSON */ }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function formatNumber(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("es-ES").format(value);
}

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (Number.isNaN(diff)) return "";
  if (diff < 60) return "ahora";
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`;
  const days = Math.floor(diff / 86400);
  return days === 1 ? "ayer" : `hace ${days} días`;
}

function showWarnings(messages, isError = false) {
  const box = $("#warnings");
  if (!messages || !messages.length) {
    box.hidden = true;
    box.innerHTML = "";
    return;
  }
  box.hidden = false;
  box.innerHTML = messages
    .map((m) => `<div class="warning${isError ? " is-error" : ""}">${esc(m)}</div>`)
    .join("");
}

/* -------------------------------- ranking -------------------------------- */

function positionOf(player) {
  return player.position || (player.fantasy_positions || [])[0] || "UNK";
}

function statusCell(player) {
  if (player.injury_status) {
    const severe = ["IR", "Out", "PUP", "NFI", "Sus"].includes(player.injury_status);
    const label = player.injury_body_part
      ? `${player.injury_status} · ${player.injury_body_part}`
      : player.injury_status;
    return `<span class="badge ${severe ? "badge-danger" : "badge-warn"}">${esc(label)}</span>`;
  }
  if (player.status && player.status !== "Active") {
    return `<span class="badge badge-warn">${esc(player.status)}</span>`;
  }
  return '<span class="badge badge-ok">Sano</span>';
}

function rowHtml(entry) {
  const p = entry.player;
  const pos = positionOf(p);
  const avatar = p.headshot_url
    ? `background-image:url('${esc(p.headshot_url)}')`
    : "";
  const trend = entry.trend_adds
    ? `<span class="trend-up">▲ ${formatNumber(entry.trend_adds)}</span>`
    : entry.trend_drops
      ? `<span class="trend-down">▼ ${formatNumber(entry.trend_drops)}</span>`
      : '<span class="num">—</span>';
  const newsCount = state.newsCountByPlayer[p.player_id];

  return `
    <tr data-player-id="${esc(p.player_id)}">
      <td class="col-rank">
        <div class="rank-cell">
          <span class="rank-num">${entry.rank}</span>
          <span class="tier-badge" title="Tier ${entry.tier}">T${entry.tier}</span>
        </div>
      </td>
      <td>
        <div class="player-cell">
          <div class="avatar" style="${avatar}"></div>
          <div>
            <div class="player-name">${esc(p.name)}${
              newsCount ? `<span class="badge badge-news" title="${newsCount} noticia(s)">${newsCount} 📰</span>` : ""
            }</div>
            <div class="player-meta">${esc(p.team || "Agente libre")}${
              p.age ? ` · ${p.age} años` : ""
            }${p.years_exp === 0 ? " · rookie" : ""}</div>
          </div>
        </div>
      </td>
      <td><span class="pos-tag pos-${esc(pos)}">${esc(pos)}${
        entry.position_rank ? entry.position_rank : ""
      }</span></td>
      <td>
        <div class="score-cell">
          <span class="score-num">${entry.score.toFixed(1)}</span>
          <span class="score-bar"><i style="width:${Math.min(100, entry.score)}%"></i></span>
        </div>
      </td>
      <td class="num">${entry.points_per_game ? entry.points_per_game.toFixed(1) : "—"}</td>
      <td class="num">${entry.points ? entry.points.toFixed(1) : "—"}</td>
      <td>${trend}</td>
      <td>${statusCell(p)}</td>
    </tr>`;
}

function skeletonRows(count = 10) {
  return Array.from({ length: count })
    .map(() => `<tr class="skeleton-row"><td colspan="8"><div class="skeleton"></div></td></tr>`)
    .join("");
}

async function loadRankings({ append = false } = {}) {
  const body = $("#ranking-body");
  if (!append) {
    state.offset = 0;
    body.innerHTML = skeletonRows();
  }

  try {
    const data = await api("/api/rankings", {
      scoring: state.scoring,
      superflex: state.superflex,
      position: state.position,
      team: state.team,
      search: state.search,
      hide_injured: state.hideInjured,
      free_agents_only: state.freeAgents,
      limit: PAGE_SIZE,
      offset: state.offset,
    });

    state.total = data.total;
    const rows = data.players.map(rowHtml).join("");
    if (append) {
      body.insertAdjacentHTML("beforeend", rows);
    } else {
      body.innerHTML = rows;
    }

    $("#ranking-empty").hidden = data.total > 0;
    const shown = state.offset + data.count;
    $("#result-line").textContent = data.total
      ? `${formatNumber(shown)} de ${formatNumber(data.total)} jugadores · formato ${
          { ppr: "PPR", half_ppr: "media PPR", standard: "estándar" }[data.scoring]
        }${state.superflex ? " · superflex" : ""}`
      : "";
    $("#load-more").hidden = shown >= data.total;
    state.offset = shown;
  } catch (error) {
    body.innerHTML = "";
    $("#ranking-empty").hidden = false;
    $("#ranking-empty").textContent = error.message;
    if (error.status === 409) {
      $("#free-agents").checked = false;
      state.freeAgents = false;
    }
    showWarnings([error.message], true);
  }
}

/* -------------------------------- noticias ------------------------------- */

function newsCardHtml(item) {
  const chips = (item.player_ids || [])
    .map((pid, i) => `<button class="player-chip" data-player-id="${esc(pid)}">${esc(
      item.player_names[i] || pid
    )}</button>`)
    .join("");

  return `
    <article class="news-card">
      ${item.image_url ? `<img class="news-thumb" src="${esc(item.image_url)}" alt="" loading="lazy" onerror="this.remove()">` : ""}
      <div class="news-body">
        <div class="news-source">
          <span>${esc(item.source)}</span>
          <span>${esc(timeAgo(item.published))}</span>
        </div>
        <h3 class="news-title">${
          item.url
            ? `<a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a>`
            : esc(item.title)
        }</h3>
        ${item.summary ? `<p class="news-summary">${esc(item.summary)}</p>` : ""}
        ${chips ? `<div class="news-players">${chips}</div>` : ""}
      </div>
    </article>`;
}

async function loadNews() {
  const grid = $("#news-grid");
  grid.innerHTML = `<p class="empty">Cargando noticias…</p>`;
  try {
    const items = await api("/api/news", {
      limit: 120,
      q: state.newsSearch,
      only_players: state.newsOnlyPlayers,
    });
    grid.innerHTML = items.map(newsCardHtml).join("");
    $("#news-empty").hidden = items.length > 0;
    if (!items.length) grid.innerHTML = "";
  } catch (error) {
    grid.innerHTML = "";
    $("#news-empty").hidden = false;
    $("#news-empty").textContent = error.message;
  }
}

/** Cuenta cuántas noticias tiene cada jugador, para el distintivo de la tabla. */
async function loadNewsCounts() {
  try {
    const items = await api("/api/news", { limit: 200, only_players: true });
    const counts = {};
    items.forEach((item) => {
      (item.player_ids || []).forEach((pid) => {
        counts[pid] = (counts[pid] || 0) + 1;
      });
    });
    state.newsCountByPlayer = counts;
  } catch (_) {
    state.newsCountByPlayer = {};
  }
}

/* --------------------------------- ficha --------------------------------- */

const BREAKDOWN_LABELS = {
  consensus: "Consenso",
  production: "Producción",
  opportunity: "Oportunidad",
  momentum: "Momentum",
  availability: "Disponibilidad",
  age_curve: "Edad",
};

function drawerTrendHtml(trend) {
  if (!trend) return "";
  const color = trend.direction === "alza" ? "#35d07f" : trend.direction === "baja" ? "#ff6b6b" : "#8d99ae";
  const clase = trend.direction === "alza" ? "up" : trend.direction === "baja" ? "down" : "flat";
  const serie = trend.weeks.map((w) => w.opportunities ?? w.targets ?? w.points);

  return `
    <h3>Tendencia · últimas ${trend.games_tracked} jornadas</h3>
    <div class="drawer-rank" style="align-items:center">
      <div class="trend-score ${clase}" style="min-width:64px">${
        trend.trend_score > 0 ? "+" : ""
      }${trend.trend_score.toFixed(0)}</div>
      <div>
        ${sparkline(serie, color)}
        <span class="spark-label">Oportunidades por jornada</span>
      </div>
    </div>
    <ul class="reason-list">${trend.signals.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>`;
}

function drawerVegasHtml(vegas, props) {
  if (!vegas && (!props || !props.length)) return "";
  const bloque = vegas
    ? `<div class="drawer-rank">
        <div class="stat-block"><span class="stat-value">${
          vegas.implied_total?.toFixed(1) ?? "—"
        }</span><span class="stat-label">Pts implícitos</span></div>
        <div class="stat-block"><span class="stat-value">${
          vegas.spread > 0 ? "+" : ""
        }${vegas.spread?.toFixed(1) ?? "—"}</span><span class="stat-label">Spread</span></div>
        <div class="stat-block"><span class="stat-value">${
          vegas.total?.toFixed(1) ?? "—"
        }</span><span class="stat-label">Total</span></div>
        <div class="stat-block"><span class="stat-value">${
          vegas.implied_rank ?? "—"
        }</span><span class="stat-label">Ataque nº</span></div>
      </div>
      <p class="panel-sub" style="font-size:12.5px">${esc(vegas.verdict || "")}${
        vegas.opponent ? ` · ${vegas.is_home ? "recibe a" : "visita a"} ${esc(vegas.opponent)}` : ""
      }</p>`
    : "";

  const lineas = (props || []).length
    ? `<div class="trend-metrics" style="margin-top:8px">${props
        .map(
          (pr) =>
            `<span class="trend-metric">${esc(pr.label)}: <b>${
              pr.line ?? "—"
            }</b>${pr.bookmaker ? ` · ${esc(pr.bookmaker)}` : ""}</span>`
        )
        .join("")}</div>`
    : "";

  return `<h3>Lo que dice el mercado</h3>${bloque}${lineas}`;
}

function drawerHtml(detail) {
  const { ranked, news, trend, vegas, props } = detail;
  const p = ranked.player;
  const pos = positionOf(p);

  const breakdown = Object.entries(BREAKDOWN_LABELS)
    .map(([key, label]) => {
      const value = ranked.breakdown[key] ?? 0;
      return `
        <div class="bd-row">
          <span class="bd-label">${label}</span>
          <span class="bd-bar"><i style="width:${Math.min(100, value)}%"></i></span>
          <span class="bd-value">${value.toFixed(0)}</span>
        </div>`;
    })
    .join("");

  const newsHtml = news.length
    ? news
        .map(
          (item) => `
        <article>
          <div class="news-source"><span>${esc(item.source)}</span><span>${esc(timeAgo(item.published))}</span></div>
          <h4>${
            item.url
              ? `<a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a>`
              : esc(item.title)
          }</h4>
          ${item.summary ? `<p>${esc(item.summary)}</p>` : ""}
        </article>`
        )
        .join("")
    : `<p class="empty" style="padding:16px 0">Sin noticias recientes de este jugador.</p>`;

  return `
    <div class="drawer-head">
      <div class="avatar" style="${p.headshot_url ? `background-image:url('${esc(p.headshot_url)}')` : ""}"></div>
      <div>
        <h2>${esc(p.name)}</h2>
        <p class="drawer-sub">
          <span class="pos-tag pos-${esc(pos)}">${esc(pos)}</span>
          ${esc(p.team || "Agente libre")}${p.number ? ` · #${p.number}` : ""}
          ${p.age ? ` · ${p.age} años` : ""}${p.college ? ` · ${esc(p.college)}` : ""}
        </p>
      </div>
    </div>

    <div class="drawer-rank">
      <div class="stat-block"><span class="stat-value">#${ranked.rank}</span><span class="stat-label">General</span></div>
      <div class="stat-block"><span class="stat-value">${esc(pos)}${ranked.position_rank}</span><span class="stat-label">Posición</span></div>
      <div class="stat-block"><span class="stat-value">${ranked.score.toFixed(1)}</span><span class="stat-label">Nota</span></div>
      <div class="stat-block"><span class="stat-value">T${ranked.tier}</span><span class="stat-label">Tier</span></div>
    </div>

    ${statusCell(p)}

    <h3>Por qué está aquí</h3>
    <ul class="reason-list">${ranked.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>

    ${drawerTrendHtml(trend)}
    ${drawerVegasHtml(vegas, props)}

    <h3>Desglose de la nota</h3>
    <div class="breakdown">${breakdown}</div>

    <h3>Temporada</h3>
    <div class="drawer-rank">
      <div class="stat-block"><span class="stat-value">${ranked.points ? ranked.points.toFixed(1) : "—"}</span><span class="stat-label">Puntos</span></div>
      <div class="stat-block"><span class="stat-value">${ranked.points_per_game ? ranked.points_per_game.toFixed(1) : "—"}</span><span class="stat-label">Por partido</span></div>
      <div class="stat-block"><span class="stat-value">${ranked.games ?? "—"}</span><span class="stat-label">Partidos</span></div>
      <div class="stat-block"><span class="stat-value">${ranked.projected_points ? ranked.projected_points.toFixed(0) : "—"}</span><span class="stat-label">Proyección</span></div>
    </div>

    <h3>Noticias</h3>
    <div class="drawer-news">${newsHtml}</div>`;
}

async function openDrawer(playerId) {
  const drawer = $("#drawer");
  const content = $("#drawer-content");
  drawer.hidden = false;
  $("#scrim").hidden = false;
  content.innerHTML = `<div class="skeleton" style="height:120px;margin-top:30px"></div>`;
  document.body.style.overflow = "hidden";

  try {
    const detail = await api(`/api/players/${encodeURIComponent(playerId)}`, {
      scoring: state.scoring,
      superflex: state.superflex,
      news_limit: 15,
    });
    content.innerHTML = drawerHtml(detail);
  } catch (error) {
    content.innerHTML = `<p class="empty">${esc(error.message)}</p>`;
  }
}

function closeDrawer() {
  $("#drawer").hidden = true;
  $("#scrim").hidden = true;
  document.body.style.overflow = "";
}

/* ------------------------------- metadatos ------------------------------- */

async function loadMeta() {
  try {
    const meta = await api("/api/meta");
    const parts = [];
    if (meta.season) parts.push(`Temporada ${meta.season}`);
    if (meta.week) parts.push(`Semana ${meta.week}`);
    if (meta.player_count) parts.push(`${formatNumber(meta.player_count)} jugadores`);
    $("#season-line").textContent = parts.join(" · ") || "NFL";

    const teamSelect = $("#team");
    teamSelect.innerHTML =
      '<option value="ALL">Todos los equipos</option>' +
      meta.teams.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");

    if (meta.league_configured) {
      $("#free-agents").disabled = false;
      $("#trend-free-agents").disabled = false;
      $("#fa-toggle-wrap").title = `Liga ${meta.league_id || ""}`;
      $("#trend-fa-wrap").title = `Liga ${meta.league_id || ""}`;
    }
    $("#footer-meta").textContent = meta.league_configured
      ? `Liga conectada: ${meta.league_id}`
      : "Liga de Sleeper sin conectar";

    showWarnings(meta.warnings);
  } catch (error) {
    $("#season-line").textContent = "Sin conexión con Sleeper";
    showWarnings([error.message], true);
  }
}

/* -------------------------------- eventos -------------------------------- */

const VIEWS = ["rankings", "draft", "trends", "team", "odds", "news"];

function switchView(view) {
  state.view = view;
  $$(".tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.view === view));
  VIEWS.forEach((name) => {
    const el = $(`#view-${name}`);
    if (el) el.hidden = name !== view;
  });

  // Cada vista se carga la primera vez que se abre, no antes.
  if (view === "news" && !$("#news-grid").children.length) loadNews();
  if (view === "draft" && !$("#draft-content").children.length) loadDraft();
  if (view === "trends" && !$("#trend-list").children.length) loadTrends();

  // El refresco automático solo tiene sentido mirando el draft.
  if (view !== "draft") stopDraftRefresh();
  if (view === "team" && !$("#team-content").children.length) loadTeam();
  if (view === "odds" && !$("#odds-content").children.length) loadOdds();
}

function bindEvents() {
  $$(".tab").forEach((tab) =>
    tab.addEventListener("click", () => switchView(tab.dataset.view))
  );

  $("#scoring").addEventListener("change", (e) => {
    state.scoring = e.target.value;
    loadRankings();
    invalidateDerivedViews();
  });
  $("#superflex").addEventListener("change", (e) => {
    state.superflex = e.target.checked;
    loadRankings();
    invalidateDerivedViews();
  });
  $("#hide-injured").addEventListener("change", (e) => {
    state.hideInjured = e.target.checked;
    loadRankings();
  });
  $("#free-agents").addEventListener("change", (e) => {
    state.freeAgents = e.target.checked;
    loadRankings();
  });
  $("#team").addEventListener("change", (e) => {
    state.team = e.target.value;
    loadRankings();
  });

  $("#position-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    $$("#position-chips .chip").forEach((c) => c.classList.toggle("is-active", c === chip));
    state.position = chip.dataset.position;
    loadRankings();
  });

  $("#search").addEventListener(
    "input",
    debounce((e) => {
      state.search = e.target.value.trim();
      loadRankings();
    }, 260)
  );

  $("#load-more").addEventListener("click", () => loadRankings({ append: true }));

  $("#refresh").addEventListener("click", async () => {
    const button = $("#refresh");
    button.disabled = true;
    button.textContent = "…";
    try {
      const respuesta = await fetch("/api/refresh", { method: "POST" });
      if (respuesta.status === 401) {
        // Instalación publicada con ADMIN_TOKEN: el botón no puede vaciar la
        // caché desde el navegador, pero los datos se refrescan solos por TTL.
        showWarnings([
          "Vaciar la caché está protegido en esta instalación. Los datos se " +
            "actualizan solos igualmente: el catálogo cada 12 h, las noticias cada " +
            "10 min y los picks del draft cada 10 s.",
        ]);
        return;
      }
      await loadMeta();
      await loadNewsCounts();
      await loadRankings();
      invalidateDerivedViews();
      if (state.view === "news") await loadNews();
      if (state.view === "trends") await loadTrends();
      if (state.view === "team") await loadTeam();
      if (state.view === "odds") await loadOdds();
    } finally {
      button.disabled = false;
      button.textContent = "↻";
    }
  });

  $("#ranking-body").addEventListener("click", (e) => {
    const row = e.target.closest("tr[data-player-id]");
    if (row) openDrawer(row.dataset.playerId);
  });

  $("#news-grid").addEventListener("click", (e) => {
    const chip = e.target.closest(".player-chip");
    if (chip) openDrawer(chip.dataset.playerId);
  });

  $("#news-search").addEventListener(
    "input",
    debounce((e) => {
      state.newsSearch = e.target.value.trim();
      loadNews();
    }, 300)
  );
  $("#news-only-players").addEventListener("change", (e) => {
    state.newsOnlyPlayers = e.target.checked;
    loadNews();
  });

  // --- Tendencias ---
  $("#direction-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    $$("#direction-chips .chip").forEach((c) => c.classList.toggle("is-active", c === chip));
    state.trendDirection = chip.dataset.direction;
    loadTrends();
  });
  $("#trend-position-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    $$("#trend-position-chips .chip").forEach((c) => c.classList.toggle("is-active", c === chip));
    state.trendPosition = chip.dataset.position;
    loadTrends();
  });
  $("#trend-weeks").addEventListener("change", (e) => {
    state.trendWeeks = Number(e.target.value);
    loadTrends();
  });
  $("#trend-free-agents").addEventListener("change", (e) => {
    state.trendFreeAgents = e.target.checked;
    loadTrends();
  });
  $("#trend-list").addEventListener("click", (e) => {
    const card = e.target.closest(".trend-card[data-player-id]");
    if (card) openDrawer(card.dataset.playerId);
  });

  // --- Draft ---
  $("#draft-content").addEventListener("click", (e) => {
    const fila = e.target.closest("[data-player-id]");
    if (fila) openDrawer(fila.dataset.playerId);
  });

  // Botones que saltan a otra pestaña (por ejemplo, "ir al draft").
  document.addEventListener("click", (e) => {
    const salto = e.target.closest("[data-goto]");
    if (salto) switchView(salto.dataset.goto);
  });

  $("#drawer-close").addEventListener("click", closeDrawer);
  $("#scrim").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });
}

/* --------------------------------- inicio -------------------------------- */

async function init() {
  bindEvents();
  await loadMeta();
  await loadRankings();
  // Los distintivos de noticias llegan después: no bloquean la tabla.
  await loadNewsCounts();
  if (Object.keys(state.newsCountByPlayer).length) loadRankings();
}

/* ============================== Tendencias =============================== */

Object.assign(state, {
  trendDirection: "alza",
  trendPosition: "ALL",
  trendWeeks: 6,
  trendFreeAgents: false,
});

/** Minigráfico de una serie de números, en SVG puro. */
function sparkline(values, color) {
  const clean = values.filter((v) => v !== null && v !== undefined);
  if (clean.length < 2) return "";
  const width = 120;
  const height = 34;
  const pad = 3;
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min || 1;
  const step = (width - pad * 2) / (clean.length - 1);

  const points = clean.map((v, i) => {
    const x = pad + i * step;
    const y = height - pad - ((v - min) / span) * (height - pad * 2);
    return [x, y];
  });
  const line = points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${points[points.length - 1][0].toFixed(1)},${height - pad} L${pad},${height - pad} Z`;
  const [lastX, lastY] = points[points.length - 1];

  return `<svg class="spark" viewBox="0 0 ${width} ${height}" aria-hidden="true">
    <path d="${area}" fill="${color}" opacity="0.13"></path>
    <path d="${line}" fill="none" stroke="${color}" stroke-width="1.8"
          stroke-linecap="round" stroke-linejoin="round"></path>
    <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="2.6" fill="${color}"></circle>
  </svg>`;
}

function trendCardHtml(trend) {
  const p = trend.player;
  const pos = positionOf(p);
  const clase = trend.direction === "alza" ? "up" : trend.direction === "baja" ? "down" : "flat";
  const color = trend.direction === "alza" ? "#35d07f" : trend.direction === "baja" ? "#ff6b6b" : "#8d99ae";

  // Se dibuja el volumen, no los puntos: es la señal que se adelanta.
  const serie = trend.weeks.map((w) => w.opportunities ?? w.targets ?? w.points);
  const etiqueta = trend.weeks.some((w) => w.opportunities !== null && w.opportunities !== undefined)
    ? "Oportunidades por jornada"
    : "Puntos por jornada";

  const metricas = ["targets", "snap_share", "opportunities"]
    .map((clave) => trend.metrics[clave])
    .filter(Boolean)
    .map((m) => {
      const esCuota = m.metric === "snap_share";
      const fmt = (v) => (v === null || v === undefined ? "—" : esCuota ? `${(v * 100).toFixed(0)} %` : v.toFixed(1));
      const signo = (m.delta ?? 0) > 0 ? "+" : "";
      const deltaTxt = esCuota
        ? `${signo}${((m.delta ?? 0) * 100).toFixed(0)} pp`
        : `${signo}${(m.delta ?? 0).toFixed(1)}`;
      return `<span class="trend-metric">${esc(m.label)}: <b>${fmt(m.previous)} → ${fmt(m.recent)}</b> (${deltaTxt})</span>`;
    })
    .join("");

  return `
    <article class="trend-card" data-player-id="${esc(p.player_id)}">
      <div class="trend-score ${clase}">${trend.trend_score > 0 ? "+" : ""}${trend.trend_score.toFixed(0)}</div>

      <div class="trend-player">
        <div class="avatar" style="${p.headshot_url ? `background-image:url('${esc(p.headshot_url)}')` : ""}"></div>
        <div style="min-width:0">
          <div class="player-name">${esc(p.name)}</div>
          <div class="player-meta">
            <span class="pos-tag pos-${esc(pos)}">${esc(pos)}</span>
            ${esc(p.team || "Libre")}${trend.rank ? ` · #${trend.rank} del ranking` : ""}
          </div>
        </div>
      </div>

      <div class="spark-wrap">
        ${sparkline(serie, color)}
        <span class="spark-label">${etiqueta}</span>
      </div>

      <div>
        <ul class="trend-signals">
          ${trend.signals.map((s) => `<li>${esc(s)}</li>`).join("")}
        </ul>
        ${metricas ? `<div class="trend-metrics" style="margin-top:6px">${metricas}</div>` : ""}
      </div>
    </article>`;
}

async function loadTrends() {
  const list = $("#trend-list");
  list.innerHTML = `<p class="empty">Calculando tendencias…</p>`;
  try {
    const data = await api("/api/trends", {
      scoring: state.scoring,
      superflex: state.superflex,
      weeks: state.trendWeeks,
      direction: state.trendDirection,
      position: state.trendPosition,
      free_agents_only: state.trendFreeAgents,
      limit: 60,
    });

    list.innerHTML = data.players.map(trendCardHtml).join("");
    $("#trend-empty").hidden = data.players.length > 0;
    if (!data.players.length) {
      list.innerHTML = "";
      $("#trend-empty").textContent =
        data.warnings[0] || "Ningún jugador encaja con estos filtros.";
    }
    $("#trend-result-line").textContent = data.weeks_analyzed.length
      ? `${data.total} jugadores · jornadas ${data.weeks_analyzed[0]}–${
          data.weeks_analyzed[data.weeks_analyzed.length - 1]
        }`
      : "";
  } catch (error) {
    list.innerHTML = "";
    $("#trend-empty").hidden = false;
    $("#trend-empty").textContent = error.message;
    if (error.status === 409) {
      $("#trend-free-agents").checked = false;
      state.trendFreeAgents = false;
    }
  }
}

/* ============================== Mi equipo =============================== */

function setupTeamHtml(mensaje) {
  return `
    <div class="panel">
      <h2>Conecta tu liga de Sleeper</h2>
      <p class="panel-sub">${esc(mensaje)}</p>
      <ol class="setup-steps">
        <li>Copia el archivo de ejemplo: <code>cp .env.example .env</code></li>
        <li>Abre tu liga en la web de Sleeper y copia el número de la URL:
            <code>sleeper.com/leagues/<b>123456789012345678</b>/team</code></li>
        <li>Pega ese número y tu usuario en <code>.env</code>:
          <span class="code-block">SLEEPER_LEAGUE_ID=123456789012345678
SLEEPER_USERNAME=tu_usuario</span>
        </li>
        <li>Reinicia el servidor y vuelve aquí.</li>
      </ol>
      <p class="panel-sub" style="margin-top:14px">
        No hace falta ninguna contraseña ni llave: la API de lectura de Sleeper es pública.
      </p>
    </div>`;
}

function positionBarsHtml(team) {
  const posiciones = Object.entries(team.positions).sort(
    (a, b) => a[1].percentile - b[1].percentile
  );

  return posiciones
    .map(([pos, b]) => {
      const clase = b.verdict === "débil" ? "weak" : b.verdict === "fuerte" ? "strong" : "mid";
      // Cada posición va a su propia escala: comparar tus 2 receptores titulares
      // con tu único quarterback en el mismo eje no dice nada. Lo que importa
      // en cada fila es dónde caes tú frente a la liga en ESA posición.
      const tope = Math.max(b.starter_score, b.league_best, 1) * 1.08;
      return `
        <div class="pos-bar-row">
          <span class="pos-tag pos-${esc(pos)}">${esc(pos)}</span>
          <div class="pos-bar-track" title="Media de la liga: ${b.league_avg.toFixed(1)}">
            <div class="pos-bar-fill ${clase}" style="width:${(b.starter_score / tope) * 100}%"></div>
            <div class="pos-bar-avg" style="left:${(b.league_avg / tope) * 100}%"></div>
          </div>
          <div class="pos-bar-meta">
            <b>${b.starter_score.toFixed(1)}</b> vs ${b.league_avg.toFixed(1)} de media
            · ${b.rank_in_league}º de la liga
            <span class="verdict ${esc(b.verdict)}">${esc(b.verdict)}</span>
          </div>
        </div>`;
    })
    .join("");
}

function tradeCardHtml(idea) {
  return `
    <div class="trade-card">
      <div class="trade-partner">Con ${esc(idea.partner_team_name || idea.partner_owner || "otro equipo")}</div>
      <div class="trade-swap">
        <div class="trade-side">
          <div class="label">Das</div>
          <div class="who">${idea.give.map((g) => esc(g.player.name)).join(", ")}</div>
        </div>
        <div class="trade-arrow">⇄</div>
        <div class="trade-side">
          <div class="label">Recibes</div>
          <div class="who">${idea.get.map((g) => esc(g.player.name)).join(", ")}</div>
        </div>
      </div>
      <div class="trade-gains">
        <span class="gain-me">Tú +${idea.my_gain.toFixed(1)}</span>
        <span class="gain-them">Él +${idea.their_gain.toFixed(1)}</span>
        <span style="color:var(--text-faint)">Equilibrio ${idea.fairness.toFixed(0)}/100</span>
      </div>
      <ul class="trade-why">${idea.rationale.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
    </div>`;
}

function teamAnalysisHtml(data) {
  const me = data.me;

  // Antes del draft no hay plantillas que comparar: pintar una clasificación
  // vacía sería ruido. Se manda al usuario a lo que sí le sirve hoy.
  if (data.pre_draft) {
    return `
      <div class="panel">
        <h2>${esc(data.league_name || "Tu liga")}</h2>
        <p class="panel-sub">${data.warnings.map(esc).join(" ")}</p>
        <p style="margin:18px 0 0">
          <button class="btn" data-goto="draft">Ir al tablero de draft →</button>
        </p>
        <p class="panel-sub" style="margin-top:16px; font-size:12.5px; color:var(--text-faint)">
          En cuanto termine el draft, esta pestaña te dirá en qué posiciones estás
          flojo comparado con el resto de la liga y qué intercambios te convienen.
        </p>
      </div>`;
  }
  const standings = `
    <div class="panel">
      <h3>Clasificación por valor de plantilla</h3>
      <table class="standings">
        <thead><tr><th>#</th><th>Equipo</th><th>Mánager</th><th>Alineación titular</th><th>Fuertes</th><th>Débiles</th></tr></thead>
        <tbody>
          ${data.teams
            .map(
              (t) => `
            <tr class="${t.is_me ? "is-me" : ""}">
              <td>${t.rank_in_league}</td>
              <td>${esc(t.team_name || "—")}${t.is_me ? " ← tú" : ""}</td>
              <td>${esc(t.owner || "—")}</td>
              <td class="num">${t.total_score.toFixed(1)}</td>
              <td>${t.strengths.map((p) => `<span class="pos-tag pos-${esc(p)}">${esc(p)}</span>`).join(" ")}</td>
              <td>${t.weaknesses.map((p) => `<span class="pos-tag pos-${esc(p)}">${esc(p)}</span>`).join(" ")}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>`;

  if (!me) {
    return `
      <div class="panel">
        <h2>${esc(data.league_name || "Tu liga")}</h2>
        <p class="panel-sub">${data.warnings.map(esc).join(" ")}</p>
      </div>
      ${standings}`;
  }

  const avisos = data.warnings.length
    ? `<div class="warnings" style="margin:0 0 16px">${data.warnings
        .map((w) => `<div class="warning">${esc(w)}</div>`)
        .join("")}</div>`
    : "";

  return `
    ${avisos}
    <div class="panel">
      <h2>${esc(me.team_name || me.owner || "Mi equipo")}</h2>
      <p class="panel-sub">
        ${me.rank_in_league}º de ${data.teams.length} equipos en ${esc(data.league_name || "la liga")}
        · alineación titular valorada en ${me.total_score.toFixed(1)}
        · ${me.player_count} jugadores en plantilla
      </p>

      <h3>Dónde estás flojo y dónde vas sobrado</h3>
      <div class="pos-bars">${positionBarsHtml(me)}</div>
      <p class="panel-sub" style="margin-top:12px; font-size:12px; color:var(--text-faint)">
        La barra es la suma de tus titulares en esa posición; la línea vertical, la media de la liga.
      </p>

      ${
        me.surplus.length
          ? `<h3>Valor parado en tu banquillo</h3>
             <p class="panel-sub">Suplentes tuyos que serían titulares en otros equipos: la moneda con la que pagar un intercambio.</p>
             <div class="trend-metrics">${me.surplus
               .slice(0, 8)
               .map(
                 (s) =>
                   `<span class="trend-metric"><b>${esc(s.player.name)}</b> ${esc(
                     positionOf(s.player)
                   )} · nota ${s.score.toFixed(0)}</span>`
               )
               .join("")}</div>`
          : ""
      }
    </div>

    <div class="panel">
      <h3>Intercambios que mejoran a las dos partes (${data.trade_ideas.length})</h3>
      <p class="panel-sub">
        Se recalculan las dos alineaciones con el cambio hecho. Si solo ganas tú, no aparece:
        eso no es una propuesta, es un favor que nadie acepta.
      </p>
      ${
        data.trade_ideas.length
          ? `<div class="trade-grid">${data.trade_ideas.map(tradeCardHtml).join("")}</div>`
          : `<p class="empty">Ahora mismo no hay ningún intercambio uno por uno que os venga bien a los dos.</p>`
      }
    </div>

    ${standings}`;
}

async function loadTeam() {
  const box = $("#team-content");
  box.innerHTML = `<div class="panel"><div class="skeleton" style="height:90px"></div></div>`;
  try {
    const data = await api("/api/league/analysis", {
      scoring: state.scoring,
      superflex: state.superflex,
    });
    box.innerHTML = teamAnalysisHtml(data);
  } catch (error) {
    box.innerHTML =
      error.status === 409 ? setupTeamHtml(error.message) : `<p class="empty">${esc(error.message)}</p>`;
  }
}

/* =============================== Apuestas =============================== */

function oddsHtml(data) {
  const equipos = data.teams.filter((t) => t.implied_total !== null && t.implied_total !== undefined);
  const tope = Math.max(...equipos.map((t) => t.implied_total), 1);

  const avisos = data.warnings.length
    ? `<div class="warnings" style="margin:0 0 16px">${data.warnings
        .map((w) => `<div class="warning">${esc(w)}</div>`)
        .join("")}</div>`
    : "";

  if (!equipos.length) return `${avisos}<p class="empty">No hay cuotas publicadas ahora mismo.</p>`;

  return `
    ${avisos}
    <div class="panel">
      <h3>Ataques mejor y peor vistos por el mercado${data.week ? ` · jornada ${data.week}` : ""}</h3>
      <table class="odds-table">
        <thead><tr><th>#</th><th>Equipo</th><th>Rival</th><th>Puntos implícitos</th><th></th><th>Spread</th><th>Total</th><th>Lectura</th></tr></thead>
        <tbody>
          ${equipos
            .map(
              (t) => `
            <tr>
              <td class="num">${t.implied_rank ?? "—"}</td>
              <td><b>${esc(t.team)}</b></td>
              <td>${t.is_home ? "vs" : "en"} ${esc(t.opponent || "—")}</td>
              <td class="num">${t.implied_total.toFixed(1)}</td>
              <td style="width:110px"><span class="implied-bar"><i style="width:${
                (t.implied_total / tope) * 100
              }%"></i></span></td>
              <td class="num">${t.spread > 0 ? "+" : ""}${t.spread?.toFixed(1) ?? "—"}</td>
              <td class="num">${t.total?.toFixed(1) ?? "—"}</td>
              <td style="color:var(--text-dim);font-size:12.5px">${esc(t.verdict || "")}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h3>Partidos de la jornada</h3>
      <div class="games-grid">
        ${data.games
          .map(
            (g) => `
          <div class="game-card">
            <div class="game-teams">
              <span class="abbr">${esc(g.away)} @ ${esc(g.home)}</span>
              <span class="game-line">${g.total ? `O/U ${g.total.toFixed(1)}` : ""}</span>
            </div>
            <div class="game-line">${
              g.favorite ? `Favorito: ${esc(g.favorite)} ${Math.abs(g.spread ?? 0).toFixed(1)}` : "Sin línea"
            }${g.bookmaker ? ` · ${esc(g.bookmaker)}` : ""}</div>
            <div class="game-implied">
              <span>${esc(g.away)} <b>${g.away_implied?.toFixed(1) ?? "—"}</b></span>
              <span>${esc(g.home)} <b>${g.home_implied?.toFixed(1) ?? "—"}</b></span>
            </div>
          </div>`
          )
          .join("")}
      </div>
    </div>`;
}

async function loadOdds() {
  const box = $("#odds-content");
  box.innerHTML = `<div class="panel"><div class="skeleton" style="height:90px"></div></div>`;
  try {
    box.innerHTML = oddsHtml(await api("/api/odds"));
  } catch (error) {
    box.innerHTML = `<p class="empty">${esc(error.message)}</p>`;
  }
}

/* ================================ Arranque =============================== */

/** Vacía las vistas que dependen del ranking, para que se recalculen. */
function invalidateDerivedViews() {
  $("#trend-list").innerHTML = "";
  $("#team-content").innerHTML = "";
  $("#draft-content").innerHTML = "";
  if (state.view === "trends") loadTrends();
  if (state.view === "team") loadTeam();
  if (state.view === "draft") loadDraft();
}

init();

/* ================================= Draft ================================= */

let draftTimer = null;

function stopDraftRefresh() {
  if (draftTimer) {
    clearInterval(draftTimer);
    draftTimer = null;
  }
}

/** Mientras el draft esté en marcha se recarga solo: los picks vuelan. */
function startDraftRefresh() {
  stopDraftRefresh();
  draftTimer = setInterval(() => {
    if (state.view === "draft" && !document.hidden) loadDraft({ quiet: true });
  }, 12000);
}

function draftStatusHtml(b) {
  const progreso = b.total_picks ? `${b.picks_made}/${b.total_picks} picks` : `${b.picks_made} picks`;

  let turno;
  if (b.status === "pre_draft") {
    turno = `<div class="draft-waiting">El draft no ha empezado${
      b.my_slot ? ` · eliges en el puesto ${b.my_slot} de ${b.teams}` : ""
    }</div>`;
  } else if (b.status === "complete") {
    turno = `<div class="draft-waiting">Draft terminado</div>`;
  } else if (b.is_my_turn) {
    turno = `<div class="draft-turn">🔥 ¡Te toca elegir!</div>`;
  } else if (b.picks_until_my_turn !== null && b.picks_until_my_turn !== undefined) {
    turno = `<div class="draft-waiting">Faltan ${b.picks_until_my_turn} pick${
      b.picks_until_my_turn === 1 ? "" : "s"
    } para tu turno${b.my_next_pick_no ? ` (pick #${b.my_next_pick_no})` : ""}</div>`;
  } else {
    turno = `<div class="draft-waiting">Draft en marcha</div>`;
  }

  return `
    <div class="draft-status ${b.is_my_turn ? "is-my-turn" : ""}">
      ${turno}
      <div class="stat-block"><span class="stat-value">${b.current_round ?? "—"}</span><span class="stat-label">Ronda</span></div>
      <div class="stat-block"><span class="stat-value">${b.my_slot ?? "—"}</span><span class="stat-label">Mi puesto</span></div>
      <div class="stat-block"><span class="stat-value">${progreso}</span><span class="stat-label">Progreso</span></div>
      ${
        b.status === "drafting"
          ? `<div class="autorefresh"><span class="dot"></span>Actualizando solo cada 12 s</div>`
          : ""
      }
    </div>`;
}

function suggestionHtml(sug, i) {
  return `
    <div class="sug-card ${i === 0 ? "top" : ""}" data-player-id="${esc(sug.player.player_id)}">
      <div class="sug-order">${i + 1}</div>
      <div>
        <div class="sug-name">${esc(sug.player.name)}
          <span class="pos-tag pos-${esc(positionOf(sug.player))}">${esc(positionOf(sug.player))}</span>
          <span class="player-meta">${esc(sug.player.team || "—")}${
            sug.tier ? ` · tier ${sug.tier}` : ""
          }</span>
        </div>
        <ul class="sug-why">${sug.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      </div>
      <div class="sug-value"><b>${sug.value.toFixed(0)}</b><span>Para ti</span></div>
    </div>`;
}

function draftHtml(b) {
  const avisos = b.warnings.length
    ? `<div class="warnings" style="margin:0 0 16px">${b.warnings
        .map((w) => `<div class="warning">${esc(w)}</div>`)
        .join("")}</div>`
    : "";

  const needs = b.needs.length
    ? `<h3>Huecos por cubrir</h3>
       <div class="need-chips">${b.needs
         .map(
           (n) =>
             `<span class="need-chip ${esc(n.urgency)}">${esc(n.position)} ${n.filled}/${
               n.required
             }${n.missing ? ` · faltan ${n.missing}` : " ✓"}</span>`
         )
         .join("")}</div>`
    : "";

  const cliffs = b.tiers.length
    ? `<h3>Tiers que se están vaciando</h3>
       ${b.tiers
         .map(
           (t) =>
             `<div class="cliff-item">${esc(t.position)} tier ${t.tier}: quedan <b>${
               t.remaining
             }</b></div>`
         )
         .join("")}`
    : "";

  const rachas = Object.entries(b.position_run || {})
    .filter(([, n]) => n >= 3)
    .sort((a, b2) => b2[1] - a[1]);
  const rachasHtml = rachas.length
    ? `<h3>Qué se está llevando la sala</h3>
       <div class="need-chips">${rachas
         .map(
           ([pos, n]) =>
             `<span class="need-chip ${n >= 4 ? "alta" : "media"}">${esc(pos)}: ${n} de los últimos 10</span>`
         )
         .join("")}</div>`
    : "";

  const miRoster = b.my_roster.length
    ? `<h3>Mi plantilla (${b.my_roster.length})</h3>
       ${b.my_roster
         .map(
           (p) => `
        <div class="pick-row mine">
          <span class="no">R${p.round}</span>
          <span>${esc(p.player ? p.player.name : "?")}</span>
          <span class="pos-tag pos-${esc(p.player ? positionOf(p.player) : "UNK")}">${esc(
            p.player ? positionOf(p.player) : "?"
          )}</span>
        </div>`
         )
         .join("")}`
    : `<h3>Mi plantilla</h3><p class="panel-sub">Todavía no has elegido a nadie.</p>`;

  const ultimos = b.recent_picks.length
    ? `<h3>Últimos picks</h3>
       ${b.recent_picks
         .map(
           (p) => `
        <div class="pick-row ${p.is_mine ? "mine" : ""}">
          <span class="no">#${p.pick_no}</span>
          <span>${esc(p.player ? p.player.name : "?")}</span>
          <span class="pos-tag pos-${esc(p.player ? positionOf(p.player) : "UNK")}">${esc(
            p.player ? positionOf(p.player) : "?"
          )}</span>
          <span class="who">${esc(p.picked_by_name || (p.is_mine ? "tú" : ""))}</span>
        </div>`
         )
         .join("")}`
    : "";

  const tablero = b.best_available
    .map(
      (e) => `
      <div class="board-row" data-player-id="${esc(e.player.player_id)}">
        <span class="r">${e.rank}</span>
        <span class="n">${esc(e.player.name)}
          <span class="t">${esc(e.player.team || "—")}${e.tier ? ` · T${e.tier}` : ""}</span>
        </span>
        <span class="pos-tag pos-${esc(positionOf(e.player))}">${esc(positionOf(e.player))}${
          e.position_rank || ""
        }</span>
        <span class="s">${e.score.toFixed(1)}</span>
      </div>`
    )
    .join("");

  return `
    ${avisos}
    ${draftStatusHtml(b)}
    <div class="draft-cols">
      <div>
        <div class="panel">
          <h3>${b.is_my_turn ? "Cógelo a él" : "Si te tocara ahora"}</h3>
          <p class="panel-sub">
            No es el mejor disponible a secas: es el mejor <em>para ti</em>, contando los huecos
            que te faltan y los tiers que se están vaciando.
          </p>
          ${b.suggestions.map(suggestionHtml).join("")}
        </div>
        <div class="panel">
          ${needs}
          ${rachasHtml}
          ${cliffs}
        </div>
      </div>

      <div>
        <div class="panel">
          <h3>Mejores disponibles</h3>
          <div class="board-list">${tablero}</div>
        </div>
        <div class="panel">
          ${miRoster}
          ${ultimos}
        </div>
      </div>
    </div>`;
}

async function loadDraft({ quiet = false } = {}) {
  const box = $("#draft-content");
  if (!quiet) box.innerHTML = `<div class="panel"><div class="skeleton" style="height:90px"></div></div>`;
  try {
    const board = await api("/api/draft", {
      scoring: state.scoring,
      superflex: state.superflex,
      board_size: 80,
    });
    box.innerHTML = draftHtml(board);
    if (board.status === "drafting") startDraftRefresh();
    else stopDraftRefresh();
  } catch (error) {
    stopDraftRefresh();
    if (quiet) return; // un fallo puntual no borra lo que ya se ve
    box.innerHTML =
      error.status === 409
        ? setupTeamHtml(error.message)
        : `<div class="panel"><p class="empty">${esc(error.message)}</p></div>`;
  }
}
