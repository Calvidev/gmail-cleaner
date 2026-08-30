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

function drawerHtml(detail) {
  const { ranked, news } = detail;
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
      $("#fa-toggle-wrap").title = `Liga ${meta.league_id || ""}`;
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

function switchView(view) {
  state.view = view;
  $$(".tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.view === view));
  $("#view-rankings").hidden = view !== "rankings";
  $("#view-news").hidden = view !== "news";
  if (view === "news" && !$("#news-grid").children.length) loadNews();
}

function bindEvents() {
  $$(".tab").forEach((tab) =>
    tab.addEventListener("click", () => switchView(tab.dataset.view))
  );

  $("#scoring").addEventListener("change", (e) => {
    state.scoring = e.target.value;
    loadRankings();
  });
  $("#superflex").addEventListener("change", (e) => {
    state.superflex = e.target.checked;
    loadRankings();
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
      await fetch("/api/refresh", { method: "POST" });
      await loadMeta();
      await loadNewsCounts();
      await loadRankings();
      if (state.view === "news") await loadNews();
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

init();
