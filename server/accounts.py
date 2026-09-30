"""Comptes et sessions de l'appli (SQLite). Un compte = un joueur wiki-pick, avec ses cookies chiffrés ;
une session = un navigateur connecté à ce compte (téléphone, ordinateur…). Seule l'empreinte du jeton est gardée."""
import secrets
import sqlite3
import threading
import time

from .security import token_hash

SEEN_EVERY = 600  # secondes : la date de dernière activité n'est réécrite qu'à ce rythme


class AccountStore:
    def __init__(self, path):
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("CREATE TABLE IF NOT EXISTS accounts (uid INTEGER PRIMARY KEY, name TEXT NOT NULL, blob BLOB NOT NULL, updated REAL NOT NULL)")
            self._db.execute("CREATE TABLE IF NOT EXISTS sessions (tid TEXT PRIMARY KEY, uid INTEGER NOT NULL, created REAL NOT NULL, seen REAL NOT NULL)")
            self._db.execute("CREATE INDEX IF NOT EXISTS sessions_uid ON sessions(uid)")

    def _q(self, sql, args=()):
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    # ---- comptes ----
    def put_account(self, uid, name, blob):
        self._q("INSERT INTO accounts(uid, name, blob, updated) VALUES(?,?,?,?) ON CONFLICT(uid) DO UPDATE SET name=excluded.name, blob=excluded.blob, updated=excluded.updated",
                (uid, name, blob, time.time()))

    def get_account(self, uid):
        rows = self._q("SELECT name, blob FROM accounts WHERE uid=?", (uid,))
        return {"name": rows[0][0], "blob": rows[0][1]} if rows else None

    def has_account(self, uid):
        return bool(self._q("SELECT 1 FROM accounts WHERE uid=?", (uid,)))

    def count_accounts(self):
        return self._q("SELECT COUNT(*) FROM accounts")[0][0]

    def drop_account(self, uid):
        """Plus de cookies, plus de session : le joueur doit se reconnecter."""
        self._q("DELETE FROM sessions WHERE uid=?", (uid,))
        self._q("DELETE FROM accounts WHERE uid=?", (uid,))

    # ---- sessions ----
    def create_session(self, uid):
        token = secrets.token_urlsafe(32)
        now = time.time()
        self._q("INSERT INTO sessions(tid, uid, created, seen) VALUES(?,?,?,?)", (token_hash(token), uid, now, now))
        return token

    def resolve(self, token, max_age_days):
        """uid de la session, ou None (inconnue ou expirée). L'activité prolonge la session."""
        if not token or len(token) > 100:
            return None
        rows = self._q("SELECT uid, seen FROM sessions WHERE tid=?", (token_hash(token),))
        if not rows:
            return None
        uid, seen = rows[0]
        now = time.time()
        if now - seen > max_age_days * 86400:
            self._q("DELETE FROM sessions WHERE tid=?", (token_hash(token),))
            return None
        if now - seen > SEEN_EVERY:
            self._q("UPDATE sessions SET seen=? WHERE tid=?", (now, token_hash(token)))
        return uid

    def delete_session(self, token):
        """Supprime la session ; renvoie (uid, sessions restantes pour ce compte) ou None."""
        h = token_hash(token or "")
        rows = self._q("SELECT uid FROM sessions WHERE tid=?", (h,))
        if not rows:
            return None
        uid = rows[0][0]
        self._q("DELETE FROM sessions WHERE tid=?", (h,))
        return uid, self._q("SELECT COUNT(*) FROM sessions WHERE uid=?", (uid,))[0][0]

    def purge_expired(self, max_age_days):
        self._q("DELETE FROM sessions WHERE seen<?", (time.time() - max_age_days * 86400,))
        self._q("DELETE FROM accounts WHERE uid NOT IN (SELECT DISTINCT uid FROM sessions)")
