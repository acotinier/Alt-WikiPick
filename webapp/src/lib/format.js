// Raretés, nombres, durées : les mêmes règles que l'appli de bureau.
export const RARITY_ORDER = ['EXC', 'WBC', 'SIXSEVEN', 'M', 'L', 'UR', 'SR', 'R', 'PC', 'C'];
const TOP = new Set(['EXC', 'WBC', 'SIXSEVEN', 'M', 'L', 'UR']); // les raretés qui méritent des effets
export const EXCLUSIVE = ['EXC', 'WBC', 'SIXSEVEN'];           // ni vendues, ni recyclées, ni échangées

export const rarityRank = (r) => { const i = RARITY_ORDER.indexOf(r); return i < 0 ? 99 : i; };
export const color = (r) => `var(--r-${RARITY_ORDER.includes(r) ? r : 'C'})`;
export const isTop = (c) => TOP.has(c.rarity) || !!c.shiny;

export const fmt = (n) => Number(n || 0).toLocaleString('fr-FR').replace(/ /g, ' ');
export const compact = (n) => Number(n || 0).toLocaleString('fr-FR', { notation: 'compact' });
export const plural = (n, one, many = one + 's') => `${n} ${n > 1 ? many : one}`;

export function clock(s) {
  s = Math.max(0, Math.floor(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h} h ${String(m).padStart(2, '0')}` : `${m}:${String(s % 60).padStart(2, '0')}`;
}

export function ago(ts, now = Date.now() / 1000) {
  if (!ts) return '';
  const s = Math.max(1, Math.floor(now - ts));
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
  return `il y a ${Math.floor(s / 86400)} j`;
}

export function duration(s) {
  s = Math.max(0, s | 0);
  const j = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return j ? `${j} j ${h} h` : h ? `${h} h ${m} min` : `${Math.max(1, m)} min`;
}

// Les vignettes Wikimedia existent en tailles fixes : une grille mobile n'a pas besoin de 330 px par carte.
export function thumb(url, width) {
  if (!url) return url;
  return url.replace(/\/(\d+)px-/, (m, w) => (+w > width ? `/${width}px-` : m));
}

export const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
export const same = (a, b) => String(a || '').toLowerCase() === String(b || '').toLowerCase();

// Adresse Wikipédia d'une carte (pour celles qui n'en ont pas : marché, échanges).
export function wikiUrl(cid) {
  const i = String(cid).indexOf(':'), lang = String(cid).slice(0, i), title = String(cid).slice(i + 1);
  if (i < 1 || !title || !/^[a-z-]{2,12}$/.test(lang)) return null;
  return `https://${lang}.wikipedia.org/wiki/` + encodeURIComponent(title.replace(/ /g, '_')).replace(/%(2C|3A|28|29|2F)/g, (m) => decodeURIComponent(m));
}
