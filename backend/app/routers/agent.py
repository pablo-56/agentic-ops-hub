# backend/app/routers/agent.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, List, Tuple
from sqlalchemy import text
from ..db import engine
from ..kafka_bus import safe_publish as publish
import re, uuid, datetime as dt, asyncio
import httpx

router = APIRouter()

class AgentQuery(BaseModel):
    message: str
    scope: Optional[Dict[str, Any]] = None  # e.g., {"entity_type":"Service","entity_id":"order-service"}

class AgentResponse(BaseModel):
    reply: str
    confidence: float
    reasoning_summary: str
    related_entities: List[Dict[str, Any]] = []
    suggested_actions: List[Dict[str, Any]] = []

BASE = "http://localhost:8000"  # internal self-calls

def _now_iso():
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()

def _guess_entity(msg: str, scope: Optional[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str]]:
    """Very light parser: prefer explicit scope, otherwise parse 'service X', 'db Y', etc."""
    if scope and scope.get("entity_type") and scope.get("entity_id"):
        return scope["entity_type"], scope["entity_id"]

    # simple patterns
    patterns = [
        (r"\bservice\s+([a-zA-Z0-9\-_:./]+)", "Service"),
        (r"\bdatabase\s+([a-zA-Z0-9\-_:./]+)", "Database"),
        (r"\bdb\s+([a-zA-Z0-9\-_:./]+)", "Database"),
        (r"\bmachine\s+([a-zA-Z0-9\-_:./]+)", "Machine"),
        (r"\bsensor\s+([a-zA-Z0-9\-_:./]+)", "Sensor"),
        (r"\bapi\s+([a-zA-Z0-9\-_:./]+)", "API"),
        (r"\btopic\s+([a-zA-Z0-9\-_:./]+)", "Topic"),
        (r"\bserver\s+([a-zA-Z0-9\-_:./]+)", "Server"),
        (r"\bteam\s+([a-zA-Z0-9\-_:./]+)", "Team"),
        (r"\bsrc|srv[-_]?([0-9]+)", "Server"),
    ]
    for pat, lbl in patterns:
        m = re.search(pat, msg, re.I)
        if m:
            return lbl, m.group(1)
    return None, None

async def _call_json(method: str, url: str, **kwargs):
    """
    Small HTTP client helper:
    - follow_redirects=True fixes 307 from /runbooks -> /runbooks/
    - raise with response text for easier debugging
    """
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as cx:
        r = await cx.request(method, url, **kwargs)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = r.text
            except Exception:
                pass
            raise httpx.HTTPStatusError(
                f"{e} :: body={detail!r}", request=e.request, response=e.response
            )
        return r.json()

@router.post("/query", response_model=AgentResponse)
async def agent_query(payload: AgentQuery):
    msg = payload.message.strip().lower()

    # ---- Health / status ----------------------------------------------------------------
    if any(k in msg for k in ["status", "health", "how are we", "overview"]):
        topo = await _call_json("GET", f"{BASE}/graph/topology-summary")
        alerts = await _call_json("GET", f"{BASE}/events/alerts/active")
        reply = f"Plants={topo['summary'].get('plants',0)}, Services={topo['summary'].get('services',0)}, Incidents={topo['summary'].get('incidents',0)}. Active alerts={len(alerts.get('alerts',[]))}."
        return AgentResponse(
            reply=reply,
            confidence=0.8,
            reasoning_summary="Called /graph/topology-summary and /events/alerts/active.",
        )

    # ---- Incidents last X ----------------------------------------------------------------
    if "incident" in msg and any(k in msg for k in ["last", "recent", "open", "active"]):
        res = await _call_json("GET", f"{BASE}/incidents/search")
        reply = f"Found {len(res.get('incidents',[]))} matching incidents (stub or real depending on data)."
        return AgentResponse(
            reply=reply,
            confidence=0.7,
            reasoning_summary="Called /incidents/search.",
        )

    # ---- Why is X slow?  Show context + propose a runbook --------------------------------
    if "why" in msg or "what should we do" in msg or "remediate" in msg or "action" in msg:
        etype, eid = _guess_entity(msg, payload.scope)
        if not etype or not eid:
            raise HTTPException(status_code=400, detail="Provide scope.entity_type/entity_id or mention the component (e.g., 'service order-service').")

        # 1) Pull entity context + recent events
        entity_ctx, recent, timeline = await asyncio.gather(
            _call_json("GET", f"{BASE}/graph/entity/{etype}/{eid}"),
            _call_json("GET", f"{BASE}/events/recent", params={"entity_type": etype, "entity_id": eid, "window": "15m"}),
            _call_json("GET", f"{BASE}/events/timeline", params={"entity_type": etype, "entity_id": eid, "window": "2h"}),
        )

        # 2) Fetch candidate runbooks for this entity
        # same file, inside agent_query()
        rb = await _call_json("GET", f"{BASE}/runbooks/", params={"entity_type": etype, "entity_id": eid})
        runbooks = rb.get("runbooks", [])

        if not runbooks:
            return AgentResponse(
                reply=f"No runbooks bound to {etype}:{eid}.",
                confidence=0.5,
                reasoning_summary="Looked up /runbooks with entity filter; none found.",
                related_entities=[{"type": etype, "id": eid}],
                suggested_actions=[],
            )

        # 3) Propose the safest (lowest risk_level string) and create a pending action
        candidate = sorted(runbooks, key=lambda r: r.get("risk_level","medium").lower())[0]
        action_id = f"ACT-{uuid.uuid4().hex[:10].upper()}"

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO agent_actions(action_id, runbook_id, action_type, incident_id, entity_id,
                                          status, triggered_by, reasoning)
                VALUES (:aid, :rbid, 'runbook', NULL, :ent, 'pending_approval', 'agent',
                        'Proposed by Ops Copilot based on recent alerts and topology context.')
            """), {"aid": action_id, "rbid": candidate["runbook_id"], "ent": eid})

        # Emit proposal to Kafka for audit
        await publish("agent.actions", {
            "ts": _now_iso(),
            "action_id": action_id,
            "runbook_id": candidate["runbook_id"],
            "status": "pending_approval",
            "entity_id": eid,
            "reason": "Agent proposal",
        })

        return AgentResponse(
            reply=f"I propose runbook **{candidate['name']}** for {etype}:{eid}. Approve to execute.",
            confidence=0.7,
            reasoning_summary="Gathered entity context + events, selected lowest-risk bound runbook, created pending action.",
            related_entities=[{"type": etype, "id": eid}],
            suggested_actions=[{
                "action_id": action_id,
                "runbook_id": candidate["runbook_id"],
                "name": candidate["name"],
                "risk_level": candidate["risk_level"],
                "how_to_approve": f"POST /runbooks/{candidate['runbook_id']}/execute?mode=execute "
                                  f"with body {{\"target_entities\":[{{\"entity_type\":\"{etype}\",\"entity_id\":\"{eid}\"}}],"
                                  f"\"approve_action_id\":\"{action_id}\"}}"
            }],
        )

    # ---- Fallback -------------------------------------------------------------------------
    return AgentResponse(
        reply=f"Stub response for: {payload.message}",
        confidence=0.6,
        reasoning_summary="No matched intent; future: route to broader toolset.",
    )
