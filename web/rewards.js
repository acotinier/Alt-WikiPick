"use strict";
/* Récompenses : série de connexion, quêtes du jour, quêtes de bienvenue, succès. Formes lues dans social.js / core.js du site.
   La série, les quêtes et la bienvenue arrivent déjà avec le profil (load_me -> rewards) : aucun appel en plus.
   Les succès sont lus à l'ouverture de l'onglet. Réclamer = un clic, une action : le serveur vérifie tout.
   Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const RW = { ach: null, seq: 0 };
const STREAK_ICON = { wikiki: "coin", paquet: "pack", dore: "pack", minipack: "pack", carte: "cards" };

function rewardsReady() {
  const rw = (S.data && S.data.rewards) || {}, me = (S.data && S.data.me) || {};
  return !!((rw.streak && rw.streak.ready) || (rw.quests || []).some((q) => q.finished && !q.claimed && !q.locked)
    || (rw.welcome || []).some((w) => w.finished && !w.claimed) || me.succes > 0);
}
const untilNode = (secs, prefix) => el("span", { class: "until", "data-until": String(S.meAt + Math.max(0, secs) * 1000), "data-prefix": prefix || "", text: (prefix || "") + clock(secs) });
function tickRewards() {
  document.querySelectorAll("[data-until]").forEach((n) => { n.textContent = n.dataset.prefix + clock(Math.max(0, (+n.dataset.until - Date.now()) / 1000)); });
}
setInterval(tickRewards, 1000);
function bar(done, goal) { return el("div", { class: "rbar" }, el("i", { style: `width:${Math.min(100, Math.round((100 * done) / Math.max(1, goal)))}%` })); }
function progressText(done, goal, finished) { return goal > 1 ? `${fmt(Math.min(done, goal))} / ${fmt(goal)}` : finished ? "C'est fait" : "Pas encore"; }

function claimed(r, fallback) { // une réclamation réussie : on le dit, on relit le profil (le serveur a tout recalculé)
  const what = r.titles.length > 1 ? `${r.titles.length} récompenses` : r.titles[0] || fallback;
  toast(`${what} · ${r.packs ? plural(r.gain, "paquet") + " offert" + (r.gain > 1 ? "s" : "") : "+" + fmt(r.gain) + " Wikiki"}`, "good");
  if (r.gift) setTimeout(() => toast("Bienvenue terminée : un paquet doré de 20 cartes t'attend dans Paquets !", "good"), 900);
  ping("good"); refreshMe();
}

/* ---------------- série de connexion ---------------- */
function streakNode(e) {
  const days = e.days.map((g, i) => {
    const n = i + 1, done = n <= e.done, today = n === e.day && e.open && !e.wait;
    const ic = g.kind === "carte" && g.card ? el("span", { class: "sd-card", style: `--c:${color(g.card.rarity)}` }) : el("span", { class: "sd-ic k-" + g.kind }, icon(STREAK_ICON[g.kind] || "pack"));
    if (g.kind === "carte" && g.card && g.card.img) ic.style.backgroundImage = `url("${g.card.img.replace(/"/g, "%22")}")`;
    return el("div", { class: "sday" + (done ? " done" : "") + (today ? " today" : "") + (today && e.ready ? " ready" : "") + (n === 7 ? " grand" : "") },
      n === 7 ? el("span", { class: "sd-tag", text: "Grand prix" }) : today && !done ? el("span", { class: "sd-tag now", text: "Aujourd'hui" }) : null,
      el("span", { class: "sd-n", text: `Jour ${n}` }), ic, el("span", { class: "sd-t", text: g.text }),
      done ? el("span", { class: "sd-ok" }, icon("check")) : null);
  });
  const foot = !e.open ? el("span", { class: "muted", text: "La série n'est pas encore ouverte : reviens bientôt." })
    : e.wait ? el("span", { class: "muted" }, "Ton compte doit avoir 48 h : ", untilNode(e.wait, "encore "))
      : e.ready ? actBtn(`Récupérer le jour ${e.day} · ${(e.days[e.day - 1] || {}).text || ""}`, "gold", (b) => act(b, () => api().claim("serie"), (r) => {
        const tile = document.querySelectorAll("#rw-top .sday")[r.day - 1];
        if (tile && !reduced()) { tile.style.setProperty("--c", "var(--gold)"); tile.classList.add("burst"); burst(tile, 20); }
        toast(`Jour ${r.day} : ${r.text} !` + (r.kind === "minipack" ? " Il t'attend dans l'Arène." : r.kind === "dore" ? " Il t'attend dans Paquets." : r.kind === "carte" ? " Elle est dans ta collection." : ""), "good");
        ping("good"); refreshMe(); if (r.kind === "carte") collectionChanged();
      }))
        : el("span", { class: "muted" }, "Prochaine récompense dans ", untilNode(e.next));
  return el("section", { class: "rw-card streak" },
    el("header", { class: "rw-head" }, el("span", { class: "flame" }, icon("flame")),
      el("div", {}, el("h3", { text: "Série de connexion" }), el("p", { class: "muted", text: "Connecte-toi chaque jour : la récompense grossit jusqu'au 7e jour." })),
      el("div", { class: "streak-n" }, el("b", { text: String(e.done) }), el("small", { text: "/7" }), el("span", { class: "muted", text: e.done > 1 ? "jours d'affilée" : "jour d'affilée" }))),
    el("div", { class: "strack" }, el("i", { style: `width:${Math.round((100 * Math.min(7, e.done)) / 7)}%` })),
    el("div", { class: "sdays" + (!e.open || e.wait ? " closed" : "") }, days),
    el("footer", { class: "rw-foot" }, el("p", { class: "muted small", text: "Un jour manqué et la série repart au jour 1. Après le 7e jour, elle recommence." }), foot));
}

/* ---------------- quêtes du jour et de bienvenue ---------------- */
function questNode(q) {
  const state = q.locked ? "locked" : q.claimed ? "claimed" : q.finished ? "ready" : "";
  const gain = q.packs ? plural(q.gain, "Mini-Pack") : `${fmt(q.gain)} Wikiki`;
  return el("article", { class: "quest " + state },
    el("div", { class: "q-main" },
      el("span", { class: "q-tag", text: q.locked ? "Verrouillée" : q.claimed ? "Récompense touchée" : q.finished ? "Accomplie" : "Quête du jour" }),
      el("h4", { text: q.title }), q.what ? el("p", { class: "muted", text: q.what }) : null,
      q.locked ? el("p", { class: "muted small", text: "Termine tes quêtes de bienvenue pour ouvrir la quête du jour." }) : null,
      bar(q.done, q.goal),
      el("div", { class: "q-line" }, el("span", { text: progressText(q.done, q.goal, q.finished) }), q.next ? untilNode(q.next, "Nouvelle quête dans ") : null)),
    el("div", { class: "q-side" }, el("span", { class: "q-gain" }, icon(q.packs ? "pack" : "coin"), gain),
      q.claimed ? el("span", { class: "q-done" }, icon("check"), "Réclamée")
        : q.finished && !q.locked ? actBtn(`Réclamer ${gain}`, "gold small", (b) => act(b, () => api().claim("quete", q.packs ? 2 : 1), (r) => claimed(r, q.title)))
          : null));
}
function welcomeNode(list) {
  const toClaim = list.filter((w) => w.finished && !w.claimed), left = list.filter((w) => !w.finished).length;
  return el("section", { class: "rw-card" },
    el("header", { class: "rw-head" }, el("span", { class: "flame gift" }, icon("gift")),
      el("div", {}, el("h3", { text: "Quêtes de bienvenue" }), el("p", { class: "muted", text: left ? "Quelques gestes pour faire le tour du jeu. Au bout, un paquet doré de 20 cartes t'est offert." : "C'est fait : la quête du jour t'est ouverte." })),
      el("span", { class: "pill", text: `${list.filter((w) => w.finished).length} / ${list.length}` })),
    el("div", { class: "wlist" }, list.map((w) => el("div", { class: "wrow" + (w.finished ? " done" : "") },
      el("div", { class: "tx" }, el("b", { text: w.title }), w.what ? el("small", { class: "muted", text: w.what }) : null),
      bar(w.done, w.goal), el("span", { class: "muted small", text: progressText(w.done, w.goal, w.finished) }), el("span", { class: "gainx", text: `+${fmt(w.gain)} W` }),
      w.claimed ? el("span", { class: "q-done" }, icon("check")) : w.finished ? actBtn("Réclamer", "gold small", (b) => act(b, () => api().claim("bienvenue", w.code), (r) => claimed(r, w.title))) : el("span", { class: "muted small", text: "En cours" })))),
    toClaim.length > 1 ? el("footer", { class: "rw-foot end" }, actBtn(`Tout réclamer · ${fmt(toClaim.reduce((t, w) => t + w.gain, 0))} Wikiki`, "gold", (b) => act(b, () => api().claim("bienvenue", null), (r) => claimed(r)))) : null);
}

/* ---------------- succès ---------------- */
function achievementsNode(a) {
  const fam = (f) => a.items.filter((s) => s.family === f);
  return el("section", { class: "rw-ach" },
    el("div", { class: "ach-top" },
      el("div", { class: "pst" }, el("b", { text: `${fmt(a.earned)} / ${fmt(a.total)}` }), el("span", { text: "succès obtenus" })),
      el("div", { class: "pst" }, el("b", { text: `${fmt(a.won)}` }), el("span", { text: "Wikiki déjà gagnés" })),
      el("div", { class: "pst" }, el("b", { text: a.to_claim ? `${fmt(a.to_claim)}` : "—" }), el("span", { text: "Wikiki à réclamer" })),
      a.to_claim ? actBtn(`Tout réclamer · ${fmt(a.to_claim)} Wikiki`, "gold", (b) => act(b, () => api().claim("succes", null), (r) => { claimed(r); loadAchievements(); })) : null),
    a.locked ? el("p", { class: "twarn", text: "Les succès s'ouvrent quand tes quêtes de bienvenue sont terminées." }) : null,
    ...a.families.map((f) => fam(f)).filter((l) => l.length).map((lot) => el("div", { class: "ach-fam" + (a.locked ? " locked" : "") },
      el("div", { class: "fam-head" }, el("h3", { class: "sec small", text: lot[0].family }), el("span", { class: "muted small", text: `${lot.filter((s) => s.claimed).length} / ${lot.length} obtenus` })),
      el("div", { class: "ach-grid" }, lot.map((s) => el("div", { class: "ach" + (s.claimed ? " done" : s.finished ? " ready" : "") },
        el("div", { class: "ach-hd" }, el("b", { text: s.title }), el("span", { class: "gainx", text: `+${fmt(s.gain)} W` })),
        s.what ? el("p", { class: "muted small", text: s.what }) : null, bar(s.done, s.goal),
        el("div", { class: "q-line" }, el("span", { text: progressText(s.done, s.goal, s.finished) }),
          s.claimed ? el("span", { class: "q-done" }, icon("check"), "Obtenu")
            : s.finished && !a.locked ? actBtn("Réclamer", "gold small", (b) => act(b, () => api().claim("succes", s.code), (r) => { claimed(r, s.title); loadAchievements(); })) : null)))))));
}

/* ---------------- l'onglet ---------------- */
function paintRewardsTop() { // série, quêtes, bienvenue : tout vient du profil déjà chargé
  const box = $("rw-top");
  if (!box || !S.data) return;
  const rw = S.data.rewards || {}, parts = [];
  if (rw.streak) parts.push(streakNode(rw.streak));
  if ((rw.welcome || []).some((w) => !w.claimed)) parts.push(welcomeNode(rw.welcome));
  if ((rw.quests || []).length) parts.push(el("section", { class: "quests" }, el("h3", { class: "sec", text: "Quêtes du jour" }), ...rw.quests.map(questNode),
    el("p", { class: "muted small", text: "Une nouvelle quête est tirée chaque nuit à minuit. Les cartes comptent d'où qu'elles viennent : paquet, enchère ou échange." })));
  box.replaceChildren(...(parts.length ? parts : [el("p", { class: "muted", text: "Aucune quête ni série pour le moment : actualise depuis le menu du compte." })]));
}
async function loadAchievements() {
  const mine = ++RW.seq, r = await api().achievements_get();
  if (r.expired) return sessionLost(r);
  if (mine !== RW.seq || S.tab !== "rewards") return;
  const box = $("rw-ach");
  if (!box) return;
  if (!r.ok) { box.replaceChildren(el("p", { class: "muted", text: r.error || "Succès indisponibles." })); return; }
  RW.ach = r; box.replaceChildren(el("h3", { class: "sec", text: "Succès" }), achievementsNode(r));
}
function loadRewards() {
  const body = $("rw-body");
  if (!$("rw-top")) body.replaceChildren(el("div", { id: "rw-top", class: "rw-top" }), el("div", { id: "rw-ach" }));
  paintRewardsTop();
  if (!RW.ach) $("rw-ach").replaceChildren(el("p", { class: "muted", text: "Chargement des succès…" }));
  loadAchievements();
}
