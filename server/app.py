"""Serveur d'Alt-WikiPick (version web, auto-hébergeable).

Un navigateur ne peut pas appeler wiki-pick.com directement (cookies et domaines différents) : ce serveur le fait à sa
place, avec le même code que l'appli de bureau (`wikipick/`). Le joueur se connecte avec ses identifiants wiki-pick
(transmis une seule fois, jamais gardés) ; le serveur garde ses cookies chiffrés et lui donne un cookie de session
propre à l'appli. Chaque appel de l'interface passe par `/api/rpc/<méthode>` sur une liste blanche (server/rpc.py)."""
import asyncio
import collections
import inspect
import json
import secrets
import threading
import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from wikipick.client import ApiError, WikiPickClient
from wikipick.export import collection_csv
from wikipick.parse import parse_pack_challenge

from . import config
from .accounts import AccountStore
from .rpc import ALLOWED
from .runtime import Hub
from .security import SECURITY_HEADERS, RateLimiter, Vault, load_key

COOKIE = "altwp"
MIME = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".html": "text/html", ".svg": "image/svg+xml",
        ".webmanifest": "application/manifest+json", ".json": "application/json", ".woff2": "font/woff2", ".png": "image/png",
        ".ico": "image/x-icon", ".jpg": "image/jpeg", ".webp": "image/webp", ".txt": "text/plain"}


class Call(BaseModel):
    args: list = Field(default_factory=list, max_length=8)


class LoginBody(BaseModel):
    pending: str = Field(min_length=8, max_length=64)
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)
    defi: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    rep: int = Field(ge=0, le=11)


class Pending:
    """Questions « es-tu un robot ? » en attente de réponse : un client anonyme par question, gardé 5 minutes."""
    TTL, MAX = 300, 500

    def __init__(self, factory, settings):
        self._factory, self._st = factory, settings
        self._items = collections.OrderedDict()
        self._lock = threading.Lock()

    def create(self):
        client = self._factory(session_file=self._st.data_dir / "pending.json")  # jamais écrit
        client.set_user_agent(self._st.user_agent)
        pid = secrets.token_urlsafe(16)
        with self._lock:
            self._purge_locked()
            while len(self._items) >= self.MAX:
                self._items.popitem(last=False)
            self._items[pid] = (time.monotonic(), client)
        return pid, client

    def take(self, pid):
        with self._lock:
            item = self._items.pop(pid, None)
        return item[1] if item and time.monotonic() - item[0] < self.TTL else None

    def discard(self, pid):
        with self._lock:
            self._items.pop(pid, None)

    def _purge_locked(self):
        now = time.monotonic()
        for k in [k for k, (t, _) in self._items.items() if now - t > self.TTL]:
            del self._items[k]

    def purge(self):
        with self._lock:
            self._purge_locked()


def create_app(settings=None, client_factory=None):
    st = settings or config.load()
    st.data_dir.mkdir(parents=True, exist_ok=True)
    factory = client_factory or WikiPickClient
    vault = Vault(load_key(st.data_dir, st.secret))
    store = AccountStore(st.data_dir / "accounts.db")
    hub = Hub(st, vault, store, factory)
    limiter = RateLimiter()
    pending = Pending(factory, st)

    def sweep():
        hub.reap()
        pending.purge()
        store.purge_expired(st.session_days)

    @asynccontextmanager
    async def lifespan(_app):
        async def reaper():
            while True:
                await asyncio.sleep(30)
                try:
                    await run_in_threadpool(sweep)
                except Exception:
                    pass
        task = asyncio.create_task(reaper())
        yield
        task.cancel()

    app = FastAPI(title="Alt-WikiPick", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.state.hub, app.state.store, app.state.settings = hub, store, st

    def client_ip(request):
        if st.trust_proxy:
            fwd = request.headers.get("x-forwarded-for", "")
            if fwd:
                return fwd.split(",")[0].strip()[:64]
        return request.client.host if request.client else "?"

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):  # un autre site ne peut pas agir au nom du joueur
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"ok": False, "error": "Origine refusée."}, status_code=403)
        resp = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            resp.headers.setdefault(k, v)
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        body = {"ok": False, "error": str(exc.detail)}
        if exc.status_code == 401:
            body["expired"] = True
        return JSONResponse(body, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def bad_request(_request, _exc):
        return JSONResponse({"ok": False, "error": "Requête invalide."}, status_code=422)

    def current(request: Request):
        uid = store.resolve(request.cookies.get(COOKIE), st.session_days)
        rt = hub.get(uid) if uid else None
        if not rt:
            raise HTTPException(401, "Session expirée, reconnecte-toi.")
        return rt

    def forget(uid):  # wiki-pick a refusé la session : le joueur doit se reconnecter
        store.drop_account(uid)
        hub.drop(uid, wipe=True)

    # ---------------- connexion ----------------
    @app.get("/api/auth/challenge")
    def challenge(request: Request):
        if not limiter.allow(f"chal:{client_ip(request)}", 12, 600):
            raise HTTPException(429, "Trop de demandes : réessaie dans quelques minutes.")
        pid, client = pending.create()
        try:
            q = parse_pack_challenge(client.pack_challenge())
        except ApiError as e:
            pending.discard(pid)
            return {"ok": False, "error": str(e)}
        if not q:
            pending.discard(pid)
            return {"ok": False, "error": "Le site n'a pas envoyé de question lisible : réessaie."}
        return {"ok": True, "pending": pid, "challenge": q}

    @app.post("/api/auth/login")
    def login(body: LoginBody, request: Request, response: Response):
        name_key = body.login.strip().lower()
        if not (limiter.allow(f"login:{client_ip(request)}", 10, 600) and limiter.allow(f"loginname:{name_key}", 6, 600)):
            raise HTTPException(429, "Trop d'essais : réessaie dans quelques minutes.")
        client = pending.take(body.pending)
        if not client:
            return {"ok": False, "retry": True, "error": "La question a expiré : recommence."}
        try:
            client.login(body.login.strip(), body.password, body.defi, body.rep)
            state = client.state()
        except ApiError as e:
            return {"ok": False, "retry": True, "error": str(e)}
        me = state.get("me") if isinstance(state, dict) else None
        uid = me.get("id") if isinstance(me, dict) else None
        if not isinstance(uid, int) or isinstance(uid, bool):
            return {"ok": False, "retry": True, "error": "Le site n'a pas ouvert de session : réessaie."}
        name = str(me.get("name") or "")[:100]
        if st.allowed_users and name.lower() not in st.allowed_users:
            return {"ok": False, "error": "Cette instance est privée."}
        if st.max_users and not store.has_account(uid) and store.count_accounts() >= st.max_users:
            return {"ok": False, "error": "Cette instance est pleine."}
        store.put_account(uid, name, vault.seal({"cookies": client.cookies_dict(), "ua": client.http.headers.get("User-Agent")}))
        hub.drop(uid)  # repart des nouveaux cookies
        token = store.create_session(uid)
        response.set_cookie(COOKIE, token, max_age=st.session_days * 86400, httponly=True, secure=st.secure_cookies, samesite="lax", path="/")
        return {"ok": True, "name": name}

    @app.get("/api/auth/me")
    def whoami(request: Request):
        uid = store.resolve(request.cookies.get(COOKIE), st.session_days)
        acc = store.get_account(uid) if uid else None
        return {"ok": bool(acc), "name": acc["name"] if acc else None}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response):
        gone = store.delete_session(request.cookies.get(COOKIE))
        if gone and gone[1] == 0:  # plus aucun appareil : on oublie les cookies wiki-pick et le cache
            store.drop_account(gone[0])
            hub.drop(gone[0], wipe=True)
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    # ---------------- le jeu ----------------
    @app.post("/api/rpc/{method}")
    def rpc(method: str, call: Call, rt=Depends(current)):
        if method not in ALLOWED:
            raise HTTPException(404, "Méthode inconnue.")
        if not limiter.allow(f"rpc:{rt.uid}", st.rpc_per_minute, 60):
            raise HTTPException(429, "Trop de requêtes : ralentis un peu.")
        fn = getattr(rt.service, method)
        try:
            inspect.signature(fn).bind(*call.args)
        except TypeError:
            raise HTTPException(422, "Arguments invalides.")
        out = fn(*call.args)
        if isinstance(out, dict) and out.get("expired"):
            forget(rt.uid)
        return out

    @app.get("/api/events")
    async def events(request: Request, rt=Depends(current)):
        """Le flux temps réel, filtré en Python : plusieurs appareils d'un même joueur partagent UNE connexion vers wiki-pick.com."""
        await run_in_threadpool(rt.service.ensure_me)
        hub.watch(rt, 1)
        rt.service.start_stream()
        mine = collections.deque()
        rt.subs.append(mine)

        async def gen():
            last, beat = None, 0
            try:
                yield "retry: 3000\n\n"
                while not await request.is_disconnected():
                    rt.pump()
                    if rt.state != last:
                        last = rt.state
                        yield f"event: live\ndata: {json.dumps(last)}\n\n"
                    while mine:
                        ev = mine.popleft()
                        if ev.get("event") == "expired":
                            forget(rt.uid)
                        yield f"event: msg\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    beat += 1
                    if beat % 15 == 0:
                        yield ": battement\n\n"
                    await asyncio.sleep(1)
            finally:
                if mine in rt.subs:
                    rt.subs.remove(mine)
                hub.watch(rt, -1)

        # Content-Encoding: identity empêche la compression de retenir les événements en mémoire tampon
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no", "Content-Encoding": "identity"})

    @app.get("/api/export.csv")
    def export_csv(rt=Depends(current)):
        cached = rt.service.cache_get()
        if not cached.get("ok"):
            raise HTTPException(404, "Aucune collection chargée : ouvre d'abord ta collection.")
        text = collection_csv(cached["data"]["cards"], cached["data"].get("names"))
        return Response(("﻿" + text).encode("utf-8"), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="wikipick-collection.csv"'})

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "players": hub.count()}

    # ---------------- l'interface (Svelte compilée) ----------------
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Introuvable.")
        root = st.static_dir
        if root.is_dir():
            target = (root / path).resolve()
            if path and target.is_file() and target.is_relative_to(root):
                cache = ("public, max-age=31536000, immutable" if path.startswith("assets/")
                         else "public, max-age=2592000" if path.startswith("fonts/") else "no-cache")
                return FileResponse(target, media_type=MIME.get(target.suffix.lower()), headers={"Cache-Control": cache})
            index = root / "index.html"
            if index.is_file():
                return FileResponse(index, media_type="text/html", headers={"Cache-Control": "no-cache"})
        raise HTTPException(404, "Interface non construite : lance `npm run build` dans webapp/.")

    return app
