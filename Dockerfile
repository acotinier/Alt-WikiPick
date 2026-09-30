# Alt-WikiPick (version web) : interface Svelte compilée + serveur FastAPI, dans une seule image légère.
FROM node:22-alpine AS web
WORKDIR /app/webapp
COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci
COPY webapp/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    ALTWP_DATA=/data ALTWP_STATIC=/app/webapp/dist ALTWP_HOST=0.0.0.0 ALTWP_PORT=8000
WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
COPY wikipick/ wikipick/
COPY server/ server/
COPY --from=web /app/webapp/dist webapp/dist
# un utilisateur sans droits ; /data (sessions chiffrées, clé, dossiers des joueurs) est le seul endroit où l'on écrit
RUN useradd --system --uid 10001 altwp && mkdir /data && chown altwp /data
USER altwp
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=4s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)"
CMD ["python", "-m", "server"]
