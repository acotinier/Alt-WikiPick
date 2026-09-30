"use strict";
/* Onglet Paquets : le paquet foil, la déchirure, la révélation carte par carte.
   Écriture : un clic = un paquet (api.open_pack), jamais en boucle.
   Chargé AVANT app.js : ne rien exécuter ici au chargement, S / $ / el… n'existent pas encore. */

const PK = { cards: [], flipped: 0, opening: false };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- écran d'attente ---------- */
function renderPacks() {
  const n = S.data.me.packs ?? 0;
  const w = $("pack-wrap"); w.dataset.n = String(Math.min(n, 3)); w.classList.toggle("empty", n < 1);
  $("pk-count").textContent = n < 1 ? "Aucun paquet en réserve" : `${n} paquet${n > 1 ? "s" : ""} en réserve`;
  $("btn-open").disabled = PK.opening || n < 1;
  const me = S.data.me, gold = $("btn-gold"); // paquet doré : offert ou PRO du jour, quand le profil l'indique (comme le site)
  gold.classList.toggle("hidden", !(me.proPack || me.paquetOr)); gold.disabled = PK.opening;
  gold.textContent = `${me.proPack ? "Paquet PRO du jour" : "Ton paquet doré offert"} · ${plural(me.proCards || 20, "carte")}`;
  $("pack").tabIndex = n < 1 ? -1 : 0;
}

function tilt(e, target, max) { // le foil suit le pointeur
  const r = target.getBoundingClientRect();
  const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height));
  target.style.setProperty("--ry", `${(x - 0.5) * max}deg`); target.style.setProperty("--rx", `${(0.5 - y) * max}deg`);
  target.style.setProperty("--mx", `${x * 100}%`); target.style.setProperty("--my", `${y * 100}%`);
}
const untilt = (target) => ["--rx", "--ry"].forEach((k) => target.style.removeProperty(k));

/* ---------- vérification « es-tu un robot ? » ----------
   De temps en temps, le site veut une preuve qu'un humain ouvre le paquet (me.defi). On pose SA question, telle quelle :
   c'est le joueur qui clique la bonne forme, l'appli ne fait que transmettre son choix (jamais de réponse devinée). */
const CH = { res: null }; // la promesse en attente de la réponse du joueur
function pictogram(p) { // redessine un pictogramme déjà décodé par Python (formes et attributs sur liste blanche)
  const s = document.createElementNS(SVGNS, "svg"); s.setAttribute("viewBox", p.viewBox); s.setAttribute("aria-hidden", "true");
  for (const sh of p.shapes) {
    const n = document.createElementNS(SVGNS, sh.tag);
    for (const [k, v] of Object.entries(sh.attrs)) n.setAttribute(k, v);
    s.append(n);
  }
  return s;
}
async function askChallenge() { // -> {defi, rep}, ou null si le joueur renonce
  const r = await api().pack_challenge();
  if (r.expired) { closeDialog(); sessionLost(r); return null; }
  if (!r.ok) { closeDialog(); toast(r.error || "Vérification indisponible pour le moment."); return null; }
  const q = r.challenge;
  return new Promise((res) => {
    CH.res = res;
    const done = (v) => { const f = CH.res; CH.res = null; closeDialog(); if (f) f(v); };
    const another = () => { const f = CH.res; CH.res = null; askChallenge().then(f); };
    openDialog("Avant d'ouvrir ton paquet", el("div", { class: "defi" },
      el("p", { class: "defi-q", text: q.consigne || "Choisis la bonne forme" }),
      el("div", { class: "defi-grid" }, q.choix.map((p, i) => el("button", {
        class: "defi-c", type: "button", "aria-label": `Forme ${i + 1}`, "data-rep": String(i),
        onclick: () => done({ defi: q.id, rep: i }),
      }, p ? pictogram(p) : el("span", { class: "muted", text: "?" })))),
      el("p", { class: "muted small", text: "Le site vérifie de temps en temps qu'un humain ouvre les paquets. Clique la forme demandée : c'est ton choix qui est envoyé, rien d'autre." }),
      el("div", { class: "row" },
        el("button", { class: "btn small ghost", type: "button", text: "Une autre question", onclick: another }),
        el("button", { class: "btn small", type: "button", text: "Annuler", onclick: () => done(null) }))));
    q.choix.forEach((p, i) => { if (!p) $("dialog-body").querySelector(`[data-rep="${i}"]`).disabled = true; }); // forme illisible : on ne la propose pas
  });
}

async function openPack(kind, proof) { // "gold" : le paquet doré ; sinon un paquet normal. proof = la réponse du joueur à la vérification
  const me = S.data && S.data.me, gold = kind === "gold";
  if (PK.opening || !me || (gold ? !(me.proPack || me.paquetOr) : (me.packs ?? 0) < 1)) return;
  if (!gold && !proof && me.defi) { // le site veut une vérification : sa question d'abord, le paquet ensuite
    PK.opening = true; renderPacks();
    const p = await askChallenge();
    PK.opening = false; renderPacks();
    return p ? openPack(kind, p) : undefined;
  }
  PK.opening = true; renderPacks();
  const pack = $("pack"); pack.classList.add("tearing");
  // la déchirure dure au moins 0,9 s ; la réponse du site arrive pendant ce temps
  const [r] = await Promise.all([
    (gold ? api().open_gold_pack() : proof ? api().open_pack(proof.defi, proof.rep) : api().open_pack())
      .catch((e) => ({ ok: false, error: "Erreur inattendue : " + e })),
    sleep(reduced() ? 150 : 900),
  ]);
  if (!r.ok) {
    PK.opening = false; pack.classList.remove("tearing");
    if (r.expired) return sessionLost(r);
    if (r.challenge && !proof) { me.defi = true; renderPacks(); return openPack(kind); } // demandée entre-temps : on pose la question
    toast(r.error || "Ouverture impossible"); renderPacks(); return;
  }
  S.data.me = r.me; S.dirty = true; renderHeader();
  showCards(r.cards);
  PK.opening = false; renderPacks();
  api().pack_seen(); // « les cartes sont à l'écran », comme le fait le site
}

/* ---------- révélation ---------- */
function showCards(cards) {
  // de la plus commune à la plus rare : le meilleur pour la fin
  const list = [...cards].sort((a, b) => rarityRank(b.rarity) - rarityRank(a.rarity) || Number(a.shiny) - Number(b.shiny));
  PK.cards = list; PK.flipped = 0;
  const box = $("pk-cards"); box.replaceChildren(...list.map(packCard));
  $("pk-end").classList.add("hidden"); $("btn-flip-all").classList.remove("hidden");
  $("packs-idle").classList.add("hidden"); $("reveal").classList.remove("hidden"); $("tab-packs").classList.add("revealing");
  updateProgress();
  if (box.firstChild) box.firstChild.focus({ preventScroll: true });
}

function packCard(c, i) {
  const face = cardNode(c, null);
  face.append(el("i", { class: "glare" }));
  if (c.new) face.append(el("span", { class: "new", text: "Nouvelle" }));
  const n = el("div", {
    class: "pcard" + (isTop(c) ? " top" : ""), style: `--c:${color(c.rarity)};--i:${i}`, "data-i": String(i),
    tabindex: "0", role: "button", "aria-label": "Retourner la carte",
    onclick: () => flipCard(n),
    onkeydown: (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      if (n.classList.contains("open") && e.key === " ") flipNext(); else flipCard(n);
    },
  }, el("div", { class: "inner" },
    el("div", { class: "face back cardback" }, el("span", { class: "mark", text: "W·P" })),
    el("div", { class: "face front" }, face)));
  return n;
}

function flipCard(n) {
  const c = PK.cards[+n.dataset.i];
  if (n.classList.contains("open")) return openModal(c); // déjà retournée : sa fiche
  n.classList.add("open"); PK.flipped++;
  n.setAttribute("aria-label", c.name);
  if (isTop(c) && !reduced()) setTimeout(() => { burst(n, c.shiny ? 26 : 18); pulse(c); }, 320); // au milieu du retournement
  updateProgress();
}

function flipNext() {
  const n = [...$("pk-cards").children].find((x) => !x.classList.contains("open"));
  if (n) flipCard(n);
}

async function flipAll() {
  $("btn-flip-all").disabled = true;
  for (const n of [...$("pk-cards").children]) {
    if (!n.classList.contains("open")) { flipCard(n); await sleep(reduced() ? 0 : 260); }
  }
  $("btn-flip-all").disabled = false;
}

function burst(n, count) { // étincelles de la couleur de la rareté
  for (let k = 0; k < count; k++) {
    const a = Math.random() * Math.PI * 2, d = 70 + Math.random() * 90;
    const s = el("i", { class: "spark", style: `--dx:${Math.cos(a) * d}px;--dy:${Math.sin(a) * d}px` });
    s.addEventListener("animationend", () => s.remove()); n.append(s);
  }
}
function pulse(c) { // la scène s'éclaire à la couleur de la carte
  const r = $("reveal"); r.style.setProperty("--glow", color(c.rarity));
  r.classList.remove("pulse"); void r.offsetWidth; r.classList.add("pulse");
}

function updateProgress() {
  const t = PK.cards.length, f = PK.flipped;
  $("pk-progress").textContent = `${f} sur ${t} retournée${f > 1 ? "s" : ""}`;
  $("pk-fill").style.width = `${t ? (f / t) * 100 : 0}%`;
  if (f < t) return;
  const best = PK.cards[t - 1], news = PK.cards.filter((c) => c.new).length;
  $("btn-flip-all").classList.add("hidden");
  $("pk-summary").textContent = `Paquet ouvert : ${t} cartes, dont ${news} nouvelle${news > 1 ? "s" : ""}. La plus rare : ${best.name} (${label(best.rarity)}).`;
  $("btn-again").disabled = (S.data.me.packs ?? 0) < 1;
  $("pk-end").classList.remove("hidden");
}

/* again = true : un nouveau paquet, sur un nouveau clic. La collection se relit à la fin (S.dirty). */
function donePack(again) {
  $("reveal").classList.add("hidden"); $("packs-idle").classList.remove("hidden"); $("tab-packs").classList.remove("revealing");
  $("pack").classList.remove("tearing");
  loadJournal();
  const w = $("pack-wrap"); w.classList.remove("in"); void w.offsetWidth; w.classList.add("in");
  renderPacks();
  if (again) openPack(); else refresh();
}

function resetPacks() { // déconnexion
  PK.cards = []; PK.flipped = 0; PK.opening = false;
  $("reveal").classList.add("hidden"); $("packs-idle").classList.remove("hidden"); $("pack").classList.remove("tearing");
  $("tab-packs").classList.remove("revealing"); PJ.packs = []; renderJournal();
}

function bindPacks() {
  const p = $("pack"), w = $("pack-wrap");
  p.onclick = () => openPack(); $("btn-open").onclick = () => openPack(); $("btn-gold").onclick = () => openPack("gold");
  p.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openPack(); } };
  w.addEventListener("pointermove", (e) => tilt(e, p, 26));
  w.addEventListener("pointerleave", () => untilt(p));
  const box = $("pk-cards");
  box.addEventListener("pointermove", (e) => { const c = e.target.closest(".pcard.open"); if (c) tilt(e, c, 14); });
  box.addEventListener("pointerout", (e) => { const c = e.target.closest(".pcard"); if (c && !c.contains(e.relatedTarget)) untilt(c); });
  $("btn-flip-all").onclick = flipAll;
  $("btn-done").onclick = () => donePack(false); $("btn-again").onclick = () => donePack(true);
  document.addEventListener("keydown", (e) => { // Espace : carte suivante, hors champs et boutons
    if (e.key !== " " || S.tab !== "packs" || $("reveal").classList.contains("hidden")) return;
    if (e.target.closest && e.target.closest("button, [role=button], input, select, textarea")) return;
    e.preventDefault(); flipNext();
  });
}
