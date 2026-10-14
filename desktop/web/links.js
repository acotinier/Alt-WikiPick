"use strict";
/* Où mène une notification (même liste que le site, followLink de social.js) + la sélection multiple de la collection.
   Seuls les liens connus sont suivis ; le reste n'est pas cliquable. Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const NL_PAGES = { guild: "guild", combat: "arena", packs: "packs", coll: "collection", nouveautes: "news", market: "market", rewards: "rewards", saison: "season", trades: "trades" };
const NL_SITE = new Set(["wbc", "support", "post"]); // pas d'écran chez nous : on ouvre le site
const nlSplit = (link) => { const s = String(link || ""), i = s.indexOf(":"); return i < 0 ? [s, ""] : [s.slice(0, i), s.slice(i + 1)]; };

function linkKind(link) { // "page" | "auction" | "site" | null
  const [k, arg] = nlSplit(link);
  if (k === "auction") return /^\d{1,12}$/.test(arg) ? "auction" : null;
  if (k === "profile" || k === "msg") return arg ? "page" : null;
  if (NL_PAGES[k]) return "page";
  return NL_SITE.has(k) ? "site" : null;
}
function followLink(link) {
  const [k, arg] = nlSplit(link), kind = linkKind(link);
  if (kind === "auction") return openAuctionById(+arg);
  if (kind === "site") return api().open_url("https://wiki-pick.com/");
  if (kind !== "page") return;
  if (k === "profile") return openProfile(arg);
  if (k === "msg") return openMessages(arg);
  if (k === "trades") return setTab("trades");
  setTab(NL_PAGES[k]);
}

/* une enchère précise (notification « on a surenchéri sur… ») : la carte, le prix, le temps restant, de quoi miser */
async function openAuctionById(id) {
  const r = await api().auction_get(id);
  if (r.expired) return sessionLost(r);
  const a = r.ok && r.auction && r.auction.id ? r.auction : null;
  if (!a) return openDialog("Enchère", el("p", { class: "muted", text: (r && r.error) || "Cette enchère n'est plus disponible." }));
  const c = a.lot ? { ...(a.lot.cards[0] || {}), name: a.lot.name, copies: 1, desc: "" } : a.card;
  const live = a.status === "live";
  const body = el("div", { class: "aucd" }, c ? el("div", { class: "aucd-card" }, cardNode(c, null)) : null,
    el("div", { class: "aucd-info" },
      a.lot ? el("p", { class: "muted", text: `Lot de ${plural(a.lot.n || a.lot.cards.length, "carte")}` }) : null,
      el("p", { class: "price serif" }, icon("coin"), fmt(a.price)),
      el("p", { class: "muted", text: (a.bids ? `${plural(a.bids, "mise")} · en tête : ${a.leader || a.seller}` : `par ${a.seller}`) + (a.leading ? " (toi)" : "") }),
      el("p", { class: "aucd-st", ...(live ? { "data-ends": String(a.ends_at) } : {}), text: live ? "" : a.status === "cancelled" ? "Annulée" : a.leader ? `Adjugé à ${a.leader}` : "Terminée sans preneur" }),
      live ? bidControls(a) : null,
      el("button", { class: "btn small", text: "Voir le marché", onclick: () => { closeDialog(); setTab("market"); } })));
  openDialog("Enchère", body);
  if (live) { const st = body.querySelector(".aucd-st"), tick = () => { const s = Math.max(0, Math.ceil(a.ends_at - nowSrv())); st.textContent = s > 0 ? `Se termine dans ${clock(s)}` : "Clôture…"; }; tick(); const t = setInterval(() => { if (!st.isConnected) return clearInterval(t); tick(); }, 1000); }
}

/* ---------------- sélection multiple de la collection : étiqueter, verrouiller, masquer en masse ---------------- */
const chunks500 = (arr, n = 500) => Array.from({ length: Math.ceil(arr.length / n) }, (_, i) => arr.slice(i * n, i * n + n));
const selCards = () => (S.sel ? S.data.cards.filter((c) => S.sel.has(c.cid)) : []);

function selStart() { S.sel = new Set(); $("btn-select").classList.add("on"); $("grid").classList.add("selecting"); applyFilters(true); } // la grille se redessine : un clic choisit la carte au lieu de l'ouvrir
function selEnd() { S.sel = null; $("btn-select").classList.remove("on"); $("grid").classList.remove("selecting"); applyFilters(true); }
function pickCard(c, node) {
  if (S.sel.has(c.cid)) { S.sel.delete(c.cid); node.classList.remove("picked"); } else { S.sel.add(c.cid); node.classList.add("picked"); }
  selPaint();
}
function selSet(list) { S.sel = new Set(list.map((c) => c.cid)); document.querySelectorAll("#grid .card").forEach((n) => n.classList.toggle("picked", S.sel.has(n.dataset.cid))); selPaint(); }

function selPaint() {
  const bar = $("selbar");
  bar.classList.toggle("hidden", !S.sel);
  if (!S.sel) return;
  const cs = selCards(), free = cs.flatMap((c) => c.free_ids || []), locked = cs.flatMap((c) => c.locked_ids || []), none = !S.sel.size, hid = $("f-hidden").checked;
  $("sel-n").textContent = `${fmt(S.sel.size)} ${S.sel.size > 1 ? "cartes sélectionnées" : "carte sélectionnée"}`;
  $("sel-sub").textContent = none ? "Clique des cartes pour les choisir" : `${plural(free.length, "exemplaire libre", "exemplaires libres")} · ${plural(locked.length, "verrouillé", "verrouillés")}`;
  ["sel-tag", "sel-lock", "sel-unlock", "sel-hide", "sel-none"].forEach((id) => { $(id).disabled = none; });
  $("sel-hide").textContent = hid ? "Réafficher" : "Masquer";
}

function selTagPanel() {
  const cs = selCards(), total = cs.length, body = el("div", { class: "seltags" });
  const paint = () => {
    const cur = selCards();
    body.replaceChildren(el("p", { class: "muted", text: "Clique une étiquette : si toutes les cartes l'ont déjà, elle est retirée de toutes ; sinon elle est posée sur toutes." }),
      el("div", { class: "tg" }, S.data.tags.length ? S.data.tags.map((t) => {
        const n = cur.filter((c) => (c.tags || []).includes(t.id)).length, all = n === cur.length && n > 0;
        return el("button", { class: "tgc" + (all ? " on" : ""), style: `--t:${t.color}`, "data-tag": String(t.id), onclick: (e) => selTag(t, !all, e.currentTarget, paint) },
          (all ? "✓ " : "") + t.name, el("small", { class: "num", text: ` ${n}/${cur.length}` }));
      }) : [el("p", { class: "muted", text: "Tu n'as pas encore d'étiquette." })]),
      el("button", { class: "btn small", text: "Gérer mes étiquettes", onclick: () => { closeDialog(); openTagManager(); } }));
  };
  paint(); openDialog(`Étiqueter ${plural(total, "carte")}`, body);
}
async function selTag(t, pose, btn, repaint) {
  const done = [];
  const r = await act(btn, async () => { for (const part of chunks500([...S.sel])) { const x = await api().cards_tag(part, t.id, pose); if (!x.ok) return x; done.push(...x.cids); } return { ok: true }; },
    () => toast(`« ${t.name} » ${pose ? "posée sur" : "retirée de"} ${plural(done.length, "carte")}.`, "good"));
  const set = new Set(done);
  S.data.cards.forEach((c) => { if (!set.has(c.cid)) return; const has = (c.tags || []).includes(t.id); if (pose && !has) c.tags = [...(c.tags || []), t.id]; else if (!pose && has) c.tags = c.tags.filter((i) => i !== t.id); });
  if (r !== null || done.length) repaint();
}
async function selLock(on) {
  const cs = selCards(), ids = cs.flatMap((c) => (on ? c.free_ids : c.locked_ids) || []), done = [];
  if (!ids.length) return toast(on ? "Ces cartes sont déjà verrouillées." : "Aucune de ces cartes n'est verrouillée.");
  await act(null, async () => { for (const part of chunks500(ids)) { const x = await api().cards_lock(part, on); if (!x.ok) return x; done.push(...x.ids); } return { ok: true }; },
    () => toast(done.length ? `${plural(done.length, on ? "exemplaire verrouillé" : "exemplaire déverrouillé", on ? "exemplaires verrouillés" : "exemplaires déverrouillés")}.` : "Rien à changer : les cartes exclusives n'ont pas de cadenas."));
  const s = new Set(done);
  S.data.cards.forEach((c) => {
    if (!(c.ids || []).some((i) => s.has(i))) return;
    c.locked_ids = on ? [...new Set([...(c.locked_ids || []), ...c.ids.filter((i) => s.has(i))])] : (c.locked_ids || []).filter((i) => !s.has(i));
    c.locked = on ? c.locked_ids.length >= c.ids.length : false;
    c.free_ids = c.locked || EXCLUSIVE.includes(c.rarity) ? [] : c.ids.filter((i) => !c.locked_ids.includes(i));
  });
  if (done.length) { S.dirty = true; applyFilters(true); selPaint(); }
}
async function selHide(on) {
  const cids = [...S.sel];
  await act(null, async () => { let x; for (const part of chunks500(cids)) { x = await api().hidden_set(part, on); if (!x.ok) return x; } HID.list = x.list; HID.set = new Set(x.list); return x; },
    () => toast(on ? `${plural(cids.length, "carte masquée", "cartes masquées")} : retrouve-les avec « Masquées seulement ».` : `${plural(cids.length, "carte réaffichée", "cartes réaffichées")} dans ta collection.`, "good"));
  S.sel = new Set(); applyFilters(true); selPaint();
}
