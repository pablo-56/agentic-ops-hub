# backend/app/routers/ingestion.py
from fastapi import APIRouter, Request
from typing import Dict, Any
from ..kafka_bus import safe_publish

router = APIRouter()

async def _json(request: Request) -> Dict[str, Any]:
    """Parse JSON body; tolerate empty or invalid JSON by returning {}."""
    try:
        return await request.json()
    except Exception:
        return {}

@router.post("/iot")
async def ingest_iot(request: Request):
    """IoT telemetry → iot.telemetry.raw"""
    data = await _json(request)
    return await safe_publish("iot.telemetry.raw", data)

@router.post("/monitoring")
async def ingest_monitoring(request: Request):
    """Prom/Alertmanager/Zabbix/Splunk alerts → monitoring.alerts"""
    data = await _json(request)
    return await safe_publish("monitoring.alerts", data)

@router.post("/logs")
async def ingest_logs(request: Request):
    """App logs/errors → app.logs"""
    data = await _json(request)
    return await safe_publish("app.logs", data)

@router.post("/deployments")
async def ingest_deployments(request: Request):
    """CI/CD deployment events → cicd.deployments"""
    data = await _json(request)
    return await safe_publish("cicd.deployments", data)

@router.post("/tickets")
async def ingest_tickets(request: Request):
    """Ticketing/Jira/ServiceNow hooks → ops.tickets"""
    data = await _json(request)
    return await safe_publish("ops.tickets", data)

@router.post("/topology")
async def ingest_topology(request: Request):
    """Topology changes (CMDB/MES/CM) → topology.updates"""
    data = await _json(request)
    return await safe_publish("topology.updates", data)
