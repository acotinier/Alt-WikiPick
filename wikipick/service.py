"""Le service du jeu : tout ce qu'un joueur peut lire ou faire sur wiki-pick.com, validé et décodé.

Partagé entre l'appli de bureau (desktop/app.py) et le serveur web (server/). Aucune dépendance à une interface :
ni fenêtre, ni navigateur, ni HTTP entrant.
"""
import json
import os
import threading
import time
from pathlib import Path

from .client import BASE, ApiError, SessionExpired
from .export import collection_csv
from .live import LiveStream
from .parse import (FUSION_RANKS, compute_stats, expand_pack_card, parse_auction, parse_card_sheet, parse_chest, parse_collection,
                    parse_combat_info, parse_corbeille, parse_decks, parse_defi, parse_duel, parse_friends, parse_fusion, parse_history,
                    parse_notification, parse_pack_challenge, parse_pro_market, parse_ranking, parse_trade, parse_user_cards, parse_users, _safe_img, _to_int)
from .social import (parse_achievements, parse_claim, parse_conversations, parse_friend_lists, parse_guild, parse_guilds,
                     parse_player_cards, parse_profile, parse_rewards_state, parse_thread, parse_user_search)
from .store import JsonStore

PACK_HISTORY_MAX = 300  # paquets gardés dans le journal local
WATCH_MAX = 200  # cartes surveillées au plus
ACTIONS_MAX = 200  # actions gardées dans le journal local
ACTIONS_MAX = 200  # actions gardées dans le journal local
FUSION_PAUSE = 1.0  # secondes entre deux fusions d'un lot (le site, lui, anime chaque fusion pendant plus de deux secondes)
FUSION_DEADMAN = 90  # un lot s'arrête si l'interface n'est pas venue voir où il en est depuis ce nombre de secondes
FUSION_MAX_CARDS = 20000  # cartes consommées au plus par lot
AUCTION_DURATIONS = ("10m", "30m", "1h", "6h", "12h", "24h")  # celles du site
# Préférences : seules ces clés et ces valeurs sont acceptées (l'interface ne peut rien écrire d'autre)
PREF_BOOLS = ("sound",)
PREF_CHOICES = {
    "market_view": ("grid", "dense", "list"),
    "market_sort": ("fin", "rarete", "prixbas", "prix", "mises", "lectures", "nom"),
    "collection_sort": ("rarity", "reads", "name", "copies"),
}


def safe_me(me, info):
    """Profil sans données sensibles (pas d'email) pour l'interface."""
    avatar = me.get("avatar")
    if isinstance(avatar, str) and avatar.startswith("/"):
        avatar = BASE + avatar
    elif not (isinstance(avatar, str) and avatar.startswith("https://")):
        avatar = None
    keys = ("id", "name", "coins", "packs", "packMax", "packStock", "packReserve", "next", "cards", "pro", "succes", "aucLive", "aucMax",
            "unread", "unreadMsg", "trades", "friendReq", "proPack", "paquetOr", "proCards", "defi")
    out = {k: me.get(k) for k in keys}
    out["avatar"] = avatar
    return out


def _num(v, name, lo=1, hi=10**9):
    """Entier strict (jamais un booléen, une chaîne ou un décimal) dans [lo, hi] : tout ce qui part vers le site est validé ici."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != int(v) or not lo <= v <= hi:
        raise ApiError(f"{name} invalide.")
    return int(v)


def _fusion_ids(v):
    ids = _ids(v, "Cartes", 3)
    if len(ids) not in (2, 3) or len(set(ids)) != len(ids):
        raise ApiError("Une fusion prend 2 ou 3 cartes différentes.")
    return ids


def _ids(v, name, limit):
    if not isinstance(v, list) or len(v) > limit:
        raise ApiError(f"{name} invalide.")
    return [_num(i, name) for i in v]


def _cid(v):
    if not (isinstance(v, str) and 2 < len(v) <= 300 and ":" in v and v.split(":", 1)[0].isalpha()):
        raise ApiError("Carte inconnue.")
    return v


def safe_info(info):
    """Chiffres de jeu utiles à l'interface (chances de tirage, valeur de recyclage) : rien d'autre ne sort de Python."""
    def num(v):
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    def nums(d):
        return {str(k): v for k, v in d.items() if num(v) is not None} if isinstance(d, dict) else {}
    return {"odds": nums(info.get("odds")), "bank": nums(info.get("bank")), "shinyOdds": num(info.get("shinyOdds")), "perPack": num(info.get("perPack"))}


class Service:
    """Toute la logique du jeu pour UN joueur : lectures, écritures validées, fichiers locaux. Utilisée telle quelle par l'appli
    de bureau (`desktop/app.py`, qui y ajoute la fenêtre de connexion) et par le serveur web (un Service par joueur connecté).

    Toutes les méthodes publiques renvoient un dict {ok, error?, …} : aucune exception ne sort d'ici."""

    def __init__(self, client, data_dir):
        self._client = client
        self._dir = Path(data_dir)  # prefs, journaux et cache de CE joueur
        self._dir.mkdir(parents=True, exist_ok=True)
        self._pack_lock = threading.Lock()  # une seule ouverture à la fois
        self._write_lock = threading.Lock()  # une seule écriture à la fois : jamais deux clics simultanés
        self._fusion = None  # le lot de fusions en cours (ou le dernier), voir fusion_start()
        self._fusion_halt = threading.Event()
        self._actions = JsonStore(self._dir / "actions.json", [])  # journal local de ce que tu as fait depuis l'appli
        self._seen_ts = None  # horodatage du dernier paquet ouvert, à acquitter via pack_seen()
        self._seen_genre = "normal"  # normal | or
        self._names = {}  # noms de raretés (state.info.names), remplis par load_me()
        self._me = {}  # profil sans données sensibles, mis en cache avec la collection
        self._cache_file = self._dir / "collection_cache.json"
        self._info = {}  # chiffres de jeu (state.info), remplis par load_me()
        self._prefs = JsonStore(self._dir / "prefs.json", {})
        self._packs = JsonStore(self._dir / "packs_history.json", [])  # journal local des paquets ouverts ici
        self._watch = JsonStore(self._dir / "watch.json", [])  # cartes surveillées : [{cid, name}]
        # journal de diagnostic du flux : noms d'événements et de champs seulement, jamais de valeurs
        self._live = LiveStream(self._client, lambda: self._me.get("id"), self._dir / "stream_debug.log")
        self._live.watch_cids = frozenset(w["cid"] for w in self._clean_watch(self._watch.read()))

    # ---- session : la connexion elle-même est propre à chaque plateforme (fenêtre du site au bureau, identifiants au serveur) ----
    def ensure_me(self):
        """Le profil est chargé (le flux temps réel en a besoin pour savoir ce qui te concerne) : un seul appel, une seule fois."""
        if not self._me.get("id"):
            return self.load_me()
        return {"ok": True}

    def logout(self):
        self._live.stop()
        self._fusion_halt.set()
        self._client.clear_session()
        try:  # la collection en cache appartient au compte qui se déconnecte
            self._cache_file.unlink()
        except OSError:
            pass
        return {"ok": True}

    # ---- données -------------------------------------------------------
    def _guard(self, fn):
        """Exécute fn() et convertit toute erreur en dict {ok: False, ...} : rien ne traverse pywebview."""
        try:
            return fn()
        except SessionExpired as e:
            self._client.clear_session()
            return {"ok": False, "expired": True, "error": str(e)}
        except ApiError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"Erreur inattendue : {e.__class__.__name__}: {e}"}

    def _state(self):
        state = self._client.state() or {}
        me = state.get("me")
        if not (isinstance(me, dict) and me.get("id")):
            raise SessionExpired("Session expirée, reconnecte-toi.")
        return state, me

    def cache_get(self):
        """Dernière collection connue : affichage instantané au démarrage (jamais sans session)."""
        if not self._client.cookies_dict():
            self._client.load_session()
        if not self._client.cookies_dict():
            return {"ok": False}
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"ok": False}
        return {"ok": True, "data": data} if isinstance(data, dict) and data.get("cards") else {"ok": False}

    def load_me(self):
        """Profil + noms de raretés : un seul appel `state`, rapide. Sert aussi au minuteur de paquets."""
        def run():
            state, me = self._state()
            self._names = (state.get("info") or {}).get("names") or {}
            self._me = safe_me(me, None)
            self._info = safe_info(state.get("info") or {})
            rewards = parse_rewards_state(me)  # quêtes, bienvenue, série de connexion, tchat de guilde : déjà dans `state`
            if rewards["guild_chat"]:
                self._live.guild_id = rewards["guild_chat"]["guild"]  # le flux ne transmet que les nouvelles de SA guilde
            return {"ok": True, "me": self._me, "names": self._names, "info": self._info, "rewards": rewards}
        return self._guard(run)

    def load_collection(self):
        """Collection décodée + stats ; le résultat est aussi écrit en cache pour le prochain démarrage."""
        def run():
            parsed = parse_collection(self._client.collection())
            out = {
                "rank": parsed["rank"],
                "tags": parsed["tags"],
                "cards": parsed["cards"],
                "stats": compute_stats(parsed["cards"], self._names),
            }
            try:  # écriture atomique ; un échec de cache ne doit jamais faire échouer le chargement
                tmp = self._cache_file.with_suffix(".tmp")
                tmp.write_text(json.dumps({**out, "me": self._me, "names": self._names}, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self._cache_file)
            except OSError:
                pass
            return {"ok": True, **out}
        return self._guard(run)

    # ---- paquets (écriture : un clic = un paquet) -----------------------
    def pack_challenge(self):
        """La question « es-tu un robot ? » du site, à montrer au joueur : c'est lui qui répond, l'appli ne devine jamais."""
        def run():
            q = parse_pack_challenge(self._client.pack_challenge())
            if not q:
                raise ApiError("Le site n'a pas envoyé de question lisible : réessaie, ou ouvre ce paquet sur wiki-pick.com.")
            return {"ok": True, "challenge": q}
        return self._guard(run)

    def open_pack(self, defi_id=None, rep=None):
        """Un clic = un paquet. Quand le site demande une vérification (`me.defi`), il faut la réponse que le joueur
        vient de cliquer (defi_id, rep) ; sans elle, on renvoie `challenge: True` pour que l'interface pose la question."""
        if not self._pack_lock.acquire(blocking=False):
            return {"ok": False, "error": "Une ouverture est déjà en cours."}

        def run():
            _, me = self._state()
            if (me.get("packs") or 0) < 1:
                return {"ok": False, "error": "Plus de paquet en réserve : le prochain arrive bientôt."}
            proof = None
            if me.get("defi"):
                if defi_id is None:
                    return {"ok": False, "challenge": True, "error": "Le site demande une petite vérification avant ce paquet."}
                if not (isinstance(defi_id, str) and 0 < len(defi_id) <= 64 and defi_id.replace("-", "").replace("_", "").isalnum()):
                    raise ApiError("Vérification invalide : recommence.")
                proof = {"defi": defi_id, "rep": _num(rep, "Réponse", 0, 11)}
            d = self._client.open_pack(proof) or {}
            self._seen_ts = ((d.get("me") or {}).get("revoirTs") or {}).get("normal")
            self._seen_genre = "normal"
            cards = [expand_pack_card(c) for c in d.get("cards") or [] if isinstance(c, dict)]
            self._record_pack(cards)
            return {"ok": True, "cards": cards, "me": safe_me(d.get("me") or me, None)}
        try:
            out = self._guard(run)
            self._log_action("Paquet ouvert", out)
            return out
        finally:
            self._pack_lock.release()

    def open_gold_pack(self):
        """Paquet doré (offert, ou PRO du jour) : seulement quand le profil l'indique, comme le site. Un clic = un paquet."""
        if not self._pack_lock.acquire(blocking=False):
            return {"ok": False, "error": "Une ouverture est déjà en cours."}

        def run():
            _, me = self._state()
            if not (me.get("proPack") or me.get("paquetOr")):
                return {"ok": False, "error": "Aucun paquet doré disponible pour le moment."}
            d = self._client.open_gold_pack() or {}
            self._seen_ts = ((d.get("me") or {}).get("revoirTs") or {}).get("or")
            self._seen_genre = "or"
            cards = [expand_pack_card(c) for c in d.get("cards") or [] if isinstance(c, dict)]
            self._record_pack(cards, gold=True)
            return {"ok": True, "cards": cards, "me": safe_me(d.get("me") or me, None)}
        try:
            out = self._guard(run)
            self._log_action("Paquet doré ouvert", out)
            return out
        finally:
            self._pack_lock.release()

    def _record_pack(self, cards, gold=False):
        hist = self._packs.read()
        keep = ("cid", "name", "rarity", "reads", "img", "shiny", "new")
        hist.append({"ts": time.time(), "gold": gold, "cards": [{k: c[k] for k in keep} for c in cards]})
        self._packs.write(hist[-PACK_HISTORY_MAX:])

    def pack_history(self):
        """Journal des paquets ouverts avec cette appli (le site ne garde que le dernier), le plus récent d'abord."""
        return {"ok": True, "packs": list(reversed(self._packs.read()))}

    def prefs_get(self):
        return {"ok": True, "prefs": self._prefs.read()}

    def prefs_set(self, key, value):
        if not ((key in PREF_BOOLS and isinstance(value, bool)) or (key in PREF_CHOICES and value in PREF_CHOICES[key])):
            return {"ok": False, "error": "Préférence inconnue."}
        prefs = self._prefs.read()
        prefs[key] = value
        self._prefs.write(prefs)
        return {"ok": True}

    @staticmethod
    def _clean_watch(items):
        out = []
        for w in items if isinstance(items, list) else []:
            if isinstance(w, dict) and isinstance(w.get("cid"), str) and isinstance(w.get("name"), str) and ":" in w["cid"]:
                out.append({"cid": w["cid"][:300], "name": w["name"][:200]})
        return out[:WATCH_MAX]

    def watch_get(self):
        return {"ok": True, "list": self._clean_watch(self._watch.read())}

    def watch_set(self, cid, name, on):
        """Surveiller (ou non) une carte : tu es prévenu quand elle est mise aux enchères. Liste locale, rien n'est écrit sur le site."""
        if not (isinstance(cid, str) and 2 < len(cid) <= 300 and cid.split(":", 1)[0].isalpha() and ":" in cid):
            return {"ok": False, "error": "Carte inconnue."}
        items = [w for w in self._clean_watch(self._watch.read()) if w["cid"] != cid]
        if on:
            if len(items) >= WATCH_MAX:
                return {"ok": False, "error": f"Tu surveilles déjà {WATCH_MAX} cartes : retires-en une d'abord."}
            items.append({"cid": cid, "name": str(name or cid.split(":", 1)[1].replace("_", " "))[:200]})
        self._watch.write(items)
        self._live.watch_cids = frozenset(w["cid"] for w in items)
        return {"ok": True, "list": items}

    def pack_seen(self):
        """À appeler quand les cartes sont à l'écran (comme le fait le site). Sans erreur bloquante."""
        ts, self._seen_ts = self._seen_ts, None
        if ts:
            try:
                self._client.pack_seen(ts, self._seen_genre)
            except Exception:
                return {"ok": False}
        return {"ok": True}

    # ---- temps réel (lecture seule) -------------------------------------
    def start_stream(self):
        self._live.start()
        return {"ok": True}

    def stop_stream(self):
        self._live.stop()
        return {"ok": True}

    def stream_watch_market(self, on):
        self._live.watch_market = bool(on)
        return {"ok": True}

    def poll_events(self):
        """Appelé chaque seconde par l'interface : appel local, aucun trafic réseau."""
        return {"ok": True, "state": self._live.state, "events": self._live.poll()}

    def load_notifications(self):
        def run():
            d = self._client.notifications() or {}
            return {
                "ok": True,
                "items": [parse_notification(n) for n in d.get("items") or [] if isinstance(n, dict)],
                "unread": int(d.get("unread") or 0),
                "now": d.get("now"),
            }
        return self._guard(run)

    def read_notifications(self):
        """Marque tout comme lu, comme quand on ouvre la cloche sur le site (action manuelle)."""
        def run():
            self._client.mark_notifications_read()
            return {"ok": True}
        return self._guard(run)

    def load_market(self, scope="live", page=0, q="", rarities=None, tri="fin", kind=""):
        """scope : live (le marché), mine (en vente), bidding (mes mises), purchases (achetées), ventes (vendues).
        Valeurs de tri et de type : celles du site."""
        def run():
            if scope in ("purchases", "ventes"):  # historique : pages de `more` en `more`, sans filtre côté site
                p = max(0, int(page or 0))
                d = self._client.history(scope, p) or {}
                return {
                    "ok": True, "history": True,
                    "items": [parse_history(a) for a in d.get("items") or [] if isinstance(a, dict)],
                    "page": p, "pages": p + 2 if d.get("more") else p + 1, "total": int(d.get("n") or 0),
                    "sum": int(d.get("somme") or 0), "now": d.get("now"),
                }
            codes = [r for r in (rarities or []) if isinstance(r, str) and r.isalnum() and len(r) <= 12][:10]
            sc = scope if scope in ("live", "mine", "bidding") else "live"
            order = tri if tri in ("fin", "rarete", "prixbas", "prix", "mises") else "fin"
            t = kind if kind in ("", "cartes", "lots") else ""
            d = self._client.auctions(sc, max(0, int(page or 0)), str(q or "")[:100], codes, order, t) or {}
            return {
                "ok": True,
                "items": [parse_auction(a) for a in d.get("items") or [] if isinstance(a, dict)],
                "page": int(d.get("page") or 0), "pages": int(d.get("pages") or 1), "total": int(d.get("total") or 0),
                "now": d.get("now"),
            }
        return self._guard(run)

    def export_collection(self):
        """Écrit ta collection (celle du dernier chargement) en CSV dans le dossier Téléchargements. Rien n'est envoyé."""
        def run():
            cached = self.cache_get()
            if not cached.get("ok"):
                return {"ok": False, "error": "Aucune collection chargée : actualise d'abord."}
            home = Path(os.environ.get("USERPROFILE") or Path.home())
            folder = home / "Downloads" if (home / "Downloads").is_dir() else home
            dest = folder / f"wikipick-collection-{time.strftime('%Y-%m-%d')}.csv"
            dest.write_text(collection_csv(cached["data"]["cards"], cached["data"].get("names")), encoding="utf-8-sig")  # BOM : Excel lit les accents
            return {"ok": True, "path": str(dest), "count": len(cached["data"]["cards"])}
        return self._guard(run)

    # ---- écritures MANUELLES : un clic = une action, validées ici, jamais en boucle, jamais rejouées automatiquement ----
    def _log_action(self, label, out):
        log = self._actions.read()
        ok = bool(out.get("ok"))
        log.append({"ts": time.time(), "action": str(label)[:160], "ok": ok, "error": None if ok else str(out.get("error") or "")[:200]})
        self._actions.write(log[-ACTIONS_MAX:])

    def _write(self, label, fn):
        """Une écriture à la fois (un deuxième clic pendant la première est refusé), journalisée localement, jamais rejouée."""
        if not self._write_lock.acquire(blocking=False):
            return {"ok": False, "error": "Une action est déjà en cours."}
        try:
            out = self._guard(fn)
        finally:
            self._write_lock.release()
        self._log_action(label, out)
        return out

    def actions_get(self):
        return {"ok": True, "actions": list(reversed(self._actions.read()))}

    def auction_get(self, auction_id):
        def run():
            d = self._client.auction(_num(auction_id, "Enchère")) or {}
            return {"ok": True, "auction": parse_auction(d.get("auction") or {})}
        return self._guard(run)

    def bid(self, auction_id, amount):
        def run():
            r = self._client.bid(_num(auction_id, "Enchère"), _num(amount, "Montant", 1, 9_999_999)) or {}
            try:
                ends = float(r.get("endsAt") or 0)
            except (TypeError, ValueError):
                ends = 0.0
            return {"ok": True, "extended": bool(r.get("extended")), "ends_at": ends}
        return self._write(f"Mise de {str(amount)[:12]} Wikiki sur l'enchère {str(auction_id)[:12]}", run)

    def auction_create(self, card_id, start_price, duration):
        def run():
            if duration not in AUCTION_DURATIONS:
                raise ApiError("Durée invalide.")
            self._client.auction_create(_num(card_id, "Carte"), _num(start_price, "Mise de départ", 1, 9_999_999), duration)
            return {"ok": True}
        return self._write(f"Enchère lancée : carte {str(card_id)[:12]}, départ {str(start_price)[:12]} Wikiki, {str(duration)[:4]}", run)

    def auction_cancel(self, auction_id):
        def run():
            self._client.auction_cancel(_num(auction_id, "Enchère"))
            return {"ok": True}
        return self._write(f"Enchère {str(auction_id)[:12]} annulée", run)

    def auction_price(self, auction_id, start_price):
        def run():
            self._client.auction_price(_num(auction_id, "Enchère"), _num(start_price, "Mise de départ", 1, 9_999_999))
            return {"ok": True}
        return self._write(f"Mise de départ de l'enchère {str(auction_id)[:12]} : {str(start_price)[:12]} Wikiki", run)

    def trade_action(self, action, trade_id):
        """Accepter, refuser ou annuler un échange (les seules actions possibles sur un échange existant)."""
        def run():
            if action not in ("accept", "decline", "cancel"):
                raise ApiError("Action inconnue.")
            self._client.trade_action(action, _num(trade_id, "Échange"))
            return {"ok": True}
        return self._write(f"Échange {str(trade_id)[:12]} : {str(action)[:8]}", run)

    def trade_send(self, to, give, take, give_coins=0, take_coins=0, message="", counter_of=None):
        def run():
            name = str(to or "").strip()
            if not name or len(name) > 100:
                raise ApiError("Joueur invalide.")
            g, t = _ids(give, "Cartes données", 10), _ids(take, "Cartes reçues", 10)
            gc, tc = _num(give_coins, "Wikiki offerts", 0), _num(take_coins, "Wikiki demandés", 0)
            if not (g or t or gc or tc):
                raise ApiError("L'échange est vide.")
            body = {"to": name, "give": g, "take": t, "give_coins": gc, "take_coins": tc, "message": str(message or "")[:200]}
            if counter_of is not None:
                body["trade_id"] = _num(counter_of, "Échange")
            self._client.trade_send(body, counter=counter_of is not None)
            return {"ok": True}
        kind = "Contre-proposition" if counter_of is not None else "Proposition d'échange"
        return self._write(f"{kind} à {str(to)[:40]}", run)

    def recycle(self, card_ids):
        """Recycle des exemplaires précis (au plus 100 à la fois) contre des Wikiki. Le site garde une corbeille de 20 minutes."""
        def run():
            ids = _ids(card_ids, "Cartes", 100)
            if not ids:
                raise ApiError("Aucune carte à recycler.")
            if len(ids) == 1:
                d = self._client.bank(ids[0]) or {}
                return {"ok": True, "gain": _num(d.get("gain") or 0, "Gain", 0), "sold": 1, "locked": 0}
            d = self._client.bank_bulk(ids) or {}
            sold = d.get("sold")
            return {"ok": True, "gain": _num(d.get("gain") or 0, "Gain", 0), "sold": _num(len(ids) if sold is None else sold, "Ventes", 0),
                    "locked": _num(d.get("locked") or 0, "Verrouillées", 0)}
        return self._write(f"Recyclage de {len(card_ids) if isinstance(card_ids, list) else '?'} carte(s)", run)

    # ---- fusion : 2 ou 3 cartes du même rang -> une carte du rang au-dessus, ou tout est perdu ----
    def fusion_get(self, rank=None, page=0):
        """L'atelier. Sans rang : le plus bas où l'on peut tenter une fusion (comme le site)."""
        def run():
            if rank is not None and rank not in FUSION_RANKS:
                raise ApiError("Rang invalide.")
            d = parse_fusion(self._client.fusion(rank, _num(page, "Page", 0, 100000)) or {})
            if rank is None and d["recipes"]:
                best = next((x for x in d["recipes"] if x["avail"] >= d["small"]), d["recipes"][0])
                d = parse_fusion(self._client.fusion(best["rank"], 0) or {})
            return {"ok": True, **d}
        return self._guard(run)

    @staticmethod
    def _fusion_result(r, sent):
        """Lit la réponse d'une fusion SANS jamais lever d'erreur de forme : la fusion a déjà eu lieu, il faut en rendre compte."""
        card = expand_pack_card(r["carte"]) if r.get("reussie") is True and isinstance(r.get("carte"), dict) else None
        parts = [i for i in r.get("parties") or [] if isinstance(i, int) and not isinstance(i, bool)] or list(sent)
        me = r.get("me")
        return {"success": r.get("reussie") is True, "rank": r.get("rang"), "to": r.get("vers"), "chance": _to_int(r.get("chance")),
                "next_chance": _to_int(r.get("prochaine")), "used": parts, "card": card, "me": safe_me(me, None) if isinstance(me, dict) else None}

    def fusion_do(self, ids, page=0):
        """UNE fusion à la main. Elle peut rater : les cartes posées sont alors perdues (la confirmation se fait dans l'interface)."""
        def run():
            sent = _fusion_ids(ids)
            r = self._client.fusion_do(sent, _num(page, "Page", 0, 100000)) or {}
            if not isinstance(r.get("reussie"), bool):
                raise ApiError("Réponse inattendue du site : vérifie ta collection avant de réessayer.")
            return {"ok": True, **self._fusion_result(r, sent), "state": parse_fusion(r.get("etat"))}
        return self._write(f"Fusion de {len(ids) if isinstance(ids, list) else '?'} cartes", run)

    def fusion_start(self, rank, count, size=3, dups_only=True):
        """Lot de fusions : jusqu'à `count` cartes d'un rang, `size` par fusion, une fusion à la fois, au plus une par seconde.
        Lancé et confirmé par le joueur ; il s'arrête à l'objectif, s'il n'y a plus de cartes éligibles, à la moindre erreur
        (jamais de nouvel essai), sur fusion_stop(), ou si l'interface ne vient plus voir (FUSION_DEADMAN). Pendant le lot,
        aucune autre écriture n'est possible. `dups_only` : n'utilise que des doublons (il reste toujours un exemplaire)."""
        if rank not in FUSION_RANKS:
            return {"ok": False, "error": "Rang invalide."}
        try:
            size = _num(size, "Cartes par fusion", 2, 3)
            count = _num(count, "Nombre de cartes", size, FUSION_MAX_CARDS)
        except ApiError as e:
            return {"ok": False, "error": str(e)}
        if not isinstance(dups_only, bool):
            return {"ok": False, "error": "Option invalide."}
        if not self._write_lock.acquire(blocking=False):
            return {"ok": False, "error": "Une action est déjà en cours."}
        goal = count // size
        job = {"running": True, "rank": rank, "to": None, "size": size, "dups_only": dups_only, "goal": goal, "fusions": 0, "won": 0, "lost": 0,
               "used": 0, "new": 0, "last": None, "chance": None, "left": None, "reason": None, "error": None, "me": None, "poll": time.monotonic()}
        self._log_action(f"Fusion automatique lancée : {rank}, {goal} fusion(s) de {size} cartes" + (" (doublons seulement)" if dups_only else ""), {"ok": True})
        self._fusion = job
        self._fusion_halt.clear()
        try:
            threading.Thread(target=self._fusion_run, args=(job,), daemon=True).start()
        except Exception:
            job["running"] = False
            self._write_lock.release()
            return {"ok": False, "error": "Impossible de lancer le lot."}
        return self.fusion_job()

    def _fusion_run(self, job):
        reason, error = "done", None
        try:
            d = parse_fusion(self._client.fusion(job["rank"], 0) or {})
            while job["fusions"] < job["goal"]:
                if self._fusion_halt.is_set():
                    reason = "stopped"
                    break
                if time.monotonic() - job["poll"] > FUSION_DEADMAN:
                    reason = "away"
                    break
                recipe = next((x for x in d["recipes"] if x["rank"] == job["rank"]), None)
                job["to"] = recipe["to"] if recipe else job["to"]
                job["left"] = recipe["avail"] if recipe else None
                picks = [c for c in d["cards"] if c["copies"] > 1 or not job["dups_only"]][:job["size"]]
                if len(picks) < job["size"]:
                    reason = "empty"
                    break
                sent = [c["id"] for c in picks]
                r = self._client.fusion_do(sent, 0) or {}
                if not isinstance(r.get("reussie"), bool):
                    raise ApiError("Réponse inattendue du site : le lot est arrêté, vérifie ta collection.")
                res = self._fusion_result(r, sent)
                job["fusions"] += 1
                job["used"] += len(res["used"])
                job["won" if res["success"] else "lost"] += 1
                job["chance"] = res["next_chance"]
                job["me"] = res["me"] or job["me"]
                if res["card"]:
                    job["new"] += 1 if res["card"]["new"] else 0
                    job["last"] = {k: res["card"][k] for k in ("cid", "name", "img", "rarity", "new")}
                d = parse_fusion(r["etat"]) if isinstance(r.get("etat"), dict) else parse_fusion(self._client.fusion(job["rank"], 0) or {})
                if job["fusions"] < job["goal"] and self._fusion_halt.wait(FUSION_PAUSE):
                    reason = "stopped"
                    break
        except SessionExpired as e:
            self._client.clear_session()
            reason, error = "error", str(e)
        except ApiError as e:
            reason, error = "error", str(e)
        except Exception as e:  # rien ne doit tuer le fil sans le dire
            reason, error = "error", f"Erreur inattendue : {e.__class__.__name__}: {e}"
        finally:  # « terminé » n'est annoncé qu'une fois le journal écrit et le verrou libéré
            job["reason"], job["error"] = reason, error
            try:
                self._log_action(f"Fusion automatique terminée ({reason}) : {job['fusions']} fusion(s), {job['won']} réussie(s), {job['lost']} ratée(s), "
                                 f"{job['used']} cartes consommées", {"ok": reason != "error", "error": error})
            finally:
                self._write_lock.release()
                job["running"] = False

    def fusion_job(self):
        """Où en est le lot (ou le dernier). L'interface doit le demander régulièrement : c'est ce qui le garde en vie."""
        job = self._fusion
        if job is None:
            return {"ok": True, "job": None}
        job["poll"] = time.monotonic()
        return {"ok": True, "job": {k: v for k, v in job.items() if k != "poll"}}

    def fusion_stop(self):
        self._fusion_halt.set()
        return {"ok": True}

    def corbeille_get(self):
        return self._guard(lambda: {"ok": True, **parse_corbeille(self._client.corbeille() or {})})

    def corbeille_restore(self, ids=None, everything=False):
        def run():
            body = {"tout": True} if everything is True else {"ids": _ids(ids, "Cartes", 100)}
            if "ids" in body and not body["ids"]:
                raise ApiError("Aucune carte à récupérer.")
            d = self._client.corbeille_restore(body) or {}
            return {"ok": True, "restored": _num(d.get("restaurees") or 0, "Cartes", 0), "cost": _num(d.get("cout") or 0, "Coût", 0)}
        return self._write("Corbeille : récupération" + (" de tout" if everything is True else ""), run)

    def corbeille_empty(self):
        def run():
            d = self._client.corbeille_empty() or {}
            return {"ok": True, "erased": _num(d.get("videes") or 0, "Cartes", 0)}
        return self._write("Corbeille vidée", run)

    def card_lock(self, card_id, cid, shiny, on):
        def run():
            r = self._client.card_lock(_num(card_id, "Carte"), _cid(cid), bool(shiny), on is True) or {}
            return {"ok": True, "locked": bool(r.get("locked"))}
        return self._write(f"Carte {str(card_id)[:12]} : {'verrouillée' if on is True else 'déverrouillée'}", run)

    def card_for_sale(self, card_id, on):
        def run():
            r = self._client.card_for_sale(_num(card_id, "Carte"), on is True) or {}
            return {"ok": True, "n": _num(r.get("n") or 0, "Nombre", 0)}
        return self._write(f"Carte {str(card_id)[:12]} : {'mise de côté' if on is True else 'remise dans la collection'}", run)

    def wish_set(self, cid, on, card):
        """Liste de souhaits du site (le site te prévient quand la carte passe aux enchères)."""
        def run():
            c = card if isinstance(card, dict) else {}
            site_card = {"cid": _cid(cid), "n": str(c.get("name") or "")[:200], "d": str(c.get("desc") or "")[:300],
                         "img": _safe_img(c.get("img")), "r": str(c.get("rarity") or "")[:12], "lang": str(c.get("lang") or "")[:12]}
            r = self._client.wish(cid, on is True, site_card) or {}
            return {"ok": True, "wished": bool(r.get("wished"))}
        return self._write(f"Souhait {'ajouté' if on is True else 'retiré'} : {str(cid)[:80]}", run)

    def friends_get(self):
        return self._guard(lambda: {"ok": True, **parse_friends(self._client.friends() or {})})

    def user_cards(self, name):
        def run():
            n = str(name or "").strip()
            if not n or len(n) > 100:
                raise ApiError("Joueur invalide.")
            return {"ok": True, "groups": parse_user_cards(self._client.user_cards(n) or {})}
        return self._guard(run)

    def pro_market(self, cid, rarity, shiny):
        """Historique des prix : fonction WIKI-PRO. Rien n'est demandé au site si ton profil n'est pas abonné."""
        def run():
            if not self._me.get("pro"):
                return {"ok": False, "error": "Réservé aux abonnés WIKI-PRO."}
            r = str(rarity or "")
            if not r.isalnum() or len(r) > 12:
                raise ApiError("Rareté invalide.")
            return {"ok": True, **parse_pro_market(self._client.pro_market(_cid(cid), r, bool(shiny)) or {})}
        return self._guard(run)

    # ---- arène : combats à deux ----
    def combat_info(self):
        return self._guard(lambda: {"ok": True, **parse_combat_info(self._client.combat() or {})})

    def combat_state(self):
        """Un défi en cours (rafraîchissement de la page, retour dans l'appli) : on retrouve sa place."""
        return self._guard(lambda: {"ok": True, "defi": parse_defi((self._client.combat_state() or {}).get("defi"))})

    def combat_decks(self):
        return self._guard(lambda: {"ok": True, "decks": parse_decks(self._client.combat_decks() or {})})

    def combat_deck_save(self, deck_id, name, cards):
        def run():
            n = str(name or "").strip()
            if not n or len(n) > 30:
                raise ApiError("Donne un nom à ton deck (30 caractères au plus).")
            r = self._client.combat_deck_save(_num(deck_id, "Deck", 0), n, _ids(cards, "Cartes", 10)) or {}
            return {"ok": True, "decks": parse_decks(r)}
        return self._write(f"Arène : deck « {str(name)[:30]} » enregistré", run)

    def combat_deck_delete(self, deck_id):
        def run():
            return {"ok": True, "decks": parse_decks(self._client.combat_deck_delete(_num(deck_id, "Deck")) or {})}
        return self._write(f"Arène : deck {str(deck_id)[:12]} supprimé", run)

    def combat_challenge(self, name):
        def run():
            n = str(name or "").strip()
            if not n or len(n) > 100:
                raise ApiError("Joueur invalide.")
            return {"ok": True, "defi": parse_defi(self._client.combat_challenge(n))}
        return self._write(f"Arène : défi lancé à {str(name)[:40]}", run)

    def combat_answer(self, defi_id, ok):
        def run():
            r = self._client.combat_answer(_num(defi_id, "Défi"), ok is True)
            return {"ok": True, "defi": parse_defi(r) if ok is True else None}
        return self._write(f"Arène : invitation {'acceptée' if ok is True else 'refusée'}", run)

    def combat_choice(self, defi_id, cards):
        """Les cartes que tu poses, montrées en direct à l'adversaire pendant que tu choisis (pas de journal : c'est un geste continu)."""
        def run():
            self._client.combat_choice(_num(defi_id, "Défi"), _ids(cards, "Cartes", 10))
            return {"ok": True}
        return self._guard(run)

    def combat_team(self, defi_id, cards):
        """Valide ton équipe : soit l'autre n'est pas prêt (attente), soit le combat part et son détail revient."""
        def run():
            r = self._client.combat_team(_num(defi_id, "Défi"), _ids(cards, "Cartes", 10)) or {}
            if r.get("attente"):
                return {"ok": True, "waiting": True, "duel": None}
            return {"ok": True, "waiting": False, "duel": parse_duel(r)}
        return self._write("Arène : équipe validée", run)

    def combat_cancel(self, defi_id):
        def run():
            self._client.combat_cancel(_num(defi_id, "Défi"))
            return {"ok": True}
        return self._write("Arène : défi annulé", run)

    def combat_chest(self):
        return self._write("Arène : Mini-Pack ouvert", lambda: {"ok": True, **parse_chest(self._client.combat_chest() or {})})

    def users_search(self, q):
        def run():
            s = str(q or "").strip()
            if not s or len(s) > 50:
                return {"ok": True, "users": []}
            return {"ok": True, "users": parse_users(self._client.users(s) or {})}
        return self._guard(run)

    def load_card(self, cid):
        """Fiche détaillée d'une carte, à l'ouverture de sa fiche (un appel, comme sur le site)."""
        def run():
            if not (isinstance(cid, str) and 2 < len(cid) <= 300 and ":" in cid):
                return {"ok": False, "error": "Carte inconnue."}
            return {"ok": True, **parse_card_sheet(self._client.card(cid) or {})}
        return self._guard(run)

    def load_trades(self, box="received"):
        """Échanges entre amis, en lecture seule : received | sent | history."""
        def run():
            b = box if box in ("received", "sent", "history") else "received"
            d = self._client.trades(b) or {}
            return {"ok": True, "trades": [parse_trade(t) for t in d.get("trades") or [] if isinstance(t, dict)], "now": d.get("now")}
        return self._guard(run)

    def load_ranking(self, period="tout"):
        def run():
            p = period if period in ("semaine", "mois", "tout") else "tout"
            return {"ok": True, **parse_ranking(self._client.ranking(p) or {})}
        return self._guard(run)

    # ---- social : messagerie, amis, profils, guilde. Lectures comme le site ; écritures sur clic, une à la fois ----
    @staticmethod
    def _name(v):
        n = str(v or "").strip()
        if not n or len(n) > 100:
            raise ApiError("Joueur invalide.")
        return n

    @staticmethod
    def _text(v, limit):
        t = str(v or "").strip()
        if not t:
            raise ApiError("Le message est vide.")
        if len(t) > limit:
            raise ApiError(f"{limit} caractères au plus.")
        return t

    def conversations_get(self):
        return self._guard(lambda: {"ok": True, "conversations": parse_conversations(self._client.conversations() or {})})

    def thread_get(self, name):
        return self._guard(lambda: {"ok": True, "thread": parse_thread(self._client.thread(self._name(name)) or {})})

    def message_send(self, to, text):
        def run():
            self._client.message_send(self._name(to), self._text(text, 1000))
            return {"ok": True}
        return self._write(f"Message envoyé à {str(to)[:40]}", run)  # le texte du message n'est jamais journalisé

    def friends_list(self):
        return self._guard(lambda: {"ok": True, **parse_friend_lists(self._client.friends() or {})})

    def players_search(self, q):
        def run():
            s = str(q or "").strip()
            return {"ok": True, "users": parse_user_search(self._client.users(s) or {}) if 0 < len(s) <= 50 else []}
        return self._guard(run)

    _FRIEND_ACTIONS = {"request": "demande d'ami envoyée", "accept": "demande acceptée", "decline": "demande refusée",
                       "remove": "retiré(e) des amis", "block": "bloqué(e)", "unblock": "débloqué(e)"}

    def friend_action(self, action, name):
        def run():
            if action not in self._FRIEND_ACTIONS:
                raise ApiError("Action inconnue.")
            r = self._client.friend_action(action, self._name(name)) or {}
            rel = r.get("relation") if isinstance(r, dict) else None
            return {"ok": True, "relation": rel if rel in ("friends", "incoming", "outgoing") else ""}
        return self._write(f"{str(name)[:40]} : {self._FRIEND_ACTIONS.get(action, '?')}", run)

    def friend_favorite(self, name, on):
        def run():
            self._client.friend_favorite(self._name(name), on is True)
            return {"ok": True}
        return self._write(f"{str(name)[:40]} : {'mis en favori' if on is True else 'retiré des favoris'}", run)

    def profile_get(self, name=None):
        return self._guard(lambda: {"ok": True, "profile": parse_profile(self._client.profile(self._name(name) if name else None) or {})})

    def player_cards(self, name, page=0, q="", rarities=None, order=""):
        def run():
            codes = ",".join(r for r in (rarities or []) if isinstance(r, str) and r.isalnum() and len(r) <= 12)
            d = self._client.player_cards(self._name(name), _num(page, "Page", 0, 100000), str(q or "")[:100], codes, "asc" if order == "asc" else "")
            return {"ok": True, **parse_player_cards(d or {})}
        return self._guard(run)

    def guilds_get(self):
        def run():
            g = parse_guilds(self._client.guilds() or {})
            self._live.guild_id = g["mine"]
            return {"ok": True, **g}
        return self._guard(run)

    def guild_get(self, gid):
        return self._guard(lambda: {"ok": True, "guild": parse_guild(self._client.guild(_num(gid, "Guilde")) or {})})

    def guild_chat_seen(self):
        """Le tchat de ta guilde est à l'écran : le site le note (même geste que `paquet/vu`). Sans erreur bloquante."""
        try:
            self._client.guild_post("chat/vu", {})
        except Exception:
            return {"ok": False}
        return {"ok": True}

    def guild_action(self, action, arg=None, text=None):
        """Une action de guilde, validée ici. arg = id de guilde, pseudo, id de publication ou de commentaire selon l'action ;
        pour `officier`, text = True pour nommer, False pour retirer."""
        def body():
            if action in ("apply", "apply/cancel"):
                return {"id": _num(arg, "Guilde")}
            if action in ("apply/accept", "apply/decline", "kick"):
                return {"name": self._name(arg)}
            if action == "officier":
                return {"name": self._name(arg), "on": text is True}
            if action == "leave":
                return {}
            if action == "chat":
                return {"text": self._text(text, 400)}
            if action == "comment":
                return {"feed_id": _num(arg, "Publication"), "text": self._text(text, 400)}
            if action == "like":
                return {"feed_id": _num(arg, "Publication")}
            if action == "comment/delete":
                return {"comment_id": _num(arg, "Commentaire")}
            if action == "create":
                f = arg if isinstance(arg, dict) else {}
                name, tag, descr = str(f.get("name") or "").strip(), str(f.get("tag") or "").strip().upper(), str(f.get("descr") or "").strip()
                if not 2 <= len(name) <= 30 or not (2 <= len(tag) <= 5 and tag.isalnum()) or len(descr) > 200:
                    raise ApiError("Nom (2 à 30 caractères) et blason (2 à 5 lettres ou chiffres) obligatoires.")
                return {"name": name, "tag": tag, "descr": descr}
            raise ApiError("Action inconnue.")

        def run():
            r = self._client.guild_post(action, body()) or {}
            out = {"ok": True}
            if action == "like":
                out["liked"] = r.get("liked") is True or r.get("liked") == 1
            if action == "leave":
                out["dissolved"] = r.get("result") == "deleted"
                self._live.guild_id = None
            return out
        label = {"chat": "message dans le tchat", "comment": "commentaire", "like": "j'aime"}.get(action, str(action)[:20])
        shown = arg if isinstance(arg, (int, str)) and action not in ("comment", "like", "comment/delete") else None
        return self._write(f"Guilde : {label}" + (f" ({str(shown)[:40]})" if shown is not None else ""), run)

    # ---- récompenses : quêtes du jour, bienvenue, succès, série de connexion (encaisser ce qui est déjà gagné) ----
    def achievements_get(self):
        return self._guard(lambda: {"ok": True, **parse_achievements(self._client.achievements() or {})})

    def claim(self, kind, key=None):
        """kind : quete (key = 1 ou 2, comme le site) | bienvenue | succes (key = code, ou None pour tout) | serie."""
        def run():
            if kind == "quete":
                body = {"n": _num(key, "Quête", 1, 2)}
            elif kind in ("bienvenue", "succes"):
                if key is None:
                    body = {}
                elif isinstance(key, str) and 0 < len(key) <= 40 and key.replace("_", "").replace("-", "").isalnum():
                    body = {"code": key}
                else:
                    raise ApiError("Récompense inconnue.")
            elif kind == "serie":
                body = {}
            else:
                raise ApiError("Récompense inconnue.")
            return {"ok": True, **parse_claim(self._client.claim(kind, body) or {})}
        names = {"quete": "quête du jour", "bienvenue": "quête de bienvenue", "succes": "succès", "serie": "série de connexion"}
        return self._write(f"Récompense réclamée : {names.get(kind, '?')}" + (f" ({str(key)[:40]})" if key is not None else ""), run)

