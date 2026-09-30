"""Réglages d'une instance : tout passe par des variables d'environnement (voir `.env.example`)."""
import os
from dataclasses import dataclass
from pathlib import Path


def _flag(value, default):
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "oui", "on")


def _int(value, default, lo=0, hi=10**6):
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path                 # sessions chiffrées (SQLite), clé, dossiers par joueur
    secret: str                    # phrase secrète qui chiffre les sessions ; vide = clé générée dans data_dir/secret.key
    secure_cookies: bool           # cookie `Secure` (HTTPS) : laisser à vrai sauf essai en HTTP hors localhost
    session_days: int              # durée d'une session de l'appli, glissante
    max_users: int                 # nombre maximum de comptes wiki-pick sur l'instance (0 = illimité)
    allowed_users: frozenset       # si non vide : seuls ces pseudos (minuscules) peuvent se connecter
    user_agent: str                # User-Agent envoyé à wiki-pick.com
    static_dir: Path               # l'interface compilée (webapp/dist)
    trust_proxy: bool              # lire l'IP dans X-Forwarded-For (derrière Caddy, nginx…)
    rpc_per_minute: int            # appels de l'interface par minute et par joueur


def load(env=None):
    e = os.environ if env is None else env
    root = Path(__file__).resolve().parents[1]
    allowed = frozenset(p.strip().lower() for p in (e.get("ALTWP_ALLOWED_USERS") or "").split(",") if p.strip())
    return Settings(
        data_dir=Path(e.get("ALTWP_DATA") or "data").resolve(),
        secret=e.get("ALTWP_SECRET") or "",
        secure_cookies=_flag(e.get("ALTWP_COOKIE_SECURE"), True),
        session_days=_int(e.get("ALTWP_SESSION_DAYS"), 30, 1, 365),
        max_users=_int(e.get("ALTWP_MAX_USERS"), 20, 0, 100000),
        allowed_users=allowed,
        user_agent=e.get("ALTWP_USER_AGENT") or "Mozilla/5.0 (compatible; Alt-WikiPick-Web/0.1; +https://github.com/acotinier/Alt-WikiPick)",
        static_dir=Path(e.get("ALTWP_STATIC") or root / "webapp" / "dist").resolve(),
        trust_proxy=_flag(e.get("ALTWP_TRUST_PROXY"), False),
        rpc_per_minute=_int(e.get("ALTWP_RPC_PER_MINUTE"), 240, 10, 100000),
    )
