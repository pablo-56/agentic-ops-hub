# Agentic Operational Intelligence Hub (Local Dev Repo) — v3

Fixes included:
- Postgres healthcheck + api depends_on condition (service_healthy)
- Startup DB retry loop to avoid race on container boot
- Web Dockerfile no longer requires package-lock.json

## Quickstart
```bash
cp .env.example .env
docker compose up --build
```
# agentic-ops-hub
# agentic-ops-hub
