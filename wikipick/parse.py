"""Décodage de /api/collection?v=2 et calcul des statistiques.

Format observé (identique à `groupeCompact` dans le JS du site) :
    groups[i] = [ <n valeurs dans l'ordre de `champs`>,
                  ids des exemplaires (liste),
                  ids des tags (liste),
                  sac de champs rares (dict : sh, frt, perso...) ]
    champs   = cid, n, d, img, r, v, nl, lang, locked
    img      = 1 chiffre (index dans `imgp`) + fin de l'URL
    v        = « lectures dans le monde » de l'article Wikipédia (ni un id, ni un prix) :
               ce sont les seuils de `state.info.scale` appliqués à ce nombre qui donnent la rareté.
"""
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

# Les cartes exclusives ne se vendent, ne se recyclent et ne s'échangent pas (règle du site).
EXCLUSIVE = ("EXC", "WBC", "SIXSEVEN")

# Ordre d'affichage : exclusives d'abord, puis du plus rare au plus commun.
RARITY_ORDER = ["EXC", "WBC", "SIXSEVEN", "M", "L", "UR", "SR", "R", "PC", "C"]

_ALLOWED_IMG_HOSTS = ("https://upload.wikimedia.org/", "https://thumb.wikimedia.org/")


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1")
    return bool(value)


_PERSO_IMG = re.compile(r"^/perso/[A-Za-z0-9._-]{1,80}$")  # les images des cartes exclusives vivent sur wiki-pick.com, dans /perso/


def _safe_img(img):
    if not isinstance(img, str):
        return None
    if img.startswith(_ALLOWED_IMG_HOSTS):
        return img
    path = img[len("https://wiki-pick.com"):] if img.startswith("https://wiki-pick.com/") else img
    return "https://wiki-pick.com" + path if _PERSO_IMG.match(path) else None


def wiki_url(cid):
    """'fr:Rudná_(district)' -> https://fr.wikipedia.org/wiki/Rudn%C3%A1_(district)"""
    if not isinstance(cid, str) or ":" not in cid:
        return None
    lang, title = cid.split(":", 1)
    if not lang.isalpha() or not title:
        return None
    return f"https://{lang}.wikipedia.org/wiki/{quote(title, safe='_()/,:')}"


def expand_group(row, champs, imgp):
    """Transforme une ligne compacte en dict de carte lisible."""
    n = len(champs)
    raw = {champs[i]: row[i] for i in range(min(n, len(row)))}

    img = raw.get("img")
    if isinstance(img, str) and img and img[0].isdigit():
        idx = int(img[0])
        if idx < len(imgp):
            img = imgp[idx] + img[1:]
    img = _safe_img(img)

    ids = row[n] if len(row) > n and isinstance(row[n], list) else []
    tags = row[n + 1] if len(row) > n + 1 and isinstance(row[n + 1], list) else []
    extra = row[n + 2] if len(row) > n + 2 and isinstance(row[n + 2], dict) else {}
    if not img:  # carte exclusive : son illustration est le média de sa mise en page personnalisée (sauf une vidéo)
        perso = extra.get("perso")
        if isinstance(perso, dict) and not perso.get("video"):
            img = _safe_img(perso.get("media"))
    ids = [_to_int(i) for i in ids if _to_int(i) > 0]
    rarity = raw.get("r") or "C"
    locked = _to_bool(raw.get("locked"))
    verrous = extra.get("verrous")  # exemplaires verrouillés un par un (ids), dans le sac des champs rares
    locked_ids = [_to_int(i) for i in verrous if _to_int(i) > 0] if isinstance(verrous, list) else []
    # ce qu'on peut vendre, recycler ou échanger : jamais un exemplaire verrouillé, jamais une exclusive (même règle que freeIds du site)
    free_ids = [] if (locked or rarity in EXCLUSIVE) else [i for i in ids if i not in locked_ids]

    return {
        "cid": raw.get("cid"),
        "name": raw.get("n") or "?",
        "desc": raw.get("d") or "",
        "img": img,
        "rarity": rarity,
        "reads": _to_int(raw.get("v")),
        "nl": _to_int(raw.get("nl")),
        "lang": raw.get("lang") or "",
        "locked": locked,
        "locked_ids": locked_ids,
        "free_ids": free_ids,
        "ids": ids,
        "copies": max(len(ids), 1),
        "tags": tags,
        "shiny": bool(extra.get("sh")),
        "url": wiki_url(raw.get("cid")),
    }


def expand_pack_card(c):
    """Carte d'un paquet ouvert (`/api/open` -> cards[]) : dict lisible, même forme que expand_group.
    Forme vérifiée sur une vraie réponse : cid, n, d, img (URL complète ou null), r, v, id, isNew (+ sh si chromatique)."""
    return {
        "cid": c.get("cid"),
        "name": c.get("n") or "?",
        "desc": c.get("d") or "",
        "img": _safe_img(c.get("img")),
        "rarity": c.get("r") or "C",
        "reads": _to_int(c.get("v")),
        "lang": c.get("lang") or "",
        "locked": False,
        "ids": [c["id"]] if c.get("id") else [],
        "copies": 1,
        "tags": [],
        "shiny": bool(c.get("sh")),
        "new": bool(c.get("isNew")),
        "url": wiki_url(c.get("cid")),
    }


TAG_COLOR = re.compile(r"^#[0-9a-f]{6}$")


def parse_tags(items):
    """Étiquettes du joueur (`GET /api/tags`, `POST /api/tag/*` -> tags) : id, nom, couleur (#rrggbb), dans l'ordre choisi sur le site."""
    out = []
    for t in items if isinstance(items, list) else []:
        if isinstance(t, dict) and _to_int(t.get("id")) > 0:
            color = str(t.get("color") or "").lower()
            out.append({"id": _to_int(t["id"]), "name": str(t.get("name") or "")[:40], "color": color if TAG_COLOR.match(color) else "#64748b",
                        "order": _to_int(t.get("ordre"))})
    return sorted(out, key=lambda x: (x["order"], x["id"]))


FUSION_RANKS = ("C", "PC", "R", "SR", "UR")  # les rangs qu'on peut fusionner (les légendaires et mythiques ne se fusionnent pas)


def parse_fusion(d):
    """Atelier de fusion (`GET /api/fusion`, `POST /api/fusion` -> `etat`). Forme vérifiée sur une vraie réponse :
    petite / cartes (2 ou 3 cartes), bonus / bonus2 (points de maîtrise par échec), recettes[{rang, vers, base, base2, echecs,
    chance, chance2, dispo}], rang, page, pages, total, parPage, liste[carte + id + exemplaires] (doublons d'abord)."""
    d = d if isinstance(d, dict) else {}
    recipes = []
    for x in d.get("recettes") or []:
        if isinstance(x, dict) and x.get("rang") in FUSION_RANKS:
            recipes.append({"rank": x["rang"], "to": str(x.get("vers") or ""), "base": _to_int(x.get("base")), "base2": _to_int(x.get("base2")),
                            "chance": _to_int(x.get("chance")), "chance2": _to_int(x.get("chance2")), "fails": _to_int(x.get("echecs")),
                            "avail": _to_int(x.get("dispo"))})
    cards = []
    for c in d.get("liste") or []:
        if isinstance(c, dict) and c.get("id"):
            card = expand_pack_card(c)
            card["id"] = _to_int(c["id"])
            card["copies"] = max(1, _to_int(c.get("exemplaires"), 1))
            cards.append(card)
    return {"small": _to_int(d.get("petite"), 2), "big": _to_int(d.get("cartes"), 3), "bonus": _to_int(d.get("bonus")), "bonus2": _to_int(d.get("bonus2")),
            "recipes": recipes, "rank": d.get("rang") if d.get("rang") in FUSION_RANKS else None, "page": _to_int(d.get("page")),
            "pages": _to_int(d.get("pages")), "total": _to_int(d.get("total")), "cards": cards}


def _parse_lot(lot):
    if not isinstance(lot, dict):
        return None
    return {
        "n": _to_int(lot.get("n")),
        "name": str(lot.get("nom") or "Lot"),
        "cards": [expand_pack_card(c) for c in lot.get("cartes") or [] if isinstance(c, dict)],
    }


def parse_auction(a):
    """Enchère de /api/auctions?scope=live -> dict lisible.
    Forme lue dans le JS du site (auctionTile / majTuile), jamais vue en vrai : id, card | lot{n, nom, cartes},
    price, min, bids, leader, seller, mine, leading, endsAt (secondes, heure du serveur), status."""
    card = a.get("card") if isinstance(a.get("card"), dict) else None
    return {
        "id": _to_int(a.get("id")),
        "card": expand_pack_card(card) if card else None,
        "lot": _parse_lot(a.get("lot")),
        "price": _to_int(a.get("price")),
        "min": _to_int(a.get("min")),
        "bids": _to_int(a.get("bids")),
        "leader": str(a.get("leader") or ""),
        "seller": str(a.get("seller") or ""),
        "mine": bool(a.get("mine")),
        "leading": bool(a.get("leading")),
        "ends_at": _to_float(a.get("endsAt")),
        "status": str(a.get("status") or "live"),
    }


def parse_history(a):
    """Achat ou vente terminé (/api/purchases, /api/ventes) -> dict lisible (forme lue dans cards.js, `achatTile`) :
    cid, title, rarity, img, shiny | lot{n, nom, cartes}, price, vente (vrai = c'est une vente), buyer / seller, ts."""
    vente = bool(a.get("vente"))
    card = None
    if not isinstance(a.get("lot"), dict):
        card = expand_pack_card({"cid": a.get("cid"), "n": a.get("title"), "r": a.get("rarity"), "img": a.get("img"), "sh": a.get("shiny")})
    return {
        "card": card,
        "lot": _parse_lot(a.get("lot")),
        "price": _to_int(a.get("price")),
        "sold": vente,
        "who": str(a.get("buyer") or "un joueur") if vente else str(a.get("seller") or "un bot"),
        "ts": _to_float(a.get("ts")),
    }


def parse_trade(t):
    """Échange de /api/trades?box=… -> dict lisible, vu depuis le joueur : ce qu'il donne, ce qu'il reçoit
    (même logique que `tradeHTML` dans social.js). Forme lue dans le JS, jamais vue en vrai."""
    inc = bool(t.get("incoming"))
    cards = lambda k: [expand_pack_card(c) for c in t.get(k) or [] if isinstance(c, dict)]  # noqa: E731
    return {
        "id": _to_int(t.get("id")),
        "incoming": inc,
        "other": str((t.get("from") if inc else t.get("to")) or "?"),
        "give": cards("take" if inc else "give"),
        "get": cards("give" if inc else "take"),
        "give_coins": _to_int(t.get("takeCoins" if inc else "giveCoins")),
        "get_coins": _to_int(t.get("giveCoins" if inc else "takeCoins")),
        "status": str(t.get("status") or "pending"),
        "message": str(t.get("message") or ""),
        "valid": t.get("valid") is not False,
        "created": _to_float(t.get("created")),
        "closed": _to_float(t.get("closed")),
    }


def parse_ranking(d):
    """/api/ranking?periode=… -> dict lisible (forme lue dans social.js, `paintRanking`, jamais vue en vrai)."""
    pts = d.get("points") if isinstance(d.get("points"), dict) else {}
    return {
        "points": {str(k): _to_int(v) for k, v in pts.items()},  # points par carte, selon la rareté
        "chroma_points": _to_int(d.get("diamant")),
        "rule": str(d.get("regle") or ""),  # "acquis" (semaine, mois) | "glissant" | ""
        "reset_in": _to_int(d.get("reste")),  # secondes avant la remise à zéro
        "top": [{
            "rank": _to_int(r.get("rank")), "name": str(r.get("name") or "?"), "guild": str(r.get("guild") or ""),
            "me": bool(r.get("me")), "chroma": _to_int(r.get("chroma")), "mythic": _to_int(r.get("mythic")),
            "legend": _to_int(r.get("legend")), "ultra": _to_int(r.get("ultra")),
            "cards": _to_int(r.get("cards")), "points": _to_int(r.get("points")),
        } for r in d.get("top") or [] if isinstance(r, dict)],
    }


def _names(v):
    return [str(n) for n in v if isinstance(n, str)][:50] if isinstance(v, list) else []


def parse_card_sheet(d):
    """Fiche d'une carte (`/api/card?cid=`) -> dict lisible. Forme lue dans cards.js (`sheetBody`, `provHTML`), jamais vue en vrai.
    Ne contient rien de la vue du marché `/api/pro/marche` : elle est réservée aux abonnés WIKI-PRO, on n'y touche pas."""
    c = d.get("card") if isinstance(d.get("card"), dict) else {}
    mine = []
    for m in d.get("mine") if isinstance(d.get("mine"), list) else []:
        if not isinstance(m, dict):
            continue
        p = m.get("prov") if isinstance(m.get("prov"), dict) else {}
        mine.append({
            "id": _to_int(m.get("id")), "state": str(m.get("state") or ""), "shiny": bool(m.get("sh")),
            "for_sale": bool(m.get("aVendre")),
            "via": str(p.get("via") or ""), "ts": _to_float(p.get("ts")), "price": _to_int(p.get("prix")) if p.get("prix") is not None else None,
            "from": str(p.get("de") or ""), "lot": bool(p.get("lot")),
        })
    return {
        "extract": str(c.get("e") or ""),
        "mine": mine,
        "wished": bool(d.get("wished")),
        "friends": _names(d.get("chezAmis")), "guild": _names(d.get("chezGuilde")), "friend_wishes": _names(d.get("souhaitAmis")),
        "auctions": [parse_auction(a) for a in d.get("auctions") or [] if isinstance(a, dict)][:20],
    }


def parse_friends(d):
    """/api/friends -> noms seulement (lu dans social.js, `paintFriends`)."""
    def people(v):
        return [{"name": str(u.get("name")), "fav": bool(u.get("fav"))} for u in v if isinstance(u, dict) and u.get("name")] if isinstance(v, list) else []
    return {"friends": people(d.get("friends")), "incoming": people(d.get("incoming")), "outgoing": people(d.get("outgoing"))}


def parse_user_cards(d):
    """/api/user/cards?name= -> cartes échangeables d'un ami, groupées : [{card, ids}] (lu dans social.js, ouverture de l'échange)."""
    out = []
    for g in d.get("groups") or []:
        if isinstance(g, dict) and isinstance(g.get("card"), dict):
            ids = [_to_int(i) for i in g.get("ids") or [] if _to_int(i) > 0]
            if ids:
                out.append({"card": expand_pack_card(g["card"]), "ids": ids})
    return out


def parse_corbeille(d):
    """/api/corbeille -> cartes recyclées récemment et récupérables (lu dans cards.js, `openCorbeille`)."""
    items = []
    for x in d.get("items") or []:
        if isinstance(x, dict) and _to_int(x.get("id")) > 0:
            items.append({"id": _to_int(x.get("id")), "card": expand_pack_card(x), "left": _to_int(x.get("reste"))})
    return {"items": items, "price": _to_int(d.get("prix")) or 1, "minutes": _to_int(d.get("minutes")) or 20}


def parse_pro_market(d):
    """/api/pro/marche (WIKI-PRO : abonnés seulement) -> statistiques et ventes récentes (lu dans cards.js, `marketBody`)."""
    def stats(s):
        s = s if isinstance(s, dict) else {}
        return {k: _to_int(s.get(k)) for k in ("n", "last", "avg", "min", "max")}

    def sales(v):
        return [{"ts": _to_float(x.get("ts")), "price": _to_int(x.get("price")), "title": str(x.get("title") or "")}
                for x in v if isinstance(x, dict)][-200:] if isinstance(v, list) else []
    return {"live": _to_int(d.get("live")), "stats": stats(d.get("stats")), "rarity": stats(d.get("rarity")),
            "sales": sales(d.get("sales")), "rsales": sales(d.get("rsales"))}


def _card_list(v):
    return [expand_pack_card(c) for c in v if isinstance(c, dict)][:12] if isinstance(v, list) else []


def parse_combat_info(d):
    """/api/combat -> quota de combats, amis à défier, historique, Mini-Pack (lu dans combat.js, `paintAccueil`)."""
    def person(u):
        return {"name": str(u.get("name")), "online": bool(u.get("enligne")), "fighting": bool(u.get("encombat")),
                "cards": _to_int(u.get("cartes")) if u.get("cartes") is not None else None, "fav": bool(u.get("fav"))}
    return {
        "left": _to_int(d.get("restant")), "total": _to_int(d.get("total")) or 5, "next": _to_float(d.get("prochain")),
        "window": _to_int(d.get("fenetre")), "size": _to_int(d.get("taille")) or 3, "wait": _to_int(d.get("attente")), "prep": _to_int(d.get("prepa")),
        "opponents": [person(u) for u in d.get("adversaires") or [] if isinstance(u, dict) and u.get("name")],
        "history": [{"me": _to_int(h.get("moi")), "them": _to_int(h.get("lui")), "defended": bool(h.get("defense")),
                     "opponent": str(h.get("adversaire") or "?"), "gain": _to_int(h.get("gain")), "when": _to_float(h.get("quand"))}
                    for h in d.get("historique") or [] if isinstance(h, dict)][:30],
        "chests": _to_int(d.get("coffres")), "chest_all": _to_int(d.get("coffreTous")) or 1, "chest_left": _to_int(d.get("coffreReste")),
    }


def parse_decks(d):
    """/api/combat/decks (et la réponse de deck / deck/supprimer) -> decks enregistrés (lu dans combat.js, `paintDecks`)."""
    out = []
    for dk in d.get("decks") or []:
        if isinstance(dk, dict) and _to_int(dk.get("id")) > 0:
            cards = dk.get("cartes") if isinstance(dk.get("cartes"), list) else []
            out.append({"id": _to_int(dk.get("id")), "name": str(dk.get("nom") or "")[:60], "complete": bool(dk.get("complet")),
                        "cards": [expand_pack_card(c) if isinstance(c, dict) else None for c in cards][:12],
                        "ids": [_to_int(i) for i in dk.get("ids") or [] if _to_int(i) > 0][:12]})
    return out[:20]


def parse_defi(d):
    """Défi en cours (réponses de defier / repondre, et /api/combat/defi) -> dict lisible."""
    if not isinstance(d, dict) or not d.get("id"):
        return None
    adv = d.get("adversaire") if isinstance(d.get("adversaire"), dict) else {}
    return {"id": _to_int(d.get("id")), "state": str(d.get("etat") or ""), "expire": _to_float(d.get("expire")), "launched": bool(d.get("lance")),
            "opponent": str(adv.get("name") or "?"), "my_ready": bool(d.get("moiPret")), "opp_ready": bool(d.get("advPret")),
            "team": _card_list(d.get("equipe"))}


# ---- vérification « es-tu un robot ? » avant un paquet (GET /api/defi) ----
# Le site envoie six pictogrammes en SVG brut ; on n'en garde que des formes simples, attribut par attribut,
# pour que l'interface les redessine elle-même (jamais d'innerHTML). La réponse, c'est le joueur qui la clique.
_SVG_NS = "{http://www.w3.org/2000/svg}"
_SVG_SHAPES = ("path", "circle", "ellipse", "rect", "polygon", "polyline", "line")
_SVG_NUM = r"-?[0-9.]+(?:e-?[0-9]+)?%?"
_SVG_ATTRS = {
    "d": r"[0-9MmLlHhVvCcSsQqTtAaZz .,+\-eE]{1,2000}",
    "points": r"[0-9 .,+\-eE]{1,2000}",
    "fill": r"#[0-9a-fA-F]{3,8}|none|currentColor|[a-z]{3,20}",
    "stroke": r"#[0-9a-fA-F]{3,8}|none|currentColor|[a-z]{3,20}",
    "transform": r"(?:(?:rotate|translate|scale|matrix|skewX|skewY)\([0-9 .,+\-eE]{1,120}\)\s*){1,4}",
    "fill-rule": r"nonzero|evenodd", "stroke-linecap": r"butt|round|square", "stroke-linejoin": r"miter|round|bevel",
    **{k: _SVG_NUM for k in ("cx", "cy", "r", "rx", "ry", "x", "y", "width", "height", "x1", "y1", "x2", "y2", "stroke-width", "opacity")},
}


def _pictogram(svg):
    """SVG du site -> {viewBox, shapes: [{tag, attrs}]}, ou None s'il contient quoi que ce soit d'autre que des formes."""
    if not isinstance(svg, str) or len(svg) > 6000 or "<!" in svg or "<?" in svg:  # pas de DOCTYPE ni d'entités
        return None
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return None
    if root.tag not in ("svg", _SVG_NS + "svg"):
        return None
    vb = root.get("viewBox", "0 0 40 40")
    if not re.fullmatch(r"(?:%s ){3}%s" % (_SVG_NUM, _SVG_NUM), vb):
        return None
    shapes = []
    for node in root.iter():
        if node is root:
            continue
        tag = node.tag.replace(_SVG_NS, "")
        if tag == "g" and not node.attrib:
            continue
        if tag not in _SVG_SHAPES or len(shapes) >= 30:
            return None
        attrs = {}
        for k, v in node.attrib.items():
            rule = _SVG_ATTRS.get(k)
            if rule is None or not re.fullmatch(rule, v.strip()):
                return None  # un attribut inconnu (onload, href, style…) : on jette tout le pictogramme
            attrs[k] = v.strip()
        shapes.append({"tag": tag, "attrs": attrs})
    return {"viewBox": vb, "shapes": shapes} if shapes else None


def parse_pack_challenge(d):
    """Réponse de GET /api/defi -> {id, consigne, choix: [pictogramme ou None]} ; l'index de `choix` est la réponse `rep`."""
    d = d if isinstance(d, dict) else {}
    cid = d.get("id")
    if not (isinstance(cid, str) and 0 < len(cid) <= 64 and cid.replace("-", "").replace("_", "").isalnum()):
        return None
    choix = d.get("choix") if isinstance(d.get("choix"), list) else []
    return {"id": cid, "consigne": str(d.get("consigne") or "")[:200], "choix": [_pictogram(s) for s in choix[:12]]}


def parse_duel(d):
    """Combat joué (réponse de equipe, événement `go`) -> détail rejouable. Le serveur joue TOUT : on ne fait que rejouer."""
    def hit(c):
        return {"by": "a" if c.get("par") == "a" else "b", "damage": _to_int(c.get("degats")), "crit": bool(c.get("crit")),
                "spell": str(c.get("sort") or "epee")[:12], "spell_name": str(c.get("sortNom") or "")[:40],
                "hp_a": _to_int(c.get("pvA")), "hp_b": _to_int(c.get("pvB"))}

    def round_(m):
        return {"hp_a": _to_int(m.get("pvA")), "hp_b": _to_int(m.get("pvB")), "left_a": _to_int(m.get("resteA")), "left_b": _to_int(m.get("resteB")),
                "hits": [hit(c) for c in m.get("coups") or [] if isinstance(c, dict)][:400], "sequential": bool(m.get("seq")),
                "winner": "a" if m.get("gagnant") == "a" else "b", "ko": bool(m.get("ko"))}
    me = d.get("moi") if isinstance(d.get("moi"), dict) else {}
    adv = d.get("adversaire") if isinstance(d.get("adversaire"), dict) else {}
    return {"me": str(me.get("name") or "Moi"), "opponent": str(adv.get("name") or "?"),
            "team_a": _card_list(d.get("equipeA")), "team_b": _card_list(d.get("equipeB")),
            "rounds": [round_(m) for m in d.get("manches") or [] if isinstance(m, dict)][:10],
            "won": bool(d.get("gagne")), "score_a": _to_int(d.get("scoreA")), "score_b": _to_int(d.get("scoreB")),
            "gain": _to_int(d.get("gain")), "left": _to_int(d.get("restant")), "total": _to_int(d.get("total"))}


def parse_chest(d):
    """/api/combat/coffre -> ce que contient le Mini-Pack (lu dans combat.js)."""
    c = d.get("carte") if isinstance(d.get("carte"), dict) else None
    return {"kind": "packs" if d.get("lot") == "paquets" else "wikiki", "n": _to_int(d.get("n")), "left": _to_int(d.get("reste")),
            "card": expand_pack_card(c) if c else None}


def parse_users(d):
    """/api/users?q= -> pseudos et présence seulement."""
    return [{"name": str(u.get("name")), "online": bool(u.get("enligne"))} for u in d.get("users") or []
            if isinstance(u, dict) and u.get("name") and not u.get("me")][:20]


def parse_notification(n):
    """Élément de /api/notifications (`items`) -> dict lisible (forme lue dans le JS du site)."""
    tone = n.get("tone")
    return {
        "id": _to_int(n.get("id")),
        "type": str(n.get("ntype") or n.get("type") or ""),
        "text": str(n.get("text") or ""),
        "tone": tone if tone in ("good", "bad") else "",
        "link": str(n.get("link") or ""),
        "read": bool(n.get("read")),
        "created": _to_float(n.get("created")),
    }


def parse_collection(payload):
    """Payload complet de /api/collection?v=2 -> dict prêt pour l'interface."""
    champs = payload.get("champs") or []
    imgp = payload.get("imgp") or []
    groups = payload.get("groups") or []
    if champs:
        cards = [expand_group(row, champs, imgp) for row in groups]
    else:  # ancien format : déjà des dicts
        cards = [dict(g) for g in groups]
    return {
        "cards": cards,
        "tags": parse_tags(payload.get("tags")),
        "rank": payload.get("rank") or {},
        "masked": [i for i in (_to_int(x) for x in payload.get("masquees") or []) if i > 0],  # exclusives masquées du profil (ids d'exemplaires)
    }


def compute_stats(cards, names=None):
    """Statistiques agrégées sur la collection."""
    names = names or {}
    by = {}
    for c in cards:
        b = by.setdefault(c["rarity"], {"unique": 0, "copies": 0})
        b["unique"] += 1
        b["copies"] += c["copies"]

    order = [r for r in RARITY_ORDER if r in by] + sorted(r for r in by if r not in RARITY_ORDER)
    rarities = [
        {"code": r, "label": names.get(r, r), **by[r]} for r in order
    ]

    def slim(c):
        return {k: c[k] for k in ("cid", "name", "rarity", "reads", "copies", "img")}

    return {
        "unique": len(cards),
        "copies": sum(c["copies"] for c in cards),
        "duplicates": sum(1 for c in cards if c["copies"] > 1),
        "extra_copies": sum(c["copies"] - 1 for c in cards),
        "shiny": sum(1 for c in cards if c["shiny"]),
        "locked": sum(1 for c in cards if c["locked"]),
        "rarities": rarities,
        "top_reads": [slim(c) for c in sorted(cards, key=lambda c: -c["reads"])[:10]],
        "top_copies": [slim(c) for c in sorted(cards, key=lambda c: -c["copies"])[:10] if c["copies"] > 1],
    }
