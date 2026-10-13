"use strict";
/* Season Pass : cinquante niveaux, une récompense par niveau (forme lue dans saison.js du site). La récompense choisie s'affiche en grand,
   les niveaux défilent dessous. Récupérer = un clic, un niveau. Une récompense réservée aux abonnés WIKI-PRO ne se récupère pas sans l'être
   (le serveur le refuse aussi). Le signal d'activité du site, qui rapporte de l'XP au temps passé, n'est volontairement PAS envoyé.
   Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const SP = { d: null, sel: null, loading: false, rules: false };
const SP_KIND = { paquets: "Paquets", dore: "Paquet doré", wikiki: "Wikiki", dos: "Dos de carte", carte: "Carte exclusive", skin: "Skin de carte", cadre: "Cadre de photo",
  vitrine: "Vitrine", fond: "Fond de vitrine", legende: "Paquet légendaire", mythique: "Paquet mythique" };
const spTone = (r) => (r === "C" ? "var(--ivory-2)" : color(r));
const spWhen = (s) => { const j = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600); return j ? `${j} j ${h} h` : h ? `${h} h` : "moins d'une heure"; };

function spState(d, x) { // taken | reserved | locked | soon | ready
  if (d.me.taken.includes(x.level)) return "taken";
  if (!d.season.free.includes(x.level) && !d.me.subscriber) return "reserved";
  if (Math.min(x.level, d.season.levels) > d.me.level) return "locked";
  if (x.kind === "carte" && !x.card) return "soon";
  return "ready";
}
function spProgress(d) {
  const { xp, xp_level: a, xp_next: b } = d.me;
  return !b ? 1 : Math.max(0, Math.min(1, (xp - a) / Math.max(1, b - a)));
}

/* l'anneau de niveau autour de la photo, dans l'en-tête */
function spHeader() {
  const d = SP.d, lvl = (d && d.me.level) || (S.data && S.data.me && S.data.me.niveau) || 0;
  const chip = $("me-lvl"), ring = $("me-ring");
  if (chip) { chip.textContent = lvl ? `Niv. ${lvl}` : ""; chip.classList.toggle("hidden", !lvl); }
  if (ring) ring.style.setProperty("--p", String(Math.round((d ? spProgress(d) : 0) * 100)));
  const dot = $("tab-season-dot"); if (dot) dot.classList.toggle("hidden", !(d && d.levels.some((x) => spState(d, x) === "ready")));
}
async function loadSeasonBg() { // une seule lecture à l'ouverture de l'appli (comme le site), pour l'anneau et la pastille
  if (SP.d || SP.loading) return;
  SP.loading = true;
  const r = await api().season_get();
  SP.loading = false;
  if (r.ok) { SP.d = r; spHeader(); }
}

/* l'objet d'une récompense, dessiné en CSS : le même en grand et en petit */
function spArt(x, big) {
  const wrap = el("div", { class: "ra" + (big ? " big" : ""), style: `--rc:${spTone(x.rarity)}` });
  const k = x.kind;
  if (k === "carte" && x.card) wrap.append(el("div", { class: "ra-card" }, cardNode(x.card, null)));
  else if (k === "carte") wrap.append(el("div", { class: "ra-soon" }, el("b", { class: "serif", text: "?" }), big ? el("small", { text: "Carte exclusive, bientôt" }) : null));
  else if (["paquets", "dore", "legende", "mythique"].includes(k)) {
    const tone = k === "dore" ? "gold" : k === "legende" ? "ember" : k === "mythique" ? "night" : "plum";
    wrap.append(el("div", { class: "ra-pile" }, x.n > 1 ? el("div", { class: "ra-pk back " + tone }) : null,
      el("div", { class: "ra-pk " + tone }, el("b", { class: "serif", text: "W·P" }), big && k !== "paquets" ? el("small", { text: k === "legende" ? "Légendaire garantie" : k === "mythique" ? "Mythique garantie" : "Paquet doré" }) : null)));
    if (x.n > 1) wrap.append(el("i", { class: "ra-x", text: `×${x.n}` }));
  } else if (k === "wikiki") { wrap.append(el("div", { class: "ra-coin" }, el("span", { class: "serif", text: "W" }))); if (!big && x.n) wrap.append(el("i", { class: "ra-x", text: String(x.n) })); }
  else if (k === "dos") wrap.append(el("div", { class: "ra-back" }, el("i"), el("span", { class: "serif", text: "W" })));
  else if (k === "cadre") wrap.append(el("div", { class: "ra-ring" }, el("span", { class: "serif", text: "A" })));
  else wrap.append(el("div", { class: "ra-misc" }, icon(k === "skin" ? "spark" : "cards")));
  return wrap;
}

function spRules() {
  const d = SP.d, r = d.rules;
  const row = (t, v, c) => el("li", {}, el("span", { text: t, style: c ? `color:${c}` : "" }), el("b", { class: "num", text: v }));
  openDialog("Comment gagner de l'XP", el("div", { class: "sp-rules" }, el("ul", {},
    row("Ouvrir un paquet", `+${r.pack}`), row("Ouvrir un paquet doré", `+${r.gold_pack}`),
    row(`Tes ${r.market_first} premiers achats aux enchères du jour`, `+${r.bid}`), row(`Tes ${r.market_first} premières ventes du jour`, `+${r.sale}`),
    row("Achats et ventes suivants", `+${r.bid_after}`), row("Réussir un défi WBC", `+${r.wbc}`),
    r.active_xp ? row("Rester actif sur wiki-pick.com", `+${r.active_xp} / ${r.active_every} min`) : null,
    el("li", { class: "sub", text: "Chaque carte trouvée dans un paquet" }),
    Object.entries(r.cards).map(([k, v]) => row(label(k), `+${v}`, color(k))), r.shiny ? row("Chromatique", `+${r.shiny}`) : null),
    el("p", { class: "muted small", text: "Le temps passé sur le site rapporte aussi de l'XP, mais seulement sur wiki-pick.com : Alt-WikiPick n'envoie pas ce signal d'activité à ta place." })));
}

async function loadSeason() {
  const box = $("sp-body");
  if (!SP.d) box.replaceChildren(el("p", { class: "muted", text: "Chargement…" }));
  const r = await api().season_get();
  if (r.expired) return sessionLost(r);
  if (!r.ok) return box.replaceChildren(el("p", { class: "note", text: r.error || "Le Season Pass ne répond pas." }), el("button", { class: "btn small", text: "Réessayer", onclick: loadSeason }));
  SP.d = r; spHeader();
  if (SP.sel == null || !r.levels.some((x) => x.level === SP.sel)) {
    const first = r.levels.find((x) => spState(r, x) === "ready") || r.levels.find((x) => x.level > r.me.level) || r.levels[0];
    SP.sel = first ? first.level : 1;
  }
  paintSeason();
}

function paintSeason() {
  const d = SP.d, box = $("sp-body");
  if (!d) return;
  if (d.season.future) return box.replaceChildren(el("p", { class: "note", text: `${d.season.name || "Season Pass"} : la saison commence dans ${spWhen(d.season.in)}.` }));
  const x = d.levels.find((l) => l.level === SP.sel) || d.levels[0], st = spState(d, x), m = d.me;
  const ready = d.levels.filter((l) => spState(d, l) === "ready").length;
  const head = el("header", { class: "sp-head" },
    el("div", { class: "sp-lvl" }, el("span", { text: "Niveau" }), el("b", { class: "serif num", text: String(m.level) })),
    el("div", { class: "sp-prog" }, el("div", { class: "sp-trk" }, el("i", { style: `width:${Math.round(spProgress(d) * 100)}%` })),
      el("div", { class: "sp-meta num" }, el("span", { text: m.xp_next ? `${fmt(m.xp)} / ${fmt(m.xp_next)} XP` : `${fmt(m.xp)} XP · niveau maximum` }),
        el("span", { text: d.season.open ? `se termine dans ${spWhen(d.season.left)}` : "terminée" }))),
    el("button", { class: "icon-btn", "aria-label": "Comment gagner de l'XP", title: "Comment gagner de l'XP", onclick: spRules }, icon("help")));
  const takeBtn = tag(actBtn(x.kind === "legende" || x.kind === "mythique" ? "Récupérer et ouvrir" : "Récupérer", "primary", (b) => act(b, () => api().season_take(x.level), spTaken)), "sp-take"); // une récompense gratuite ou gagnée : un clic, comme sur le site
  const equip = (kind) => el("button", { class: "btn small", "data-act": "sp-equip", text: kind === "dos" ? "Utiliser ce dos" : "Mettre sur ma photo",
    onclick: (e) => act(e.currentTarget, () => api().season_equip(kind, `${d.season.key}-${x.key}`), () => toast(kind === "dos" ? "Ce dos est maintenant sur tes cartes." : "Ce cadre est maintenant autour de ta photo.", "good")) });
  const action = el("div", { class: "sp-act" },
    st === "ready" ? takeBtn
    : st === "taken" ? [el("span", { class: "sp-done" }, icon("check"), " Récupérée"), x.kind === "dos" ? equip("dos") : null, x.kind === "cadre" ? equip("cadre") : null]
    : st === "reserved" ? [el("span", { class: "sp-lock" }, icon("lock"), " Réservée aux abonnés WIKI-PRO"), el("button", { class: "btn small", text: "Voir sur le site", onclick: () => api().open_url("https://wiki-pick.com/season-pass") })]
    : st === "soon" ? el("span", { class: "sp-lock", text: "Niveau atteint · la carte arrive bientôt" })
    : el("span", { class: "sp-lock" }, icon("lock"), ` Encore ${fmt(Math.max(0, x.xp - m.xp))} XP`));
  const stage = el("section", { class: "sp-stage" + (st === "reserved" ? " reserved" : ""), style: `--rc:${spTone(x.rarity)}` },
    el("div", { class: "sp-rays", "aria-hidden": "true" }), el("div", { class: "sp-obj" }, spArt(x, true)),
    el("div", { class: "sp-txt" }, el("p", { class: "sp-kind", text: `${SP_KIND[x.kind] || ""} · ${x.bonus ? "Bonus" : `Niveau ${x.level}`}` }),
      el("h2", { class: "serif", text: x.title }), x.text ? el("p", { class: "sp-desc", text: x.text }) : null, action));
  const band = el("div", { class: "sp-bandw" },
    el("button", { class: "sp-arr", "aria-label": "Niveau précédent", ...(SP.sel <= 1 ? { disabled: "" } : {}), onclick: () => { SP.sel = Math.max(1, SP.sel - 1); paintSeason(); } }, icon("chev")),
    el("div", { class: "sp-band", id: "sp-band" }, d.levels.map((l) => {
      const s = spState(d, l);
      return el("button", { class: `sp-cell ${s}${l.level === SP.sel ? " on" : ""}`, "data-l": String(l.level), style: `--rc:${spTone(l.rarity)}`, title: `${l.bonus ? "Bonus" : "Niveau " + l.level} · ${l.title}`,
        onclick: () => { SP.sel = l.level; paintSeason(); } },
        el("span", { class: "n num", text: l.bonus ? "★" : String(l.level) }), el("span", { class: "mini" }, spArt(l, false)),
        el("span", { class: "st" }, s === "taken" ? icon("check") : s === "ready" ? el("i", { class: "dot" }) : s === "reserved" ? icon("lock") : s === "locked" ? icon("clock") : null));
    })),
    el("button", { class: "sp-arr next", "aria-label": "Niveau suivant", ...(SP.sel >= d.levels.length ? { disabled: "" } : {}), onclick: () => { SP.sel = Math.min(d.levels.length, SP.sel + 1); paintSeason(); } }, icon("chev")));
  box.replaceChildren(head, d.me.subscriber ? null : el("p", { class: "sp-note", text: `${d.season.free.length} récompenses gratuites · les autres avec WIKI-PRO` }), stage, band,
    ready ? el("p", { class: "sp-foot" }, el("button", { class: "link", text: `${plural(ready, "récompense")} à récupérer`, onclick: () => { SP.sel = d.levels.find((l) => spState(d, l) === "ready").level; paintSeason(); } })) : null);
  const cell = $("sp-band").querySelector(`[data-l="${SP.sel}"]`), band2 = $("sp-band");
  if (cell) band2.scrollTo({ left: cell.offsetLeft - band2.clientWidth / 2 + cell.clientWidth / 2 });
}

function spTaken(r) {
  if (r.state && r.state.levels.length) SP.d = r.state;
  if (r.me) { Object.assign(S.data.me, r.me); renderHeader(); }
  S.dirty = true; spHeader();
  if (r.cards.length) showHaul(r.mythic ? "Ton paquet mythique" : "Ton paquet légendaire", `${plural(r.cards.length, "carte")}, dont une ${r.mythic ? "mythique" : "légendaire"} garantie.`, r.cards);
  else if (r.merge) toast(`Fusion : ${r.merge.from} devient ${r.merge.to}.`, "good");
  else toast(`${r.title} : c'est à toi !`, "good");
  if (r.badge) toast("Un insigne de saison est maintenant à côté de ton pseudo.", "good");
  paintSeason();
}

/* une pile de cartes reçue d'un coup : toutes visibles, la plus rare en premier */
function showHaul(title, hint, cards) {
  const list = [...cards].sort((a, b) => rarityRank(a.rarity) - rarityRank(b.rarity) || Number(b.shiny) - Number(a.shiny));
  const fresh = list.filter((c) => c.new).length;
  openDialog(title, el("div", { class: "haul" }, el("p", { class: "muted", text: hint + (fresh ? ` · ${plural(fresh, "nouvelle")}` : "") }),
    el("div", { class: "bgrid" }, list.map((c) => cardNode(c)))), true);
}
