// Faux serveur pour le développement (`npm run dev:mock`) et les tests d'interface : mêmes formes de réponses que le vrai
// (wikipick.service.Service), données fictives en mémoire. Jamais inclus dans la version de production.
import { ARTICLES } from './mock-data.js';

const now = () => Math.floor(Date.now() / 1000);
const NAMES = { C: 'Commune', PC: 'Inhabituelle', R: 'Rare', SR: 'Épique', UR: 'Exceptionnelle', L: 'Légendaire', M: 'Mythique', EXC: 'Exclusive' };
const ORDER = ['EXC', 'M', 'L', 'UR', 'SR', 'R', 'PC', 'C'];
const RAR = ['L', 'UR', 'SR', 'SR', 'R', 'R', 'R', 'PC', 'PC', 'PC', 'PC', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C', 'C'];
const COPIES = [1, 2, 1, 3, 1, 1, 2, 1, 4, 1, 1, 2, 1, 1, 6, 1, 1, 3, 1, 1, 2, 1];
const wait = (ms = 60) => new Promise((r) => setTimeout(r, ms));
const seed = (i) => ((i * 9301 + 49297) % 233280) / 233280;

function makeCards() {
  const cards = [];
  for (let k = 0; k < 96; k++) {
    const a = ARTICLES[k % ARTICLES.length], round = Math.floor(k / ARTICLES.length);
    const r = round ? ['R', 'PC', 'C', 'C'][(k + round) % 4] : RAR[k % RAR.length];
    const n = round ? (k % 5 === 0 ? 2 : 1) : COPIES[k % COPIES.length];
    const id = 1000 + k * 10;
    cards.push({ cid: 'fr:' + a[0] + (round ? '_' + round : ''), name: round ? `${a[1]} (${round + 1})` : a[1], desc: a[2], img: a[3], rarity: r,
      reads: Math.round(40000 + seed(k) * 18000000), nl: 1, lang: 'fr', locked: k === 5, ids: Array.from({ length: n }, (_, i) => id + i), free_ids: k === 5 ? [] : Array.from({ length: n }, (_, i) => id + i),
      locked_ids: k === 5 ? [id] : [], copies: n, tags: k % 5 === 0 ? [7] : [], shiny: k === 0 || k === 3, url: 'https://fr.wikipedia.org/wiki/' + a[0] });
  }
  return cards;
}

function stats(cards) {
  const by = {};
  for (const c of cards) { const b = (by[c.rarity] ||= { unique: 0, copies: 0 }); b.unique++; b.copies += c.copies; }
  const slim = (c) => ({ cid: c.cid, name: c.name, rarity: c.rarity, reads: c.reads, copies: c.copies, img: c.img });
  return {
    unique: cards.length, copies: cards.reduce((t, c) => t + c.copies, 0), duplicates: cards.filter((c) => c.copies > 1).length,
    extra_copies: cards.reduce((t, c) => t + c.copies - 1, 0), shiny: cards.filter((c) => c.shiny).length, locked: cards.filter((c) => c.locked).length,
    rarities: ORDER.filter((r) => by[r]).map((r) => ({ code: r, label: NAMES[r], ...by[r] })),
    top_reads: [...cards].sort((a, b) => b.reads - a.reads).slice(0, 10).map(slim),
    top_copies: [...cards].sort((a, b) => b.copies - a.copies).filter((c) => c.copies > 1).slice(0, 10).map(slim),
  };
}

const card = (i, r, extra) => { const a = ARTICLES[i % ARTICLES.length]; return { cid: 'fr:' + a[0], name: a[1], desc: a[2], img: a[3], rarity: r, reads: 5000 + i * 1111, shiny: false, copies: 1, locked: false, tags: [], ids: [], url: 'https://fr.wikipedia.org/wiki/' + a[0], new: false, ...extra }; };

const S = {
  logged: localStorage.getItem('mock-logged') !== '0',
  cards: makeCards(), coins: 1629, packs: 3, defi: false, unread: 2, unreadMsg: 2, friendReq: 1, trades: 1,
  prefs: {}, watch: [], log: [], bids: {}, packsOpened: 0,
  friends: [{ name: 'Camille', avatar: null, fav: true }, { name: 'Zoé', avatar: null, fav: false }, { name: 'Théo', avatar: null, fav: false }],
  incoming: [{ name: 'Inès', avatar: null, fav: false }], outgoing: [{ name: 'Malo', avatar: null, fav: false }],
  threads: { Camille: [{ id: 1, mine: false, text: 'Salut ! Tu as une Joconde à échanger ?' }, { id: 2, mine: true, text: 'Peut-être, je regarde ça ce soir.' }, { id: 3, mine: false, text: 'Top, merci 🙏' }], Zoé: [{ id: 4, mine: true, text: 'ok' }] },
  chat: [{ id: 1, uid: 5, name: 'Ada', text: 'Bienvenue à tous !', ts: now() - 300 }, { id: 2, uid: 1, name: 'Alex', text: 'Merci, content d’être là.', ts: now() - 120 }],
  streak: { open: true, wait: 0, ready: true, day: 3, done: 2, next: 5400, start: 0, days: [1, 2, 3, 4, 5, 6, 7].map((n) => ({ kind: n === 7 ? 'carte' : n === 5 ? 'dore' : n === 4 ? 'minipack' : 'wikiki', text: n === 7 ? 'Une carte rare' : n === 5 ? 'Un paquet doré' : n === 4 ? 'Un Mini-Pack' : `${n}0 Wikiki`, n: 1, card: n === 7 ? card(4, 'L') : null })) },
  quests: [{ title: 'Ouvre 3 paquets', what: 'Trois paquets dans la journée', done: 1, goal: 3, finished: false, claimed: false, locked: false, next: 3600, gain: 50, packs: false },
    { title: 'Une belle prise', what: 'Obtiens une carte rare ou mieux', done: 1, goal: 1, finished: true, claimed: false, locked: false, next: 3600, gain: 2, packs: true }],
  welcome: [{ code: 'b1', title: 'Ouvrir un premier paquet', what: '', done: 1, goal: 1, finished: true, claimed: false, gain: 20 }, { code: 'b2', title: 'Faire un premier échange', what: '', done: 0, goal: 1, finished: false, claimed: false, gain: 30 }],
};

function me() {
  return { id: 1, name: 'Alex', coins: S.coins, packs: S.packs, packMax: 10, packReserve: S.packs, next: 423, cards: S.cards.length, pro: false, succes: 1, aucLive: 0, aucMax: 5,
    unread: S.unread, unreadMsg: S.unreadMsg, trades: S.trades, friendReq: S.incoming.length, proPack: 0, paquetOr: 0, proCards: 20, defi: S.defi, avatar: null };
}
const rewards = () => ({ quests: S.quests, welcome: S.welcome, streak: S.streak, guild_chat: { guild: 3, last: 10, seen: 8 } });
const INFO = { odds: { M: 0.1, L: 0.5, UR: 2, SR: 8, R: 30, PC: 70, C: 100 }, bank: { C: 1, PC: 3, R: 10, SR: 40, UR: 100, L: 500, M: 2000 }, shinyOdds: 0.2, perPack: 5 };

const auc = (id, over) => ({ id, card: card(id, 'SR'), lot: null, price: 100 + id, min: 110 + id, bids: 2, leader: 'Bob', seller: 'Eve', mine: false, leading: false, ends_at: now() + 300 + id * 50, status: 'live', ...over });
const market = (page) => {
  const b = page * 10;
  return [auc(b + 11, { ends_at: now() + 25 }), auc(b + 12, { card: null, lot: { n: 3, name: 'Lot Renaissance', cards: [card(4, 'R'), card(20, 'SR'), card(21, 'C')] }, leader: 'Ann' }),
    auc(b + 13, { card: card(b + 3, 'L'), price: 900, min: 950, bids: 7 }), auc(b + 14, { mine: true, bids: 0, leader: '', seller: 'Alex', card: card(8, 'PC') }),
    auc(b + 15, { card: card(b + 9, 'R') }), auc(b + 16, { card: card(b + 14, 'C'), price: 12, min: 13, bids: 0, leader: '' })];
};

const defiSq = (f) => ({ viewBox: '0 0 40 40', shapes: [{ tag: 'path', attrs: { d: 'M7 7h26v26H7z', fill: f, transform: 'rotate(8 20 20)' } }] });
const CHALLENGE = { id: 'mockchallenge1', consigne: 'Clique sur la goutte', choix: [defiSq('#ef6f8d'), { viewBox: '0 0 40 40', shapes: [{ tag: 'path', attrs: { d: 'M20 3c8 10 12 15 12 20a12 12 0 01-24 0c0-5 4-10 12-20z', fill: '#40bd8f' } }] }, defiSq('#a78bfa'), defiSq('#40bd8f'), defiSq('#4aa7e6'), defiSq('#f3b33d')] };

const guildData = (id) => ({ id, name: id === 3 ? 'Les Encyclopédistes' : 'Autre guilde', tag: id === 3 ? 'WIKI' : 'ZZ', descr: 'Une guilde de collectionneurs passionnés.', color: '#e0a030', rank: 1, count: 2, score: 90000, leader: 'Ada',
  max_members: 50, is_member: id === 3, is_manager: id === 3, is_leader: false, applied: false,
  members: [{ name: 'Ada', me: false, leader: true, officer: false, total: 9000, joined: now() - 86400 * 40 }, { name: 'Alex', me: true, leader: false, officer: false, total: 1200, joined: now() - 86400 * 9 }, { name: 'Bob', me: false, leader: false, officer: true, total: 500, joined: now() - 86400 * 3 }],
  applications: [{ name: 'Zoé', created: now() - 600 }],
  feed: id === 3 ? [{ id: 9, name: 'Ada', card: card(18, 'L'), ts: now() - 100, likes: 2, liked: false, points: 900, comments: [{ id: 1, name: 'Bob', text: 'Bravo !', ts: now() - 50, can_delete: false }] }] : [],
  chat: id === 3 ? S.chat : [] });

window.__mock = S; // idem : les tests peuvent préparer l'état
const H = {
  load_me: () => ({ ok: true, me: me(), names: NAMES, info: INFO, rewards: rewards() }),
  load_collection: () => ({ ok: true, rank: { rank: 232, total: 6898, points: 14374, cards: 300, toNext: 15, nextName: 'Rival' }, tags: [{ id: 7, name: 'Peintres', color: '#fff' }], cards: S.cards, stats: stats(S.cards) }),
  cache_get: () => ({ ok: false }),
  prefs_get: () => ({ ok: true, prefs: S.prefs }),
  prefs_set: (k, v) => { S.prefs[k] = v; return { ok: true }; },
  watch_get: () => ({ ok: true, list: S.watch }),
  watch_set: (cid, name, on) => { S.watch = S.watch.filter((w) => w.cid !== cid); if (on) S.watch.push({ cid, name }); return { ok: true, list: S.watch }; },
  load_card: (cid) => ({ ok: true, extract: "La Joconde est un portrait peint à l’huile sur panneau de peuplier par Léonard de Vinci au début du XVIe siècle. Exposé au musée du Louvre depuis 1797, ce tableau est l’une des œuvres d’art les plus célèbres au monde. Son sourire énigmatique, son clair-obscur et la profondeur de son paysage en font un sommet de la Renaissance italienne. Elle est conservée derrière une vitre blindée, dans la salle des États, et attire plusieurs millions de visiteurs chaque année.",
    mine: (S.cards.find((c) => c.cid === cid) || { ids: [] }).ids.map((id, i) => ({ id, for_sale: false, state: i === 1 ? 'locked' : 'free', shiny: false, via: i ? 'paquet' : 'enchere', ts: now() - 86400 * (3 + i), price: i ? null : 250, from: i ? '' : 'Bob', lot: false })),
    wished: false, friends: ['Camille', 'Inès'], guild: ['Ada'], friend_wishes: ['Théo'], auctions: [auc(31, { card: card(4, 'L'), ends_at: now() + 120 })] }),
  recycle: (ids) => { S.coins += 40 * ids.length; return { ok: true, gain: 40 * ids.length, sold: ids.length, locked: 0 }; },
  card_lock: (id, cid, sh, on) => ({ ok: true, locked: on }),
  card_for_sale: () => ({ ok: true, n: 3 }),
  wish_set: (cid, on) => ({ ok: true, wished: on }),
  auction_create: () => ({ ok: true }),
  pack_challenge: () => ({ ok: true, challenge: CHALLENGE }),
  open_pack: (defi, rep) => {
    if (S.defi && defi == null) return { ok: false, challenge: true, error: 'Le site demande une petite vérification avant ce paquet.' };
    if (S.defi && rep !== 1) return { ok: false, error: 'Mauvaise réponse : réessaie.' };
    S.defi = false; S.packs = Math.max(0, S.packs - 1); S.packsOpened++;
    const pk = (i, r, sh, nw) => card(i, r, { shiny: sh, new: nw, ids: [i + 1] });
    return { ok: true, me: me(), cards: [pk(10, 'C', false, false), pk(6, 'PC', false, true), pk(14, 'R', false, false), pk(3, 'SR', false, true), pk(4, 'L', true, true)] };
  },
  pack_seen: () => ({ ok: true }),
  pack_history: () => ({ ok: true, packs: [{ ts: now() - 3600, gold: false, cards: [card(1, 'C'), card(2, 'PC', { new: true }), card(5, 'SR'), card(7, 'C'), card(9, 'R')] }] }),
  achievements_get: () => ({ ok: true, earned: 3, total: 50, won: 300, to_claim: 20, locked: false, families: ['Collection', 'Marché'], items: [
    { code: 'c10', family: 'Collection', title: '10 cartes', what: 'Posséder 10 cartes', done: 10, goal: 10, finished: true, claimed: false, gain: 20 },
    { code: 'c100', family: 'Collection', title: '100 cartes', what: 'Posséder 100 cartes', done: 96, goal: 100, finished: false, claimed: false, gain: 100 },
    { code: 'c1', family: 'Collection', title: 'Première carte', what: '', done: 1, goal: 1, finished: true, claimed: true, gain: 5 },
    { code: 'm1', family: 'Marché', title: 'Première enchère', what: 'Remporter une enchère', done: 0, goal: 1, finished: false, claimed: false, gain: 30 }] }),
  claim: (kind, key) => {
    if (kind === 'serie') { const d = S.streak.day; S.streak.ready = false; S.streak.done++; return { ok: true, titles: [], gain: 0, packs: false, gift: false, day: d, text: S.streak.days[d - 1].text, kind: S.streak.days[d - 1].kind }; }
    if (kind === 'quete') { const q = S.quests[key - 1]; q.claimed = true; return { ok: true, titles: [q.title], gain: q.gain, packs: q.packs, gift: false }; }
    if (kind === 'bienvenue') { const w = S.welcome.filter((x) => x.finished && !x.claimed && (key == null || x.code === key)); w.forEach((x) => (x.claimed = true)); return { ok: true, titles: w.map((x) => x.title), gain: w.reduce((t, x) => t + x.gain, 0), packs: false, gift: false }; }
    return { ok: true, titles: ['10 cartes'], gain: 20, packs: false, gift: false };
  },
  load_notifications: () => ({ ok: true, now: now(), unread: 2, items: [{ id: 9, type: 'outbid', text: "Quelqu'un a surenchéri sur La Joconde", tone: 'bad', link: '', read: false, created: now() - 40 }, { id: 8, type: 'won', text: 'Enchère remportée : Vincent van Gogh', tone: 'good', link: '', read: false, created: now() - 600 }, { id: 7, type: 'fin', text: 'Plus que 3 minutes sur Mont Blanc', tone: '', link: '', read: true, created: now() - 7200 }] }),
  read_notifications: () => { S.unread = 0; return { ok: true }; },
  load_market: (scope, page) => {
    if (scope === 'purchases' || scope === 'ventes') return { ok: true, history: true, page, pages: 1, total: 2, sum: 330, now: now(), items: [{ card: card(2, 'SR'), lot: null, price: 250, sold: scope === 'ventes', who: 'Bob', ts: now() - 7200 }, { card: card(6, 'C'), lot: null, price: 80, sold: scope === 'ventes', who: 'Ann', ts: now() - 90000 }] };
    if (scope === 'mine') return { ok: true, items: [auc(21, { mine: true, bids: 1, seller: 'Alex' })], page: 0, pages: 1, total: 1, now: now() };
    if (scope === 'bidding') return { ok: true, items: [auc(22, { leading: true })], page: 0, pages: 1, total: 1, now: now() };
    return { ok: true, page, pages: 2, total: 12, now: now(), items: market(page) };
  },
  stream_watch_market: () => ({ ok: true }),
  auction_get: (id) => ({ ok: true, auction: auc(id, { price: (S.bids[id] || 100 + id), leader: S.bids[id] ? 'Alex' : 'Bob', leading: !!S.bids[id], min: (S.bids[id] || 100 + id) + 10 }) }),
  bid: (id, amount) => { S.bids[id] = amount; S.coins -= amount; return { ok: true, extended: false, ends_at: 0 }; },
  auction_cancel: () => ({ ok: true }),
  auction_price: () => ({ ok: true }),
  load_trades: (box) => ({ ok: true, now: now(), trades: box === 'history' ? [] : [
    { id: 5, incoming: true, other: 'Camille', give: [card(4, 'R')], get: [card(1, 'SR'), card(9, 'C')], give_coins: 0, get_coins: 50, status: 'pending', message: 'Un échange équitable ?', valid: true, created: now() - 120, closed: 0 },
    { id: 7, incoming: false, other: 'Zoé', give: [card(12, 'PC')], get: [card(3, 'SR')], give_coins: 10, get_coins: 0, status: 'pending', message: '', valid: true, created: now() - 3600, closed: 0 }] }),
  trade_action: () => { S.trades = 0; return { ok: true }; },
  trade_send: () => ({ ok: true }),
  user_cards: () => ({ ok: true, groups: [{ card: card(1, 'SR'), ids: [9001, 9002] }, { card: card(9, 'C'), ids: [9003] }] }),
  conversations_get: () => ({ ok: true, conversations: [{ name: 'Camille', avatar: null, fav: true, blocked: false, last: S.threads.Camille.at(-1).text, mine: false, unread: S.unreadMsg, created: now() - 120 }, { name: 'Zoé', avatar: null, fav: false, blocked: false, last: 'ok', mine: true, unread: 0, created: now() - 7200 }] }),
  thread_get: (n) => { if (n === 'Camille') S.unreadMsg = 0; return { ok: true, thread: { with: n, avatar: null, friend: true, blocked: '', messages: S.threads[n] || [] } }; },
  message_send: (to, text) => { (S.threads[to] ||= []).push({ id: Date.now(), mine: true, text: text.trim() }); return { ok: true }; },
  friends_list: () => ({ ok: true, friends: S.friends, incoming: S.incoming, outgoing: S.outgoing }),
  friends_get: () => ({ ok: true, friends: S.friends, incoming: [], outgoing: [] }),
  players_search: (q) => ({ ok: true, users: ['Théo', 'Théa', 'Théodore'].filter((n) => n.toLowerCase().includes(q.toLowerCase())).map((name) => ({ name, avatar: null, me: false, relation: name === 'Théo' ? 'friends' : '' })) }),
  users_search: (q) => ({ ok: true, users: [{ name: 'Théo', online: true }] }),
  friend_action: (a, n) => {
    if (a === 'accept') { S.friends.push(...S.incoming.filter((u) => u.name === n)); S.incoming = S.incoming.filter((u) => u.name !== n); }
    if (a === 'remove') { S.friends = S.friends.filter((u) => u.name !== n); S.outgoing = S.outgoing.filter((u) => u.name !== n); }
    if (a === 'decline') S.incoming = S.incoming.filter((u) => u.name !== n);
    if (a === 'request') S.outgoing.push({ name: n, avatar: null, fav: false });
    return { ok: true, relation: a === 'accept' ? 'friends' : '' };
  },
  friend_favorite: (n, on) => { S.friends.forEach((u) => { if (u.name === n) u.fav = on; }); return { ok: true }; },
  profile_get: (n) => ({ ok: true, profile: { me: !n, blocked: '', name: n || 'Alex', avatar: null, created: now() - 86400 * 120, bio: n ? 'Collectionneur de chefs-d’œuvre et de paysages.' : '', stats: { cards: 737, distinct: S.cards.length, legend: 1, sales: 4 },
    relation: n ? 'friends' : '', friends: 3, rank: { rank: 232, total: 6898, points: 14374 }, guild: { id: 3, tag: 'WIKI', name: 'Les Encyclopédistes' },
    showcases: [{ id: 1, name: 'Mes chefs-d’œuvre', cards: [card(4, 'L'), card(3, 'UR'), card(8, 'SR')] }], slots: 5, max: 3, private_showcases: false } }),
  player_cards: (n, page) => ({ ok: true, page, pages: 2, total: 120, cards: S.cards.slice(page * 12, page * 12 + 12).map((c) => ({ card: c, n: c.copies })) }),
  guilds_get: () => ({ ok: true, mine: 3, guilds: [{ id: 3, rank: 1, tag: 'WIKI', name: 'Les Encyclopédistes', color: '#e0a030', leader: 'Ada', descr: 'Une guilde de collectionneurs passionnés.', members: 12, score: 90000, applied: false },
    { id: 4, rank: 2, tag: 'ZZ', name: 'Autre guilde', color: '#6d9bff', leader: 'Bob', descr: '', members: 3, score: 100, applied: false }] }),
  guild_get: (id) => ({ ok: true, guild: guildData(id) }),
  guild_chat_seen: () => ({ ok: true }),
  guild_action: (a, arg, text) => { if (a === 'chat') S.chat.push({ id: Date.now(), uid: 1, name: 'Alex', text, ts: now() }); return { ok: true, liked: true, dissolved: false }; },
  load_ranking: (period) => ({ ok: true, points: { M: 5000, L: 900, UR: 300, SR: 100, R: 30, PC: 10, C: 3 }, chroma_points: 12000, rule: period === 'tout' ? '' : 'acquis', reset_in: 90000,
    top: [['Ada', 12345, 'WIKI'], ['Alex', 11000, 'WIKI'], ['Bob', 9000, ''], ['Camille', 7200, ''], ['Zoé', 5100, '']].map(([name, points, guild], i) => ({ rank: i + 1, name, guild, me: name === 'Alex', chroma: 2, mythic: 1, legend: 3, ultra: 4, cards: 99 - i * 9, points })) }),
  combat_info: () => ({ ok: true, left: 4, total: 5, next: now() + 900, window: 1800, size: 3, wait: 60, prep: 120, chests: 1, chest_all: 5, chest_left: 3,
    opponents: [{ name: 'Camille', online: true, fighting: false, cards: 40, fav: true }, { name: 'Zoé', online: false, fighting: false, cards: 40, fav: false }],
    history: [{ me: 2, them: 1, defended: false, opponent: 'Bob', gain: 30, when: now() - 600 }] }),
  combat_state: () => ({ ok: true, defi: null }),
  actions_get: () => ({ ok: true, actions: S.log }),
  corbeille_get: () => ({ ok: true, price: 4, minutes: 20, items: [{ id: 801, card: card(11, 'C'), left: 600 }] }),
  corbeille_restore: () => ({ ok: true, restored: 1, cost: 4 }),
  corbeille_empty: () => ({ ok: true, erased: 1 }),
};

export async function rpc(method, args) {
  (window.__calls ||= []).push([method, ...args]); // pour les tests d'interface : ce que l'écran a demandé
  await wait(40 + Math.random() * 60);
  if (!S.logged) return { ok: false, expired: true, error: 'Session expirée, reconnecte-toi.' };
  const fn = H[method];
  return fn ? JSON.parse(JSON.stringify(fn(...args))) : { ok: false, error: `(démo) ${method} n'est pas simulé.` };
}

export async function auth(kind, body) {
  await wait(120);
  if (kind === 'me') return { ok: S.logged, name: S.logged ? 'Alex' : null };
  if (kind === 'challenge') return { ok: true, pending: 'mockpending', challenge: CHALLENGE };
  if (kind === 'login') {
    if (body.password !== 'demo') { return { ok: false, retry: true, error: 'Identifiants incorrects (démo : le mot de passe est « demo »).' }; }
    S.logged = true; localStorage.setItem('mock-logged', '1');
    return { ok: true, name: 'Alex' };
  }
  S.logged = false; localStorage.setItem('mock-logged', '0');
  return { ok: true };
}

// Temps réel factice : un message arrive peu après l'ouverture.
export function events(onState, onEvent) {
  onState('live');
  const t = setTimeout(() => onEvent({ event: 'message', data: { from: 'Camille' } }), 8000);
  return { close: () => clearTimeout(t) };
}
