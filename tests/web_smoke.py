"""Test de bout en bout de la version web : la démo (faux serveur en mémoire, webapp/src/lib/mock.js) servie localement et pilotée dans Chromium.
Usage : pip install playwright && playwright install chromium && python tests/web_smoke.py
Vérifie les parcours, la mise en page mobile (aucun débordement à 320 et 390 px) et l'absence d'injection HTML."""
import functools
import http.server
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "webapp"
out = Path(tempfile.mkdtemp(prefix="altwp_web_"))
print("screenshots ->", out)

subprocess.run("npm run build:mock", cwd=WEB, shell=True, check=True, capture_output=True)
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


handler = functools.partial(Quiet, directory=str(WEB / "dist-mock"))
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}/"

ROUTES = ["collection", "packs", "market/auctions", "market/trades", "social/messages", "social/messages/Camille", "social/friends", "social/guild", "social/arena",
          "me/profile", "me/rewards", "me/rank", "me/stats", "player/Camille"]


def calls(pg, name):
    return [c for c in pg.evaluate("window.__calls || []") if c[0] == name]


with sync_playwright() as p:
    b = p.chromium.launch()

    def page(w=390, h=844, logged=True):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if w < 600 else 1, is_mobile=w < 600, has_touch=w < 600)
        ctx.add_init_script("localStorage.setItem('mock-logged','%s')" % ("1" if logged else "0"))
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
        pg.on("console", lambda m: errs.append("CONSOLE " + m.text) if m.type == "error" else None)
        pg.goto(URL)
        return pg, errs

    # ---- connexion : identifiants via le serveur, puis la question du site, clic du joueur
    pg, errs = page(logged=False)
    pg.wait_for_selector("input[autocomplete=username]")
    assert pg.is_disabled("button.primary"), "rien à envoyer sans identifiants"
    pg.fill("input[autocomplete=username]", "alex"); pg.fill("input[type=password]", "mauvais"); pg.click("button.primary")
    pg.wait_for_selector(".defi"); pg.click(".c >> nth=1")
    pg.wait_for_selector(".err"); assert "incorrects" in pg.inner_text(".err") and pg.is_visible("input[type=password]")
    pg.fill("input[type=password]", "demo"); pg.click("button.primary"); pg.wait_for_selector(".defi")
    assert pg.locator(".c svg").count() == 6 and "Clique sur la goutte" in pg.inner_text(".defi")
    pg.screenshot(path=str(out / "login-challenge.png"))
    pg.click(".c >> nth=1"); pg.wait_for_selector(".tabbar")
    assert pg.is_visible(".tabbar") and not pg.is_visible(".rail"), "mobile : onglets en bas"
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "pas de débordement horizontal"

    # ---- collection : dessinée par paquets, recherche, raretés, fiche
    pg.wait_for_selector(".grid .card"); pg.wait_for_timeout(400)
    assert pg.locator(".grid .card").count() == 60, "60 cartes d'abord"
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(700)
    assert pg.locator(".grid .card").count() == 96, "le reste arrive au défilement"
    pg.evaluate("window.scrollTo(0, 0)")
    pg.fill("input[type=search]", "joconde"); pg.wait_for_timeout(500)
    n = pg.locator(".grid .card").count(); assert 0 < n < 10 and "Joconde" in pg.inner_text(".grid")
    pg.fill("input[type=search]", ""); pg.wait_for_timeout(400)
    pg.locator(".chip").first.click(); pg.wait_for_timeout(200)
    assert 0 < pg.locator(".grid .card").count() < 96 and "Légendaire" in pg.locator(".chip.on").inner_text()
    pg.locator(".chip").first.click()
    pg.locator(".grid .card", has_text="La Joconde").first.click(); pg.wait_for_selector("[role=dialog] .extract")
    sheet = pg.inner_text("[role=dialog]")
    assert "Tes exemplaires" in sheet and "Achetée 250 Wikiki aux enchères à Bob" in sheet and "Lire la suite" in sheet and "Chez tes amis : Camille, Inès" in sheet
    pg.screenshot(path=str(out / "card-sheet.png"))
    # recycler : une légendaire demande une confirmation, rien ne part au premier toucher
    rec = pg.locator("[role=dialog] button", has_text="Recycler"); assert rec.count() == 1
    rec.click(); pg.wait_for_timeout(100)
    assert not calls(pg, "recycle"), "première pression : rien ne part"
    pg.locator("[role=dialog] button.armed").click(); pg.wait_for_timeout(400)
    assert len(calls(pg, "recycle")) == 1 and "Carte recyclée" in pg.inner_text(".toasts")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200); assert not pg.is_visible("[role=dialog]"), "Échap ferme la fiche"

    # ---- aucune injection HTML : un nom de carte reste du texte
    pg.evaluate("window.__mock.cards[1].name = '<img src=x onerror=\"window.__pwn=1\">Piégée'")
    pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Actualiser").click(); pg.wait_for_timeout(900)
    assert "<img src=x" in pg.inner_text(".grid") and pg.evaluate("window.__pwn") is None and pg.locator(".grid img[src=x]").count() == 0

    # ---- paquets : un clic = un paquet ; la vérification du site est posée au joueur, jamais devinée
    pg.click(".tabbar button >> nth=1"); pg.wait_for_selector(".idle")
    assert "3 paquets en réserve" in pg.inner_text(".idle")
    pg.evaluate("window.__mock.defi = true")
    pg.click("text=Ouvrir un paquet"); pg.wait_for_timeout(300)
    assert not calls(pg, "open_pack") or calls(pg, "open_pack")[-1][1:] == [], "sans réponse du joueur, aucune preuve n'est envoyée"
    pg.evaluate("window.__calls = []")
    pg.wait_for_selector("[role=dialog] .defi"); pg.click("[role=dialog] .c >> nth=0"); pg.wait_for_timeout(1800)  # mauvaise réponse : la mock refuse
    assert [c for c in calls(pg, "open_pack") if len(c) == 3] and "Mauvaise réponse" in pg.inner_text(".toasts")
    pg.evaluate("window.__mock.defi = true; window.__calls = []")
    pg.click("text=Ouvrir un paquet"); pg.wait_for_selector("[role=dialog] .defi"); pg.click("[role=dialog] .c >> nth=1"); pg.wait_for_selector(".reveal", timeout=6000)
    assert calls(pg, "open_pack")[-1][1:] == ["mockchallenge1", 1] and pg.locator(".pcard").count() == 5 and pg.locator(".pcard.open").count() == 0
    pg.locator(".pcard").first.click(); pg.wait_for_timeout(300); assert pg.locator(".pcard.open").count() == 1
    pg.click("text=Tout retourner"); pg.wait_for_selector(".end", timeout=6000)
    assert "Paquet ouvert : 5 cartes, dont 3 nouvelles" in pg.inner_text(".end") and len(calls(pg, "pack_seen")) == 1
    pg.screenshot(path=str(out / "reveal.png"))
    pg.click("text=Terminer"); pg.wait_for_selector(".idle")

    # ---- marché : miser demande deux pressions
    pg.click(".tabbar button >> nth=2"); pg.wait_for_selector(".offer"); pg.wait_for_timeout(300)
    assert pg.locator(".offer").count() >= 5 and "Lot de 3 cartes" in pg.inner_text(".grid")
    bid = pg.locator(".offer", has_text="Colisée").locator("button.bid"); bid.click(); pg.wait_for_timeout(100)
    assert "Confirmer" in pg.locator(".offer", has_text="Colisée").inner_text() and not calls(pg, "bid")
    pg.locator(".offer", has_text="Colisée").locator("button.armed").click(); pg.wait_for_timeout(500)
    assert calls(pg, "bid")[-1][1:] == [11, 121] and "tu es en tête" in pg.inner_text(".toasts")
    assert "stream_watch_market" == calls(pg, "stream_watch_market")[0][0] and calls(pg, "stream_watch_market")[0][1] is True
    pg.click(".seg button >> text=Échanges"); pg.wait_for_selector(".trade")
    assert "Camille te propose un échange" in pg.inner_text(".trade") and len(calls(pg, "stream_watch_market")) >= 2, "quitter le marché arrête son flux"

    # ---- social : message, amis
    pg.click(".tabbar button >> nth=3"); pg.wait_for_selector(".conv"); pg.locator(".conv", has_text="Camille").click(); pg.wait_for_selector(".bub")
    assert pg.locator(".bub").count() == 3 and pg.locator(".conv .badge").count() <= 1
    ta = pg.locator(".sendbox textarea"); ta.fill("   "); ta.press("Enter"); pg.wait_for_timeout(150); assert not calls(pg, "message_send")
    ta.fill("Bonjour <b>toi</b>"); ta.press("Enter"); pg.wait_for_timeout(500)
    assert calls(pg, "message_send")[-1][1:] == ["Camille", "Bonjour <b>toi</b>"] and "Bonjour <b>toi</b>" in pg.inner_text(".body") and pg.locator(".body b").count() == 0
    pg.click(".seg button >> text=Amis"); pg.wait_for_selector(".item")
    pg.locator(".item", has_text="Inès").locator("button", has_text="Accepter").click(); pg.wait_for_timeout(500)
    assert calls(pg, "friend_action")[-1][1:] == ["accept", "Inès"] and "maintenant ami(e)s" in pg.inner_text(".toasts")

    # ---- récompenses
    pg.click(".tabbar button >> nth=4"); pg.click(".seg button >> text=Récompenses"); pg.wait_for_selector(".streak")
    assert pg.locator(".day").count() == 7 and "Série de connexion" in pg.inner_text(".streak")
    pg.locator(".streak button.gold").click(); pg.wait_for_timeout(500)
    assert calls(pg, "claim")[-1][1:] == ["serie"] and "Jour 3" in pg.inner_text(".toasts")
    pg.screenshot(path=str(out / "rewards.png"), full_page=True)
    assert not errs, errs

    # ---- aucune page ne déborde, à 390 px comme à 320 px ; aucune erreur dans la console
    for w in (390, 320):
        pg, errs = page(w, 700)
        pg.wait_for_selector(".tabbar")
        for r in ROUTES:
            pg.evaluate("location.hash = '#/%s'" % r); pg.wait_for_timeout(900)
            over = pg.evaluate("document.documentElement.scrollWidth - innerWidth")
            assert over <= 0, (w, r, "déborde de", over)
            body = pg.inner_text("body"); assert "[object" not in body and "undefined" not in body and "NaN" not in body, (w, r)
        assert not errs, (w, errs)
        pg.context.close()

    # ---- grand écran : colonne de gauche, pas d'onglets du bas
    pg, errs = page(1320, 800)
    pg.wait_for_selector(".rail")
    assert pg.is_visible(".rail") and not pg.is_visible(".tabbar")
    for r in ROUTES:
        pg.evaluate("location.hash = '#/%s'" % r); pg.wait_for_timeout(700)
    pg.screenshot(path=str(out / "desktop.png"))
    pg.keyboard.press("2"); pg.wait_for_timeout(300); assert pg.evaluate("location.hash") == "#/packs", "raccourci clavier : 2 = Paquets"
    assert not errs, errs

    # ---- déconnexion
    pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Se déconnecter").click(); pg.locator("[role=dialog] button.armed").click(); pg.wait_for_selector("input[type=password]")
    b.close()
srv.shutdown()
print("OK")
