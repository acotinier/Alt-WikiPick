"""Écritures manuelles : validation stricte, une action à la fois, journal local, pas de rejeu, garde-fous WIKI-PRO.

Toutes les Api sont créées dans un dossier temporaire (jamais le vrai dossier de données de l'utilisateur) et le
client est remplacé par un faux : aucun test ne parle au site."""
import importlib
import json
import sys
import threading
import types
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wikipick.client import ApiError, WikiPickClient  # noqa: E402
from wikipick.parse import expand_group, parse_card_sheet, parse_corbeille, parse_friends, parse_pro_market, parse_user_cards  # noqa: E402

CHAMPS = ["cid", "n", "d", "img", "r", "v", "nl", "lang", "locked"]
IMGP = ["https://thumb.wikimedia.org/", "https://upload.wikimedia.org/"]


def make_api(tmp_path, monkeypatch, me=None):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setitem(sys.modules, "webview", types.ModuleType("webview"))
    api = importlib.import_module("desktop.app").Api()
    api._me = me if me is not None else {"id": 1, "name": "Moi"}
    api._client = mock.Mock()
    return api


def journal(api):
    return api.actions_get()["actions"]


# ---------------------------------------------------------------- décodage des exemplaires
def test_free_ids_exclude_locked_and_exclusive():
    row = lambda r, locked, ids, extra=None: ["fr:X", "X", "", "", r, "5", "1", "fr", locked, ids, [], extra]  # noqa: E731
    libre = expand_group(row("R", "false", [1, 2, 3]), CHAMPS, IMGP)
    assert libre["free_ids"] == [1, 2, 3] and libre["locked_ids"] == []
    partiel = expand_group(row("R", "false", [1, 2, 3], {"verrous": [2]}), CHAMPS, IMGP)
    assert partiel["free_ids"] == [1, 3] and partiel["locked_ids"] == [2], "un exemplaire verrouillé n'est jamais proposé"
    assert expand_group(row("R", "true", [1, 2]), CHAMPS, IMGP)["free_ids"] == [], "groupe entièrement verrouillé"
    assert expand_group(row("EXC", "false", [9]), CHAMPS, IMGP)["free_ids"] == [], "les exclusives ne se vendent ni ne se recyclent"
    assert expand_group(row("C", "false", ["4", "x", -1, 0]), CHAMPS, IMGP)["ids"] == [4], "identifiants nettoyés"


def test_new_decoders():
    sheet = parse_card_sheet({"mine": [{"id": 7, "state": "free", "aVendre": 1, "sh": 0}]})
    assert sheet["mine"][0]["id"] == 7 and sheet["mine"][0]["for_sale"] is True
    assert parse_friends({"friends": [{"name": "a", "fav": 1}, "x"], "incoming": [{"name": "b"}], "outgoing": None}) == \
        {"friends": [{"name": "a", "fav": True}], "incoming": [{"name": "b", "fav": False}], "outgoing": []}
    groups = parse_user_cards({"groups": [{"card": {"cid": "fr:A", "n": "A", "r": "R"}, "ids": [5, "6", 0]}, {"card": {"cid": "fr:B"}, "ids": []}, "x"]})
    assert len(groups) == 1 and groups[0]["ids"] == [5, 6] and groups[0]["card"]["name"] == "A"
    c = parse_corbeille({"items": [{"id": 3, "cid": "fr:Z", "n": "Z", "r": "C", "reste": 300}, {"id": 0}], "prix": 4, "minutes": 20})
    assert c["items"][0]["id"] == 3 and c["items"][0]["left"] == 300 and c["price"] == 4 and c["minutes"] == 20 and len(c["items"]) == 1
    p = parse_pro_market({"live": 2, "stats": {"n": 3, "last": 10, "avg": 9.6, "min": 5, "max": 20}, "sales": [{"ts": 1, "price": 10, "title": "T"}, "x"]})
    assert p["live"] == 2 and p["stats"]["avg"] == 9 and p["sales"] == [{"ts": 1.0, "price": 10, "title": "T"}] and p["rsales"] == []


# ---------------------------------------------------------------- validation stricte
@pytest.mark.parametrize("bad", ["12", 12.5, True, None, -1, 0, 10**7, [1], {"a": 1}])
def test_bid_rejects_anything_but_a_sane_integer_amount(tmp_path, monkeypatch, bad):
    a = make_api(tmp_path, monkeypatch)
    r = a.bid(5, bad)
    assert r["ok"] is False and "invalide" in r["error"]
    a._client.bid.assert_not_called()  # rien ne part vers le site


def test_bid_sends_integers_and_is_journaled(tmp_path, monkeypatch):
    a = make_api(tmp_path, monkeypatch)
    a._client.bid.return_value = {"extended": True, "endsAt": 1790000000.5}
    assert a.bid(5, 120.0) == {"ok": True, "extended": True, "ends_at": 1790000000.5}
    a._client.bid.assert_called_once_with(5, 120)
    assert journal(a)[0]["action"] == "Mise de 120.0 Wikiki sur l'enchère 5" and journal(a)[0]["ok"] is True
    a._client.bid.side_effect = ApiError("La mise minimale est de 130.")
    r = a.bid(5, 120)
    assert r == {"ok": False, "error": "La mise minimale est de 130."}
    assert journal(a)[0]["ok"] is False and "130" in journal(a)[0]["error"] and len(journal(a)) == 2


def test_one_write_at_a_time(tmp_path, monkeypatch):
    a = make_api(tmp_path, monkeypatch)
    started, release = threading.Event(), threading.Event()

    def slow(*_):
        started.set(); release.wait(2)
        return {}
    a._client.bid.side_effect = slow
    t = threading.Thread(target=lambda: a.bid(1, 10)); t.start()
    assert started.wait(2)
    second = a.bid(1, 10)  # le deuxième clic, pendant le premier
    assert second == {"ok": False, "error": "Une action est déjà en cours."}
    release.set(); t.join(2)
    assert a._client.bid.call_count == 1, "un double clic ne mise qu'une fois"
    assert a.bid(1, 10)["ok"] is True  # et le verrou est bien relâché ensuite


def test_auction_and_trade_inputs(tmp_path, monkeypatch):
    a = make_api(tmp_path, monkeypatch)
    assert a.auction_create(3, 50, "10m")["ok"] and a._client.auction_create.call_args.args == (3, 50, "10m")
    assert a.auction_create(3, 50, "2j")["ok"] is False and a.auction_create(3, 0, "1h")["ok"] is False and a.auction_create("3", 5, "1h")["ok"] is False
    assert a._client.auction_create.call_count == 1
    assert a.auction_cancel(9)["ok"] and a.auction_price(9, 7)["ok"] and a.auction_price(9, -7)["ok"] is False
    assert a.trade_action("accept", 4)["ok"] and a._client.trade_action.call_args.args == ("accept", 4)
    assert a.trade_action("delete", 4)["ok"] is False and a.trade_action("accept", "4")["ok"] is False
    assert a._client.trade_action.call_count == 1


def test_trade_send_validation_and_counter(tmp_path, monkeypatch):
    a = make_api(tmp_path, monkeypatch)
    assert a.trade_send("", [1], [2])["ok"] is False and a.trade_send("ami", [], [], 0, 0)["ok"] is False, "un échange vide est refusé"
    assert a.trade_send("ami", list(range(1, 12)), [1])["ok"] is False, "10 cartes au plus de chaque côté"
    assert a.trade_send("ami", [1], ["2"])["ok"] is False and a.trade_send("ami", [1], [2], -5)["ok"] is False
    assert a._client.trade_send.call_count == 0
    assert a.trade_send("ami", [1, 2], [3], 5, 0, "x" * 500)["ok"]
    body, kw = a._client.trade_send.call_args.args[0], a._client.trade_send.call_args.kwargs
    assert body == {"to": "ami", "give": [1, 2], "take": [3], "give_coins": 5, "take_coins": 0, "message": "x" * 200} and kw == {"counter": False}
    assert a.trade_send("ami", [1], [], 0, 0, "", 42)["ok"]
    assert a._client.trade_send.call_args.args[0]["trade_id"] == 42 and a._client.trade_send.call_args.kwargs == {"counter": True}


def test_recycle_single_bulk_and_limits(tmp_path, monkeypatch):
    a = make_api(tmp_path, monkeypatch)
    a._client.bank.return_value = {"gain": 3}
    assert a.recycle([7]) == {"ok": True, "gain": 3, "sold": 1, "locked": 0} and a._client.bank.call_args.args == (7,)
    a._client.bank_bulk.return_value = {"gain": 9, "sold": 2, "locked": 1}
    assert a.recycle([1, 2, 3]) == {"ok": True, "gain": 9, "sold": 2, "locked": 1} and a._client.bank_bulk.call_args.args == ([1, 2, 3],)
    assert a.recycle([])["ok"] is False and a.recycle(list(range(1, 102)))["ok"] is False and a.recycle("1,2")["ok"] is False and a.recycle([1, "2"])["ok"] is False
    assert a._client.bank.call_count == 1 and a._client.bank_bulk.call_count == 1


def test_corbeille_lock_forsale_wish(tmp_path, monkeypatch):
    a = make_api(tmp_path, monkeypatch)
    a._client.corbeille_restore.return_value = {"restaurees": 2, "cout": 8}
    assert a.corbeille_restore([1, 2]) == {"ok": True, "restored": 2, "cost": 8} and a._client.corbeille_restore.call_args.args == ({"ids": [1, 2]},)
    a.corbeille_restore(everything=True); assert a._client.corbeille_restore.call_args.args == ({"tout": True},)
    assert a.corbeille_restore([])["ok"] is False and a.corbeille_restore("tout")["ok"] is False
    a._client.corbeille_empty.return_value = {"videes": 5}
    assert a.corbeille_empty() == {"ok": True, "erased": 5}
    a._client.card_lock.return_value = {"locked": True}
    assert a.card_lock(4, "fr:Rembrandt", True, True) == {"ok": True, "locked": True} and a._client.card_lock.call_args.args == (4, "fr:Rembrandt", True, True)
    assert a.card_lock(4, "pas-un-cid", False, True)["ok"] is False and a.card_lock("4", "fr:X", False, True)["ok"] is False
    a._client.card_for_sale.return_value = {"n": 3}
    assert a.card_for_sale(4, True) == {"ok": True, "n": 3}
    a._client.wish.return_value = {"wished": True}
    r = a.wish_set("fr:X", True, {"name": "X", "desc": "d", "img": "https://evil.example/x.png", "rarity": "R", "lang": "fr", "email": "secret"})
    assert r == {"ok": True, "wished": True}
    sent = a._client.wish.call_args.args
    assert sent[0] == "fr:X" and sent[1] is True and sent[2] == {"cid": "fr:X", "n": "X", "d": "d", "img": None, "r": "R", "lang": "fr"}, "champs limités, image filtrée"


def test_writes_are_never_retried_automatically(tmp_path):
    import requests
    c = WikiPickClient(session_file=tmp_path / "s.json")
    with mock.patch.object(c.http, "post", side_effect=requests.ConnectionError("réseau coupé")) as post:
        with pytest.raises(ApiError):
            c.bid(5, 100)
        assert post.call_count == 1, "une écriture qui échoue n'est jamais rejouée toute seule (elle a pu réussir côté serveur)"
    with mock.patch.object(c.http, "post", return_value=mock.Mock(status_code=200, json=lambda: {})) as post:
        c.trade_action("accept", 4); assert post.call_args.args[0].endswith("/api/trade/accept") and post.call_args.kwargs["json"] == {"trade_id": 4}
        c.bank_bulk([1, 2]); assert post.call_args.kwargs["json"] == {"card_ids": [1, 2]}
        c.auction_price(3, 9); assert post.call_args.args[0].endswith("/api/auction/prix") and post.call_args.kwargs["json"] == {"auction_id": 3, "start_price": 9}
        c.card_lock(1, "fr:X", True, True); assert post.call_args.kwargs["json"] == {"card_id": 1, "cid": "fr:X", "shiny": 1, "on": True}


# ---------------------------------------------------------------- WIKI-PRO et paquet doré : le drapeau du profil décide
def test_pro_market_is_never_requested_for_a_non_subscriber(tmp_path, monkeypatch):
    a = make_api(tmp_path, monkeypatch, me={"id": 1, "pro": False})
    r = a.pro_market("fr:X", "R", False)
    assert r == {"ok": False, "error": "Réservé aux abonnés WIKI-PRO."}
    a._client.pro_market.assert_not_called()
    a._me = {"id": 1, "pro": True}
    a._client.pro_market.return_value = {"live": 1, "stats": {"n": 2}}
    r = a.pro_market("fr:X", "R", True)
    assert r["ok"] and r["live"] == 1 and a._client.pro_market.call_args.args == ("fr:X", "R", True)
    assert a.pro_market("fr:X", "R;drop", False)["ok"] is False


def test_gold_pack_needs_the_profile_flag_and_is_journaled(tmp_path, monkeypatch):
    a = make_api(tmp_path, monkeypatch)
    a._client.state = lambda: {"me": {"id": 1, "name": "Moi", "proPack": False, "paquetOr": 0}, "info": {}}
    r = a.open_gold_pack()
    assert r["ok"] is False and "Aucun paquet doré" in r["error"]
    a._client.open_gold_pack.assert_not_called()
    a._client.state = lambda: {"me": {"id": 1, "name": "Moi", "paquetOr": 1}, "info": {}}
    a._client.open_gold_pack.return_value = {"cards": [{"cid": "fr:A", "n": "A", "r": "L", "v": 9, "id": 1}], "me": {"id": 1, "name": "Moi", "revoirTs": {"or": 123.5}}}
    r = a.open_gold_pack()
    assert r["ok"] and r["cards"][0]["name"] == "A"
    assert a.pack_history()["packs"][0]["gold"] is True, "marqué doré : exclu de la chance mesurée"
    a.pack_seen()
    a._client.pack_seen.assert_called_once_with(123.5, "or")
    assert journal(a)[0]["action"] == "Paquet doré ouvert"


# ---------------------------------------------------------------- arène : décodeurs, Api, événements du flux
DUEL = {
    "moi": {"name": "Moi", "avatar": "x"}, "adversaire": {"name": "Rival <b>x</b>", "email": "secret@example.org"},
    "equipeA": [{"cid": "fr:A", "n": "A", "r": "R", "e": "long extrait"}], "equipeB": [{"cid": "fr:B", "n": "B", "r": "C"}, "bizarre"],
    "manches": [{"pvA": 192, "pvB": 180, "resteA": 40, "resteB": 0, "seq": 1, "gagnant": "a", "ko": True,
                 "coups": [{"par": "a", "degats": 30, "crit": 0, "sort": "foudre", "sortNom": "Éclair", "pvA": 192, "pvB": 150}, {"par": "b", "degats": 152, "crit": 1, "pvA": 40, "pvB": 0}]}],
    "gagne": True, "scoreA": 2, "scoreB": 1, "gain": 30, "restant": 4, "total": 5,
}


def test_combat_decoders():
    from wikipick.parse import parse_chest, parse_combat_info, parse_decks, parse_defi, parse_duel, parse_users
    info = parse_combat_info({"restant": 3, "total": 5, "prochain": 99.5, "taille": 3, "attente": 60, "prepa": 300,
                              "adversaires": [{"name": "ami", "enligne": 1, "encombat": 0, "cartes": 40, "fav": 1}, {"pseudo": "x"}, "y"],
                              "historique": [{"moi": 2, "lui": 1, "defense": 1, "adversaire": "ami", "gain": 30, "quand": 5}], "coffres": 1, "coffreTous": 5, "coffreReste": 2})
    assert info["left"] == 3 and info["size"] == 3 and info["opponents"] == [{"name": "ami", "online": True, "fighting": False, "cards": 40, "fav": True}]
    assert info["history"][0]["defended"] is True and info["chests"] == 1 and info["chest_left"] == 2
    d = parse_decks({"decks": [{"id": 4, "nom": "Mes <b>mythiques</b>", "complet": 1, "cartes": [{"cid": "fr:A", "n": "A"}, None], "ids": [1, "2", 0]}, {"id": 0}, "x"]})
    assert len(d) == 1 and d[0]["name"] == "Mes <b>mythiques</b>" and d[0]["cards"][1] is None and d[0]["ids"] == [1, 2]
    df = parse_defi({"id": 9, "etat": "prepa", "expire": 123.5, "lance": 0, "adversaire": {"name": "Rival"}, "moiPret": 1, "equipe": [{"cid": "fr:A", "n": "A"}]})
    assert df == {"id": 9, "state": "prepa", "expire": 123.5, "launched": False, "opponent": "Rival", "my_ready": True, "opp_ready": False, "team": df["team"]} and df["team"][0]["name"] == "A"
    assert parse_defi(None) is None and parse_defi({}) is None
    du = parse_duel(DUEL)
    assert du["opponent"] == "Rival <b>x</b>" and len(du["team_b"]) == 1 and du["won"] is True and du["rounds"][0]["winner"] == "a" and du["rounds"][0]["ko"] is True
    assert du["rounds"][0]["hits"][0] == {"by": "a", "damage": 30, "crit": False, "spell": "foudre", "spell_name": "Éclair", "hp_a": 192, "hp_b": 150}
    assert du["rounds"][0]["hits"][1]["crit"] is True and du["rounds"][0]["hits"][1]["spell"] == "epee"
    assert "email" not in json.dumps(du) and "extrait" not in json.dumps(du), "rien d'autre que les champs connus"
    assert parse_chest({"lot": "paquets", "n": 2, "reste": 1, "carte": {"cid": "fr:Z", "n": "Z", "r": "L", "isNew": 1}}) == \
        {"kind": "packs", "n": 2, "left": 1, "card": parse_chest({"carte": {"cid": "fr:Z", "n": "Z", "r": "L", "isNew": 1}})["card"]}
    assert parse_chest({"lot": "wikiki", "n": 40})["kind"] == "wikiki" and parse_users({"users": [{"name": "a", "enligne": 1}, {"name": "moi", "me": 1}, {}]}) == [{"name": "a", "online": True}]


def test_combat_api_validation_and_journal(tmp_path, monkeypatch):
    a = make_api(tmp_path, monkeypatch)
    a._client.combat_challenge.return_value = {"id": 9, "etat": "attente", "expire": 5, "lance": 1, "adversaire": {"name": "Rival"}}
    r = a.combat_challenge("Rival")
    assert r["ok"] and r["defi"]["id"] == 9 and r["defi"]["launched"] is True and a._client.combat_challenge.call_args.args == ("Rival",)
    assert a.combat_challenge("")["ok"] is False and a.combat_challenge("x" * 101)["ok"] is False and a._client.combat_challenge.call_count == 1
    a._client.combat_answer.return_value = {"id": 9, "etat": "prepa", "adversaire": {"name": "Rival"}}
    assert a.combat_answer(9, True)["defi"]["state"] == "prepa" and a._client.combat_answer.call_args.args == (9, True)
    assert a.combat_answer(9, False)["defi"] is None and a._client.combat_answer.call_args.args == (9, False)
    assert a.combat_answer(9, "oui")["defi"] is None and a._client.combat_answer.call_args.args == (9, False), "seul True accepte"
    a._client.combat_team.return_value = {"attente": 1}
    assert a.combat_team(9, [1, 2, 3]) == {"ok": True, "waiting": True, "duel": None}
    a._client.combat_team.return_value = DUEL
    r = a.combat_team(9, [1, 2, 3]); assert r["waiting"] is False and r["duel"]["gain"] == 30
    assert a.combat_team(9, ["1"])["ok"] is False and a.combat_team(9, list(range(1, 12)))["ok"] is False and a._client.combat_team.call_count == 2
    a._client.combat_deck_save.return_value = {"decks": [{"id": 1, "nom": "D", "complet": 1, "cartes": [], "ids": [1, 2, 3]}]}
    assert a.combat_deck_save(0, " Mon deck ", [1, 2, 3])["decks"][0]["ids"] == [1, 2, 3] and a._client.combat_deck_save.call_args.args == (0, "Mon deck", [1, 2, 3])
    assert a.combat_deck_save(0, "", [1])["ok"] is False and a.combat_deck_save(0, "x" * 31, [1])["ok"] is False and a.combat_deck_save(-1, "D", [1])["ok"] is False
    a._client.combat_chest.return_value = {"lot": "wikiki", "n": 40, "reste": 0}
    assert a.combat_chest()["kind"] == "wikiki"
    a._client.combat_choice.return_value = {}
    before = len(journal(a)); assert a.combat_choice(9, [1, 2])["ok"] and len(journal(a)) == before, "la synchro en direct n'encombre pas le journal"
    assert a.combat_choice(9, "1")["ok"] is False and a.combat_cancel(9)["ok"] and journal(a)[0]["action"] == "Arène : défi annulé"
    a._client.users.return_value = {"users": [{"name": "zoé", "enligne": 1}]}
    assert a.users_search("zo") == {"ok": True, "users": [{"name": "zoé", "online": True}]} and a.users_search("  ")["users"] == []


def test_combat_stream_events_are_personal_and_sanitized():
    from wikipick.live import LiveStream
    live = LiveStream(client=None, my_id=lambda: 1)
    live.push("combat", {"what": "defi", "to": 2, "id": 5})  # pour un autre joueur
    assert live.poll() == []
    live.push("combat", {"what": "defi", "to": 1, "id": 5, "expire": 99.5, "de": {"name": "Rival", "email": "secret@example.org", "avatar": "https://evil.example/a.png"},
                         "equipe": [{"cid": "fr:A", "n": "A", "r": "L", "e": "extrait"}], "interne": "x"})
    ev = live.poll()[0]["data"]
    assert ev["from"] == "Rival" and ev["team"][0]["name"] == "A" and ev["id"] == 5 and "interne" not in ev and "de" not in ev and "secret" not in json.dumps(ev)
    live.push("combat", {"what": "go", "to": 1, "combat": DUEL})
    go = live.poll()[0]["data"]
    assert go["what"] == "go" and go["duel"]["score_a"] == 2 and "email" not in json.dumps(go)
    live.push("combat", {"what": "choix", "to": 1, "id": 5, "cartes": [{"cid": "fr:B", "n": "B"}]})
    assert live.poll()[0]["data"]["cards"][0]["name"] == "B"
