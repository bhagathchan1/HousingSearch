// Thin client for the HousingSearch JSON API.

async function get(path, params) {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length))
          .map(([k, v]) => [k, Array.isArray(v) ? v.join(",") : String(v)])
      )
    : "";
  const res = await fetch("/api" + path + qs);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

const cache = new Map();
async function cached(key, fn) {
  if (!cache.has(key)) cache.set(key, fn().catch((e) => (cache.delete(key), Promise.reject(e))));
  return cache.get(key);
}

export const api = {
  meta: () => cached("meta", () => get("/meta")),
  search: (params) => get("/properties", params),
  property: (id) => cached("p" + id, () => get("/properties/" + id)),
  suggest: (q, city) => get("/suggest", { q, city }),
  compare: (ids) => get("/compare", { ids }),
  localities: (city) => cached("loc" + city, () => get("/localities/" + encodeURIComponent(city))),
  builder: (id) => cached("b" + id, () => get("/builders/" + id)),
  exportUrl: (params) =>
    "/api/properties/export.csv?" +
    new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null && !(Array.isArray(v) && !v.length))
      .map(([k, v]) => [k, Array.isArray(v) ? v.join(",") : String(v)])),
};
