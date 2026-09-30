"""Décodage des fonctions sociales et des récompenses : messagerie, amis, profil, guilde, quêtes, série, succès.

Formes lues dans le JS public du site (`social.js`, `core.js`, sept. 2026), jamais observées en vrai : au moindre
écran vide, comparer avec ce JS d'abord. Chaque champ passe par une liste blanche ; les textes écrits par
d'autres joueurs restent des chaînes (l'interface les pose en textContent, jamais en HTML).
"""
import re

from .parse import _to_bool, _to_int, expand_pack_card

BASE = "https://wiki-pick.com"
_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}")


def _s(v, n=200):
    return str(v)[:n] if v is not None else ""


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else _to_int(v)


def _avatar(u):
    """Avatar d'un joueur : chemin du site ou https seulement, et jamais une image marquée sensible (le site la floute)."""
    if not isinstance(u, dict) or u.get("avatarNSFW"):
        return None
    a = u.get("avatar")
    if isinstance(a, str) and a.startswith("/") and not a.startswith("//"):
        return BASE + a
    return a if isinstance(a, str) and a.startswith("https://") else None


def _card(c):
    return expand_pack_card(c) if isinstance(c, dict) else None


def _rows(v, fn, limit=500):
    return [x for x in (fn(i) for i in v[:limit]) if x] if isinstance(v, list) else []


def _dicts(v):
    return v if isinstance(v, dict) else {}


# ---- messagerie ----
def parse_conversations(d):
    """GET /api/conversations -> [{name, avatar, fav, blocked, last, mine, unread, created}]."""
    def conv(c):
        if not isinstance(c, dict) or not c.get("name"):
            return None
        return {"name": _s(c["name"], 100), "avatar": _avatar(c), "fav": _to_bool(c.get("fav")), "blocked": _to_bool(c.get("bloque")),
                "last": _s(c.get("last"), 300), "mine": _to_bool(c.get("mine")), "unread": _to_int(c.get("unread")), "created": _num(c.get("created"))}
    return _rows(_dicts(d).get("conversations"), conv)


def parse_thread(d):
    """GET /api/thread?name= -> {with, avatar, friend, blocked: "moi"|"lui"|"", messages: [{id, mine, text}]}."""
    d = _dicts(d)
    b = d.get("bloque")
    msgs = _rows(d.get("messages"), lambda m: {"id": _to_int(m.get("id")), "mine": _to_bool(m.get("mine")), "text": _s(m.get("text"), 2000)}
                 if isinstance(m, dict) else None, 1000)
    return {"with": _s(d.get("with"), 100), "avatar": _avatar(d), "friend": d.get("relation") == "friends",
            "blocked": b if b in ("moi", "lui") else "", "messages": msgs}


# ---- amis ----
def parse_friend_lists(d):
    """GET /api/friends -> {friends, incoming, outgoing} : [{name, avatar, fav}]."""
    d = _dicts(d)

    def person(u):
        return {"name": _s(u["name"], 100), "avatar": _avatar(u), "fav": _to_bool(u.get("fav"))} if isinstance(u, dict) and u.get("name") else None
    return {k: _rows(d.get(k), person) for k in ("friends", "incoming", "outgoing")}


def parse_user_search(d):
    """GET /api/users?q= -> [{name, avatar, relation, me}] (relation : friends | incoming | outgoing | "")."""
    def user(u):
        if not isinstance(u, dict) or not u.get("name"):
            return None
        rel = u.get("relation")
        return {"name": _s(u["name"], 100), "avatar": _avatar(u), "me": _to_bool(u.get("me")),
                "relation": rel if rel in ("friends", "incoming", "outgoing") else ""}
    return _rows(_dicts(d).get("users"), user, 30)


# ---- profil ----
def parse_profile(d):
    """GET /api/profile[?name=] -> profil d'un joueur (ou le sien), ses vitrines, son rang, sa guilde."""
    d = _dicts(d)
    u, st, so, rk, g = _dicts(d.get("user")), _dicts(_dicts(d.get("user")).get("stats")), _dicts(d.get("social")), d.get("rank"), d.get("guild")
    rel = so.get("relation")
    b = d.get("bloque")
    return {
        "me": _to_bool(d.get("isMe")),
        "blocked": b if b in ("moi", "lui") else "",
        "name": _s(u.get("name"), 100), "avatar": _avatar(u), "created": _num(u.get("created")), "bio": _s(u.get("description"), 500),
        "stats": {k: _to_int(st.get(k)) for k in ("cards", "distinct", "legend", "sales")},
        "relation": rel if rel in ("friends", "incoming", "outgoing", "self") else "",
        "friends": _to_int(so.get("friends")),
        "rank": {k: _to_int(rk.get(k)) for k in ("rank", "total", "points")} if isinstance(rk, dict) else None,
        "guild": {"id": _to_int(g.get("id")), "tag": _s(g.get("tag"), 8), "name": _s(g.get("name"), 60)} if isinstance(g, dict) and g.get("id") else None,
        "showcases": _rows(d.get("showcases"), lambda v: {"id": _to_int(v.get("id")), "name": _s(v.get("name"), 60),
                                                          "cards": _rows(v.get("cards"), _card, 12)} if isinstance(v, dict) else None, 20),
        "slots": _to_int(d.get("slots")) or 5, "max": _to_int(d.get("max")),
        "private_showcases": _to_bool(d.get("vitrinesPrivees")),
    }


def parse_player_cards(d):
    """GET /api/joueur/cartes?name=&page= -> {page, pages, total, cards: [{card, n}]} (collection d'un ami, page par page)."""
    d = _dicts(d)
    rows = _rows(d.get("cards"), lambda x: {"card": _card(x.get("card")), "n": max(1, _to_int(x.get("n"), 1))}
                 if isinstance(x, dict) and isinstance(x.get("card"), dict) else None, 200)
    return {"page": _to_int(d.get("page")), "pages": max(1, _to_int(d.get("pages"), 1)), "total": _to_int(d.get("total")), "cards": rows}


# ---- guilde ----
def _color(v):
    return v if isinstance(v, str) and _COLOR.fullmatch(v) else ""


def parse_guilds(d):
    """GET /api/guilds -> {mine, guilds: [{id, rank, tag, name, color, leader, descr, members, score, applied}]}."""
    d = _dicts(d)
    rows = _rows(d.get("guilds"), lambda g: {
        "id": _to_int(g.get("id")), "rank": _to_int(g.get("rank")), "tag": _s(g.get("tag"), 8), "name": _s(g.get("name"), 60),
        "color": _color(g.get("couleur")), "leader": _s(g.get("leader"), 100), "descr": _s(g.get("descr"), 300),
        "members": _to_int(g.get("members")), "score": _to_int(g.get("score")), "applied": _to_bool(g.get("applied")),
    } if isinstance(g, dict) and g.get("id") else None)
    return {"mine": _to_int(d.get("mine")) or None, "guilds": rows}


def parse_guild(d):
    """GET /api/guild?id= -> la guilde ; le fil et le tchat ne sont envoyés qu'à ses membres."""
    d = _dicts(d)
    member = lambda m: {"name": _s(m.get("name"), 100), "me": _to_bool(m.get("me")), "leader": _to_bool(m.get("leader")),  # noqa: E731
                        "officer": _to_bool(m.get("officier")), "total": _to_int(m.get("total")), "joined": _num(m.get("joined"))} if isinstance(m, dict) and m.get("name") else None
    comment = lambda c: {"id": _to_int(c.get("id")), "name": _s(c.get("name"), 100), "text": _s(c.get("text"), 400), "ts": _num(c.get("ts")),  # noqa: E731
                         "can_delete": _to_bool(c.get("canDelete"))} if isinstance(c, dict) else None
    feed = lambda f: {"id": _to_int(f.get("id")), "name": _s(f.get("name"), 100), "card": _card(f.get("card")), "ts": _num(f.get("ts")),  # noqa: E731
                      "likes": _to_int(f.get("likes")), "liked": _to_bool(f.get("liked")), "points": _to_int(f.get("points")),
                      "comments": _rows(f.get("comments"), comment, 200)} if isinstance(f, dict) and isinstance(f.get("card"), dict) else None
    chat = lambda m: {"id": _to_int(m.get("id")), "uid": _to_int(m.get("uid")), "name": _s(m.get("name"), 100), "text": _s(m.get("text"), 400),  # noqa: E731
                      "ts": _num(m.get("ts"))} if isinstance(m, dict) else None
    return {
        "id": _to_int(d.get("id")), "name": _s(d.get("name"), 60), "tag": _s(d.get("tag"), 8), "descr": _s(d.get("descr"), 300),
        "color": _color(d.get("couleur")), "rank": _to_int(d.get("rank")), "count": _to_int(d.get("count")), "score": _to_int(d.get("score")),
        "leader": _s(d.get("leader"), 100), "max_members": _to_int(d.get("maxMembres")) or 100,
        "is_member": _to_bool(d.get("isMember")), "is_manager": _to_bool(d.get("isGerant")), "is_leader": _to_bool(d.get("isLeader")),
        "applied": _to_bool(d.get("applied")),
        "members": _rows(d.get("members"), member),
        "applications": _rows(d.get("applications"), lambda a: {"name": _s(a.get("name"), 100), "created": _num(a.get("created"))}
                              if isinstance(a, dict) and a.get("name") else None),
        "feed": _rows(d.get("feed"), feed, 200),
        "chat": _rows(d.get("chat"), chat, 200),
    }


# ---- quêtes, bienvenue, série, succès (dans /api/state : me.quete, me.quete2, me.bienvenue, me.serie, me.gchat) ----
def _quest(q):
    if not isinstance(q, dict):
        return None
    return {"title": _s(q.get("titre"), 120), "what": _s(q.get("quoi"), 300), "done": _to_int(q.get("fait")), "goal": max(1, _to_int(q.get("cible"), 1)),
            "finished": _to_bool(q.get("fini")), "claimed": _to_bool(q.get("pris")), "locked": _to_bool(q.get("verrou")),
            "next": _num(q.get("next")), "gain": _to_int(q.get("gain")), "packs": _to_bool(q.get("packs"))}


def _welcome(b):
    if not isinstance(b, dict) or not b.get("code"):
        return None
    return {"code": _s(b["code"], 40), "title": _s(b.get("titre"), 120), "what": _s(b.get("quoi"), 300), "done": _to_int(b.get("fait")),
            "goal": max(1, _to_int(b.get("cible"), 1)), "finished": _to_bool(b.get("fini")), "claimed": _to_bool(b.get("pris")), "gain": _to_int(b.get("gain"))}


def parse_streak(e):
    """me.serie -> la série de connexion (7 jours) ; None si le site n'en envoie pas."""
    if not isinstance(e, dict):
        return None
    day = lambda g: {"kind": g.get("genre") if g.get("genre") in ("wikiki", "paquet", "dore", "minipack", "carte") else "paquet",  # noqa: E731
                     "text": _s(g.get("texte"), 80), "n": _to_int(g.get("n")), "card": _card(g.get("carte"))} if isinstance(g, dict) else None
    return {"open": _to_bool(e.get("ouvert")), "wait": _num(e.get("attente")), "ready": _to_bool(e.get("pret")), "day": _to_int(e.get("jour")),
            "done": _to_int(e.get("faits")), "next": _num(e.get("prochain")), "start": _num(e.get("debut")), "days": _rows(e.get("jours"), day, 7)}


def parse_rewards_state(me):
    """Ce que /api/state dit déjà des récompenses : pas d'appel en plus."""
    me = _dicts(me)
    g = me.get("gchat")
    return {"quests": _rows([me.get("quete"), me.get("quete2")], _quest, 2), "welcome": _rows(me.get("bienvenue"), _welcome, 20),
            "streak": parse_streak(me.get("serie")),
            "guild_chat": {"guild": _to_int(g.get("g")), "last": _to_int(g.get("dernier")), "seen": _to_int(g.get("vu"))} if isinstance(g, dict) else None}


def parse_achievements(d):
    """GET /api/succes -> {earned, total, won, to_claim, locked, families, items: [{code, family, title, what, done, goal, finished, claimed, gain}]}."""
    d = _dicts(d)
    item = lambda s: {"code": _s(s.get("code"), 40), "family": _s(s.get("fam"), 60), "title": _s(s.get("titre"), 120), "what": _s(s.get("quoi"), 300),  # noqa: E731
                      "done": _to_int(s.get("fait")), "goal": max(1, _to_int(s.get("but"), 1)), "finished": _to_bool(s.get("fini")),
                      "claimed": _to_bool(s.get("pris")), "gain": _to_int(s.get("gain"))} if isinstance(s, dict) and s.get("code") else None
    fams = [_s(f, 60) for f in d.get("familles") or [] if isinstance(f, str)][:30] if isinstance(d.get("familles"), list) else []
    return {"earned": _to_int(d.get("acquis")), "total": _to_int(d.get("total")), "won": _to_int(d.get("gagnes")), "to_claim": _to_int(d.get("aPrendre")),
            "locked": _to_bool(d.get("verrou")), "families": fams, "items": _rows(d.get("succes"), item, 200)}


def parse_claim(d):
    """Réponse d'une réclamation (quête, bienvenue, succès, série) -> {titles, gain, packs, gift, day, text, kind}."""
    d = _dicts(d)
    titles = [_s(t, 120) for t in d.get("titres") or [] if isinstance(t, str)][:60] if isinstance(d.get("titres"), list) else []
    if not titles and d.get("titre"):
        titles = [_s(d.get("titre"), 120)]
    return {"titles": titles, "gain": _to_int(d.get("gain")), "packs": _to_bool(d.get("packs")), "gift": _to_bool(d.get("cadeau")),
            "day": _to_int(d.get("jour")), "text": _s(d.get("texte"), 80), "kind": _s(d.get("genre"), 20)}
