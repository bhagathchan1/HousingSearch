// Tiny dependency-free SVG charts.
import { esc, date } from "./util.js";

/** Line chart of [{x: "YYYY-MM", y: number}] with optional horizontal reference line. */
export function lineChart(points, { refY = null, refLabel = "", height = 220, fmt = (v) => "₹" + Math.round(v).toLocaleString("en-IN") } = {}) {
  if (!points.length) return '<p class="muted">Not enough history yet.</p>';
  const W = 720, H = height, L = 64, R = 16, T = 14, B = 30;
  const ys = points.map((p) => p.y).concat(refY ? [refY] : []);
  let lo = Math.min(...ys), hi = Math.max(...ys);
  const pad = (hi - lo) * 0.12 || hi * 0.05 || 1;
  lo -= pad;
  hi += pad;
  const x = (i) => L + (points.length === 1 ? (W - L - R) / 2 : (i / (points.length - 1)) * (W - L - R));
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const ticks = 4;
  let grid = "";
  for (let i = 0; i <= ticks; i++) {
    const v = lo + ((hi - lo) * i) / ticks;
    grid += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" /><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${fmt(v)}</text>`;
  }
  const step = Math.ceil(points.length / 8);
  const xl = points
    .map((p, i) => (i % step === 0 || i === points.length - 1
        ? `<text x="${x(i)}" y="${H - 8}" text-anchor="${i === points.length - 1 && points.length > 1 ? "end" : i === 0 ? "start" : "middle"}">${esc(date(p.x))}</text>`
        : ""))
    .join("");
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ");
  const area = `${path} L${x(points.length - 1)},${H - B} L${x(0)},${H - B} Z`;
  const ref = refY
    ? `<line x1="${L}" x2="${W - R}" y1="${y(refY)}" y2="${y(refY)}" stroke="var(--accent)" stroke-dasharray="5 4" stroke-width="1.5"/>
       <text x="${W - R}" y="${y(refY) - 6}" text-anchor="end" style="fill:var(--accent)">${esc(refLabel)} ${fmt(refY)}</text>`
    : "";
  const dots = points
    .map((p, i) => `<circle cx="${x(i)}" cy="${y(p.y)}" r="3.5" fill="var(--brand)"><title>${esc(date(p.x))}: ${fmt(p.y)}</title></circle>`)
    .join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Price trend chart">
    ${grid}${xl}
    <path d="${area}" fill="var(--brand)" opacity=".08"/>
    <path d="${path}" fill="none" stroke="var(--brand)" stroke-width="2.5" stroke-linejoin="round"/>
    ${ref}${dots}
  </svg>`;
}
