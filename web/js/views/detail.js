// Property detail: everything known about one project, in one page.
import { api } from "../api.js";
import { $, $$, esc, inr, psf, num, pct, date, ago, trendArrow, stars, scoreRing, reraBadge, statusBadge, fairBadge, emi, toast, priceRange, sourceBadge } from "../util.js";
import { state, onChange } from "../state.js";
import { lineChart } from "../charts.js";

const SECTIONS = [
  ["overview", "Overview"], ["prices", "Prices by source"], ["configs", "Configurations"], ["delivery", "Delivery"],
  ["rera", "RERA & approvals"], ["legal", "Legal"], ["reviews", "Reviews"], ["builder", "Builder"],
  ["location", "Location"], ["costs", "Total cost & EMI"], ["verify", "Verify live"], ["checklist", "Buyer checklist"],
];
const STATUS_ICON = { Obtained: "✓", Pending: "…", Missing: "✕", Unknown: "?", "Not Yet Due": "–", "Not Applicable": "n/a" };
const STATUS_LABEL = { Unknown: "Not verified" };

export async function renderDetail(main, meta, id) {
  const d = await api.property(id);
  const p = d.property;
  const s = d.summary;
  const b = d.builder;
  document.title = `${p.name}, ${p.locality} — HousingSearch`;

  main.innerHTML = `
  <nav class="crumbs"><a href="#/">${esc(p.city)}</a> › <a href="#/?locality=${encodeURIComponent(p.locality)}">${esc(p.locality)}</a> › ${esc(p.name)}</nav>
  <div class="card hero">
    <div>
      <h1>${esc(p.name)}</h1>
      <div class="meta">by ${b ? `<a href="#/builder/${b.id}">${esc(b.name)}</a>` : "Unknown builder"} · ${esc(p.address || p.locality + ", " + p.city)}</div>
      <div class="chips" style="margin-top:8px">${statusBadge(p.status)} ${reraBadge(p.rera_status)} <span class="badge">${esc(p.property_type || "")}</span> ${fairBadge(d.fair_price)}
        ${sourceBadge(p)}</div>
      <div class="kpis" style="margin-top:14px">
        ${kpi("Price range", priceRange(s.price_min, s.price_max), s.price_min == null ? "Check “Verify live” below" : s.configs.join(" · "))}
        ${kpi("Median rate", psf(d.prices.psf_median), d.prices.has_data ? `${trendArrow(d.prices.change_12m_pct)} last 12 months` : "")}
        ${kpi("Possession (RERA)", p.status === "Ready to Move" ? "Ready to move" : date(p.rera_possession_date), d.delivery.overdue_months ? `<span class="down">overdue ${d.delivery.overdue_months} mo</span>` : p.builder_possession_date ? "Builder says " + date(p.builder_possession_date) : "")}
        ${kpi(p.available_units == null ? "Total units" : "Units available", p.available_units == null ? num(p.total_units) : `${num(p.available_units)} / ${num(p.total_units)}`, p.total_units && p.available_units != null ? Math.round((1 - p.available_units / p.total_units) * 100) + "% sold" : "")}
        ${kpi("Approvals", d.approvals.unverified_count ? `${d.approvals.obtained_count} of ${d.approvals.due_count}` : d.approvals.completeness_pct != null ? d.approvals.completeness_pct + "%" : "—", d.approvals.unverified_count ? `confirmed · ${d.approvals.unverified_count} not verified yet` : `${d.approvals.obtained_count}/${d.approvals.due_count} due obtained`)}
        ${kpi("Reviews", d.reviews_summary.avg_rating ? d.reviews_summary.avg_rating + " ★" : d.reviews_summary.count ? d.reviews_summary.positive_pct + "% positive" : "—", `${d.reviews_summary.count} reviews, ${(d.reviews_summary.sources || []).length} sources`)}
      </div>
      <div class="actions">
        <button class="btn ${state.isShortlisted(p.id) ? "on" : ""}" id="btnShort">${state.isShortlisted(p.id) ? "♥ Shortlisted" : "♡ Shortlist"}</button>
        <button class="btn ${state.inCompare(p.id) ? "on" : ""}" id="btnCmp">⇄ ${state.inCompare(p.id) ? "In compare" : "Compare"}</button>
        <button class="btn" id="btnShare">🔗 Copy link</button>
        <button class="btn" onclick="window.print()">🖨 Print / PDF report</button>
        <a class="btn" href="${esc(d.verify_links.rera.url || "#")}" target="_blank" rel="noopener">Open ${esc(d.verify_links.rera.name)} ↗</a>
      </div>
    </div>
    <div style="text-align:center">
      ${scoreRing(d.trust.score, d.trust.grade, "", d.trust.limited)}
      <div class="small muted" style="margin-top:6px">Trust score${d.trust.limited ? ` · ${d.trust.coverage_pct}% data` : ""}</div>
      <a href="#" class="small" id="howScore">How is this calculated?</a>
    </div>
  </div>

  <nav class="secnav" aria-label="Sections">${SECTIONS.map(([k, l]) => `<a href="#" data-sec="${k}">${l}</a>`).join("")}</nav>

  <div class="detail-grid">
    <div>
      ${overview(d)}
      ${prices(d)}
      ${configs(d)}
      ${delivery(d)}
      ${approvals(d)}
      ${legal(d)}
      ${reviews(d)}
      ${builder(d)}
      ${locationSec(d)}
      ${costs(d)}
      ${verify(d)}
      ${checklist(d)}
    </div>
    <aside>
      ${scoreCard(d)}
      <div class="card panel note-box">
        <h3>My notes</h3>
        <textarea id="note" placeholder="Site-visit notes, quotes from sales, questions…">${esc(state.note(p.id))}</textarea>
        <div class="small muted">Saved in this browser only.</div>
      </div>
      ${d.similar.length ? `<div class="card panel"><h3>Similar projects nearby</h3><div class="similar" style="grid-template-columns:1fr">${d.similar
        .map((x) => `<a class="card" href="#/property/${x.id}"><strong>${esc(x.name)}</strong><div class="small muted">${esc(x.locality)}${x.psf ? " · " + psf(x.psf) : ""} · ${esc(x.status || "")}</div><div class="small">${priceRange(x.price_min, x.price_max)}</div></a>`)
        .join("")}</div></div>` : ""}
    </aside>
  </div>`;

  // --- behaviour
  $$(".secnav a").forEach((a) =>
    a.addEventListener("click", (e) => {
      e.preventDefault();
      document.getElementById("sec-" + a.dataset.sec)?.scrollIntoView({ behavior: "smooth" });
    })
  );
  $("#howScore").onclick = (e) => {
    e.preventDefault();
    $("#scoreCard").scrollIntoView({ behavior: "smooth" });
  };
  $("#btnShort").onclick = () => state.toggleShortlist(s);
  $("#btnCmp").onclick = () => state.toggleCompare(p.id);
  $("#btnShare").onclick = async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      toast("Link copied");
    } catch {
      toast(location.href);
    }
  };
  onChange(() => {
    const bs = $("#btnShort"), bc = $("#btnCmp");
    if (!bs) return;
    bs.className = "btn " + (state.isShortlisted(p.id) ? "on" : "");
    bs.textContent = state.isShortlisted(p.id) ? "♥ Shortlisted" : "♡ Shortlist";
    bc.className = "btn " + (state.inCompare(p.id) ? "on" : "");
    bc.textContent = "⇄ " + (state.inCompare(p.id) ? "In compare" : "Compare");
  });
  $("#note").addEventListener("input", (e) => state.setNote(p.id, e.target.value));
  $$("[data-copy]").forEach((el) =>
    el.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(el.dataset.copy);
        toast("Copied " + el.dataset.copy);
      } catch {}
    })
  );

  bindQuoteFilter(d);
  bindReviewFilter(d);
  bindCostCalc(d);
  drawMiniMap(d);
}

function kpi(label, value, sub = "") {
  return `<div class="kpi"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
}

// ---------------------------------------------------------------- sections
function overview(d) {
  const p = d.property;
  const flags = d.red_flags.length
    ? d.red_flags.map((f) => `<div class="flagrow ${f.level}"><span>${{ critical: "⛔", warning: "⚠", info: "ℹ" }[f.level]}</span><div><div class="t">${esc(f.title)}</div><div class="d">${esc(f.detail)}</div></div></div>`).join("")
    : `<div class="flagrow ok"><span>✓</span><div><div class="t">No red flags found</div><div class="d">Based on the data available. Still verify documents yourself.</div></div></div>`;
  const facts = [
    ["Project type", p.property_type], ["Launched", date(p.launch_date)], ["Land area", p.land_area_acres ? p.land_area_acres + " acres" : null],
    ["Open space", p.open_space_pct ? p.open_space_pct + "%" : null], ["Towers", p.towers], ["Floors", p.floors],
    ["Total units", num(p.total_units)], ["Density", p.land_area_acres && p.total_units ? Math.round(p.total_units / p.land_area_acres) + " units/acre" : null],
    ["PIN code", p.pincode], ["Bank loans approved by", (p.bank_approvals || []).join(", ") || "None recorded"],
    ["Data updated", date((p.updated_at || "").slice(0, 10), true)],
  ].filter(([, v]) => v != null && v !== "");
  return `
  <section class="card block" id="sec-overview">
    <h2>Overview & red flags</h2>
    <div class="flags">${flags}</div>
    <p style="margin-top:14px">${esc(p.description || "")}</p>
    <div class="table-wrap"><table class="data"><tbody>${facts.map(([k, v]) => `<tr><th style="width:38%">${k}</th><td>${esc(v)}</td></tr>`).join("")}</tbody></table></div>
    ${p.amenities?.length ? `<h3 style="margin-top:14px">Amenities (${p.amenities.length})</h3><div class="chips">${p.amenities.map((a) => `<span class="badge">${esc(a)}</span>`).join("")}</div>` : ""}
  </section>`;
}

function prices(d) {
  const ps = d.prices;
  if (!ps.has_data) return `<section class="card block" id="sec-prices"><h2>Prices by source</h2><p class="muted">No price quotes recorded yet. Use the Verify live links below.</p></section>`;
  const configsSeen = [...new Set(d.latest_quotes.map((q) => q.config_label).filter(Boolean))];
  const min = Math.min(...d.latest_quotes.filter((q) => q.price_per_sqft).map((q) => q.price_per_sqft));
  return `
  <section class="card block" id="sec-prices">
    <h2>Latest prices by source <span class="small muted">most recent quote seen on each source · last update ${date(ps.latest_quote_date, true)}</span></h2>
    <div class="kpis" style="margin-bottom:14px">
      ${kpi("Lowest quote", psf(ps.psf_min), "on " + esc(ps.cheapest_source || "—"))}
      ${kpi("Highest quote", psf(ps.psf_max), ps.source_spread_pct != null ? ps.source_spread_pct + "% spread across sources" : "")}
      ${kpi("Locality median", psf(d.fair_price.locality_median_psf), d.fair_price.delta_pct != null ? `This project ${pct(d.fair_price.delta_pct)}` : "")}
      ${kpi("12-month change", ps.change_12m_pct != null ? trendArrow(ps.change_12m_pct) : "—", `${ps.source_count} sources tracked`)}
    </div>
    <div class="row" style="margin-bottom:8px;flex-wrap:wrap">
      <label class="field" style="margin:0">Configuration</label>
      <select id="quoteCfg" style="width:auto"><option value="">All</option>${configsSeen.map((c) => `<option>${esc(c)}</option>`).join("")}</select>
      <label class="switch" style="margin-left:auto">Show full history <input type="checkbox" id="quoteAll"></label>
    </div>
    <div class="table-wrap" style="max-height:380px;overflow:auto"><table class="data" id="quoteTable"></table></div>
    <h3 style="margin-top:18px">Price trend (median ₹/sq ft across sources)</h3>
    ${lineChart(ps.series.map((x) => ({ x: x.month, y: x.psf })), { refY: d.fair_price.locality_median_psf, refLabel: "Locality median" })}
    <p class="small muted">Tip: quotes on portals are often asking prices. Builder and broker quotes may exclude GST, parking, clubhouse and PLC charges — always ask for an all-inclusive cost sheet. Lowest quote currently ${psf(min)}.</p>
  </section>`;
}

function bindQuoteFilter(d) {
  const tbl = $("#quoteTable");
  if (!tbl) return;
  const draw = () => {
    const cfg = $("#quoteCfg").value;
    const all = $("#quoteAll").checked;
    const rows = (all ? d.price_quotes : d.latest_quotes).filter((q) => !cfg || q.config_label === cfg);
    const lo = Math.min(...rows.filter((q) => q.price_per_sqft).map((q) => q.price_per_sqft));
    tbl.innerHTML = `<thead><tr><th>Source</th><th>Config</th><th class="num">Price</th><th class="num">₹/sq ft</th><th>Quoted on</th><th>Where quoted</th></tr></thead><tbody>${rows
      .map((q) => `<tr>
        <td><strong>${esc(q.source)}</strong>${q.price_per_sqft === lo ? ' <span class="badge good">lowest</span>' : ""}</td>
        <td>${esc(q.config_label || "—")}</td>
        <td class="num">${inr(q.price)}</td>
        <td class="num">${psf(q.price_per_sqft)}</td>
        <td class="nowrap">${date(q.quoted_on, true)} <span class="muted small">${ago(q.quoted_on)}</span></td>
        <td>${q.source_url ? `<a href="${esc(q.source_url)}" target="_blank" rel="noopener nofollow">View listing ↗</a>` : `<span class="muted small">${esc(q.notes || "No link")}</span>`}</td>
      </tr>`).join("")}</tbody>`;
  };
  $("#quoteCfg").onchange = draw;
  $("#quoteAll").onchange = draw;
  draw();
}

function configs(d) {
  const rows = d.configurations;
  if (!rows.length) return "";
  return `
  <section class="card block" id="sec-configs">
    <h2>Configurations, sizes & availability</h2>
    <div class="table-wrap"><table class="data">
      <thead><tr><th>Type</th><th class="num">Carpet</th><th class="num">Super built-up</th><th class="num">Loading</th><th class="num">Price range</th><th class="num">Effective ₹/sq ft (carpet)</th><th>Availability</th><th>Facing</th></tr></thead>
      <tbody>${rows.map((c) => {
        const load = c.carpet_sqft && c.super_builtup_sqft ? Math.round((c.super_builtup_sqft / c.carpet_sqft - 1) * 100) : null;
        const avail = c.units_total ? Math.round((c.units_available / c.units_total) * 100) : null;
        return `<tr>
          <td><strong>${esc(c.label)}</strong></td>
          <td class="num">${num(c.carpet_sqft)} sq ft</td>
          <td class="num">${c.super_builtup_sqft ? num(c.super_builtup_sqft) + " sq ft" : "—"}</td>
          <td class="num">${load != null ? `<span class="${load > 35 ? "down" : ""}">${load}%</span>` : "—"}</td>
          <td class="num nowrap">${priceRange(c.price_min, c.price_max)}</td>
          <td class="num">${c.carpet_sqft && c.price_min ? psf(c.price_min / c.carpet_sqft) : "—"}</td>
          <td style="min-width:140px">${c.units_total && c.units_available != null ? `<div class="small">${c.units_available} of ${c.units_total} left</div><div class="bar"><span style="width:${avail}%"></span></div>` : c.units_total ? `<div class="small">${c.units_total} units</div>` : "—"}</td>
          <td class="small">${esc(c.facing || "—")}</td>
        </tr>`;
      }).join("")}</tbody>
    </table></div>
    <p class="small muted" style="margin-top:8px">RERA requires sale by <strong>carpet area</strong>. Loading above ~35% means you pay for a lot of common area — compare effective carpet rates, not super built-up rates.</p>
  </section>`;
}

function delivery(d) {
  const p = d.property, dl = d.delivery;
  const pts = [
    ["launch", "Launch", p.launch_date],
    ["builder", "Builder promise", p.builder_possession_date],
    ["rera", "RERA date", p.rera_possession_date],
    ["today", "Today", new Date().toISOString().slice(0, 10)],
  ].filter(([, , v]) => v);
  const ts = pts.map(([, , v]) => new Date(v).getTime());
  const lo = Math.min(...ts), hi = Math.max(...ts);
  const pos = (v) => (hi === lo ? 50 : ((new Date(v).getTime() - lo) / (hi - lo)) * 100);
  let verdict;
  if (p.status === "Ready to Move") verdict = `<div class="flagrow ok"><span>✓</span><div><div class="t">Completed — ready to move</div><div class="d">Confirm the Occupancy Certificate before registration.</div></div></div>`;
  else if (dl.overdue_months) verdict = `<div class="flagrow critical"><span>⛔</span><div><div class="t">Overdue by ${dl.overdue_months} months vs RERA date</div><div class="d">Under RERA Sec 18 allottees can claim interest for every month of delay, or a full refund with interest.</div></div></div>`;
  else if (dl.on_track === false) verdict = `<div class="flagrow warning"><span>⚠</span><div><div class="t">At risk of delay</div><div class="d">${dl.progress_pct}% built with ${dl.months_to_rera_date} months left.</div></div></div>`;
  else if (!p.rera_possession_date) verdict = `<div class="flagrow info"><span>ℹ</span><div><div class="t">Completion date not in the register list</div><div class="d">Open the project's RERA page (button at the top) for the declared completion date and quarterly progress.</div></div></div>`;
  else verdict = `<div class="flagrow ok"><span>✓</span><div><div class="t">Looks on track</div><div class="d">${dl.months_to_rera_date ?? "—"} months to the RERA possession date.</div></div></div>`;
  return `
  <section class="card block" id="sec-delivery">
    <h2>Expected delivery</h2>
    ${verdict}
    <div class="timeline">
      <div class="fill" style="width:${pos(new Date().toISOString().slice(0, 10))}%"></div>
      ${pts.map(([k, l, v], i) => `<div class="mark ${k} ${i % 2 ? "up" : ""}" style="left:${pos(v)}%"><i></i><span>${l}<br>${date(v)}</span></div>`).join("")}
    </div>
    <div class="kpis">
      ${kpi("Construction progress", (dl.progress_pct ?? "—") + "%", `<div class="bar" style="margin-top:4px"><span style="width:${dl.progress_pct || 0}%"></span></div>`)}
      ${kpi("RERA possession date", date(p.rera_possession_date), "Legally binding")}
      ${kpi("Builder / broker claims", date(p.builder_possession_date), dl.gap_months ? `${dl.gap_months} months earlier than RERA` : "Same as RERA")}
      ${kpi("Builder's avg delay", d.builder?.avg_delay_months != null ? d.builder.avg_delay_months + " mo" : "—", "across past projects")}
    </div>
  </section>`;
}

function approvals(d) {
  const p = d.property, ap = d.approvals;
  const statusCls = (s) => "st-" + s.replace(/\s/g, "");
  return `
  <section class="card block" id="sec-rera">
    <h2>RERA registration</h2>
    <div class="table-wrap"><table class="data"><tbody>
      <tr><th style="width:38%">Status</th><td>${reraBadge(p.rera_status)}</td></tr>
      <tr><th>Registration number</th><td>${p.rera_number ? `<code>${esc(p.rera_number)}</code> <button class="btn small" data-copy="${esc(p.rera_number)}">Copy</button>` : '<span class="down">Not available</span>'}</td></tr>
      <tr><th>Authority</th><td>${esc(p.rera_authority || "")} — <a href="${esc(p.rera_url || "#")}" target="_blank" rel="noopener">search this number on the portal ↗</a></td></tr>
      <tr><th>Declared completion</th><td>${date(p.rera_possession_date, true)}</td></tr>
      <tr><th>What to check on the portal</th><td class="small">Quarterly progress reports, approved plans, number of units booked, litigation disclosed by builder, extension orders, complaints & orders against the project.</td></tr>
    </tbody></table></div>

    <h2 style="margin-top:20px">Government approvals <span class="small muted">${ap.obtained_count} confirmed · ${ap.pending_count} pending · ${ap.missing_count} missing · ${ap.unverified_count} not verified</span></h2>
    ${ap.missing_count ? `<div class="flagrow critical" style="margin-bottom:10px"><span>⛔</span><div><div class="t">Missing</div><div class="d">${esc(ap.missing.join(", "))}</div></div></div>` : ""}
    ${ap.unverified_count && !p.is_demo ? `<div class="flagrow info" style="margin-bottom:10px"><span>ℹ</span><div><div class="t">Not verified yet</div><div class="d">The RERA register lists the project but not each approval. Builders upload approval documents on the RERA portal — open it above and check them, or ask the builder for copies.</div></div></div>` : ""}
    <div class="table-wrap"><table class="data">
      <thead><tr><th></th><th>Approval</th><th>Issuing authority</th><th>Status</th><th>Reference / date</th></tr></thead>
      <tbody>${ap.items.map((a) => `<tr>
        <td><span class="status-ic ${statusCls(a.status)}">${STATUS_ICON[a.status] || "?"}</span></td>
        <td><strong>${esc(a.name)}</strong>${a.applies_when ? `<div class="small muted">Applies: ${esc(a.applies_when)}</div>` : ""}
          <details class="why"><summary>Why it matters</summary><div class="small">${esc(a.why)}</div></details></td>
        <td class="small">${esc(a.authority)}</td>
        <td><span class="badge ${a.status === "Obtained" ? "good" : a.status === "Pending" ? "warn" : a.status === "Missing" ? "bad" : ""}">${esc(STATUS_LABEL[a.status] || a.status)}</span>${a.notes ? `<div class="small muted">${esc(a.notes)}</div>` : ""}</td>
        <td class="small">${a.reference ? `<code>${esc(a.reference)}</code>` : "—"}${a.issued_on ? `<div>${date(a.issued_on, true)}</div>` : ""}${a.document_url ? `<a href="${esc(a.document_url)}" target="_blank" rel="noopener">Document ↗</a>` : ""}</td>
      </tr>`).join("")}</tbody>
    </table></div>
    <p class="small muted" style="margin-top:8px">“Not Yet Due” items are issued at completion. Ask the builder for copies of every “Obtained” document and match reference numbers with the RERA portal uploads.</p>
  </section>`;
}

function legal(d) {
  const l = d.litigation;
  return `
  <section class="card block" id="sec-legal">
    <h2>Litigation & complaints</h2>
    ${l.length
      ? `<div class="table-wrap"><table class="data"><thead><tr><th>Forum</th><th>Case</th><th>Filed</th><th>Status</th><th>Summary</th></tr></thead><tbody>${l
          .map((c) => `<tr><td>${esc(c.forum)}</td><td><code>${esc(c.case_ref || "")}</code></td><td class="nowrap">${date(c.filed_on, true)}</td>
          <td><span class="badge ${c.status === "Open" ? "bad" : "good"}">${esc(c.status)}</span></td><td>${esc(c.summary || "")}${c.url ? ` <a href="${esc(c.url)}" target="_blank" rel="noopener">↗</a>` : ""}</td></tr>`)
          .join("")}</tbody></table></div>`
      : `<div class="flagrow ok"><span>✓</span><div><div class="t">No cases recorded</div><div class="d">Also search the RERA portal's complaint section and e-Courts / e-Daakhil (consumer commission) by builder name.</div></div></div>`}
    ${d.builder ? `<p class="small muted" style="margin-top:8px">Builder-wide: ${d.builder.rera_complaints ?? "—"} RERA complaints across all projects.</p>` : ""}
  </section>`;
}

function reviews(d) {
  const r = d.reviews_summary;
  if (!r.count) return `<section class="card block" id="sec-reviews"><h2>Reviews</h2><p class="muted">No reviews collected yet. Try the forum links under “Verify live”.</p></section>`;
  const sources = [...new Set(d.reviews.map((x) => x.source))];
  return `
  <section class="card block" id="sec-reviews">
    <h2>Reviews from forums & portals <span class="small muted">${r.count} reviews · ${r.sources.length} sources</span></h2>
    <div class="cols">
      <div>
        <div class="kpis">
          ${kpi("Average rating", r.avg_rating ? r.avg_rating + " / 5" : "—", r.avg_rating ? stars(r.avg_rating) : "forums without ratings")}
          ${kpi("Sentiment", r.positive_pct + "% positive", r.negative_pct + "% negative")}
        </div>
        <div class="sentbar" style="margin:12px 0" title="positive / neutral / negative">
          <span class="p" style="width:${r.positive_pct}%"></span><span class="n" style="width:${100 - r.positive_pct - r.negative_pct}%"></span><span class="x" style="width:${r.negative_pct}%"></span>
        </div>
        <table class="data"><thead><tr><th>Source</th><th class="num">Reviews</th><th class="num">Avg ★</th></tr></thead><tbody>
          ${r.sources.map((s) => `<tr><td>${esc(s.source)}</td><td class="num">${s.count}</td><td class="num">${s.avg_rating ?? "—"}</td></tr>`).join("")}
        </tbody></table>
      </div>
      <div>
        <h3>What people talk about</h3>
        ${r.themes.map((t) => `<div style="margin-bottom:8px"><div class="row" style="justify-content:space-between"><span>${esc(t.theme)}</span>
          <span class="badge ${t.tone === "positive" ? "good" : t.tone === "negative" ? "bad" : "warn"}">${t.tone} · ${t.mentions}</span></div>
          <div class="sentbar"><span class="p" style="width:${(t.positive / t.mentions) * 100}%"></span><span class="n" style="width:${(t.neutral / t.mentions) * 100}%"></span><span class="x" style="width:${(t.negative / t.mentions) * 100}%"></span></div></div>`).join("") || '<p class="muted">Not enough text.</p>'}
      </div>
    </div>
    <div class="row" style="margin:14px 0 4px;flex-wrap:wrap">
      <select id="revSource" style="width:auto"><option value="">All sources</option>${sources.map((s) => `<option>${esc(s)}</option>`).join("")}</select>
      <div class="chips" id="revSent">${["all", "positive", "neutral", "negative"].map((s) => `<button class="chip ${s === "all" ? "on" : ""}" data-s="${s}">${s}</button>`).join("")}</div>
    </div>
    <div id="revList"></div>
  </section>`;
}

function bindReviewFilter(d) {
  const list = $("#revList");
  if (!list) return;
  let sent = "all";
  const draw = () => {
    const src = $("#revSource").value;
    const rows = d.reviews.filter((r) => (!src || r.source === src) && (sent === "all" || r.sentiment === sent));
    list.innerHTML = rows.length
      ? rows.map((r) => `<div class="review"><div class="h"><strong>${esc(r.title || "")}</strong>
          <span class="badge ${r.sentiment === "positive" ? "good" : r.sentiment === "negative" ? "bad" : ""}">${r.sentiment}</span>
          ${r.rating ? stars(r.rating) : ""}</div>
          <div>${esc(r.body || "")}</div>
          <div class="small muted">${esc(r.source)} · ${esc(r.author || "anonymous")} · ${date(r.posted_on, true)}${r.url ? ` · <a href="${esc(r.url)}" target="_blank" rel="noopener nofollow">original ↗</a>` : ""}</div></div>`).join("")
      : '<p class="muted">No reviews match.</p>';
  };
  $("#revSource").onchange = draw;
  $("#revSent").onclick = (e) => {
    const c = e.target.closest("[data-s]");
    if (!c) return;
    sent = c.dataset.s;
    $$("#revSent .chip").forEach((x) => x.classList.toggle("on", x === c));
    draw();
  };
  draw();
}

function builder(d) {
  const b = d.builder;
  if (!b) return "";
  return `
  <section class="card block" id="sec-builder">
    <h2>Builder track record <a class="btn small" href="#/builder/${b.id}">All projects by ${esc(b.name)} →</a></h2>
    <div class="kpis">
      ${kpi("Established", b.established_year || "—", b.established_year ? new Date().getFullYear() - b.established_year + " years" : "")}
      ${kpi("Projects delivered", b.projects_delivered ?? "—", `${b.projects_ongoing ?? "—"} ongoing`)}
      ${kpi("On-time delivery", b.on_time_delivery_pct != null ? Math.round(b.on_time_delivery_pct) + "%" : "—", `<div class="bar" style="margin-top:4px"><span style="width:${b.on_time_delivery_pct || 0}%"></span></div>`)}
      ${kpi("Average delay", b.avg_delay_months != null ? b.avg_delay_months + " months" : "—")}
      ${kpi("RERA complaints", b.rera_complaints ?? "—", "all projects")}
    </div>
    ${b.description ? `<p style="margin-top:10px">${esc(b.description)}</p>` : ""}
  </section>`;
}

function locationSec(d) {
  const order = ["Metro", "IT Park", "School", "Hospital", "Mall", "Railway", "Airport"];
  const near = [...d.nearby].sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category));
  return `
  <section class="card block" id="sec-location">
    <h2>Location & connectivity <a class="btn small" href="${esc(d.verify_links.map || "#")}" target="_blank" rel="noopener">Open map ↗</a></h2>
    <div class="cols">
      <div class="mini-map" id="miniMap"></div>
      ${near.length ? `<table class="data"><thead><tr><th>Nearby</th><th></th><th class="num">Distance</th></tr></thead><tbody>
        ${near.map((n) => `<tr><td class="small muted">${esc(n.category)}</td><td>${esc(n.name)}</td><td class="num">${n.distance_km} km</td></tr>`).join("")}
      </tbody></table>` : `<div class="small muted">${d.property.address ? `<p><strong>Address on the register:</strong> ${esc(d.property.address)}${d.property.pincode ? " – " + esc(d.property.pincode) : ""}</p>` : ""}<p>Nearby schools, hospitals and transit aren't recorded for this project yet. Use “Open map” to explore the area.</p></div>`}
    </div>
  </section>`;
}

function drawMiniMap(d) {
  const p = d.property;
  const el = $("#miniMap");
  if (!el || !window.L || !p.lat) {
    if (el) el.innerHTML = '<div class="empty small">Map unavailable</div>';
    return;
  }
  const map = L.map(el, { scrollWheelZoom: false }).setView([p.lat, p.lng], 14);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(map);
  L.marker([p.lat, p.lng]).addTo(map).bindPopup(esc(p.name)).openPopup();
  d.similar.filter((s) => s.lat).forEach((s) =>
    L.circleMarker([s.lat, s.lng], { radius: 6, color: "#4f46e5" }).addTo(map).bindPopup(`<a href="#/property/${s.id}">${esc(s.name)}</a><br>${psf(s.psf)}`)
  );
}

function costs(d) {
  const sc = d.state_costs;
  const underCon = d.property.status !== "Ready to Move";
  return `
  <section class="card block" id="sec-costs">
    <h2>Total cost of ownership & EMI</h2>
    <p class="small muted">The sticker price is never what you pay. Pick a configuration and adjust — rates are pre-filled for ${esc(d.property.state)} and are indicative; confirm with the sub-registrar and builder cost sheet.</p>
    <div class="calc-grid">
      <div><label class="field">Configuration</label><select id="cCfg">${d.configurations.length ? d.configurations.map((c, i) => `<option value="${i}">${esc(c.label)}${c.price_min ? " · " + inr(c.price_min) : ""}</option>`).join("") : '<option value="">Enter a price →</option>'}</select></div>
      <div><label class="field">Base price (₹)</label><input type="number" id="cBase" step="10000" /></div>
      <div><label class="field">Car parking (₹)</label><input type="number" id="cPark" value="300000" step="10000" /></div>
      <div><label class="field">Clubhouse / PLC / misc (₹)</label><input type="number" id="cMisc" value="250000" step="10000" /></div>
      <div><label class="field">Maintenance deposit (₹)</label><input type="number" id="cMaint" value="${Math.round((d.configurations[0]?.super_builtup_sqft || 1200) * 60 / 1000) * 1000}" step="1000" /></div>
      <div><label class="field">GST %</label><input type="number" id="cGst" value="${underCon ? d.gst.under_construction_pct : 0}" step="0.5" /></div>
      <div><label class="field">Stamp duty %</label><input type="number" id="cStamp" value="${sc.stamp_duty_pct ?? 6}" step="0.1" /></div>
      <div><label class="field">Registration %</label><input type="number" id="cReg" value="${sc.registration_pct ?? 1}" step="0.1" /></div>
      <div><label class="field">Legal & misc (₹)</label><input type="number" id="cLegal" value="40000" step="5000" /></div>
      <div><label class="switch" style="margin-top:22px">Woman buyer (concession) <input type="checkbox" id="cWoman"></label></div>
    </div>
    <div class="cols" style="margin-top:14px">
      <div id="costBreakdown"></div>
      <div>
        <h3>Home loan EMI</h3>
        <div class="calc-grid">
          <div><label class="field">Down payment %</label><input type="number" id="eDown" value="20" min="10" max="100" /></div>
          <div><label class="field">Interest % p.a.</label><input type="number" id="eRate" value="8.5" step="0.05" /></div>
          <div><label class="field">Tenure (years)</label><input type="number" id="eYears" value="20" min="1" max="30" /></div>
        </div>
        <div id="emiOut" style="margin-top:10px"></div>
      </div>
    </div>
  </section>`;
}

function bindCostCalc(d) {
  if (!$("#cCfg")) return;
  const sc = d.state_costs;
  const v = (id) => parseFloat($("#" + id).value) || 0;
  const setBase = () => ($("#cBase").value = d.configurations[+$("#cCfg").value]?.price_min || $("#cBase").value || 10000000);
  const calc = () => {
    const base = v("cBase");
    const woman = $("#cWoman").checked;
    const stampPct = woman && sc.stamp_duty_women_pct != null && v("cStamp") === sc.stamp_duty_pct ? sc.stamp_duty_women_pct : v("cStamp");
    const gstPct = base <= d.gst.affordable_limit && v("cGst") > 0 ? Math.min(v("cGst"), d.gst.affordable_pct) : v("cGst");
    const agreement = base + v("cPark") + v("cMisc");
    const gst = (agreement * gstPct) / 100;
    const stamp = (agreement * stampPct) / 100;
    let reg = (agreement * v("cReg")) / 100;
    if (sc.registration_cap) reg = v("cReg") ? Math.min(reg, sc.registration_cap) : sc.registration_cap;
    const total = agreement + gst + stamp + reg + v("cMaint") + v("cLegal");
    const line = (l, x, note = "") => `<div class="costline"><span>${l}${note ? ` <span class="small muted">${note}</span>` : ""}</span><span>${inr(x, { short: false })}</span></div>`;
    $("#costBreakdown").innerHTML = `<h3>Breakdown</h3>
      ${line("Base price", base)}${line("Car parking", v("cPark"))}${line("Clubhouse / PLC / misc", v("cMisc"))}
      ${line("GST", gst, gstPct + "%" + (gstPct !== v("cGst") ? " (affordable housing rate)" : ""))}
      ${line("Stamp duty", stamp, stampPct + "%")}${line("Registration", reg, sc.registration_cap ? "capped at " + inr(sc.registration_cap) : "")}
      ${line("Maintenance deposit", v("cMaint"))}${line("Legal & misc", v("cLegal"))}
      <div class="costline total"><span>All-in cost</span><span>${inr(total, { short: false })}</span></div>
      <div class="small muted">${Math.round(((total - base) / base) * 100) || 0}% above the base price</div>`;
    const loan = agreement * (1 - v("eDown") / 100);
    const m = emi(loan, v("eRate"), v("eYears"));
    const paid = m * v("eYears") * 12;
    $("#emiOut").innerHTML = `
      <div class="kpis">${kpi("Monthly EMI", inr(m, { short: false }))}${kpi("Loan amount", inr(loan))}${kpi("Total interest", inr(paid - loan))}${kpi("Cash needed upfront", inr(total - loan), "down payment + taxes + charges")}</div>
      <p class="small muted" style="margin-top:6px">Banks typically lend up to 75–90% of the agreement value (not stamp duty/registration). Keep EMI under ~40% of take-home income.</p>`;
  };
  $("#cCfg").onchange = () => (setBase(), calc());
  $("#sec-costs").addEventListener("input", calc);
  $("#cWoman").onchange = calc;
  setBase();
  calc();
}

function verify(d) {
  const v = d.verify_links;
  return `
  <section class="card block" id="sec-verify">
    <h2>Verify live at the source</h2>
    <p class="small muted">Prices and listings change daily. These open a search for this exact project on each site so you can confirm the latest quote, and the official RERA portal for the legal record.</p>
    <h3>Listing portals</h3>
    <div class="linklist">${v.portals.map((l) => `<a class="btn small" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.name)} ↗</a>`).join("")}</div>
    <h3 style="margin-top:12px">Forums & reviews</h3>
    <div class="linklist">${v.forums.map((l) => `<a class="btn small" href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.name)} ↗</a>`).join("")}</div>
    <h3 style="margin-top:12px">Official</h3>
    <div class="linklist"><a class="btn small primary" href="${esc(v.rera.url || "#")}" target="_blank" rel="noopener">${esc(v.rera.name)} ↗</a>
      ${v.map ? `<a class="btn small" href="${esc(v.map)}" target="_blank" rel="noopener">OpenStreetMap ↗</a>` : ""}</div>
  </section>`;
}

function checklist(d) {
  const uc = d.property.status !== "Ready to Move";
  const items = [
    "Match the RERA number, carpet area and possession date in the agreement with the RERA portal.",
    "Get an all-inclusive cost sheet in writing (GST, parking, PLC, clubhouse, maintenance, legal).",
    "Have a property lawyer verify title deed, mother deed chain, EC and land-use conversion.",
    "Ask for copies of plan sanction and commencement certificate; compare with the brochure.",
    uc ? "Pay only as per construction-linked stages; never more than 10% before the sale agreement (RERA Sec 13)." : "Insist on the Occupancy Certificate and completion certificate before registration.",
    uc ? "Check RERA quarterly progress photos and visit the site at least twice." : "Inspect for seepage, cracks, finishing; get a snag list fixed before possession.",
    "Check which banks have approved the project — it means their legal team vetted it.",
    "Read RERA complaints & orders against the builder; talk to residents of their earlier projects.",
    "Confirm water source (municipal vs borewell/tanker) and power connection status.",
    "Keep every payment receipt and communication; use the RERA portal for disputes.",
  ];
  return `
  <section class="card block" id="sec-checklist">
    <h2>Buyer checklist for this project</h2>
    <ol>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ol>
  </section>`;
}

function scoreCard(d) {
  const t = d.trust;
  const names = { rera: "RERA status", approvals: "Approvals", builder: "Builder record", delivery: "Delivery", reviews: "Reviews", legal: "Legal" };
  return `<div class="card panel" id="scoreCard">
    <h3>Trust score breakdown</h3>
    ${Object.entries(t.components).map(([k, v]) => `<div style="margin-bottom:8px"><div class="row" style="justify-content:space-between"><span class="small">${names[k]}</span><span class="small"><strong>${v}</strong> / ${t.max[k]}</span></div><div class="bar"><span style="width:${(v / t.max[k]) * 100}%"></span></div></div>`).join("")}
    <div class="costline total"><span>Total</span><span>${t.score} / 100 · ${t.limited ? "limited data" : t.grade}</span></div>
    ${t.limited ? `<p class="small" style="margin-top:6px"><strong>Limited data (${t.coverage_pct}%).</strong> Parts we have no information on yet (${Object.entries(t.known).filter(([, v]) => !v).map(([k]) => names[k]).join(", ")}) get a neutral middle score, so treat this number as provisional.</p>` : ""}
    <p class="small muted">A heuristic to help you prioritise due diligence — not a rating or a recommendation.</p>
  </div>`;
}
