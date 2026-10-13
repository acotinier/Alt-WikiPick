"""Les notes de version d'Alt-WikiPick, affichées dans l'onglet « Nouveautés » des deux interfaces.

Une entrée par version, la plus récente en premier. Les notes du site lui-même sont sur https://wiki-pick.com/nouveautes
(page statique, sans API : l'interface y renvoie par un lien plutôt que de la recopier)."""

SITE_NEWS_URL = "https://wiki-pick.com/nouveautes"

# kind : new (nouveau) | better (amélioré) | fix (corrigé)
CHANGELOG = [
    {"version": "0.4.0", "date": "2026-10-13", "title": "Season Pass, niveaux et nouveau design", "items": [
        ("new", "Season Pass : les cinquante niveaux, la récompense choisie en grand, récupérer une récompense, mettre un dos ou un cadre gagné."),
        ("new", "Ton niveau s'affiche autour de ta photo, avec l'anneau de progression."),
        ("new", "XP au temps passé, comme sur le site : le signal ne part que si tu joues vraiment (un geste, au plus toutes les 5 minutes)."),
        ("new", "Sur la fiche d'une carte : combien d'exemplaires existent déjà dans le jeu, chez combien de joueurs."),
        ("new", "Un onglet Nouveautés pour relire les mises à jour d'Alt-WikiPick."),
        ("new", "Nouvelle identité visuelle : cabinet de curiosités, laiton et velours, cartes montées sous passe-partout."),
        ("fix", "Les paquets de 20 cartes (dorés, légendaires) s'affichent en grille lisible, y compris sur téléphone."),
        ("fix", "Ouvrir plusieurs paquets d'un coup : boutons refaits pour le téléphone, et le nombre démarre au maximum disponible."),
    ]},
    {"version": "0.3.0", "date": "2026-10-08", "title": "Fusion, étiquettes et paquets groupés", "items": [
        ("new", "Fusion de cartes, à la main ou en lot automatique."),
        ("new", "Étiquettes, cartes masquées, tri par date d'obtention, ouverture de plusieurs paquets d'un coup."),
        ("new", "Marché en vue liste, images des cartes exclusives, description courte sur les aperçus."),
        ("better", "Les notifications sont lues dès qu'on ouvre la cloche."),
    ]},
    {"version": "0.2.0", "date": "2026-09-30", "title": "Version web et communauté", "items": [
        ("new", "Version web mobile d'abord, à héberger chez soi (multi-utilisateurs)."),
        ("new", "Messagerie, amis, guilde, profil, récompenses, quêtes et série de connexion."),
        ("new", "La vérification « es-tu un robot ? » du site est posée au joueur à l'ouverture d'un paquet."),
    ]},
    {"version": "0.1.0", "date": "2026-09-30", "title": "Première version", "items": [
        ("new", "Appli Windows : collection, paquets, marché en direct, échanges, arène, classement."),
    ]},
]


def news():
    return {"site_url": SITE_NEWS_URL, "versions": [
        {"version": v["version"], "date": v["date"], "title": v["title"], "items": [{"kind": k, "text": t} for k, t in v["items"]]} for v in CHANGELOG]}
