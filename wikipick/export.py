"""Export de la collection en CSV (local : rien n'est envoyé nulle part).

Les noms de cartes viennent du site : une cellule qui commence par `=`, `+`, `-`, `@` (ou une tabulation)
serait prise pour une formule par Excel ou LibreOffice. On la préfixe d'une apostrophe, comme le recommande l'OWASP.
"""
import csv
import io

COLUMNS = ("Nom", "Rareté", "Lectures", "Exemplaires", "Chromatique", "Verrouillée", "Langue", "Identifiant", "Wikipédia")
_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_DANGEROUS) else text


def collection_csv(cards, names=None):
    """Cartes décodées (parse_collection) -> texte CSV, séparateur « ; » (Excel en français), triées par rareté puis lectures."""
    names = names or {}
    order = {"EXC": 0, "WBC": 1, "SIXSEVEN": 2, "M": 3, "L": 4, "UR": 5, "SR": 6, "R": 7, "PC": 8, "C": 9}
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    w.writerow(COLUMNS)
    for c in sorted(cards, key=lambda c: (order.get(c.get("rarity"), 99), -int(c.get("reads") or 0))):
        w.writerow([safe_cell(x) for x in (
            c.get("name"), names.get(c.get("rarity"), c.get("rarity")), c.get("reads"), c.get("copies"),
            "oui" if c.get("shiny") else "non", "oui" if c.get("locked") else "non", c.get("lang"), c.get("cid"), c.get("url"))])
    return out.getvalue()
