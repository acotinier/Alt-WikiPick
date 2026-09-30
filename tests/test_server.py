"""Serveur web : connexion, sessions chiffrées, liste blanche des appels, limites, événements. Aucun réseau :
le client vers wiki-pick.com est remplacé par un faux."""
import collections
import json
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from server import config  # noqa: E402
from server.app import create_app  # noqa: E402
from server.rpc import ALLOWED, DENIED  # noqa: E402
from server.runtime import Runtime  # noqa: E402
from wikipick.client import ApiError, SessionExpired, WikiPickClient  # noqa: E402
from wikipick.service import Service  # noqa: E402

DEFI = {"id": "ZheyznhTbvnkI4we", "consigne": "Clique sur la goutte",
        "choix": ['<svg viewBox="0 0 40 40"><path d="M7 7h26v26H7z" fill="#ef6f8d"/></svg>'] * 6}
IDS = {"alex": 42, "bob": 43, "zoé": 44}


class FakeClient(WikiPickClient):
    """Le site, en mémoire : mot de passe « good », une question, un profil par pseudo."""
    expired = False
    logins = []

    def __init__(self, session_file=None):
        super().__init__(session_file=session_file or "unused.json")
        self._closed = False

    def pack_challenge(self):
        return DEFI

    def login(self, login, password, defi, rep):
        FakeClient.logins.append((login, defi, rep))
        if password != "good" or defi != DEFI["id"]:
            raise ApiError("Identifiants incorrects.")
        self.set_cookies({"sid": "cookie-secret-" + login.lower()})
        return True

    def state(self):
        if FakeClient.expired or not self.cookies_dict():
            raise SessionExpired("Session expirée, reconnecte-toi.")
        name = self.cookies_dict()["sid"].split("cookie-secret-")[1]
        return {"me": {"id": IDS.get(name, 99), "name": name.capitalize(), "email": "secret@example.org", "coins": 5, "packs": 3, "defi": False}, "info": {}}

    def friends(self):
        return {"friends": [{"name": "zoé", "fav": True}], "incoming": [], "outgoing": []}

    def stream_events(self):
        yield "open", {}
        yield "message", {"from": "zoé", "to": self.state()["me"]["id"], "texte": "ne doit pas passer"}
        while not self._closed:
            time.sleep(0.02)

    def close_stream(self):
        self._closed = True


def make(tmp_path, **over):
    base = config.load({"ALTWP_DATA": str(tmp_path), "ALTWP_COOKIE_SECURE": "0", "ALTWP_SECRET": "phrase de test", "ALTWP_STATIC": str(tmp_path / "nope")})
    st = base.__class__(**{**base.__dict__, **over})
    FakeClient.expired, FakeClient.logins = False, []
    app = create_app(st, FakeClient)
    return app, TestClient(app, base_url="http://testserver")


def log_in(client, login="alex", password="good"):
    c = client.get("/api/auth/challenge").json()
    assert c["ok"] and c["challenge"]["id"] == DEFI["id"] and len(c["challenge"]["choix"]) == 6
    return client.post("/api/auth/login", json={"pending": c["pending"], "login": login, "password": password, "defi": c["challenge"]["id"], "rep": 1})


def rpc(client, method, *args):
    return client.post(f"/api/rpc/{method}", json={"args": list(args)})


def test_rpc_list_covers_every_public_method_of_service():
    public = {n for n in dir(Service) if not n.startswith("_") and callable(getattr(Service, n))}
    assert not (ALLOWED & DENIED), "une méthode ne peut pas être à la fois permise et interdite"
    assert public == ALLOWED | DENIED, ("à ranger dans server/rpc.py :", public - ALLOWED - DENIED, "inconnues :", (ALLOWED | DENIED) - public)


def test_login_flow_cookie_and_no_email_leak(tmp_path):
    app, c = make(tmp_path)
    assert c.get("/api/auth/me").json() == {"ok": False, "name": None}
    assert rpc(c, "load_me").status_code == 401 and rpc(c, "load_me").json()["expired"] is True
    bad = log_in(c, password="nope").json()
    assert bad["ok"] is False and bad["retry"] and "incorrects" in bad["error"] and "altwp" not in c.cookies
    r = log_in(c)
    assert r.json() == {"ok": True, "name": "Alex"}
    sc = r.headers["set-cookie"].lower()
    assert "altwp=" in sc and "httponly" in sc and "samesite=lax" in sc and "max-age=" in sc
    assert c.get("/api/auth/me").json() == {"ok": True, "name": "Alex"}
    me = rpc(c, "load_me").json()
    assert me["ok"] and me["me"]["name"] == "Alex" and "email" not in json.dumps(me) and "secret@" not in json.dumps(me)
    assert ("alex", DEFI["id"], 1) in FakeClient.logins


def test_credentials_and_cookies_are_never_stored_in_clear(tmp_path):
    app, c = make(tmp_path)
    log_in(c, password="good")
    blob = b"".join(p.read_bytes() for p in tmp_path.rglob("*") if p.is_file() and p.name != "secret.key")
    assert b"cookie-secret-alex" not in blob, "les cookies wiki-pick sont chiffrés dans la base"
    assert b"good" not in blob or b"cookie-secret" not in blob
    # une autre phrase secrète ne peut pas relire les sessions : le joueur doit se reconnecter
    app2 = create_app(config.load({"ALTWP_DATA": str(tmp_path), "ALTWP_SECRET": "autre phrase", "ALTWP_COOKIE_SECURE": "0"}), FakeClient)
    c2 = TestClient(app2, base_url="http://testserver")
    c2.cookies.update(c.cookies)
    assert rpc(c2, "load_me").status_code == 401


def test_unknown_method_bad_args_and_origin_check(tmp_path):
    app, c = make(tmp_path)
    log_in(c)
    assert rpc(c, "logout").status_code == 404 and rpc(c, "start_login").status_code == 404, "méthodes réservées : refusées"
    assert rpc(c, "_guard").status_code == 404 and rpc(c, "__init__").status_code == 404
    assert rpc(c, "load_me", 1, 2, 3).status_code == 422
    assert c.post("/api/rpc/load_me", json={"args": "x"}).status_code == 422
    evil = c.post("/api/rpc/load_me", json={"args": []}, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    assert c.post("/api/rpc/load_me", json={"args": []}, headers={"Origin": "http://testserver"}).status_code == 200


def test_security_headers_and_no_store(tmp_path):
    app, c = make(tmp_path)
    r = c.get("/api/auth/me")
    assert "default-src 'self'" in r.headers["content-security-policy"] and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store" and r.headers["x-frame-options"] == "DENY"
    assert c.get("/healthz").json() == {"ok": True, "players": 0}


def test_private_instance_and_capacity(tmp_path):
    app, c = make(tmp_path, allowed_users=frozenset({"alex"}))
    assert log_in(c, "alex").json()["ok"]
    priv = log_in(c, "bob").json()
    assert priv == {"ok": False, "error": "Cette instance est privée."}
    app, c = make(tmp_path / "b", max_users=1)
    assert log_in(c, "alex").json()["ok"]
    full = log_in(TestClient(app, base_url="http://testserver"), "bob").json()
    assert full == {"ok": False, "error": "Cette instance est pleine."}
    assert log_in(TestClient(app, base_url="http://testserver"), "alex").json()["ok"], "un compte déjà présent peut se reconnecter"


def test_login_attempts_are_rate_limited(tmp_path):
    app, c = make(tmp_path)
    codes = [log_in(c, "alex", "nope").status_code for _ in range(8)]
    assert codes[:6] == [200] * 6 and 429 in codes[6:], codes


def test_logout_keeps_other_devices_until_the_last_one(tmp_path):
    app, phone = make(tmp_path)
    laptop = TestClient(app, base_url="http://testserver")
    assert log_in(phone).json()["ok"] and log_in(laptop).json()["ok"]
    assert rpc(phone, "load_me").json()["ok"] and rpc(laptop, "load_me").json()["ok"]
    assert phone.post("/api/auth/logout").json() == {"ok": True}
    assert rpc(phone, "load_me").status_code == 401
    assert rpc(laptop, "load_me").json()["ok"], "l'autre appareil reste connecté"
    assert laptop.post("/api/auth/logout").json() == {"ok": True}
    assert app.state.store.count_accounts() == 0, "plus aucun appareil : les cookies wiki-pick sont oubliés"
    assert rpc(laptop, "load_me").status_code == 401


def test_expired_upstream_session_forces_a_new_login(tmp_path):
    app, c = make(tmp_path)
    log_in(c)
    assert rpc(c, "load_me").json()["ok"]
    FakeClient.expired = True
    r = rpc(c, "load_me").json()
    assert r["ok"] is False and r["expired"] is True
    FakeClient.expired = False
    assert rpc(c, "load_me").status_code == 401, "le compte est oublié : il faut se reconnecter"
    assert app.state.store.count_accounts() == 0


def test_rpc_is_rate_limited_per_player(tmp_path):
    app, c = make(tmp_path, rpc_per_minute=10)
    log_in(c)
    codes = [rpc(c, "friends_list").status_code for _ in range(12)]
    assert codes[:10] == [200] * 10 and codes[10:] == [429, 429]


def test_players_do_not_share_data(tmp_path):
    app, a = make(tmp_path)
    b = TestClient(app, base_url="http://testserver")
    log_in(a, "alex"); log_in(b, "bob")
    assert rpc(a, "prefs_set", "sound", True).json()["ok"]
    assert rpc(a, "prefs_get").json()["prefs"] == {"sound": True}
    assert rpc(b, "prefs_get").json()["prefs"] == {}, "les préférences sont par joueur"
    assert (tmp_path / "users" / "42" / "prefs.json").is_file() and (tmp_path / "users" / "43").is_dir()


def test_export_csv_needs_a_loaded_collection_and_neutralizes_formulas(tmp_path):
    app, c = make(tmp_path)
    log_in(c)
    assert c.get("/api/export.csv").status_code == 404
    cache = tmp_path / "users" / "42" / "collection_cache.json"
    cache.write_text(json.dumps({"cards": [{"cid": "fr:X", "name": "=cmd()", "rarity": "C", "reads": 5, "copies": 2, "shiny": False, "locked": False, "lang": "fr", "url": "https://fr.wikipedia.org/wiki/X"}],
                                 "names": {"C": "Commune"}}), encoding="utf-8")
    r = c.get("/api/export.csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.content.startswith("﻿".encode("utf-8"))
    assert "'=cmd()" in r.text and "Commune" in r.text


def serve(app):
    """Un vrai serveur uvicorn sur un port libre : le client de test de Starlette ne sait pas lire un flux infini."""
    import contextlib
    import socket

    import uvicorn

    @contextlib.contextmanager
    def run():
        with socket.socket() as sk:
            sk.bind(("127.0.0.1", 0))
            port = sk.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        deadline = time.time() + 10
        while not server.started and time.time() < deadline:
            time.sleep(0.05)
        try:
            yield port
        finally:
            server.should_exit = True
            t.join(10)
    return run()


def test_events_stream_carries_only_the_filtered_events(tmp_path):
    import httpx
    app, c = make(tmp_path)
    log_in(c)
    got = []
    with serve(app) as port:
        with httpx.stream("GET", f"http://127.0.0.1:{port}/api/events", cookies={"altwp": c.cookies["altwp"]}, timeout=10) as r:
            assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream") and r.headers["content-encoding"] == "identity"
            name = None
            for line in r.iter_lines():
                if line.startswith("event:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("data:") and name:
                    got.append((name, json.loads(line.split(":", 1)[1])))
                    if name == "msg":
                        break
        deadline = time.time() + 5
        while app.state.hub.get(42).watchers and time.time() < deadline:
            time.sleep(0.05)
        assert app.state.hub.get(42).watchers == 0, "le navigateur parti, plus personne n'écoute"
    assert ("live", "live") in got
    msg = [d for n, d in got if n == "msg"][0]
    assert msg == {"event": "message", "data": {"from": "zoé"}}, "seuls les champs de la liste blanche sortent"


def test_two_devices_each_get_every_event():
    class Fake:
        def __init__(self):
            self.queue = []

        def poll_events(self):
            out, self.queue = self.queue, []
            return {"ok": True, "state": "live", "events": out}

    svc = Fake()
    rt = Runtime(1, "Alex", svc)
    rt.subs.extend([collections.deque(), collections.deque()])
    svc.queue = [{"event": "message", "data": {"from": "zoé"}}, {"event": "notify", "data": {"id": 1}}]
    rt.pump()
    assert [e["event"] for e in rt.subs[0]] == ["message", "notify"] and [e["event"] for e in rt.subs[1]] == ["message", "notify"]
    assert rt.state == "live"


def test_stream_stops_when_nobody_listens_and_idle_players_are_released(tmp_path, monkeypatch):
    import server.runtime as runtime
    app, c = make(tmp_path)
    log_in(c)
    hub = app.state.hub
    rt = hub.get(42)
    stopped = []
    monkeypatch.setattr(rt.service, "stop_stream", lambda: stopped.append(1))
    rt.unwatched_since -= runtime.STREAM_GRACE + 1
    hub.reap()
    assert stopped and hub.count() == 1
    rt.last -= runtime.IDLE_DROP + 1
    hub.reap()
    assert hub.count() == 0, "un joueur inactif ne garde ni mémoire ni thread"
    assert rpc(c, "load_me").json()["ok"], "il est recréé à la demande, sans se reconnecter"


def test_spa_fallback_and_path_traversal(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    (dist / "assets" / "a.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    app, c = make(tmp_path / "d", static_dir=dist)
    assert "<title>x</title>" in c.get("/market/auctions").text and c.get("/market/auctions").headers["cache-control"] == "no-cache"
    js = c.get("/assets/a.js")
    assert js.headers["cache-control"].endswith("immutable") and js.headers["content-type"].startswith("text/javascript")
    assert c.get("/../secret.txt").text != "secret" and c.get("/%2e%2e/secret.txt").text != "secret"
    assert c.get("/api/inconnu").status_code in (404, 405)
