// Entry point: router, header (city + global search), compare tray.
import { api } from "./api.js";
import { $, $$, esc, debounce, store } from "./util.js";
import { state, onChange, renderCounts } from "./state.js";
import { renderExplore, renderMap } from "./views/explore.js";
import { renderDetail } from "./views/detail.js";
import { renderCompare, renderShortlist, renderLocalities, renderTools, renderGuide, renderAbout, renderBuilder } from "./views/pages.js";

const main = $("#main");
let meta;

const routes = [
  [/^\/?$/, "explore", (p, q) => renderExplore(main, meta, q)],
  [/^\/map$/, "map", (p, q) => renderMap(main, meta, q)],
  [/^\/property\/(\d+)/, "explore", (m) => renderDetail(main, meta, +m[1])],
  [/^\/builder\/(\d+)/, "explore", (m) => renderBuilder(main, meta, +m[1])],
  [/^\/compare$/, "compare", (p, q) => renderCompare(main, meta, q)],
  [/^\/shortlist$/, "shortlist", () => renderShortlist(main, meta)],
  [/^\/localities$/, "localities", () => renderLocalities(main, meta)],
  [/^\/tools$/, "tools", () => renderTools(main, meta)],
  [/^\/guide$/, "guide", () => renderGuide(main, meta)],
  [/^\/about$/, "about", () => renderAbout(main, meta)],
];

export function parseHash() {
  const h = location.hash.replace(/^#/, "") || "/";
  const [path, qs = ""] = h.split("?");
  return { path, query: Object.fromEntries(new URLSearchParams(qs)) };
}

async function route() {
  const { path, query } = parseHash();
  for (const [re, nav, fn] of routes) {
    const m = path.match(re);
    if (m) {
      $$(".mainnav a").forEach((a) => a.classList.toggle("active", a.dataset.nav === nav));
      $("#mainnav").classList.remove("open");
      main.innerHTML = '<div class="spinner" aria-label="Loading"></div>';
      try {
        await fn(m, query);
      } catch (e) {
        console.error(e);
        main.innerHTML = `<div class="empty card"><h2>Something went wrong</h2><p>${esc(e.message)}</p><a class="btn" href="#/">Back to search</a></div>`;
      }
      if (!path.startsWith("/property") || !query.section) window.scrollTo(0, 0);
      return;
    }
  }
  main.innerHTML = `<div class="empty card"><h2>Page not found</h2><a class="btn" href="#/">Back to search</a></div>`;
}

// ---------------------------------------------------------------- header
function setupCity() {
  const sel = $("#citySelect");
  if (!meta.cities.find((c) => c.city === state.city) && meta.cities[0]) state.city = meta.cities[0].city;
  sel.innerHTML = meta.cities.map((c) => `<option value="${esc(c.city)}">${esc(c.city)} (${c.count})</option>`).join("");
  sel.value = state.city;
  sel.addEventListener("change", () => {
    state.city = sel.value;
    const { path } = parseHash();
    const target = path === "/map" ? "#/map" : path === "/localities" ? "#/localities" : "#/";
    if ((location.hash || "#/") === target) route();
    else location.hash = target;
  });
}

function setupSearch() {
  const input = $("#globalSearch");
  const box = $("#suggestions");
  let items = [];
  let active = -1;

  const close = () => {
    box.hidden = true;
    active = -1;
    input.parentElement.setAttribute("aria-expanded", "false");
  };
  const go = (it) => {
    close();
    if (!it) {
      location.hash = "#/?q=" + encodeURIComponent(input.value.trim());
      return;
    }
    if (it.type === "project") {
      location.hash = "#/property/" + it.id;
      input.value = "";
    } else {
      state.city = it.city;
      $("#citySelect").value = it.city;
      location.hash = "#/?locality=" + encodeURIComponent(it.name);
      input.value = "";
    }
  };
  const render = () => {
    if (!items.length) return close();
    box.innerHTML = items
      .map((it, i) =>
        `<li role="option" data-i="${i}" aria-selected="${i === active}"><span>${esc(it.name)}${
          it.type === "project" ? ` <span class="muted small">· ${esc(it.builder || "")}</span>` : ""
        }</span><span class="tag">${it.type === "project" ? esc(it.locality + ", " + it.city) : "Locality · " + esc(it.city)}</span></li>`)
      .join("") + `<li data-i="-1"><span>Search all for “${esc(input.value)}”</span><span class="tag">Enter ↵</span></li>`;
    box.hidden = false;
    input.parentElement.setAttribute("aria-expanded", "true");
  };
  const fetchSug = debounce(async () => {
    const q = input.value.trim();
    if (q.length < 2) return close();
    items = await api.suggest(q).catch(() => []);
    active = -1;
    render();
  }, 180);

  input.addEventListener("input", fetchSug);
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      active = Math.max(-1, Math.min(items.length - 1, active + (e.key === "ArrowDown" ? 1 : -1)));
      render();
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(items[active]);
    } else if (e.key === "Escape") close();
  });
  box.addEventListener("mousedown", (e) => {
    const li = e.target.closest("li");
    if (li) {
      e.preventDefault();
      go(items[+li.dataset.i]);
    }
  });
  input.addEventListener("blur", () => setTimeout(close, 120));
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      e.preventDefault();
      input.focus();
    }
  });
}

function setupTheme() {
  const saved = store.get("theme", null);
  if (saved) document.documentElement.dataset.theme = saved;
  $("#themeToggle").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.dataset.theme = dark ? "light" : "dark";
    store.set("theme", document.documentElement.dataset.theme);
  });
  $("#menuToggle").addEventListener("click", () => $("#mainnav").classList.toggle("open"));
}

async function renderTray() {
  const ids = state.compare();
  const tray = $("#compareTray");
  const { path } = parseHash();
  if (!ids.length || path === "/compare") {
    tray.hidden = true;
    return;
  }
  tray.hidden = false;
  tray.innerHTML = `<strong>${ids.length} to compare</strong>
    <a class="btn primary small" href="#/compare">Compare now</a>
    <button class="btn small" id="trayClear">Clear</button>`;
  $("#trayClear").onclick = () => state.clearCompare();
}

async function init() {
  setupTheme();
  try {
    meta = await api.meta();
  } catch (e) {
    main.innerHTML = `<div class="empty card"><h2>Cannot reach the API</h2><p>${esc(e.message)}</p><p>Is the server running? <code>python -m housingsearch</code></p></div>`;
    return;
  }
  $("#demoBanner").hidden = !meta.has_demo_data;
  setupCity();
  setupSearch();
  renderCounts();
  onChange(renderTray);
  window.addEventListener("hashchange", () => {
    route();
    renderTray();
  });
  await route();
  renderTray();
}

init();
