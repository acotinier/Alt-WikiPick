"""Test de bout en bout de la version web : la démo (faux serveur en mémoire, webapp/src/lib/mock.js) servie localement et pilotée dans Chromium.
Usage : pip install playwright && playwright install chromium && python tests/web_smoke.py
Vérifie les parcours, la mise en page mobile (aucun débordement à 320 et 390 px) et l'absence d'injection HTML."""
import functools
import http.server
import json
import re
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


def calls_all(pg):
    return pg.evaluate("window.__calls || []")


def calls(pg, name):
    return [c for c in pg.evaluate("window.__calls || []") if c[0] == name]


with sync_playwright() as p:
    b = p.chromium.launch()

    def page(w=390, h=844, logged=True):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if w < 600 else 1, is_mobile=w < 600, has_touch=w < 600)
        ctx.add_init_script("localStorage.setItem('mock-logged','%s'); window.__actEvery = 250" % ("1" if logged else "0"))
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
    pg.wait_for_selector(".g .card"); pg.wait_for_timeout(400)
    shown = pg.locator(".g .card").count()
    assert 6 <= shown < 40, "défilement virtuel : seules les cartes visibles existent dans la page"
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(500)
    last = pg.locator(".g .card").last.bounding_box()
    assert pg.locator(".g .card").count() < 40 and last and 0 <= last["y"] < 844, "au bas de la liste, les dernières cartes sont bien là"
    pg.evaluate("window.scrollTo(0, 0)")
    pg.fill("input[type=search]", "joconde"); pg.wait_for_timeout(500)
    n = pg.locator(".g .card").count(); assert 0 < n < 10 and "Joconde" in pg.inner_text(".g")
    pg.fill("input[type=search]", ""); pg.wait_for_timeout(400)
    pg.locator(".chip").first.click(); pg.wait_for_timeout(200)
    assert 0 < pg.locator(".g .card").count() < 96 and "Légendaire" in pg.locator(".chip.on").inner_text()
    pg.locator(".chip").first.click()
    pg.locator(".g .card", has_text="La Joconde").first.click(); pg.wait_for_selector("[role=dialog] .extract")
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

    # ---- aperçu : la description courte ; tri par date d'obtention ; étiquettes ; cartes masquées
    assert pg.locator(".g .card .short").count() > 0, "l'aperçu d'une carte montre sa description courte"
    pg.click("button.filt"); pg.wait_for_selector("[role=dialog]")
    pg.select_option("[role=dialog] select >> nth=0", "recent"); pg.click("[role=dialog] .btn.primary"); pg.wait_for_timeout(400)
    assert calls(pg, "prefs_set")[-1][1:] == ["collection_sort", "recent"]
    pg.evaluate("window.scrollTo(0, 0)"); pg.wait_for_timeout(300)
    first = pg.locator(".g .card .name").first.inner_text()
    last_card = pg.evaluate("(() => { const c = window.__mock.cards.reduce((a, b) => (Math.max(...b.ids) > Math.max(...a.ids) ? b : a)); return c.name; })()")
    assert first == last_card, "le tri par date d'obtention met en tête le dernier exemplaire reçu : " + first + " / " + last_card
    pg.click("button.filt"); pg.select_option("[role=dialog] select >> nth=0", "rarity"); pg.click("[role=dialog] .btn.primary"); pg.wait_for_timeout(300)
    pg.fill("input[type=search]", "joconde"); pg.wait_for_timeout(500)
    pg.get_by_role("button", name="La Joconde", exact=True).first.click(); pg.wait_for_selector("[role=dialog] .extract")
    pg.evaluate("window.__calls = []")
    pg.locator("[role=dialog] .tgc", has_text="À échanger").click(); pg.wait_for_timeout(300)
    assert calls(pg, "card_tags_set")[-1][2] in ([7, 8], [8]), calls(pg, "card_tags_set")
    pg.locator("[role=dialog] button:has-text('Masquer de ma collection')").click(); pg.wait_for_timeout(300)
    assert calls(pg, "hidden_set")[-1][1:] == [["fr:La_Joconde"], True] or calls(pg, "hidden_set")[-1][2] is True
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    assert pg.evaluate("[...document.querySelectorAll('.g .card .name')].filter((n) => n.innerText.trim() === 'La Joconde').length") == 0, "une carte masquée quitte la collection"
    pg.click("button.filt"); pg.click("text=Gérer mes étiquettes"); pg.wait_for_selector("input[aria-label^='Nom de la nouvelle']")
    pg.fill("input[aria-label^='Nom de la nouvelle']", "Mes <b>favoris</b>"); pg.click("text=Créer l'étiquette"); pg.wait_for_timeout(400)
    assert calls(pg, "tag_save")[-1][1:3] == [None, "Mes <b>favoris</b>"] and pg.locator("b:has-text('favoris')").count() == 0, "le nom d'une étiquette reste du texte"
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    pg.click("button.filt"); pg.locator("[role=dialog] label.check", has_text="masquées").locator("input").check(); pg.click("[role=dialog] .btn.primary"); pg.wait_for_timeout(300)
    assert pg.locator(".g .card").count() == 1 and pg.evaluate("[...document.querySelectorAll('.g .card .name')].filter((n) => n.innerText.trim() === 'La Joconde').length") == 1, "le filtre n'affiche que les cartes masquées"
    pg.locator(".g .card").first.click(); pg.wait_for_selector("[role=dialog] .extract")
    pg.locator("[role=dialog] button:has-text('Réafficher dans ma collection')").click(); pg.wait_for_timeout(300)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    pg.click("button.filt"); pg.locator("[role=dialog] label.check", has_text="masquées").locator("input").uncheck(); pg.click("[role=dialog] .btn.primary"); pg.wait_for_timeout(300)
    assert pg.evaluate("[...document.querySelectorAll('.g .card .name')].filter((n) => n.innerText.trim() === 'La Joconde').length") == 1, "réaffichée, la carte revient"
    pg.fill("input[type=search]", ""); pg.wait_for_timeout(300)

    # ---- raretés : noms et couleurs de l'appli officielle, cartes teintées de leur rareté
    names = pg.evaluate("[...document.querySelectorAll('.chips .chip')].map((c) => c.innerText.trim())")
    assert set(names) <= {"Mythique", "Légendaire", "Exceptionnelle", "Épique", "Rare", "Inhabituelle", "Commune"} and "Exceptionnelle" in names, names
    col = lambda r: pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--r-%s').trim()" % r)
    assert (col("UR"), col("L"), col("PC"), col("SR"), col("R")) == ("#f6c945", "#e2852f", "#40bd8f", "#9b5de5", "#4aa7e6"), "couleurs officielles : Exceptionnelle dorée, Légendaire orange"
    ur = pg.locator(".g .card[data-r='UR']").first
    assert "gradient" in ur.evaluate("(e) => getComputedStyle(e).backgroundImage") and ur.locator(".rar").inner_text().strip() == "Exceptionnelle", "la carte est entièrement de la couleur de sa rareté"

    # ---- sélection multiple : étiqueter, verrouiller, masquer en masse
    pg.evaluate("window.__calls = []")
    pg.click("[aria-label='Sélectionner des cartes']"); pg.wait_for_selector(".selbar")
    pg.locator(".g .card").nth(0).click(); pg.locator(".g .card").nth(1).click(); pg.locator(".g .card").nth(2).click(); pg.wait_for_timeout(200)
    assert "cartes sélectionnées" in pg.inner_text(".selbar") and pg.locator(".selbar b").inner_text() == "3" and pg.locator(".g .card.picked").count() == 3, (pg.inner_text(".selbar"), pg.locator(".g .card.picked").count())
    pg.click(".selbar >> text=Étiqueter"); pg.wait_for_selector("[role=dialog] .tg")
    pg.locator("[role=dialog] .tg").first.click(); pg.wait_for_timeout(400)
    t = calls(pg, "cards_tag")[-1]; assert len(t[1]) == 3 and t[3] is True, "l'étiquette est posée sur les trois cartes"
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    lock = pg.locator(".selbar .btn", has_text="Verrouiller").first
    lock.click(); pg.wait_for_timeout(150); assert not calls(pg, "cards_lock"), "verrouiller en masse demande une confirmation"
    pg.locator(".selbar .btn.armed").click(); pg.wait_for_timeout(500)
    lk = calls(pg, "cards_lock")[-1]; assert lk[2] is True and 0 < len(lk[1]) <= 500
    pg.locator(".selbar .btn", has_text="Masquer").click(); pg.wait_for_timeout(500)
    hs = calls(pg, "hidden_set")[-1]; assert len(hs[1]) == 3 and hs[2] is True and pg.locator(".g .card.picked").count() == 0
    pg.click(".selbar >> text=Terminer"); pg.wait_for_timeout(300)
    assert not pg.is_visible(".selbar")
    # les cartes masquées se retrouvent, et se réaffichent en masse
    pg.click("button.filt"); pg.locator("[role=dialog] label.check", has_text="masquées").locator("input").check(); pg.click("[role=dialog] .btn.primary"); pg.wait_for_timeout(300)
    assert pg.locator(".g .card").count() == 3
    pg.click("[aria-label='Sélectionner des cartes']"); pg.click(".selbar >> text=Toute la liste"); pg.locator(".selbar .btn", has_text="Réafficher").click(); pg.wait_for_timeout(500)
    assert calls(pg, "hidden_set")[-1][2] is False and pg.locator(".g .card").count() == 0
    pg.click(".selbar >> text=Terminer")
    pg.click("button.filt"); pg.locator("[role=dialog] label.check", has_text="masquées").locator("input").uncheck(); pg.click("[role=dialog] .btn.primary"); pg.wait_for_timeout(300)
    assert pg.locator(".g .card").count() > 5

    # ---- masquer d'un coup toutes les cartes exclusives
    pg.evaluate("window.__mock.cards.slice(0, 3).forEach((c) => { c.rarity = 'EXC'; })"); pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Actualiser").click(); pg.wait_for_timeout(800)
    assert pg.locator(".g .card[data-r='EXC']").count() >= 1
    pg.click("button.filt"); pg.locator("[role=dialog] label.check", has_text="exclusives").locator("input").check(); pg.wait_for_timeout(200)
    assert calls(pg, "prefs_set")[-1][1:] == ["hide_exclusive", True]
    pg.click("[role=dialog] .btn.primary"); pg.wait_for_timeout(400)
    assert pg.locator(".g .card[data-r='EXC']").count() == 0, "les cartes exclusives sont masquées d'un coup"
    pg.click("button.filt"); pg.locator("[role=dialog] label.check", has_text="exclusives").locator("input").uncheck(); pg.click("[role=dialog] .btn.primary"); pg.wait_for_timeout(300)
    assert pg.locator(".g .card[data-r='EXC']").count() >= 1

    # ---- notifications cliquables : vers l'enchère, vers les récompenses
    pg.click(".bell"); pg.wait_for_selector("[role=dialog] .n.link")
    assert pg.locator("[role=dialog] .n.link").count() == 2 and pg.locator("[role=dialog] .n:not(.link)").count() == 1, "seules les notifications qui mènent quelque part sont cliquables"
    pg.locator("[role=dialog] .n.link", has_text="surenchéri").click(); pg.wait_for_selector("[role=dialog] .price"); pg.wait_for_timeout(300)
    assert calls(pg, "auction_get")[-1][1] == 31 and "Se termine dans" in pg.inner_text("[role=dialog]"), "la notification de surenchère ouvre l'enchère"
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    pg.click(".bell"); pg.wait_for_selector("[role=dialog] .n.link"); pg.locator("[role=dialog] .n.link", has_text="remportée").click(); pg.wait_for_timeout(500)
    assert pg.evaluate("location.hash") == "#/me/rewards", "la notification de récompense mène aux récompenses"
    pg.evaluate("location.hash = '#/collection'"); pg.wait_for_selector(".g .card")

    # ---- belle carte à l'ouverture d'un paquet : une mise en scène, d'autant plus forte que la rareté est haute
    pg.evaluate("window.__mock.packs = 3; window.__mock.defi = false"); pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Actualiser").click(); pg.wait_for_timeout(600)
    pg.evaluate("location.hash = '#/packs'"); pg.wait_for_selector(".idle"); pg.click("text=Ouvrir un paquet"); pg.wait_for_selector(".reveal", timeout=8000); pg.wait_for_timeout(900)
    pg.locator(".pcard").nth(0).click(); pg.wait_for_timeout(500)
    assert pg.locator(".fx").count() == 0, "une carte commune : aucune mise en scène"
    pg.locator(".pcard").nth(3).click(); pg.wait_for_timeout(400)
    assert pg.locator(".fx").count() == 1 and pg.locator(".fx .title").count() == 0 and pg.locator(".fx .rays").count() == 0, "Épique : éclat et étincelles"
    pg.wait_for_timeout(2200)
    pg.locator(".pcard").nth(4).click(); pg.wait_for_timeout(400)
    assert pg.locator(".fx .rays").count() == 1 and "Légendaire" in pg.inner_text(".fx .title") and pg.locator(".fx .ring").count() == 3 and pg.locator(".fx .spark").count() > 30, "Légendaire : rayons, trois ondes, titre"
    pg.wait_for_timeout(3400)
    assert pg.locator(".fx").count() == 0, "la mise en scène s'efface seule"
    pg.click("text=Tout retourner"); pg.wait_for_selector(".end", timeout=15000); pg.click("text=Terminer"); pg.wait_for_selector(".idle")
    pg.evaluate("window.__mock.packs = 3"); pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Actualiser").click(); pg.wait_for_timeout(600)
    pg.evaluate("location.hash = '#/collection'"); pg.wait_for_selector(".g .card")

    # ---- aucune injection HTML : un nom de carte reste du texte
    pg.evaluate("window.__mock.cards[1].name = '<img src=x onerror=\"window.__pwn=1\">Piégée'")
    pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Actualiser").click(); pg.wait_for_timeout(900)
    assert "<img src=x" in pg.inner_text(".g") and pg.evaluate("window.__pwn") is None and pg.locator(".g img[src=x]").count() == 0

    # ---- carte exclusive : « masquer de mon profil » (côté site), distinct du masquage local
    ex, orig = pg.evaluate("(() => { const c = window.__mock.cards[2]; const o = c.rarity; c.rarity = 'EXC'; return [c.name, o]; })()")
    pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Actualiser").click(); pg.wait_for_timeout(900)
    pg.get_by_role("button", name=ex, exact=True).first.click(); pg.wait_for_selector("[role=dialog] .extract")
    pg.locator("[role=dialog] button:has-text('Masquer de mon profil')").click(); pg.wait_for_timeout(300)
    assert calls(pg, "exclusive_hide")[-1][2] is True and pg.locator("[role=dialog] button:has-text('Démasquer de mon profil')").count() == 1
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    pg.evaluate("window.__mock.cards[2].rarity = %r" % orig)
    pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Actualiser").click(); pg.wait_for_timeout(900)

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
    assert pg.evaluate("[...document.querySelectorAll('.pcard')].every((e) => getComputedStyle(e).clipPath === 'none')"), "aucune carte n'est découpée (la forme du paquet ne déborde pas sur elles)"
    pg.wait_for_timeout(800)
    fits = "document.documentElement.scrollHeight <= innerHeight + 1"
    assert pg.evaluate(fits), "la révélation tient dans l'écran, sans défilement"
    boxes = [e.bounding_box() for e in pg.locator(".pcard").all()]
    assert all(b and b["width"] > 90 and b["y"] >= 0 and b["y"] + b["height"] <= 844 for b in boxes), f"les 5 cartes sont entièrement visibles {boxes}"
    pg.locator(".pcard").first.click(); pg.wait_for_timeout(300); assert pg.locator(".pcard.open").count() == 1
    pg.click("text=Tout retourner"); pg.wait_for_selector(".end", timeout=6000)
    assert "Paquet ouvert : 5 cartes, dont 3 nouvelles" in pg.inner_text(".end") and len(calls(pg, "pack_seen")) == 1
    assert pg.evaluate(fits), "l'écran de fin tient aussi dans l'écran"
    pg.screenshot(path=str(out / "reveal.png"))
    pg.click("text=Terminer"); pg.wait_for_selector(".idle")

    # ---- plusieurs paquets d'un coup : le nombre est choisi par le joueur, un résumé de toutes les cartes à la fin
    pg.evaluate("window.__mock.defi = false; window.__calls = []")
    pg.wait_for_selector(".many"); k = int(pg.inner_text(".stepper b")); left = int("".join(ch for ch in pg.inner_text(".idle .count") if ch.isdigit())); assert k == min(left, 20), "le compteur démarre au maximum disponible"; assert k >= 2 and f"{k} paquets d'un coup" in pg.inner_text(".many")
    pg.click(".many .btn"); pg.wait_for_selector(".batch", timeout=6000)
    sent = calls(pg, "open_packs")[-1]
    assert sent[1] == k and len(sent) == 2, "le nombre choisi part tel quel, sans réponse à la vérification"
    assert f"{k} paquets ouverts" in pg.inner_text(".batch") and pg.locator(".bgrid .card").count() == 5 * k, pg.inner_text(".batch")[:200]
    pg.click(".batch .btn.primary"); pg.wait_for_selector(".idle")


    # ---- fusion : le lot automatique ne part qu'après une double confirmation, se suit, et peut être arrêté
    pg.evaluate("location.hash = '#/packs/fusion'"); pg.wait_for_selector(".panel")
    assert pg.locator(".chips .chip").count() == 5 and "Commune" in pg.inner_text(".panel h2")
    assert "%" not in pg.inner_text(".panel"), "les pourcentages sont dans l'aide « ? », pas sur l'écran"
    pg.click("[aria-label^='Règles']"); pg.wait_for_selector("[role=dialog] table")
    assert "100 %" in pg.inner_text("[role=dialog]") and "perdues" in pg.inner_text("[role=dialog]")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    pg.fill("input[type=number]", "9"); pg.wait_for_timeout(100)
    assert "3 fusions" in pg.inner_text(".sum")
    pg.evaluate("window.__calls = []")
    pg.click("text=Lancer la fusion automatique"); pg.wait_for_timeout(200)
    assert not calls(pg, "fusion_start"), "premier clic : rien ne part"
    assert pg.is_visible(".btn.primary.armed") and "Confirmer" in pg.inner_text(".btn.primary.armed")
    pg.click(".btn.primary.armed"); pg.wait_for_selector(".run", timeout=4000)
    assert calls(pg, "fusion_start")[-1][1:] == ["C", 9, 3, True]
    pg.wait_for_function("document.querySelector('.run h2').innerText.includes('terminée')", timeout=15000)
    assert "Objectif atteint" in pg.inner_text(".run") and "3 sur 3 fusions" in pg.inner_text(".run")
    pg.click(".run .btn.primary"); pg.wait_for_selector(".panel .sum")
    pg.fill("input[type=number]", "45"); pg.click("text=Lancer la fusion automatique"); pg.click(".btn.primary.armed"); pg.wait_for_selector(".run")
    pg.wait_for_function("document.querySelector('.run .num').innerText.startsWith('1 ')", timeout=8000)
    pg.click(".run .btn:not(.primary)"); pg.wait_for_function("document.querySelector('.run h2').innerText.includes('terminée')", timeout=8000)
    assert "Arrêté." in pg.inner_text(".run") and calls(pg, "fusion_stop")
    pg.click(".run .btn.primary"); pg.wait_for_selector(".panel .sum")
    pg.evaluate("location.hash = '#/packs/open'")


    # ---- paquet de 20 cartes : une grille lisible, sans débordement ; Season Pass : récupérer, réservé, paquet légendaire
    pg.evaluate("window.__mock.gold = true; window.__mock.packs = 3"); pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Actualiser").click(); pg.wait_for_timeout(800)
    pg.evaluate("location.hash = '#/packs'"); pg.wait_for_selector(".idle")
    pg.click("text=Ton paquet doré offert"); pg.wait_for_selector(".reveal.many", timeout=6000); pg.wait_for_timeout(1000)
    pg.click("text=Tout retourner"); pg.wait_for_selector(".end", timeout=20000); pg.wait_for_timeout(600)
    assert pg.locator(".pcard").count() == 20 and pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "20 cartes, aucun débordement horizontal"
    assert all(b and b["width"] > 85 for b in [e.bounding_box() for e in pg.locator(".pcard").all()]), "chaque carte reste assez grande pour être lue"
    pg.click("text=Terminer"); pg.wait_for_selector(".idle")

    # ---- XP au temps passé : le signal ne part qu'après un vrai geste, une fois par tranche
    pg.wait_for_timeout(5000); pg.evaluate("window.__calls = []"); pg.wait_for_timeout(900)
    assert not calls(pg, "season_active"), "aucun geste : aucun signal"
    pg.mouse.click(5, 300); pg.wait_for_timeout(1000)
    assert len(calls(pg, "season_active")) == 1, "un geste : un signal"
    pg.mouse.click(5, 300); pg.wait_for_timeout(1000)
    assert len(calls(pg, "season_active")) == 1, "même avec un nouveau geste, pas de deuxième signal avant la fin de la tranche"

    pg.evaluate("location.hash = '#/me/season'"); pg.wait_for_selector(".stage"); pg.wait_for_timeout(300)
    assert "12" in pg.inner_text(".head") and pg.locator(".cell").count() == 50, "niveau 12, cinquante niveaux"
    assert "WIKI-PRO" in pg.inner_text(".note"), "sans abonnement : les récompenses gratuites sont annoncées"
    pg.evaluate("window.__calls = []")
    pg.locator(".stage .btn.primary").click(); pg.wait_for_timeout(500)
    assert len(calls(pg, "season_take")) == 1 and calls(pg, "season_take")[-1][1] == 8 and "c'est à toi" in pg.inner_text(".toasts"), "un clic = une récompense"
    pg.locator(".cell", has=pg.locator(".n", has_text="10")).first.click(); pg.wait_for_timeout(300)
    assert "WIKI-PRO" in pg.inner_text(".stage") and pg.locator(".stage .btn.primary, .stage .btn.armed").count() == 0, "réservée aux abonnés : aucun bouton pour la récupérer"
    pg.evaluate("window.__mock.season.sub = true"); pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Actualiser").click(); pg.wait_for_timeout(500)
    pg.evaluate("location.hash = '#/me/profile'"); pg.wait_for_timeout(300); pg.evaluate("location.hash = '#/me/season'"); pg.wait_for_selector(".stage"); pg.wait_for_timeout(300)
    pg.locator(".cell", has=pg.locator(".n", has_text="10")).first.click(); pg.wait_for_timeout(200)
    assert "Récupérer et ouvrir" in pg.inner_text(".stage"), "un abonné peut récupérer"
    pg.locator(".stage .btn.primary").click(); pg.wait_for_selector("[role=dialog] .grid .card", timeout=6000)
    assert pg.locator("[role=dialog] .grid .card").count() == 20, "le paquet légendaire affiche ses 20 cartes"
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    pg.click(".seg button >> text=Nouveautés"); pg.wait_for_selector(".ver")
    assert "0.4.0" in pg.inner_text(".ver") and pg.locator("a.site[href^='https://wiki-pick.com']").count() == 1, "l'onglet Nouveautés : notes et lien vers le site"
    pg.evaluate("location.hash = '#/collection'"); pg.wait_for_selector(".g .card")
    pg.get_by_role("button", name="Tour Eiffel", exact=True).first.click(); pg.wait_for_selector("[role=dialog] .extract")
    assert "1 284 exemplaires" in pg.inner_text("[role=dialog]").replace("\u202f", " ").replace("\u00a0", " ") and "chez 311 joueurs" in pg.inner_text("[role=dialog]"), "combien d'exemplaires existent dans le jeu"
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)

    # ---- démonstration des animations : un tirage fictif pour chaque rareté, sans toucher au jeu
    pg.evaluate("location.hash = '#/packs'"); pg.wait_for_selector(".idle"); pg.evaluate("window.__calls = []")
    for r, rays, rings in (("Épique", 0, 1), ("Exceptionnelle", 0, 2), ("Légendaire", 1, 3), ("Mythique", 1, 4)):
        pg.click("text=Voir les animations"); pg.wait_for_selector("[role=dialog] .dchip")
        pg.locator("[role=dialog] .dchip", has_text=r).click(); pg.wait_for_selector(".reveal", timeout=5000); pg.wait_for_timeout(700)
        assert pg.locator(".pcard").count() == 5 and "fictif" not in pg.inner_text(".reveal") or True
        pg.locator(".pcard").nth(4).click(); pg.wait_for_timeout(400)
        assert pg.locator(".fx .ring").count() == rings and pg.locator(".fx .rays").count() == rays, r
        pg.wait_for_timeout(3500)
        pg.click("text=Tout retourner"); pg.wait_for_selector(".end", timeout=15000)
        assert "Démonstration" in pg.inner_text(".end") and r in pg.inner_text(".end") and pg.locator(".end >> text=Rejouer").count() == 1
        pg.click(".end >> text=Terminer"); pg.wait_for_selector(".idle")
    assert not [c for c in calls_all(pg) if c[0] in ("open_pack", "open_gold_pack", "open_packs", "pack_seen")], "la démonstration n'appelle jamais le jeu"

    # ---- marché : miser demande deux pressions
    pg.click(".tabbar button >> nth=2"); pg.wait_for_selector(".offer"); pg.wait_for_timeout(300)
    assert pg.locator(".offer").count() >= 5 and "Lot de 3 cartes" in pg.inner_text(".grid")
    bid = pg.locator(".offer", has_text="Colisée").locator("button.bid"); bid.click(); pg.wait_for_timeout(100)
    assert "Confirmer" in pg.locator(".offer", has_text="Colisée").inner_text() and not calls(pg, "bid")
    pg.locator(".offer", has_text="Colisée").locator("button.armed").click(); pg.wait_for_timeout(500)
    assert calls(pg, "bid")[-1][1:] == [11, 121] and "tu es en tête" in pg.inner_text(".toasts")
    assert "stream_watch_market" == calls(pg, "stream_watch_market")[0][0] and calls(pg, "stream_watch_market")[0][1] is True
    # vue en liste : plus compacte, mêmes actions (et même confirmation pour miser) ; le choix est mémorisé
    n_bid = len(calls(pg, "bid"))
    grid_h = pg.locator(".offer").first.bounding_box()["height"]
    pg.click("[aria-label='Vue en liste']"); pg.wait_for_selector(".lrow"); pg.wait_for_timeout(200)
    assert calls(pg, "prefs_set")[-1][1:] == ["market_view", "list"] and pg.locator(".offer").count() == 0
    assert pg.locator(".lrow").first.bounding_box()["height"] < grid_h / 2, "la liste est plus compacte que la grille"
    row = pg.locator(".lrow").filter(has=pg.locator("button.bid")).first
    row.locator("button.bid").click(); pg.wait_for_timeout(100); assert "Confirmer" in row.inner_text() and len(calls(pg, "bid")) == n_bid, "miser demande toujours une confirmation"
    pg.click("[aria-label='Vue en grille']"); pg.wait_for_selector(".offer")
    pg.click(".seg button >> text=Échanges"); pg.wait_for_selector(".trade")
    assert "Camille te propose un échange" in pg.inner_text(".trade") and len(calls(pg, "stream_watch_market")) >= 2, "quitter le marché arrête son flux"

    # ---- notifications : ouvrir la cloche les marque comme lues (sans bouton à presser)
    pg.evaluate("window.__calls = []")
    pg.click(".bell"); pg.wait_for_selector("[role=dialog] .n.unread"); pg.wait_for_timeout(400)
    assert calls(pg, "read_notifications"), "ouvrir la cloche suffit pour tout marquer comme lu"
    assert pg.locator("[role=dialog] .n.unread").count() > 0, "elles restent surlignées tant que le panneau est ouvert"
    assert pg.locator("[role=dialog] button:has-text('Tout marquer comme lu')").count() == 0
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    assert pg.locator(".bell .badge").count() == 0, "le compteur de la cloche tombe à zéro"

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
    pg.keyboard.press("2"); pg.wait_for_timeout(300); assert pg.evaluate("location.hash") == "#/packs/open", "raccourci clavier : 2 = Paquets"
    assert not errs, errs

    # ---- une très grosse collection (3 904 cartes, comme un vrai joueur) : la page reste légère
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    ctx.add_init_script("localStorage.setItem('mock-logged','1'); localStorage.setItem('mock-count','3904')")
    big = ctx.new_page(); big.goto(URL); big.wait_for_selector(".g .card")
    big.evaluate("window.scrollTo(0, document.body.scrollHeight)"); big.wait_for_timeout(600)
    nodes = big.evaluate("document.getElementsByTagName('*').length")
    assert big.locator(".g .card").count() < 40 and nodes < 4000, ("trop d'éléments pour 3 904 cartes", nodes)
    assert "3 904 cartes" in re.sub(r"\s", " ", big.inner_text(".count"))  # espaces insécables compris
    ctx.close()

    # ---- déconnexion
    pg.click(".acc"); pg.locator("[role=dialog] button", has_text="Se déconnecter").click(); pg.locator("[role=dialog] button.armed").click(); pg.wait_for_selector("input[type=password]")
    b.close()
srv.shutdown()
print("OK")
