"use strict";
/* Nouveautés : les notes de version d'Alt-WikiPick (fichier local). Celles du site lui-même sont sur wiki-pick.com/nouveautes : un lien, pas une copie.
   Chargé AVANT app.js : rien ne s'exécute ici au chargement. */

const NEWS_KIND = { new: "Nouveau", better: "Amélioré", fix: "Corrigé" };
const newsDay = (s) => new Date(s + "T12:00:00").toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });

async function loadNews() {
  const box = $("news-body");
  if (box.dataset.done) return;
  const r = await api().news_get();
  if (!r.ok) return box.replaceChildren(el("p", { class: "note", text: "Nouveautés indisponibles pour le moment." }));
  box.dataset.done = "1";
  box.replaceChildren(
    el("button", { class: "news-site", onclick: () => api().open_url(r.site_url) }, icon("out"), el("span", {}, "Les mises à jour de wiki-pick.com", el("small", { text: "Les notes du jeu lui-même, sur le site" }))),
    ...r.versions.map((v, i) => el("article", { class: "ver" + (i === 0 ? " latest" : "") },
      el("header", {}, el("b", { class: "serif num", text: v.version }), el("span", { class: "muted", text: newsDay(v.date) }), i === 0 ? el("em", { text: "Dernière" }) : null),
      el("h2", { class: "serif", text: v.title }),
      el("ul", {}, v.items.map((it) => el("li", {}, el("span", { class: "k " + it.kind, text: NEWS_KIND[it.kind] }), el("p", { text: it.text })))))));
}
