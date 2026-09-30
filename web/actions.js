"use strict";
/* Actions MANUELLES qui écrivent sur le site : miser, mettre aux enchères, annuler, échanger, recycler, verrouiller…
   Règles : un clic = une action ; tout ce qui engage des pièces ou des cartes demande une deuxième confirmation ;
   une seule action à la fois ; jamais de boucle, jamais de rejeu automatique ; le résultat affiché est celui du serveur.
   Les fonctions WIKI-PRO (marché, paquet doré) n'apparaissent que si ton profil les indique.
   Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const ACT = { busy: false, error: "" };
const CONFIRM_MS = 4500; // la confirmation retombe seule
const EXCLUSIVE = ["EXC", "WBC", "SIXSEVEN"]; // ni vendues, ni recyclées, ni échangées
const RECYCLE_CONFIRM = ["R", "SR", "UR", "L", "M"]; // au-dessus d'une inhabituelle (et toute chromatique) : on confirme
const DURATIONS = [["10m", "10 minutes"], ["30m", "30 minutes"], ["1h", "1 heure"], ["6h", "6 heures"], ["12h", "12 heures"], ["24h", "24 heures"]];
const bankOf = (r) => ((S.data && S.data.info && S.data.info.bank) || {})[r];

/* ---------------- briques communes ---------------- */
function disarm(b) {
  clearTimeout(b._t); delete b.dataset.armed; b.classList.remove("armed");
  if (b.dataset.label) b.textContent = b.dataset.label;
}
function armed(b, text) { // première pression : le bouton demande confirmation ; seconde (dans les 4,5 s) : vrai
  if (b.dataset.armed) { disarm(b); return true; }
  b.dataset.label = b.textContent; b.dataset.armed = "1"; b.classList.add("armed"); b.textContent = text;
  b._t = setTimeout(() => disarm(b), CONFIRM_MS);
  return false;
}
function actBtn(text, cls, handler, confirm, check) { // confirm : texte de la confirmation (ou rien : action sans enjeu) ; check : message d'erreur avant toute confirmation
  return el("button", { class: "btn " + cls, text, onclick: (e) => {
    e.stopPropagation();
    const b = e.currentTarget, bad = check && check();
    if (bad) { disarm(b); return toast(bad); }
    if (confirm && !armed(b, typeof confirm === "function" ? confirm() : confirm)) return;
    handler(b);
  } });
}
const tag = (b, name) => { b.dataset.act = name; return b; }; // identifiant stable : le texte d'un bouton armé change
async function act(btn, call, onOk) { // une seule action à la fois ; l'erreur est celle du serveur
  if (ACT.busy) { toast("Une action est déjà en cours."); return null; }
  ACT.busy = true; ACT.error = ""; if (btn) btn.disabled = true;
  try {
    const r = await call();
    if (r.expired) { sessionLost(r); return null; }
    if (!r.ok) { ACT.error = r.error || "Action impossible"; toast(ACT.error); return null; }
    if (onOk) await onOk(r);
    refreshOpenSheet();
    return r;
  } catch (e) {
    ACT.error = "Erreur inattendue : " + e; toast(ACT.error); return null;
  } finally {
    ACT.busy = false; if (btn && btn.isConnected) { btn.disabled = false; disarm(btn); }
  }
}
function refreshOpenSheet() { // la fiche ouverte se relit (les exemplaires ont pu changer)
  const c = MODAL.card;
  if (!c || $("modal").classList.contains("hidden")) return;
  SHEETS.delete(c.cid); loadCardSheet(c);
}
const numberField = (value, ph, w = 96) => el("input", { class: "field", type: "number", min: "1", step: "1", inputmode: "numeric", placeholder: ph, value: String(value ?? ""), style: `width:${w}px` });
const posInt = (v) => Math.floor(Number(v) || 0);

/* ---------------- dialogue commun (corbeille, doublons, journal, échange) ---------------- */
let dialogFrom = null;
function openDialog(title, body, wide = false) {
  if ($("dialog").classList.contains("hidden")) dialogFrom = document.activeElement;
  const d = $("dialog-body"); d.className = "dialog" + (wide ? " wide" : "");
  d.replaceChildren(el("header", { class: "dhd" }, el("h2", { text: title }),
    el("button", { class: "icon-btn", "aria-label": "Fermer", title: "Fermer (Échap)", onclick: closeDialog }, icon("close"))), body);
  $("dialog").classList.remove("hidden");
}
function closeDialog() {
  if (CH.res) { const f = CH.res; CH.res = null; f(null); } // Échap ou clic à côté pendant la vérification : on renonce au paquet
  $("dialog").classList.add("hidden");
  if (dialogFrom && dialogFrom.isConnected && dialogFrom.focus) dialogFrom.focus({ preventScroll: true });
  dialogFrom = null;
}

/* ---------------- enchères : miser, annuler, changer le prix ---------------- */
async function syncAuction(id) { // relit CETTE enchère : la tuile montre le vrai montant (une mise a pu passer avant la nôtre)
  const r = await api().auction_get(id);
  if (!r.ok || !r.auction || !r.auction.id) return null;
  const a = LV.market.items.find((x) => x.id === id);
  if (a) { const n = r.auction; Object.assign(a, { price: n.price, leader: n.leader, min: n.min, bids: n.bids, leading: n.leading, ends_at: n.ends_at, status: n.status }); swapTile(a); }
  return r.auction;
}
async function placeBid(id, amount, btn) {
  const ok = await act(btn, () => api().bid(id, amount), (r) => {
    toast(r.extended ? "Mise placée ! Le chrono repart à 1 minute." : "Mise placée : tu es en tête.", "good");
    ping("good"); refreshMeSoon();
  });
  const a = await syncAuction(id);
  if (!ok && a) {
    if (a.leading) toast("Tu es déjà en tête de cette enchère.");
    else if (a.min && /minimale/i.test(ACT.error)) toast(`Quelqu'un a misé avant toi : il faut maintenant ${fmt(a.min)} Wikiki.`);
  }
}
function dropAuction(id) {
  LV.market.items = LV.market.items.filter((a) => a.id !== id);
  if (LV.market.total) LV.market.total--;
  if (S.tab === "market") renderMarket();
}
function priceEditor(a) { // seulement tant que personne n'a misé
  const input = numberField(a.price, "Nouveau départ", 110);
  const btn = actBtn("Changer", "small", (b) => {
    const v = posInt(input.value);
    act(b, () => api().auction_price(a.id, v), () => { toast(`Mise de départ changée : ${fmt(v)} Wikiki.`, "good"); return syncAuction(a.id); });
  }, null, () => (posInt(input.value) < 1 ? "Indique une mise de départ d'au moins 1 Wikiki." : ""));
  btn.title = "Changer la mise de départ (tant que personne n'a misé)"; input.title = "Nouvelle mise de départ";
  return el("span", { class: "priceedit" }, input, btn);
}
function bidControls(a) { // ce qu'on peut faire d'une enchère en cours : la miser, ou (si elle est à toi) l'annuler
  if (a.hist || a.status !== "live") return null;
  if (a.mine) {
    const kids = [actBtn("Annuler la vente", "small danger", (b) => act(b, () => api().auction_cancel(a.id), () => {
      toast("Enchère annulée : la carte revient dans ta collection.", "good"); dropAuction(a.id); collectionChanged();
    }), "Confirmer l'annulation")];
    if (!a.bids) kids.push(priceEditor(a));
    return el("div", { class: "bidrow" }, kids);
  }
  if (a.leading || !(a.min > 0)) return null;
  return el("div", { class: "bidrow" }, actBtn(`Miser ${fmt(a.min)}`, "small bid", (b) => placeBid(a.id, a.min, b), () => `Confirmer : miser ${fmt(a.min)} Wikiki`));
}

/* ---------------- fiche de carte : recycler, mettre aux enchères, verrouiller, mettre de côté, souhaits ---------------- */
function sheetActions(c, d) {
  if (!c.cid) return null;
  const version = d.mine.filter((m) => m.shiny === !!c.shiny);
  const free = version.filter((m) => m.state === "free"), lockedCopies = version.filter((m) => m.state === "locked");
  const exclusive = EXCLUSIVE.includes(c.rarity) || version.some((m) => m.state === "exclusive");
  const kids = [];
  const done = () => { collectionChanged(); refreshMeSoon(); };

  if (exclusive && version.length) kids.push(el("p", { class: "muted", text: "Carte exclusive : elle ne se vend pas, ne se recycle pas et ne s'échange pas." }));
  if (free.length && !exclusive) {
    const gain = bankOf(c.rarity), need = c.shiny || RECYCLE_CONFIRM.includes(c.rarity);
    kids.push(tag(actBtn(`Recycler${gain ? ` · +${fmt(gain)} Wikiki` : ""}`, "small danger", (b) => act(b, () => api().recycle([free[free.length - 1].id]), (r) => {
      toast(`Carte recyclée : +${fmt(r.gain)} Wikiki. Elle reste 20 minutes dans la corbeille.`, "good"); done();
    }), need ? () => `Vraiment ? ${c.shiny ? "Ta chromatique" : "Ta " + label(c.rarity).toLowerCase()} contre ${fmt(gain || 1)} Wikiki` : null), "recycle"));

    const start = numberField(10, "Départ", 90), dur = el("select", { class: "field" }, DURATIONS.map(([v, t]) => el("option", { value: v, text: t })));
    kids.push(el("div", { class: "auctform" },
      el("h4", { text: "Mettre aux enchères" }),
      el("div", { class: "row" }, el("label", {}, "Départ (Wikiki) ", start), el("label", {}, "Durée ", dur),
        tag(actBtn("Lancer l'enchère", "small primary", (b) => {
          act(b, () => api().auction_create(free[0].id, posInt(start.value), dur.value), () => { toast("Enchère lancée ! Tu la retrouves dans Marché, En vente.", "good"); done(); });
        }, () => `Confirmer : lancer à ${fmt(posInt(start.value))} Wikiki`, () => (posInt(start.value) < 1 ? "Indique une mise de départ d'au moins 1 Wikiki." : "")), "auction")),
      el("p", { class: "muted", text: "Aucune commission. Une mise dans les 15 dernières secondes relance 1 minute ; sans mise, la carte te revient." })));
  }
  if (free.length && !exclusive) kids.push(tag(actBtn("Verrouiller un exemplaire", "small", (b) => act(b, () => api().card_lock(free[0].id, c.cid, !!c.shiny, true), () => { toast("Carte verrouillée : elle ne peut plus être vendue, mise aux enchères ni échangée.", "good"); done(); })), "lock"));
  if (lockedCopies.length) kids.push(tag(actBtn("Déverrouiller un exemplaire", "small", (b) => act(b, () => api().card_lock(lockedCopies[0].id, c.cid, !!c.shiny, false), () => { toast("Carte déverrouillée.", "good"); done(); })), "unlock"));
  if (free.length && !exclusive) {
    const on = !free[0].for_sale;
    kids.push(tag(actBtn(on ? "Mettre de côté pour la vente" : "Retirer des cartes à vendre", "small", (b) => act(b, () => api().card_for_sale(free[0].id, on),
      (r) => toast(on ? `Mise de côté (${fmt(r.n)} cartes à vendre).` : "Retirée des cartes à vendre.", "good"))), "forsale"));
  }
  kids.push(tag(actBtn(d.wished ? "Retirer de mes souhaits" : "Ajouter à mes souhaits", "small", (b) => act(b,
    () => api().wish_set(c.cid, !d.wished, { name: c.name, desc: c.desc, img: c.img, rarity: c.rarity, lang: c.lang }),
    (r) => toast(r.wished ? "Ajoutée à ta liste de souhaits : le site te prévient dès qu'elle passe aux enchères." : "Retirée de ta liste de souhaits.", "good"))), "wish"));
  return el("div", { class: "actions" }, el("h3", { text: "Actions" }), el("div", { class: "row" }, kids.filter((k) => k.tagName === "BUTTON")), ...kids.filter((k) => k.tagName !== "BUTTON"));
}

/* ---------------- WIKI-PRO : la vue du marché d'une carte (abonnés seulement) ---------------- */
function priceChart(sales, avg) {
  const W = 340, H = 96, m = { l: 8, r: 8, t: 8, b: 8 };
  const t0 = sales[0].ts, t1 = sales[sales.length - 1].ts || t0 + 1;
  const ps = sales.map((s) => s.price), lo = Math.min(...ps, avg || Infinity), hi = Math.max(...ps, avg || 0);
  const x = (t) => m.l + ((t - t0) / Math.max(1, t1 - t0)) * (W - m.l - m.r), y = (p) => H - m.b - ((p - lo) / Math.max(1, hi - lo)) * (H - m.t - m.b);
  const ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("class", "chart"); svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "Évolution des prix de vente");
  const add = (tag, attrs) => { const n = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v)); svg.append(n); };
  if (avg) add("line", { x1: m.l, x2: W - m.r, y1: y(avg), y2: y(avg), class: "avg" });
  add("polyline", { points: sales.map((s) => `${x(s.ts).toFixed(1)},${y(s.price).toFixed(1)}`).join(" "), class: "line" });
  sales.forEach((s) => add("circle", { cx: x(s.ts).toFixed(1), cy: y(s.price).toFixed(1), r: 2.2, class: "pt" }));
  return svg;
}
function proNodes(c, d, scope) { // scope : "carte" | "rang"
  const s = scope === "rang" ? d.rarity : d.stats, sales = scope === "rang" ? d.rsales : d.sales, name = label(c.rarity).toLowerCase();
  const chips = el("div", { class: "seg" }, ["carte", "rang"].map((k) => el("button", { class: k === scope ? "on" : "", text: k === "carte" ? "Cette carte" : `Toutes les ${name}s`,
    onclick: () => renderPro(c, d, k) })));
  const cases = [["Ventes", s.n ? fmt(s.n) : "0"], ["Dernier", s.n ? fmt(s.last) : "—"], ["Moyenne", s.n ? fmt(s.avg) : "—"], ["Min", s.n ? fmt(s.min) : "—"], ["Max", s.n ? fmt(s.max) : "—"]];
  const last = sales.slice().reverse().slice(0, 10);
  return [chips,
    d.live && scope === "carte" ? el("p", { class: "muted", text: `${plural(d.live, "exemplaire")} aux enchères en ce moment.` }) : null,
    el("div", { class: "mstats" }, cases.map(([k, v]) => el("div", {}, el("b", { text: v }), el("small", { text: k })))),
    sales.length > 1 ? priceChart(sales, s.avg) : el("p", { class: "muted", text: sales.length ? "Une seule vente pour l'instant : pas encore de courbe."
      : scope === "rang" ? `Aucune ${name} ne s'est encore vendue aux enchères.` : "Cette carte ne s'est encore jamais vendue aux enchères." }),
    ...last.map((v) => el("p", { class: "copy" }, el("span", { class: "price" }, icon("coin"), fmt(v.price)),
      el("span", { class: "muted", text: (scope === "rang" && v.title ? v.title + ", " : "") + parisDate(v.ts) })))];
}
function renderPro(c, d, scope = "carte") {
  const host = $("pro-extra");
  if (host && host.isConnected) host.replaceChildren(el("h3", { text: "Vue du marché (WIKI-PRO)" }), ...proNodes(c, d, scope).filter(Boolean));
}
async function loadProMarket(c) { // seulement pour un profil abonné : sinon une simple mention, rien n'est demandé au site
  const host = $("pro-extra");
  if (!host || !c.cid) return;
  if (!(S.data && S.data.me.pro)) {
    host.replaceChildren(el("p", { class: "muted" }, "Historique des prix : réservé aux abonnés WIKI-PRO. ", el("button", { class: "link", text: "Voir l'offre", onclick: openSite })));
    return;
  }
  host.replaceChildren(el("p", { class: "muted", text: "Lecture du marché…" }));
  const r = await api().pro_market(c.cid, c.rarity, !!c.shiny);
  if (!r.ok) { if (host.isConnected) host.replaceChildren(el("p", { class: "muted", text: r.error || "Marché indisponible." })); return; }
  if ($("modal-body").dataset.cid === c.cid) renderPro(c, r);
}

/* ---------------- échanges : accepter, refuser, annuler, proposer, contre-proposer ---------------- */
function tradeButtons(t) {
  if (t.status !== "pending") return null;
  const done = () => { loadTrades(); collectionChanged(); refreshMeSoon(); };
  if (!t.incoming) return el("div", { class: "row" }, actBtn("Annuler ma proposition", "small danger", (b) => act(b, () => api().trade_action("cancel", t.id),
    () => { toast("Proposition annulée.", "good"); done(); }), "Confirmer l'annulation"));
  const acc = actBtn("Accepter l'échange", "small primary", (b) => act(b, () => api().trade_action("accept", t.id),
    () => { toast("Échange conclu : les cartes ont changé de main.", "good"); ping("good"); done(); }), "Confirmer l'échange");
  if (!t.valid) acc.disabled = true;
  return el("div", { class: "row" }, acc,
    actBtn("Contre-proposer", "small", () => openComposer(t.other, { counterOf: t.id, note: summarize(t) })),
    actBtn("Refuser", "small danger", (b) => act(b, () => api().trade_action("decline", t.id), () => { toast("Proposition refusée.", "good"); done(); })));
}
const summarize = (t) => `Proposition de ${t.other} : tu donnes ${plural(t.give.length, "carte")}${t.give_coins ? ` et ${fmt(t.give_coins)} Wikiki` : ""}, tu reçois ${plural(t.get.length, "carte")}${t.get_coins ? ` et ${fmt(t.get_coins)} Wikiki` : ""}.`;

const TC = { to: "", mine: [], theirs: [], give: [], take: [], q: { give: "", take: "" }, lim: { give: 60, take: 60 }, counterOf: null };
async function openTradeStart() { // « Nouvel échange » : on choisit un ami (les échanges se font entre amis)
  const r = await api().friends_get();
  if (r.expired) return sessionLost(r);
  if (!r.ok) return toast(r.error || "Liste d'amis indisponible");
  const list = r.friends.length ? r.friends.map((f) => el("button", { class: "frow", onclick: () => openComposer(f.name) }, el("b", { text: f.name }), f.fav ? el("small", { text: "favori" }) : null))
    : [el("p", { class: "muted", text: "Tu n'as pas encore d'amis : les échanges se font entre amis, ajoute-en depuis le site." })];
  openDialog("Échanger avec qui ?", el("div", { class: "flist" }, list));
}
async function openComposer(name, opts = {}) {
  if (!S.data || !S.data.loaded || S.data.cards.some((c) => !c.free_ids)) return toast("Actualise d'abord ta collection (menu du compte), puis réessaie.");
  Object.assign(TC, { to: name, give: [], take: [], q: { give: "", take: "" }, lim: { give: 60, take: 60 }, counterOf: opts.counterOf ?? null, theirs: [] });
  TC.mine = S.data.cards.filter((c) => c.free_ids.length).map((c) => ({ card: c, ids: c.free_ids }));
  openDialog(opts.counterOf ? `Contre-proposition à ${name}` : `Échange avec ${name}`, el("p", { class: "muted", text: "Chargement des cartes…" }), true);
  const r = await api().user_cards(name);
  if (r.expired) return sessionLost(r);
  if (!r.ok) { closeDialog(); return toast(r.error || "Impossible de lire les cartes de ce joueur"); }
  TC.theirs = r.groups; paintComposer(opts.note);
}
const tcOf = (key) => (key === "give" ? TC.mine : TC.theirs);
function tcPick(key, g) { // un clic ajoute un exemplaire, encore un autre, puis retire tout (comme sur le site)
  const chosen = TC[key], n = g.ids.filter((id) => chosen.some((x) => x.id === id)).length;
  if (n < g.ids.length) { if (chosen.length >= 10) return toast("10 cartes au maximum de chaque côté."); chosen.push({ id: g.ids.find((i) => !chosen.some((x) => x.id === i)), card: g.card }); }
  else TC[key] = chosen.filter((x) => !g.ids.includes(x.id));
  paintTcSide(key); $("tc-n-" + key).textContent = String(TC[key].length);
}
function paintTcSide(key) {
  const grid = $("tc-grid-" + key), q = TC.q[key].toLowerCase();
  const rows = tcOf(key).filter((g) => !q || g.card.name.toLowerCase().includes(q)).sort((a, b) => rarityRank(a.card.rarity) - rarityRank(b.card.rarity) || b.card.reads - a.card.reads);
  grid.replaceChildren(...rows.slice(0, TC.lim[key]).map((g) => {
    const n = g.ids.filter((id) => TC[key].some((x) => x.id === id)).length;
    const node = cardNode({ ...g.card, copies: g.ids.length }, () => tcPick(key, g));
    if (n) { node.classList.add("picked"); node.append(el("span", { class: "selmark", text: g.ids.length > 1 ? `${n}/${g.ids.length}` : "✓" })); }
    return node;
  }), ...(rows.length > TC.lim[key] ? [el("button", { class: "btn small", text: `Afficher plus (encore ${rows.length - TC.lim[key]})`, onclick: () => { TC.lim[key] += 60; paintTcSide(key); } })] : []),
  ...(rows.length ? [] : [el("div", { class: "empty", text: tcOf(key).length ? "Aucune carte ne correspond." : key === "give" ? "Tu n'as aucune carte disponible." : `${TC.to} n'a aucune carte disponible.` })]));
}
function paintComposer(note) {
  const col = (key, title) => el("div", { class: "ccol" },
    el("h3", {}, `${title} `, el("span", { id: "tc-n-" + key, text: String(TC[key].length) }), " / 10"),
    el("input", { class: "field", type: "search", placeholder: "Chercher une carte", autocomplete: "off", oninput: (e) => { TC.q[key] = e.target.value.trim(); TC.lim[key] = 60; paintTcSide(key); } }),
    el("div", { class: "grid tcgrid", id: "tc-grid-" + key }),
    el("label", { class: "wline" }, icon("coin"), el("input", { class: "field", id: "tc-coins-" + key, type: "number", min: "0", step: "1", inputmode: "numeric", placeholder: key === "give" ? "Wikiki offerts en plus" : "Wikiki demandés en plus", style: "width:220px" })));
  const msg = el("input", { class: "field grow", id: "tc-msg", maxlength: "200", placeholder: `Un message pour ${TC.to} (facultatif)` });
  const empty = () => (!TC.give.length && !TC.take.length && !posInt($("tc-coins-give").value) && !posInt($("tc-coins-take").value) ? "L'échange est vide : choisis au moins une carte ou des Wikiki." : "");
  const send = actBtn("Envoyer la proposition", "primary", (b) => {
    const gc = posInt($("tc-coins-give").value), tc = posInt($("tc-coins-take").value);
    act(b, () => api().trade_send(TC.to, TC.give.map((x) => x.id), TC.take.map((x) => x.id), gc, tc, msg.value, TC.counterOf), () => {
      toast(TC.counterOf ? `Contre-proposition envoyée à ${TC.to}.` : `Proposition envoyée à ${TC.to}.`, "good");
      closeDialog(); TR.box = "sent"; if (S.tab === "trades") loadTrades(true); else setTab("trades");
    });
  }, () => `Confirmer : envoyer à ${TC.to} (${plural(TC.give.length, "carte")} contre ${plural(TC.take.length, "carte")})`, empty);
  $("dialog-body").replaceChildren($("dialog-body").firstChild, el("div", { class: "composer" },
    el("p", { class: "muted", text: (note ? note + " " : "") + "Clique sur une carte pour l'ajouter (encore une fois pour un autre exemplaire). 10 cartes au maximum de chaque côté, rangées de la plus rare à la plus commune." }),
    el("div", { class: "ccols" }, col("give", "Tu donnes"), col("take", "Tu reçois")), el("div", { class: "row" }, msg, send)));
  paintTcSide("give"); paintTcSide("take");
}

/* ---------------- corbeille : récupérer ce qu'on vient de recycler (20 minutes) ---------------- */
async function openCorbeille() {
  openDialog("Corbeille", el("p", { class: "muted", text: "Chargement…" }), true);
  const r = await api().corbeille_get();
  if (r.expired) return sessionLost(r);
  if (!r.ok) { closeDialog(); return toast(r.error || "Corbeille indisponible"); }
  const reload = () => { collectionChanged(); refreshMeSoon(); openCorbeille(); };
  const left = (s) => (s >= 60 ? `encore ${Math.ceil(s / 60)} min` : "moins d'une minute");
  const body = el("div", {}, el("p", { class: "muted", text: `Une carte recyclée reste ici ${r.minutes} minutes, le temps de te raviser. La récupérer coûte ${fmt(r.price)} Wikiki : celui que la banque t'avait donné. Passé ce délai, elle disparaît pour de bon.` }));
  if (!r.items.length) body.append(el("div", { class: "empty", text: `La corbeille est vide. Rien n'a été recyclé ces ${r.minutes} dernières minutes.` }));
  else {
    body.append(el("div", { class: "row" },
      actBtn(`Tout récupérer · ${fmt(r.items.length * r.price)} Wikiki`, "small primary", (b) => act(b, () => api().corbeille_restore(null, true), (x) => { toast(`${plural(x.restored, "carte récupérée", "cartes récupérées")} pour ${fmt(x.cost)} Wikiki.`, "good"); reload(); }), () => `Confirmer : ${fmt(r.items.length * r.price)} Wikiki`),
      actBtn("Vider la corbeille", "small danger", (b) => act(b, () => api().corbeille_empty(), (x) => { toast(`Corbeille vidée : ${plural(x.erased, "carte effacée", "cartes effacées")} pour de bon.`, "good"); reload(); }), `Confirmer : effacer ${plural(r.items.length, "carte")} pour de bon`)),
      el("div", { class: "grid corbgrid" }, r.items.map((x) => el("div", { class: "corbslot" }, cardNode(x.card, null),
        actBtn(`Récupérer · ${fmt(r.price)} W`, "small", (b) => act(b, () => api().corbeille_restore([x.id], false), (y) => { toast(`Carte récupérée pour ${fmt(y.cost)} Wikiki.`, "good"); reload(); })),
        el("small", { class: "muted", text: left(x.left) })))));
  }
  openDialog("Corbeille", body, true);
}

/* ---------------- recycler les doublons en une fois (avec confirmation, une corbeille de 20 minutes derrière) ---------------- */
function dupBuckets() { // par rareté : les exemplaires en trop. On garde toujours au moins un exemplaire ; ni verrouillées, ni chromatiques, ni exclusives.
  const out = {};
  for (const c of S.data.cards) {
    if (c.shiny || c.copies < 2 || !c.free_ids || EXCLUSIVE.includes(c.rarity) || bankOf(c.rarity) == null) continue;
    const spare = c.free_ids.slice(c.locked_ids && c.locked_ids.length ? 0 : 1); // un exemplaire verrouillé compte déjà comme gardé
    if (!spare.length) continue;
    (out[c.rarity] = out[c.rarity] || { ids: [], gain: 0 }).ids.push(...spare);
    out[c.rarity].gain += spare.length * bankOf(c.rarity);
  }
  return out;
}
function openDups() {
  if (!S.data.loaded || S.data.cards.some((c) => !c.free_ids)) return toast("Actualise d'abord ta collection (menu du compte), puis réessaie.");
  const buckets = dupBuckets(), keys = RARITY_ORDER.filter((k) => buckets[k]);
  if (!keys.length) return openDialog("Recycler les doublons", el("p", { class: "muted", text: "Aucun doublon à recycler : il reste toujours au moins un exemplaire de chaque carte." }));
  const picked = new Set(["C", "PC"].filter((k) => buckets[k])); // les raretés courantes seulement, par défaut
  const total = () => keys.filter((k) => picked.has(k)).reduce((t, k) => ({ n: t.n + buckets[k].ids.length, gain: t.gain + buckets[k].gain,
    rare: t.rare + (RECYCLE_CONFIRM.includes(k) ? buckets[k].ids.length : 0) }), { n: 0, gain: 0, rare: 0 });
  const summary = el("p", { class: "dupsum" }), go = el("button", { class: "btn danger" }); // une action de masse : rouge, comme « Vider »
  const paint = () => {
    const t = total(); disarm(go);
    go.textContent = t.n ? `Recycler ${plural(t.n, "carte")} · +${fmt(t.gain)} Wikiki` : "Choisis au moins une rareté";
    go.disabled = !t.n;
    summary.textContent = t.rare ? `Attention : ${plural(t.rare, "carte rare")} comprise${t.rare > 1 ? "s" : ""} (rare ou mieux).` : "";
  };
  go.onclick = () => {
    const t = total();
    if (!t.n || !armed(go, t.rare ? `Confirmer : ${plural(t.n, "carte")} dont ${plural(t.rare, "rare")}` : `Confirmer : ${plural(t.n, "carte")}`)) return;
    runBulkRecycle(keys.filter((k) => picked.has(k)).flatMap((k) => buckets[k].ids), go);
  };
  const rows = keys.map((k) => {
    const cb = el("input", { type: "checkbox" }); cb.checked = picked.has(k);
    cb.onchange = () => { cb.checked ? picked.add(k) : picked.delete(k); paint(); };
    return el("label", { class: "duprow", style: `--c:${color(k)}` }, cb, el("span", { class: "lab", text: label(k) }),
      el("span", { class: "n", text: plural(buckets[k].ids.length, "exemplaire") }), el("span", { class: "n", text: `+${fmt(buckets[k].gain)} Wikiki` }));
  });
  openDialog("Recycler les doublons", el("div", {}, el("p", { class: "muted", text: "Il reste toujours au moins un exemplaire de chaque carte. Les cartes verrouillées, chromatiques et exclusives ne sont jamais recyclées. Tout ce que tu recycles reste 20 minutes dans la corbeille." }),
    el("div", { class: "dups" }, rows), summary, el("div", { class: "row" }, go)));
  paint();
}
async function runBulkRecycle(ids, btn) { // par paquets de 50 : un seul geste de ta part, chaque appel est journalisé ; on s'arrête à la première erreur
  let sold = 0, gain = 0, locked = 0;
  for (let i = 0; i < ids.length; i += 50) {
    btn.textContent = `Recyclage… ${Math.min(i + 50, ids.length)} / ${ids.length}`;
    const r = await act(btn, () => api().recycle(ids.slice(i, i + 50)), null);
    if (!r) break;
    sold += r.sold; gain += r.gain; locked += r.locked;
  }
  collectionChanged(); refreshMeSoon(); closeDialog();
  if (sold) toast(`${plural(sold, "carte recyclée", "cartes recyclées")} : +${fmt(gain)} Wikiki${locked ? `, ${plural(locked, "verrouillée conservée", "verrouillées conservées")}` : ""}. Récupérables 20 minutes dans la corbeille.`, "good");
}

/* ---------------- journal de ce que tu as fait depuis l'appli ---------------- */
async function openActionsLog() {
  const r = await api().actions_get();
  const rows = r.ok && r.actions.length ? r.actions.slice(0, 100).map((a) => el("div", { class: "arow2" + (a.ok ? "" : " bad") },
    el("small", { text: ago(a.ts, Date.now() / 1000) }), el("span", { text: a.action }), el("em", { text: a.ok ? "fait" : a.error || "refusé" })))
    : [el("p", { class: "muted", text: "Rien pour l'instant : chaque mise, vente, échange ou recyclage fait depuis l'appli apparaîtra ici." })];
  openDialog("Journal des actions", el("div", {}, el("p", { class: "muted", text: "Ce que tu as fait depuis cette appli (les 200 dernières actions). Le fichier reste sur cet ordinateur." }), ...rows), true);
}

function bindActions() {
  $("btn-corb").onclick = () => { $("user-menu").classList.add("hidden"); openCorbeille(); };
  $("btn-actlog").onclick = () => { $("user-menu").classList.add("hidden"); openActionsLog(); };
  $("t-new").onclick = openTradeStart;
  $("dialog").addEventListener("click", (e) => { if (e.target === $("dialog")) closeDialog(); });
}
