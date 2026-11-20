// Shared helpers: formatting, escaping, DOM, local storage.

export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** ₹ in Indian units: 1.25 Cr, 85.5 L, 9,800 */
export function inr(v, { short = true } = {}) {
  if (v == null || isNaN(v)) return "—";
  if (!short) return "₹" + Math.round(v).toLocaleString("en-IN");
  const a = Math.abs(v);
  if (a >= 1e7) return "₹" + (v / 1e7).toFixed(a >= 1e9 ? 0 : 2).replace(/\.?0+$/, "") + " Cr";
  if (a >= 1e5) return "₹" + (v / 1e5).toFixed(1).replace(/\.0$/, "") + " L";
  return "₹" + Math.round(v).toLocaleString("en-IN");
}
export const psf = (v) => (v ? "₹" + Math.round(v).toLocaleString("en-IN") + "/sq ft" : "—");
export const num = (v) => (v == null ? "—" : Number(v).toLocaleString("en-IN"));
export const pct = (v, sign = true) => (v == null ? "—" : (sign && v > 0 ? "+" : "") + v + "%");

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function date(s, withDay = false) {
  if (!s) return "—";
  const [y, m, d] = s.split("-").map(Number);
  return (withDay && d ? d + " " : "") + MONTHS[(m || 1) - 1] + " " + y;
}
export function ago(s) {
  if (!s) return "";
  const days = Math.round((Date.now() - new Date(s).getTime()) / 864e5);
  if (days < 1) return "today";
  if (days < 31) return days + "d ago";
  if (days < 365) return Math.round(days / 30) + "mo ago";
  return (days / 365).toFixed(1) + "y ago";
}
export function trendArrow(v) {
  if (v == null) return "";
  return v >= 0 ? `<span class="up">▲ ${v}%</span>` : `<span class="down">▼ ${Math.abs(v)}%</span>`;
}
export function stars(r) {
  if (r == null) return "";
  const full = Math.round(r);
  return `<span class="stars" aria-label="${r} out of 5">${"★".repeat(full)}${"☆".repeat(5 - full)}</span>`;
}
export function scoreRing(score, grade, size = "") {
  return `<div class="score ${grade} ${size}" style="--s:${score}" title="Trust score ${score}/100 (grade ${grade})"><span>${score}<small>${grade}</small></span></div>`;
}
export function reraBadge(status) {
  const cls = { Registered: "good", Applied: "warn", Lapsed: "bad", Revoked: "bad", "Not Registered": "bad" }[status] || "";
  return `<span class="badge ${cls}">RERA: ${esc(status || "Unknown")}</span>`;
}
export function statusBadge(s) {
  const cls = { "Ready to Move": "good", "Under Construction": "info", "Pre-launch": "warn" }[s] || "";
  return `<span class="badge ${cls}">${esc(s)}</span>`;
}
export function fairBadge(fp) {
  if (!fp || fp.delta_pct == null) return "";
  const cls = fp.verdict.startsWith("Below") ? "good" : fp.verdict.startsWith("Premium") ? "warn" : "";
  return `<span class="badge ${cls}" title="vs locality median ${psf(fp.locality_median_psf)}">${esc(fp.verdict)} (${pct(fp.delta_pct)})</span>`;
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 2400);
}

// localStorage wrappers that never throw (private mode, blocked storage…)
export const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem("hs:" + key);
      return v == null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem("hs:" + key, JSON.stringify(value));
    } catch {}
  },
};

export function debounce(fn, ms = 250) {
  let t;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
}

/** Monthly EMI for principal P at annual rate r% over n years. */
export function emi(P, r, years) {
  const n = years * 12;
  const m = r / 12 / 100;
  if (!P || !n) return 0;
  if (!m) return P / n;
  return (P * m * Math.pow(1 + m, n)) / (Math.pow(1 + m, n) - 1);
}
