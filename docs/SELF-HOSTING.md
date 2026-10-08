# Héberger sa propre instance d'Alt-WikiPick (version web)

La version web est une application à installer **chez toi** : un petit serveur (Python) qui parle à wiki-pick.com pour toi, et une interface (Svelte) pensée pour le téléphone. Chaque personne qui s'y connecte utilise son propre compte du jeu ; tu décides qui peut venir.

> Projet **non officiel**, sans lien avec wiki-pick.com, qui n'a pas d'API publique. Une instance multiplie les connexions vers le site (une par joueur actif) : reste raisonnable (`ALTWP_MAX_USERS`) et, si tu ouvres ton instance à d'autres, préviens le développeur du jeu. Le jeu n'a pas de conditions d'utilisation publiées.

## Ce qu'il te faut

- Un serveur ou un petit VPS avec **Docker**, ou Python 3.10+ et Node 20+.
- Un nom de domaine et **HTTPS** : les sessions voyagent dans un cookie réservé à HTTPS.

## Démarrage rapide (Docker)

```bash
git clone https://github.com/acotinier/Alt-WikiPick.git
cd Alt-WikiPick
cp .env.example .env            # puis édite-le : au minimum ALTWP_SECRET
docker compose up -d --build
```

L'appli écoute sur `127.0.0.1:8000` (change le port avec `ALTWP_HOST_PORT` dans `.env`, sans toucher à `docker-compose.yml`). Pour la mettre sur Internet avec HTTPS automatique, le plus simple est [Caddy](https://caddyserver.com) : copie `Caddyfile.example`, remplace le nom de domaine par le tien, et mets `ALTWP_TRUST_PROXY=1` dans `.env`.

> L'image Docker n'a pas encore été construite par l'auteur dans son environnement de développement (le même enchaînement a été exécuté à la main : `npm ci && npm run build`, `pip install -r requirements-server.txt`, `python -m server`). Si quelque chose coince, ouvre une issue.

## Sans Docker

```bash
pip install -r requirements-server.txt
(cd webapp && npm ci && npm run build)
ALTWP_SECRET="une longue phrase" ALTWP_COOKIE_SECURE=0 python -m server    # http://localhost:8000
```

`ALTWP_COOKIE_SECURE=0` ne sert qu'à essayer en local ; en production, laisse HTTPS et la valeur par défaut.

## Réglages (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `ALTWP_SECRET` | *(clé générée)* | Phrase secrète qui chiffre les sessions wiki-pick au repos. La perdre oblige chacun à se reconnecter. |
| `ALTWP_COOKIE_SECURE` | `1` | Cookie réservé à HTTPS. |
| `ALTWP_TRUST_PROXY` | `0` | `1` derrière un reverse proxy, pour lire la vraie adresse du visiteur. **Jamais à `1` sans proxy** : l'adresse deviendrait falsifiable. |
| `ALTWP_MAX_USERS` | `20` | Nombre maximum de comptes wiki-pick sur l'instance (`0` = illimité). |
| `ALTWP_ALLOWED_USERS` | *(tous)* | Liste de pseudos autorisés, séparés par des virgules : une instance privée pour toi et tes amis. |
| `ALTWP_SESSION_DAYS` | `30` | Durée d'une session de l'appli (glissante). |
| `ALTWP_RPC_PER_MINUTE` | `240` | Appels autorisés par minute et par joueur. |
| `ALTWP_USER_AGENT` | *(Alt-WikiPick-Web)* | Identifiant envoyé à wiki-pick.com. |
| `ALTWP_DATA` | `data` (`/data` en Docker) | Dossier des données. |
| `ALTWP_HOST` / `ALTWP_PORT` | `0.0.0.0` / `8000` | Adresse d'écoute. |

## Ce que le serveur voit, garde et oublie

- **Connexion** : le joueur saisit son pseudo et son mot de passe ; le serveur les envoie **une seule fois** à wiki-pick.com (avec la réponse à la question « es-tu un robot ? » que le joueur clique lui-même) et ne les garde pas. Il conserve seulement les cookies de session reçus, **chiffrés** (Fernet) dans une base SQLite, et donne au navigateur un cookie propre à l'appli (`HttpOnly`, `SameSite=Lax`, `Secure`) dont seule l'empreinte est stockée. Conséquence à assumer : *pendant la connexion, le mot de passe passe par ton serveur*. Héberger sa propre instance, c'est précisément pouvoir lui faire confiance.
- **Plusieurs appareils** : téléphone et ordinateur d'un même joueur partagent une seule connexion temps réel vers wiki-pick.com. La déconnexion du dernier appareil efface les cookies wiki-pick et le cache du joueur.
- **Par joueur** (dans `data/users/<id>/`) : préférences, cartes surveillées, journal des paquets et des actions, cache de la collection. Le texte de tes messages n'est jamais écrit dans le journal.
- **Rien d'autre ne sort** : aucune télémétrie, aucun service tiers ; le navigateur charge seulement les images de Wikimedia et les avatars de wiki-pick.com (politique de sécurité stricte).
- **Protection** : origine vérifiée sur chaque écriture, limites de débit (connexions, appels), en-têtes de sécurité, chaque appel de l'interface passe par une liste blanche de méthodes (`server/rpc.py`).

## Être poli avec wiki-pick.com

- Une connexion temps réel par joueur **actif** : elle s'ouvre quand un navigateur écoute, se ferme 45 secondes après son départ, et l'interface la coupe quand l'onglet est caché plus de 45 s.
- Un appel « profil » et un appel « collection » par actualisation, pas de sondage ; les enchères ne sont suivies que sur l'écran Marché.
- Presque aucune automatisation : tout ce qui écrit part sur un clic, avec confirmation quand il engage des pièces ou des cartes. Seule exception, le lot de fusions lancé et confirmé par le joueur : une fusion à la fois (au plus une par seconde), arrêt à la moindre erreur, interrompu si l'interface ne le suit plus. L'appli ne répond jamais à la vérification du site à la place du joueur.

## Sauvegarde et mise à jour

- **Sauvegarde** : le dossier des données (volume Docker `altwp-data`). `accounts.db` et `secret.key` (ou ta `ALTWP_SECRET`) vont ensemble. Perdre la clé n'est pas grave : les joueurs se reconnectent.
- **Mise à jour** : `git pull && docker compose up -d --build`. Les sessions survivent. Si `git pull` refuse à cause d'un fichier que tu as modifié (`docker-compose.yml`, par exemple) : `git stash && git pull && git stash pop`, ou remets le fichier d'origine (`git checkout docker-compose.yml`) et règle ce que tu voulais dans `.env`.
- **Santé** : `GET /healthz` renvoie le nombre de joueurs en mémoire.

## Développer

```bash
cd webapp && npm install
npm run dev:mock      # interface seule, données de démonstration (mot de passe : demo)
npm run dev           # interface sur :5173, relayée vers un serveur local (python -m server sur :8000)
python tests/web_smoke.py   # test de bout en bout (Chromium)
pytest tests                # noyau, bureau et serveur
```

Quand le site change de format, on corrige à **un seul endroit** : le noyau partagé (`wikipick/`), utilisé par l'appli de bureau comme par ce serveur.
