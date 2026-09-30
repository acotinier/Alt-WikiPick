"""Chiffrement des sessions au repos, limitation de débit, en-têtes de sécurité."""
import base64
import hashlib
import json
import os
import stat
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def load_key(data_dir, secret=""):
    """Clé Fernet : dérivée de la phrase secrète si elle est donnée, sinon générée une fois dans data_dir/secret.key."""
    if secret:
        return base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    path = Path(data_dir) / "secret.key"
    try:
        return path.read_bytes().strip()
    except OSError:
        pass
    key = Fernet.generate_key()
    path.write_bytes(key)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return key


class Vault:
    """Les cookies wiki-pick des joueurs ne sont jamais écrits en clair."""

    def __init__(self, key):
        self._f = Fernet(key)

    def seal(self, obj):
        return self._f.encrypt(json.dumps(obj, separators=(",", ":")).encode("utf-8"))

    def open(self, blob):
        try:
            return json.loads(self._f.decrypt(bytes(blob)).decode("utf-8"))
        except (InvalidToken, ValueError, TypeError):
            return None


class RateLimiter:
    """Fenêtre glissante par clé. `allow` renvoie False quand la limite est atteinte."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def allow(self, key, limit, window):
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            if now - self._last_sweep > 300:  # les clés oubliées ne s'accumulent pas
                self._last_sweep = now
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > 3600]:
                    del self._hits[k]
            return True


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Les images viennent de Wikimedia, les avatars de wiki-pick.com : rien d'autre ne peut se charger.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; "
       "img-src 'self' data: https://upload.wikimedia.org https://thumb.wikimedia.org https://wiki-pick.com; "
       "font-src 'self'; connect-src 'self'; manifest-src 'self'; worker-src 'self'; "
       "base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'")

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
