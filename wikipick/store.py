"""Petits fichiers JSON locaux (préférences, journal des paquets, cartes surveillées).

Lecture tolérante (fichier absent, abîmé ou de mauvais type : on repart des valeurs par défaut) et écriture
atomique (fichier temporaire puis remplacement) : une panne au mauvais moment ne corrompt pas le fichier.
Rien de sensible ici : ni cookie, ni e-mail (la session reste dans session.json).
"""
import copy
import json
import os
import threading
from pathlib import Path


class JsonStore:
    def __init__(self, path, default):
        self.path = Path(path)
        self.default = default
        self._lock = threading.Lock()

    def read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return copy.deepcopy(self.default)
        return data if type(data) is type(self.default) else copy.deepcopy(self.default)

    def write(self, data):
        with self._lock:
            try:
                tmp = self.path.with_name(self.path.name + ".tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError:
                pass  # un fichier local en moins ne doit jamais faire échouer une action du joueur
