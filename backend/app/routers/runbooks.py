# backend/app/routers/runbooks.py
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from ..db import engine
from ..kafka_bus import safe_publish as publish
import uuid
import datetime as dt

router = APIRouter()

# --------- Models -------------------------------------------------------------

class RunbookExecution(BaseModel):
    mode: str = "dry_run"  # dry_run | execute
    target_entities: List[Dict[str, Any]] = []  # [{entity_type, entity_id}]
    incident_id: Optional[str] = None
    approve_action_id: Optional[str] = None  # when approving a pending proposal

# --------- Helpers ------------------------------------------------------------

def _steps_for(runbook_id: str, targets: List[Dict[str, Any]]) -> List[str]:
    """
    Minimal step generator (mock automation):
    In real life you'd dispatch to Ansible/SRE scripts/K8s ops, etc.
    """
    # Simple examples keyed by runbook id prefix
    if runbook_id.startswith("RB-RESTART"):
        tid = ", ".join([t.get("entity_id", "?") for t in targets]) or "target"
        return [
            f"Check health of {tid}",
            f"Drain traffic from {tid}",
            f"Restart {tid}",
            f"Warm-up & health-check {tid}",
            f"Restore traffic to {tid}",
        ]
    if runbook_id.startswith("RB-REDUCE-RATE"):
        return ["Calculate safe reduction", "Apply scaling to line/service", "Monitor for 10m"]
    if runbook_id.startswith("RB-SWITCH-DB"):
        return ["Enable read-only on primary", "Promote replica", "Redirect traffic", "Validate consistency"]
    # generic fallback
    return ["Validate preconditions", "Apply action", "Verify outcome", "Record evidence"]

def _now_iso() -> str:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()

# --------- Endpoints ----------------------------------------------------------

@router.get("/")
async def list_runbooks(
    entity_type: str | None = Query(None, description="Filter by entity type"),
    entity_id: str | None   = Query(None, description="Filter by entity id (LIKE binding)"),
    only_enabled: bool = True,
):
    """
    Returns runbooks. When entity filters are passed, returns those bound to the entity
    via runbook_bindings (entity_type + match_pattern LIKE match on entity_id).
    """
    with engine.begin() as conn:
        if entity_type and entity_id:
            q = text("""
                SELECT rb.runbook_id, rb.name, rb.description, rb.risk_level, rb.enabled
                FROM runbooks rb
                JOIN runbook_bindings b
                  ON b.runbook_id = rb.runbook_id
                 AND b.entity_type = :etype
                 AND :eid LIKE b.match_pattern   -- pattern stored like '%order-service%'
                WHERE (:enabled IS FALSE OR rb.enabled = TRUE)
                ORDER BY rb.risk_level, rb.name
            """)
            rows = conn.execute(q, {"etype": entity_type, "eid": entity_id, "enabled": only_enabled}).mappings().all()
        else:
            q = text("""
                SELECT runbook_id, name, description, risk_level, enabled
                FROM runbooks
                WHERE (:enabled IS FALSE OR enabled = TRUE)
                ORDER BY risk_level, name
            """)
            rows = conn.execute(q, {"enabled": only_enabled}).mappings().all()

    return {"runbooks": rows, "filters": {"entity_type": entity_type, "entity_id": entity_id}}

# at the bottom of backend/app/routers/runbooks.py, AFTER list_runbooks() is defined:

# Accept /runbooks (no trailing slash) as well
@router.get("")
async def list_runbooks_noslash(
    entity_type: str | None = None,
    entity_id: str | None = None,
    only_enabled: bool = True,
):
    return await list_runbooks(entity_type=entity_type, entity_id=entity_id, only_enabled=only_enabled)



@router.post("/{runbook_id}/execute")
async def execute_runbook(runbook_id: str, payload: RunbookExecution):
    """
    - dry_run: return the step list only.
    - execute: write agent_actions row, emit event to Kafka (agent.actions), return execution receipt.
      If approve_action_id is passed, mark that action as approved by user and continue to execute.
    """
    steps = _steps_for(runbook_id, payload.target_entities or [])
    mode = payload.mode or "dry_run"

    # Approve a pending proposal if given
    if payload.approve_action_id:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE agent_actions
                   SET status = 'approved',
                       approved_by = COALESCE(approved_by, 'human'),
                       reasoning = COALESCE(reasoning, '') || E'\nApproved at ' || NOW()
                 WHERE action_id = :aid
            """), {"aid": payload.approve_action_id})

    if mode == "dry_run":
        return {"runbook_id": runbook_id, "mode": "dry_run", "steps": steps, "executed": False}

    # "execute" mode -> log to DB + emit Kafka event
    action_id = f"ACT-{uuid.uuid4().hex[:10].upper()}"
    entity_id = (payload.target_entities[0] or {}).get("entity_id") if payload.target_entities else None

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO agent_actions(action_id, runbook_id, action_type, incident_id, entity_id,
                                      status, triggered_by, approved_by, reasoning)
            VALUES (:aid, :rbid, 'runbook', :inc, :ent, 'executing', 'agent', COALESCE(:approved_by, 'human'),
                    :reason)
        """), {
            "aid": action_id,
            "rbid": runbook_id,
            "inc": payload.incident_id,
            "ent": entity_id,
            "approved_by": "human" if payload.approve_action_id else None,
            "reason": f"Executing {runbook_id} with {len(steps)} steps at { _now_iso() }",
        })

    # Emit audit event to Kafka
    await publish("agent.actions", {
        "ts": _now_iso(),
        "action_id": action_id,
        "runbook_id": runbook_id,
        "mode": "execute",
        "incident_id": payload.incident_id,
        "entity_id": entity_id,
        "steps": steps,
        "status": "executing",
    })

    # Fake completion (dev) – in prod you'd run async workers and update later
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE agent_actions SET status='completed'
            WHERE action_id=:aid
        """), {"aid": action_id})

    await publish("agent.actions", {
        "ts": _now_iso(),
        "action_id": action_id,
        "runbook_id": runbook_id,
        "status": "completed",
    })

    return {"runbook_id": runbook_id, "mode": "execute", "action_id": action_id, "executed": True, "steps": steps}

@router.get("/agent-actions")
async def get_agent_actions(
    incident_id: str | None = None,
    entity_id: str | None = None,
    status: str | None = None,
):
    """
    Read audit log of agent actions. Filterable by incident/entity/status.
    """
    clauses = []
    params = {}
    if incident_id:
        clauses.append("incident_id = :inc")
        params["inc"] = incident_id
    if entity_id:
        clauses.append("entity_id = :ent")
        params["ent"] = entity_id
    if status:
        clauses.append("status = :st")
        params["st"] = status

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    q = text(f"""
        SELECT action_id, runbook_id, action_type, incident_id, entity_id,
               status, triggered_by, approved_by, reasoning, created_at
          FROM agent_actions
          {where}
         ORDER BY created_at DESC
         LIMIT 200
    """)

    with engine.begin() as conn:
        rows = conn.execute(q, params).mappings().all()
    return {"actions": rows}
