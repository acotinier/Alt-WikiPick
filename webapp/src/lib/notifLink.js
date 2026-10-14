// Où mène une notification (même liste que le site, followLink de social.js). Seuls les liens connus sont suivis ; le reste n'est pas cliquable.
import { go } from './router.svelte.js';
import { ui } from './store.svelte.js';

const SITE = 'https://wiki-pick.com/';
const PAGES = { guild: '/social/guild', combat: '/social/arena', packs: '/packs', coll: '/collection', nouveautes: '/me/news', market: '/market/auctions', rewards: '/me/rewards', saison: '/me/season', trades: '/market/trades' };
const EXTERNAL = new Set(['wbc', 'support', 'post']);   // pas d'écran chez nous : on ouvre le site

const split = (link) => { const s = String(link || ''), i = s.indexOf(':'); return i < 0 ? [s, ''] : [s.slice(0, i), s.slice(i + 1)]; };

// 'page' (écran de l'appli), 'sheet' (fiche d'enchère), 'site' (wiki-pick.com) ou null
export function linkKind(link) {
  const [k, arg] = split(link);
  if (k === 'auction') return /^\d{1,12}$/.test(arg) ? 'sheet' : null;
  if (k === 'profile' || k === 'msg') return arg ? 'page' : null;
  if (PAGES[k]) return 'page';
  return EXTERNAL.has(k) ? 'site' : null;
}

export function follow(link) {
  const [k, arg] = split(link), kind = linkKind(link);
  if (kind === 'sheet') { ui.auction = +arg; return true; }
  if (kind === 'site') { window.open(SITE, '_blank', 'noopener,noreferrer'); return true; }
  if (kind !== 'page') return false;
  go(k === 'profile' ? `/player/${arg}` : k === 'msg' ? `/social/messages/${arg}` : PAGES[k]);
  return true;
}
