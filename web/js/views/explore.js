// Explore (search + filters + results) and Map views.
import { api } from "../api.js";
import { $, $$, esc, inr, psf, date, trendArrow, scoreRing, reraBadge, statusBadge, fairBadge, stars, debounce } from "../util.js";
import { state, onChange } from "../state.js";

const BUDGETS = [0, 2.5e6, 5e6, 7.5e6, 1e7, 1.5e7, 2e7, 3e7, 5e7, 1e8, 2e8];
const MULTI = ["locality", "builder", "property_type", "status", "rera_status", "bhk", "amenities", "fair_price"];
const SORTS = [
  ["trust", "Trust score (high → low)"],
  ["relevance", "Best match"],
  ["price_asc", "Price (low → high)"],
  ["price_desc", "Price (high → low)"],
  ["psf_asc", "₹/sq ft (low → high)"],
  ["psf_desc", "₹/sq ft (high → low)"],
  ["possession", "Earliest possession"],
  ["appreciation", "12-month appreciation"],
  ["rating", "Review rating"],
  ["name", "Name (A → Z)"],
];
const LABELS = {
  q: "Search", locality: "Locality", builder: "Builder", property_type: "Type", status: "Status", rera_status: "RERA",
  bhk: "BHK", amenities: "Amenity", fair_price: "Price vs locality", min_price: "Min", max_price: "Max",
  min_size: "Min size", max_size: "Max size", min_psf: "Min ₹/sqft", max_psf: "Max ₹/sqft", possession_by: "Possession by",
  min_trust: "Trust ≥", min_rating: "Rating ≥", rera_only: "RERA registered", no_red_flags: "No critical flags",
  all_approvals: "All approvals", available_only: "Units available",
};

function toArr(v) {
  return v ? String(v).split(",").filter(Boolean) : [];
}
function cityMeta(meta) {
  return meta.cities.find((c) => c.city === state.city) || meta.cities[0];
}

export async function renderExplore(main, meta, query) {
  const f = { ...query };
  const city = cityMeta(meta);
  const view = f.view || "grid";

  main.innerHTML = `
  <div class="explore">
    <aside class="filters card" id="filters" aria-label="Filters">${filtersHtml(meta, city, f)}</aside>
    <section>
      <div class="results-head">
        <div>
          <h1 id="resultsTitle">Projects in ${esc(city.city)}</h1>
          <div class="muted small" id="resultsSub"></div>
        </div>
        <div class="row" style="flex-wrap:wrap">
          <button class="btn filter-toggle" id="openFilters">⚙ Filters</button>
          <select id="sort" aria-label="Sort by" style="width:auto">${SORTS.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select>
          <div class="row" role="group" aria-label="View">
            <button class="btn small ${view === "grid" ? "on" : ""}" data-view="grid" title="Grid">▦</button>
            <button class="btn small ${view === "list" ? "on" : ""}" data-view="list" title="List">☰</button>
            <a class="btn small" id="toMap" title="Map">🗺 Map</a>
          </div>
          <a class="btn small" id="exportCsv" title="Download results as CSV">⬇ CSV</a>
        </div>
      </div>
      <div class="active-filters" id="activeFilters"></div>
      <div id="results" class="results ${view}"></div>
      <div class="pager" id="pager"></div>
    </section>
  </div>`;

  $("#sort").value = f.sort || (f.q ? "relevance" : "trust");

  const update = (patch = {}, { resetPage = true } = {}) => {
    Object.assign(f, patch);
    if (resetPage && !("page" in patch)) delete f.page;
    for (const k of Object.keys(f)) if (f[k] === "" || f[k] == null || f[k] === false) delete f[k];
    const qs = new URLSearchParams(f).toString();
    history.replaceState(null, "", "#/" + (qs ? "?" + qs : ""));
    load();
  };

  // ---- wire filters
  const fl = $("#filters");
  fl.addEventListener("change", (e) => {
    const t = e.target;
    if (!t.name) return;
    if (t.type === "checkbox" && MULTI.includes(t.name)) {
      const vals = $$(`input[name="${t.name}"]:checked`, fl).map((x) => x.value);
      update({ [t.name]: vals.join(",") });
    } else if (t.type === "checkbox") update({ [t.name]: t.checked ? "1" : "" });
    else update({ [t.name]: t.value });
  });
  fl.addEventListener("input", debounce((e) => {
    const t = e.target;
    if (t.name === "q") update({ q: t.value.trim() });
    if (t.dataset.filterList) {
      const term = t.value.toLowerCase();
      $$(`#${t.dataset.filterList} label`, fl).forEach((l) => (l.hidden = !l.textContent.toLowerCase().includes(term)));
    }
    if (t.type === "range") $("#" + t.name + "Val").textContent = t.value;
  }, 250));
  fl.addEventListener("click", (e) => {
    const chip = e.target.closest("[data-chip]");
    if (chip) {
      const key = chip.dataset.chip;
      const vals = new Set(toArr(f[key]));
      vals.has(chip.dataset.value) ? vals.delete(chip.dataset.value) : vals.add(chip.dataset.value);
      chip.classList.toggle("on");
      update({ [key]: [...vals].join(",") });
    }
    if (e.target.id === "clearAll") {
      renderExplore(main, meta, f.view ? { view: f.view } : {});
      history.replaceState(null, "", "#/");
    }
    if (e.target.id === "closeFilters") closeFilters();
  });
  $("#sort").addEventListener("change", (e) => update({ sort: e.target.value }));
  $$("[data-view]").forEach((b) =>
    b.addEventListener("click", () => {
      $$("[data-view]").forEach((x) => x.classList.toggle("on", x === b));
      $("#results").className = "results " + b.dataset.view;
      update({ view: b.dataset.view }, { resetPage: false });
    })
  );
  const openFilters = () => {
    fl.classList.add("open");
    const bd = document.createElement("div");
    bd.className = "backdrop";
    bd.id = "filterBackdrop";
    bd.onclick = closeFilters;
    document.body.appendChild(bd);
  };
  const closeFilters = () => {
    fl.classList.remove("open");
    $("#filterBackdrop")?.remove();
  };
  $("#openFilters").onclick = openFilters;

  $("#activeFilters").addEventListener("click", (e) => {
    const c = e.target.closest("[data-remove]");
    if (!c) return;
    const [key, val] = [c.dataset.remove, c.dataset.value];
    if (MULTI.includes(key)) {
      const vals = toArr(f[key]).filter((v) => v !== val);
      update({ [key]: vals.join(",") });
    } else update({ [key]: "" });
    syncControls(fl, f);
  });
  $("#pager").addEventListener("click", (e) => {
    const b = e.target.closest("[data-page]");
    if (b) {
      update({ page: b.dataset.page }, { resetPage: false });
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

  // re-render cards when shortlist/compare changes (buttons state)
  let lastData = null;
  const offChange = () => lastData && $("#results") && renderCards(lastData.results);
  onChange(offChange);

  async function load() {
    const params = { ...f, city: city.city, page_size: 24 };
    delete params.view;
    $("#toMap").href = "#/map?" + new URLSearchParams({ ...f, view: "" }).toString().replace(/&?view=/, "");
    $("#exportCsv").href = api.exportUrl({ ...params, page_size: undefined });
    $("#results").innerHTML = '<div class="spinner"></div>';
    const data = await api.search(params);
    lastData = data;
    $("#resultsTitle").textContent = `${data.total} project${data.total === 1 ? "" : "s"} in ${city.city}`;
    $("#resultsSub").textContent = f.q ? `Matching “${f.q}”` : `Prices compiled from ${meta.cities.length > 0 ? "multiple portals, builders and brokers" : ""}; last update ${date(meta.last_price_update, true)}`;
    renderActive(f);
    renderCards(data.results);
    renderPager(data);
  }

  function renderCards(items) {
    const el = $("#results");
    if (!items.length) {
      el.innerHTML = `<div class="empty card" style="grid-column:1/-1"><h2>No projects match</h2><p>Try removing a filter or widening the budget.</p><button class="btn" onclick="location.hash='#/'">Clear all filters</button></div>`;
      return;
    }
    el.innerHTML = items.map(cardHtml).join("");
    bindCardActions(el, items);
  }

  function renderPager(data) {
    const pages = Math.ceil(data.total / data.page_size);
    if (pages <= 1) return ($("#pager").innerHTML = "");
    let h = "";
    for (let i = 1; i <= pages; i++) {
      if (i === 1 || i === pages || Math.abs(i - data.page) <= 2)
        h += `<button class="btn small ${i === data.page ? "on" : ""}" data-page="${i}">${i}</button>`;
      else if (Math.abs(i - data.page) === 3) h += `<span class="muted">…</span>`;
    }
    $("#pager").innerHTML = h;
  }

  function renderActive(f) {
    const chips = [];
    for (const [k, v] of Object.entries(f)) {
      if (["sort", "page", "view"].includes(k) || !LABELS[k]) continue;
      if (MULTI.includes(k)) toArr(v).forEach((x) => chips.push([k, x, `${LABELS[k]}: ${k === "bhk" ? (x === "4" ? "4+" : x) + " BHK" : x}`]));
      else if (["rera_only", "no_red_flags", "all_approvals", "available_only"].includes(k)) chips.push([k, v, LABELS[k]]);
      else if (k.includes("price")) chips.push([k, v, `${LABELS[k]} ${inr(+v)}`]);
      else chips.push([k, v, `${LABELS[k]} ${v}`]);
    }
    $("#activeFilters").innerHTML = chips.length
      ? chips.map(([k, v, l]) => `<button class="chip" data-remove="${esc(k)}" data-value="${esc(v)}">${esc(l)} ✕</button>`).join("") +
        `<button class="chip" onclick="location.hash='#/'">Clear all</button>`
      : "";
  }

  syncControls(fl, f);
  await load();
}

function syncControls(fl, f) {
  $$("input, select", fl).forEach((el) => {
    if (!el.name) return;
    if (el.type === "checkbox" && MULTI.includes(el.name)) el.checked = toArr(f[el.name]).includes(el.value);
    else if (el.type === "checkbox") el.checked = !!f[el.name];
    else el.value = f[el.name] ?? (el.type === "range" ? el.min : "");
  });
  $$("[data-chip]", fl).forEach((c) => c.classList.toggle("on", toArr(f[c.dataset.chip]).includes(c.dataset.value)));
}

function filtersHtml(meta, city, f) {
  const chipGroup = (key, opts) =>
    `<div class="chips">${opts.map(([v, l]) => `<button type="button" class="chip" data-chip="${key}" data-value="${esc(v)}">${esc(l)}</button>`).join("")}</div>`;
  const check = (key, opts, id) =>
    `<div class="checklist" id="${id}">${opts
      .map(([v, l, n]) => `<label><input type="checkbox" name="${key}" value="${esc(v)}"> ${esc(l)}${n != null ? `<span class="n">${n}</span>` : ""}</label>`)
      .join("")}</div>`;
  const budgetOpts = (placeholder) =>
    `<option value="">${placeholder}</option>` + BUDGETS.slice(1).map((b) => `<option value="${b}">${inr(b)}</option>`).join("");

  return `
  <h3>Filters <span class="row"><button class="btn small" id="clearAll" type="button">Reset</button><button class="btn small filter-toggle" id="closeFilters" type="button">✕</button></span></h3>
  <div class="fgroup">
    <label class="field" for="fq">Keyword</label>
    <input id="fq" name="q" type="search" placeholder="Project, builder, RERA no.…" />
  </div>
  <div class="fgroup">
    <div class="ftitle">Budget</div>
    <div class="grid2">
      <select name="min_price" aria-label="Minimum budget">${budgetOpts("No min")}</select>
      <select name="max_price" aria-label="Maximum budget">${budgetOpts("No max")}</select>
    </div>
  </div>
  <div class="fgroup">
    <div class="ftitle">Bedrooms</div>
    ${chipGroup("bhk", [["1", "1 BHK"], ["2", "2 BHK"], ["3", "3 BHK"], ["4", "4+ BHK"]])}
  </div>
  <div class="fgroup">
    <div class="ftitle">Construction status</div>
    ${chipGroup("status", meta.statuses.map((s) => [s, s]))}
  </div>
  <div class="fgroup">
    <div class="ftitle">Possession by</div>
    <input type="month" name="possession_by" aria-label="Possession by month" />
  </div>
  <div class="fgroup">
    <div class="ftitle">Safety checks</div>
    <label class="switch">RERA registered only <input type="checkbox" name="rera_only"></label>
    <label class="switch">No critical red flags <input type="checkbox" name="no_red_flags"></label>
    <label class="switch">All due approvals in place <input type="checkbox" name="all_approvals"></label>
    <label class="switch">Units still available <input type="checkbox" name="available_only"></label>
  </div>
  <div class="fgroup">
    <div class="ftitle">Min trust score <span id="min_trustVal" class="muted">${esc(f.min_trust || 0)}</span></div>
    <input type="range" name="min_trust" min="0" max="100" step="5" value="0" style="width:100%" />
  </div>
  <div class="fgroup">
    <div class="ftitle">Locality</div>
    <input type="search" placeholder="Filter localities…" data-filter-list="locList" style="margin-bottom:6px" />
    ${check("locality", city.localities.map((l) => [l.name, l.name, l.count]), "locList")}
  </div>
  <div class="fgroup">
    <div class="ftitle">Price vs locality</div>
    ${chipGroup("fair_price", [["Below locality average", "Below avg"], ["In line with locality", "In line"], ["Premium over locality", "Premium"]])}
  </div>
  <div class="fgroup">
    <div class="ftitle">Property type</div>
    ${chipGroup("property_type", meta.property_types.map((s) => [s, s]))}
  </div>
  <div class="fgroup">
    <div class="ftitle">Size (super built-up, sq ft)</div>
    <div class="grid2"><input type="number" name="min_size" placeholder="Min" min="0" step="50" /><input type="number" name="max_size" placeholder="Max" min="0" step="50" /></div>
  </div>
  <div class="fgroup">
    <div class="ftitle">Price per sq ft (₹)</div>
    <div class="grid2"><input type="number" name="min_psf" placeholder="Min" min="0" step="250" /><input type="number" name="max_psf" placeholder="Max" min="0" step="250" /></div>
  </div>
  <div class="fgroup">
    <div class="ftitle">Review rating</div>
    <select name="min_rating"><option value="">Any</option><option value="3">3★ & above</option><option value="3.5">3.5★ & above</option><option value="4">4★ & above</option></select>
  </div>
  <div class="fgroup">
    <div class="ftitle">RERA status</div>
    ${chipGroup("rera_status", meta.rera_statuses.map((s) => [s, s]))}
  </div>
  <div class="fgroup">
    <div class="ftitle">Builder</div>
    <input type="search" placeholder="Filter builders…" data-filter-list="builderList" style="margin-bottom:6px" />
    ${check("builder", meta.builders.map((b) => [b, b]), "builderList")}
  </div>
  <div class="fgroup">
    <div class="ftitle">Must have amenities</div>
    ${check("amenities", meta.amenities.map((a) => [a, a]), "amenList")}
  </div>`;
}

export function cardHtml(p) {
  const flag = p.top_flag
    ? `<div class="flag ${p.flags_critical ? "" : "warn"}">⚠ ${esc(p.top_flag)}${p.flags_critical + p.flags_warning > 1 ? ` <span class="small">+${p.flags_critical + p.flags_warning - 1} more</span>` : ""}</div>`
    : "";
  const configs = p.configs.slice(0, 4).join(", ") + (p.configs.length > 4 ? "…" : "");
  return `
  <article class="pcard card">
    <div class="top">
      <div class="title">
        <a href="#/property/${p.id}">${esc(p.name)}</a>
        <div class="sub">${esc(p.builder || "")} · ${esc(p.locality)}, ${esc(p.city)}</div>
      </div>
      ${scoreRing(p.trust_score, p.trust_grade)}
    </div>
    <div class="badges">${statusBadge(p.status)} ${reraBadge(p.rera_status)} ${fairBadge(p.fair_price)}
      ${p.overdue_months ? `<span class="badge bad">Overdue ${p.overdue_months} mo</span>` : ""}</div>
    <div class="stats">
      <div><div class="l">Price</div><div class="v">${inr(p.price_min)} – ${inr(p.price_max)}</div></div>
      <div><div class="l">Rate</div><div class="v">${psf(p.psf)}</div><div class="small">${trendArrow(p.price_change_12m)} <span class="muted">12m</span></div></div>
      <div><div class="l">Possession</div><div class="v">${p.status === "Ready to Move" ? "Ready" : date(p.possession_date)}</div></div>
      <div><div class="l">Configs</div><div class="v small">${esc(configs)}</div></div>
      <div><div class="l">Available</div><div class="v">${p.available_units ?? "—"}<span class="muted small"> / ${p.total_units ?? "—"}</span></div></div>
      <div><div class="l">Reviews</div><div class="v small">${p.avg_rating ? stars(p.avg_rating) + " " + p.avg_rating : "—"} <span class="muted">(${p.review_count})</span></div></div>
    </div>
    ${flag}
    <div class="foot">
      <span class="small muted">${p.source_count} price sources · approvals ${p.approvals_pct ?? "—"}%</span>
      <span class="spacer"></span>
      <button class="btn small ${state.isShortlisted(p.id) ? "on" : ""}" data-act="short" data-id="${p.id}" title="Shortlist">${state.isShortlisted(p.id) ? "♥" : "♡"}</button>
      <button class="btn small ${state.inCompare(p.id) ? "on" : ""}" data-act="cmp" data-id="${p.id}" title="Add to compare">⇄</button>
      <a class="btn small primary" href="#/property/${p.id}">Details</a>
    </div>
  </article>`;
}

export function bindCardActions(root, items) {
  const byId = Object.fromEntries(items.map((i) => [i.id, i]));
  root.onclick = (e) => {
    const b = e.target.closest("[data-act]");
    if (!b) return;
    const p = byId[b.dataset.id];
    if (b.dataset.act === "short") state.toggleShortlist(p);
    if (b.dataset.act === "cmp") state.toggleCompare(p.id);
  };
}

// --------------------------------------------------------------------- map
const GRADE_COLORS = { A: "#16a34a", B: "#65a30d", C: "#d97706", D: "#dc2626" };

export async function renderMap(main, meta, query) {
  const city = cityMeta(meta);
  const params = { ...query, city: city.city, page_size: 200 };
  delete params.view;
  main.innerHTML = `
    <div class="results-head">
      <div><h1 id="mapTitle">Map of ${esc(city.city)}</h1><div class="muted small">Colour = trust grade. Click a pin for details. Filters from the Explore page apply here.</div></div>
      <a class="btn" href="#/?${new URLSearchParams(query)}">⚙ Edit filters / list view</a>
    </div>
    <div class="legend">${Object.entries(GRADE_COLORS).map(([g, c]) => `<span><i class="dot" style="background:${c}"></i>Grade ${g}</span>`).join("")}</div>
    <div id="mapView"></div>`;
  let results = [];
  let page = 1;
  for (;;) {
    const d = await api.search({ ...params, page });
    results = results.concat(d.results);
    if (results.length >= d.total || !d.results.length) break;
    page++;
  }
  $("#mapTitle").textContent = `${results.length} projects on the map · ${city.city}`;
  if (!window.L) {
    $("#mapView").innerHTML = `<div class="empty">Map library could not load (offline?). Use the list view instead.</div>`;
    return;
  }
  const pts = results.filter((r) => r.lat);
  const map = L.map("mapView");
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18, attribution: "© OpenStreetMap contributors",
  }).addTo(map);
  pts.forEach((p) => {
    L.circleMarker([p.lat, p.lng], { radius: 9, color: "#fff", weight: 2, fillColor: GRADE_COLORS[p.trust_grade], fillOpacity: 0.9 })
      .addTo(map)
      .bindPopup(`<strong><a href="#/property/${p.id}">${esc(p.name)}</a></strong><br>${esc(p.builder || "")}<br>
        ${esc(p.locality)} · ${esc(p.status)}<br>${inr(p.price_min)} – ${inr(p.price_max)} · ${psf(p.psf)}<br>
        Trust ${p.trust_score} (${p.trust_grade}) · RERA ${esc(p.rera_status)}`);
  });
  if (pts.length) map.fitBounds(pts.map((p) => [p.lat, p.lng]), { padding: [30, 30] });
  else map.setView([20.6, 78.9], 5);
}
