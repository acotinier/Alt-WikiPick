"""Alt-WikiPick Desktop : point d'entrée.

Une fenêtre locale (web/index.html) affiche l'interface ; le login se fait dans une vraie fenêtre wiki-pick.com,
puis la session est réutilisée par le client Python (requests). Toute la logique du jeu vit dans le noyau partagé
(`wikipick.service.Service`, aussi utilisé par le serveur web) : ici, seulement ce qui dépend du bureau.
"""
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

if not getattr(sys, "frozen", False):  # en développement, le noyau partagé (wikipick/) est à la racine du dépôt
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import webview  # noqa: E402

from wikipick.client import BASE, WikiPickClient, data_dir  # noqa: E402
from wikipick.service import Service  # noqa: E402

OPENABLE_HOSTS = ("wikipedia.org", "wiki-pick.com")
TITLE = "Wiki-Pick Desktop"
INK = "#07090e"  # = --ink dans web/style.css : pas de flash de couleur à l'ouverture


def resource_path(rel):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return str(base / rel)


class Api(Service):
    """Méthodes appelables depuis le JavaScript (window.pywebview.api.*) : le service partagé + la connexion par fenêtre."""

    def __init__(self):
        super().__init__(WikiPickClient(), data_dir())
        self._main_window = None
        self._login_window = None
        self._login_state = "idle"  # idle | pending | ok | cancelled
        self._lock = threading.Lock()

    # ---- session -------------------------------------------------------
    def status(self):
        if not self._client.cookies_dict():
            self._client.load_session()
        me = self._client.current_user() if self._client.cookies_dict() else None
        if me:
            return {"logged_in": True, "name": me.get("name")}
        return {"logged_in": False}

    def start_login(self):
        with self._lock:
            if self._login_state == "pending":
                return {"ok": True}
            self._login_state = "pending"
        win = webview.create_window("Connexion à Wiki-Pick", BASE + "/", width=1000, height=800)
        self._login_window = win
        win.events.closed += self._on_login_closed
        threading.Thread(target=self._watch_login, args=(win,), daemon=True).start()
        return {"ok": True}

    def _on_login_closed(self):
        with self._lock:
            if self._login_state == "pending":
                self._login_state = "cancelled"

    def _watch_login(self, win):
        last = None
        while self._login_state == "pending":
            time.sleep(1.5)
            try:
                jar = {}
                for cookie in win.get_cookies() or []:
                    for name, morsel in cookie.items():
                        domain = morsel["domain"] if "domain" in morsel.keys() else ""
                        if not domain or "wiki-pick.com" in domain:
                            jar[name] = morsel.value
                if not jar or jar == last:
                    continue
                last = dict(jar)
                self._client.set_cookies(jar)
                if self._client.current_user():
                    try:
                        self._client.set_user_agent(win.evaluate_js("navigator.userAgent"))
                    except Exception:
                        pass
                    self._client.save_session()
                    with self._lock:
                        self._login_state = "ok"
                    win.destroy()
                    return
            except Exception:
                continue  # fenêtre en cours de chargement / fermée

    def login_state(self):
        return {"state": self._login_state}

    def cancel_login(self):
        with self._lock:
            self._login_state = "cancelled"
        try:
            if self._login_window:
                self._login_window.destroy()
        except Exception:
            pass
        return {"ok": True}

    def import_cookie_header(self, header):
        """Secours : coller l'en-tête Cookie copié depuis les DevTools."""
        jar = {}
        for part in (header or "").split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k:
                    jar[k] = v
        if not jar:
            return {"ok": False, "error": "Aucun cookie reconnu dans le texte collé."}
        self._client.set_cookies(jar)
        if not self._client.current_user():
            self._client.http.cookies.clear()
            return {"ok": False, "error": "Ces cookies ne donnent pas de session valide."}
        self._client.save_session()
        return {"ok": True}

    def open_url(self, url):
        host = urlparse(url or "").hostname or ""
        if url.startswith("https://") and any(host == h or host.endswith("." + h) for h in OPENABLE_HOSTS):
            webbrowser.open(url)
            return {"ok": True}
        return {"ok": False}


def _tint_title_bar(title):
    """Windows 11 : la barre de titre native prend la couleur de l'appli. On garde une vraie fenêtre Windows
    (redimensionnement par les bords, aimantation) : pywebview en mode sans cadre les perd. Sans effet ailleurs."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if not hwnd:
            return
        for attr, value in ((20, 1),              # DWMWA_USE_IMMERSIVE_DARK_MODE (Windows 10 aussi)
                            (35, 0x000E0907),     # DWMWA_CAPTION_COLOR, COLORREF 0x00BBGGRR = #07090e
                            (36, 0x00F5F0ED),     # DWMWA_TEXT_COLOR = #edf0f5
                            (34, 0x0030211A)):    # DWMWA_BORDER_COLOR = #1a2130
            v = ctypes.c_int(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass  # Windows trop ancien : la barre reste celle du système


def main():
    api = Api()
    api._main_window = webview.create_window(
        TITLE,
        resource_path("web/index.html"),
        js_api=api,
        width=1320,
        height=860,
        min_size=(900, 600),
        background_color=INK,
    )
    api._main_window.events.shown += lambda: _tint_title_bar(TITLE)
    icon = Path(__file__).parent / "icon.ico"  # en .exe, pywebview reprend l'icône de l'exécutable
    webview.start(icon=str(icon) if icon.is_file() else None)


if __name__ == "__main__":
    main()
