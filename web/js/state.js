// Per-browser state: chosen city, shortlist (with the price when saved), compare list, notes.
import { store, $, toast } from "./util.js";

const listeners = new Set();
export const onChange = (fn) => listeners.add(fn);
const emit = () => listeners.forEach((fn) => fn());

export const state = {
  get city() {
    return store.get("city", "Bengaluru");
  },
  set city(c) {
    store.set("city", c);
  },

  // shortlist: { [id]: { savedOn, priceMin, psf, name } }
  shortlist() {
    return store.get("shortlist", {});
  },
  isShortlisted(id) {
    return !!this.shortlist()[id];
  },
  toggleShortlist(p) {
    const s = this.shortlist();
    if (s[p.id]) {
      delete s[p.id];
      toast("Removed from shortlist");
    } else {
      s[p.id] = { savedOn: new Date().toISOString().slice(0, 10), priceMin: p.price_min, psf: p.psf, name: p.name };
      toast("Saved to shortlist — we'll show price changes since today");
    }
    store.set("shortlist", s);
    emit();
  },

  compare() {
    return store.get("compare", []);
  },
  inCompare(id) {
    return this.compare().includes(id);
  },
  toggleCompare(id) {
    let c = this.compare();
    if (c.includes(id)) c = c.filter((x) => x !== id);
    else if (c.length >= 4) {
      toast("You can compare up to 4 projects");
      return;
    } else c.push(id);
    store.set("compare", c);
    emit();
  },
  clearCompare() {
    store.set("compare", []);
    emit();
  },

  note(id) {
    return store.get("notes", {})[id] || "";
  },
  setNote(id, text) {
    const n = store.get("notes", {});
    if (text) n[id] = text;
    else delete n[id];
    store.set("notes", n);
  },
};

export function renderCounts() {
  const s = Object.keys(state.shortlist()).length;
  const c = state.compare().length;
  $("#shortlistCount").textContent = s || "";
  $("#compareCount").textContent = c || "";
}
onChange(renderCounts);
