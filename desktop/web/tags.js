"use strict";
/* Étiquettes (créer, renommer, supprimer, poser sur une carte) et cartes masquées de TA collection (liste locale : rien n'est écrit
   sur wiki-pick.com). Formes de l'API lues dans cards.js du site. Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const HID = { set: new Set(), list: [] };
const TAG_COLORS = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#14b8a6", "#3b82f6", "#8b5cf6", "#ec4899", "#64748b", "#a16207"];

async function loadHidden() {
  const r = await api().hidden_get();
  if (r.ok) { HID.list = r.list; HID.set = new Set(r.list); }
}
async function setHiddenCard(c, on) {
  const r = await api().hidden_set([c.cid], on);
  if (r.expired) return sessionLost(r);
  if (!r.ok) return toast(r.error || "Impossible de masquer cette carte.");
  HID.list = r.list; HID.set = new Set(r.list);
  toast(on ? "Carte masquée : elle reste à toi, mais disparaît de ta collection." : "La carte est de nouveau dans ta collection.", "good");
  applyFilters(true); closeModal();
}
function hideButton(c) {
  const on = HID.set.has(c.cid);
  return el("button", { class: "btn small", text: on ? "Réafficher dans ma collection" : "Masquer de ma collection", onclick: () => setHiddenCard(c, !on) });
}

/* carte exclusive : la masquer de ton PROFIL (côté site) ; elle reste à toi, grisée dans ta collection */
function exclusiveMaskButton(c, own) {
  if (!EXCLUSIVE.includes(c.rarity) || !(own.ids || []).length) return null;
  const id = own.ids[0], was = (S.data.masked || []).includes(id);
  return el("button", { class: "btn small", text: was ? "Démasquer de mon profil" : "Masquer de mon profil", onclick: (e) => act(e.currentTarget, () => api().exclusive_hide(id, !was), () => {
    S.data.masked = was ? S.data.masked.filter((i) => i !== id) : [...(S.data.masked || []), id];
    toast(was ? "Carte de nouveau visible sur ton profil." : "Carte masquée : elle n'apparaît plus sur ton profil.", "good"); openModal(c); }) });
}

/* ---- sur la fiche d'une carte : les étiquettes de la carte, une pastille par étiquette ---- */
function setTagsData(tags) { // la liste a changé (créer, renommer, supprimer) : on la répercute sur les cartes
  const ids = new Set(tags.map((t) => t.id));
  S.data.tags = tags;
  S.data.cards.forEach((c) => { if ((c.tags || []).some((i) => !ids.has(i))) c.tags = c.tags.filter((i) => ids.has(i)); });
  buildFilters(); applyFilters(true);
}
function tagChips(c, own) {
  const mine = own.tags || [];
  const toggle = (t) => {
    const ids = mine.includes(t.id) ? mine.filter((i) => i !== t.id) : [...mine, t.id];
    act(null, () => api().card_tags_set(c.cid, ids), () => { own.tags = ids; applyFilters(true); openModal(c); });
  };
  return el("div", { class: "tg" },
    S.data.tags.map((t) => el("button", { class: "tgc" + (mine.includes(t.id) ? " on" : ""), style: `--t:${t.color}`, "data-tag": String(t.id), text: t.name, onclick: () => toggle(t) })),
    el("button", { class: "tgc add", text: S.data.tags.length ? "Gérer" : "Créer une étiquette", onclick: openTagManager }));
}

/* ---- le gestionnaire d'étiquettes ---- */
function openTagManager() {
  const draft = new Map(); // id -> {name, color} en cours de modification
  const body = el("div", { class: "tagmgr" });
  const swatches = (get, set) => el("div", { class: "sw", role: "group", "aria-label": "Couleur" }, TAG_COLORS.map((col) => el("button", {
    type: "button", class: get() === col ? "on" : "", style: `background:${col}`, "aria-label": col, onclick: () => { set(col); paint(); } })));
  let newName = "", newColor = TAG_COLORS[5];
  const paint = () => {
    const nameIn = el("input", { class: "field", maxlength: "20", placeholder: "Nouvelle étiquette", "aria-label": "Nom de la nouvelle étiquette", value: newName });
    nameIn.addEventListener("input", () => { newName = nameIn.value; create.disabled = !newName.trim(); });
    const create = el("button", { class: "btn primary", text: "Créer l'étiquette", ...(newName.trim() ? {} : { disabled: "" }), onclick: () =>
      act(create, () => api().tag_save(null, newName, newColor), (r) => { setTagsData(r.tags); newName = ""; newColor = TAG_COLORS[r.tags.length % TAG_COLORS.length]; toast("Étiquette créée.", "good"); paint(); }) });
    const rows = S.data.tags.map((t) => {
      const d = draft.get(t.id) || { name: t.name, color: t.color };
      const nm = el("input", { class: "field", maxlength: "20", value: d.name, "aria-label": "Nom" });
      const save = el("button", { class: "btn small", text: "Enregistrer", disabled: "", onclick: () =>
        act(save, () => api().tag_save(t.id, nm.value, d.color), (r) => { draft.delete(t.id); setTagsData(r.tags); toast("Étiquette modifiée.", "good"); paint(); }) });
      const dirty = () => { draft.set(t.id, { name: nm.value, color: d.color }); if (nm.value.trim() && (nm.value.trim() !== t.name || d.color !== t.color)) save.removeAttribute("disabled"); else save.setAttribute("disabled", ""); };
      nm.addEventListener("input", dirty);
      const del = tag(actBtn("Supprimer", "small danger", () => act(del, () => api().tag_delete(t.id), (r) => { setTagsData(r.tags); toast(`« ${t.name} » supprimée.`, "good"); paint(); }), "Confirmer"), "tag-del");
      return el("li", { "data-tag": String(t.id) }, nm, swatches(() => d.color, (col) => { d.color = col; draft.set(t.id, { name: nm.value, color: col }); }), el("div", { class: "row" }, save, del));
    });
    body.replaceChildren(el("div", { class: "tagmgr-new" }, nameIn, swatches(() => newColor, (col) => { newColor = col; }), create),
      rows.length ? el("ul", { class: "tagmgr-list" }, rows) : el("p", { class: "muted", text: "Tu n'as pas encore d'étiquette. Crée la première ci-dessus, puis pose-la sur tes cartes depuis leur fiche." }));
  };
  paint();
  openDialog("Étiquettes", body);
}
