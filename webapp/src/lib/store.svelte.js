// État global de l'appli : qui est connecté, son profil, sa collection, les notifications et le temps réel.
import { auth, call, connectEvents, setExpiredHandler } from './api.js';
import { debounce } from './format.js';
import { idbClear, idbGet, idbSet } from './idb.js';

export const app = $state({
  phase: 'boot',       // boot | login | app
  name: null, me: null, names: {}, info: {}, rewards: null,
  live: 'down',        // état de la connexion temps réel : live | down
  meAt: 0,             // quand le profil a été lu (pour le compte à rebours des paquets)
  skew: 0,             // écart d'horloge avec le serveur (les fins d'enchère sont dans son référentiel)
});

// Les cartes sont des milliers d'objets qu'on ne modifie jamais sur place : $state.raw évite d'en faire des proxys.
class Collection {
  cards = $state.raw([]);
  tags = $state.raw([]);
  rank = $state.raw({});
  stats = $state.raw(null);
  loaded = $state(false);
  loading = $state(false);
  byCid = $derived(new Map(this.cards.map((c) => [c.cid, c])));
}
export const coll = new Collection();

// Ce qui est ouvert par-dessus l'écran courant : la fiche d'une carte, les notifications, le menu du compte.
export const ui = $state({ card: null, bell: false, menu: false, trade: null });
export const openCard = (c) => { ui.card = c; };
export const openTrade = (to, counterOf = null, note = '') => { ui.trade = { to, counterOf, note }; };

// Cartes surveillées (liste locale à l'instance) : une alerte quand l'une d'elles est mise aux enchères.
export const watch = $state({ list: [] });
export async function loadWatch() { const r = await call('watch_get'); if (r && r.ok) watch.list = r.list; }

export const toasts = $state([]);
let toastId = 0;
export function toast(msg, kind = 'info', ms = 4500) {
  const id = ++toastId;
  toasts.push({ id, msg, kind });
  if (toasts.length > 3) toasts.shift();
  setTimeout(() => { const i = toasts.findIndex((t) => t.id === id); if (i >= 0) toasts.splice(i, 1); }, ms);
}

// ---- petits bus d'événements : les écrans s'abonnent à ce qui les concerne ----
const listeners = new Map();
export function on(type, fn) {
  if (!listeners.has(type)) listeners.set(type, new Set());
  listeners.get(type).add(fn);
  return () => listeners.get(type).delete(fn);
}
const emit = (type, data) => (listeners.get(type) || []).forEach((fn) => { try { fn(data); } catch (e) { console.error(e); } });

// ---- une seule action qui écrit à la fois, comme sur le bureau ----
export const busy = $state({ on: false });
export async function run(fn, onOk) {
  if (busy.on) { toast('Une action est déjà en cours.'); return null; }
  busy.on = true;
  try {
    const r = await fn();
    if (!r || !r.ok) { if (!(r && r.expired)) toast((r && r.error) || 'Action impossible', 'error'); return null; }
    if (onOk) await onOk(r);
    return r;
  } catch (e) {
    toast('Erreur inattendue : ' + e, 'error');
    return null;
  } finally {
    busy.on = false;
  }
}

// ---- démarrage, connexion, déconnexion ----
export async function boot() {
  setExpiredHandler(() => signedOut('Session expirée, reconnecte-toi.'));
  const r = await auth.me();
  if (r.ok) await enter(r.name); else app.phase = 'login';
}

let stopLive = null;
export async function enter(name) {
  app.name = name;
  app.phase = 'app';
  hydrateCollection();            // instantané, depuis le cache du navigateur
  await refreshMe();
  refreshCollection();            // en arrière-plan
  loadWatch();
  stopLive?.();
  stopLive = connectEvents({
    onState: (s) => { app.live = s === 'live' ? 'live' : 'down'; },
    onEvent: handleEvent,
    onResume: () => { refreshMe(); emit('resync'); },
  });
}

export function signedOut(message) {
  stopLive?.(); stopLive = null;
  app.phase = 'login'; app.me = null; app.rewards = null; app.live = 'down';
  coll.cards = []; coll.stats = null; coll.loaded = false;
  if (message) toast(message, 'error');
}

export async function logout() {
  await auth.logout();
  await idbClear();
  signedOut();
}

// ---- profil ----
export async function refreshMe() {
  const r = await call('load_me');
  if (!r || !r.ok) return r;
  app.me = r.me; app.names = r.names || {}; app.info = r.info || {}; app.rewards = r.rewards || app.rewards; app.meAt = Date.now();
  return r;
}
export const refreshMeSoon = debounce(refreshMe, 400);

// ---- collection : cache navigateur d'abord, serveur ensuite, l'écran ne bouge que si quelque chose a changé ----
const sig = (cards) => cards.map((c) => `${c.cid}|${c.name}|${c.copies}|${c.rarity}|${c.reads}|${c.locked ? 1 : 0}`).join(';');
const cacheKey = () => `coll:${app.name}`;

async function hydrateCollection() {
  const cached = await idbGet(cacheKey());
  if (cached && cached.cards && !coll.loaded) { applyCollection(cached); }
}
function applyCollection(d) {
  coll.cards = d.cards; coll.tags = d.tags || []; coll.rank = d.rank || {}; coll.stats = d.stats || null; coll.loaded = true;
}
export async function refreshCollection() {
  if (coll.loading) return;
  coll.loading = true;
  const r = await call('load_collection');
  coll.loading = false;
  if (!r || !r.ok) { if (!coll.loaded && r && !r.expired) toast(r.error || 'Collection indisponible', 'error'); return; }
  if (!coll.loaded || sig(coll.cards) !== sig(r.cards)) applyCollection(r);
  else { coll.rank = r.rank || {}; coll.stats = r.stats || null; }
  idbSet(cacheKey(), { cards: r.cards, tags: r.tags, rank: r.rank, stats: r.stats });
}
export const collectionChanged = debounce(refreshCollection, 1500); // gagné, vendu, échangé : la collection a bougé

// ---- temps réel ----
function handleEvent({ event, data }) {
  const d = data || {};
  if (event === 'notify') {
    toast(String(d.text || ''), d.kind === 'good' ? 'good' : d.kind === 'bad' ? 'error' : 'info');
    if (['won', 'sold', 'unsold'].includes(d.type)) collectionChanged();
    if (app.me) app.me.unread = (app.me.unread || 0) + 1;
    refreshMeSoon();
  } else if (event === 'message') {
    toast(`Nouveau message de ${d.from}`);
    refreshMeSoon();
  } else if (event === 'trade') {
    refreshMeSoon();
    if (d.what === 'accepted') collectionChanged();
  } else if (event === 'guild') {
    const gc = app.rewards && app.rewards.guild_chat;
    if (d.what === 'chat' && gc && app.me && d.par !== app.me.id) gc.last = Math.max(gc.last, d.mid || 0, gc.seen + 1);
  } else if (event === 'resync') {
    refreshMe();
  } else if (event === 'expired') {
    signedOut('Session expirée, reconnecte-toi.');
    return;
  }
  if (event === 'auction' && d.what === 'new' && d.cid) {
    const w = watch.list.find((x) => x.cid === d.cid);
    if (w) toast(`« ${w.name} » vient d'être mise aux enchères.`, 'good');
  }
  emit(event, d);
}

// ---- heure du serveur ----
export const setSkew = (now) => { if (typeof now === 'number') app.skew = now - Date.now() / 1000; };
export const nowSrv = () => Date.now() / 1000 + app.skew;
