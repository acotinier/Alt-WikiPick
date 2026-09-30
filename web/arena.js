"use strict";
/* L'arène : des combats à deux, en direct. On défie un joueur connecté ; il accepte, vous composez chacun
   trois cartes en même temps (chacun voit l'équipe de l'autre se construire), puis le serveur joue TOUT le duel
   et renvoie le détail de chaque coup : ici on ne fait que le rejouer. Tes cartes ne quittent jamais ta collection.
   Chaque geste est un clic ; rien ne se joue tout seul.
   Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const CB = {
  info: null, defi: null, recu: null, target: null, choix: [], advChoix: [], advPret: false, monPret: false,
  duel: null, decks: null, edit: null, q: "", view: "lobby", run: 0, skip: false, done: false, playing: 0, chestBusy: false,
};
const CB_PV = { C: 180, PC: 186, R: 192, SR: 198, UR: 204, L: 210, M: 216, WBC: 210, SIXSEVEN: 210, EXC: 210 }; // comme le serveur
const cbForce = (c) => Math.round((CB_PV[c.rarity] || 180) * (c.shiny ? 1.04 : 1));
const cbSize = () => (CB.info && CB.info.size) || 3;
const cbLeft = (t) => Math.max(0, Math.round(t - nowSrv()));
const cbStop = (run) => run !== CB.run || S.tab !== "arena";
const cbPause = async (run, ms) => { if (!CB.skip && !cbStop(run)) await new Promise((r) => setTimeout(r, ms)); };

/* ---------------- entrée et routage ---------------- */
async function loadArena() {
  refreshArenaDot();
  if (CB.duel) return paintArena();
  const r = await api().combat_info();
  if (r.expired) return sessionLost(r);
  if (!r.ok) return $("cb-body").replaceChildren(el("div", { class: "empty", text: r.error || "Arène indisponible" }));
  CB.info = r; paintArena();
}
async function resumeArena() { // au démarrage : un défi en cours, ou une invitation qu'on n'a pas encore vue
  const r = await api().combat_state();
  if (!r.ok || !r.defi) return;
  const d = r.defi;
  if (!d.launched && d.state === "attente") return showInvite({ id: d.id, from: d.opponent, expire: d.expire, team: d.team });
  CB.defi = d; CB.monPret = d.my_ready; CB.advPret = d.opp_ready;
  if (S.tab === "arena") paintArena();
}
function paintArena() {
  if (S.tab !== "arena" || !CB.info) return;
  if (CB.duel) return paintDuel();
  if (CB.defi && CB.defi.launched && CB.defi.state === "attente") return paintWaiting();
  if (CB.defi || CB.target) return paintPrep();
  if (CB.view === "decks") return paintDecks();
  paintLobby();
}

/* ---------------- salon ---------------- */
function quotaNode() {
  const i = CB.info, open = i.next > 0, ok = i.left > 0;
  return el("div", { class: "cbquota" + (ok ? "" : " none") },
    el("div", { class: "cbdots" }, Array.from({ length: i.total }, (_, n) => el("i", { class: n < i.left ? "on" : "" }))),
    el("div", {}, el("b", { text: `Combats disponibles : ${i.left} / ${i.total}` }),
      el("small", {}, !open ? `${i.total} combats toutes les ${Math.round(i.window / 60)} minutes : le compte à rebours démarre à ton premier combat. `
        : ok ? "Le compteur revient à " + i.total + " dans " : "Tes combats reviennent dans ", open ? el("span", { "data-cbclock": String(i.next), text: clock(cbLeft(i.next)) }) : null)));
}
function chestNode() {
  const i = CB.info, ready = i.chests > 0, done = i.chest_all - i.chest_left;
  const box = el("div", { class: "cbchest " + (ready ? "ready" : "locked"), id: "cb-chest" },
    el("div", {}, el("b", { text: ready ? (i.chests > 1 ? `${i.chests} Mini-Packs t'attendent` : "Un Mini-Pack t'attend") : "Ton prochain Mini-Pack" }),
      el("p", { class: "muted", text: ready ? "Ouvre-le : des récompenses, rares ou moins rares, t'attendent à l'intérieur."
        : `Joue ${plural(i.chest_all, "combat")} dans l'arène pour le débloquer : ${done} / ${i.chest_all} joués, encore ${plural(i.chest_left, "combat")}.` }),
      ready ? actBtn("Ouvrir le Mini-Pack", "primary small", (b) => act(b, () => api().combat_chest(), (r) => revealChest(box, r))) : el("div", { class: "cbbar" }, el("i", { style: `width:${Math.min(100, Math.round((100 * done) / i.chest_all))}%` }))));
  return box;
}
function revealChest(box, r) {
  const out = el("div", { class: "cbprize" }, r.kind === "packs" ? el("b", { text: `${plural(r.n, "paquet")} !` }) : el("span", {}, icon("coin"), el("b", { text: `+${fmt(r.n)}` }), " Wikiki"));
  if (r.card) out.append(cardNode(r.card, () => openModal(r.card)), el("small", { text: `+ une carte ${label(r.card.rarity).toLowerCase()}${r.card.new ? ", nouvelle !" : ""}` }));
  box.replaceChildren(el("b", { text: "Mini-Pack ouvert !" }), out, el("p", { class: "muted", text: r.left ? `Il t'en reste ${plural(r.left, "autre")} à ouvrir.` : "Rejoue pour en mériter un autre." }));
  ping("good"); refreshMeSoon(); if (r.card) collectionChanged();
  CB.info.chests = r.left;
}
function playerRow(u) {
  let action;
  if (!u.online) action = el("span", { class: "muted", text: "Hors ligne" });
  else if (u.fighting) action = el("span", { class: "muted", text: "En combat" });
  else if (u.cards != null && u.cards < cbSize()) action = el("span", { class: "muted", title: `Il lui faut ${cbSize()} cartes différentes`, text: "Pas prêt" });
  else action = actBtn("Affronter", "small primary", (b) => {
    if (!CB.info.left) return toast("Tes combats de la demi-heure sont joués : attends la fin du compte à rebours.");
    act(b, () => api().combat_challenge(u.name), (r) => { newChallenge(r.defi); });
  });
  return el("div", { class: "cbplayer" + (u.online ? " cbon" : "") }, el("i", { class: "cbdot" }),
    el("div", { class: "who" }, el("b", { text: (u.fav ? "★ " : "") + u.name }), el("small", { text: u.online ? (u.fighting ? "En combat" : "En ligne") + (u.cards != null ? `, ${plural(u.cards, "carte")}` : "") : "Hors ligne" })), action);
}
function paintLobby() {
  const i = CB.info, online = i.opponents.filter((u) => u.online).length;
  const res = el("div", { id: "cb-res", class: "cbplayers" });
  const search = el("input", { class: "field", type: "search", placeholder: "Chercher un pseudo", autocomplete: "off", style: "width:100%" });
  search.addEventListener("input", debounce(async () => {
    const q = search.value.trim();
    if (!q) return res.replaceChildren();
    const r = await api().users_search(q);
    res.replaceChildren(...(r.ok && r.users.length ? r.users.map((u) => playerRow({ name: u.name, online: u.online })) : [el("p", { class: "muted", text: "Aucun joueur ne correspond." })]));
  }, 250));
  $("cb-body").replaceChildren(
    el("p", { class: "muted intro", text: `Défie un joueur connecté : vous alignez ${cbSize()} cartes chacun et le duel se joue sous vos yeux, en même temps. Tes cartes ne quittent jamais ta collection : l'arène ne risque rien.` }),
    el("div", { class: "cbgrid2" },
      el("div", {}, quotaNode(), chestNode(),
        el("div", { class: "row" }, actBtn("Mes decks", "small", () => { CB.view = "decks"; CB.edit = null; paintArena(); })),
        historyNode()),
      el("div", {}, el("h3", { class: "sec small", text: `Amis${online ? `, ${online} en ligne` : ""}` }),
        el("div", { class: "cbplayers" }, i.opponents.length ? i.opponents.map(playerRow) : [el("p", { class: "muted", text: "Tu n'as pas encore d'amis à défier. Cherche un joueur ci-dessous." })]),
        el("h3", { class: "sec small", text: "Défier un autre joueur" }), search, res)));
}
function historyNode() {
  const h = CB.info.history;
  if (!h.length) return el("div");
  return el("div", { class: "cbhist" }, el("h3", { class: "sec small", text: "Tes derniers combats" }), ...h.map((r) => el("div", { class: "cbhrow " + (r.me > r.them ? "win" : "lose") },
    el("b", { text: r.me > r.them ? "Victoire" : "Défaite" }), el("span", { text: `${r.me} – ${r.them}` }), el("span", { text: `${r.defended ? "défié par " : "contre "}${r.opponent}` }),
    el("span", { class: "gain", text: r.gain ? `+${fmt(r.gain)}` : "—" }), el("small", { text: ago(r.when) }))));
}

/* ---------------- un défi : lancé, en attente, puis composition des équipes ---------------- */
function newChallenge(defi) {
  Object.assign(CB, { defi, target: null, choix: [], advChoix: [], advPret: false, monPret: false, q: "" });
  ping("info"); paintArena();
}
function waitingClock(t) { return el("b", { class: "cbchrono", "data-cbchrono": String(t), text: clock(cbLeft(t)) }); }
function paintWaiting() {
  const d = CB.defi;
  $("cb-body").replaceChildren(el("div", { class: "cbwait" }, el("h2", { text: `En attente de ${d.opponent}…` }),
    el("p", { class: "muted", text: "L'invitation vient de partir. S'il ne répond pas à temps, ton combat ne sera pas décompté." }),
    waitingClock(d.expire), actBtn("Annuler le défi", "small danger", (b) => leaveChallenge(b))));
}
async function leaveChallenge(btn) {
  const d = CB.defi;
  if (!d) return;
  await act(btn, () => api().combat_cancel(d.id), null);
  Object.assign(CB, { defi: null, choix: [], monPret: false, advChoix: [], advPret: false });
  loadArena();
}
function cbCards() { // ta collection, la plus solide d'abord ; un exemplaire par carte
  const q = CB.q.toLowerCase();
  return S.data.cards.filter((c) => c.ids.length && (!q || c.name.toLowerCase().includes(q)))
    .sort((a, b) => cbForce(b) - cbForce(a) || a.name.localeCompare(b.name, "fr"));
}
const pickedCard = (id) => S.data.cards.find((c) => c.ids[0] === id);
const sendChoice = debounce(() => { // l'autre te regarde choisir : tes cartes lui sont montrées en direct
  const d = CB.defi;
  if (d && d.state === "prepa" && !CB.monPret) api().combat_choice(d.id, CB.choix);
}, 250);
function teamSlot(c, i, onDel) {
  return c ? el("div", { class: "cbslot on" }, el("span", { class: "cbnum", text: String(i + 1) }), cardNode(c, null),
    onDel ? el("button", { class: "icon-btn cbdel", "aria-label": "Retirer", onclick: () => onDel(c) }, icon("close")) : null)
    : el("div", { class: "cbslot" }, el("span", { class: "cbnum", text: String(i + 1) }), el("div", { class: "cbempty", text: "à choisir" }));
}
function advSlots() {
  return Array.from({ length: cbSize() }, (_, i) => CB.advChoix[i] ? el("div", { class: "cbslot on" }, el("span", { class: "cbnum", text: String(i + 1) }), cardNode(CB.advChoix[i], null))
    : el("div", { class: "cbslot" }, el("span", { class: "cbnum", text: String(i + 1) }), el("div", { class: "cbempty", text: CB.defi ? "il choisit…" : "?" })));
}
function pickGrid() {
  const list = cbCards();
  return list.length ? [el("div", { class: "grid cbpick" }, list.slice(0, 60).map((c) => {
    const n = cardNode(c, () => togglePick(c.ids[0])); n.classList.toggle("picked", CB.choix.includes(c.ids[0]));
    n.append(el("span", { class: "cbstat", text: `${cbForce(c)} PV` })); return n;
  })), ...(list.length > 60 ? [el("p", { class: "muted", text: `${plural(list.length - 60, "autre carte")} : affine la recherche.` })] : [])]
    : [el("div", { class: "empty", text: CB.q ? "Aucune carte ne correspond." : "Ouvre quelques paquets pour composer ton équipe." })];
}
function togglePick(id) {
  if (CB.monPret) return toast("Ton équipe est déjà validée.");
  const i = CB.choix.indexOf(id);
  if (i >= 0) CB.choix.splice(i, 1);
  else if (CB.choix.length >= cbSize()) return toast("Ton équipe est complète : retire une carte d'abord.");
  else CB.choix.push(id);
  paintPrep(); sendChoice();
}
function paintPrep() {
  const n = cbSize(), d = CB.defi, adv = d ? d.opponent : CB.target.name, ready = CB.choix.length === n;
  const mine = Array.from({ length: n }, (_, i) => teamSlot(pickedCard(CB.choix[i]), i, CB.monPret ? null : (c) => { CB.choix.splice(CB.choix.indexOf(c.ids[0]), 1); paintPrep(); sendChoice(); }));
  const search = el("input", { class: "field", type: "search", placeholder: "Chercher dans ta collection", autocomplete: "off", value: CB.q });
  const grid = el("div", { id: "cb-grid" }, pickGrid());
  search.addEventListener("input", debounce((e) => { CB.q = e.target.value; grid.replaceChildren(...pickGrid()); }, 180));
  const decks = el("div", { class: "cbdecks" }, ...(CB.decks || []).filter((k) => k.complete).map((k) => actBtn(k.name, "small", () => {
    if (CB.monPret) return; CB.choix = k.ids.slice(0, n); paintPrep(); sendChoice();
  })));
  if (!CB.decks) loadDecks().then(() => S.tab === "arena" && (CB.defi || CB.target) && paintPrep());
  const go = d ? (CB.monPret ? el("span", { class: "muted", text: `Équipe validée : le combat part quand ${adv} est prêt…` })
    : actBtn("Valider mon équipe", "primary", (b) => act(b, () => api().combat_team(d.id, CB.choix), (r) => { if (r.waiting) { CB.monPret = true; paintPrep(); } else startDuel(r.duel); })))
    : actBtn(`Défier ${adv}`, "primary", (b) => act(b, () => api().combat_challenge(adv), (r) => newChallenge(r.defi)));
  if (!CB.monPret && !ready) go.disabled = true;
  $("cb-body").replaceChildren(
    el("div", { class: "cbhead" }, d ? el("span", { class: "muted" }, CB.monPret ? "Équipe validée. " : "Valide ton équipe avant : ", waitingClock(d.expire)) : actBtn("← Changer d'adversaire", "small", () => { CB.target = null; CB.choix = []; paintArena(); }), quotaNode()),
    el("div", { class: "cbprep" },
      el("div", {}, el("h3", { class: "sec small", text: `Équipe de ${adv}` }), el("div", { class: "cbslots", id: "cb-adv" }, advSlots()), el("small", { class: "muted", id: "cb-advstate", text: d ? (CB.advPret ? "a validé son équipe" : "est en train de choisir…") : "il la composera lui-même s'il accepte" })),
      el("div", {}, el("h3", { class: "sec small", text: `Ton équipe, ${CB.choix.length} / ${n}` }), el("div", { class: "cbslots" }, mine))),
    el("div", { class: "row" }, actBtn("Meilleure équipe", "small", () => { if (CB.monPret) return; CB.choix = cbCards().slice(0, n).map((c) => c.ids[0]); paintPrep(); sendChoice(); }),
      actBtn("Tout enlever", "small", () => { if (CB.monPret) return; CB.choix = []; paintPrep(); sendChoice(); }),
      d ? actBtn("Abandonner", "small danger", (b) => leaveChallenge(b), "Confirmer l'abandon") : null, go),
    decks, el("div", { class: "tools" }, el("h3", { class: "sec small", text: `Choisis tes ${n} cartes` }), search), grid);
}

/* ---------------- decks enregistrés ---------------- */
async function loadDecks() { const r = await api().combat_decks(); CB.decks = r.ok ? r.decks : []; return CB.decks; }
async function paintDecks() {
  if (!CB.decks) await loadDecks();
  if (S.tab !== "arena" || CB.view !== "decks") return;
  const n = cbSize(), e = CB.edit;
  if (!e) return $("cb-body").replaceChildren(
    el("div", { class: "cbhead" }, actBtn("← Retour à l'arène", "small", () => { CB.view = "lobby"; paintArena(); })),
    el("h2", { class: "sec", text: "Mes decks" }), el("p", { class: "muted", text: `Prépare tes équipes de ${n} cartes à l'avance : quand tu défies quelqu'un, ou qu'on te défie, tu choisis un deck et ton équipe est prête en un clic.` }),
    el("div", { class: "cbdecklist" }, ...CB.decks.map((k) => el("div", { class: "cbdeck" + (k.complete ? "" : " incomplete") },
      el("b", { text: k.name }), k.complete ? null : el("small", { class: "muted", text: "une carte n'est plus dans ta collection" }),
      el("div", { class: "cbslots mini" }, k.cards.map((c, i) => teamSlot(c, i, null))),
      el("div", { class: "row" }, actBtn("Modifier", "small", () => { CB.edit = { id: k.id, name: k.name, choix: k.ids.slice(0, n) }; CB.q = ""; paintArena(); }),
        actBtn("Supprimer", "small danger", (b) => act(b, () => api().combat_deck_delete(k.id), (r) => { CB.decks = r.decks; toast("Deck supprimé.", "good"); paintArena(); }), "Confirmer la suppression")))),
      CB.decks.length < 10 ? actBtn("Nouveau deck", "small primary", () => { CB.edit = { id: 0, name: "", choix: [] }; CB.q = ""; paintArena(); }) : null));
  const name = el("input", { class: "field", maxlength: "30", placeholder: "Nom du deck (ex. « Mes mythiques »)", value: e.name });
  name.addEventListener("input", (ev) => { e.name = ev.target.value; });
  const grid = el("div", {}, ...deckGrid());
  const search = el("input", { class: "field", type: "search", placeholder: "Chercher dans ta collection", value: CB.q });
  search.addEventListener("input", debounce((ev) => { CB.q = ev.target.value; grid.replaceChildren(...deckGrid()); }, 180));
  function deckGrid() {
    const list = cbCards();
    return [el("div", { class: "grid cbpick" }, list.slice(0, 60).map((c) => {
      const node = cardNode(c, () => { const i = e.choix.indexOf(c.ids[0]); if (i >= 0) e.choix.splice(i, 1); else if (e.choix.length >= n) return toast("Le deck est complet : retire une carte d'abord."); else e.choix.push(c.ids[0]); paintArena(); });
      node.classList.toggle("picked", e.choix.includes(c.ids[0])); node.append(el("span", { class: "cbstat", text: `${cbForce(c)} PV` })); return node;
    }))];
  }
  $("cb-body").replaceChildren(el("div", { class: "cbhead" }, actBtn("← Mes decks", "small", () => { CB.edit = null; paintArena(); })),
    el("h2", { class: "sec", text: e.id ? "Modifier le deck" : "Nouveau deck" }), name,
    el("div", { class: "cbslots" }, Array.from({ length: n }, (_, i) => teamSlot(pickedCard(e.choix[i]), i, (c) => { e.choix.splice(e.choix.indexOf(c.ids[0]), 1); paintArena(); }))),
    el("div", { class: "row" }, actBtn("Meilleure équipe", "small", () => { e.choix = cbCards().slice(0, n).map((c) => c.ids[0]); paintArena(); }),
      (() => { const b = actBtn("Enregistrer le deck", "primary", (x) => act(x, () => api().combat_deck_save(e.id, e.name, e.choix), (r) => { CB.decks = r.decks; CB.edit = null; toast(`Deck « ${e.name.trim()} » enregistré.`, "good"); paintArena(); }), null, () => (!e.name.trim() ? "Donne un nom à ton deck." : "")); if (e.choix.length !== n) b.disabled = true; return b; })()),
    el("div", { class: "tools" }, el("h3", { class: "sec small", text: `Choisis ${n} cartes` }), search), grid);
}

/* ---------------- invitation reçue : visible partout dans l'appli ---------------- */
function showInvite(d) {
  CB.recu = d;
  const cards = (d.team || []).length ? el("div", { class: "cbinvteam" }, d.team.map((c) => cardNode(c, null))) : null;
  $("cb-invite").replaceChildren(el("div", { class: "cbinv" },
    el("div", {}, el("b", { text: `${d.from} te défie !` }), el("small", { class: "muted", text: (d.team || []).length ? " Voici ses trois cartes. À toi de composer ton équipe." : " Accepte, puis vous composez vos équipes en même temps." }), waitingClock(d.expire)),
    cards,
    el("div", { class: "row" }, actBtn("Refuser", "small", (b) => answerInvite(b, false)), actBtn("Accepter le combat", "small primary", (b) => answerInvite(b, true)))));
  $("cb-invite").classList.remove("hidden"); refreshArenaDot();
}
function closeInvite() { CB.recu = null; $("cb-invite").classList.add("hidden"); $("cb-invite").replaceChildren(); refreshArenaDot(); }
const refreshArenaDot = () => $("tab-arena-dot").classList.toggle("hidden", S.tab === "arena" || !(CB.defi || CB.duel || CB.recu));
async function answerInvite(btn, ok) {
  const d = CB.recu;
  if (!d) return;
  const r = await act(btn, () => api().combat_answer(d.id, ok), null);
  closeInvite();
  if (!r || !ok || !r.defi) return;
  newChallenge(r.defi); setTab("arena");
}

/* ---------------- le direct : événements de combat ---------------- */
function onCombat(d) {
  if (d.what === "defi") { if (CB.defi || CB.recu) return; showInvite({ id: d.id, from: d.from || "?", expire: d.expire, team: d.team }); ping("info"); toast(`${d.from || "Un joueur"} te défie dans l'arène !`, "info"); return; }
  if (d.what === "go") return startDuel(d.duel);
  if (d.what === "choix") { if (!CB.defi || d.id !== CB.defi.id) return; CB.advChoix = d.cards || []; const z = $("cb-adv"); if (z) z.replaceChildren(...advSlots()); return; }
  if (d.what === "pret") { if (!CB.defi || d.id !== CB.defi.id) return; CB.advPret = true; const z = $("cb-advstate"); if (z) z.textContent = "a validé son équipe"; return; }
  if (d.what === "accepte") {
    if (!CB.defi) return;
    Object.assign(CB, { advChoix: [], advPret: false, monPret: false, choix: [], q: "" }); CB.defi = { ...CB.defi, state: "prepa", expire: d.expire };
    ping("good"); toast(`${d.nom || "Ton adversaire"} a accepté ! Composez vos équipes.`, "good"); refreshArenaDot(); setTab("arena"); paintArena(); return;
  }
  if (d.what === "refuse" || d.what === "annule") {
    Object.assign(CB, { defi: null, choix: [], monPret: false }); closeInvite();
    toast(d.what === "refuse" ? `${d.nom || "Ton adversaire"} a refusé le combat.` : `${d.nom || "Ton adversaire"} a annulé le défi.`);
    if (S.tab === "arena") loadArena();
  }
}
function tickArena() { // compteurs et échéances : ceux de l'arène vivent ici, quelle que soit la page
  document.querySelectorAll("[data-cbclock]").forEach((n) => { n.textContent = clock(cbLeft(+n.dataset.cbclock)); });
  document.querySelectorAll("[data-cbchrono]").forEach((n) => { const s = cbLeft(+n.dataset.cbchrono); n.textContent = clock(s); n.classList.toggle("urgent", s <= 10); });
  if (CB.recu && nowSrv() >= CB.recu.expire) { closeInvite(); toast("Trop tard : le défi a expiré."); }
  if (CB.defi && nowSrv() >= CB.defi.expire) {
    const d = CB.defi; Object.assign(CB, { defi: null, choix: [], monPret: false });
    api().combat_cancel(d.id); toast(d.launched ? `${d.opponent} n'a pas répondu à temps.` : "Trop tard : le défi a expiré.");
    if (S.tab === "arena") loadArena();
  }
}
setInterval(tickArena, 1000);

/* ---------------- le duel : rejoué à partir du détail renvoyé par le serveur ---------------- */
function startDuel(d) {
  CB.duel = d; CB.skip = false; CB.done = false; CB.defi = null; CB.target = null; CB.choix = []; closeInvite(); refreshArenaDot();
  setTab("arena"); paintArena();
}
function fighter(c, side, pv) {
  return el("div", { class: "arfighter", id: "arF" + side }, el("div", { class: "arhp" }, el("b", { text: c.name }), el("div", { class: "hpbar" }, el("i", { style: "width:100%" })),
    el("small", { class: "arpv" }, el("b", { text: fmt(pv) }), ` / ${fmt(pv)} PV`)), cardNode(c, null), el("div", { class: "arfloat" }));
}
function setHp(side, hp, max) {
  const f = $("arF" + side); if (!f) return;
  const pc = Math.max(0, Math.min(100, (100 * hp) / Math.max(1, max))), bar = f.querySelector(".hpbar i");
  bar.style.width = pc + "%"; bar.className = pc <= 0 ? "ko" : pc < 25 ? "low" : pc < 55 ? "mid" : "";
  f.querySelector(".arpv b").textContent = fmt(hp); f.classList.toggle("down", hp <= 0);
}
function floatHit(side, hit) {
  const z = $("arF" + side) && $("arF" + side).querySelector(".arfloat"); if (!z) return;
  const s = el("span", { class: "cbdeg" + (hit.crit ? " crit" : ""), style: `left:${16 + Math.random() * 60}%`, text: `-${fmt(hit.damage)}${hit.crit ? " Coup critique !" : hit.spell_name ? " " + hit.spell_name : ""}` });
  z.append(s); setTimeout(() => s.remove(), 1200);
}
function paintDuel() {
  const d = CB.duel;
  $("cb-body").replaceChildren(el("div", { class: "arena", id: "arena" },
    el("div", { class: "arwho" }, el("b", { text: d.opponent }), el("small", { text: "Équipe adverse" }), el("span", { class: "arscore", id: "arScoreB", text: "0" })),
    el("div", { class: "arstage" }, el("div", { class: "arturn", id: "arTurn", text: "Préparation…" }),
      el("div", { class: "arduo" }, el("div", { id: "arSlotB" }), el("div", { class: "arvs", text: "VS" }), el("div", { id: "arSlotA" })),
      el("div", { class: "arann", id: "arAnn" }), el("div", { class: "arend hidden", id: "arEnd" })),
    el("div", { class: "arwho" }, el("b", { text: d.me }), el("small", { text: "Ton équipe" }), el("span", { class: "arscore", id: "arScoreA", text: "0" }))),
    el("div", { class: "row", id: "arActs" }, actBtn("Passer l'animation", "small", (b) => { CB.skip = true; b.disabled = true; })));
  if (CB.done) finishDuel(); else playDuel();
}
async function playDuel() {
  const run = ++CB.run, d = CB.duel; let sa = 0, sb = 0;
  CB.playing = run;
  for (let i = 0; i < d.rounds.length; i++) {
    const m = d.rounds[i]; if (cbStop(run)) return;
    $("arTurn").textContent = `Manche ${i + 1} sur ${d.rounds.length}`; $("arAnn").textContent = "";
    $("arSlotA").replaceChildren(fighter(d.team_a[i], "A", m.hp_a)); $("arSlotB").replaceChildren(fighter(d.team_b[i], "B", m.hp_b));
    await cbPause(run, 700);
    const step = m.sequential ? 1 : 2;
    for (let k = 0; k < m.hits.length; k += step) {
      if (CB.skip || cbStop(run)) break;
      const ex = m.hits.slice(k, k + step);
      await cbPause(run, 300);
      for (const h of ex) floatHit(h.by === "a" ? "B" : "A", h);
      const last = ex[ex.length - 1]; setHp("A", last.hp_a, m.hp_a); setHp("B", last.hp_b, m.hp_b);
      await cbPause(run, ex.some((h) => h.crit) ? 700 : 520);
    }
    if (cbStop(run)) return;
    setHp("A", m.left_a, m.hp_a); setHp("B", m.left_b, m.hp_b);
    const a = m.winner === "a"; a ? sa++ : sb++;
    $("arScoreA").textContent = String(sa); $("arScoreB").textContent = String(sb);
    const win = (a ? d.team_a : d.team_b)[i].name, lose = (a ? d.team_b : d.team_a)[i].name;
    $("arAnn").className = "arann " + (a ? "win" : "lose"); $("arAnn").textContent = m.ko ? `${win} met ${lose} K.-O. !` : `${win} a battu ${lose}`;
    await cbPause(run, 1500);
  }
  if (!cbStop(run)) finishDuel();
}
function finishDuel() {
  const d = CB.duel, end = $("arEnd"); CB.done = true;
  const acts = $("arActs"); if (acts) acts.remove();
  if (!end) return;
  end.className = "arend " + (d.won ? "win" : "lose");
  end.replaceChildren(el("h2", { text: d.won ? "Victoire !" : "Défaite" }), el("p", { class: "arsc", text: `${d.score_a} – ${d.score_b}` }),
    el("p", { text: d.won ? "Ton équipe remporte le duel." : `${d.opponent} remporte le duel. Ce sera pour la prochaine fois.` }),
    el("p", { class: "price" }, icon("coin"), `+${fmt(d.gain)} Wikiki`),
    el("div", { class: "row" }, actBtn("Retour à l'arène", "primary", () => { CB.run++; CB.duel = null; CB.done = false; refreshArenaDot(); loadArena(); }), el("small", { class: "muted", text: `Combats restants : ${d.left} / ${d.total}` })));
  ping(d.won ? "good" : "bad"); refreshMeSoon();
}
