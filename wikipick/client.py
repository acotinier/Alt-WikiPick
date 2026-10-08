"""Client HTTP pour l'API de wiki-pick.com (lecture seule pour l'instant).

L'authentification repose sur le cookie de session du site : on le récupère
depuis la vraie fenêtre de connexion (voir app.py), le mot de passe ne passe
jamais par ce code.
"""
import json
import os
import stat
import sys
from pathlib import Path
from urllib.parse import quote, urlencode

import requests

from .stream import parse_sse

BASE = "https://wiki-pick.com"
DEFAULT_UA = "Mozilla/5.0 (compatible; WikiPickDesktop/0.1; client perso)"


class ApiError(Exception):
    pass


class SessionExpired(ApiError):
    pass


def data_dir():
    if sys.platform.startswith("win"):
        root = Path(os.environ.get("APPDATA") or Path.home())
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    d = root / "WikiPickDesktop"
    d.mkdir(parents=True, exist_ok=True)
    return d


class WikiPickClient:
    def __init__(self, session_file=None):
        self.session_file = Path(session_file) if session_file else data_dir() / "session.json"
        self.http = requests.Session()
        self.http.headers.update({"User-Agent": DEFAULT_UA, "Accept": "application/json"})
        self._stream_resp = None

    # ---- session -------------------------------------------------------
    def set_user_agent(self, ua):
        if ua:
            self.http.headers["User-Agent"] = ua

    def set_cookies(self, mapping):
        self.http.cookies.clear()
        for name, value in mapping.items():
            self.http.cookies.set(name, value, domain="wiki-pick.com", path="/")

    def cookies_dict(self):
        return {c.name: c.value for c in self.http.cookies}

    def save_session(self):
        payload = {"cookies": self.cookies_dict(), "ua": self.http.headers.get("User-Agent")}
        self.session_file.write_text(json.dumps(payload), encoding="utf-8")
        try:  # lisible uniquement par l'utilisateur (no-op utile sous Linux/macOS)
            os.chmod(self.session_file, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    def load_session(self):
        try:
            payload = json.loads(self.session_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        cookies = payload.get("cookies") or {}
        if not cookies:
            return False
        self.set_cookies(cookies)
        self.set_user_agent(payload.get("ua"))
        return True

    def clear_session(self):
        self.http.cookies.clear()
        try:
            self.session_file.unlink()
        except OSError:
            pass

    # ---- requêtes ------------------------------------------------------
    def _decode(self, r, path, expired):
        path = path.split("?")[0]
        if r.status_code in expired:
            raise SessionExpired("Session expirée, reconnecte-toi.")
        if r.status_code >= 400:
            try:  # le site renvoie {"error": "<message en français>"}
                msg = (r.json() or {}).get("error")
            except (ValueError, AttributeError):
                msg = None
            raise ApiError(msg if isinstance(msg, str) and msg else f"Le site a répondu HTTP {r.status_code} pour {path}")
        try:
            return r.json()
        except ValueError as e:
            raise ApiError("Réponse inattendue (pas du JSON) : session invalide ?") from e

    def _get_json(self, path):
        try:
            r = self.http.get(BASE + path, timeout=25)
        except requests.RequestException as e:
            raise ApiError(f"Réseau indisponible : {e.__class__.__name__}") from e
        return self._decode(r, path, (401, 403))

    def _post_json(self, path, body):
        # Un 403 sur une écriture n'est pas forcément une session morte : seul 401 l'est (comme dans core.js).
        try:
            r = self.http.post(BASE + path, json=body, timeout=25,
                               headers={"Origin": BASE, "Referer": BASE + "/"})
        except requests.RequestException as e:
            raise ApiError(f"Réseau indisponible : {e.__class__.__name__}") from e
        return self._decode(r, path, (401,))

    def login(self, login, password, defi, rep):
        """Connexion par identifiants (version web) : `POST /api/login` avec la réponse à la question « es-tu un robot ? »
        (lue dans social.js). Les cookies de session arrivent dans `self.http.cookies`. Le mot de passe n'est jamais gardé."""
        try:
            r = self.http.post(BASE + "/api/login", json={"login": login, "password": password, "defi": defi, "rep": rep},
                               timeout=25, headers={"Origin": BASE, "Referer": BASE + "/"})
        except requests.RequestException as e:
            raise ApiError(f"Réseau indisponible : {e.__class__.__name__}") from e
        if r.status_code >= 400:  # 401 = mauvais identifiants ici, pas une session expirée
            try:
                msg = (r.json() or {}).get("error")
            except (ValueError, AttributeError):
                msg = None
            raise ApiError(msg if isinstance(msg, str) and msg else f"Connexion refusée (HTTP {r.status_code}).")
        if not self.http.cookies:
            raise ApiError("Le site n'a pas ouvert de session : réessaie.")
        return True

    def state(self):
        return self._get_json("/api/state")

    def collection(self):
        return self._get_json("/api/collection?v=2")

    def pack_challenge(self):
        """Question « es-tu un robot ? » que le site pose avant un paquet quand `me.defi` est vrai (comme social.js)."""
        return self._get_json("/api/defi")

    def open_pack(self, proof=None):
        """Ouvre UN paquet (action manuelle, jamais en boucle). proof = {defi, rep} : la réponse cliquée par le joueur.
        -> {cards: [...], me: {...}}"""
        return self._post_json("/api/open", {"sait": 1, **(proof or {})})

    def pack_seen(self, ts, genre="normal"):
        """Dit au serveur que les cartes ont été affichées (sinon un bouton « Revoir » reste sur le site)."""
        return self._post_json("/api/paquet/vu", {"genre": genre, "ts": ts})

    def notifications(self):
        return self._get_json("/api/notifications")

    def mark_notifications_read(self):
        """Comme quand on ouvre la cloche sur le site."""
        return self._post_json("/api/notifications/read", {})

    def auctions(self, scope="live", page=0, q="", rarities=(), tri="fin", kind=""):
        """Enchères (lecture seule). `live` = le marché, paginé, avec recherche / tri / type / raretés côté serveur ;
        `mine` (mes ventes) et `bidding` (mes mises) reviennent en une fois, sans paramètres, comme sur le site."""
        if scope == "live":
            qs = urlencode({"scope": "live", "q": q, "tri": tri, "page": page, "r": ",".join(rarities), "t": kind})
        else:
            qs = urlencode({"scope": scope})
        return self._get_json("/api/auctions?" + qs)

    def card(self, cid):
        """Fiche d'une carte (lecture seule) : extrait Wikipédia, provenance de tes exemplaires, amis, enchères en cours."""
        return self._get_json("/api/card?" + urlencode({"cid": cid}))

    # ---- écritures manuelles : jamais appelées en boucle, jamais rejouées automatiquement ----
    def auction(self, auction_id):
        return self._get_json("/api/auction?" + urlencode({"id": auction_id}))

    def bid(self, auction_id, amount):
        return self._post_json("/api/auction/bid", {"auction_id": auction_id, "amount": amount})

    def auction_create(self, card_id, start_price, duration):
        return self._post_json("/api/auction/create", {"card_id": card_id, "start_price": start_price, "duration": duration})

    def auction_cancel(self, auction_id):
        return self._post_json("/api/auction/cancel", {"auction_id": auction_id})

    def auction_price(self, auction_id, start_price):
        return self._post_json("/api/auction/prix", {"auction_id": auction_id, "start_price": start_price})

    def trade_action(self, action, trade_id):
        return self._post_json(f"/api/trade/{action}", {"trade_id": trade_id})

    def trade_send(self, body, counter=False):
        return self._post_json("/api/trade/counter" if counter else "/api/trade/create", body)

    def fusion(self, rank=None, page=0):
        """L'atelier de fusion : sans rang, seulement les recettes ; avec un rang, les cartes fusionnables (24 par page, doublons d'abord)."""
        return self._get_json("/api/fusion" + (f"?rang={quote(rank, safe='')}&page={int(page)}" if rank else ""))

    def fusion_do(self, ids, page=0):
        """UNE fusion (2 ou 3 cartes du même rang). Elle peut rater : les cartes sont alors perdues. Jamais rejouée."""
        return self._post_json("/api/fusion", {"ids": ids, "page": page})

    def bank(self, card_id):
        return self._post_json("/api/bank", {"card_id": card_id})

    def bank_bulk(self, card_ids):
        return self._post_json("/api/bank/bulk", {"card_ids": card_ids})

    def corbeille(self):
        return self._get_json("/api/corbeille")

    def corbeille_restore(self, body):
        return self._post_json("/api/corbeille/restaurer", body)

    def corbeille_empty(self):
        return self._post_json("/api/corbeille/vider", {})

    def card_lock(self, card_id, cid, shiny, on):
        return self._post_json("/api/card/lock", {"card_id": card_id, "cid": cid, "shiny": 1 if shiny else 0, "on": bool(on)})

    def card_for_sale(self, card_id, on):
        return self._post_json("/api/card/avendre", {"card_id": card_id, "on": bool(on)})

    def wish(self, cid, on, card):
        return self._post_json("/api/wish", {"cid": cid, "on": bool(on), "card": card})

    def friends(self):
        return self._get_json("/api/friends")

    def user_cards(self, name):
        return self._get_json("/api/user/cards?" + urlencode({"name": name}))

    def pro_market(self, cid, rarity, shiny):
        """WIKI-PRO : le serveur ne répond qu'aux abonnés. L'appelant ne tente rien si le profil n'est pas abonné."""
        return self._get_json("/api/pro/marche?" + urlencode({"cid": cid, "r": rarity, "sh": 1 if shiny else 0}))

    def open_gold_pack(self):
        """Paquet doré (offert ou PRO du jour), quand le profil l'indique (`proPack` / `paquetOr`)."""
        return self._post_json("/api/pro/paquet", {"sait": 1})

    # ---- arène : invitations et combats à deux, sur clic ; le serveur joue tout le duel ----
    def combat(self):
        return self._get_json("/api/combat")

    def combat_state(self):
        return self._get_json("/api/combat/defi")

    def combat_decks(self):
        return self._get_json("/api/combat/decks")

    def combat_deck_save(self, deck_id, name, cards):
        return self._post_json("/api/combat/deck", {"id": deck_id, "nom": name, "cards": cards})

    def combat_deck_delete(self, deck_id):
        return self._post_json("/api/combat/deck/supprimer", {"id": deck_id})

    def combat_challenge(self, name):
        return self._post_json("/api/combat/defier", {"name": name})

    def combat_answer(self, defi_id, ok):
        return self._post_json("/api/combat/repondre", {"id": defi_id, "ok": bool(ok)})

    def combat_choice(self, defi_id, cards):
        return self._post_json("/api/combat/choix", {"id": defi_id, "cards": cards})

    def combat_team(self, defi_id, cards):
        return self._post_json("/api/combat/equipe", {"id": defi_id, "cards": cards})

    def combat_cancel(self, defi_id):
        return self._post_json("/api/combat/annuler", {"id": defi_id})

    def combat_chest(self):
        return self._post_json("/api/combat/coffre", {})

    def users(self, q):
        return self._get_json("/api/users?" + urlencode({"q": q}))

    def history(self, kind, page=0):
        """Achats (`purchases`) ou ventes (`ventes`) terminés, par pages, comme le site."""
        return self._get_json(f"/api/{kind}?" + urlencode({"page": page}))

    def trades(self, box):
        """Échanges entre amis (lecture seule) : `received`, `sent` ou `history`."""
        return self._get_json("/api/trades?" + urlencode({"box": box}))

    def ranking(self, period):
        return self._get_json("/api/ranking?" + urlencode({"periode": period}))

    # ---- social et récompenses (formes lues dans social.js). Les écritures ne partent que sur un clic. ----
    def conversations(self):
        return self._get_json("/api/conversations")

    def thread(self, name):
        return self._get_json("/api/thread?" + urlencode({"name": name}))

    def message_send(self, to, text):
        return self._post_json("/api/message/send", {"to": to, "text": text})

    def friend_action(self, action, name):
        """request | accept | decline | remove | block | unblock"""
        return self._post_json("/api/friend/" + action, {"name": name})

    def friend_favorite(self, name, on):
        return self._post_json("/api/friend/favori", {"name": name, "on": bool(on)})

    def profile(self, name=None):
        return self._get_json("/api/profile" + ("?" + urlencode({"name": name}) if name else ""))

    def player_cards(self, name, page=0, q="", rarities="", order=""):
        return self._get_json("/api/joueur/cartes?" + urlencode({"name": name, "page": page, "q": q, "r": rarities, "ordre": order}))

    def guilds(self):
        return self._get_json("/api/guilds")

    def guild(self, gid):
        return self._get_json("/api/guild?" + urlencode({"id": gid}))

    def guild_post(self, action, body):
        """apply, apply/cancel, apply/accept, apply/decline, leave, kick, officier, chat, chat/vu, comment, comment/delete, like, create"""
        return self._post_json("/api/guild/" + action, body)

    def achievements(self):
        return self._get_json("/api/succes")

    def claim(self, kind, body):
        """Encaisser une récompense déjà gagnée : quete | bienvenue | succes | serie (le serveur vérifie tout)."""
        return self._post_json("/api/" + kind, body)

    # ---- temps réel ----------------------------------------------------
    def stream_events(self):
        """Générateur (événement, données) de /api/stream. Une seule connexion, comme le site.
        Émet d'abord ("open", {}) ; se termine à la coupure (le rappelant se reconnecte avec un délai)."""
        s = requests.Session()  # session à part : le flux bloque, les appels normaux ne doivent pas l'attendre
        s.headers.update(self.http.headers)
        s.headers.update({"Accept": "text/event-stream", "Accept-Encoding": "identity", "Cache-Control": "no-cache"})
        s.cookies.update(self.http.cookies)
        try:
            r = s.get(BASE + "/api/stream", stream=True, timeout=(10, 90))
        except requests.RequestException as e:
            raise ApiError(f"Réseau indisponible : {e.__class__.__name__}") from e
        self._stream_resp = r
        try:
            if r.status_code == 401:
                raise SessionExpired("Session expirée, reconnecte-toi.")
            if r.status_code >= 400:
                raise ApiError(f"Le flux a répondu HTTP {r.status_code}")
            yield "open", {}
            lines = (raw.rstrip(b"\r\n").decode("utf-8", "replace") for raw in iter(r.raw.readline, b""))
            yield from parse_sse(lines)
        except (ApiError, GeneratorExit):
            raise
        except Exception as e:  # coupure réseau, délai dépassé, flux fermé par close_stream()
            raise ApiError(f"Flux interrompu : {e.__class__.__name__}") from e
        finally:
            r.close()
            if self._stream_resp is r:  # un ancien flux qui se termine ne doit pas effacer le nouveau
                self._stream_resp = None

    def close_stream(self):
        r = self._stream_resp
        if r is not None:
            try:
                r.close()
            except Exception:
                pass

    def current_user(self):
        """Profil si la session est valide, sinon None."""
        try:
            me = (self.state() or {}).get("me")
        except ApiError:
            return None
        return me if isinstance(me, dict) and me.get("id") else None
