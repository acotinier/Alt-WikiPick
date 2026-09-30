"""Messagerie, amis, profils, guilde, récompenses : décodage (formes lues dans social.js) et écritures validées."""
import importlib
import sys
import types
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wikipick.live import LiveStream  # noqa: E402
from wikipick.social import (parse_achievements, parse_claim, parse_conversations, parse_friend_lists, parse_guild,  # noqa: E402
                             parse_guilds, parse_player_cards, parse_profile, parse_rewards_state, parse_thread, parse_user_search)

CARD = {"cid": "fr:La_Joconde", "n": "La Joconde <b>x</b>", "d": "tableau", "img": "https://upload.wikimedia.org/a.jpg", "r": "L", "v": 900000, "id": 7}


def _api(tmp_path, monkeypatch):
    """Api réelle, dans un dossier temporaire (jamais le vrai dossier de données de l'utilisateur)."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setitem(sys.modules, "webview", types.ModuleType("webview"))
    a = importlib.import_module("desktop.app").Api()
    a._client = mock.MagicMock()
    return a


def test_messages_decoding():
    convs = parse_conversations({"conversations": [
        {"name": "ami <i>", "avatar": "/avatars/1.png", "fav": 1, "bloque": False, "last": "salut <script>", "mine": True, "unread": 2, "created": 1790000000},
        {"name": "sensible", "avatar": "https://img.example/x.png", "avatarNSFW": True}, {"pas": "de nom"}, "x"]})
    assert len(convs) == 2 and convs[0]["avatar"] == "https://wiki-pick.com/avatars/1.png" and convs[0]["last"] == "salut <script>"
    assert convs[0]["fav"] is True and convs[0]["unread"] == 2 and convs[1]["avatar"] is None, "avatar marqué sensible : jamais affiché"
    t = parse_thread({"with": "ami", "relation": "friends", "bloque": "moi", "avatar": "javascript:alert(1)",
                      "messages": [{"id": 1, "mine": True, "text": "a" * 5000}, {"id": 2, "text": "<img src=x>"}, None]})
    assert t["friend"] and t["blocked"] == "moi" and t["avatar"] is None and len(t["messages"]) == 2
    assert len(t["messages"][0]["text"]) == 2000 and t["messages"][1] == {"id": 2, "mine": False, "text": "<img src=x>"}
    assert parse_thread({"bloque": "n'importe"})["blocked"] == ""


def test_friends_and_search_decoding():
    f = parse_friend_lists({"friends": [{"name": "a", "fav": True, "avatar": "//evil.example/x"}], "incoming": [{"name": "b"}], "outgoing": None})
    assert f == {"friends": [{"name": "a", "avatar": None, "fav": True}], "incoming": [{"name": "b", "avatar": None, "fav": False}], "outgoing": []}
    u = parse_user_search({"users": [{"name": "moi", "me": True}, {"name": "x", "relation": "friends"}, {"name": "y", "relation": "admin"}]})
    assert [x["relation"] for x in u] == ["", "friends", ""] and u[0]["me"] is True


def test_profile_and_player_cards_decoding():
    p = parse_profile({"isMe": False, "user": {"name": "Ada", "created": 1780000000, "description": "Bio <b>", "stats": {"cards": 10, "distinct": 8, "legend": 1, "sales": 3}},
                       "social": {"relation": "friends", "friends": 4}, "rank": {"rank": 12, "total": 900, "points": 5000},
                       "guild": {"id": 3, "tag": "WIKI", "name": "Les Encyclo"}, "showcases": [{"id": 1, "name": "Mes légendaires", "cards": [CARD, "x"]}],
                       "slots": 5, "max": 3, "email": "secret@example.org"})
    assert p["name"] == "Ada" and p["bio"] == "Bio <b>" and p["relation"] == "friends" and p["rank"]["rank"] == 12 and p["guild"]["tag"] == "WIKI"
    assert p["showcases"][0]["cards"][0]["name"] == "La Joconde <b>x</b>" and len(p["showcases"][0]["cards"]) == 1
    assert "secret" not in str(p), "rien d'autre que la liste blanche"
    assert parse_profile({})["rank"] is None and parse_profile({})["guild"] is None
    c = parse_player_cards({"page": 1, "pages": 3, "total": 120, "cards": [{"card": CARD, "n": 2}, {"card": None}]})
    assert c["page"] == 1 and c["pages"] == 3 and len(c["cards"]) == 1 and c["cards"][0]["n"] == 2 and c["cards"][0]["card"]["rarity"] == "L"


def test_guild_decoding():
    g = parse_guilds({"mine": 3, "guilds": [{"id": 3, "rank": 1, "tag": "WIKI", "name": "Encyclo", "couleur": "red;background:url(x)", "members": 12, "score": 9000},
                                             {"id": 4, "couleur": "#8b5cf6", "applied": True}, {"sans": "id"}]})
    assert g["mine"] == 3 and len(g["guilds"]) == 2 and g["guilds"][0]["color"] == "" and g["guilds"][1]["color"] == "#8b5cf6"
    d = parse_guild({"id": 3, "name": "Encyclo", "isMember": True, "isGerant": True, "isLeader": False, "maxMembres": 50,
                     "members": [{"name": "Ada", "leader": True, "total": 900, "joined": 1}, {"name": "Bob", "officier": 1, "me": True}],
                     "applications": [{"name": "Zoé", "created": 5}],
                     "feed": [{"id": 9, "name": "Ada", "card": CARD, "ts": 3, "likes": 2, "liked": True, "points": 900,
                               "comments": [{"id": 1, "name": "Bob", "text": "Bravo <3", "canDelete": True}]}, {"id": 10, "card": None}],
                     "chat": [{"id": 1, "uid": 2, "name": "Bob", "text": "salut", "ts": 4}]})
    assert d["is_member"] and d["is_manager"] and not d["is_leader"] and d["max_members"] == 50
    assert d["members"][1]["officer"] and d["members"][1]["me"] and d["applications"] == [{"name": "Zoé", "created": 5}]
    assert len(d["feed"]) == 1 and d["feed"][0]["card"]["name"].startswith("La Joconde") and d["feed"][0]["comments"][0]["can_delete"]
    assert d["chat"][0]["text"] == "salut"
    assert parse_guild({})["feed"] == [] and parse_guild({})["chat"] == [], "hors de la guilde : pas de fil ni de tchat"


def test_rewards_decoding():
    me = {"quete": {"titre": "Ouvre 3 paquets", "quoi": "…", "fait": 1, "cible": 3, "fini": False, "pris": False, "next": 3600, "gain": 50},
          "quete2": {"titre": "Mini", "fait": 1, "cible": 1, "fini": True, "packs": True, "gain": 2},
          "bienvenue": [{"code": "b1", "titre": "Premier paquet", "fait": 1, "cible": 1, "fini": True, "pris": False, "gain": 20}, {"titre": "sans code"}],
          "serie": {"ouvert": True, "pret": True, "jour": 3, "faits": 2, "prochain": 5000, "jours": [{"genre": "wikiki", "texte": "50 Wikiki"},
                    {"genre": "carte", "texte": "Une carte", "carte": CARD}, {"genre": "<script>", "texte": "x"}]},
          "gchat": {"g": 3, "dernier": 10, "vu": 8}}
    r = parse_rewards_state(me)
    assert [q["title"] for q in r["quests"]] == ["Ouvre 3 paquets", "Mini"] and r["quests"][1]["packs"] is True
    assert r["welcome"] == [{"code": "b1", "title": "Premier paquet", "what": "", "done": 1, "goal": 1, "finished": True, "claimed": False, "gain": 20}]
    s = r["streak"]
    assert s["ready"] and s["day"] == 3 and s["days"][1]["card"]["rarity"] == "L" and s["days"][2]["kind"] == "paquet", "genre inconnu : ramené à un genre connu"
    assert r["guild_chat"] == {"guild": 3, "last": 10, "seen": 8}
    assert parse_rewards_state({}) == {"quests": [], "welcome": [], "streak": None, "guild_chat": None}
    a = parse_achievements({"acquis": 3, "total": 50, "gagnes": 300, "aPrendre": 40, "familles": ["Collection", 5],
                            "succes": [{"code": "c10", "fam": "Collection", "titre": "10 cartes", "fait": 10, "but": 10, "fini": True, "gain": 20}]})
    assert a["families"] == ["Collection"] and a["to_claim"] == 40 and a["items"][0]["finished"] and not a["items"][0]["claimed"]
    assert parse_claim({"titres": ["A", "B"], "gain": 40})["titles"] == ["A", "B"] and parse_claim({"titre": "Q", "gain": 2, "packs": True})["titles"] == ["Q"]
    assert parse_claim({"jour": 3, "texte": "Un paquet doré", "genre": "dore"})["day"] == 3


def test_social_writes_are_validated_and_exact(tmp_path, monkeypatch):
    a = _api(tmp_path, monkeypatch)
    c = a._client
    c.friend_action.return_value = {"relation": "friends"}
    c.guild_post.return_value = {"liked": True}
    c.claim.return_value = {"titres": ["Premier paquet"], "gain": 20}
    # messagerie : pseudo et texte obligatoires, 1000 caractères au plus
    for bad in (("", "salut"), ("ami", "   "), ("ami", "x" * 1001), ("x" * 101, "salut")):
        assert a.message_send(*bad)["ok"] is False
    assert not c.message_send.called
    assert a.message_send("ami", "  salut  ")["ok"] and c.message_send.call_args.args == ("ami", "salut")
    # amis : seulement les actions du site
    assert a.friend_action("admin", "x")["ok"] is False and not c.friend_action.called
    assert a.friend_action("accept", "Zoé") == {"ok": True, "relation": "friends"} and c.friend_action.call_args.args == ("accept", "Zoé")
    assert a.friend_favorite("Zoé", "oui")["ok"] and c.friend_favorite.call_args.args == ("Zoé", False), "seul True met en favori"
    # guilde : un corps exact par action, rien pour une action inconnue ou une entrée invalide
    for bad in (("admin/x", 1), ("apply", "3"), ("kick", ""), ("chat", None, " "), ("comment", 9, "x" * 401), ("like", True),
                ("create", {"name": "A", "tag": "WK"}), ("create", {"name": "Guilde", "tag": "W<>K"})):
        assert a.guild_action(*bad)["ok"] is False, bad
    assert not c.guild_post.called
    ok = [(("apply", 3), ("apply", {"id": 3})), (("apply/accept", "Zoé"), ("apply/accept", {"name": "Zoé"})),
          (("officier", "Bob", True), ("officier", {"name": "Bob", "on": True})), (("leave",), ("leave", {})),
          (("chat", None, " coucou "), ("chat", {"text": "coucou"})), (("comment", 9, "Bravo"), ("comment", {"feed_id": 9, "text": "Bravo"})),
          (("like", 9), ("like", {"feed_id": 9})), (("comment/delete", 4), ("comment/delete", {"comment_id": 4})),
          (("create", {"name": " Les Encyclo ", "tag": "wiki", "descr": "x"}), ("create", {"name": "Les Encyclo", "tag": "WIKI", "descr": "x"}))]
    for args, sent in ok:
        assert a.guild_action(*args)["ok"], args
        assert c.guild_post.call_args.args == sent, (args, c.guild_post.call_args)
    # récompenses : les corps du site
    for bad in (("quete", 3), ("quete", None), ("succes", "a b"), ("boutique", None), ("bienvenue", 5)):
        assert a.claim(*bad)["ok"] is False, bad
    assert not c.claim.called
    for args, sent in ((("quete", 2), ("quete", {"n": 2})), (("bienvenue", None), ("bienvenue", {})), (("succes", "c10"), ("succes", {"code": "c10"})),
                       (("serie",), ("serie", {}))):
        r = a.claim(*args)
        assert r["ok"] and r["titles"] == ["Premier paquet"] and c.claim.call_args.args == sent
    log = a.actions_get()["actions"]
    assert log and not any("salut" in x["action"] or "coucou" in x["action"] or "Bravo" in x["action"] for x in log), "le texte des messages n'est jamais journalisé"


def test_one_write_at_a_time(tmp_path, monkeypatch):
    a = _api(tmp_path, monkeypatch)
    a._write_lock.acquire()
    try:
        assert a.message_send("ami", "salut") == {"ok": False, "error": "Une action est déjà en cours."} and not a._client.message_send.called
    finally:
        a._write_lock.release()


def test_load_me_brings_rewards_and_guild_id(tmp_path, monkeypatch):
    a = _api(tmp_path, monkeypatch)
    a._client.state.return_value = {"me": {"id": 1, "name": "Moi", "email": "secret@example.org", "gchat": {"g": 7, "dernier": 2, "vu": 1},
                                           "serie": {"ouvert": True, "jour": 1, "jours": []}}, "info": {}}
    r = a.load_me()
    assert r["ok"] and r["rewards"]["streak"]["day"] == 1 and a._live.guild_id == 7 and "secret" not in str(r)
    a._client.guilds.return_value = {"mine": None, "guilds": []}
    a.guilds_get()
    assert a._live.guild_id is None


def test_live_passes_only_my_guild_news():
    live = LiveStream(mock.MagicMock(), lambda: 1)
    live.push("guild", {"what": "chat", "id": 7, "mid": 3, "par": 2})
    assert live.poll() == [], "pas de guilde : rien"
    live.guild_id = 7
    live.push("guild", {"what": "chat", "id": 8, "mid": 3, "par": 2})
    live.push("guild", {"what": "chat", "id": 7, "mid": 3, "par": 2, "text": "privé"})
    assert live.poll() == [{"event": "guild", "data": {"what": "chat", "id": 7, "mid": 3, "par": 2}}]
