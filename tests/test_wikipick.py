import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wikipick.client import ApiError, SessionExpired, WikiPickClient  # noqa: E402
from wikipick.parse import (compute_stats, expand_group, expand_pack_card, parse_auction, parse_collection,  # noqa: E402
                            parse_history, parse_notification, parse_ranking, parse_trade, wiki_url)
from wikipick.stream import parse_sse  # noqa: E402

CHAMPS = ["cid", "n", "d", "img", "r", "v", "nl", "lang", "locked"]
IMGP = ["https://thumb.wikimedia.org/wikipedia/commons/thumb/", "https://upload.wikimedia.org/wikipedia/commons/"]

PAYLOAD = {
    "champs": CHAMPS,
    "imgp": IMGP,
    "tags": [{"id": 7, "name": "Acteur", "color": "#fff"}],
    "rank": {"rank": 232, "total": 6898, "points": 14374, "cards": 3904, "toNext": 15, "nextName": "rival"},
    "groups": [
        # ligne calquée sur les données réelles observées
        ["fr:Rudná_(district_de_Prague-Ouest)", "Rudná (district de Prague-Ouest)", "commune tchèque",
         "05/5e/Rudn%C3%A1.JPG/960px-Rudn%C3%A1.JPG", "C", "173", "1", "fr", "false", [5791707], [], {}],
        ["fr:Rembrandt", "Rembrandt", "peintre", "10/aa/R.jpg", "L", "30000001", "1", "fr", "false",
         [1, 2, 3], [7], {"sh": 1}],
        ["fr:Sans_image", "Sans image", "", "", "PC", "5", "0", "fr", True, [], [], None],
    ],
}


def test_image_prefix_index_is_resolved():
    c = expand_group(PAYLOAD["groups"][0], CHAMPS, IMGP)
    assert c["img"] == IMGP[0] + "5/5e/Rudn%C3%A1.JPG/960px-Rudn%C3%A1.JPG"
    c2 = expand_group(PAYLOAD["groups"][1], CHAMPS, IMGP)
    assert c2["img"] == IMGP[1] + "0/aa/R.jpg"


def test_fields_types_copies_tags_extra():
    c = expand_group(PAYLOAD["groups"][1], CHAMPS, IMGP)
    assert c["reads"] == 30000001 and c["copies"] == 3 and c["tags"] == [7] and c["shiny"] is True
    d = expand_group(PAYLOAD["groups"][2], CHAMPS, IMGP)
    assert d["img"] is None and d["locked"] is True and d["copies"] == 1 and d["shiny"] is False


def test_untrusted_image_host_is_dropped():
    row = ["fr:X", "X", "", "1https://evil.example/x.png", "C", "1", "1", "fr", "false", [1], [], {}]
    assert expand_group(row, CHAMPS, ["https://evil.example/", "https://evil.example/"])["img"] is None


def test_wiki_url():
    assert wiki_url("fr:Rudná_(district)") == "https://fr.wikipedia.org/wiki/Rudn%C3%A1_(district)"
    assert wiki_url("pas-un-cid") is None


def test_parse_and_stats():
    parsed = parse_collection(PAYLOAD)
    assert len(parsed["cards"]) == 3 and parsed["rank"]["rank"] == 232
    stats = compute_stats(parsed["cards"], {"L": "Légendaire", "C": "Commune", "PC": "Inhabituelle"})
    assert stats["unique"] == 3 and stats["copies"] == 5 and stats["duplicates"] == 1 and stats["extra_copies"] == 2
    assert [r["code"] for r in stats["rarities"]] == ["L", "PC", "C"]  # du plus rare au plus commun
    assert stats["rarities"][0]["label"] == "Légendaire"
    assert stats["top_reads"][0]["cid"] == "fr:Rembrandt" and stats["shiny"] == 1 and stats["locked"] == 1


def _resp(status=200, body=None, text=None):
    r = mock.Mock(status_code=status)
    if body is None and text is not None:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = body
    return r


def test_client_session_roundtrip(tmp_path):
    c = WikiPickClient(session_file=tmp_path / "s.json")
    c.set_cookies({"sid": "abc"}); c.set_user_agent("UA-test"); c.save_session()
    c2 = WikiPickClient(session_file=tmp_path / "s.json")
    assert c2.load_session() and c2.cookies_dict() == {"sid": "abc"}
    assert c2.http.headers["User-Agent"] == "UA-test"
    c2.clear_session()
    assert not (tmp_path / "s.json").exists()


def test_client_current_user_and_errors(tmp_path):
    c = WikiPickClient(session_file=tmp_path / "s.json")
    with mock.patch.object(c.http, "get", return_value=_resp(body={"me": {"id": 5, "name": "x"}})):
        assert c.current_user()["id"] == 5
    with mock.patch.object(c.http, "get", return_value=_resp(body={"me": None})):
        assert c.current_user() is None
    with mock.patch.object(c.http, "get", return_value=_resp(status=401)):
        with pytest.raises(SessionExpired):
            c.state()
        assert c.current_user() is None
    with mock.patch.object(c.http, "get", return_value=_resp(status=500)):
        with pytest.raises(ApiError):
            c.collection()
    with mock.patch.object(c.http, "get", return_value=_resp(text="<html>")):
        with pytest.raises(ApiError):
            c.collection()


# cartes d'une vraie réponse de /api/open (champs inutiles retirés)
PACK_CARDS = [
    {"cid": "fr:Gleeph", "lang": "fr", "n": "Gleeph", "d": "", "r": "PC", "v": 1659, "id": 5813894, "isNew": True,
     "img": "https://upload.wikimedia.org/wikipedia/fr/4/47/Gleeph_logo.png?utm_source=fr.wikipedia.org"},
    {"cid": "fr:Le_Choucas", "n": "Le Choucas", "d": "série de bande dessinée", "r": "C", "v": 295,
     "id": 5813895, "isNew": False, "img": None},
    {"cid": "fr:X", "n": "X", "r": "L", "v": 1, "id": 1, "sh": 1, "img": "https://evil.example/x.png"},
]


def test_expand_pack_card():
    a, b, c = (expand_pack_card(x) for x in PACK_CARDS)
    assert a["reads"] == 1659 and a["new"] is True and a["ids"] == [5813894] and a["img"].startswith("https://upload.wikimedia.org/")
    assert b["img"] is None and b["new"] is False and b["url"] == "https://fr.wikipedia.org/wiki/Le_Choucas"
    assert c["shiny"] is True and c["img"] is None  # hôte d'image non autorisé


def test_client_open_pack_posts_sait_and_surfaces_site_error(tmp_path):
    c = WikiPickClient(session_file=tmp_path / "s.json")
    with mock.patch.object(c.http, "post", return_value=_resp(body={"cards": [], "me": {}})) as post:
        assert c.open_pack() == {"cards": [], "me": {}}
        assert post.call_args.args[0].endswith("/api/open") and post.call_args.kwargs["json"] == {"sait": 1}
    with mock.patch.object(c.http, "post", return_value=_resp(status=429, body={"error": "Trop vite."})):
        with pytest.raises(ApiError, match="Trop vite"):
            c.open_pack()
    with mock.patch.object(c.http, "post", return_value=_resp(status=403, body={"error": "Défi requis."})):
        with pytest.raises(ApiError):  # 403 sur écriture : erreur métier, pas session expirée
            c.open_pack()
    with mock.patch.object(c.http, "post", return_value=_resp(status=401)):
        with pytest.raises(SessionExpired):
            c.open_pack()


# ---- temps réel ---------------------------------------------------------
def test_parse_sse_events_comments_and_bad_json():
    lines = [": keepalive", "", "event: notify", 'data: {"to": 1}', "", "data: pas du json", "",
             'data: {"a":', 'data: 2}', "", "event: sans-donnees", ""]
    assert list(parse_sse(lines)) == [("notify", {"to": 1}), ("message", {"a": 2})]


def test_parse_auction_card_and_lot():
    a = parse_auction({"id": "7", "card": {"cid": "fr:X", "n": "X", "r": "R", "v": 5, "img": "https://evil.example/a.png"},
                       "price": 120, "min": 130, "bids": 3, "leader": "bob", "seller": "eve", "leading": 1, "endsAt": 1790000000.5})
    assert a["id"] == 7 and a["card"]["reads"] == 5 and a["card"]["img"] is None and a["lot"] is None
    assert a["price"] == 120 and a["leading"] is True and a["mine"] is False and a["ends_at"] == 1790000000.5 and a["status"] == "live"
    lot = parse_auction({"id": 8, "lot": {"n": 2, "nom": "Mon <b>lot</b>", "cartes": [{"cid": "fr:A", "n": "A"}, "bizarre"]}})
    assert lot["card"] is None and lot["lot"]["n"] == 2 and len(lot["lot"]["cards"]) == 1 and lot["price"] == 0


def test_parse_notification():
    n = parse_notification({"id": 4, "ntype": "outbid", "text": "Surenchère", "tone": "bad", "link": "auction:5", "created": 1.5})
    assert n == {"id": 4, "type": "outbid", "text": "Surenchère", "tone": "bad", "link": "auction:5", "read": False, "created": 1.5}
    assert parse_notification({"tone": "bizarre"})["tone"] == "" and parse_notification({})["type"] == ""


class _Sse(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):
        self.send_response(self.status); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        if self.status != 200:
            return
        self.wfile.write(b': keepalive\n\nevent: notify\ndata: {"to": 1, "text": "Yo"}\n\n'); self.wfile.flush()
        time.sleep(0.6)  # le premier événement doit arriver pendant cette pause, pas après
        self.wfile.write(b'event: auction\r\ndata: {"what": "bid", "id": 5}\r\n\r\n'); self.wfile.flush()

    def log_message(self, *args):
        pass


def _serve(status):
    handler = type("H", (_Sse,), {"status": status})
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_stream_events_arrive_as_sent(tmp_path):
    srv = _serve(200)
    c = WikiPickClient(session_file=tmp_path / "s.json")
    t0, seen = time.time(), []
    with mock.patch("wikipick.client.BASE", f"http://127.0.0.1:{srv.server_port}"):
        for ev, data in c.stream_events():
            seen.append((ev, data, time.time() - t0))
    srv.shutdown()
    assert [(e, d) for e, d, _ in seen] == [("open", {}), ("notify", {"to": 1, "text": "Yo"}), ("auction", {"what": "bid", "id": 5})]
    assert seen[1][2] < 0.4, "pas de mise en tampon : l'événement doit arriver avant la fin de la pause du serveur"


def test_stream_401_is_session_expired_and_close_is_safe(tmp_path):
    srv = _serve(401)
    c = WikiPickClient(session_file=tmp_path / "s.json")
    with mock.patch("wikipick.client.BASE", f"http://127.0.0.1:{srv.server_port}"):
        with pytest.raises(SessionExpired):
            list(c.stream_events())
    srv.shutdown()
    c.close_stream()  # sans flux ouvert : ne fait rien


# ---- LiveStream : filtrage, reconnexion, journal --------------------------
from wikipick.live import LiveStream  # noqa: E402


def test_live_push_whitelist_and_ownership():
    live = LiveStream(client=None, my_id=lambda: 1)
    live.push("notify", {"to": 2, "text": "pour un autre"})
    live.push("notify", {"to": 1, "id": 3, "text": "Salut", "secret": "x"})
    live.push("feed", {"to": 1, "what": "post"})  # événement que l'appli n'utilise pas
    live.push("auction", {"what": "bid", "id": 5, "price": 10})  # onglet Marché fermé
    assert live.poll() == [{"event": "notify", "data": {"id": 3, "text": "Salut"}}]
    live.watch_market = True
    live.push("auction", {"what": "bid", "id": 5, "price": 10, "interne": 1})
    assert live.poll() == [{"event": "auction", "data": {"what": "bid", "id": 5, "price": 10}}]
    LiveStream(client=None, my_id=lambda: None).push("notify", {"text": "sans destinataire"})  # ne plante pas, n'accepte rien


class _FakeClient:
    def __init__(self, run):
        self.run, self.closed = run, 0

    def stream_events(self):
        return self.run()

    def close_stream(self):
        self.closed += 1


def _wait(cond, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout and not cond():
        time.sleep(0.02)
    return cond()


def test_live_thread_delivers_then_stops(tmp_path):
    def run():
        yield "open", {}
        yield "notify", {"to": 1, "text": "Bravo", "cache": "valeur-privee"}
    log = tmp_path / "stream.log"
    live = LiveStream(_FakeClient(run), my_id=lambda: 1, log_file=log)
    live.start()
    assert _wait(lambda: live.state == "live" or live._events)
    got = []
    assert _wait(lambda: got.extend(live.poll()) or got)
    assert got == [{"event": "notify", "data": {"text": "Bravo"}}]
    live.stop()
    assert live.state == "down" and live._thread.join(2) is None and not live._thread.is_alive()
    text = log.read_text(encoding="utf-8")
    assert "notify: cache,text,to" in text and "valeur-privee" not in text and "Bravo" not in text


def test_live_session_expired_ends_thread():
    def run():
        raise SessionExpired("fini")
        yield  # pragma: no cover
    live = LiveStream(_FakeClient(run), my_id=lambda: 1)
    live.start()
    got = []
    assert _wait(lambda: got.extend(live.poll()) or got)
    assert got == [{"event": "expired", "data": {}}]
    live._thread.join(2)
    assert not live._thread.is_alive()


def test_api_exposes_only_methods(tmp_path, monkeypatch):
    """pywebview parcourt récursivement tous les attributs publics non callables de l'objet js_api (fenêtre .NET
    comprise) sur le fil de l'interface : un attribut public de trop = interface figée ~30 s au lancement."""
    import importlib
    import types
    monkeypatch.setenv("APPDATA", str(tmp_path))  # jamais le vrai dossier de données de l'utilisateur
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setitem(sys.modules, "webview", types.ModuleType("webview"))
    api = importlib.import_module("desktop.app").Api()
    public = [k for k, v in vars(api).items() if not k.startswith("_") and not callable(v)]
    assert public == [], f"attributs publics exposés à pywebview : {public} (les préfixer par _)"


def test_client_auctions_query_by_scope(tmp_path):
    c = WikiPickClient(session_file=tmp_path / "s.json")
    with mock.patch.object(c.http, "get", return_value=_resp(body={"items": []})) as get:
        c.auctions("live", 2, "rembrandt", ["SR", "L"], "prixbas", "lots")
        url = get.call_args.args[0]
        assert "scope=live" in url and "page=2" in url and "q=rembrandt" in url and "tri=prixbas" in url
        assert "r=SR%2CL" in url and "t=lots" in url
        c.auctions("mine", 5, "ignoré", ["C"], "prix", "cartes")  # mine / bidding : le site n'envoie que le scope
        assert get.call_args.args[0].endswith("/api/auctions?scope=mine")
        c.auctions("bidding")
        assert get.call_args.args[0].endswith("/api/auctions?scope=bidding")


# ---- classement, échanges, historique ---------------------------------------
def test_parse_ranking():
    r = parse_ranking({"points": {"M": 5000, "L": "900"}, "diamant": 12000, "regle": "acquis", "reste": 3600.5,
                       "top": [{"rank": 1, "name": "Ada <b>x</b>", "guild": "ABC", "gcouleur": "#f00", "me": False, "chroma": 2, "mythic": 1,
                                "legend": 3, "ultra": 4, "cards": 99, "points": 12345}, "bizarre", {"rank": "2", "name": "Moi", "me": 1}]})
    assert r["points"] == {"M": 5000, "L": 900} and r["chroma_points"] == 12000 and r["rule"] == "acquis" and r["reset_in"] == 3600
    assert len(r["top"]) == 2 and r["top"][0]["name"] == "Ada <b>x</b>" and r["top"][0]["points"] == 12345
    assert r["top"][1]["me"] is True and r["top"][1]["rank"] == 2 and r["top"][1]["cards"] == 0
    assert "gcouleur" not in r["top"][0]  # jamais de style venu du site
    assert parse_ranking({})["top"] == []


def test_parse_trade_is_seen_from_the_player():
    card = lambda n: {"cid": "fr:" + n, "n": n, "r": "R", "v": 10}  # noqa: E731
    incoming = parse_trade({"id": 5, "incoming": True, "from": "ami", "to": "moi", "give": [card("Offerte")], "take": [card("Demandée")],
                            "giveCoins": 10, "takeCoins": 20, "status": "pending", "message": "Salut", "created": 5.5})
    # reçue : ce que l'ami « prend » est ce que JE donne
    assert incoming["other"] == "ami" and incoming["give"][0]["name"] == "Demandée" and incoming["get"][0]["name"] == "Offerte"
    assert incoming["give_coins"] == 20 and incoming["get_coins"] == 10 and incoming["valid"] is True
    sent = parse_trade({"id": 6, "incoming": False, "from": "moi", "to": "ami2", "give": [card("A")], "take": [], "valid": False, "status": "declined"})
    assert sent["other"] == "ami2" and sent["give"][0]["name"] == "A" and sent["get"] == [] and sent["valid"] is False and sent["status"] == "declined"


def test_parse_history_card_and_lot():
    a = parse_history({"cid": "fr:X", "title": "Xavier", "rarity": "SR", "img": "https://upload.wikimedia.org/a.png", "price": 250,
                       "vente": True, "buyer": "bob", "ts": 1790000000})
    assert a["card"]["name"] == "Xavier" and a["card"]["rarity"] == "SR" and a["sold"] is True and a["who"] == "bob" and a["price"] == 250
    b = parse_history({"cid": "fr:Y", "title": "Y", "price": 5, "vente": False, "seller": "", "ts": 1})
    assert b["sold"] is False and b["who"] == "un bot" and parse_history({"vente": True})["who"] == "un joueur"
    lot = parse_history({"lot": {"n": 2, "nom": "Lot", "cartes": [{"cid": "fr:Z", "n": "Z"}]}, "price": 9})
    assert lot["card"] is None and lot["lot"]["n"] == 2 and lot["lot"]["cards"][0]["name"] == "Z"


def test_client_history_trades_ranking_urls(tmp_path):
    c = WikiPickClient(session_file=tmp_path / "s.json")
    with mock.patch.object(c.http, "get", return_value=_resp(body={})) as get:
        c.history("purchases", 3); assert get.call_args.args[0].endswith("/api/purchases?page=3")
        c.history("ventes"); assert get.call_args.args[0].endswith("/api/ventes?page=0")
        c.trades("sent"); assert get.call_args.args[0].endswith("/api/trades?box=sent")
        c.ranking("mois"); assert get.call_args.args[0].endswith("/api/ranking?periode=mois")


# ---- stockage local, préférences, journal des paquets ---------------------------
def _api(tmp_path, monkeypatch):
    """Api réelle, mais dans un dossier temporaire (jamais le vrai dossier de données de l'utilisateur)."""
    import importlib
    import types
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setitem(sys.modules, "webview", types.ModuleType("webview"))
    return importlib.import_module("desktop.app").Api()


def test_json_store_is_tolerant_and_atomic(tmp_path):
    from wikipick.store import JsonStore
    st = JsonStore(tmp_path / "a.json", [])
    assert st.read() == []  # absent
    (tmp_path / "a.json").write_text("{pas du json", encoding="utf-8"); assert st.read() == []  # abîmé
    (tmp_path / "a.json").write_text('{"un": "dict"}', encoding="utf-8"); assert st.read() == []  # mauvais type
    st.write([1, 2]); assert st.read() == [1, 2] and not list(tmp_path.glob("*.tmp"))
    default = {"k": 1}
    d = JsonStore(tmp_path / "b.json", default).read(); d["k"] = 2
    assert default == {"k": 1}, "la valeur par défaut ne doit jamais être modifiée par un appelant"


def test_prefs_whitelist(tmp_path, monkeypatch):
    a = _api(tmp_path, monkeypatch)
    assert a.prefs_get() == {"ok": True, "prefs": {}}
    assert a.prefs_set("sound", True)["ok"] and a.prefs_set("market_view", "list")["ok"]
    for bad in (("sound", "oui"), ("market_view", "carre"), ("inconnu", 1), ("market_sort", "<script>")):
        assert a.prefs_set(*bad)["ok"] is False
    assert a.prefs_get()["prefs"] == {"sound": True, "market_view": "list"}


def test_open_pack_is_journaled_and_capped(tmp_path, monkeypatch):
    a = _api(tmp_path, monkeypatch)
    me = {"id": 1, "name": "Moi", "email": "secret@example.org", "packs": 2}
    a._client.state = lambda: {"me": me, "info": {}}
    a._client.open_pack = lambda proof=None: {"cards": [{"cid": "fr:A", "n": "A", "r": "R", "v": 5, "id": 1, "isNew": True, "img": None, "e": "long extrait"}], "me": me}
    r = a.open_pack()
    assert r["ok"] and "email" not in r["me"]
    hist = a.pack_history()["packs"]
    assert len(hist) == 1 and hist[0]["cards"][0]["name"] == "A" and hist[0]["cards"][0]["new"] is True and hist[0]["ts"] > 0
    raw = (tmp_path / "WikiPickDesktop" / "packs_history.json").read_text(encoding="utf-8")
    assert "secret@example.org" not in raw and "long extrait" not in raw, "le journal ne garde que le strict nécessaire"
    import importlib
    mod = importlib.import_module("wikipick.service")
    monkeypatch.setattr(mod, "PACK_HISTORY_MAX", 3)
    for _ in range(5):
        a.open_pack()
    assert len(a.pack_history()["packs"]) == 3


# ---- vérification « es-tu un robot ? » avant un paquet : le joueur répond, l'appli ne fait que transmettre ----
DEFI_SAMPLE = {  # vraie réponse de GET /api/defi fournie par l'utilisateur
    "id": "ZheyznhTbvnkI4we", "consigne": "Clique sur la goutte",
    "choix": [
        '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M7 7h26v26H7z" fill="#ef6f8d" transform="rotate(8 20 20)"/></svg>',
        '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 3c8 10 12 15 12 20a12 12 0 01-24 0c0-5 4-10 12-20z" fill="#40bd8f" transform="rotate(-2 20 20)"/></svg>',
        '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M16 4h8v12h12v8H24v12h-8V24H4v-8h12z" fill="#a78bfa" transform="rotate(-12 20 20)"/></svg>',
        '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 3l5 11 12 1-9 8 3 12-11-6-11 6 3-12-9-8 12-1z" fill="#40bd8f" transform="rotate(-10 20 20)"/></svg>',
        '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 35C6 26 3 19 7 13c3-5 10-4 13 2 3-6 10-7 13-2 4 6 1 13-13 22z" fill="#40bd8f" transform="rotate(-21 20 20)"/></svg>',
        '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M27 5a9 9 0 00-8 12L5 31v5h6v-4h4v-4h4l2-2a9 9 0 006-21z" fill="#4aa7e6" transform="rotate(19 20 20)"/></svg>',
    ],
}


def test_parse_pack_challenge_keeps_only_simple_shapes():
    from wikipick.parse import parse_pack_challenge
    q = parse_pack_challenge(DEFI_SAMPLE)
    assert q["id"] == "ZheyznhTbvnkI4we" and q["consigne"] == "Clique sur la goutte" and len(q["choix"]) == 6
    assert q["choix"][1] == {"viewBox": "0 0 40 40", "shapes": [{"tag": "path", "attrs": {
        "d": "M20 3c8 10 12 15 12 20a12 12 0 01-24 0c0-5 4-10 12-20z", "fill": "#40bd8f", "transform": "rotate(-2 20 20)"}}]}
    evil = [
        '<svg viewBox="0 0 40 40"><path d="M0 0z" onload="alert(1)"/></svg>',  # gestionnaire d'événement
        '<svg viewBox="0 0 40 40"><script>alert(1)</script></svg>',  # script
        '<svg viewBox="0 0 40 40"><image href="https://evil.example/x.png"/></svg>',  # ressource externe
        '<svg viewBox="0 0 40 40"><path d="M0 0z" style="fill:url(https://evil.example)"/></svg>',  # style
        '<svg viewBox="0 0 40 40"><path d="M0 0z" fill="url(#x)"/></svg>',  # référence
        '<!DOCTYPE x [<!ENTITY a "aaaa">]><svg viewBox="0 0 40 40"><path d="&a;"/></svg>',  # entités
        '<svg viewBox="0 0 40 40"><foreignObject><div/></foreignObject></svg>', '<div>pas un svg</div>', '<svg', 42, None,
    ]
    q = parse_pack_challenge({"id": "abc", "consigne": "x", "choix": evil})
    assert q["choix"] == [None] * len(evil), "tout pictogramme douteux est jeté en entier"
    for bad_id in (None, "", "a" * 65, "abc/../x", 12):
        assert parse_pack_challenge({"id": bad_id, "choix": []}) is None


def test_client_pack_challenge_and_proof_payload(tmp_path):
    c = WikiPickClient(session_file=tmp_path / "s.json")
    with mock.patch.object(c.http, "get", return_value=_resp(body=DEFI_SAMPLE)) as get:
        assert c.pack_challenge()["id"] == "ZheyznhTbvnkI4we" and get.call_args.args[0].endswith("/api/defi")
    with mock.patch.object(c.http, "post", return_value=_resp(body={"cards": [], "me": {}})) as post:
        c.open_pack({"defi": "ZheyznhTbvnkI4we", "rep": 1})
        assert post.call_args.kwargs["json"] == {"sait": 1, "defi": "ZheyznhTbvnkI4we", "rep": 1}, "le corps exact du site"


def test_open_pack_asks_the_player_when_the_site_wants_a_check(tmp_path, monkeypatch):
    a = _api(tmp_path, monkeypatch)
    me = {"id": 1, "name": "Moi", "packs": 2, "defi": True}
    sent = []
    a._client.state = lambda: {"me": me, "info": {}}
    a._client.open_pack = lambda proof=None: sent.append(proof) or {"cards": [], "me": {**me, "defi": False}}
    a._client.pack_challenge = lambda: DEFI_SAMPLE
    r = a.open_pack()
    assert r["ok"] is False and r["challenge"] is True and sent == [], "sans réponse du joueur, rien ne part"
    q = a.pack_challenge()
    assert q["ok"] and q["challenge"]["id"] == "ZheyznhTbvnkI4we" and len(q["challenge"]["choix"]) == 6
    assert "answer" not in str(q) and "rep" not in q["challenge"], "l'appli ne propose jamais de réponse"
    for bad in (("ZheyznhTbvnkI4we", 12), ("ZheyznhTbvnkI4we", "1"), ("ZheyznhTbvnkI4we", True), ("../x", 1), (7, 1)):
        assert a.open_pack(*bad)["ok"] is False
    assert sent == []
    r = a.open_pack("ZheyznhTbvnkI4we", 1)
    assert r["ok"] and sent == [{"defi": "ZheyznhTbvnkI4we", "rep": 1}] and r["me"]["defi"] is False
    me["defi"] = False
    a.open_pack("ZheyznhTbvnkI4we", 1)
    assert sent[-1] is None, "pas de vérification demandée : on n'envoie pas de preuve"
    a._client.pack_challenge = lambda: {"id": "abc", "choix": "pas une liste"}
    assert a.pack_challenge()["challenge"]["choix"] == []
    a._client.pack_challenge = lambda: {"consigne": "sans id"}
    assert a.pack_challenge()["ok"] is False


def test_load_me_exposes_only_game_numbers(tmp_path, monkeypatch):
    a = _api(tmp_path, monkeypatch)
    info = {"odds": {"M": 0.1, "C": 100, "x": "texte"}, "bank": {"C": 1, "UR": 25}, "shinyOdds": 0.01, "perPack": 5,
            "shop": [{"prix": "secret"}], "oauth": ["google"], "odds_bad": True}
    a._client.state = lambda: {"me": {"id": 1, "name": "Moi", "email": "e@x.y"}, "info": {**info, "names": {"C": "Commune"}}}
    r = a.load_me()
    assert r["info"] == {"odds": {"M": 0.1, "C": 100}, "bank": {"C": 1, "UR": 25}, "shinyOdds": 0.01, "perPack": 5}
    assert "email" not in r["me"] and r["names"] == {"C": "Commune"}


def test_live_forwards_new_auction_of_watched_card_even_when_market_closed():
    live = LiveStream(client=None, my_id=lambda: 1)
    live.watch_cids = frozenset({"fr:Rembrandt"})
    live.push("auction", {"what": "new", "id": 7, "cid": "fr:Autre"})  # pas surveillée
    live.push("auction", {"what": "bid", "id": 7, "cid": "fr:Rembrandt", "price": 5})  # surveillée, mais ce n'est pas une mise en vente
    assert live.poll() == []
    live.push("auction", {"what": "new", "id": 8, "cid": "fr:Rembrandt", "prive": "x"})
    assert live.poll() == [{"event": "auction", "data": {"what": "new", "id": 8, "cid": "fr:Rembrandt"}}]


def test_watch_list_is_validated_persisted_and_feeds_the_stream(tmp_path, monkeypatch):
    a = _api(tmp_path, monkeypatch)
    assert a.watch_get() == {"ok": True, "list": []}
    r = a.watch_set("fr:Rembrandt", "Rembrandt <b>x</b>", True)
    assert r["ok"] and r["list"] == [{"cid": "fr:Rembrandt", "name": "Rembrandt <b>x</b>"}] and a._live.watch_cids == {"fr:Rembrandt"}
    assert a.watch_set("fr:Rembrandt", "autre nom", True)["list"][0]["name"] == "autre nom", "pas de doublon"
    assert a.watch_set("pas-un-cid", "x", True)["ok"] is False and a.watch_set(42, "x", True)["ok"] is False
    assert a.watch_set("fr:Sans_nom", None, True)["list"][-1]["name"] == "Sans nom"
    assert a.watch_set("fr:Rembrandt", "", False)["list"] == [{"cid": "fr:Sans_nom", "name": "Sans nom"}]
    b = _api(tmp_path, monkeypatch)  # nouvelle session de l'appli : la liste revient, et le flux la connaît
    assert b.watch_get()["list"] == [{"cid": "fr:Sans_nom", "name": "Sans nom"}] and b._live.watch_cids == {"fr:Sans_nom"}


def test_parse_card_sheet():
    from wikipick.parse import parse_card_sheet
    d = parse_card_sheet({
        "card": {"e": "Rembrandt est un peintre.\nIl est né à Leyde.", "qid": "Q5598"},
        "mine": [{"state": "free", "sh": 1, "prov": {"via": "enchere", "ts": 1790000000.5, "prix": 250, "de": "bob", "lot": True}},
                 {"state": "locked", "prov": {"via": "paquet", "ts": 1780000000}}, "bizarre"],
        "wished": 1, "chezAmis": ["ami1", "ami2", 3], "chezGuilde": ["g1"], "souhaitAmis": "pas une liste",
        "auctions": [{"id": 5, "card": {"cid": "fr:R", "n": "Rembrandt", "r": "SR"}, "price": 90, "endsAt": 5, "seller": "eve"}, "x"],
    })
    assert d["extract"].startswith("Rembrandt est") and d["wished"] is True
    assert d["mine"][0] == {"id": 0, "state": "free", "shiny": True, "for_sale": False, "via": "enchere", "ts": 1790000000.5, "price": 250, "from": "bob", "lot": True}
    assert d["mine"][1]["price"] is None and d["mine"][1]["via"] == "paquet" and len(d["mine"]) == 2
    assert d["friends"] == ["ami1", "ami2"] and d["guild"] == ["g1"] and d["friend_wishes"] == []
    assert d["auctions"][0]["price"] == 90 and d["auctions"][0]["card"]["name"] == "Rembrandt"
    assert parse_card_sheet({})["mine"] == [] and parse_card_sheet({})["extract"] == ""
    # les fonctions WIKI-PRO ne sont appelées que derrière le drapeau du profil : voir tests/test_actions.py


def test_client_card_url_and_api_load_card_validation(tmp_path, monkeypatch):
    c = WikiPickClient(session_file=tmp_path / "s.json")
    with mock.patch.object(c.http, "get", return_value=_resp(body={})) as get:
        c.card("fr:Rudná (district)")
        assert get.call_args.args[0].endswith("/api/card?cid=fr%3ARudn%C3%A1+%28district%29")
    a = _api(tmp_path, monkeypatch)
    assert a.load_card("pas-un-cid")["ok"] is False and a.load_card(None)["ok"] is False
    a._client.card = lambda cid: {"card": {"e": "Texte"}, "mine": [], "auctions": []}
    r = a.load_card("fr:X")
    assert r["ok"] and r["extract"] == "Texte" and r["friends"] == []


def test_collection_csv_is_sorted_and_neutralises_formulas():
    from wikipick.export import COLUMNS, collection_csv, safe_cell
    cards = [
        {"name": "=HYPERLINK(\"http://evil\")", "rarity": "C", "reads": 5, "copies": 1, "shiny": False, "locked": False, "lang": "fr", "cid": "fr:X", "url": "https://fr.wikipedia.org/wiki/X"},
        {"name": "Rembrandt; le peintre", "rarity": "L", "reads": 900, "copies": 3, "shiny": True, "locked": True, "lang": "fr", "cid": "fr:R", "url": None},
        {"name": "+33 1 23", "rarity": "M", "reads": 10, "copies": 1, "shiny": False, "locked": False, "lang": "", "cid": "fr:Y", "url": None},
    ]
    out = collection_csv(cards, {"L": "Légendaire", "M": "Mythique"})
    lines = out.split("\r\n")
    assert lines[0] == ";".join(COLUMNS)
    assert lines[1].startswith("'+33 1 23;Mythique;10;1;non;non") and lines[2].startswith('"Rembrandt; le peintre";Légendaire;900;3;oui;oui')
    assert lines[3].startswith("\"'=HYPERLINK(\"\"http") and "Commune" not in out  # rareté sans nom connu : le code
    assert [safe_cell(v) for v in ("=1", "-2", "@x", "\tx", "ok", None, 5)] == ["'=1", "'-2", "'@x", "'\tx", "ok", "", "5"]


def test_export_collection_writes_a_file_in_downloads(tmp_path, monkeypatch):
    a = _api(tmp_path, monkeypatch)
    assert a.export_collection()["ok"] is False  # rien de chargé
    a._client.set_cookies({"sid": "x"})
    a._cache_file.write_text(json.dumps({"cards": [{"name": "A", "rarity": "C", "reads": 1, "copies": 2, "shiny": False, "locked": False, "lang": "fr", "cid": "fr:A", "url": None}],
                                         "names": {"C": "Commune"}}), encoding="utf-8")
    home = tmp_path / "home"; (home / "Downloads").mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(home))
    r = a.export_collection()
    assert r["ok"] and r["count"] == 1 and Path(r["path"]).parent == home / "Downloads"
    raw = Path(r["path"]).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and "Commune".encode() in raw and b"A;Commune;1;2;non;non;fr;fr:A" in raw
