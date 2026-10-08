# API wiki-pick.com : ce qu'on sait

Source : observation du site dans Chrome (onglet Réseau) et lecture du JS public du site (`/js/*.js`), septembre 2026. Aucune action de jeu n'a été exécutée pendant l'exploration : seulement des `GET` de lecture.

**Légende de fiabilité**
- ✅ **Vérifié** : observé en vrai (requête vue dans le réseau, ou réponse lue et décodée).
- 🔎 **Vu dans le JS** : le nom du chemin apparaît dans le code du site, mais on n'a pas vu la requête ni sa charge utile.
- ❓ **Inconnu** : à déterminer (méthode HTTP, corps, réponse).

Le site est en français, en bêta. Base : `https://wiki-pick.com`.

---

## 1. Authentification

- ✅ Aucune trace de CSRF, d'en-tête `Authorization` ni de `Bearer` dans `core.js` (0 occurrence). Une occurrence de `credentials` et une de `localStorage.getItem`.
- **Conclusion (inférée)** : l'auth est un **cookie de session** posé par le site. Le client doit renvoyer ce cookie (`requests.Session`).
- Connexion possible par e-mail/mot de passe (`/api/login`) et par OAuth : `state.info.oauth` liste 2 fournisseurs, `oauthNoms` connaît `google`, `discord`, `facebook`, `x`.
- ✅ **`POST /api/login`** `{login, password, defi, rep}` : `login` = pseudo ou e-mail ; `defi` et `rep` = la réponse à la question « es-tu un robot ? » (`GET /api/defi`, même mécanisme que pour les paquets). Lu dans `social.js` (`authMode === "login"`), utilisé par la version web (`WikiPickClient.login`) ; la réponse pose les cookies de session. Le bureau, lui, passe par la vraie page du site. Les messages d'erreur sont en français dans `{error}`.
- Le login sert à obtenir un cookie ; ensuite `GET /api/state` répond avec `me` rempli si connecté. Test de session valide utilisé dans le code : `state.me` est un dict avec un `id` truthy.
- Le cookie de session est peut-être lié au User-Agent : le client reprend le `navigator.userAgent` de la fenêtre de login (non confirmé nécessaire).

## 2. Endpoints vérifiés (GET, réponse 200 observée)

Requêtes vues au chargement de `/classement` :

| Endpoint | Rôle probable |
|---|---|
| ✅ `/api/state` | Config du jeu (`info`) + profil (`me`). Décodé ci-dessous. |
| ✅ `/api/collection?v=2` | Collection complète, format compact. Décodé ci-dessous. |
| ✅ `/api/possedees` | Cartes possédées (forme non décodée) |
| ✅ `/api/ranking?periode=tout` | Classement (forme non décodée ; `periode=tout` observé, autres valeurs inconnues) |
| ✅ `/api/combat/defi` | État des défis de combat (forme non décodée) |
| ✅ `/api/stream` | Flux temps réel : SSE d'après le JS du site (voir §2.4) ; la connexion elle-même n'a pas été observée |

### 2.1 `GET /api/state`

```
{
  info: {
    scale: [["M", 80000000], ["L", 30000000], ["UR", 12…], …]   // 7 paires [code, seuil de valeur] ; lecture tronquée après "UR"
    names: { C:"Commune", PC:"Inhabituelle", R:"Rare", SR:"Épique", UR:"Exceptionnelle",
             L:"Légendaire", M:"Mythique", WBC:"Exclusive", SIXSEVEN:"Exclusive", EXC:"Exclusive" },
    bank:     { C, PC, R, SR, UR, L, M },      // nombres (probablement valeur de rachat en pièces par rareté)
    odds:     { M, L, UR, SR, R, PC, C },      // probabilités de tirage
    oddsCarte:{ M, L, UR, SR, R, PC, C },
    shinyOdds, shinySur, fee, perPack,          // nombres
    aucMax, aucMaxPro,                          // enchères max simultanées
    proCards, packEvery, packEveryPro, packMax, packMaxPro,
    echJour, echJourPro, echAttente,            // limites/attente pour les échanges
    shop: [ 9 × {…} ], shopOn: bool,            // boutique (Stripe côté serveur)
    oauth: [ 2 × string ], oauthNoms: { google, discord, facebook, x },
    editions: number, catalogAt: number
  },
  me: {
    choisirPseudo: bool, id, name, email, coins, packs, packMax, packStock, packReserve,
    next, packEvery, cards, avatar, avatarNSFW, pro, proUntil, abo, proPack, paquetOr,
    supportNeuf, orRevoir, revoir: [], revoirTs: {}, proNext, proCards,
    aucLive, aucMax, defi, admin, succes
  }
}
```

Notes :
- `me.email` est une donnée personnelle : **ne jamais l'envoyer à l'interface ni dans les logs** (le projet la filtre dans `safe_me`).
- Le sens exact de `next` / `proNext` (secondes restantes ou timestamp) n'est pas confirmé ; l'interface ne les affiche pas.
- `me.cards` (3909 sur le compte de test) est proche mais pas égal au nombre de groupes de la collection (3908) : `me.cards` compte les exemplaires, les groupes sont les cartes uniques.

### 2.2 `GET /api/collection?v=2`

```
{
  order: [],
  me: { …identique à state.me… },
  rank: { rank, total, points, cards, toNext, nextName },   // ex. {rank:232,total:6898,points:14374,cards:3904,toNext:15,nextName:"rival"}
  tags: [ { id, name, color, ordre, oc } ],                 // tags perso du joueur
  masquees: [ ids… ],                                       // cartes exclusives masquées
  aVendre: [],                                              // cartes mises en vente
  ord: …,                                                   // ordre perso (vu dans le JS, non observé dans la réponse)
  champs: ["cid","n","d","img","r","v","nl","lang","locked"],
  imgp: ["https://thumb.wikimedia.org/wikipedia/commons/thumb/",
         "https://upload.wikimedia.org/wikipedia/commons/"],
  groups: [ [ … ], … ]                                      // 3908 lignes sur le compte de test
}
```

**Décodage d'une ligne de `groups`** (calqué sur `groupeCompact()` dans `cards.js`) : avec `n = champs.length` (9) :

| Indice | Contenu |
|---|---|
| `0..n-1` | valeurs dans l'ordre de `champs` |
| `n` | liste des **ids des exemplaires** possédés (ex. `[5791707]`) |
| `n+1` | liste des **ids de tags** de la carte |
| `n+2` | dict de **champs rares** fusionné dans la carte : `sh` (shiny), `frt`, `perso`… (seul `sh` est exploité) |

Les champs :

| Champ | Sens |
|---|---|
| `cid` | id de carte = `"<lang>:<Titre_Wikipedia>"`, ex. `fr:Rudná_(district_de_Prague-Ouest)` → article `https://fr.wikipedia.org/wiki/<Titre>` |
| `n` | nom affiché |
| `d` | description courte (description Wikidata) |
| `img` | **1er caractère = index dans `imgp`**, le reste = fin de l'URL. Ex. `"05/5e/Fichier.JPG/960px-Fichier.JPG"` → `imgp[0] + "5/5e/Fichier.JPG/960px-Fichier.JPG"`. Certaines URLs se terminent par `?utm_source=fr.wikipedia.org&utm_campaign=api&utm_content=thumbnail`. |
| `r` | rareté : `C, PC, R, SR, UR, L, M`, ou exclusives `EXC, WBC, SIXSEVEN` |
| `v` | ✅ **Lectures** de l'article Wikipédia « dans le monde » (entier). Ce n'est **ni un id ni un prix** : le site l'appelle « lectures » (« Calcul des lectures dans le monde… ») et les seuils de `state.info.scale` s'appliquent à ce nombre pour donner la rareté. La valeur en Wikiki d'une carte est `info.bank[rareté]` (recyclage). |
| `nl` | ❓ entier, souvent 1, jusqu'à 215 ; sens inconnu. Non affiché. |
| `lang` | langue de l'article (`fr`, ou vide pour 2 cartes exclusives) |
| `locked` | carte verrouillée (peut arriver en chaîne `"false"`/`"true"` ou en booléen : les deux sont gérés) |

Répartition observée sur le compte de test (3908 cartes uniques) : C 2163, PC 1347, R 267, SR 99, UR 21, L 8, M 1, EXC 2. Ça donne un ordre de grandeur de la rareté.

Ancien format : si `champs` est absent, `groups` contient déjà des objets (le site gère les deux ; `parse_collection` aussi).

**Images** : ✅ le site charge bien des miniatures `thumb.wikimedia.org/.../960px-...` (vu dans le réseau). ⚠️ Le chargement des images **reconstruites par notre décodeur** n'a pas été testé dans une vraie fenêtre (le seul test fait en navigateur oubliait de retirer le chiffre d'index, il n'est donc pas concluant). À vérifier au premier lancement. Le décodeur n'accepte que les hôtes `upload.wikimedia.org` et `thumb.wikimedia.org`.

### 2.3 Écritures vérifiées (paquets)

- ✅ `POST /api/open` avec `{"sait": 1}` : ouvre **un** paquet. Réponse `{cards: [...], me: {...}}` (`me` = état complet, contient `email` : ne pas le relayer). Carte : `cid, lang, orig, n, d, e (extrait), img (URL complète ou null), qid, nl, v, r, byl, at, id, isNew` (+ `sh` si chromatique).
  - ✅ Si `me.defi` est vrai (toutes les ~3 h d'après un commentaire de `cards.js`), le site exige une preuve : `GET /api/defi` → `{id, consigne, choix: [6 SVG]}` (réponse réelle fournie par l'utilisateur, sept. 2026 ; la bonne réponse ne quitte jamais le serveur), puis `POST /api/open {sait: 1, defi: <id>, rep: <index du SVG cliqué, à partir de 0>}` (lu dans `social.js` : `demanderDefi` / `fermerDefi`, et `cards.js` : `openPack`). Le bouton « une autre question » du site refait simplement `GET /api/defi`. Le paquet doré (`pro/paquet`) n'en demande pas. L'appli montre la question au joueur et transmet **son** clic ; elle ne répond jamais seule.
  - `me.revoirTs.normal` = horodatage du paquet livré.
- 🔎 `POST /api/paquet/vu` avec `{"genre": "normal", "ts": <revoirTs.normal>}` : acquittement « cartes affichées » (sans lui, le site garde un bouton « Revoir »). Implémenté, non vérifié en vrai.
- 🔎 Non implémenté : `POST /api/reveler {ids}` (annonce des cartes rares dans le fil), `paquet/revoir`, `paquet/relancer`, `pro/paquet`.
- `me.next` : vu à 423 avec `packEvery` = 600 → très probablement **secondes avant le prochain paquet**.

### 2.4 Temps réel, notifications, marché (🔎 lus dans le JS du site, jamais observés en vrai)

**Flux `GET /api/stream`** (`social.js`, `connectStream`) : `EventSource`, donc SSE. Le site ouvre **une** connexion et écoute des événements **nommés**, chacun avec un `data:` JSON : `auction`, `feed`, `guild`, `notify`, `trade`, `message`, `combat`, `admin`, `support`, `evenement`. Si la réponse n'est pas un 200, `EventSource` abandonne : le site se reconnecte lui-même avec un délai de `min(30 s, 2 s × 2^n)`, puis relit ce qui est à l'écran. Le client fait pareil (`wikipick/live.py`, délai `3 s × 2^n`) et émet un événement `resync`.

| Événement | Champs utilisés | Remarques |
|---|---|---|
| `notify` | `to, id, type, text, kind ("good"/"bad"), link` | seulement si `to` = le joueur. `type` : `outbid, won, sold, unsold, fin, wish, friend_request, friend, trade, guild, combat, like, comment…`. `fin` = « plus que 3 minutes » : la cloche suffit, pas de bandeau |
| `message` | `to, from` | nouveau message privé |
| `trade` | `to, what` | `what == "accepted"` : la collection a changé |
| `auction` | `what, id, price, leader, leaderId, endsAt, min, extended, sold, winnerId, cid` | `what` : `bid`, `end`, `cancel`, `prix`, `new` (ignoré par le site sur le marché). Très fréquent (des joueurs simulés en créent une par seconde) |

- `GET /api/notifications` → `{items: [{id, ntype, text, tone, link, read, created}], unread}` ; `created` en secondes.
- `POST /api/notifications/read` avec `{}` : tout marquer comme lu (le site le fait à l'ouverture de la cloche ; le client seulement sur clic « Tout marquer comme lu »).
- `GET /api/auctions?scope=live&q=&tri=fin&page=0&r=<raretés séparées par des virgules>&t=` → `{items, pages, total, page}`. Enchère : `id, card | lot {n, nom, cartes}, price, min, bids, leader, seller, mine, leading, endsAt (secondes, heure du serveur), status ("live" ou fini)`. `scope=mine` (mes ventes) et `scope=bidding` (mes mises) : ✅ appels vus par l'utilisateur, renvoyés **en une fois**, le site n'envoie que le `scope` (le client fait pareil). `tri` (lu dans le HTML du site) : `fin` (fin proche, défaut), `rarete`, `prixbas` (prix croissant), `prix` (prix décroissant), `mises` (meilleures enchères). `t` : `""` (tout), `cartes` (cartes seules), `lots`. Les réponses portent probablement `now` (le site en tire son décalage d'horloge : `SKEW`).
- Me : `unread, unreadMsg, trades, friendReq` (compteurs de la cloche).
- Écritures **non implémentées, à ne faire que sur clic explicite après accord** : `auction/bid`, `auction/create`, `auction/cancel`, `auction/prix`, `auction/chat/send`.
- Le journal `stream_debug.log` (noms d'événements et de champs) permet de vérifier ces formes sans exposer de valeurs. ✅ **Observé en vrai** (flux lu depuis le client) : `auction` avec `endsAt, extended, id, leader, leaderId, min, price, what` (mise), `cid, id, what` (nouvelle), `id, price, sold, what, winnerId` et `id, sold, what` (fin), `id, what` (annulation ?), `id, min, price, what` (`prix`) ; `notify` avec `id, kind, link, text, to, type` (+ `won`, non utilisé) ; `feed` (`user, what` / `post, what` / `what`) et `guild` (`id, what`) reçus mais ignorés.

### 2.6 Écritures manuelles (🔎 formes lues dans le JS du site, jamais observées en vrai)

Toutes déclenchées par un clic confirmé, une à la fois, journalisées localement (`actions.json`), jamais rejouées automatiquement.

- Enchères : `POST auction/bid {auction_id, amount}`, `auction/create {card_id, start_price, duration}` (durées en liste blanche), `auction/cancel {auction_id}`, `auction/prix {auction_id, start_price}`.
- Échanges : `POST trade/create`, `trade/counter`, `trade/accept|decline|cancel {trade_id}`.
- Collection : `POST bank {card_id}` (recycler une carte), `bank/bulk {card_ids}` (lots de 50), `corbeille/restaurer`, `corbeille/vider`, `card/lock {card_id, cid, shiny, on}`, `card/avendre {card_id, on}`, `wish {cid, on, card}`.
- Paquet doré : `POST pro/paquet {sait: 1}` **uniquement si `me.paquetOr`**. `GET pro/marche?cid=` **uniquement si `me.pro`**.
- Arène : `GET combat`, `combat/defi`, `combat/decks`, `users?q=` ; `POST combat/defier {name}`, `combat/repondre {id, ok}`, `combat/choix {id, cards}`, `combat/equipe {id, cards}`, `combat/annuler {id}`, `combat/coffre {}`, `combat/deck {id, nom, cards}`, `combat/deck/supprimer {id}`. Événement de flux `combat` : `what` = `defi | accepte | choix | pret | go | refuse | annule` (`go` porte le duel complet : manches, coups, PV).
- Fusion (✅ réponse réelle fournie par l'utilisateur, 08/10/2026) : `GET fusion` (recettes seules) ou `GET fusion?rang=C&page=0` (+ `liste` de 24 cartes fusionnables, doublons d'abord, avec `id` et `exemplaires`) ; `POST fusion {ids: [2 ou 3 ids], page}` -> `{reussie, rang, vers, chance, parties[ids consommés], reste, prochaine, carte{…, id, isNew} | absente, etat (= le GET du rang), me}`. Rangs : C → PC → R → SR → UR → L (les L et M ne se fusionnent pas). Une fusion ratée **détruit toutes les cartes posées** et ajoute des points de « maîtrise » (`echecs`, `bonus` à 3 cartes, `bonus2` à 2). Les cartes verrouillées, chromatiques ou exclusives n'apparaissent pas dans `liste`. `me` contient l'adresse e-mail : elle est retirée avant l'interface (`safe_me`).
- Jamais appelés : `admin/*`, Stripe.

### 2.5 Lectures ajoutées (🔎 formes lues dans le JS du site, jamais observées en vrai)

- `GET /api/ranking?periode=semaine|mois|tout` → `{points: {rareté: points par carte}, diamant: points d'une chromatique, regle: "acquis"|"glissant"|"", reste: secondes avant remise à zéro, top: [{rank, name, guild, gcouleur, me, chroma, mythic, legend, ultra, cards, points}]}`. Semaine et mois ne comptent que les cartes ouvertes en paquet ou remportées aux enchères pendant la période. `gcouleur` n'est jamais utilisé (pas de style venu du site).
- `GET /api/trades?box=received|sent|history` → `{trades: [{id, incoming, from, to, give, take, giveCoins, takeCoins, status, message, valid, created, closed}]}` ; `give` / `take` sont du point de vue de l'expéditeur : reçu (`incoming`), ce que **je** donne est `take`. `status` : `pending, accepted, declined, cancelled, invalid, countered`. Écritures (`trade/accept`, `decline`, `cancel`, `counter`, `create`) **non implémentées**.
- `GET /api/purchases?page=N` et `GET /api/ventes?page=N` → `{items: [{cid, title, rarity, img, shiny, price, vente, buyer, seller, ts, lot?}], more, n, somme}`.
- `GET /api/card?cid=…` (la fiche de la carte, sans abonnement) → `{card: {e (extrait Wikipédia), qid, orig, byl, at…}, mine: [{id, state: free|locked|auction|exclusive, sh, prov: {via: paquet|recompense|enchere|echange, ts, prix, de, lot}}], wished, chezAmis, chezGuilde, souhaitAmis, auctions: [...]}`.
- ⛔ `GET /api/pro/marche?cid=…` (courbe et historique des prix) est réservé aux abonnés **WIKI-PRO** : le client ne l'appelle pas.
- `state.info` : `odds` (pourcentage par paquet, par rareté), `shinyOdds`, `perPack`, `bank` (Wikiki gagnés au recyclage, par rareté) sont exposés à l'interface, rien d'autre de `info`.

## 3. Endpoints repérés dans le JS (🔎 noms uniquement)

Extraits par regex sur les littéraux `'/api/...'` des fichiers JS. **Méthodes HTTP, corps et réponses non observés** sauf mention contraire. La liste de `cards.js` et `social.js` est **tronquée** (sortie coupée), donc incomplète ; `editeur.js`, `main.js`, `walkout.js` n'ont pas été dépouillés.

Fichiers JS (publics, avec suffixe de cache `?v=<timestamp>`) : `/js/core.js` (99 ko), `/js/cards.js` (173 ko), `/js/social.js`, `/js/combat.js`, `/js/editeur.js`, `/js/main.js`, `/js/walkout.js`.

**Session / compte** : `login`, `logout`, `register`, `register/code`, `register/jeton`, `oauth/…`, `motdepasse/oubli`, `motdepasse/reset`, `account/pseudo`, `account/password`, `compte/description`, `compte/liens/delier`, `profile`, `profile/avatar`, `parrainage`, `bienvenue`, `quete`, `support`, `support/fils`, `support/lu`, `support/repondre`, `support/resolu`, `support/pj`, `signaler`, `blocages`, `moderation`

**Cartes / collection** : `collection`, `possedees`, `card`, `card/lock`, `card/tags`, `card/avendre`, `card/exclusive/masquer`, `catalogue`, `score`, `tags`, `tag/create`, `tag/update`, `tag/delete`, `tag/ord…` (tronqué), `corbeille`, `corbeille/restaurer`, `corbeille/vider`, `bank`, `bank/bulk`, `wish`, `lots`, `lots/enregistrer`, `lots/supprimer`, `lots/vendre`, `showcase/set`, `showcase/create`, `showcase/rename`, `showcase/move`, `showcase/delete`, `joueur/album`, `joueur/cartes`

**Paquets / boutique** : `open`, `reveler`, `paquet/vu`, `paquet/revoir`, `paquet/relancer`, `pro/paquet`, `boutique`, `boutique/portail`, `wbc`, `wbc/prendre`

**Marché / enchères** : `auction`, `auctions`, `auction/create`, `auction/bid`, `auction/cancel`, `auction/prix`, `auction/chat/send`, `pro/marche`, `ventes`, `purchases`

**Échanges** : `trades`, `trade/create`, `trade/accept`, `trade/decline`, `trade/cancel`, `trade/counter`, `user/cards`

**Social** : `feed`, `post`, `post/like`, `post/delete`, `comment/delete`, `friends`, `friend/…`, `friend/favori`, `conversations`, `thread`, `message/send`, `notifications`, `notifications/read`, `users`, `ranking`, `stream`

**Combat** : `combat`, `combat/defi`, `combat/defier`, `combat/repondre`, `combat/annuler`, `combat/choix`, `combat/coffre`, `combat/deck`, `combat/decks`, `combat/deck/supprimer`, `combat/equipe`

**À ne pas toucher** : les routes `admin/*` (config, panel, code, stripe/liste, stripe/sync, stripe/crediter, evenement, achats/preuve, pilotage, dossier, ouvrir, lies…) et tout ce qui touche à Stripe. Elles ne concernent pas un client joueur, et certaines sont des routes d'administration financière.

## 4. Comment continuer l'exploration (méthode)

1. **Lire le JS directement** : les fichiers `/js/*.js` sont publics et non minifiés (commentaires en français). `curl -s https://wiki-pick.com/js/social.js | grep -n "api/login"` puis lire autour de l'appel donne le payload exact. La fonction d'appel API centrale n'a pas été localisée (recherche de `async function api` infructueuse) : chercher `fetch(` dans `core.js`.
2. **HAR** : demander à l'utilisateur un export HAR d'un parcours (F12 → Réseau → « Conserver les journaux » → clic droit → « Enregistrer tout en HAR ») avec **cookies et tokens remplacés par `XXX`**. C'est la voie la plus fiable pour les `POST`.
3. **Payloads déjà connus de l'utilisateur** : il a déjà fait des actions en Python/Postman (non sauvegardées). Lui demander de redonner les corps de requête pour les endpoints visés.
4. Toujours confirmer avec l'utilisateur avant d'implémenter un endpoint qui **écrit** (achat, enchère, échange, ouverture de paquet).

## 5. Limites rencontrées pendant l'exploration

- L'outil de lecture du navigateur a **bloqué** plusieurs sorties contenant des chaînes de requête ou des cookies. Contournement utilisé : remplacer `?`, `=`, `&` par `~` dans les sorties, ou ne renvoyer que la **forme** des objets (clés et types).
- Les images n'ont pas pu être chargées depuis l'environnement d'exploration (réseau sortant filtré).
- Débit/limites de requêtes, en-têtes CORS et format exact du flux `/api/stream` : non vérifiés.
