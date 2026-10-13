"""Season Pass : décodage (forme lue dans saison.js), récupération validée, réserve WIKI-PRO respectée, aucun signal d'activité automatique.

Le client est un faux : aucun test ne parle au site."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wikipick import service as svc  # noqa: E402
from wikipick.changelog import news  # noqa: E402
from wikipick.parse import parse_card_sheet, parse_season  # noqa: E402


def state(level=5, taken=(), subscriber=False, free=(3, 5, 8)):
    return {"saison": {"cle": "s1", "nom": "Saison 1", "niveaux": 50, "ouverte": True, "reste": 86400 * 20, "gratuits": list(free)},
            "moi": {"niveau": level, "xp": 120, "xpNiveau": 100, "xpSuivant": 200, "abonne": subscriber, "pris": list(taken), "actifMinutes": 5},
            "niveaux": [{"niveau": n, "genre": "paquets" if n % 2 else "wikiki", "titre": f"Niveau {n} <b>x</b>", "texte": "t", "n": 2, "cle": "", "xp": n * 100, "rarete": "R"} for n in range(1, 51)]
                      + [{"niveau": 6, "genre": "carte", "titre": "Carte du 6", "texte": "", "cle": "perso-15", "xp": 600, "rarete": "L"}][:0],
            "regles": {"paquet": 10, "paquetOr": 30, "marchePremieres": 3, "enchere": 5, "vente": 5, "enchereSuite": 1, "marcheHeure": 4, "wbc": 50,
                       "actif": {"xp": 2, "minutes": 5, "maxMinutes": 60}, "cartes": {"PC": 1, "R": 3, "ZZ": 9}, "chromatique": 20}}


class Fake:
    def __init__(self, st=None):
        self.st, self.calls = st or state(), []

    def clear_session(self):
        pass

    def season(self):
        return self.st

    def season_take(self, level):
        self.calls.append(("take", level))
        return {"etat": self.st, "titre": "Une récompense", "genre": "paquets", "me": {"id": 1, "email": "secret@example.org", "coins": 3}}

    def season_equip(self, kind, key):
        self.calls.append(("equip", kind, key))
        return {}


def service(tmp_path, fake):
    return svc.Service(fake, tmp_path)


def test_parse_season_whitelists_and_cleans():
    d = parse_season(state())
    assert d["season"]["levels"] == 50 and d["season"]["free"] == [3, 5, 8] and d["season"]["open"] is True
    assert d["me"] == {"level": 5, "xp": 120, "xp_level": 100, "xp_next": 200, "subscriber": False, "taken": [], "active_minutes": 5}
    assert len(d["levels"]) == 50 and d["levels"][0]["kind"] == "paquets" and d["levels"][1]["kind"] == "wikiki"
    assert d["rules"]["cards"] == {"PC": 1, "R": 3}, "seules les raretés connues passent"
    weird = parse_season({"niveaux": [{"niveau": 1, "genre": "inconnu", "carte": {"cid": "fr:A", "n": "A", "r": "L", "img": "https://evil.example/x.png"}}, {"niveau": 0}, "x"],
                          "moi": {"pris": [True, "3", -1]}})
    assert weird["levels"][0]["kind"] == "paquets" and weird["levels"][0]["card"]["img"] is None and len(weird["levels"]) == 1 and weird["me"]["taken"] == [3]
    assert parse_season(None)["levels"] == []


def test_card_sheet_population():
    assert parse_card_sheet({"population": {"exemplaires": 12, "joueurs": 7, "chromatiques": 1}})["population"] == {"copies": 12, "players": 7, "shiny": 1}
    assert parse_card_sheet({"population": {"exemplaires": 0}})["population"] == {"copies": 0, "players": 0, "shiny": 0}
    assert parse_card_sheet({})["population"] is None


def test_take_a_free_reached_level(tmp_path):
    fake = Fake()
    s = service(tmp_path, fake)
    r = s.season_take(3)
    assert r["ok"] and fake.calls == [("take", 3)] and "secret@example.org" not in str(r) and r["state"]["me"]["level"] == 5
    assert s.actions_get()["actions"][0]["action"] == "Season Pass : récompense du niveau 3"


@pytest.mark.parametrize("level,subscriber,taken,why", [
    (9, False, (), "pas encore atteint"), (4, False, (), "réservée aux abonnés"), (3, False, (3,), "déjà récupérée"),
    (0, False, (), "invalide"), (51, False, (), "inconnu"), ("3", False, (), "invalide"), (True, False, (), "invalide"), (None, False, (), "invalide")])
def test_take_is_refused_before_anything_is_sent(tmp_path, level, subscriber, taken, why):
    fake = Fake(state(level=5, subscriber=subscriber, taken=taken))
    r = service(tmp_path, fake).season_take(level)
    assert r["ok"] is False and why in r["error"] and fake.calls == [], "rien ne part vers le site : la réserve WIKI-PRO n'est jamais contournée"


def test_a_subscriber_can_take_a_reserved_level(tmp_path):
    fake = Fake(state(level=5, subscriber=True))
    assert service(tmp_path, fake).season_take(4)["ok"] and fake.calls == [("take", 4)]


def test_a_card_reward_that_is_not_out_yet_is_not_claimed(tmp_path):
    st = state(level=5, free=(5,))
    st["niveaux"][4] = {"niveau": 5, "genre": "carte", "titre": "Carte", "texte": "", "cle": "perso-15", "xp": 500, "rarete": "L"}
    fake = Fake(st)
    r = service(tmp_path, fake).season_take(5)
    assert r["ok"] is False and "pas encore disponible" in r["error"] and fake.calls == []


def test_legendary_pack_cards_are_returned_and_acknowledged_like_a_gold_pack(tmp_path):
    st = state(level=5, free=(5,))
    fake = Fake(st)
    fake.season_take = lambda lv: {"etat": st, "titre": "Paquet légendaire", "genre": "legende", "me": {"revoirTs": {"or": 4242}},
                                   "cards": [{"cid": f"fr:C{i}", "n": f"C{i}", "r": "C", "id": i} for i in range(1, 21)]}
    fake.pack_seen = lambda ts, genre="normal": fake.calls.append(("seen", ts, genre))
    s = service(tmp_path, fake)
    r = s.season_take(5)
    assert r["ok"] and len(r["cards"]) == 20 and r["mythic"] is False
    assert s.pack_seen()["ok"] and fake.calls[-1] == ("seen", 4242, "or")


def test_equip_validates_the_reward_name(tmp_path):
    fake = Fake()
    s = service(tmp_path, fake)
    assert s.season_equip("dos", "s1-lagon")["ok"] and s.season_equip("cadre", "s1-or")["ok"] and fake.calls == [("equip", "dos", "s1-lagon"), ("equip", "cadre", "s1-or")]
    for bad in [("dos", "lagon"), ("dos", "../x"), ("dos", "s1-LAGON"), ("skin", "s1-x"), ("dos", None), ("dos", 5), ("dos", "s1-" + "a" * 40)]:
        assert s.season_equip(*bad)["ok"] is False
    assert len(fake.calls) == 2


def test_the_activity_signal_is_never_sent():
    from wikipick import client
    assert not hasattr(client.WikiPickClient, "season_active"), "le signal d'activité du site (qui rapporte de l'XP) n'est pas reproduit"
    from server.rpc import ALLOWED
    assert {"season_get", "season_take", "season_equip", "news_get"} <= ALLOWED
    assert "saison/actif" not in Path(client.__file__).read_text(encoding="utf-8").replace("`/api/saison/actif`", "")


def test_news_lists_versions_newest_first():
    n = news()
    assert n["site_url"].startswith("https://wiki-pick.com/") and n["versions"][0]["version"] == "0.4.0"
    assert all(i["kind"] in ("new", "better", "fix") for v in n["versions"] for i in v["items"])
