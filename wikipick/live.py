"""Temps réel : lit /api/stream dans un thread, filtre, et garde une file d'événements que l'interface vient lire.

Règles :
- une seule connexion au flux, comme le site ;
- rien ne sort de Python sans passer par la liste blanche KEYS (le flux contient aussi les événements
  des autres joueurs, du fil, des guildes… qui ne concernent pas l'appli) ;
- les événements personnels (`to`) ne passent que s'ils sont pour le joueur connecté ;
- les nouvelles de guilde (`guild` : fil, tchat) ne passent que pour la guilde du joueur (`guild_id`) ;
- les enchères (très fréquentes) ne sont transmises que si l'onglet Marché est ouvert, sauf la mise en vente
  d'une carte surveillée (`watch_cids`) : elle est toujours transmise.
"""
import collections
import threading

from .client import SessionExpired
from .parse import _card_list, parse_duel

KEYS = {
    "notify": ("id", "type", "text", "kind", "link"),
    "message": ("from",),
    "trade": ("what",),
    "auction": ("what", "id", "price", "leader", "leaderId", "endsAt", "min", "extended", "sold", "winnerId", "cid"),
    "combat": ("what", "id", "nom", "expire"),
    "guild": ("what", "id", "mid", "par"),  # + `de`, `equipe`, `cartes`, `combat` : assainis à part (voir sanitize_combat)
}


def sanitize_combat(d):
    """Événement de combat : les cartes et le duel viennent d'un autre joueur, on ne garde que des champs connus."""
    out = {k: d[k] for k in KEYS["combat"] if k in d}
    if isinstance(d.get("de"), dict):
        out["from"] = str(d["de"].get("name") or "?")
    for src, dst in (("equipe", "team"), ("cartes", "cards")):
        if src in d:
            out[dst] = _card_list(d[src])
    if isinstance(d.get("combat"), dict):
        out["duel"] = parse_duel(d["combat"])
    return out


class LiveStream:
    def __init__(self, client, my_id, log_file=None):
        self.client = client
        self.my_id = my_id  # fonction sans argument -> id du joueur (ou None)
        self.watch_market = False
        self.watch_cids = frozenset()  # cartes surveillées par le joueur (liste locale)
        self.guild_id = None  # guilde du joueur : seules ses nouvelles passent
        self.state = "down"  # live | down
        self._events = collections.deque(maxlen=500)
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._log_file = log_file
        self._seen = set()

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(self._stop,), daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self._stop.set()
            self.watch_market = False
            self.state = "down"
            self._events.clear()
        self.client.close_stream()  # débloque la lecture en cours

    def poll(self):
        """Vide la file : liste d'événements {event, data}."""
        out = []
        while True:
            try:
                out.append(self._events.popleft())
            except IndexError:
                return out

    def push(self, event, data):
        keys = KEYS.get(event)
        if keys is None or not isinstance(data, dict):
            return
        if event == "auction":
            if not (self.watch_market or (data.get("what") == "new" and data.get("cid") in self.watch_cids)):
                return
        elif event == "guild":
            if not self.guild_id or data.get("id") != self.guild_id:
                return
        else:
            me = self.my_id()
            if me is None or data.get("to") != me:
                return
        self._events.append({"event": event, "data": sanitize_combat(data) if event == "combat" else {k: data[k] for k in keys if k in data}})

    def _log(self, event, data):
        """Journal de diagnostic : le NOM des événements et de leurs champs, jamais les valeurs."""
        if not self._log_file:
            return
        sig = f"{event}: " + (",".join(sorted(data)) if isinstance(data, dict) else type(data).__name__)
        if sig in self._seen:
            return
        self._seen.add(sig)
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(sig + "\n")
        except OSError:
            pass

    def _run(self, stop):
        tries, first = 0, True
        while not stop.is_set():
            try:
                for event, data in self.client.stream_events():
                    if stop.is_set():
                        return
                    if event == "open":
                        self.state, tries = "live", 0
                        if not first:  # des événements ont pu manquer pendant la coupure
                            self._events.append({"event": "resync", "data": {}})
                        first = False
                    else:
                        self._log(event, data)
                        self.push(event, data)
            except SessionExpired:
                self.state = "down"
                self._events.append({"event": "expired", "data": {}})
                return
            except Exception:
                pass  # coupure : on se reconnecte ci-dessous, avec un délai qui grandit
            self.state = "down"
            if stop.wait(min(30, 3 * 2 ** tries)):
                return
            tries += 1
