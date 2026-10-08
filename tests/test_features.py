"""Étiquettes, cartes masquées, ouverture de plusieurs paquets, images des cartes exclusives.

Le client est un faux : aucun test ne parle au site, aucun test n'attend vraiment entre deux paquets."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wikipick import service as svc  # noqa: E402
from wikipick.client import ApiError  # noqa: E402
from wikipick.parse import _safe_img, expand_group, parse_tags  # noqa: E402

CHAMPS = ["cid", "n", "d", "img", "r", "v", "nl", "lang", "locked"]
IMGP = ["https://thumb.wikimedia.org/", "https://upload.wikimedia.org/"]


class Fake:
    def __init__(self, packs=3, defi=False):
        self.me = {"id": 1, "name": "Moi", "packs": packs, "defi": defi, "email": "secret@example.org"}
        self.opened, self.proofs, self.calls, self.fail_at = 0, [], [], None

    def clear_session(self):
        pass

    def state(self):
        return {"me": dict(self.me), "info": {}}

    def open_pack(self, proof=None):
        if self.fail_at == self.opened + 1:
            raise ApiError("Réseau indisponible : ConnectionError")
        self.opened += 1
        self.proofs.append(proof)
        self.me["packs"] -= 1
        if self.opened == 2 and getattr(self, "defi_after_2", False):
            self.me["defi"] = True
        i = self.opened
        cards = [{"cid": f"fr:P{i}_{k}", "n": f"Carte {i}-{k}", "d": "", "img": None, "r": "C", "v": 1, "id": i * 10 + k, "isNew": k == 0} for k in range(5)]
        return {"cards": cards, "me": {**self.me, "revoirTs": {"normal": 1000 + i}}}

    def pack_seen(self, ts, genre="normal"):
        self.calls.append(("seen", ts, genre))

    def tags(self):
        return {"tags": [{"id": 2, "name": "B", "color": "#ff0000", "ordre": 1}, {"id": 1, "name": "A", "color": "bad", "ordre": 0}]}

    def tag_create(self, name, color):
        self.calls.append(("create", name, color))
        return {"id": 9, "tags": [{"id": 9, "name": name, "color": color}]}

    def tag_update(self, tid, name, color):
        self.calls.append(("update", tid, name, color))
        return {"tags": [{"id": tid, "name": name, "color": color}]}

    def tag_delete(self, tid):
        self.calls.append(("delete", tid))
        return {"tags": []}

    def card_tags(self, cid, ids):
        self.calls.append(("card_tags", cid, ids))
        return {}


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(svc, "PACK_PAUSE", 0.0)


def service(tmp_path, fake=None):
    return svc.Service(fake or Fake(), tmp_path)


# ---------------------------------------------------------------- images des cartes exclusives
def test_exclusive_images_only_from_wiki_pick_perso_folder():
    assert _safe_img("/perso/518ee99f2263c486.jpg") == "https://wiki-pick.com/perso/518ee99f2263c486.jpg"
    assert _safe_img("https://wiki-pick.com/perso/a-b_c.png") == "https://wiki-pick.com/perso/a-b_c.png"
    for bad in ["/perso/../etc/passwd", "/perso/", "/autre/x.jpg", "https://wiki-pick.com/autre/x.jpg", "https://evil.example/perso/x.jpg", "//evil.example/perso/x.jpg",
                "/perso/x.jpg?a=1", "javascript:alert(1)", None, 12]:
        assert _safe_img(bad) is None, bad
    assert _safe_img("https://upload.wikimedia.org/x.jpg") == "https://upload.wikimedia.org/x.jpg"


def test_exclusive_card_takes_its_picture_from_the_custom_layout():
    row = lambda img, extra: ["perso-2", "WIKI-PICK.COM", "", img, "EXC", "0", "0", "", "false", [5], [], extra]  # noqa: E731
    assert expand_group(row("", {"perso": {"media": "/perso/abc.jpg"}}), CHAMPS, IMGP)["img"] == "https://wiki-pick.com/perso/abc.jpg"
    assert expand_group(row("/perso/def.jpg", {}), CHAMPS, IMGP)["img"] == "https://wiki-pick.com/perso/def.jpg"
    assert expand_group(row("", {"perso": {"media": "/perso/abc.mp4", "video": True}}), CHAMPS, IMGP)["img"] is None, "une vidéo n'est pas une image"
    assert expand_group(row("", {"perso": {"media": "https://evil.example/x.jpg"}}), CHAMPS, IMGP)["img"] is None


# ---------------------------------------------------------------- étiquettes
def test_parse_tags_cleans_and_orders():
    t = parse_tags([{"id": 2, "name": "B" * 90, "color": "#FF0000", "ordre": 1}, {"id": 1, "name": "A", "color": "javascript:x", "ordre": 0}, {"id": 0}, "x", {"name": "sans id"}])
    assert [x["id"] for x in t] == [1, 2] and t[0]["color"] == "#64748b" and t[1]["color"] == "#ff0000" and len(t[1]["name"]) == 40 and parse_tags(None) == []


@pytest.mark.parametrize("name,color", [("", "#ff0000"), ("x" * 21, "#ff0000"), (None, "#ff0000"), (5, "#ff0000"), ("ok", "red"), ("ok", "#ff00"), ("ok", None), ("ok", "#ff0000; x")])
def test_tag_save_validates_before_sending(tmp_path, name, color):
    fake = Fake()
    assert service(tmp_path, fake).tag_save(None, name, color)["ok"] is False and fake.calls == []


def test_tag_create_update_delete_and_card_tags(tmp_path):
    fake = Fake()
    s = service(tmp_path, fake)
    assert s.tags_get()["tags"][0]["id"] == 1
    r = s.tag_save(None, "  Mes   favoris ", "#22C55E")
    assert r["ok"] and r["id"] == 9 and fake.calls[-1] == ("create", "Mes favoris", "#22c55e")
    assert s.tag_save(9, "Autre", "#3b82f6")["ok"] and fake.calls[-1] == ("update", 9, "Autre", "#3b82f6")
    assert s.tag_save("9", "Autre", "#3b82f6")["ok"] is False
    assert s.tag_delete(9)["ok"] and fake.calls[-1] == ("delete", 9) and s.tag_delete(0)["ok"] is False
    assert s.card_tags_set("fr:Carte", [1, 2])["ok"] and fake.calls[-1] == ("card_tags", "fr:Carte", [1, 2])
    assert s.card_tags_set("perso-2", [])["ok"], "une carte exclusive peut aussi être étiquetée"
    n = len(fake.calls)
    for bad in [("fr:Carte", [1, 1]), ("fr:Carte", "1"), ("fr:Carte", [True]), ("nimporte", [1]), (5, [1]), ("fr:Carte", list(range(1, 60)))]:
        assert s.card_tags_set(*bad)["ok"] is False
    assert len(fake.calls) == n, "rien d'invalide ne part vers le site"
    assert [a["action"] for a in s.actions_get()["actions"]][0] == "Étiquettes d'une carte modifiées"


# ---------------------------------------------------------------- cartes masquées
def test_hidden_cards_are_local_and_validated(tmp_path):
    fake = Fake()
    s = service(tmp_path, fake)
    assert s.hidden_get() == {"ok": True, "list": []}
    assert s.hidden_set(["fr:A", "perso-2", "fr:A"], True)["list"] == ["fr:A", "perso-2"]
    assert s.hidden_set(["fr:B"], True)["list"] == ["fr:A", "perso-2", "fr:B"]
    assert s.hidden_set(["fr:A"], False)["list"] == ["perso-2", "fr:B"]
    assert service(tmp_path, fake).hidden_get()["list"] == ["perso-2", "fr:B"], "le choix est gardé d'une session à l'autre"
    for bad in [["x"], [5], "fr:A", None, ["fr:A"] * 501]:
        assert s.hidden_set(bad, True)["ok"] is False
    assert s.hidden_set(["fr:C"], "oui")["list"] == ["perso-2", "fr:B"], "seul True masque"
    assert s.actions_get()["actions"] == [], "rien n'est écrit sur le site, donc rien dans le journal"


# ---------------------------------------------------------------- plusieurs paquets d'affilée
def test_open_packs_opens_the_chosen_number_and_logs_once(tmp_path, quick):
    fake = Fake(packs=5)
    s = service(tmp_path, fake)
    r = s.open_packs(3)
    assert r["ok"] and len(r["packs"]) == 3 and r["stopped"] is None and r["wanted"] == 3 and fake.opened == 3
    assert "email" not in r["me"] and "secret@example.org" not in str(r)
    assert [a["action"] for a in s.actions_get()["actions"]] == ["3 paquet(s) ouverts d'un coup"]
    assert s.pack_seen()["ok"] and fake.calls[-1] == ("seen", 1003, "normal"), "le dernier paquet est acquitté comme à l'unité"
    assert len(s.pack_history()["packs"]) == 3


def test_open_packs_never_exceeds_the_stock_or_the_cap(tmp_path, quick):
    fake = Fake(packs=2)
    r = service(tmp_path, fake).open_packs(10)
    assert r["ok"] and len(r["packs"]) == 2 and r["wanted"] == 2
    assert service(tmp_path / "b", Fake(packs=0)).open_packs(3)["ok"] is False
    for bad in [0, -1, 21, 2.5, "3", True, None]:
        f = Fake(packs=5)
        assert service(tmp_path / f"c{bad!r}".replace("/", "_"), f).open_packs(bad)["ok"] is False and f.opened == 0


def test_open_packs_stops_when_the_site_asks_for_a_check_and_never_answers_for_the_player(tmp_path, quick):
    fake = Fake(packs=5)
    fake.defi_after_2 = True
    r = service(tmp_path, fake).open_packs(5)
    assert r["ok"] and len(r["packs"]) == 2 and r["stopped"] == "challenge" and fake.opened == 2
    f2 = Fake(packs=5, defi=True)
    r2 = service(tmp_path / "b", f2).open_packs(3)
    assert r2["ok"] is False and r2.get("challenge") is True and f2.opened == 0, "sans réponse du joueur, aucun paquet"
    r3 = service(tmp_path / "c", f2).open_packs(3, "abcDEF_123", 4)
    assert r3["ok"] and f2.proofs[0] == {"defi": "abcDEF_123", "rep": 4} and all(p is None for p in f2.proofs[1:]), "la preuve ne sert qu'une fois, pour le premier paquet"
    assert service(tmp_path / "d", Fake(defi=True)).open_packs(1, "bad id!", 1)["ok"] is False


def test_open_packs_keeps_the_packs_already_opened_when_one_fails(tmp_path, quick):
    fake = Fake(packs=5)
    fake.fail_at = 3
    r = service(tmp_path, fake).open_packs(5)
    assert r["ok"] and len(r["packs"]) == 2 and r["stopped"] == "error" and "Réseau" in r["error"] and fake.opened == 2, "pas de nouvel essai, rien de perdu"
    f1 = Fake(packs=5)
    f1.fail_at = 1
    assert service(tmp_path / "b", f1).open_packs(3)["ok"] is False


def test_new_methods_are_exposed_to_the_web():
    from server.rpc import ALLOWED
    assert {"open_packs", "tags_get", "tag_save", "tag_delete", "card_tags_set", "hidden_get", "hidden_set"} <= ALLOWED


# ---------------------------------------------------------------- cartes exclusives masquées du profil (côté site)
def test_exclusive_hide_is_a_validated_write(tmp_path):
    fake = Fake()
    fake.exclusive_hide = lambda i, on: fake.calls.append(("hide", i, on)) or {}
    s = service(tmp_path, fake)
    assert s.exclusive_hide(5, True)["masked"] is True and fake.calls[-1] == ("hide", 5, True)
    assert s.exclusive_hide(5, "oui")["masked"] is False and fake.calls[-1] == ("hide", 5, False), "seul True masque"
    n = len(fake.calls)
    for bad in ["5", 0, -3, None, True, 5.5]:
        assert s.exclusive_hide(bad, True)["ok"] is False
    assert len(fake.calls) == n and "exclusive_hide" in __import__("server.rpc", fromlist=["ALLOWED"]).ALLOWED


def test_collection_payload_gives_clean_tags_and_masked_ids():
    from wikipick.parse import parse_collection
    d = parse_collection({"champs": CHAMPS, "imgp": IMGP, "groups": [], "tags": [{"id": 4, "name": "X", "color": "#ABCDEF"}, {"id": "no"}], "masquees": [3, "x", 0, "7", None]})
    assert d["tags"] == [{"id": 4, "name": "X", "color": "#abcdef", "order": 0}] and d["masked"] == [3, 7]
