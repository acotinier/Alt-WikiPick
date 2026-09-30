"use strict";
/* La communauté : messagerie, amis, profils des joueurs, guilde. Formes lues dans social.js du site.
   Lectures comme le site ; chaque écriture (message, demande d'ami, action de guilde…) part sur un clic, une à la fois
   (act), avec une confirmation quand elle est difficile à défaire (retirer un ami, bloquer, quitter la guilde…).
   Les textes des autres joueurs sont toujours posés en textContent.
   Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const MS = { with: null, seq: 0 };          // messagerie : la conversation ouverte
const FR = { seq: 0 };                       // amis
const PF = { name: null, data: null, page: 0, q: "", order: "", seq: 0, cseq: 0 }; // profil affiché (name = null : le mien)
const GD = { view: null, tab: "feed", data: null, list: null, open: new Set(), seq: 0, draft: "" }; // guilde

/* ---------------- briques ---------------- */
function avatarNode(name, url, cls = "") {
  const a = el("span", { class: "av " + cls, "aria-hidden": "true" }, el("span", { text: ([...String(name || "?")][0] || "?").toUpperCase() }));
  if (url) { const img = el("img", { alt: "", referrerpolicy: "no-referrer", src: url }); img.onerror = () => img.remove(); a.append(img); }
  return a;
}
function whoLink(name, cls = "") { // un pseudo cliquable : son profil
  return el("button", { class: "who-link " + cls, type: "button", text: name, onclick: (e) => { e.stopPropagation(); openProfile(name); } });
}
const sameName = (a, b) => String(a || "").toLowerCase() === String(b || "").toLowerCase();
function emptyNode(title, text) { return el("div", { class: "empty rich" }, el("b", { text: title }), text ? el("span", { text }) : null); }
async function guarded(call) { // une lecture : null si elle échoue (le message est déjà affiché)
  const r = await call;
  if (r.expired) { sessionLost(r); return null; }
  return r;
}
function sendBox(placeholder, max, onSend) { // champ + bouton d'envoi ; Entrée envoie, Maj+Entrée va à la ligne
  const ta = el("textarea", { class: "field", rows: "1", maxlength: String(max), placeholder });
  const go = el("button", { class: "btn primary icon-send", type: "button", "aria-label": "Envoyer", title: "Envoyer (Entrée)" }, icon("send"));
  const send = () => { if (ta.value.trim()) onSend(ta.value, go, ta); };
  go.onclick = send;
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
  ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(160, ta.scrollHeight) + "px"; });
  return el("div", { class: "sendbox" }, ta, go);
}

/* ---------------- messagerie ---------------- */
function openMessages(name) { MS.with = name || null; setTab("messages"); }
async function loadMessages() {
  const r = await guarded(api().conversations_get());
  if (!r || S.tab !== "messages") return;
  const list = $("ms-list");
  if (!r.ok) { list.replaceChildren(emptyNode("Messagerie indisponible", r.error)); return; }
  list.replaceChildren(...(r.conversations.length ? r.conversations.map((c) => el("button", {
    class: "conv" + (sameName(c.name, MS.with) ? " on" : "") + (c.unread ? " unread" : ""), type: "button",
    onclick: () => { MS.with = c.name; $("ms-find").value = ""; $("ms-found").replaceChildren(); loadMessages(); },
  }, avatarNode(c.name, c.avatar),
    el("span", { class: "tx" }, el("b", {}, c.fav ? el("span", { class: "fav", text: "★ " }) : null, c.name, c.blocked ? el("em", { class: "tagx", text: "Bloqué" }) : null),
      el("small", { text: (c.mine ? "Toi : " : "") + c.last })),
    c.unread ? el("span", { class: "tabn", text: String(c.unread) }) : el("small", { class: "when", text: ago(c.created) })))
    : [el("p", { class: "muted pad", text: "Aucune conversation pour l'instant. Cherche un joueur ci-dessus pour lui écrire." })]));
  loadThread();
}
async function loadThread() {
  const box = $("ms-thread"), name = MS.with;
  if (!name) { box.replaceChildren(emptyNode("Tes conversations", "Choisis une conversation, ou cherche un joueur pour lui écrire.")); box.dataset.with = ""; return; }
  const mine = ++MS.seq;
  const r = await guarded(api().thread_get(name));
  if (!r || mine !== MS.seq || S.tab !== "messages" || MS.with !== name) return;
  if (!r.ok) { box.replaceChildren(emptyNode("Conversation indisponible", r.error)); box.dataset.with = ""; return; }
  const t = r.thread;
  const head = el("header", { class: "ms-head" }, avatarNode(t.with, t.avatar, "md"),
    el("div", {}, whoLink(t.with, "big"), t.friend ? el("span", { class: "pill good", text: "Ami(e)" }) : null),
    el("span", { class: "sp" }),
    t.blocked === "lui" ? null : t.blocked === "moi"
      ? actBtn("Débloquer", "small", (b) => act(b, () => api().friend_action("unblock", t.with), () => { toast(`${t.with} est débloqué(e).`, "good"); loadThread(); }))
      : actBtn("Bloquer", "small ghost", (b) => act(b, () => api().friend_action("block", t.with), () => { toast(`${t.with} est bloqué(e) : vous ne vous verrez plus sur le site.`, "good"); MS.with = null; loadMessages(); }), "Confirmer le blocage"));
  const body = el("div", { class: "ms-body", id: "ms-body" }, ...(t.messages.length
    ? t.messages.map((m) => el("div", { class: "bub" + (m.mine ? " mine" : ""), text: m.text }))
    : [el("p", { class: "muted center", text: `Écris ton premier message à ${t.with}.` })]));
  const foot = t.blocked === "moi" ? el("p", { class: "ms-blocked", text: `Tu as bloqué ${t.with} : vous ne pouvez plus vous écrire.` })
    : t.blocked === "lui" ? el("p", { class: "ms-blocked", text: `Tu ne peux plus écrire à ${t.with}.` })
      : sendBox(`Écrire à ${t.with}…`, 1000, (text, btn, ta) => act(btn, () => api().message_send(t.with, text), () => { ta.value = ""; ta.style.height = "auto"; loadThread(); }));
  const same = box.dataset.with === t.with && box.dataset.blocked === t.blocked && $("ms-body");
  if (same) { box.querySelector(".ms-head").replaceWith(head); $("ms-body").replaceWith(body); } // le champ de saisie garde ce qu'on tape
  else { box.replaceChildren(head, body, foot); box.dataset.with = t.with; box.dataset.blocked = t.blocked; const ta = box.querySelector("textarea"); if (ta) ta.focus(); }
  body.scrollTop = body.scrollHeight;
  if (S.data && S.data.me.unreadMsg) refreshMeSoon(); // la conversation lue : le compteur se met à jour
}
function onMessageEvent(d) { // un message arrive par le flux
  if (S.tab === "messages") { if (sameName(d.from, MS.with)) loadThread(); loadMessages(); }
  else toast(`Nouveau message de ${d.from}`, "info");
  ping("info"); refreshMeSoon();
}

/* ---------------- recherche de joueurs (messagerie, amis) ---------------- */
function playerSearch(input, box, row) {
  input.addEventListener("input", debounce(async () => {
    const q = input.value.trim();
    if (!q) return box.replaceChildren();
    const r = await guarded(api().players_search(q));
    if (!r || input.value.trim() !== q) return;
    box.replaceChildren(...(r.ok && r.users.length ? r.users.map(row) : [el("p", { class: "muted pad", text: r.ok ? "Aucun joueur ne correspond." : r.error })]));
  }, 280));
}
function friendButtons(name, rel, done) { // ce qu'on peut faire avec un joueur, selon votre relation
  const go = (action, ok) => (b) => act(b, () => api().friend_action(action, name), (r) => { toast(r.relation === "friends" ? `${name} et toi êtes maintenant ami(e)s !` : ok, "good"); if (r.relation === "friends") ping("good"); refreshMeSoon(); done(); });
  if (rel === "friends") return [el("span", { class: "pill good", text: "Ami(e)" })];
  if (rel === "outgoing") return [actBtn("Demande envoyée · annuler", "small ghost", go("remove", "Demande annulée."))];
  if (rel === "incoming") return [actBtn("Accepter", "small primary", go("accept", "Demande acceptée.")), actBtn("Refuser", "small ghost", go("decline", "Demande refusée."))];
  return [actBtn("Ajouter en ami(e)", "small primary", go("request", `Demande d'ami(e) envoyée à ${name}.`))];
}

/* ---------------- amis ---------------- */
async function loadFriends() {
  const mine = ++FR.seq, box = $("fr-main");
  if (!box.children.length) box.replaceChildren(el("p", { class: "muted", text: "Chargement…" }));
  const r = await guarded(api().friends_list());
  if (!r || mine !== FR.seq || S.tab !== "friends") return;
  if (!r.ok) { box.replaceChildren(emptyNode("Amis indisponibles", r.error)); return; }
  const row = (u, ...acts) => el("div", { class: "urow" + (u.fav ? " fav" : "") }, avatarNode(u.name, u.avatar), whoLink(u.name), el("span", { class: "sp" }), ...acts);
  const star = (u) => el("button", { class: "icon-btn star" + (u.fav ? " on" : ""), type: "button", title: u.fav ? "Retirer des favoris" : "Mettre en favori : toujours en tête des listes",
    "aria-label": u.fav ? "Retirer des favoris" : "Mettre en favori", onclick: (e) => act(e.currentTarget, () => api().friend_favorite(u.name, !u.fav), () => loadFriends()) }, icon("star"));
  const sections = [];
  if (r.incoming.length) sections.push(el("section", { class: "fr-sec" }, el("h3", { class: "sec small", text: `Demandes reçues · ${r.incoming.length}` }),
    ...r.incoming.map((u) => row(u, ...friendButtons(u.name, "incoming", loadFriends)))));
  sections.push(el("section", { class: "fr-sec" }, el("h3", { class: "sec small", text: `Tes ami(e)s · ${r.friends.length}` }),
    ...(r.friends.length ? r.friends.map((u) => row(u, star(u),
      el("button", { class: "btn small ghost", type: "button", text: "Message", onclick: () => openMessages(u.name) }),
      el("button", { class: "btn small ghost", type: "button", text: "Échanger", onclick: () => openComposer(u.name) }),
      actBtn("Retirer", "small ghost danger-text", (b) => act(b, () => api().friend_action("remove", u.name), () => { toast(`${u.name} ne fait plus partie de tes ami(e)s.`, "good"); loadFriends(); }), "Confirmer le retrait")))
      : [el("p", { class: "muted", text: "Tu n'as pas encore d'ami(e)s. Cherche des joueurs à droite et envoie-leur une demande : les échanges se font entre amis." })])));
  if (r.outgoing.length) sections.push(el("section", { class: "fr-sec" }, el("h3", { class: "sec small", text: "Demandes envoyées" }),
    ...r.outgoing.map((u) => row(u, ...friendButtons(u.name, "outgoing", loadFriends)))));
  box.replaceChildren(...sections);
}

/* ---------------- profils ---------------- */
function openProfile(name) { // le profil d'un joueur (ou le sien)
  PF.name = name && !(S.data && sameName(name, S.data.me.name)) ? name : null;
  PF.data = null; PF.page = 0; PF.q = "";
  closeDialog(); if (!$("modal").classList.contains("hidden")) closeModal();
  setTab("profile");
}
async function loadProfile() {
  const mine = ++PF.seq, box = $("pf-body"), name = PF.name;
  $("page-title").textContent = name ? `Profil de ${name}` : "Profil";
  if (!PF.data) box.replaceChildren(el("p", { class: "muted", text: "Chargement du profil…" }));
  const r = await guarded(api().profile_get(name));
  if (!r || mine !== PF.seq || S.tab !== "profile" || PF.name !== name) return;
  if (!r.ok) { box.replaceChildren(emptyNode("Profil introuvable", r.error)); return; }
  PF.data = r.profile; paintProfile();
}
function paintProfile() {
  const p = PF.data, box = $("pf-body"), rel = p.relation, friendish = p.me || rel === "friends";
  if (p.blocked === "moi") {
    box.replaceChildren(emptyNode(`Tu as bloqué ${p.name}`, "Vous ne vous voyez plus sur le site : ni ses messages, ni son profil."),
      el("div", { class: "row center" }, actBtn("Débloquer", "small", (b) => act(b, () => api().friend_action("unblock", p.name), () => loadProfile()))));
    return;
  }
  const acts = p.me ? [] : [
    rel === "friends" ? el("button", { class: "btn primary small", type: "button", text: "Proposer un échange", onclick: () => openComposer(p.name) }) : null,
    ...(rel === "friends" ? [] : friendButtons(p.name, rel, loadProfile)),
    el("button", { class: "btn small", type: "button", text: "Message", onclick: () => openMessages(p.name) }),
    rel === "friends" ? actBtn("Retirer des ami(e)s", "small ghost danger-text", (b) => act(b, () => api().friend_action("remove", p.name), () => loadProfile()), "Confirmer le retrait") : null,
    actBtn("Bloquer", "small ghost", (b) => act(b, () => api().friend_action("block", p.name), () => { toast(`${p.name} est bloqué(e).`, "good"); loadProfile(); }), "Confirmer le blocage"),
  ].filter(Boolean);
  const since = p.created ? new Date(p.created * 1000).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" }) : "";
  const stat = (n, l, cls = "") => el("div", { class: "pst " + cls }, el("b", { text: n }), el("span", { text: l }));
  box.replaceChildren(
    el("header", { class: "pf-head" }, avatarNode(p.name, p.avatar, "xl"),
      el("div", { class: "pf-id" },
        el("h2", { class: "pf-name" }, p.name, p.me ? null : rel === "incoming" ? el("span", { class: "pill", text: "Veut être ton ami(e)" }) : null),
        el("p", { class: "muted" }, since ? `Membre depuis le ${since}` : "", p.guild ? " · guilde " : "",
          p.guild ? el("button", { class: "who-link", type: "button", text: `[${p.guild.tag}] ${p.guild.name}`, onclick: () => openGuild(p.guild.id) }) : null),
        p.bio ? el("p", { class: "pf-bio", text: p.bio }) : null),
      el("div", { class: "pf-acts" }, acts)),
    el("div", { class: "pf-stats" },
      stat(p.rank ? `#${fmt(p.rank.rank)}` : "—", p.rank ? `au classement, sur ${fmt(p.rank.total)}` : "au classement", "hero"),
      stat(fmt(p.rank ? p.rank.points : 0), "points"), stat(fmt(p.stats.cards), "cartes"), stat(fmt(p.stats.distinct), "différentes"),
      stat(fmt(p.stats.legend), "légendaires", "legend"), stat(fmt(p.stats.sales), "ventes"), stat(fmt(p.friends), p.friends > 1 ? "ami(e)s" : "ami(e)")),
    showcasesNode(p),
    el("div", { class: "pf-coll-head" }, el("h3", { class: "sec", text: p.me ? "Ma collection" : "Sa collection" }), el("small", { id: "pf-total", class: "muted" })),
    friendish ? collectionTools() : emptyNode("Collection réservée aux ami(e)s", `Ajoute ${p.name} en ami(e) pour voir toute sa collection et lui proposer des échanges.`),
    friendish ? el("div", { class: "grid", id: "pf-grid" }) : null,
    friendish ? el("div", { class: "more", id: "pf-pager" }) : null);
  if (friendish) loadPlayerCards();
}
function showcasesNode(p) {
  const head = el("h3", { class: "sec", text: "Vitrines" });
  if (p.private_showcases) return el("div", {}, head, el("p", { class: "muted", text: `Ajoute ${p.name} en ami(e) pour voir ses vitrines.` }));
  if (!p.showcases.length) return el("div", {}, head, el("p", { class: "muted", text: p.me ? "Tu n'as pas encore de vitrine : elles se créent sur wiki-pick.com, dans ton profil." : `${p.name} n'expose encore aucune carte.` }));
  return el("div", {}, head, ...p.showcases.map((v) => el("section", { class: "vitrine" },
    el("header", {}, el("b", { text: v.name }), el("small", { class: "muted", text: `${v.cards.length} / ${p.slots}` })),
    el("div", { class: "vgrid" }, ...v.cards.map((c) => cardNode(c, () => openModal(fullCard(c))))))));
}
function collectionTools() {
  const q = el("input", { class: "field", type: "search", placeholder: "Chercher une carte…", autocomplete: "off", value: PF.q });
  q.addEventListener("input", debounce(() => { PF.q = q.value.trim(); PF.page = 0; loadPlayerCards(); }, 280));
  const order = el("select", { "aria-label": "Ordre" }, el("option", { value: "", text: "Plus rares d'abord" }), el("option", { value: "asc", text: "Plus communes d'abord" }));
  order.value = PF.order; order.onchange = () => { PF.order = order.value; PF.page = 0; loadPlayerCards(); };
  return el("div", { class: "toolbar" }, q, order);
}
async function loadPlayerCards() {
  const p = PF.data, mine = ++PF.cseq, grid = $("pf-grid");
  if (!p || !grid) return;
  grid.classList.add("dim");
  const r = await guarded(api().player_cards(p.name, PF.page, PF.q, [], PF.order));
  if (!r || mine !== PF.cseq || !grid.isConnected) return;
  grid.classList.remove("dim");
  if (!r.ok) { grid.replaceChildren(emptyNode("Collection indisponible", r.error)); return; }
  PF.page = r.page;
  $("pf-total").textContent = r.total ? plural(r.total, PF.q ? "carte trouvée" : "carte différente", PF.q ? "cartes trouvées" : "cartes différentes") : "";
  grid.replaceChildren(...(r.cards.length ? r.cards.map((x, i) => { const n = cardNode({ ...x.card, copies: x.n }, () => openModal(fullCard(x.card))); n.classList.add("enter"); n.style.setProperty("--k", String(Math.min(i, 20))); return n; })
    : [el("div", { class: "empty", text: PF.q ? "Aucune carte ne correspond." : "Aucune carte pour l'instant." })]));
  const prev = el("button", { class: "btn small ghost", type: "button", text: "← Précédent", onclick: () => { PF.page--; loadPlayerCards(); } });
  const next = el("button", { class: "btn small ghost", type: "button", text: "Suivant →", onclick: () => { PF.page++; loadPlayerCards(); } });
  prev.disabled = r.page <= 0; next.disabled = r.page >= r.pages - 1;
  $("pf-pager").replaceChildren(...(r.pages > 1 ? [prev, el("span", { class: "muted", text: `Page ${r.page + 1} / ${fmt(r.pages)}` }), next] : []));
}

/* ---------------- guilde ---------------- */
function openGuild(id) { GD.view = id; GD.tab = "feed"; GD.data = null; setTab("guild"); }
const guildTag = (g) => { const t = el("span", { class: "gtag", text: g.tag || "?" }); if (g.color) t.style.setProperty("--g", g.color); return t; };
async function loadGuild() {
  const mine = ++GD.seq, box = $("gd-body");
  if (!GD.data && !GD.list) box.replaceChildren(el("p", { class: "muted", text: "Chargement des guildes…" }));
  const l = await guarded(api().guilds_get());
  if (!l || mine !== GD.seq || S.tab !== "guild") return;
  if (!l.ok) { box.replaceChildren(emptyNode("Guildes indisponibles", l.error)); return; }
  GD.list = l;
  const gid = GD.view || l.mine;
  if (!gid) { GD.data = null; return paintGuildLobby(); }
  const r = await guarded(api().guild_get(gid));
  if (!r || mine !== GD.seq || S.tab !== "guild") return;
  if (!r.ok) { GD.view = null; GD.data = null; return paintGuildLobby(); }
  GD.data = r.guild;
  if (!GD.data.is_member && !["members", "board"].includes(GD.tab)) GD.tab = "members";
  paintGuild();
}
function boardNode() {
  const l = GD.list;
  if (!l.guilds.length) return emptyNode("Aucune guilde pour l'instant", "Sois le premier à en fonder une.");
  return el("div", { class: "gboard" }, el("div", { class: "grow head" }, el("span", { text: "#" }), el("span", { text: "Guilde" }), el("span", { class: "n", text: "Membres" }), el("span", { class: "n", text: "Points" }), el("span")),
    ...l.guilds.map((g) => el("div", { class: "grow" + (g.id === l.mine ? " mine" : "") },
      el("span", { class: "rk", text: String(g.rank || "—") }),
      el("span", { class: "gname" }, guildTag(g), el("span", {}, el("button", { class: "who-link", type: "button", text: g.name, onclick: () => openGuild(g.id) }),
        el("small", { class: "muted", text: `chef : ${g.leader || "—"}` + (g.descr ? ` · ${g.descr}` : "") }))),
      el("span", { class: "n", text: fmt(g.members) }), el("span", { class: "n pts", text: fmt(g.score) }),
      el("span", { class: "n" }, g.id === l.mine ? el("span", { class: "pill", text: "Ta guilde" }) : l.mine ? null : applyButton(g)))));
}
function applyButton(g) {
  return g.applied
    ? actBtn("Demande envoyée · annuler", "small ghost", (b) => act(b, () => api().guild_action("apply/cancel", g.id), () => { toast("Demande annulée.", "good"); loadGuild(); }))
    : actBtn("Demander à rejoindre", "small primary", (b) => act(b, () => api().guild_action("apply", g.id), () => { toast("Demande envoyée au chef de la guilde.", "good"); loadGuild(); }));
}
function paintGuildLobby() {
  const name = el("input", { class: "field", maxlength: "30", placeholder: "Les Encyclopédistes" });
  const tag = el("input", { class: "field upper", maxlength: "5", placeholder: "WIKI" });
  const descr = el("textarea", { class: "field", maxlength: "200", rows: "3", placeholder: "Ce qui rassemble ta guilde" });
  const create = actBtn("Fonder la guilde", "primary", (b) => act(b, () => api().guild_action("create", { name: name.value, tag: tag.value, descr: descr.value }),
    () => { toast("Ta guilde est fondée !", "good"); ping("good"); GD.view = null; loadGuild(); }),
  () => `Confirmer : fonder « ${name.value.trim()} »`, () => (name.value.trim().length < 2 || !/^[a-z0-9]{2,5}$/i.test(tag.value.trim()) ? "Donne un nom (2 caractères au moins) et un blason de 2 à 5 lettres ou chiffres." : ""));
  $("gd-body").replaceChildren(
    el("p", { class: "muted intro", text: "Une guilde vaut ce que valent les collections de ses membres : quand l'un d'eux sort une grosse carte, toute la guilde monte avec lui. Le fil et le tchat ne se lisent que de l'intérieur." }),
    el("div", { class: "gd-lobby" }, boardNode(),
      el("aside", { class: "gd-create" }, el("h3", { class: "sec small", text: "Fonder une guilde" }),
        el("label", { class: "lab", text: "Nom" }), name, el("label", { class: "lab", text: "Blason (2 à 5 lettres)" }), tag,
        el("label", { class: "lab", text: "Description" }), descr, create)));
}
function paintGuild() {
  const g = GD.data, l = GD.list, inside = g.is_member;
  const tabs = (inside ? [["feed", "Le fil", g.feed.length], ["chat", "Tchat"], ["members", "Membres", g.members.length]] : [["members", "Membres", g.members.length]])
    .concat(g.is_manager ? [["apply", "Demandes", g.applications.length]] : []).concat([["board", "Classement des guildes"]]);
  if (!tabs.some(([k]) => k === GD.tab)) GD.tab = tabs[0][0];
  const acts = [
    GD.view && GD.view !== l.mine ? el("button", { class: "btn small ghost", type: "button", text: "Toutes les guildes", onclick: () => { GD.view = null; GD.data = null; loadGuild(); } }) : null,
    !inside && !l.mine ? applyButton(g) : null,
    inside ? actBtn("Quitter la guilde", "small ghost danger-text", (b) => act(b, () => api().guild_action("leave"), (r) => {
      toast(r.dissolved ? "Tu étais le dernier membre : la guilde est dissoute." : "Tu as quitté la guilde.", "good"); GD.view = null; GD.data = null; loadGuild();
    }), "Confirmer : quitter") : null,
  ].filter(Boolean);
  const stat = (n, l2) => el("div", { class: "pst" }, el("b", { text: n }), el("span", { text: l2 }));
  $("gd-body").replaceChildren(
    el("header", { class: "gd-head" }, guildTag(g), el("div", {}, el("h2", { class: "pf-name", text: g.name }), el("p", { class: "muted", text: g.descr || "Pas de description." })),
      el("span", { class: "sp" }), el("div", { class: "pf-acts" }, acts)),
    el("div", { class: "pf-stats" }, stat(`#${g.rank || "—"}`, `sur ${plural(g.count, "guilde")}`), stat(fmt(g.score), "points de guilde"),
      stat(`${fmt(g.members.length)} / ${fmt(g.max_members)}`, "membres"), stat(g.leader || "—", "chef de guilde")),
    el("div", { class: "seg gd-tabs", role: "group" }, tabs.map(([k, t, n]) => el("button", { class: GD.tab === k ? "on" : "", type: "button", onclick: () => { GD.tab = k; paintGuild(); } },
      t, n ? el("i", { class: "segn", text: String(n) }) : null))),
    el("div", { id: "gd-tab" }, guildTabNode()));
  if (GD.tab === "chat") { const b = $("gd-chat"); if (b) b.scrollTop = b.scrollHeight; seenGuildChat(); }
}
function guildTabNode() {
  const g = GD.data;
  if (GD.tab === "board") return boardNode();
  if (GD.tab === "apply") return g.applications.length ? el("div", { class: "ulist" }, ...g.applications.map((a) => el("div", { class: "urow" },
    avatarNode(a.name), el("span", {}, whoLink(a.name), el("small", { class: "muted", text: ` a demandé ${ago(a.created)}` })), el("span", { class: "sp" }),
    actBtn("Accepter", "small primary", (b) => act(b, () => api().guild_action("apply/accept", a.name), () => { toast(`${a.name} rejoint la guilde !`, "good"); loadGuild(); })),
    actBtn("Refuser", "small ghost", (b) => act(b, () => api().guild_action("apply/decline", a.name), () => { toast("Demande refusée.", "good"); loadGuild(); }), "Confirmer le refus"))))
    : emptyNode("Aucune demande en attente", "Quand un joueur demande à rejoindre ta guilde, il apparaît ici.");
  if (GD.tab === "members") return el("div", { class: "gboard" }, el("div", { class: "grow mem head" }, el("span", { text: "#" }), el("span", { text: "Membre" }), el("span", { class: "n", text: "Points apportés" }), el("span")),
    ...g.members.map((m, i) => el("div", { class: "grow mem" + (m.me ? " mine" : "") }, el("span", { class: "rk", text: String(i + 1) }),
      el("span", { class: "gname" }, whoLink(m.name), m.leader ? el("span", { class: "pill gold", text: "Chef" }) : m.officer ? el("span", { class: "pill", text: "Officier" }) : null,
        m.joined ? el("small", { class: "muted", text: `membre ${ago(m.joined)}` }) : null),
      el("span", { class: "n pts", text: fmt(m.total) }),
      el("span", { class: "n acts" },
        g.is_leader && !m.me ? actBtn(m.officer ? "Retirer officier" : "Nommer officier", "small ghost", (b) => act(b, () => api().guild_action("officier", m.name, !m.officer), () => loadGuild()),
          m.officer ? "Confirmer : retirer" : "Confirmer : nommer") : null,
        g.is_manager && !m.me && !m.leader && (g.is_leader || !m.officer) ? actBtn("Exclure", "small ghost danger-text", (b) => act(b, () => api().guild_action("kick", m.name), () => loadGuild()), "Confirmer l'exclusion") : null))));
  if (GD.tab === "chat") {
    const list = el("div", { class: "ms-body gd-chat", id: "gd-chat" }, ...(g.chat.length ? g.chat.map((m) => {
      const me = S.data && m.uid === S.data.me.id;
      return el("div", { class: "bub" + (me ? " mine" : "") }, me ? null : el("b", { class: "bub-who", text: m.name }), el("span", { text: m.text }), el("small", { text: ago(m.ts) }));
    }) : [el("p", { class: "muted center", text: "Personne n'a encore parlé ici. Lance la discussion." })]));
    const box = sendBox("Écris à ta guilde…", 400, (text, btn, ta) => act(btn, () => api().guild_action("chat", null, text), () => { ta.value = ""; GD.draft = ""; loadGuild(); }));
    const ta = box.querySelector("textarea"); ta.value = GD.draft; ta.addEventListener("input", () => { GD.draft = ta.value; });
    return el("div", { class: "gd-chatwrap" }, list, box);
  }
  if (!g.feed.length) return emptyNode("Rien d'exceptionnel pour l'instant", "Dès qu'un membre tire une légendaire, une mythique ou une carte chromatique, elle s'affiche ici.");
  return el("div", { class: "gfeed" }, ...g.feed.map((f) => {
    const open = GD.open.has(f.id), what = f.card.shiny ? "une carte chromatique" : `une ${label(f.card.rarity).toLowerCase()}`;
    const like = el("button", { class: "pact" + (f.liked ? " on" : ""), type: "button", "aria-label": "J'aime" }, icon("heart"), el("span", { text: String(f.likes) }));
    like.onclick = () => act(like, () => api().guild_action("like", f.id), (r) => { f.liked = r.liked; f.likes = Math.max(0, f.likes + (r.liked ? 1 : -1)); like.classList.toggle("on", r.liked); like.lastChild.textContent = String(f.likes); });
    const comments = open ? el("div", { class: "gcom" }, ...f.comments.map((c) => el("div", { class: "cm" }, whoLink(c.name), el("span", { text: " " + c.text }), el("small", { class: "muted", text: " · " + ago(c.ts) }),
      c.can_delete ? actBtn("Supprimer", "small ghost", (b) => act(b, () => api().guild_action("comment/delete", c.id), () => loadGuild()), "Confirmer") : null)),
      sendBox("Féliciter, commenter…", 400, (text, btn, ta) => act(btn, () => api().guild_action("comment", f.id, text), () => { ta.value = ""; loadGuild(); }))) : null;
    return el("article", { class: "gf" }, el("div", { class: "gf-card" }, cardNode(f.card, () => openModal(fullCard(f.card)))),
      el("div", { class: "gf-body" },
        el("p", { class: "gf-title" }, whoLink(f.name), " a sorti ", el("b", { style: `color:${color(f.card.rarity)}`, text: what })),
        el("p", { class: "muted", text: `« ${f.card.name} » · ${ago(f.ts)}` }),
        el("div", { class: "gf-acts" }, like, el("button", { class: "pact" + (open ? " on" : ""), type: "button", onclick: () => { open ? GD.open.delete(f.id) : GD.open.add(f.id); paintGuild(); } },
          icon("chat"), el("span", { text: String(f.comments.length) })), el("span", { class: "sp" }), el("span", { class: "pts", text: `+${fmt(f.points)} pts` })),
        comments));
  }));
}
function seenGuildChat() { // le tchat de SA guilde est à l'écran : le site le note, la pastille s'éteint
  const gc = S.data && S.data.rewards && S.data.rewards.guild_chat;
  if (!gc || !GD.data || GD.data.id !== gc.guild || !(gc.last > gc.seen)) return;
  gc.seen = gc.last; renderSocialBadges(); api().guild_chat_seen();
}
const refreshGuildSoon = debounce(() => {
  const a = document.activeElement;
  if (S.tab === "guild" && !($("gd-body").contains(a) && /^(INPUT|TEXTAREA)$/.test(a.tagName) && a.value)) loadGuild(); // ce qu'on tape n'est pas écrasé
}, 600);
function onGuildEvent(d) { // une nouvelle de SA guilde (le flux ne laisse passer que celles-là)
  const gc = S.data && S.data.rewards && S.data.rewards.guild_chat;
  if (d.what === "chat" && gc && !(S.data && d.par === S.data.me.id)) { gc.last = Math.max(gc.last, d.mid || 0, gc.seen + 1); renderSocialBadges(); }
  if (S.tab === "guild") refreshGuildSoon();
}

/* ---------------- pastilles du rail ---------------- */
let streakToast = false;
function renderSocialBadges() {
  if (!S.data) return;
  const me = S.data.me, rw = S.data.rewards || {};
  const set = (id, n) => { const b = $(id); b.textContent = n > 99 ? "99+" : String(n); b.classList.toggle("hidden", !(n > 0)); };
  set("tab-messages-n", me.unreadMsg || 0); set("tab-friends-n", me.friendReq || 0);
  const gc = rw.guild_chat; $("tab-guild-dot").classList.toggle("hidden", !(gc && gc.last > gc.seen) || S.tab === "guild" && GD.tab === "chat");
  const ready = rewardsReady(); $("tab-rewards-dot").classList.toggle("hidden", !ready);
  if (rw.streak && rw.streak.ready && !streakToast) { streakToast = true; setTimeout(() => toast(`Série de connexion : le jour ${rw.streak.day} t'attend dans Récompenses.`, "info"), 1200); }
  if (S.tab === "rewards") paintRewardsTop();
}

function bindCommunity() {
  playerSearch($("ms-find"), $("ms-found"), (u) => el("button", { class: "conv", type: "button", onclick: () => { MS.with = u.name; $("ms-find").value = ""; $("ms-found").replaceChildren(); loadMessages(); } },
    avatarNode(u.name, u.avatar), el("span", { class: "tx" }, el("b", { text: u.name }), el("small", { text: u.me ? "Toi" : u.relation === "friends" ? "Ami(e)" : "Joueur" }))));
  playerSearch($("fr-find"), $("fr-found"), (u) => el("div", { class: "urow" }, avatarNode(u.name, u.avatar), whoLink(u.name), el("span", { class: "sp" }),
    ...(u.me ? [el("span", { class: "pill", text: "Toi" })] : friendButtons(u.name, u.relation, () => { $("fr-find").dispatchEvent(new Event("input")); loadFriends(); }))));
}
