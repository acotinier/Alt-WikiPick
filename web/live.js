"use strict";
/* Temps réel (lecture seule). Le flux /api/stream est lu par Python ; ici on vient chercher les
   événements déjà filtrés chaque seconde (appel local, aucun trafic réseau).
   Contenu : notifications + cloche, et l'onglet Marché avec enchères mises à jour en direct.
   Chargé AVANT app.js : rien ne s'exécute ici au chargement, S / $ / el… n'existent pas encore. */

const LV = {
  timer: null, busy: false, ever: false, watching: false, skew: 0, lastResync: 0, notifs: [],
  local: [], localUnread: 0, // alertes locales (cartes surveillées) : ne viennent pas du serveur, donc à part de ses compteurs
  market: {
    scope: "live", items: [], page: 0, pages: 1, total: 0, sum: 0, history: false, seq: 0, loading: false, auto: 0, lastLoad: 0,
    q: "", rar: new Set(), kind: "", sort: "fin", view: "grid",
    f: { min: 0, max: 0, endsIn: 0, noBid: false }, // filtres appliqués sur ce qui est chargé
  },
};
const RARITY_FILTER = ["M", "L", "UR", "SR", "R", "PC", "C"];
const SERVER_SORTS = ["fin", "rarete", "prixbas", "prix", "mises"]; // les autres tris (lectures, nom) se font ici
const END_DELAY = 8000; // une enchère terminée reste affichée ce temps-là, puis disparaît du marché
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const plural = (n, one, many = one + "s") => `${n} ${n > 1 ? many : one}`;
const nowSrv = () => Date.now() / 1000 + LV.skew; // heure du serveur : les fins d'enchère sont dans son référentiel
const setSkew = (now) => { if (typeof now === "number") LV.skew = now - Date.now() / 1000; };
const refreshMeSoon = debounce(() => refreshMe(), 400);
const refreshSoon = debounce(() => { if (!PK.opening && S.tab !== "packs") refresh(); }, 1500);
const collectionChanged = () => { S.dirty = true; refreshSoon(); }; // gagné, vendu, échangé : la collection a bougé

function ago(ts, now = nowSrv()) {
  if (!ts) return "";
  const s = Math.max(1, Math.floor(now - ts));
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
  return `il y a ${Math.floor(s / 86400)} j`;
}
function sessionLost(r) {
  stopLive(); S.data = null; show("login"); loginMsg(r.error || "Session expirée, reconnecte-toi.", true);
}

/* ---------------- flux ---------------- */
function startLive() {
  if (LV.timer) return;
  api().start_stream(); resumeArena();
  LV.timer = setInterval(pollLive, 1000);
  loadNotifs(); loadWatch();
}
function stopLive() {
  clearInterval(LV.timer); LV.timer = null; LV.ever = false; LV.notifs = []; LV.local = []; LV.localUnread = 0; LV.market.items = []; LV.watching = false;
  api().stop_stream(); setLive(""); closeBell();
}
async function pollLive() {
  if (LV.busy) return;
  LV.busy = true;
  try {
    const r = await api().poll_events();
    if (!LV.timer) return;
    setLive(r.state);
    for (const ev of r.events || []) onStream(ev);
  } catch (e) { /* le pont ne répond pas : on réessaie à la seconde suivante */ } finally { LV.busy = false; }
}
function setLive(state) {
  const n = $("live"); if (state === "live") LV.ever = true;
  n.classList.toggle("hidden", !state); n.classList.toggle("down", !!state && state !== "live");
  $("live-t").textContent = state === "live" ? "En direct" : LV.ever ? "Reconnexion…" : "Connexion…";
}
function onStream({ event, data }) {
  const d = data || {};
  if (event === "notify") onNotify(d);
  else if (event === "message") onMessageEvent(d);
  else if (event === "guild") onGuildEvent(d);
  else if (event === "trade") { refreshMeSoon(); if (d.what === "accepted") collectionChanged(); if (S.tab === "trades") loadTrades(); }
  else if (event === "auction") { watchAlert(d); applyAuction(d); }
  else if (event === "combat") onCombat(d);
  else if (event === "resync") resyncLive();
  else if (event === "expired") sessionLost({});
}
function resyncLive() { // le flux revient après une coupure : on relit ce qui est à l'écran (au plus toutes les 15 s)
  if (Date.now() - LV.lastResync < 15000) return;
  LV.lastResync = Date.now();
  loadNotifs(); refreshMeSoon();
  if (S.tab === "market") loadMarket();
}

/* ---------------- notifications ---------------- */
function onNotify(d) {
  const it = { id: d.id || 0, type: d.type || "", text: String(d.text || ""), tone: d.kind === "good" || d.kind === "bad" ? d.kind : "",
    link: d.link || "", read: false, created: nowSrv() };
  LV.notifs.unshift(it);
  if (S.data) { S.data.me.unread = (S.data.me.unread || 0) + 1; renderBell(); }
  if (it.type !== "fin") { toast(it.text, it.tone || "info"); ping(it.tone || "info"); } // « plus que 3 minutes » : la cloche suffit, comme sur le site
  if (["won", "sold", "unsold"].includes(it.type)) collectionChanged();
  renderNotifs(); refreshMeSoon(); // le serveur corrige le compteur
}
function renderBell() {
  const n = ((S.data && S.data.me.unread) || 0) + LV.localUnread, b = $("bell-n");
  b.textContent = n > 99 ? "99+" : String(n); b.classList.toggle("hidden", n < 1);
}
async function loadNotifs() {
  const r = await api().load_notifications();
  if (r.expired) return sessionLost(r);
  if (!r.ok) return;
  setSkew(r.now); LV.notifs = r.items; renderNotifs();
}
function notifNode(n) {
  return el("div", { class: "nitem" + (n.read ? "" : " unread") + (n.tone ? " " + n.tone : "") },
    el("span", { class: "tone" }),
    el("div", { class: "tx" }, el("div", { text: n.text }), el("small", { text: ago(n.created) })));
}
function renderNotifs() {
  const all = [...LV.local, ...LV.notifs].sort((a, b) => b.created - a.created);
  $("bell-list").replaceChildren(...(all.length ? all.map(notifNode)
    : [el("div", { class: "empty", text: "Rien de neuf. Tes notifications apparaîtront ici." })]));
  const me = (S.data && S.data.me) || {};
  const extra = [me.unreadMsg && plural(me.unreadMsg, "message non lu", "messages non lus"),
    me.trades && plural(me.trades, "échange en attente", "échanges en attente"),
    me.friendReq && plural(me.friendReq, "demande d'ami", "demandes d'ami")].filter(Boolean);
  $("bell-foot").replaceChildren(el("span", { text: extra.join(", ") }),
    el("button", { class: "link", text: "Ouvrir wiki-pick.com", onclick: () => api().open_url("https://wiki-pick.com/") }));
}
const closeBell = () => $("bell-panel").classList.add("hidden");
async function toggleBell() {
  const p = $("bell-panel");
  if (!p.classList.contains("hidden")) return closeBell();
  p.classList.remove("hidden"); renderNotifs();
  await loadNotifs();
}
async function markAllRead() { // action manuelle : un clic = « tout marquer comme lu », comme sur le site
  const r = await api().read_notifications();
  if (r.expired) return sessionLost(r);
  if (!r.ok) return toast(r.error || "Impossible de marquer comme lu");
  LV.notifs.forEach((n) => { n.read = true; });
  LV.local.forEach((n) => { n.read = true; }); LV.localUnread = 0;
  if (S.data) S.data.me.unread = 0;
  renderBell(); renderNotifs();
}

/* ---------------- marché (lecture seule) ----------------
   Trois vues : le marché (paginé, filtré et trié par le serveur), mes ventes et mes mises (renvoyées en entier).
   Les filtres « prix », « échéance » et « sans mise », et les tris « lectures » / « nom », s'appliquent ici,
   sur ce qui est chargé. Rien d'automatique : le défilement charge la suite, une page à la fois. */
const cardsOf = (a) => (a.card ? [a.card] : a.lot ? a.lot.cards : []);
const nameOf = (a) => (a.lot ? a.lot.name : a.card ? a.card.name : "");
const bestRank = (a) => Math.min(99, ...cardsOf(a).map((c) => rarityRank(c.rarity)));
const maxReads = (a) => Math.max(0, ...cardsOf(a).map((c) => c.reads));
const endKey = (a) => (a.status === "live" ? a.ends_at : Infinity);
const cmp = (x, y) => (x < y ? -1 : x > y ? 1 : 0);
const SORTS = {
  fin: (a, b) => cmp(endKey(a), endKey(b)),
  rarete: (a, b) => bestRank(a) - bestRank(b) || b.price - a.price,
  prixbas: (a, b) => a.price - b.price,
  prix: (a, b) => b.price - a.price,
  mises: (a, b) => b.bids - a.bids || b.price - a.price,
  lectures: (a, b) => maxReads(b) - maxReads(a),
  nom: (a, b) => nameOf(a).localeCompare(nameOf(b), "fr"),
};

function marketView() { // ce qui est chargé, filtré puis trié
  const m = LV.market, f = m.f, now = nowSrv(), q = m.q.toLowerCase();
  const list = m.items.filter((a) => {
    const cs = cardsOf(a);
    if (m.scope === "bidding" && a.mine) return false; // « mes mises » : pas mes propres ventes
    if (m.kind === "lots" && !a.lot) return false;
    if (m.kind === "cartes" && a.lot) return false;
    if (m.rar.size && !cs.some((c) => m.rar.has(c.rarity))) return false;
    if (q && !`${nameOf(a)} ${a.seller} ${a.leader} ${cs.map((c) => c.desc).join(" ")}`.toLowerCase().includes(q)) return false;
    if (f.min && a.price < f.min) return false;
    if (f.max && a.price > f.max) return false;
    if (f.noBid && a.bids > 0) return false;
    if (f.endsIn && (a.status !== "live" || a.ends_at - now > f.endsIn)) return false;
    return true;
  });
  return m.history && m.sort === "fin" ? list : list.sort(SORTS[m.sort] || SORTS.fin); // historique : l'ordre du site, le plus récent d'abord
}
const pagedScope = () => LV.market.scope === "live" || LV.market.history; // vues lues page par page

function enterMarket() {
  LV.watching = true; api().stream_watch_market(true);
  buildMarketFilters(); loadMarket(); // on relit à chaque visite : le flux n'était pas transmis pendant l'absence
}
function leaveMarket() {
  if (!LV.watching) return;
  LV.watching = false; api().stream_watch_market(false);
}
function buildMarketFilters() {
  const m = LV.market, box = $("m-rarities"); box.replaceChildren();
  RARITY_FILTER.forEach((r) => box.append(el("button", {
    class: "chip" + (m.rar.has(r) ? " on" : ""), style: `--c:${color(r)}`, text: label(r),
    onclick: (e) => { m.rar.has(r) ? m.rar.delete(r) : m.rar.add(r); e.currentTarget.classList.toggle("on"); refetchMarket(); },
  })));
}
// ce que le serveur sait faire (recherche, raretés, type, tri) : on relit ; sinon on redessine
const refetchMarket = () => (LV.market.scope === "live" ? loadMarket() : renderMarket());

async function loadMarket(more = false) {
  const m = LV.market, mine = ++m.seq; // seule la dernière demande compte (deux filtres cliqués vite)
  m.loading = true; m.lastLoad = Date.now();
  if (!more) {
    m.auto = 0; m.items = [];
    $("mgrid").replaceChildren(...Array.from({ length: 10 }, () => el("div", { class: "card sk" })));
  }
  const tri = SERVER_SORTS.includes(m.sort) ? m.sort : "fin";
  const r = await api().load_market(m.scope, more ? m.page + 1 : 0, m.q, [...m.rar], tri, m.kind);
  if (mine !== m.seq) return;
  m.loading = false;
  if (r.expired) return sessionLost(r);
  if (!r.ok) { toast(r.error || "Marché indisponible"); return; }
  setSkew(r.now);
  m.history = !!r.history; m.sum = r.sum || 0;
  // achats et ventes terminés : mêmes tuiles que les enchères, avec un identifiant négatif (ils n'en ont pas)
  const base = more ? m.items.length : 0;
  const items = r.history ? r.items.map((h, i) => ({ id: -(base + i + 1), card: h.card, lot: h.lot, price: h.price, min: 0, bids: 0, leader: "",
    seller: "", mine: false, leading: false, ends_at: 0, status: "done", hist: { sold: h.sold, who: h.who, ts: h.ts } })) : r.items;
  m.items = more ? m.items.concat(items.filter((a) => !m.items.some((x) => x.id === a.id))) : items;
  m.page = r.page; m.pages = r.pages; m.total = r.total;
  renderMarket();
  setTimeout(checkMore, 1300); // écran pas rempli (filtres serrés) : la suite se charge toute seule, doucement
}

function auctionTile(a) { return LV.market.view === "list" ? auctionRow(a) : auctionCard(a); }

function auctionState(a) {
  if (a.hist) return `${a.hist.sold ? "Vendu à" : "Acheté à"} ${a.hist.who}`;
  const fini = a.status !== "live";
  return a.status === "cancelled" ? "Annulée" : fini ? (a.leader ? `Adjugé à ${a.leader}` : "Terminé sans preneur")
    : a.mine ? (a.lot ? "Ton lot" : "Ta carte") : a.leading ? "Tu es en tête" : "";
}
function auctionCard(a) {
  const c = a.card || (a.lot && a.lot.cards[0]);
  const fini = a.status !== "live" && !a.hist; // un achat ou une vente passés ne sont pas grisés
  const shown = a.lot && c ? Object.assign({}, c, { name: a.lot.name, desc: "", copies: 1 }) : c;
  const face = shown ? cardNode(shown, () => openModal(c)) : el("div", { class: "card sk" });
  if (a.lot) face.append(el("span", { class: "lotbadge", text: `Lot de ${plural(a.lot.n || a.lot.cards.length, "carte")}` }));
  const state = a.hist ? "" : auctionState(a);
  const who = a.hist ? auctionState(a) : a.bids ? (fini ? "" : "en tête : ") + (a.leader || a.seller) : "par " + a.seller;
  return el("div", { class: "offer" + (fini ? " fini" : "") + (a.leading ? " lead" : ""), "data-id": String(a.id) },
    face,
    el("div", { class: "deal" },
      el("div", {}, el("span", { class: "price" }, icon("coin"), fmt(a.price)), el("div", { class: "seller", text: who })),
      a.hist ? el("span", { class: "timer done", text: ago(a.hist.ts) })
        : fini ? el("span", { class: "timer done", text: "Terminé" }) : el("span", { class: "timer", "data-ends": String(a.ends_at) })),
    state ? el("div", { class: "astate", text: state }) : null,
    bidControls(a));
}
function auctionRow(a) { // vue liste : beaucoup d'enchères d'un coup d'œil
  const c = a.card || (a.lot && a.lot.cards[0]);
  const fini = a.status !== "live" && !a.hist;
  const thumb = el("span", { class: "thumb", style: `--c:${color(c ? c.rarity : "C")}` });
  if (c && c.img) thumb.style.backgroundImage = `url("${c.img.replace(/"/g, "%22")}")`;
  const state = auctionState(a);
  const open = () => { if (c) openModal(c); };
  return el("div", {
    class: "offer arow" + (fini ? " fini" : "") + (a.leading ? " lead" : ""), "data-id": String(a.id), tabindex: "0", role: "button",
    onclick: open, onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } },
  },
    thumb,
    el("span", { class: "nm" }, el("b", { text: nameOf(a) || "?" }),
      el("small", { text: a.lot ? `Lot de ${plural(a.lot.n || a.lot.cards.length, "carte")}` : (c && c.desc) || "" })),
    el("span", { class: "rr", style: `--c:${color(c ? c.rarity : "C")}`, text: c ? label(c.rarity) : "" }),
    el("span", { class: "rd", text: c ? compact(maxReads(a)) : "" }),
    el("span", { class: "pr" }, icon("coin"), fmt(a.price)),
    el("span", { class: "bd", text: a.hist ? "" : String(a.bids) }),
    el("span", { class: "ld" + (state ? " st" : ""), text: state || (a.bids ? a.leader : "par " + a.seller) }),
    a.hist ? el("span", { class: "timer done", text: ago(a.hist.ts) })
      : fini ? el("span", { class: "timer done", text: "Terminé" }) : el("span", { class: "timer", "data-ends": String(a.ends_at) }),
    el("span", { class: "act" }, bidControls(a)));
}
const SORT_ARROW = { nom: "↑", rarete: "↑", prixbas: "↑", prix: "↓", lectures: "↓", mises: "↓", fin: "↑" }; // sens de chaque tri
function listHead() {
  const m = LV.market;
  const col = (text, keys, cls, key = keys[0]) => el("button", {
    class: "hd " + cls + (keys.includes(m.sort) ? " on" : ""), onclick: () => setSort(key),
    text: keys.includes(m.sort) ? `${text} ${m.history && m.sort === "fin" ? "↓" : SORT_ARROW[m.sort]}` : text,
  });
  return el("div", { class: "arow head" }, el("span"), col("Carte", ["nom"], "nm"), col("Rareté", ["rarete"], "rr"),
    col("Lectures", ["lectures"], "rd"), col("Prix", ["prixbas", "prix"], "pr", m.sort === "prixbas" ? "prix" : "prixbas"),
    m.history ? el("span", { class: "bd" }) : col("Mises", ["mises"], "bd"), el("span", { class: "ld", text: m.history ? "Avec" : "En tête" }), col(m.history ? "Date" : "Fin", ["fin"], "tm"), el("span"));
}
function setSort(key) {
  const m = LV.market; m.sort = key; $("m-sort").value = key; savePref("market_sort", key);
  if (m.scope === "live" && SERVER_SORTS.includes(key)) loadMarket(); else renderMarket();
}

const MARKET_EMPTY = { mine: "Tu n'as aucune carte en vente pour l'instant.", bidding: "Tu n'as misé sur aucune enchère en cours.",
  purchases: "Les cartes que tu remportes aux enchères apparaîtront ici.", ventes: "Les cartes que tu vends aux enchères apparaîtront ici, avec leur prix." };
const marketEmptyText = () => MARKET_EMPTY[LV.market.scope] || "Aucune enchère ne correspond.";
function renderMarketCount(list = marketView()) {
  const m = LV.market, more = m.page + 1 < m.pages;
  const noun = m.history ? (m.scope === "ventes" ? "vente" : "achat") : "enchère";
  $("m-count").textContent = plural(list.length, noun) + " affiché" + (noun === "achat" ? "" : "e") + (list.length > 1 ? "s" : "");
  $("m-note").textContent = m.scope === "live" ? `${fmt(m.items.length)} chargées sur ${fmt(m.total)} en cours.` + (more ? " Fais défiler pour charger la suite." : "")
    : m.history ? `${fmt(m.items.length)} chargés sur ${fmt(m.total)} en tout` + (m.sum ? `, pour ${fmt(m.sum)} Wikiki.` : ".") + (more ? " Fais défiler pour charger la suite." : "")
    : `${fmt(m.items.length)} au total.`;
  $("m-more").classList.toggle("hidden", !pagedScope() || !more);
}
function renderMarket() {
  const m = LV.market, g = $("mgrid"), list = marketView();
  g.className = "grid " + (m.view === "list" ? "list" : m.view === "dense" ? "g-s" : "g-l");
  $("tab-market").classList.toggle("hist", m.history); // achats et ventes passés : pas d'échéance ni de « sans mise »
  $("m-sort").options[0].text = m.history ? "Trier par date, récent d'abord" : "Trier par fin proche";
  document.querySelectorAll("#m-views button").forEach((b) => b.classList.toggle("on", b.dataset.view === m.view));
  document.querySelectorAll("#m-scopes button").forEach((b) => b.classList.toggle("on", b.dataset.scope === m.scope));
  const nodes = list.map(auctionTile);
  if (m.view === "list" && list.length) nodes.unshift(listHead());
  g.replaceChildren(...(list.length ? nodes : [el("div", { class: "empty", text: marketEmptyText() })]));
  renderMarketCount(list); tickMarket();
}
function tickMarket() {
  const now = nowSrv();
  document.querySelectorAll("#mgrid .timer[data-ends], #modal .timer[data-ends]").forEach((t) => {
    const left = Math.max(0, Math.ceil(+t.dataset.ends - now));
    t.textContent = left > 0 ? clock(left) : "Clôture…";
    t.classList.toggle("hot", left > 0 && left <= 15); t.classList.toggle("done", left <= 0);
  });
}
setInterval(tickMarket, 1000);

// Chargement de la suite au défilement : une page à la fois, au plus toutes les 1,3 s, 12 pages d'affilée au plus
// (au-delà, le bouton « Charger la suite » reprend la main).
function checkMore() {
  const s = $("m-sentinel"), m = LV.market;
  if (S.tab !== "market" || !pagedScope() || m.loading || m.page + 1 >= m.pages || m.auto >= 12) return;
  if (Date.now() - m.lastLoad < 1200 || s.getBoundingClientRect().top > innerHeight + 500) return;
  m.auto++; loadMarket(true);
}

/* Une enchère bouge : on ne retouche que sa tuile (la liste chargée ne saute pas). */
function applyAuction(d) {
  const m = LV.market, a = m.items.find((x) => x.id === d.id);
  if (!a) return;
  const me = S.data && S.data.me.id;
  if (d.what === "bid") Object.assign(a, { price: Number(d.price) || a.price, leader: d.leader ?? a.leader, min: Number(d.min) || a.min,
    ends_at: Number(d.endsAt) || a.ends_at, bids: a.bids + 1, leading: d.leaderId === me });
  else if (d.what === "end") { a.status = d.sold ? "sold" : "unsold"; if (d.price) a.price = Number(d.price); a.leading = !!d.sold && d.winnerId === me; if (!d.sold) a.leader = ""; }
  else if (d.what === "cancel") a.status = "cancelled";
  else if (d.what === "prix") Object.assign(a, { price: Number(d.price) || a.price, min: Number(d.min) || a.min });
  else return;
  swapTile(a, d);
  if (d.what === "end" || d.what === "cancel") retireAuction(a.id);
  if (d.what === "end" && d.sold && d.winnerId === me) collectionChanged();
}
function swapTile(a, d) { // remplace la tuile de cette enchère sur place (la liste chargée ne saute pas)
  const old = document.querySelector(`#mgrid .offer[data-id="${a.id}"]`);
  if (!old) return;
  const fresh = auctionTile(a);
  if (d && d.what === "bid") {
    fresh.classList.add("bump");
    if (d.extended) { const tag = el("span", { class: "xtag", text: "Prolongation" }); fresh.append(tag); setTimeout(() => tag.remove(), 6000); }
  }
  old.replaceWith(fresh); tickMarket();
}
function retireAuction(id) { // sur le marché, une enchère terminée disparaît quelques secondes après ; « mes ventes / mes mises » la gardent
  const m = LV.market, scope = m.scope;
  if (scope !== "live") return;
  setTimeout(() => {
    const x = document.querySelector(`#mgrid .offer[data-id="${id}"]`);
    if (x) x.classList.add("leaving");
    setTimeout(() => {
      if (m.scope !== scope) return; // on a changé de vue entre-temps
      m.items = m.items.filter((a) => a.id !== id); m.total = Math.max(0, m.total - 1);
      const y = document.querySelector(`#mgrid .offer[data-id="${id}"]`); if (y) y.remove();
      renderMarketCount();
    }, 350);
  }, END_DELAY);
}

function resetMarketFilters() {
  const m = LV.market;
  m.q = ""; m.rar.clear(); m.kind = ""; m.f = { min: 0, max: 0, endsIn: 0, noBid: false };
  $("m-search").value = ""; $("m-kind").value = ""; $("m-min").value = ""; $("m-max").value = ""; $("m-end").value = "0"; $("m-nobid").checked = false;
  buildMarketFilters(); refetchMarket();
}

function bindLive() {
  $("btn-bell").onclick = (e) => { e.stopPropagation(); toggleBell(); };
  $("btn-read-all").onclick = markAllRead;
  document.addEventListener("click", (e) => {
    const p = $("bell-panel");
    if (!p.classList.contains("hidden") && !p.contains(e.target) && !$("btn-bell").contains(e.target)) closeBell();
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeBell(); });

  const m = LV.market;
  $("m-search").addEventListener("input", debounce((e) => { m.q = e.target.value.trim(); refetchMarket(); }, 350));
  $("m-kind").onchange = (e) => { m.kind = e.target.value; refetchMarket(); };
  $("m-sort").onchange = (e) => setSort(e.target.value);
  $("m-end").onchange = (e) => { m.f.endsIn = +e.target.value; renderMarket(); };
  $("m-nobid").onchange = (e) => { m.f.noBid = e.target.checked; renderMarket(); };
  const num = (id, key) => $(id).addEventListener("input", debounce((e) => { m.f[key] = Math.max(0, Number(e.target.value) || 0); renderMarket(); }, 250));
  num("m-min", "min"); num("m-max", "max");
  $("m-reset").onclick = resetMarketFilters;
  document.querySelectorAll("#m-scopes button").forEach((b) => { b.onclick = () => { m.scope = b.dataset.scope; loadMarket(); }; });
  document.querySelectorAll("#m-views button").forEach((b) => { b.onclick = () => { m.view = b.dataset.view; savePref("market_view", m.view); renderMarket(); }; });
  $("m-more").onclick = () => { m.auto = 0; loadMarket(true); };
  new IntersectionObserver((e) => { if (e[0].isIntersecting) checkMore(); }, { rootMargin: "500px" }).observe($("m-sentinel"));
}
