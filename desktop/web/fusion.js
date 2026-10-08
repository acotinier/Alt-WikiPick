"use strict";
/* Fusion : 2 ou 3 cartes du même rang -> une carte du rang au-dessus, ou toutes sont perdues. Lot automatique : une double
   confirmation (bouton armé), puis le serveur local fait UNE fusion à la fois (0,2 s de pause entre deux) jusqu'à l'objectif ; il
   s'arrête à la moindre erreur, sur « Arrêter », ou si cette page ne vient plus voir où il en est (le sondage ci-dessous le garde en vie).
   Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const FU = { st: null, rank: null, size: 3, dups: true, count: 30, sel: [], page: 0, job: null, timer: 0, seq: 0 };
const FU_REASONS = { done: "Objectif atteint.", empty: "Il ne reste plus assez de cartes éligibles.", stopped: "Arrêté.", away: "Arrêté : l'appli n'a plus donné signe de vie." };

const fuRecipe = () => FU.st && FU.st.recipes.find((x) => x.rank === FU.rank);
const fuRunning = () => !!(FU.job && FU.job.running);

async function loadFusion(rank = FU.rank, page = 0) {
  const seq = ++FU.seq, body = $("fu-body");
  if (!FU.st) body.replaceChildren(el("p", { class: "muted", text: "L'atelier s'allume…" }));
  const d = await api().fusion_get(rank, page);
  if (seq !== FU.seq) return;
  if (d.expired) return sessionLost(d);
  if (!d.ok) return body.replaceChildren(el("p", { class: "note", text: d.error || "Atelier indisponible." }));
  FU.st = d; FU.rank = d.rank; FU.page = d.page; FU.sel = [];
  if (!d.recipes.some((x) => x.rank === FU.rank) && d.recipes.length) FU.rank = d.recipes[0].rank;
  if (!FU.timer) { const j = await api().fusion_job(); if (j.ok && j.job && j.job.running) { FU.job = j.job; watchFusion(); } } // un lot déjà en route
  paintFusion();
}

/* ---- le suivi du lot : demandé toutes les secondes, même quand on regarde un autre onglet (c'est ce qui le garde en vie) */
function watchFusion() {
  if (FU.timer) return;
  FU.timer = setInterval(pollFusion, 1000);
  pollFusion();
}
async function pollFusion() {
  const r = await api().fusion_job();
  if (r.expired) { clearInterval(FU.timer); FU.timer = 0; return sessionLost(r); }
  if (!r.ok) return; // un raté passager : on réessaie à la seconde suivante
  const was = fuRunning();
  FU.job = r.job;
  if (!fuRunning()) { clearInterval(FU.timer); FU.timer = 0; if (was) refresh(); } // la collection a changé
  const dot = $("tab-fusion-dot"); if (dot) dot.classList.toggle("hidden", !fuRunning());
  if (S.tab === "fusion") paintFusion();
}

/* ---- l'écran */
function fuHelp() {
  const st = FU.st;
  const rows = st ? st.recipes.map((x) => el("tr", {},
    el("td", {}, el("span", { style: `color:${color(x.rank)}`, text: label(x.rank) }), " → ", el("span", { style: `color:${color(x.to)}`, text: label(x.to) })),
    el("td", { class: "num", text: `${x.base} %` + (x.chance > x.base ? ` +${x.chance - x.base}` : "") }),
    el("td", { class: "num", text: `${x.base2} %` + (x.chance2 > x.base2 ? ` +${x.chance2 - x.base2}` : "") }))) : [];
  openDialog("Comment fonctionne la fusion", el("div", { class: "fu-help" },
    el("p", {}, "Pose ", el("b", { text: "2 ou 3 cartes du même rang" }), " : le creuset tente d'en faire ", el("b", { text: "une carte du rang au-dessus" }),
      ", tirée au hasard. Si la fusion rate, ", el("b", { text: "toutes les cartes posées sont perdues" }), ", mais ta maîtrise grandit : chaque échec d'affilée ajoute des points de chance sur ce rang."),
    st ? el("table", {}, el("thead", {}, el("tr", {}, el("th", { text: "Rang" }), el("th", { text: "3 cartes" }), el("th", { text: "2 cartes" }))), el("tbody", {}, rows)) : null,
    st ? el("p", { class: "muted", text: `Chaque échec ajoute ${st.bonus} points (à 3 cartes) ou ${st.bonus2} points (à 2 cartes) à la tentative suivante sur le même rang.` }) : null,
    el("ul", {},
      el("li", { text: "Les cartes verrouillées, chromatiques ou exclusives ne se fusionnent pas et n'apparaissent pas ici." }),
      el("li", { text: "Les légendaires ne se fusionnent pas ; les mythiques ne se trouvent que dans les paquets." }),
      el("li", { text: "Les cartes consommées comptent comme recyclées pour les défis de recyclage." }),
      el("li", { text: "Fusion automatique : une fusion à la fois, à la suite, jusqu'au nombre de cartes choisi. Elle s'arrête si tu l'arrêtes, s'il n'y a plus de cartes éligibles ou à la moindre erreur. Avec « Doublons seulement », seuls les exemplaires en trop sont utilisés." }))));
}

function fuTally(job) {
  const t = (n, text, cls) => el("div", {}, el("b", { class: "num " + (cls || ""), text: fmt(n) }), el("span", { text }));
  return el("div", { class: "fu-tally" }, t(job.won, "réussies", "ok"), t(job.lost, "ratées", "ko"), t(job.used, "cartes utilisées"), t(job.new, "nouvelles"));
}

function paintFusion() {
  const body = $("fu-body"), st = FU.st, job = FU.job;
  if (!st) return;
  const chips = el("div", { class: "fu-chips", role: "group", "aria-label": "Rang à fusionner" }, st.recipes.map((x) => el("button", {
    class: "fu-chip" + (x.rank === FU.rank ? " on" : "") + (x.avail < 2 ? " dim" : ""), style: `--c:${color(x.rank)}`, "data-rank": x.rank, ...(fuRunning() ? { disabled: "" } : {}),
    onclick: () => { if (!fuRunning() && x.rank !== FU.rank) loadFusion(x.rank, 0); },
  }, label(x.rank), el("small", { class: "num", text: fmt(x.avail) }))));
  const head = el("div", { class: "fu-top" }, chips, el("button", { class: "btn small ghost", "aria-label": "Règles et chances de réussite", title: "Règles et chances", onclick: fuHelp }, icon("help")));
  const nodes = [head];
  const rec = fuRecipe();

  if (job && (job.running || job.reason)) { // le lot : en cours, ou terminé et pas encore acquitté
    const last = job.last;
    nodes.push(el("section", { class: "fu-panel fu-run" },
      el("h2", { class: "serif", text: job.running ? "Fusion en cours" : "Fusion terminée" }),
      el("div", { class: "fu-trk" }, el("i", { style: `width:${job.goal ? (job.fusions / job.goal) * 100 : 0}%` })),
      el("p", { class: "muted num", text: `${fmt(job.fusions)} sur ${fmt(job.goal)} fusions` }),
      fuTally(job),
      last ? el("p", { class: "muted" }, "Dernière carte : ", el("b", { style: `color:${color(last.rarity)}`, text: last.name })) : null,
      job.running
        ? [el("p", { class: "muted small", text: "Tu peux changer d'onglet, mais garde l'appli ouverte : le lot s'arrête si elle ne répond plus." }),
           el("button", { class: "btn", "data-act": "fu-stop", text: "Arrêter", onclick: () => api().fusion_stop() })]
        : [el("p", { text: job.error ? `Arrêté : ${job.error}` : FU_REASONS[job.reason] || "" }),
           el("button", { class: "btn primary", "data-act": "fu-ok", text: "OK", onclick: () => { FU.job = null; loadFusion(FU.rank, 0); } })]));
  } else if (!rec) {
    nodes.push(el("p", { class: "note", text: "Rien à fusionner : ouvre des paquets pour avoir des cartes." }));
  } else {
    const avail = rec.avail, fusions = () => Math.floor((Number(FU.count) || 0) / FU.size), consumed = () => fusions() * FU.size;
    const sum = el("p", { class: "fu-sum" });
    const paintSum = () => {
      const f = fusions();
      sum.replaceChildren(`${plural(f, "fusion")} · ${plural(consumed(), "carte")} utilisées · environ ${Math.max(1, Math.ceil(f * 0.7 / 60))} min`, el("br"),
        el("span", { class: "muted", text: (FU.dups ? "Il te reste toujours un exemplaire de chaque carte." : "Tes cartes en un seul exemplaire peuvent partir.") + " Une fusion ratée perd ses cartes." }));
    };
    const input = el("input", { type: "number", min: String(FU.size), max: String(avail), step: String(FU.size), value: String(FU.count), "aria-label": "Cartes à fusionner" });
    input.addEventListener("input", () => { FU.count = Number(input.value) || 0; paintSum(); });
    const setCount = (n) => { FU.count = Math.max(FU.size, Math.min(n, avail || n)); input.value = String(FU.count); paintSum(); };
    const quick = el("div", { class: "fu-quick" }, [30, 150, 600].filter((n) => n <= avail).map((n) => el("button", { class: "btn small", text: fmt(n), onclick: () => setCount(n) })),
      el("button", { class: "btn small", text: "Tout", onclick: () => setCount(avail) }));
    const sizes = el("div", { class: "fu-sz", role: "group", "aria-label": "Cartes par fusion" }, [3, 2].map((n) => el("button", {
      class: FU.size === n ? "on" : "", "data-size": String(n), text: `${n} par fusion`, onclick: () => { FU.size = n; FU.count = Math.max(n, FU.count); paintFusion(); } })));
    const dups = el("label", { class: "fu-check" }, el("input", { type: "checkbox", ...(FU.dups ? { checked: "" } : {}), onchange: (e) => { FU.dups = e.target.checked; paintSum(); } }), " Doublons seulement");
    const go = tag(actBtn("Lancer la fusion automatique", "primary", (b) => act(b, () => api().fusion_start(FU.rank, consumed(), FU.size, FU.dups), (r) => { FU.job = r.job; watchFusion(); paintFusion(); }),
      () => `Confirmer : fusionner ${fmt(consumed())} cartes ${label(FU.rank).toLowerCase()}s`,
      () => (fusions() < 1 ? `Au moins ${FU.size} cartes.` : consumed() > Math.max(avail, FU.size) ? `Tu n'as que ${plural(avail, "carte")} de ce rang.` : null)), "fu-go");
    paintSum();
    nodes.push(el("section", { class: "fu-panel" },
      el("h2", { class: "serif" }, el("span", { style: `color:${color(FU.rank)}`, text: label(FU.rank) }), el("em", { text: " → " }), el("span", { style: `color:${color(rec.to)}`, text: label(rec.to) })),
      el("label", { class: "fu-n" }, "Cartes à fusionner", input), quick, el("div", { class: "fu-opts" }, sizes, dups), sum, go));

    // à la main : on choisit les cartes une à une
    const hand = el("details", { class: "fu-hand" }, el("summary", { text: "Choisir les cartes à la main" }));
    if (st.cards.length) {
      const grid = el("div", { class: "fu-pick" });
      const manual = tag(actBtn(`Fusionner 0 sur ${FU.size} cartes`, "", (b) => act(b, () => api().fusion_do(FU.sel, FU.page), (r) => {
        toast(r.success ? `Réussie : ${r.card ? r.card.name : label(r.to)}` : "Ratée : les cartes sont perdues.", r.success ? "good" : "error");
        if (r.card) openModal(r.card);
        FU.st = { ...r.state, ok: true }; FU.page = r.state.page; FU.sel = []; refresh(); paintFusion();
      }), () => `Confirmer : ces ${FU.size} cartes peuvent être perdues`, () => (FU.sel.length !== FU.size ? `Choisis ${FU.size} cartes.` : null)), "fu-manual");
      const paintHand = () => { manual.textContent = `Fusionner ${FU.sel.length} sur ${FU.size} cartes`; grid.querySelectorAll(".fu-slot").forEach((n) => n.classList.toggle("sel", FU.sel.includes(+n.dataset.id))); };
      st.cards.forEach((c) => {
        const slot = el("div", { class: "fu-slot", "data-id": String(c.id) }, cardNode(c, () => {
          FU.sel = FU.sel.includes(c.id) ? FU.sel.filter((i) => i !== c.id) : FU.sel.length < FU.size ? [...FU.sel, c.id] : FU.sel; paintHand();
        }));
        grid.append(slot);
      });
      hand.append(grid);
      if (st.pages > 1) hand.append(el("div", { class: "fu-pager" },
        el("button", { class: "btn small", text: "Précédent", ...(FU.page < 1 ? { disabled: "" } : {}), onclick: () => loadFusion(FU.rank, FU.page - 1) }),
        el("span", { class: "muted num", text: `${FU.page + 1} / ${st.pages}` }),
        el("button", { class: "btn small", text: "Suivant", ...(FU.page >= st.pages - 1 ? { disabled: "" } : {}), onclick: () => loadFusion(FU.rank, FU.page + 1) })));
      hand.append(manual);
    } else hand.append(el("p", { class: "muted", text: "Aucune carte de ce rang à fusionner." }));
    nodes.push(hand);
  }
  body.replaceChildren(...nodes);
}
