"""`python -m server` : lance l'instance (ALTWP_HOST, ALTWP_PORT ; le reste dans .env.example)."""
import os

import uvicorn

from . import config
from .app import create_app


def main():
    st = config.load()
    uvicorn.run(create_app(st), host=os.environ.get("ALTWP_HOST", "0.0.0.0"), port=int(os.environ.get("ALTWP_PORT", "8000")),
                proxy_headers=False, access_log=False, log_level="info")


if __name__ == "__main__":
    main()
