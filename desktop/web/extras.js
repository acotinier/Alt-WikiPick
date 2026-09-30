"use strict";
/* Fonctions locales qui n'existent pas sur le site : préférences mémorisées, journal des paquets et chance
   mesurée, valeur de recyclage des doublons, recherche rapide (Ctrl+K), son, cartes surveillées.
   Tout reste sur cet ordinateur (fichiers dans %APPDATA%\WikiPickDesktop) : aucune écriture vers le site.
   Chargé AVANT app.js : rien ne s'exécute ici au chargement, S / $ / el… n'existent pas encore. */

const PREFS = {};
const MODAL = { card: null }; // la carte de la fiche ouverte
const SND = { on: false, ctx: null };
const WATCH = { list: [] }; // [{cid, name}]
const PJ = { packs: [], shown: 12 };
const QK = { items: [], sel: 0 };
// 1 à 9 au clavier : dans cet ordre (les trois derniers seulement par la recherche rapide)
const QUICK_TABS = [["collection", "Collection"], ["packs", "Paquets"], ["market", "Marché"], ["trades", "Échanges"], ["rank", "Classement"], ["stats", "Statistiques"],
  ["messages", "Messages"], ["friends", "Amis"], ["guild", "Guilde"], ["arena", "Arène"], ["profile", "Profil"], ["rewards", "Récompenses"]];

/* ---------------- préférences ---------------- */
const savePref = (key, value) => { PREFS[key] = value; api().prefs_set(key, value); };
const hasOption = (sel, v) => [...sel.options].some((o) => o.value === v); // un fichier de préférences édité à la main ne casse rien
async function loadPrefs() {
  try { const r = await api().prefs_get(); if (r.ok) Object.assign(PREFS, r.prefs); } catch (e) { /* pas de préférences : les valeurs par défaut */ }
  const cs = $("f-sort"); if (hasOption(cs, PREFS.collection_sort)) cs.value = PREFS.collection_sort;
  const m = LV.market, ms = $("m-sort");
  if (hasOption(ms, PREFS.market_sort)) { m.sort = PREFS.market_sort; ms.value = m.sort; }
  if (["grid", "dense", "list"].includes(PREFS.market_view)) m.view = PREFS.market_view;
  SND.on = PREFS.sound === true; renderSound();
}

/* ---------------- son (optionnel) ---------------- */
function renderSound() { $("sound-t").textContent = SND.on ? "Sons : activés" : "Sons : désactivés"; }
function audioReady() { // le navigateur n'autorise le son qu'après un geste de l'utilisateur
  if (!SND.on) return;
  try {
    SND.ctx = SND.ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (SND.ctx.state === "suspended") SND.ctx.resume();
  } catch (e) { SND.ctx = null; }
}
function ping(kind) { // deux notes qui montent (bonne nouvelle), qui descendent (mauvaise), une seule sinon
  if (!SND.on || !SND.ctx || SND.ctx.state !== "running") return;
  const c = SND.ctx, t = c.currentTime, notes = kind === "good" ? [660, 880] : kind === "bad" ? [440, 330] : [587];
  notes.forEach((f, i) => {
    const o = c.createOscillator(), g = c.createGain(), at = t + i * 0.13;
    o.type = "sine"; o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(0.1, at + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, at + 0.3);
    o.connect(g); g.connect(c.destination); o.start(at); o.stop(at + 0.32);
  });
}
function toggleSound() {
  SND.on = !SND.on; savePref("sound", SND.on); renderSound(); audioReady();
  if (SND.on) ping("good"); // un aperçu, pour savoir à quoi s'attendre
}

/* ---------------- adresse Wikipédia d'une carte (pour les cartes qui n'en ont pas) ---------------- */
function wikiUrl(cid) {
  const i = String(cid).indexOf(":"), lang = String(cid).slice(0, i), title = String(cid).slice(i + 1);
  if (i < 1 || !title || !/^[a-z-]{2,12}$/.test(lang)) return null;
  return `https://${lang}.wikipedia.org/wiki/` + encodeURIComponent(title.replace(/ /g, "_")).replace(/%(2C|3A|28|29|2F)/g, (m) => decodeURIComponent(m));
}
// la carte complète (exemplaires, tags…) si elle est dans la collection, sinon une fiche minimale
const fullCard = (c) => (S.data && S.data.cards.find((x) => x.cid === c.cid)) || { desc: "", copies: 1, locked: false, tags: [], lang: "", url: wikiUrl(c.cid), ...c };

/* ---------------- fiche enrichie d'une carte : un appel /api/card à l'ouverture, comme le site (lecture seule) ---------------- */
const SHEETS = new Map(); // cid -> { ts, data } : une carte rouverte dans la minute ne rappelle pas le site
const SHEET_TTL = 60000;
const COPY_STATE = { free: "Libre", locked: "Verrouillée", auction: "Aux enchères", exclusive: "Exclusive" };
const parisDate = (ts) => { // comme le site : heure de Paris
  const d = new Date(ts * 1000), o = { timeZone: "Europe/Paris" };
  return `${d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", ...o })} à ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", ...o })}`;
};
function provText(m) { // d'où vient cet exemplaire
  const when = m.ts ? ` le ${parisDate(m.ts)}` : "";
  if (m.via === "paquet") return `Obtenue dans un paquet${when}`;
  if (m.via === "recompense") return `Obtenue en récompense${when}`;
  if (m.via === "enchere") return `Achetée${m.price != null ? ` ${fmt(m.price)} Wikiki` : ""} aux enchères${m.from ? ` à ${m.from}` : ""}${m.lot ? " (dans un lot)" : ""}${when}`;
  if (m.via === "echange") return `Reçue par échange${m.from ? ` avec ${m.from}` : ""}${when}`;
  return `Obtenue${when}`;
}
function sheetNodes(c, d) {
  const kids = [], article = [];
  if (d.extract) {
    const p = el("p", { class: "extract", text: d.extract });
    article.push(p);
    if (d.extract.length > 380) article.push(el("button", { class: "link", text: "Lire la suite", onclick: (e) => { p.classList.toggle("open"); e.target.textContent = p.classList.contains("open") ? "Réduire" : "Lire la suite"; } }));
  }
  const acts = sheetActions(c, d); // enchérir, recycler, verrouiller… (actions.js)
  kids.push(d.mine.length
    ? el("div", { class: "mycopies" }, el("h3", { text: `Tes exemplaires (${d.mine.length})` }), ...d.mine.map((m) => el("p", { class: "copy" },
      el("span", { class: "st " + m.state, text: COPY_STATE[m.state] || m.state }), m.shiny ? icon("spark") : null, el("span", { text: provText(m) }))))
    : el("p", { class: "muted", text: "Tu ne possèdes pas encore cette carte." }));
  if (acts) kids.push(acts); // juste après tes exemplaires : c'est ce qu'on vient faire ici
  kids.push(...article);
  [d.friends.length && `Chez ${d.friends.length > 1 ? "tes amis" : "ton ami"} : ${d.friends.join(", ")}`,
    d.guild.length && `Dans ta guilde : ${d.guild.join(", ")}`,
    d.friend_wishes.length && `${d.friend_wishes.length > 1 ? "Tes amis la souhaitent" : "Ton ami la souhaite"} : ${d.friend_wishes.join(", ")}`,
    d.wished && "Dans ta liste de souhaits sur le site."].filter(Boolean).forEach((t) => kids.push(el("p", { class: "social", text: t })));
  if (d.auctions.length) kids.push(el("div", { class: "mauc" }, el("h3", { text: `Aux enchères en ce moment (${d.auctions.length})` }),
    ...d.auctions.slice(0, 5).map((a) => el("p", { class: "copy" }, el("span", { class: "price" }, icon("coin"), fmt(a.price)),
      el("span", { class: "muted", text: `par ${a.seller || "?"}` }), a.status === "live" ? el("span", { class: "timer", "data-ends": String(a.ends_at) }) : null, bidControls(a))),
    el("button", { class: "link", text: "Voir sur le marché", onclick: () => { closeModal(); showOnMarket(c.name); } })));
  kids.push(el("div", { id: "pro-extra", class: "pro-extra" }));
  return kids;
}
async function loadCardSheet(c) {
  const host = $("sheet-extra");
  if (!host || !c.cid) return;
  const paint = (d) => { if (host.isConnected && $("modal-body").dataset.cid === c.cid) { host.replaceChildren(...sheetNodes(c, d)); tickMarket(); loadProMarket(c); } };
  const hit = SHEETS.get(c.cid);
  if (hit && Date.now() - hit.ts < SHEET_TTL) return paint(hit.data);
  host.replaceChildren(el("p", { class: "muted", text: "Chargement des détails…" }));
  const r = await api().load_card(c.cid);
  if (r.expired) return sessionLost(r);
  if (!r.ok) { if (host.isConnected) host.replaceChildren(el("p", { class: "muted", text: "Détails indisponibles pour le moment." })); return; }
  SHEETS.set(c.cid, { ts: Date.now(), data: r }); paint(r);
}

/* ---------------- journal des paquets et chance mesurée ---------------- */
async function loadJournal() {
  const r = await api().pack_history();
  if (!r.ok) return;
  PJ.packs = r.packs; PJ.shown = 12; renderJournal();
}
const dec = (x) => (x > 0 && x < 0.1 ? "< 0,1" : x.toLocaleString("fr-FR", { maximumFractionDigits: 1 }));
function luckRows(packs) { // paquets contenant au moins une carte de la rareté, contre les chances annoncées par le site
  const info = (S.data && S.data.info) || {}, odds = info.odds || {}, n = packs.length, rows = [];
  const line = (key, name, found, pct) => el("div", { class: "lk", style: `--c:${key ? color(key) : "var(--text)"}` },
    el("span", { class: "lab", text: name }), el("span", { class: "got", text: `${found} sur ${n}` }),
    el("span", { class: "exp", text: `attendu : ${dec((n * pct) / 100)}` }));
  for (const r of RARITY_ORDER) {
    if (odds[r] == null || odds[r] >= 50) continue; // les raretés qui sortent presque à chaque paquet ne disent rien
    rows.push(line(r, label(r), packs.filter((p) => p.cards.some((c) => c.rarity === r)).length, odds[r]));
  }
  if (info.shinyOdds) rows.push(line(null, "Chromatique", packs.filter((p) => p.cards.some((c) => c.shiny)).length, info.shinyOdds));
  return rows;
}
function miniCard(c) {
  const t = el("button", { class: "thumb mini" + (c.new ? " new" : ""), style: `--c:${color(c.rarity)}`, title: `${c.name} (${label(c.rarity)})`, "aria-label": c.name,
    onclick: () => openModal(fullCard(c)) });
  if (c.img) t.style.backgroundImage = `url("${c.img.replace(/"/g, "%22")}")`;
  return t;
}
function renderJournal() {
  const box = $("pk-journal"), packs = PJ.packs;
  box.classList.toggle("hidden", !packs.length);
  if (!packs.length) return;
  const cards = packs.reduce((n, p) => n + p.cards.length, 0), fresh = packs.reduce((n, p) => n + p.cards.filter((c) => c.new).length, 0);
  $("pj-sum").textContent = `${plural(packs.length, "paquet")} ouvert${packs.length > 1 ? "s" : ""} avec l'appli : ${plural(cards, "carte")}, dont ${plural(fresh, "nouvelle")}.`
    + (packs.length < 10 ? " La comparaison avec les chances du site devient parlante à partir d'une dizaine de paquets." : "");
  const luck = luckRows(packs);
  $("pj-luck").replaceChildren(...(luck.length ? [el("h3", { text: "Ta chance, mesurée" }), ...luck] : []));
  $("pj-list").replaceChildren(...packs.slice(0, PJ.shown).map((p) => el("div", { class: "pj-row" },
    el("small", { text: ago(p.ts, Date.now() / 1000) }), // l'horodatage vient de cet ordinateur, pas du serveur
    el("div", { class: "pj-cards" }, [...p.cards].sort((a, b) => rarityRank(a.rarity) - rarityRank(b.rarity)).map(miniCard)))));
  $("pj-more").classList.toggle("hidden", packs.length <= PJ.shown);
}

/* ---------------- doublons recyclables (estimation, lecture seule) ---------------- */
function recycling() { // exemplaires en trop x valeur de recyclage du site ; hors verrouillées, chromatiques et exclusives
  const bank = (S.data.info && S.data.info.bank) || {};
  let n = 0, total = 0;
  for (const c of S.data.cards) {
    if (c.locked || c.shiny || c.copies < 2 || bank[c.rarity] == null) continue;
    n += c.copies - 1; total += (c.copies - 1) * bank[c.rarity];
  }
  return { n, total };
}

/* ---------------- cartes surveillées ---------------- */
async function loadWatch() {
  const r = await api().watch_get();
  if (r.ok) { WATCH.list = r.list; renderWatch(); }
}
function renderWatch() {
  const n = WATCH.list.length, b = $("m-watch-n");
  b.textContent = String(n); b.classList.toggle("hidden", !n);
  $("watch-list").replaceChildren(...(n ? WATCH.list.map((w) => el("div", { class: "nitem watch" },
    el("div", { class: "tx" }, el("div", { text: w.name }), el("small", { text: w.cid })),
    el("div", { class: "acts" },
      el("button", { class: "btn small", text: "Voir sur le marché", onclick: () => { closeWatch(); showOnMarket(w.name); } }),
      el("button", { class: "btn small ghost", text: "Retirer", onclick: () => setWatch(w.cid, w.name, false) }))))
    : [el("div", { class: "empty", text: "Aucune carte surveillée. Ouvre la fiche d'une carte et clique sur « Surveiller »." })]));
}
async function setWatch(cid, name, on) {
  const r = await api().watch_set(cid, name, on);
  if (!r.ok) return toast(r.error || "Impossible de modifier la surveillance");
  WATCH.list = r.list; renderWatch(); refreshWatchButton(cid, name);
}
function refreshWatchButton(cid, name) { // le bouton de la fiche ouverte suit la liste
  const old = $("modal").querySelector("[data-watch]");
  if (old) old.replaceWith(watchButton({ cid, name }));
}
function watchButton(c) { // à mettre dans la fiche d'une carte
  if (!c.cid) return null;
  const on = WATCH.list.some((w) => w.cid === c.cid);
  return el("button", { class: "btn", "data-watch": "1", onclick: () => setWatch(c.cid, c.name, !on) }, icon("eye"), on ? "Ne plus surveiller" : "Surveiller aux enchères");
}
function watchAlert(d) { // une carte surveillée vient d'être mise aux enchères (le flux ne nous la transmet que pour elles)
  if (d.what !== "new" || !d.cid) return;
  const w = WATCH.list.find((x) => x.cid === d.cid);
  if (!w) return;
  const text = `« ${w.name} » vient d'être mise aux enchères.`;
  LV.local.unshift({ id: 0, type: "watch", text, tone: "good", link: "", read: false, created: nowSrv() });
  LV.localUnread++; renderBell(); renderNotifs();
  toast(text, "good"); ping("good");
}
const closeWatch = () => $("watch-panel").classList.add("hidden");
function showOnMarket(name) { // cherche cette carte parmi toutes les enchères en cours
  const m = LV.market; m.scope = "live"; m.q = name; $("m-search").value = name;
  setTab("market");
}

/* ---------------- recherche rapide : Ctrl+K ---------------- */
function openQuick() {
  if (!S.data || !$("login").classList.contains("hidden")) return;
  $("quick").classList.remove("hidden"); $("q-input").value = ""; QK.sel = 0; renderQuick(); $("q-input").focus();
}
const closeQuick = () => $("quick").classList.add("hidden");
function renderQuick() {
  const q = $("q-input").value.trim().toLowerCase(), items = [];
  if (q) S.data.cards.filter((c) => c.name.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q))
    .sort((a, b) => rarityRank(a.rarity) - rarityRank(b.rarity) || b.reads - a.reads).slice(0, 8).forEach((c) => items.push({ card: c }));
  QUICK_TABS.filter(([, t]) => !q || t.toLowerCase().includes(q)).forEach(([key, t]) => items.push({ tab: key, text: `Aller à ${t}` }));
  QK.items = items; QK.sel = Math.max(0, Math.min(QK.sel, items.length - 1));
  $("q-list").replaceChildren(...(items.length ? items.map((it, i) => el("div", {
    class: "qitem" + (i === QK.sel ? " on" : ""), role: "option", "aria-selected": String(i === QK.sel),
    style: it.card ? `--c:${color(it.card.rarity)}` : "", onclick: () => runQuick(it), onmousemove: () => { if (QK.sel !== i) { QK.sel = i; renderQuick(); } },
  }, it.card ? [el("span", { class: "dot" }), el("b", { text: it.card.name }), el("small", { text: label(it.card.rarity) })] : [el("b", { text: it.text })]))
    : [el("div", { class: "empty", text: "Aucun résultat." })]));
}
function runQuick(it) {
  if (it.tab === "profile") PF.name = null;
  closeQuick();
  if (it.card) openModal(it.card); else setTab(it.tab);
}

async function exportCollection() {
  $("user-menu").classList.add("hidden");
  const r = await api().export_collection();
  toast(r.ok ? `Collection exportée (${plural(r.count, "carte")}) : ${r.path}` : (r.error || "Export impossible"), r.ok ? "good" : "error");
}

function bindExtras() {
  $("btn-export").onclick = exportCollection;
  $("btn-sound").onclick = toggleSound;
  $("btn-quick").onclick = () => { $("user-menu").classList.add("hidden"); openQuick(); };
  $("f-sort").addEventListener("change", (e) => savePref("collection_sort", e.target.value));
  document.addEventListener("pointerdown", audioReady); // premier geste : le son est autorisé
  $("m-watch").onclick = (e) => { e.stopPropagation(); $("watch-panel").classList.toggle("hidden"); };
  document.addEventListener("click", (e) => {
    const p = $("watch-panel");
    if (!p.classList.contains("hidden") && !p.contains(e.target) && !$("m-watch").contains(e.target)) closeWatch();
  });
  $("pj-more").onclick = () => { PJ.shown += 24; renderJournal(); };
  $("quick").addEventListener("click", (e) => { if (e.target === $("quick")) closeQuick(); });
  $("q-input").addEventListener("input", () => { QK.sel = 0; renderQuick(); });
  $("q-input").addEventListener("keydown", (e) => {
    const n = QK.items.length;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (n) { QK.sel = (QK.sel + (e.key === "ArrowDown" ? 1 : n - 1)) % n; renderQuick(); } }
    else if (e.key === "Enter") { e.preventDefault(); if (QK.items[QK.sel]) runQuick(QK.items[QK.sel]); }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeQuick(); closeWatch(); closeDialog(); return; }
    const t = e.target || {}, typing = /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openQuick(); return; }
    if (typing || e.ctrlKey || e.metaKey || e.altKey || !S.data || !$("login").classList.contains("hidden")) return;
    if (e.key === "/") { e.preventDefault(); openQuick(); return; }
    const tab = +e.key >= 1 ? QUICK_TABS[+e.key - 1] : null; // 1 à 9 : les onglets
    if (tab && $("modal").classList.contains("hidden") && $("quick").classList.contains("hidden")) setTab(tab[0]);
  });
}
