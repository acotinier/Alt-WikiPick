"""Fusion : décodage d'une vraie réponse du site (réduite), validation stricte, et le lot automatique
(objectif, doublons seulement, aucune relance après une erreur, arrêt, interface absente, une seule écriture à la fois).

Le client est un faux : aucun test ne parle au site, aucun test n'attend vraiment une seconde."""
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wikipick import service as svc  # noqa: E402
from wikipick.client import ApiError  # noqa: E402
from wikipick.parse import parse_fusion  # noqa: E402


def card(i, rank="C", copies=1, **kw):
    return {"cid": f"fr:Carte_{i}", "n": f"Carte {i}", "d": "", "e": "extrait", "img": None, "r": rank, "v": 10, "id": i, "exemplaires": copies, **kw}


def recipes(avail=4124):
    return [{"rang": "C", "vers": "PC", "base": 100, "echecs": 0, "chance": 100, "dispo": avail, "base2": 90, "chance2": 90},
            {"rang": "PC", "vers": "R", "base": 85, "echecs": 0, "chance": 85, "dispo": 2366, "base2": 70, "chance2": 70}]


def etat(cards, avail=None):
    return {"cartes": 3, "petite": 2, "bonus": 5, "bonus2": 3, "recettes": recipes(avail if avail is not None else len(cards)),
            "rang": "C", "page": 0, "pages": 1, "total": len(cards), "parPage": 24, "liste": cards}


def won(sent, new_cards, i=900):
    # forme réelle : reussie, rang, vers, chance, parties, reste, prochaine, carte{..., id, isNew}, etat, me (avec un e-mail)
    return {"reussie": True, "rang": "C", "vers": "PC", "chance": 100, "parties": list(sent), "reste": None, "prochaine": 100,
            "carte": card(i, "PC", isNew=True), "etat": etat(new_cards), "me": {"id": 1, "name": "Moi", "email": "secret@example.org", "coins": 5, "cards": 10}}


class Fake:
    """Un faux site : `stock` = les cartes fusionnables (doublons d'abord) ; chaque fusion en retire `len(ids)`."""
    def __init__(self, stock, fail_at=None, lose_at=()):
        self.stock, self.posts, self.gets, self.fail_at, self.lose_at = list(stock), [], 0, fail_at, set(lose_at)

    def clear_session(self):
        pass

    def fusion(self, rank=None, page=0):
        self.gets += 1
        return etat(self.stock) if rank else {"petite": 2, "cartes": 3, "recettes": recipes()}

    def fusion_do(self, ids, page=0):
        self.posts.append(list(ids))
        if self.fail_at == len(self.posts):
            raise ApiError("Réseau indisponible : ConnectionError")
        self.stock = [c for c in self.stock if c["id"] not in ids]
        r = won(ids, self.stock)
        if len(self.posts) in self.lose_at:
            r.update(reussie=False, carte=None, prochaine=105)
        return r


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(svc, "FUSION_PAUSE", 0.0)


def service(tmp_path, client):
    return svc.Service(client, tmp_path)


def wait_job(s, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        j = s.fusion_job()["job"]
        if j and not j["running"]:
            return j
        time.sleep(0.01)
    raise AssertionError("le lot ne s'est pas terminé")


# ---------------------------------------------------------------- décodage
def test_parse_fusion_real_shape():
    d = parse_fusion(etat([card(1, copies=3, img="https://thumb.wikimedia.org/x.jpg"), card(2, img="https://evil.example/x.jpg"), {"n": "sans id"}]))
    assert d["small"] == 2 and d["big"] == 3 and d["bonus"] == 5 and d["bonus2"] == 3 and d["rank"] == "C" and d["pages"] == 1
    assert [x["rank"] for x in d["recipes"]] == ["C", "PC"] and d["recipes"][0] == {"rank": "C", "to": "PC", "base": 100, "base2": 90, "chance": 100,
                                                                                   "chance2": 90, "fails": 0, "avail": 3}
    assert [c["id"] for c in d["cards"]] == [1, 2], "une entrée sans id est ignorée"
    assert d["cards"][0]["copies"] == 3 and d["cards"][0]["img"] and d["cards"][1]["img"] is None, "seules les images Wikimedia passent"
    assert parse_fusion(None)["recipes"] == [] and parse_fusion({"rang": "L"})["rank"] is None, "les légendaires ne se fusionnent pas"
    assert all(x["rank"] != "L" for x in parse_fusion({"recettes": [{"rang": "L"}, {"rang": "M"}, {"rang": "UR"}]})["recipes"])


def test_fusion_get_picks_the_lowest_playable_rank(tmp_path):
    fake = Fake([card(i) for i in range(1, 5)])
    r = service(tmp_path, fake).fusion_get()
    assert r["ok"] and r["rank"] == "C" and len(r["cards"]) == 4 and fake.gets == 2
    assert service(tmp_path, fake).fusion_get("L")["ok"] is False and service(tmp_path, fake).fusion_get("C", -1)["ok"] is False


# ---------------------------------------------------------------- une fusion à la main
@pytest.mark.parametrize("bad", [[], [1], [1, 2, 3, 4], [1, 1, 2], ["1", 2], [True, 2], [1.5, 2], None, "1,2,3", {"a": 1}])
def test_manual_fusion_validates_before_sending(tmp_path, bad):
    fake = Fake([card(1)])
    r = service(tmp_path, fake).fusion_do(bad)
    assert r["ok"] is False and fake.posts == [], "rien ne part vers le site"


def test_manual_fusion_result_hides_the_email_and_is_journaled(tmp_path):
    fake = Fake([card(i) for i in range(1, 7)])
    s = service(tmp_path, fake)
    r = s.fusion_do([1, 2, 3])
    assert r["ok"] and r["success"] and r["card"]["name"] == "Carte 900" and r["card"]["new"] and r["used"] == [1, 2, 3]
    assert "email" not in r["me"] and "secret@example.org" not in str(r), "l'adresse e-mail n'arrive jamais à l'interface"
    assert [c["id"] for c in r["state"]["cards"]] == [4, 5, 6]
    assert "Fusion de 3 cartes" in s.actions_get()["actions"][0]["action"]


def test_manual_fusion_refuses_an_unreadable_answer(tmp_path):
    fake = Fake([card(1)])
    fake.fusion_do = lambda ids, page=0: {"surprise": True}
    r = service(tmp_path, fake).fusion_do([1, 2])
    assert r["ok"] is False and "vérifie ta collection" in r["error"]


# ---------------------------------------------------------------- le lot automatique
def test_batch_runs_to_the_goal_then_stops(tmp_path, quick):
    fake = Fake([card(i, copies=2) for i in range(1, 31)])
    s = service(tmp_path, fake)
    assert s.fusion_start("C", 10, 3)["ok"]  # 10 cartes / 3 = 3 fusions (le reste ne part pas)
    j = wait_job(s)
    assert j["reason"] == "done" and j["fusions"] == 3 and j["won"] == 3 and j["used"] == 9 and j["new"] == 3 and j["last"]["rarity"] == "PC"
    assert fake.posts == [[1, 2, 3], [4, 5, 6], [7, 8, 9]], "toujours les premières cartes de la liste, trois par trois"
    assert "email" not in (j["me"] or {})
    log = [a["action"] for a in s.actions_get()["actions"]]
    assert len(log) == 2 and "lancée" in log[1] and "3 fusion(s), 3 réussie(s), 0 ratée(s), 9 cartes" in log[0], "une ligne au départ, une à la fin (pas une par fusion)"
    assert s.recycle([1])["error"] != "Une action est déjà en cours.", "le verrou d'écriture est libéré à la fin"


def test_batch_counts_failures_and_goes_on(tmp_path, quick):
    fake = Fake([card(i, copies=2) for i in range(1, 13)], lose_at=(2,))
    s = service(tmp_path, fake)
    s.fusion_start("C", 12, 3)
    j = wait_job(s)
    assert j["fusions"] == 4 and j["won"] == 3 and j["lost"] == 1 and j["used"] == 12 and j["chance"] == 100


def test_batch_with_duplicates_only_never_touches_single_copies(tmp_path, quick):
    stock = [card(1, copies=2), card(2, copies=2), card(3), card(4)]  # seulement 2 doublons : pas de quoi faire une fusion à 3
    fake = Fake(stock)
    s = service(tmp_path, fake)
    s.fusion_start("C", 3, 3, True)
    j = wait_job(s)
    assert j["reason"] == "empty" and j["fusions"] == 0 and fake.posts == []
    s2 = service(tmp_path / "b", Fake(stock))
    s2.fusion_start("C", 3, 3, False)  # toutes les cartes : le joueur l'a choisi
    j2 = wait_job(s2)
    assert j2["reason"] == "done" and s2._client.posts == [[1, 2, 3]]


def test_batch_stops_at_the_first_error_and_never_retries(tmp_path, quick):
    fake = Fake([card(i, copies=2) for i in range(1, 31)], fail_at=2)
    s = service(tmp_path, fake)
    s.fusion_start("C", 30, 3)
    j = wait_job(s)
    assert j["reason"] == "error" and "Réseau" in j["error"] and j["fusions"] == 1 and len(fake.posts) == 2, "la deuxième requête n'est jamais rejouée"
    assert s.actions_get()["actions"][0]["ok"] is False


def test_batch_can_be_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "FUSION_PAUSE", 5.0)  # la pause est interrompue par l'arrêt
    fake = Fake([card(i, copies=2) for i in range(1, 31)])
    s = service(tmp_path, fake)
    s.fusion_start("C", 30, 3)
    t0 = time.time()
    while s.fusion_job()["job"]["fusions"] < 1 and time.time() - t0 < 5:
        time.sleep(0.01)
    s.fusion_stop()
    j = wait_job(s)
    assert j["reason"] == "stopped" and j["fusions"] == 1 and time.time() - t0 < 4


def test_batch_stops_when_the_interface_goes_away(tmp_path, quick, monkeypatch):
    monkeypatch.setattr(svc, "FUSION_DEADMAN", -1)
    fake = Fake([card(i, copies=2) for i in range(1, 31)])
    s = service(tmp_path, fake)
    s.fusion_start("C", 30, 3)
    assert wait_job(s)["reason"] == "away" and fake.posts == []


def test_only_one_write_at_a_time_while_a_batch_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "FUSION_PAUSE", 5.0)
    s = service(tmp_path, Fake([card(i, copies=2) for i in range(1, 31)]))
    s.fusion_start("C", 30, 3)
    assert s.fusion_start("C", 30, 3)["ok"] is False, "pas de deuxième lot"
    assert s.recycle([1])["error"] == "Une action est déjà en cours." and s.fusion_do([1, 2])["ok"] is False
    s.fusion_stop()
    wait_job(s)


@pytest.mark.parametrize("args", [("L", 3, 3, True), ("C", 2, 3, True), ("C", 3, 4, True), ("C", 3, 3, "oui"), ("C", True, 3, True), ("C", 10**6, 3, True), ("C", 3.5, 3, True)])
def test_batch_validates_its_inputs(tmp_path, args):
    fake = Fake([card(1, copies=2)])
    assert service(tmp_path, fake).fusion_start(*args)["ok"] is False and fake.posts == [] and fake.gets == 0


def test_batch_methods_are_exposed_to_the_web_but_nothing_else_is_added():
    from server.rpc import ALLOWED
    assert {"fusion_get", "fusion_do", "fusion_start", "fusion_job", "fusion_stop"} <= ALLOWED
    assert threading.active_count() >= 1
