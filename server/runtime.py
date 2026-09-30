"""Un `Service` par joueur connecté (le même pour tous ses appareils), créé à la demande et libéré quand il est inactif.

Ressources : un joueur sans appareil ouvert n'a ni thread ni connexion vers wiki-pick.com. Le flux temps réel d'un joueur
ne tourne que tant qu'au moins un navigateur écoute ses événements (et 45 s après), puis il s'arrête."""
import threading
import time

from wikipick.client import WikiPickClient
from wikipick.service import Service

STREAM_GRACE = 45      # secondes sans navigateur à l'écoute avant d'arrêter le flux
IDLE_DROP = 20 * 60    # secondes sans aucun appel avant de libérer le joueur de la mémoire


class Runtime:
    def __init__(self, uid, name, service):
        self.uid, self.name, self.service = uid, name, service
        self.last = time.monotonic()
        self.watchers = 0
        self.unwatched_since = time.monotonic()
        self.subs = []      # une file par navigateur à l'écoute : tous reçoivent chaque événement
        self.state = None   # « live » / « down », l'état de la connexion vers wiki-pick.com

    def touch(self):
        self.last = time.monotonic()

    def pump(self):
        """Vide la file du flux (appel local, sans réseau) et la distribue à tous les navigateurs à l'écoute.
        Appelé depuis la boucle asyncio : pas de concurrence, pas de verrou."""
        r = self.service.poll_events()
        self.state = r.get("state")
        for ev in r.get("events") or []:
            for q in self.subs:
                q.append(ev)


class Hub:
    def __init__(self, settings, vault, store, client_factory=None):
        self.settings, self.vault, self.store = settings, vault, store
        self._factory = client_factory or WikiPickClient
        self._rt = {}
        self._lock = threading.Lock()

    def _user_dir(self, uid):
        d = self.settings.data_dir / "users" / str(int(uid))
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get(self, uid):
        with self._lock:
            rt = self._rt.get(uid)
            if rt:
                rt.touch()
                return rt
        acc = self.store.get_account(uid)
        data = self.vault.open(acc["blob"]) if acc else None
        if not data or not data.get("cookies"):
            return None
        d = self._user_dir(uid)
        client = self._factory(session_file=d / "session.json")  # jamais écrit : les cookies vivent chiffrés dans la base
        client.set_cookies(data["cookies"])
        client.set_user_agent(data.get("ua") or self.settings.user_agent)
        rt = Runtime(uid, acc["name"], Service(client, d))
        with self._lock:
            return self._rt.setdefault(uid, rt)

    def drop(self, uid, wipe=False):
        """Libère le joueur ; wipe=True (déconnexion définitive) efface aussi son cache de collection."""
        with self._lock:
            rt = self._rt.pop(uid, None)
        if rt:
            try:
                rt.service.stop_stream()
                if wipe:
                    rt.service.logout()
            except Exception:
                pass

    def watch(self, rt, delta):
        with self._lock:
            rt.watchers = max(0, rt.watchers + delta)
            if rt.watchers == 0:
                rt.unwatched_since = time.monotonic()
        rt.touch()

    def reap(self):
        now = time.monotonic()
        with self._lock:
            items = list(self._rt.values())
        for rt in items:
            if rt.watchers == 0 and now - rt.unwatched_since > STREAM_GRACE:
                rt.service.stop_stream()
            if rt.watchers == 0 and now - rt.last > IDLE_DROP:
                self.drop(rt.uid)

    def count(self):
        with self._lock:
            return len(self._rt)
