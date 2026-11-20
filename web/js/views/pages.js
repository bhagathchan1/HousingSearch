// Secondary pages: compare, shortlist, localities, builder, calculators, guide, about.
import { api } from "../api.js";
import { $, $$, esc, inr, psf, num, pct, date, trendArrow, stars, scoreRing, reraBadge, statusBadge, emi, toast, priceRange } from "../util.js";
import { state, onChange } from "../state.js";
import { cardHtml, bindCardActions } from "./explore.js";

// ------------------------------------------------------------------ compare
export async function renderCompare(main, meta, query = {}) {
  // A shared link (#/compare?ids=1,2,3) replaces this browser's compare list.
  if (query.ids) {
    state.clearCompare();
    query.ids.split(",").filter((x) => /^\d+$/.test(x)).slice(0, 4).forEach((x) => state.toggleCompare(+x));
    history.replaceState(null, "", "#/compare");
  }
  const ids = state.compare();
  if (!ids.length) {
    main.innerHTML = `<div class="empty card"><h2>Nothing to compare yet</h2><p>Use the ⇄ button on any project card or page to add up to 4 projects.</p><a class="btn primary" href="#/">Browse projects</a></div>`;
    return;
  }
  const list = await api.compare(ids.join(","));
  const rows = [
    ["Builder", (d) => esc(d.builder?.name || "—")],
    ["Locality", (d) => esc(`${d.property.locality}, ${d.property.city}`)],
    ["Trust score", (d) => `${d.trust.score} (${d.trust.limited ? "limited data" : d.trust.grade})`, (d) => d.trust.score, "max"],
    ["Status", (d) => statusBadge(d.property.status)],
    ["RERA", (d) => reraBadge(d.property.rera_status)],
    ["Price range", (d) => priceRange(d.summary.price_min, d.summary.price_max), (d) => d.summary.price_min, "min"],
    ["Median ₹/sq ft", (d) => psf(d.prices.psf_median), (d) => d.prices.psf_median, "min"],
    ["vs locality", (d) => (d.fair_price.delta_pct != null ? pct(d.fair_price.delta_pct) : "—"), (d) => d.fair_price.delta_pct, "min"],
    ["12-month change", (d) => trendArrow(d.prices.change_12m_pct) || "—", (d) => d.prices.change_12m_pct, "max"],
    ["Cheapest source", (d) => esc(d.prices.cheapest_source || "—")],
    ["Configurations", (d) => esc(d.configurations.map((c) => c.label).join(", "))],
    ["Carpet sizes", (d) => d.configurations.map((c) => `${c.label}: ${num(c.carpet_sqft)}`).join("<br>")],
    ["Possession (RERA)", (d) => (d.property.status === "Ready to Move" ? "Ready" : date(d.property.rera_possession_date)), (d) => d.property.rera_possession_date, "min"],
    ["Construction progress", (d) => (d.property.construction_progress ?? "—") + "%", (d) => d.property.construction_progress, "max"],
    ["Overdue", (d) => (d.delivery.overdue_months ? `<span class="down">${d.delivery.overdue_months} months</span>` : "No")],
    ["Units available", (d) => `${num(d.property.available_units)} / ${num(d.property.total_units)}`],
    ["Approvals complete", (d) => (d.approvals.completeness_pct ?? "—") + "%", (d) => d.approvals.completeness_pct, "max"],
    ["Missing approvals", (d) => esc(d.approvals.missing.join(", ") || "None"), (d) => d.approvals.missing_count, "min"],
    ["Open cases", (d) => d.litigation.filter((l) => l.status === "Open").length, (d) => d.litigation.filter((l) => l.status === "Open").length, "min"],
    ["Builder on-time %", (d) => (d.builder?.on_time_delivery_pct != null ? Math.round(d.builder.on_time_delivery_pct) + "%" : "—"), (d) => d.builder?.on_time_delivery_pct, "max"],
    ["Review rating", (d) => (d.reviews_summary.avg_rating ? stars(d.reviews_summary.avg_rating) + " " + d.reviews_summary.avg_rating : "—"), (d) => d.reviews_summary.avg_rating, "max"],
    ["Positive reviews", (d) => (d.reviews_summary.count ? d.reviews_summary.positive_pct + "%" : "—"), (d) => d.reviews_summary.positive_pct, "max"],
    ["Land / open space", (d) => `${d.property.land_area_acres ?? "—"} ac · ${d.property.open_space_pct ?? "—"}%`, (d) => d.property.open_space_pct, "max"],
    ["Metro distance", (d) => { const m = d.nearby.find((n) => n.category === "Metro"); return m ? m.distance_km + " km" : "—"; }, (d) => d.nearby.find((n) => n.category === "Metro")?.distance_km, "min"],
    ["Airport distance", (d) => { const m = d.nearby.find((n) => n.category === "Airport"); return m ? m.distance_km + " km" : "—"; }],
    ["Amenities", (d) => (d.property.amenities || []).length, (d) => (d.property.amenities || []).length, "max"],
    ["Bank approvals", (d) => esc((d.property.bank_approvals || []).join(", ") || "None")],
    ["Red flags", (d) => d.red_flags.filter((f) => f.level !== "info").map((f) => `• ${esc(f.title)}`).join("<br>") || "None", (d) => d.red_flags.filter((f) => f.level !== "info").length, "min"],
  ];
  const best = (getter, dir) => {
    if (!getter || list.length < 2) return null;
    const vals = list.map(getter).filter((v) => v != null);
    if (!vals.length) return null;
    return dir === "max" ? Math.max(...vals.map(Number)) : dir === "min" ? (typeof vals[0] === "string" ? vals.sort()[0] : Math.min(...vals)) : null;
  };
  main.innerHTML = `
    <div class="results-head"><h1>Compare ${list.length} projects</h1>
      <div class="row"><span class="small muted">Green = best in row</span><button class="btn" id="cmpShare">🔗 Share</button><button class="btn" id="cmpClear">Clear all</button></div></div>
    <div class="table-wrap card"><table class="data compare-table">
      <thead><tr><th></th>${list.map((d) => `<th style="text-transform:none;font-size:.95rem;color:var(--text)">
        <a href="#/property/${d.property.id}">${esc(d.property.name)}</a>
        <div><button class="btn small" data-rm="${d.property.id}">Remove</button></div></th>`).join("")}</tr></thead>
      <tbody>${rows.map(([label, fn, getter, dir]) => {
        const b = best(getter, dir);
        return `<tr><td>${label}</td>${list.map((d) => `<td class="${b != null && getter(d) == b ? "best" : ""}">${fn(d)}</td>`).join("")}</tr>`;
      }).join("")}</tbody>
    </table></div>`;
  $("#cmpClear").onclick = () => (state.clearCompare(), renderCompare(main, meta));
  $("#cmpShare").onclick = async () => {
    const url = location.origin + location.pathname + "#/compare?ids=" + ids.join(",");
    try {
      await navigator.clipboard.writeText(url);
      toast("Comparison link copied");
    } catch {
      toast(url);
    }
  };
  main.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => (state.toggleCompare(+b.dataset.rm), renderCompare(main, meta))));
}

// ---------------------------------------------------------------- shortlist
export async function renderShortlist(main) {
  const sl = state.shortlist();
  const ids = Object.keys(sl);
  if (!ids.length) {
    main.innerHTML = `<div class="empty card"><h2>Your shortlist is empty</h2><p>Tap ♡ on a project. We remember the price on the day you saved it and show how it has moved since — a simple price tracker.</p><a class="btn primary" href="#/">Browse projects</a></div>`;
    return;
  }
  const details = (await Promise.all(ids.map((id) => api.property(id).catch(() => null)))).filter(Boolean);
  const rows = details.map((d) => {
    const saved = sl[d.property.id];
    const now = d.summary.psf;
    const change = saved.psf && now ? Math.round(((now - saved.psf) / saved.psf) * 1000) / 10 : null;
    return { d, saved, now, change };
  });
  main.innerHTML = `
    <div class="results-head"><div><h1>My shortlist (${rows.length})</h1><div class="small muted">Stored in this browser. Price change is measured from the day you saved each project.</div></div>
      <div class="row"><button class="btn" id="slCompare">⇄ Compare top 4</button><button class="btn" id="slExport">⬇ Export</button></div></div>
    <div class="table-wrap card"><table class="data">
      <thead><tr><th>Project</th><th>Saved on</th><th class="num">₹/sq ft then</th><th class="num">₹/sq ft now</th><th class="num">Change</th><th>Possession</th><th class="num">Trust</th><th>Top concern</th><th>Notes</th><th></th></tr></thead>
      <tbody>${rows.map(({ d, saved, now, change }) => `<tr>
        <td><a href="#/property/${d.property.id}"><strong>${esc(d.property.name)}</strong></a><div class="small muted">${esc(d.property.locality)}, ${esc(d.property.city)}</div></td>
        <td class="nowrap">${date(saved.savedOn, true)}</td>
        <td class="num">${psf(saved.psf)}</td><td class="num">${psf(now)}</td>
        <td class="num">${change == null ? "—" : change === 0 ? "no change" : trendArrow(change)}</td>
        <td>${d.property.status === "Ready to Move" ? "Ready" : date(d.property.rera_possession_date)}</td>
        <td class="num">${d.trust.score}</td>
        <td class="small">${esc(d.red_flags.find((f) => f.level !== "info")?.title || "—")}</td>
        <td class="small">${esc(state.note(d.property.id)).slice(0, 80)}</td>
        <td><button class="btn small" data-rm="${d.property.id}">Remove</button></td></tr>`).join("")}</tbody>
    </table></div>`;
  main.querySelectorAll("[data-rm]").forEach((b) =>
    (b.onclick = () => {
      const d = details.find((x) => x.property.id === +b.dataset.rm);
      state.toggleShortlist(d.summary);
      renderShortlist(main);
    }));
  $("#slCompare").onclick = () => {
    state.clearCompare();
    rows.slice(0, 4).forEach((r) => state.toggleCompare(r.d.property.id));
    location.hash = "#/compare";
  };
  $("#slExport").onclick = () => {
    const csv = [["name", "locality", "city", "saved_on", "psf_then", "psf_now", "change_pct", "possession", "trust", "notes"]]
      .concat(rows.map(({ d, saved, now, change }) => [d.property.name, d.property.locality, d.property.city, saved.savedOn, saved.psf, now, change, d.property.rera_possession_date, d.trust.score, state.note(d.property.id)]))
      .map((r) => r.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "housingsearch-shortlist.csv";
    a.click();
  };
}

// --------------------------------------------------------------- localities
export async function renderLocalities(main, meta) {
  const city = state.city;
  const rows = await api.localities(city);
  let sortKey = "median_psf", dir = -1;
  const cols = [
    ["locality", "Locality"], ["projects", "Projects", 1], ["median_psf", "Median ₹/sq ft", 1], ["min_psf", "Lowest", 1],
    ["max_psf", "Highest", 1], ["avg_change_12m", "12m change", 1], ["ready_to_move", "Ready to move", 1], ["avg_trust", "Avg trust", 1],
  ];
  const maxPsf = Math.max(...rows.map((r) => r.max_psf || 0));
  const draw = () => {
    const sorted = [...rows].sort((a, b) => (a[sortKey] > b[sortKey] ? 1 : a[sortKey] < b[sortKey] ? -1 : 0) * dir);
    $("#locTable").innerHTML = `<thead><tr>${cols.map(([k, l, n]) => `<th class="sortable ${n ? "num" : ""}" data-k="${k}">${l}${sortKey === k ? (dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}<th>Price band</th></tr></thead>
      <tbody>${sorted.map((r) => `<tr>
        <td><a href="#/?locality=${encodeURIComponent(r.locality)}"><strong>${esc(r.locality)}</strong></a></td>
        <td class="num">${r.projects}</td><td class="num"><strong>${psf(r.median_psf)}</strong></td><td class="num">${psf(r.min_psf)}</td><td class="num">${psf(r.max_psf)}</td>
        <td class="num">${trendArrow(r.avg_change_12m) || "—"}</td><td class="num">${r.ready_to_move}</td><td class="num">${r.avg_trust}</td>
        <td style="min-width:160px"><div class="bar" style="position:relative"><span style="position:absolute;left:${((r.min_psf || 0) / maxPsf) * 100}%;width:${(((r.max_psf || 0) - (r.min_psf || 0)) / maxPsf) * 100}%"></span></div></td>
      </tr>`).join("")}</tbody>`;
    $$("#locTable th[data-k]").forEach((th) => (th.onclick = () => {
      dir = sortKey === th.dataset.k ? -dir : -1;
      sortKey = th.dataset.k;
      draw();
    }));
  };
  main.innerHTML = `
    <div class="results-head"><div><h1>Locality price guide · ${esc(city)}</h1>
      <div class="small muted">Median of each project's latest quotes across sources. Click a locality to see its projects. Change the city at the top.</div></div></div>
    <div class="table-wrap card"><table class="data" id="locTable"></table></div>`;
  draw();
}

// ------------------------------------------------------------------ builder
export async function renderBuilder(main, meta, id) {
  const { builder: b, projects } = await api.builder(id);
  main.innerHTML = `
    <nav class="crumbs"><a href="#/">Explore</a> › Builders › ${esc(b.name)}</nav>
    <div class="card panel">
      <h1>${esc(b.name)}</h1>
      <p class="muted">${esc(b.description || "")}</p>
      <div class="kpis">
        <div class="kpi"><div class="label">Established</div><div class="value">${b.established_year || "—"}</div></div>
        <div class="kpi"><div class="label">Delivered</div><div class="value">${b.projects_delivered ?? "—"}</div></div>
        <div class="kpi"><div class="label">Ongoing</div><div class="value">${b.projects_ongoing ?? "—"}</div></div>
        <div class="kpi"><div class="label">On-time</div><div class="value">${b.on_time_delivery_pct != null ? Math.round(b.on_time_delivery_pct) + "%" : "—"}</div></div>
        <div class="kpi"><div class="label">Avg delay</div><div class="value">${b.avg_delay_months ?? "—"} mo</div></div>
        <div class="kpi"><div class="label">RERA complaints</div><div class="value">${b.rera_complaints ?? "—"}</div></div>
      </div>
    </div>
    <h2 style="margin:18px 0 10px">${projects.length} projects in HousingSearch</h2>
    <div class="results" id="bResults">${projects.map(cardHtml).join("")}</div>`;
  bindCardActions($("#bResults"), projects);
  onChange(() => $("#bResults") && ($("#bResults").innerHTML = projects.map(cardHtml).join("")));
}

// -------------------------------------------------------------------- tools
export async function renderTools(main, meta) {
  const states = meta.states;
  main.innerHTML = `
  <h1>Calculators</h1>
  <div class="cols">
    <div class="card panel">
      <h2>Home loan EMI</h2>
      <div class="calc-grid">
        <div><label class="field">Loan amount (₹)</label><input type="number" id="tLoan" value="8000000" step="100000"></div>
        <div><label class="field">Interest % p.a.</label><input type="number" id="tRate" value="8.5" step="0.05"></div>
        <div><label class="field">Tenure (years)</label><input type="number" id="tYears" value="20"></div>
      </div>
      <div id="tEmi" style="margin-top:12px"></div>
    </div>
    <div class="card panel">
      <h2>How much can I afford?</h2>
      <div class="calc-grid">
        <div><label class="field">Monthly take-home (₹)</label><input type="number" id="aIncome" value="200000" step="5000"></div>
        <div><label class="field">Existing EMIs (₹/month)</label><input type="number" id="aEmis" value="0" step="1000"></div>
        <div><label class="field">Savings for down payment (₹)</label><input type="number" id="aSave" value="2500000" step="100000"></div>
        <div><label class="field">Max EMI as % of income</label><input type="number" id="aPct" value="40"></div>
        <div><label class="field">Interest % p.a.</label><input type="number" id="aRate" value="8.5" step="0.05"></div>
        <div><label class="field">Tenure (years)</label><input type="number" id="aYears" value="20"></div>
      </div>
      <div id="aOut" style="margin-top:12px"></div>
    </div>
    <div class="card panel">
      <h2>Rent vs buy (simple)</h2>
      <div class="calc-grid">
        <div><label class="field">Property price (₹)</label><input type="number" id="rPrice" value="10000000" step="100000"></div>
        <div><label class="field">Monthly rent for similar home (₹)</label><input type="number" id="rRent" value="30000" step="1000"></div>
        <div><label class="field">Years</label><input type="number" id="rYears" value="10"></div>
        <div><label class="field">Price appreciation % p.a.</label><input type="number" id="rApp" value="5" step="0.5"></div>
        <div><label class="field">Rent increase % p.a.</label><input type="number" id="rRentInc" value="6" step="0.5"></div>
        <div><label class="field">Investment return % p.a.</label><input type="number" id="rInv" value="10" step="0.5"></div>
      </div>
      <div id="rOut" style="margin-top:12px"></div>
    </div>
    <div class="card panel">
      <h2>Stamp duty & registration by state</h2>
      <p class="small muted">Indicative defaults used in the project cost calculator. Rates change — confirm with the sub-registrar.</p>
      <table class="data"><thead><tr><th>State</th><th class="num">Stamp duty</th><th class="num">Women</th><th class="num">Registration</th></tr></thead><tbody>
      ${Object.entries(states).map(([s, v]) => `<tr><td>${esc(s)}<div class="small"><a href="${esc(v.rera_url)}" target="_blank" rel="noopener">${esc(v.rera_name)} ↗</a></div></td><td class="num">${v.stamp_duty_pct}%</td><td class="num">${v.stamp_duty_women_pct}%</td><td class="num">${v.registration_pct}%${v.registration_cap ? `<div class="small muted">cap ${inr(v.registration_cap)}</div>` : ""}</td></tr>`).join("")}
      </tbody></table>
    </div>
  </div>`;
  const v = (id) => parseFloat($("#" + id).value) || 0;
  const k = (l, val, sub = "") => `<div class="kpi"><div class="label">${l}</div><div class="value">${val}</div><div class="sub">${sub}</div></div>`;
  const calc = () => {
    const m = emi(v("tLoan"), v("tRate"), v("tYears"));
    const total = m * v("tYears") * 12;
    $("#tEmi").innerHTML = `<div class="kpis">${k("Monthly EMI", inr(m, { short: false }))}${k("Total interest", inr(total - v("tLoan")))}${k("Total paid", inr(total))}</div>`;

    const maxEmi = Math.max(0, (v("aIncome") * v("aPct")) / 100 - v("aEmis"));
    const r = v("aRate") / 1200, n = v("aYears") * 12;
    const loan = r ? (maxEmi * (Math.pow(1 + r, n) - 1)) / (r * Math.pow(1 + r, n)) : maxEmi * n;
    const budget = Math.min(loan / 0.8, loan + v("aSave") * 0.88); // ~12% of savings reserved for taxes & charges
    $("#aOut").innerHTML = `<div class="kpis">${k("Max EMI", inr(maxEmi, { short: false }))}${k("Max loan", inr(loan))}${k("Property budget", inr(budget), "after stamp duty, GST & charges")}</div>
      <a class="btn small" style="margin-top:8px" href="#/?max_price=${Math.round(budget)}">See projects within ${inr(budget)} →</a>`;

    // Both people spend the same each month: the buyer pays the EMI, the renter pays rent
    // and invests the difference (and the down payment + upfront costs on day one).
    const price = v("rPrice"), yrs = v("rYears");
    const down = price * 0.2, upfront = price * 0.1, loanR = price * 0.8, mr = 8.5 / 1200;
    const e = emi(loanR, 8.5, 20);
    let invest = down + upfront, rentM = v("rRent"), outstanding = loanR;
    for (let m = 0; m < yrs * 12; m++) {
      const pay = m < 240 ? e : 0;
      if (m < 240) outstanding = outstanding * (1 + mr) - e;
      invest = invest * (1 + v("rInv") / 1200) + (pay - rentM);
      if ((m + 1) % 12 === 0) rentM *= 1 + v("rRentInc") / 100;
    }
    const buyWealth = price * Math.pow(1 + v("rApp") / 100, yrs) - Math.max(outstanding, 0);
    $("#rOut").innerHTML = `<div class="kpis">${k("Buyer's wealth", inr(buyWealth), "home value − loan still owed")}${k("Renter's wealth", inr(invest), "investments built from the same monthly budget")}</div>
      <p class="small muted" style="margin-top:6px">${buyWealth > invest ? "Buying comes out ahead" : "Renting comes out ahead"} after ${yrs} years, assuming 20% down, 10% upfront costs and an 8.5% 20-year loan. Rough guide only.</p>`;
  };
  main.addEventListener("input", calc);
  calc();
}

// -------------------------------------------------------------------- guide
export async function renderGuide(main, meta) {
  main.innerHTML = `
  <div class="prose">
    <h1>Buyer's guide: what to check before you buy</h1>
    <p class="muted">A plain-language companion to the checks HousingSearch runs on every project.</p>

    <h2>1. RERA — your strongest protection</h2>
    <ul>
      <li>Every project above 500 sq m or 8 units must be registered with the state RERA <em>before</em> it is advertised or sold.</li>
      <li>The <strong>RERA possession date</strong> is legally binding; brochures often show an earlier date. Plan around the RERA date.</li>
      <li>Builders must keep 70% of buyer money in a project escrow account and can only withdraw it in proportion to construction progress.</li>
      <li>Sales are by <strong>carpet area</strong>. You cannot be asked for more than 10% before a registered agreement for sale.</li>
      <li>On delay you can claim interest for every month, or withdraw with a full refund plus interest (Section 18).</li>
    </ul>

    <h2>2. Government approvals, stage by stage</h2>
    <div class="table-wrap"><table class="data"><thead><tr><th>Approval</th><th>When</th><th>Why it matters</th></tr></thead><tbody>
      ${meta.approvals_catalog.map((a) => `<tr><td><strong>${esc(a.name)}</strong>${a.applies_when ? `<div class="small muted">${esc(a.applies_when)}</div>` : ""}</td><td class="nowrap">${{ pre_launch: "Before launch", construction: "During construction", completion: "At completion" }[a.stage]}</td><td class="small">${esc(a.why)}</td></tr>`).join("")}
    </tbody></table></div>

    <h2>3. Reading prices correctly</h2>
    <ul>
      <li>Portal prices are usually <em>asking</em> prices. Brokers and builder sales teams often quote different numbers for the same unit — HousingSearch shows them side by side with dates so you can negotiate.</li>
      <li>Compare <strong>effective carpet-area rate</strong> (price ÷ carpet area), not the super built-up rate. Loading above 30–35% is high.</li>
      <li>Add GST (5% under construction, 1% affordable housing, 0% for ready-to-move with OC), stamp duty, registration, parking, clubhouse, PLC and maintenance deposits. Use the cost calculator on each project page.</li>
    </ul>

    <h2>4. Red flags to walk away from</h2>
    <ul>
      <li>No RERA registration, or registration lapsed without an extension order.</li>
      <li>“Pre-launch” offers asking for money before RERA registration.</li>
      <li>Land still classified as agricultural / no conversion order.</li>
      <li>Ready-to-move without an Occupancy Certificate.</li>
      <li>Large gap between the builder's promised date and the RERA date, or slow construction progress.</li>
      <li>Many open RERA / consumer-court cases, or a builder with a poor on-time record.</li>
      <li>No major bank has approved the project for home loans.</li>
    </ul>

    <h2>5. How the trust score works</h2>
    <p>0–100, made of: RERA status (25), approvals completeness (25), builder on-time record (20), delivery status (15), review sentiment (10), open legal cases (5). Grades: A ≥ 85, B ≥ 70, C ≥ 55, D below. It is a triage aid for your own due diligence, not a rating.</p>

    <h2>6. Official portals</h2>
    <ul>${Object.entries(meta.states).map(([s, v]) => `<li>${esc(s)}: <a href="${esc(v.rera_url)}" target="_blank" rel="noopener">${esc(v.rera_name)}</a></li>`).join("")}</ul>
  </div>`;
}

// -------------------------------------------------------------------- about
export async function renderAbout(main, meta) {
  main.innerHTML = `
  <div class="prose">
    <h1>Data & sources</h1>
    ${meta.has_real_data ? `<div class="flagrow ok"><span>✓</span><div><div class="t">Projects come from official state RERA registers</div><div class="d">${meta.sources.map((x) => `${esc(x.authority)}: ${x.count.toLocaleString("en-IN")}`).join(" · ")}. Each project links back to its register entry. Registers list the project, builder, RERA number and dates; prices, reviews and most approvals are not part of them, so those show as “not published” / “not verified” until added.</div></div></div>
    <h2>Cities not covered yet</h2>
    <ul>
      <li><strong>Hyderabad (Telangana):</strong> TG RERA's project search is protected by a CAPTCHA, so it isn't queried automatically. Search pages you save from the TG RERA site can be imported (<code>import-rera tg --from-file</code>), and an RTI request for the full list is drafted in the repository (docs/RTI_TG_RERA.md).</li>
      <li><strong>Noida (Uttar Pradesh):</strong> the UP RERA portal was down for maintenance when the importers were built.</li>
    </ul>` : ""}
    ${meta.has_demo_data ? `<div class="flagrow warning"><span>⚠</span><div><div class="t">This instance is running on synthetic demo data</div><div class="d">All builders, projects, RERA numbers (prefixed DEMO-), prices, reviews and cases are generated so every feature can be explored. Localities, airports, state rules and RERA portal links are real.</div></div></div>` : ""}
    <h2>What is collected for every project</h2>
    <ul>
      <li><strong>Price quotes</strong> — source, configuration, price, ₹/sq ft, date seen, and the link where it was quoted. Kept as history, so trends and spreads across sources are computed.</li>
      <li><strong>Configurations</strong> — carpet & super built-up area, price band, units total / available, facing.</li>
      <li><strong>RERA</strong> — registration number, status, authority, declared completion date, construction progress.</li>
      <li><strong>Approvals</strong> — ${meta.approvals_catalog.length} approvals tracked with authority, status, reference and date.</li>
      <li><strong>Reviews</strong> — from forums and portals with source and link; sentiment and themes are computed.</li>
      <li><strong>Litigation</strong>, <strong>builder track record</strong>, <strong>nearby infrastructure</strong>, bank approvals.</li>
    </ul>
    <h2>Getting real data in</h2>
    <p>Listing portals such as Housing.com and 99acres do not allow automated scraping in their terms of use, so HousingSearch does not crawl them. Instead:</p>
    <ol>
      <li><strong>Import JSON</strong> records (from a data partner, your own research, or RERA data you've downloaded): <code>python -m housingsearch import-json my_projects.json</code></li>
      <li><strong>Track quotes in a CSV</strong> as you collect them from portals, brokers and builders: <code>python -m housingsearch import-quotes quotes.csv</code></li>
      <li><strong>Import one page by URL</strong> — reads schema.org data from a builder/listing page if its robots.txt allows: <code>python -m housingsearch import-url URL --city Pune</code></li>
      <li><strong>Use the API</strong>: <code>POST /api/admin/import</code> with an admin token, for scheduled feeds.</li>
    </ol>
    <p>Each project also links to a live search on every major portal, forum and the official RERA site so you can confirm the latest numbers in one click.</p>
    <h2>Coverage</h2>
    <table class="data"><thead><tr><th>City</th><th>State</th><th class="num">Projects</th><th class="num">Localities</th></tr></thead><tbody>
      ${meta.cities.map((c) => `<tr><td>${esc(c.city)}</td><td>${esc(c.state)}</td><td class="num">${c.count}</td><td class="num">${c.localities.length}</td></tr>`).join("")}
    </tbody></table>
    <p class="small muted" style="margin-top:12px">Total ${meta.total_properties} projects · ${meta.builders.length} builders · latest price ${date(meta.last_price_update, true)}. Full docs and the API reference are in the <a href="https://github.com/bhagathchan1/HousingSearch" target="_blank" rel="noopener">GitHub repository</a> and at <a href="/docs" target="_blank">/docs</a>.</p>
  </div>`;
}
