"""Décodage d'un flux Server-Sent Events (`/api/stream` de wiki-pick.com).

Format : des blocs séparés par une ligne vide, avec `event: <nom>` et `data: <json>`.
Les lignes qui commencent par `:` sont des battements de cœur (ignorés).
"""
import json


def parse_sse(lines):
    """Itère des lignes de texte (sans retour à la ligne) -> (nom d'événement, données JSON)."""
    event, data = "message", []
    for line in lines:
        if line == "":
            if data:
                try:
                    yield event, json.loads("\n".join(data))
                except ValueError:
                    pass  # bloc illisible : on passe au suivant, le flux continue
            event, data = "message", []
        elif line.startswith(":"):
            continue
        else:
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                event = value
            elif field == "data":
                data.append(value)
