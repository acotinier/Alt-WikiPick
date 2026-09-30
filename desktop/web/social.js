"use strict";
/* Échanges et classement, en lecture seule. Formes lues dans le JS du site (docs/API.md §2.5).
   Les actions (accepter, refuser, annuler, proposer) sont dans actions.js : manuelles, avec confirmation.
   Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const TR = { box: "received", seq: 0 };
const RK = { period: "tout", seq: 0 };
const T_STATUS = { pending: "En attente", accepted: "Accepté", declined: "Refusé", cancelled: "Annulé",
  invalid: "Annulé : cartes indisponibles", countered: "Remplacé par une contre-proposition" };
const T_EMPTY = {
  received: "Aucune proposition reçue. Quand un joueur te propose un échange, il apparaît ici.",
  sent: "Aucune proposition en attente. Elles se font depuis le profil d'un joueur, sur le site.",
  history: "Aucun échange terminé. Les échanges acceptés, refusés ou annulés apparaîtront ici.",
};
const R_PERIODS = { semaine: "cette semaine", mois: "ce mois-ci", tout: "depuis le début" };

function duration(s) { // 3 j 4 h, 2 h 10 min, 5 min
  s = Math.max(0, s | 0);
  const j = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return j ? `${j} j ${h} h` : h ? `${h} h ${m} min` : `${Math.max(1, m)} min`;
}
const openSite = () => api().open_url("https://wiki-pick.com/");

/* ---------------- échanges ---------------- */
async function loadTrades(reset = false) {
  const mine = ++TR.seq, list = $("t-list");
  document.querySelectorAll("#t-boxes button").forEach((b) => b.classList.toggle("on", b.dataset.box === TR.box));
  if (reset || !list.children.length) list.replaceChildren(el("div", { class: "empty", text: "Chargement…" }));
  const r = await api().load_trades(TR.box);
  if (mine !== TR.seq) return;
  if (r.expired) return sessionLost(r);
  if (!r.ok) { list.replaceChildren(el("div", { class: "empty", text: r.error || "Échanges indisponibles" })); return; }
  setSkew(r.now);
  list.replaceChildren(...(r.trades.length ? r.trades.map(tradeNode) : [el("div", { class: "empty", text: T_EMPTY[TR.box] })]));
  $("t-count").textContent = plural(r.trades.length, "échange");
}

function tradeNode(t) {
  const col = (title, cards, coins) => el("div", { class: "tcol" },
    el("h3", { text: title }),
    el("div", { class: "tcards" }, cards.map((c) => cardNode(c, () => openModal(c)))),
    coins ? el("div", { class: "price" }, icon("coin"), fmt(coins)) : null,
    !cards.length && !coins ? el("small", { class: "muted", text: "Rien" }) : null);
  const when = ago(t.created) + (t.closed ? `, terminé ${ago(t.closed)}` : "");
  return el("article", { class: "trade" },
    el("header", { class: "thd" },
      el("div", {}, el("b", { text: t.incoming ? `${t.other} te propose un échange` : `Ta proposition à ${t.other}` }), el("small", { text: when })),
      T_STATUS[t.status] ? el("span", { class: "tstatus " + t.status, text: T_STATUS[t.status] }) : null),
    t.message ? el("p", { class: "tmsg", text: `« ${t.message} »` }) : null,
    t.valid ? null : el("p", { class: "twarn", text: "Une des cartes n'est plus disponible : cet échange ne peut plus être conclu." }),
    el("div", { class: "tcols" }, col("Tu donnes", t.give, t.give_coins), el("span", { class: "tswap" }, icon("swap")), col("Tu reçois", t.get, t.get_coins)),
    tradeButtons(t));
}

/* ---------------- classement ---------------- */
async function loadRanking() {
  const mine = ++RK.seq, box = $("r-table");
  document.querySelectorAll("#r-periods button").forEach((b) => b.classList.toggle("on", b.dataset.period === RK.period));
  if (!box.children.length) box.replaceChildren(el("div", { class: "empty", text: "Calcul du classement…" }));
  const r = await api().load_ranking(RK.period);
  if (mine !== RK.seq) return;
  if (r.expired) return sessionLost(r);
  if (!r.ok) { box.replaceChildren(el("div", { class: "empty", text: r.error || "Classement indisponible" })); return; }
  renderRanking(r);
}

function rankMe(r) { // ta position : le total vient de la collection, les périodes du tableau
  const own = (S.data && S.data.rank) || {}, row = r.top.find((x) => x.me);
  if (RK.period === "tout" && own.rank) {
    const gap = own.toNext != null && own.nextName ? `${fmt(own.toNext)} points pour dépasser ${own.nextName}` : "";
    return el("div", { class: "rk-me" }, el("span", { class: "big", text: `#${fmt(own.rank)}` }),
      el("div", {}, el("b", { text: `sur ${fmt(own.total)} joueurs, ${fmt(own.points)} points` }), gap ? el("small", { text: gap }) : null));
  }
  return el("div", { class: "rk-me" }, row
    ? [el("span", { class: "big", text: `#${fmt(row.rank)}` }), el("div", {}, el("b", { text: `${R_PERIODS[RK.period]}, ${fmt(row.points)} points` }))]
    : [el("div", {}, el("b", { text: "Tu n'apparais pas dans le classement affiché." }))]);
}

function renderRanking(r) {
  const dot = (k) => `--c:${color(k)}`;
  const legend = RARITY_ORDER.filter((k) => r.points[k] != null).map((k) => el("span", { class: "pt", style: dot(k) }, `${label(k)} ${fmt(r.points[k])}`));
  if (r.chroma_points) legend.push(el("span", { class: "pt", style: "--c:var(--text)" }, `Chromatique ${fmt(r.chroma_points)}`));
  const rule = r.rule === "acquis"
    ? "Seules comptent les cartes ouvertes dans un paquet ou remportées aux enchères pendant la période, et encore dans ta collection. Les échanges et les cadeaux ne rapportent pas de points."
      + (r.reset_in ? ` Remise à zéro dans ${duration(r.reset_in)}.` : "")
    : r.rule === "glissant" ? "Sur une semaine ou un mois, seules comptent les cartes obtenues pendant la période." : "";
  $("r-me").replaceChildren(rankMe(r));
  $("r-rule").replaceChildren(el("span", { text: "Plus une carte est rare, plus elle rapporte de points. À points égaux, celui qui possède le plus de cartes passe devant. " + rule }),
    el("div", { class: "ptline" }, legend));
  const head = el("div", { class: "rrow head" }, el("span", { text: "Rang" }), el("span", { text: "Joueur" }),
    ...[["chroma", "Chromatiques", "var(--text)"], ["mythic", "Mythiques", color("M")], ["legend", "Légendaires", color("L")], ["ultra", "Exceptionnelles", color("UR")]]
      .map(([, t, c]) => el("span", { class: "n", style: `--c:${c}`, text: t })),
    el("span", { class: "n", text: "Cartes" }), el("span", { class: "n", text: "Points" }));
  const rows = r.top.map((x) => el("div", { class: "rrow" + (x.me ? " me" : "") + (x.rank <= 3 ? " top3" : "") },
    el("span", { class: "rk", text: String(x.rank) }),
    el("span", { class: "who" }, el("b", { text: x.name }), x.guild ? el("small", { text: x.guild }) : null, x.me ? el("em", { text: "Toi" }) : null),
    el("span", { class: "n c1", text: fmt(x.chroma) }), el("span", { class: "n c2", text: fmt(x.mythic) }),
    el("span", { class: "n c3", text: fmt(x.legend) }), el("span", { class: "n c4", text: fmt(x.ultra) }),
    el("span", { class: "n", text: fmt(x.cards) }), el("span", { class: "n pts", text: fmt(x.points) })));
  $("r-table").replaceChildren(...(rows.length ? [head, ...rows] : [el("div", { class: "empty", text: "Personne n'est encore classé." })]));
}

function bindSocial() {
  document.querySelectorAll("#t-boxes button").forEach((b) => { b.onclick = () => { TR.box = b.dataset.box; loadTrades(true); }; });
  document.querySelectorAll("#r-periods button").forEach((b) => { b.onclick = () => { RK.period = b.dataset.period; $("r-table").replaceChildren(); loadRanking(); }; });
}
