# backend/app/routers/events.py
from fastapi import APIRouter, Query
from typing import Any, Dict, Optional, List
from ..events_cache import EVENTS

router = APIRouter()

@router.get("/recent")
async def get_recent_events(
    entity_type: str = Query(..., description="e.g., Machine|Service|Line"),
    entity_id: str = Query(..., description="natural id (e.g., M-42, order-service)"),
    window: str = Query("15m"),
) -> Dict[str, Any]:
    """Recent events for an entity in a time window."""
    items = EVENTS.query_recent(entity_type, entity_id, window)
    return {"entity_type": entity_type, "entity_id": entity_id, "window": window, "events": items}

@router.get("/timeline")
async def get_event_timeline(
    incident_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    window: str = "2h",
) -> Dict[str, Any]:
    """Unified time-ordered story for an incident/entity window."""
    items = EVENTS.timeline(incident_id, entity_type, entity_id, window)
    return {
        "incident_id": incident_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "window": window,
        "timeline": items,
    }

@router.get("/alerts/active")
async def get_active_alerts(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    severity: Optional[str] = None,
    window: str = "30m",
) -> Dict[str, Any]:
    """Active firing alerts within a window (simple in-cache view)."""
    alerts = EVENTS.active_alerts(entity_type, entity_id, severity, window)
    return {"entity_type": entity_type, "entity_id": entity_id, "severity": severity, "alerts": alerts}

@router.get("/deployments/history")
async def get_deploy_history(
    service_name: str,
    window: str = "24h",
) -> Dict[str, Any]:
    """Naive deploy history from cache (events posted to cicd.deployments)."""
    items = EVENTS.query_recent("Service", service_name, window)
    deploys = [e for e in items if e["topic"] == "cicd.deployments"]
    return {"service_name": service_name, "window": window, "deployments": deploys}
