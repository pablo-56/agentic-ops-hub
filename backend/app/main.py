from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .db import init_db
from .kafka_bus import start_kafka, stop_kafka
from .routers import health, agent, topology, events, incidents, runbooks, knowledge, ingestion, streaming, graphql_api

app = FastAPI(title="Agentic Ops Hub API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.API_CORS_ORIGINS, "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(agent.router, prefix="/agent", tags=["agent"])
app.include_router(topology.router, prefix="/graph", tags=["graph"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
app.include_router(runbooks.router, prefix="/runbooks", tags=["runbooks"])
app.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
app.include_router(ingestion.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(streaming.router, tags=["streaming"])
app.include_router(graphql_api.router, tags=["graphql"])

@app.on_event("startup")
async def _startup():
    init_db()           # robust Postgres init (already in your repo)
    await start_kafka() # start aiokafka producer (best-effort)

@app.on_event("shutdown")
async def _shutdown():
    await stop_kafka()