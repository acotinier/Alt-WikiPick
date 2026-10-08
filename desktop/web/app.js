"use strict";
/* Interface Wiki-Pick Desktop. Toutes les données affichées sont construites
   via textContent / createElement (jamais innerHTML) : les noms de cartes
   viennent de l'extérieur et ne doivent pas pouvoir injecter de HTML.
   packs.js (onglet Paquets) est chargé avant ce fichier. */

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
const RARITY_ORDER = ["EXC", "WBC", "SIXSEVEN", "M", "L", "UR", "SR", "R", "PC", "C"];
const TOP = new Set(["EXC", "WBC", "SIXSEVEN", "M", "L", "UR"]); // rareté qui mérite des effets forts
const PAGE = 60;

const S = { data: null, filtered: [], shown: 0, rarities: new Set(), tab: "collection", dirty: false, refreshing: false, meAt: 0, lastPoll: 0 };

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k === "style") n.setAttribute("style", v);
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null) n.append(c);
  return n;
}
const SVGNS = "http://www.w3.org/2000/svg";
function icon(name) { // symboles définis dans index.html
  const s = document.createElementNS(SVGNS, "svg"); s.setAttribute("class", "i"); s.setAttribute("aria-hidden", "true");
  const u = document.createElementNS(SVGNS, "use"); u.setAttribute("href", "#i-" + name); s.append(u);
  return s;
}
const fmt = (n) => Number(n || 0).toLocaleString("fr-FR").replace(/\u202f/g, "\u00a0"); // l'espace fine ne se voit pas en petit : « 5000 »
const compact = (n) => Number(n || 0).toLocaleString("fr-FR", { notation: "compact" });
const color = (r) => `var(--r-${RARITY_ORDER.includes(r) ? r : "C"})`;
const label = (r) => (S.data && S.data.names && S.data.names[r]) || r;
const rarityRank = (r) => { const i = RARITY_ORDER.indexOf(r); return i < 0 ? 99 : i; };
const isTop = (c) => TOP.has(c.rarity) || c.shiny;
const clock = (s) => {
  s = Math.max(0, Math.floor(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${h} h ${String(m).padStart(2, "0")}` : `${m}:${String(s % 60).padStart(2, "0")}`;
};

function toast(msg, kind = "error") { // error | info | good
  const t = $("toast"); t.textContent = msg; t.className = "toast " + kind;
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), 5000);
}
function busy(text) {
  $("loading-text").textContent = text || "Chargement…";
  $("loading").classList.toggle("hidden", !text);
}
function show(screen) {
  $("login").classList.toggle("hidden", screen !== "login");
  $("app").classList.toggle("hidden", screen !== "app");
}
function setSync(text, cls = "") {
  const s = $("sync"); s.textContent = text; s.title = text; s.className = "sync " + cls + (text ? "" : " hidden");
}
const TAB_TITLES = { collection: "Collection", packs: "Paquets", fusion: "Fusion", market: "Marché", trades: "Échanges", arena: "Arène", rank: "Classement", stats: "Statistiques",
  messages: "Messages", friends: "Amis", guild: "Guilde", profile: "Profil", rewards: "Récompenses" };
const TABS = Object.keys(TAB_TITLES);
function setTab(t) {
  const changed = S.tab !== t;
  S.tab = t;
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === t));
  const title = $("page-title"); title.textContent = t === "profile" && PF.name ? `Profil de ${PF.name}` : TAB_TITLES[t];
  if (changed) { title.style.animation = "none"; void title.offsetWidth; title.style.animation = ""; } // le titre glisse à chaque changement d'onglet
  TABS.forEach((n) => $("tab-" + n).classList.toggle("hidden", t !== n));
  if (t === "market") enterMarket(); else leaveMarket();
  refreshArenaDot();
  if (t === "arena") loadArena(); else if (t === "trades") loadTrades(true); else if (t === "rank") loadRanking(); else if (t === "packs") loadJournal();
  else if (t === "messages") loadMessages(); else if (t === "friends") loadFriends(); else if (t === "guild") loadGuild();
  else if (t === "profile") loadProfile(); else if (t === "rewards") loadRewards(); else if (t === "fusion") loadFusion();
  if (t !== "packs" && S.dirty) refresh(); // un paquet a été ouvert : la collection a changé
}

/* ---------------- connexion ---------------- */
let loginTimer = null;
function loginMsg(text, err) { const m = $("login-msg"); m.textContent = text || ""; m.classList.toggle("err", !!err); }

async function startLogin() {
  $("btn-login").disabled = true;
  loginMsg("Fenêtre de connexion ouverte… connecte-toi dessus.");
  await api().start_login();
  clearInterval(loginTimer);
  loginTimer = setInterval(async () => {
    const { state } = await api().login_state();
    if (state === "ok") {
      clearInterval(loginTimer); $("btn-login").disabled = false; loginMsg(""); await refresh();
    } else if (state === "cancelled") {
      clearInterval(loginTimer); $("btn-login").disabled = false; loginMsg("Connexion annulée.", true);
    }
  }, 1000);
}

async function useCookies() {
  const r = await api().import_cookie_header($("cookie-text").value);
  if (r.ok) { $("cookie-text").value = ""; await refresh(); } else loginMsg(r.error, true);
}

async function logout() {
  stopLive(); await api().logout(); S.data = null; S.dirty = false; setSync(""); resetPacks(); show("login"); loginMsg("Déconnecté.");
}

/* ---------------- chargement : le profil d'abord, la collection ensuite ---------------- */
/* Au démarrage, la dernière collection connue (cache disque) s'affiche tout de suite, puis
   le site est relu en arrière-plan. La grille n'est reconstruite que si quelque chose a changé. */
const collSig = (cards) => cards.map((c) => `${c.cid}|${c.copies}|${c.rarity}|${c.reads}|${c.locked ? 1 : 0}|${c.tags.join(",")}`).join(";");

function failLoad(r) {
  if (r.expired) { stopLive(); S.data = null; setSync(""); show("login"); loginMsg(r.error, true); return; }
  if (S.data) {
    setSync("Hors ligne", "err"); toast(r.error || "Erreur de chargement");
    if (!S.data.loaded) $("grid").replaceChildren(el("div", { class: "empty", text: "Collection indisponible pour le moment. Utilise Actualiser pour réessayer." }));
    return;
  }
  setSync(""); show("login"); loginMsg(r.error || "Erreur de chargement", true);
}

async function refresh() {
  if (S.refreshing || PK.opening) return;
  S.refreshing = true; S.dirty = false;
  setSync("Synchronisation…", "busy");
  try {
    const m = await api().load_me();
    if (!m.ok) return failLoad(m);
    if (S.data && S.data.me && S.data.me.id !== m.me.id) S.data = null; // le cache était celui d'un autre compte
    const fresh = !S.data;
    if (fresh) S.data = { me: m.me, names: m.names, info: m.info || {}, rewards: m.rewards || null, cards: [], tags: [], rank: {}, stats: null, loaded: false };
    else Object.assign(S.data, { me: m.me, names: m.names, info: m.info || S.data.info || {}, rewards: m.rewards || S.data.rewards || null });
    show("app"); renderHeader(); startLive();
    if (fresh) { buildFilters(); applyFilters(); renderStats(); }

    const c = await api().load_collection();
    if (!c.ok) return failLoad(c);
    const same = S.data.loaded && collSig(S.data.cards) === collSig(c.cards);
    Object.assign(S.data, c, { loaded: true });
    buildFilters(); renderStats();
    if (!same) {
      applyFilters(true);
      const open = !$("modal").classList.contains("hidden") && MODAL.card && !(document.activeElement && $("modal").contains(document.activeElement) && /^(INPUT|SELECT)$/.test(document.activeElement.tagName));
      const fresh = open && S.data.cards.find((x) => x.cid === MODAL.card.cid);
      if (fresh) openModal(fresh); // la fiche ouverte montre l'état à jour de tes exemplaires (sauf si tu es en train de taper dedans)
    }
    setSync("À jour", "ok"); clearTimeout(setSync._t); setSync._t = setTimeout(() => setSync(""), 2500);
  } catch (e) {
    failLoad({ error: "Erreur inattendue : " + e });
  } finally {
    S.refreshing = false;
  }
}

/* Profil seul (1 appel) : sert au minuteur de paquets quand il arrive à zéro. */
async function refreshMe() {
  S.lastPoll = Date.now();
  const r = await api().load_me();
  if (r.ok && S.data) { S.data.me = r.me; S.data.names = r.names; S.data.info = r.info || S.data.info; S.data.rewards = r.rewards || S.data.rewards; renderHeader(); }
  else if (r.expired) sessionLost(r);
}

function renderHeader() {
  const me = S.data.me; S.meAt = Date.now();
  $("me-name").textContent = me.name || "";
  countTo($("me-coins"), me.coins);
  $("me-packs").textContent = `${me.packs ?? 0}/${me.packMax ?? "?"}`;
  renderPacks(); tickPacks(); renderBell(); renderSocialBadges();
  const tn = $("tab-trades-n"); tn.textContent = me.trades || ""; tn.classList.toggle("hidden", !me.trades); // échanges en attente
  const ini = $("me-initial"); ini.textContent = ([...(me.name || "?")][0] || "?").toUpperCase(); ini.classList.toggle("hidden", !!me.avatar);
  const av = $("me-avatar");
  if (me.avatar) { av.src = me.avatar; av.classList.remove("hidden"); av.onerror = () => av.classList.add("hidden"); }
  else av.classList.add("hidden");
}

function countTo(node, value) { // les pièces défilent jusqu'à leur nouvelle valeur au lieu de sauter
  const to = Number(value || 0), from = node.dataset.v == null ? to : Number(node.dataset.v);
  node.dataset.v = String(to);
  if (from === to || reduced()) { node.textContent = fmt(to); return; }
  const t0 = performance.now();
  const step = (t) => {
    if (node.dataset.v !== String(to)) return; // une valeur plus récente a pris la main
    const k = Math.min(1, (t - t0) / 800);
    node.textContent = fmt(Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3))));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* me.next = secondes avant le prochain paquet, au moment où le profil a été lu (S.meAt). */
function tickPacks() {
  const me = S.data && S.data.me; const t = $("me-timer");
  if (!me || me.next == null) { t.classList.add("hidden"); $("pk-next").textContent = ""; return; }
  t.classList.remove("hidden");
  const full = (me.packReserve ?? me.packs ?? 0) >= (me.packMax ?? Infinity);
  const left = Math.max(0, Math.ceil(me.next - (Date.now() - S.meAt) / 1000));
  $("me-timer-t").textContent = full ? "Réserve pleine" : clock(left);
  $("pk-next").textContent = full ? "Réserve pleine" : `Prochain paquet dans ${clock(left)}`;
  // à zéro : une relecture du profil, jamais plus d'une toutes les 5 s
  if (!full && left === 0 && Date.now() - Math.max(S.meAt, S.lastPoll) > 5000) refreshMe();
}
setInterval(tickPacks, 1000);

/* ---------------- collection ---------------- */
function buildFilters() {
  const present = [...new Set(S.data.cards.map((c) => c.rarity))].sort((a, b) => rarityRank(a) - rarityRank(b));
  const box = $("f-rarities"); box.replaceChildren();
  present.forEach((r) => box.append(el("button", {
    class: "chip" + (S.rarities.has(r) ? " on" : ""), style: `--c:${color(r)}`, text: label(r),
    onclick: (e) => { S.rarities.has(r) ? S.rarities.delete(r) : S.rarities.add(r); e.currentTarget.classList.toggle("on"); applyFilters(); },
  })));
  const tagSel = $("f-tag"); const cur = tagSel.value; tagSel.replaceChildren(el("option", { value: "", text: "Tous les tags" }));
  S.data.tags.forEach((t) => tagSel.append(el("option", { value: String(t.id), text: t.name })));
  tagSel.value = cur;
}

/* keep = true : on reconstruit la liste sans faire sauter l'écran (mise à jour en arrière-plan). */
function applyFilters(keep = false) {
  const grid = $("grid");
  if (!S.data.loaded) { // rien à trier encore : des cartes fantômes plutôt qu'un écran vide
    S.filtered = []; S.shown = 0; $("f-count").textContent = "Chargement…";
    grid.replaceChildren(...Array.from({ length: 14 }, () => el("div", { class: "card sk" })));
    return;
  }
  const prev = S.shown, y = window.scrollY;
  const q = $("f-search").value.trim().toLowerCase();
  const tag = $("f-tag").value; const dups = $("f-dups").checked; const sort = $("f-sort").value;
  const list = S.data.cards.filter((c) =>
    (!S.rarities.size || S.rarities.has(c.rarity)) &&
    (!q || c.name.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q)) &&
    (!tag || c.tags.map(String).includes(tag)) &&
    (!dups || c.copies > 1));
  const by = {
    reads: (a, b) => b.reads - a.reads,
    rarity: (a, b) => rarityRank(a.rarity) - rarityRank(b.rarity) || Number(b.shiny) - Number(a.shiny) || b.reads - a.reads,
    name: (a, b) => a.name.localeCompare(b.name, "fr"),
    copies: (a, b) => b.copies - a.copies || b.reads - a.reads,
  }[sort];
  list.sort(by);
  S.filtered = list; S.shown = 0; grid.replaceChildren();
  $("f-count").textContent = `${fmt(list.length)} carte${list.length > 1 ? "s" : ""}`;
  if (!list.length) grid.append(el("div", { class: "empty", text: "Aucune carte ne correspond." }));
  renderMore(!keep); // une mise à jour en arrière-plan ne rejoue pas l'entrée des cartes
  if (keep) { while (S.shown < Math.min(prev, list.length)) renderMore(); window.scrollTo(0, y); }
}

/* La face d'une carte : la même dans la collection, la fiche et l'ouverture d'un paquet. */
function cardNode(c, onclick = () => openModal(c)) {
  const pic = el("div", { class: "pic" });
  const initial = () => pic.append(el("span", { class: "initial", text: [...c.name][0] || "?" }));
  if (c.img) {
    pic.style.backgroundImage = `url("${c.img.replace(/"/g, "%22")}")`;
    const probe = new Image(); probe.onerror = () => { pic.style.backgroundImage = ""; initial(); }; probe.src = c.img; // image absente ou refusée : l'initiale
  } else initial();
  const props = { class: "card" + (isTop(c) ? " top" : "") + (c.shiny ? " sh" : ""), style: `--c:${color(c.rarity)}` };
  if (onclick) Object.assign(props, {
    onclick, tabindex: "0", role: "button",
    onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onclick(e); } },
  });
  return el("div", props,
    pic,
    c.copies > 1 ? el("span", { class: "copies", text: `×${c.copies}` }) : null,
    el("div", { class: "meta" },
      el("span", { class: "rar" }, label(c.rarity), c.shiny ? icon("spark") : null),
      el("h3", { text: c.name }),
      el("div", { class: "foot" },
        el("span", { class: "reads", title: "Lectures de l'article Wikipédia" }, icon("eye"), compact(c.reads)),
        c.locked ? el("span", { title: "Verrouillée" }, icon("lock")) : null)));
}

function renderMore(enter = false) {
  const grid = $("grid"); const end = Math.min(S.shown + PAGE, S.filtered.length);
  const frag = document.createDocumentFragment();
  for (let i = S.shown; i < end; i++) {
    const n = cardNode(S.filtered[i]);
    if (enter && i < 24) { n.classList.add("enter"); n.style.setProperty("--k", String(i)); } // les premières cartes arrivent en cascade
    frag.append(n);
  }
  grid.append(frag); S.shown = end;
}
new IntersectionObserver((e) => { if (e[0].isIntersecting && S.data && S.shown < S.filtered.length) renderMore(); }, { rootMargin: "600px" })
  .observe($("sentinel"));

/* La carte survolée s'incline vers le pointeur, et son reflet le suit (une seule écoute pour toutes les cartes). */
let tilted = null;
const untiltCard = (c) => ["--tx", "--ty"].forEach((k) => c.style.removeProperty(k));
document.addEventListener("pointermove", (e) => {
  const c = e.target.closest ? e.target.closest(".card[role=button], .plate > .card") : null;
  if (c !== tilted) { if (tilted) untiltCard(tilted); tilted = c; }
  if (!c || reduced()) return;
  const r = c.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
  c.style.setProperty("--ty", `${((x - 0.5) * 14).toFixed(2)}deg`); c.style.setProperty("--tx", `${((0.5 - y) * 14).toFixed(2)}deg`);
  c.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`); c.style.setProperty("--my", `${(y * 100).toFixed(1)}%`);
}, { passive: true });

let modalFrom = null; // ce qui avait le focus avant l'ouverture : on le lui rend à la fermeture
function openModal(c) {
  if ($("modal").classList.contains("hidden")) modalFrom = document.activeElement;
  // ce qui dépend de ta collection (exemplaires, tags, cadenas) vient de ta collection, pas de la carte affichée
  // (une carte du marché ou d'un échange n'est pas forcément à toi)
  const own = S.data.cards.find((x) => x.cid === c.cid);
  const tagNames = ((own && own.tags) || []).map((id) => (S.data.tags.find((t) => t.id === id) || {}).name).filter(Boolean);
  const facts = [["Lectures", fmt(c.reads)], own ? ["Exemplaires", String(own.copies)] : null, tagNames.length ? ["Tags", tagNames.join(", ")] : null,
    c.lang && c.lang !== "fr" ? ["Langue", c.lang] : null].filter(Boolean);
  const chips = [c.shiny && "Chromatique", own && own.locked && "Verrouillée"].filter(Boolean);
  MODAL.card = c; $("modal-body").dataset.cid = c.cid || "";
  $("modal-body").style.setProperty("--c", color(c.rarity)); // la fiche baigne dans la couleur de la rareté…
  const art = el("div", { class: "plate-art" }); // …et dans un reflet flou de l'image
  if (c.img) art.style.backgroundImage = `url("${c.img.replace(/"/g, "%22")}")`;
  $("modal-body").replaceChildren(
    art,
    el("button", { class: "icon-btn x", "aria-label": "Fermer", title: "Fermer (Échap)", onclick: closeModal }, icon("close")),
    cardNode(c, null),
    el("div", { class: "plate-info" },
      el("h2", { text: c.name }),
      c.desc ? el("p", { class: "desc", text: c.desc }) : null,
      el("div", { class: "row" },
        c.url ? el("button", { class: "btn primary", text: "Ouvrir sur Wikipédia", onclick: () => api().open_url(c.url) }) : null,
        watchButton(c)),
      el("dl", { class: "facts" }, facts.flatMap(([k, v]) => [el("dt", { text: k }), el("dd", { text: v })])),
      chips.length ? el("div", { class: "row" }, chips.map((t) => el("span", { class: "st", text: t }))) : null,
      el("div", { id: "sheet-extra", class: "sheet-extra" })));
  $("modal").classList.remove("hidden");
  loadCardSheet(c);
}
function closeModal() {
  $("modal").classList.add("hidden");
  if (modalFrom && modalFrom.isConnected && modalFrom.focus) modalFrom.focus({ preventScroll: true });
  modalFrom = null;
}

/* ---------------- statistiques ---------------- */
function fig(l, n, ...subs) {
  return el("div", { class: "fig" }, el("div", { class: "n", text: n }), el("div", { class: "l", text: l }),
    subs.filter(Boolean).map((s) => el("div", { class: "s", text: s })));
}

function listRows(items, valueOf) {
  return items.map((c) => el("div", { class: "list-row", style: `--c:${color(c.rarity)}`, onclick: () => { const full = S.data.cards.find((x) => x.cid === c.cid); if (full) openModal(full); } },
    el("span", { class: "t", text: c.name }), el("span", { class: "n" }, valueOf(c))));
}

function recycleFig() { // estimation : les doublons se recyclent sur le site, pas ici
  if (!(S.data.info && S.data.info.bank)) return null;
  const rc = recycling();
  const f = fig("Doublons recyclables", `${fmt(rc.total)} Wikiki`, plural(rc.n, "exemplaire en trop", "exemplaires en trop"), "hors verrouillées et chromatiques");
  if (rc.n) f.append(el("button", { class: "link", text: "Recycler les doublons…", onclick: openDups }));
  return f;
}

function renderStats() {
  const { stats, rank } = S.data; const pane = $("tab-stats");
  if (!stats) { pane.replaceChildren(el("div", { class: "empty", text: "Chargement des statistiques…" })); return; }
  const maxU = Math.max(1, ...stats.rarities.map((r) => r.unique));
  const hero = fig("Classement", rank.rank ? `#${fmt(rank.rank)}` : "—", rank.total ? `sur ${fmt(rank.total)} joueurs` : "",
    rank.toNext != null && rank.nextName ? `${fmt(rank.toNext)} points pour dépasser ${rank.nextName}` : "");
  hero.classList.add("hero");
  pane.replaceChildren(
    el("div", { class: "ledger" }, hero, fig("Points", fmt(rank.points)),
      fig("Cartes uniques", fmt(stats.unique)),
      fig("Exemplaires", fmt(stats.copies), `${fmt(stats.duplicates)} cartes en doublon`, `+${fmt(stats.extra_copies)} exemplaires en trop`),
      recycleFig(),
      fig("Chromatiques", fmt(stats.shiny), `${fmt(stats.locked)} verrouillées`)),
    el("div", { class: "cols" },
      el("div", {}, el("h2", { class: "sec", text: "Répartition par rareté" }),
        stats.rarities.map((r) => el("div", { class: "bar-row", style: `--c:${color(r.code)}` },
          el("span", { class: "lab", text: r.label }), el("div", { class: "bar" }, el("i", { style: `width:${(r.unique / maxU) * 100}%` })),
          el("span", { class: "num", text: `${fmt(r.unique)} carte${r.unique > 1 ? "s" : ""}, ×${fmt(r.copies)}` })))),
      el("div", {}, el("h2", { class: "sec", text: "Les plus lues" }), listRows(stats.top_reads, (c) => [icon("eye"), compact(c.reads)]),
        el("h2", { class: "sec", text: "En plusieurs exemplaires" }),
        stats.top_copies.length ? listRows(stats.top_copies, (c) => `×${c.copies}`) : el("div", { class: "empty", text: "Aucun doublon." }))));
}

/* ---------------- init ---------------- */
function bindUser() { // menu du compte : actualiser, ouvrir le site, se déconnecter
  const menu = $("user-menu"), btn = $("btn-user");
  const close = () => { menu.classList.add("hidden"); btn.setAttribute("aria-expanded", "false"); };
  btn.onclick = (e) => { e.stopPropagation(); btn.setAttribute("aria-expanded", String(!menu.classList.toggle("hidden"))); };
  document.addEventListener("click", (e) => { if (!menu.contains(e.target)) close(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  $("btn-refresh").onclick = () => { close(); refresh(); };
  $("btn-site").onclick = () => { close(); openSite(); };
  $("btn-logout").onclick = () => { close(); logout(); };
}

function bind() {
  $("btn-login").onclick = startLogin; $("btn-cookie").onclick = useCookies;
  $("btn-quick2").onclick = () => openQuick();
  bindUser();
  ["f-search", "f-sort", "f-tag", "f-dups"].forEach((id) => $(id).addEventListener(id === "f-search" ? "input" : "change", () => applyFilters()));
  document.querySelectorAll(".tab").forEach((b) => b.onclick = () => { if (b.dataset.tab === "profile") { PF.name = null; PF.data = null; } setTab(b.dataset.tab); });
  bindPacks(); bindLive(); bindSocial(); bindExtras(); bindActions(); bindCommunity();
  $("modal").addEventListener("click", (e) => { if (e.target === $("modal")) closeModal(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
}

async function init() {
  bind();
  try {
    await loadPrefs(); // avant tout affichage : tri, vue du marché, son
    const cached = await api().cache_get(); // dernière collection connue : affichage instantané
    if (cached.ok && cached.data && cached.data.cards) {
      S.data = Object.assign(cached.data, { loaded: true });
      S.data.me.next = null; // le minuteur d'hier ne dit rien : il revient avec les données fraîches
      show("app"); renderHeader(); buildFilters(); applyFilters(); renderStats();
      return refresh();
    }
    busy("Démarrage…");
    const st = await api().status();
    busy(null);
    if (st.logged_in) await refresh(); else show("login");
  } catch (e) { busy(null); show("login"); loginMsg("Erreur de démarrage : " + e, true); }
}
if (window.pywebview && window.pywebview.api) init(); else window.addEventListener("pywebviewready", init);
