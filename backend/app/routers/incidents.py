# backend/app/routers/incidents.py
"""
Incident & Ticket Service
- Primary store: Postgres (incidents, incident_entities, tickets)
- Graph mirror:  Neo4j (:Incident, :Ticket nodes, AFFECTS rel to assets/services)
- Event bus:     Kafka topic 'ops.incidents' (create/update/link/ticket events)

Design notes:
- Relationship whitelist in graph is enforced via sanitize_label() and only AFFECTS is used
  for linking entities. For 'root_cause', we encode as AFFECTS {role:'root_cause'} to stay
  inside REL_ALL (no custom rel types).
- Kafka publishing is best-effort and non-blocking; endpoint success does not depend on Kafka.
"""

import os
import json
import uuid
import logging
import asyncio
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from ..db import engine
from ..graph import run_cypher, sanitize_label  # Neo4j helpers

# --- Kafka (aiokafka preferred; fallback to no-op if unavailable) ------------------

logger = logging.getLogger(__name__)
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_INCIDENTS", "ops.incidents")

_producer = None
_producer_lock = asyncio.Lock()

async def _get_producer():
    """
    Lazy-init an AIOKafkaProducer. If client is missing or cluster is unreachable,
    return a sentinel that just logs.
    """
    global _producer
    async with _producer_lock:
        if _producer is not None:
            return _producer
        try:
            from aiokafka import AIOKafkaProducer  # runtime import to avoid hard dependency at import time
            _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, value_serializer=lambda v: json.dumps(v).encode())
            await _producer.start()
            logger.info("AIOKafkaProducer started for ops.incidents")
        except Exception as e:  # pragma: no cover
            logger.warning("Kafka disabled (producer init failed): %s", e)
            class _NoOp:
                async def send_and_wait(self, *args, **kwargs):
                    logger.debug("Kafka noop send: %s %s", args, kwargs)
            _producer = _NoOp()
        return _producer

async def _emit(event: Dict[str, Any]):
    """
    Publish an event to Kafka (best effort).
    """
    try:
        producer = await _get_producer()
        key = (event.get("incident_id") or event.get("ticket_id") or "ops").encode()
        await producer.send_and_wait(KAFKA_TOPIC, value=event, key=key)
    except Exception as e:  # pragma: no cover
        logger.warning("Kafka publish failed: %s", e)


# --- Helpers -----------------------------------------------------------------------

def _new_incident_id() -> str:
    return f"INC-{uuid.uuid4().hex[:10].upper()}"

def _new_ticket_id() -> str:
    return f"TIC-{uuid.uuid4().hex[:10].upper()}"

def _status_is_closed(status: str) -> bool:
    return status.lower() in {"mitigated", "resolved", "closed"}

# Map entity role -> relationship properties (always AFFECTS to respect REL_ALL)
def _affects_rel_props(role: str) -> Dict[str, Any]:
    role = (role or "affected").lower()
    if role not in {"affected", "root_cause"}:
        role = "affected"
    return {"role": role}


# --- Pydantic models ---------------------------------------------------------------

class IncidentEntity(BaseModel):
    entity_type: str  # must be in ALLOWED_LABELS (e.g., Service, Machine, Plant, ...)
    entity_id: str
    role: Literal["affected", "root_cause"] = "affected"

class IncidentCreate(BaseModel):
    summary: str
    severity: Literal["low", "medium", "high", "critical"]
    entities: List[IncidentEntity] = Field(default_factory=list)
    source: Literal["agent", "human"] = "human"

class IncidentUpdate(BaseModel):
    status: Literal["investigating", "mitigated", "resolved", "closed"]
    resolution_summary: Optional[str] = None

class IncidentSearchResponse(BaseModel):
    incident_id: str
    summary: str
    severity: str
    status: str
    created_at: str
    updated_at: str

class TicketCreate(BaseModel):
    incident_id: str
    system: Literal["jira", "servicenow", "mock"] = "mock"
    title: str
    description: Optional[str] = None
    assignee_team: Optional[str] = None

class TicketUpdateStatus(BaseModel):
    ticket_id: str
    status: str

router = APIRouter()


# --- Neo4j ops ---------------------------------------------------------------------

def _neo4j_merge_incident(incident_id: str, summary: str, severity: str, status: str):
    """
    Create/Update the :Incident node in Neo4j.
    """
    q = """
    MERGE (i:Incident {id: $id})
    ON CREATE SET i.summary=$summary, i.severity=$severity, i.status=$status, i.created_at=datetime()
    ON MATCH  SET i.summary=$summary, i.severity=$severity, i.status=$status, i.updated_at=datetime()
    RETURN i
    """
    run_cypher(q, {"id": incident_id, "summary": summary, "severity": severity, "status": status})

def _neo4j_update_incident_status(incident_id: str, status: str, resolution_summary: Optional[str]):
    """
    Update status (+ optional resolution_summary) on :Incident.
    """
    q = """
    MATCH (i:Incident {id: $id})
    SET i.status=$status,
        i.updated_at=datetime()
    WITH i
    FOREACH (_ IN CASE WHEN $resolution_summary IS NOT NULL THEN [1] ELSE [] END |
        SET i.resolution_summary=$resolution_summary
    )
    RETURN i
    """
    run_cypher(q, {"id": incident_id, "status": status, "resolution_summary": resolution_summary})

def _neo4j_link_incident_entity(incident_id: str, entity_type: str, entity_id: str, role: str):
    """
    Link (:Incident)-[:AFFECTS {role:<role>}]->(:<entity_type> {id:<entity_id>})
    Only uses allowed rel type AFFECTS; encodes role on the rel to respect REL_ALL.
    """
    label = sanitize_label(entity_type)
    q = f"""
    MERGE (i:Incident {{id: $incident_id}})
    MERGE (e:{label} {{id: $entity_id}})
    MERGE (i)-[r:AFFECTS]->(e)
    ON CREATE SET r.role = $role, r.created_at=datetime()
    ON MATCH  SET r.role = $role, r.updated_at=datetime()
    RETURN r
    """
    run_cypher(q, {"incident_id": incident_id, "entity_id": entity_id, "role": role})

def _neo4j_merge_ticket(ticket_id: str, system: str, status: str, incident_id: str,
                        title: Optional[str], assignee_team: Optional[str], external_id: Optional[str]):
    """
    Create/Update :Ticket and TRACKS relationship to :Incident.
    """
    q = """
    MERGE (t:Ticket {id: $ticket_id})
    ON CREATE SET t.system=$system, t.status=$status, t.title=$title,
                  t.assignee_team=$assignee_team, t.external_id=$external_id,
                  t.created_at=datetime()
    ON MATCH  SET t.system=$system, t.status=$status, t.title=$title,
                  t.assignee_team=$assignee_team, t.external_id=$external_id,
                  t.updated_at=datetime()
    WITH t
    MATCH (i:Incident {id: $incident_id})
    MERGE (t)-[:TRACKS]->(i)
    RETURN t
    """
    run_cypher(q, {
        "ticket_id": ticket_id,
        "system": system,
        "status": status,
        "title": title,
        "assignee_team": assignee_team,
        "external_id": external_id,
        "incident_id": incident_id
    })


# --- Endpoints ---------------------------------------------------------------------

@router.post("/", summary="Create an incident")
async def create_incident(payload: IncidentCreate):
    """
    1) Insert incident into Postgres
    2) Create/Update :Incident in Neo4j
    3) Link provided entities in Postgres + Neo4j with AFFECTS {role}
    4) Emit 'incident.created' to Kafka
    """
    incident_id = _new_incident_id()
    # 1) Postgres: insert incident
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO incidents (incident_id, summary, severity, status)
                VALUES (:iid, :summary, :severity, 'investigating')
            """),
            {"iid": incident_id, "summary": payload.summary, "severity": payload.severity}
        )
        # Insert incident_entities if provided
        for ent in payload.entities:
            conn.execute(
                text("""
                    INSERT INTO incident_entities (incident_id, entity_type, entity_id, role)
                    VALUES (:iid, :etype, :eid, :role)
                    ON CONFLICT (incident_id, entity_type, entity_id, role) DO NOTHING
                """),
                {"iid": incident_id, "etype": ent.entity_type, "eid": ent.entity_id, "role": ent.role}
            )

    # 2) Neo4j: upsert incident node
    _neo4j_merge_incident(incident_id, payload.summary, payload.severity, "investigating")

    # 3) Neo4j: link entities
    for ent in payload.entities:
        props = _affects_rel_props(ent.role)
        _neo4j_link_incident_entity(incident_id, ent.entity_type, ent.entity_id, props["role"])

    # 4) Kafka: event
    await _emit({
        "type": "incident.created",
        "incident_id": incident_id,
        "summary": payload.summary,
        "severity": payload.severity,
        "status": "investigating",
        "source": payload.source,
        "entities": [e.model_dump() for e in payload.entities]
    })

    return {
        "incident_id": incident_id,
        "status": "investigating",
        "summary": payload.summary,
        "severity": payload.severity,
        "entities": [e.model_dump() for e in payload.entities],
    }


@router.patch("/{incident_id}", summary="Update incident status")
async def update_incident(incident_id: str, payload: IncidentUpdate):
    """
    1) Update status/resolution in Postgres
    2) Mirror to Neo4j
    3) Emit 'incident.updated' to Kafka
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE incidents
                   SET status=:st,
                       resolution_summary = COALESCE(:rs, resolution_summary),
                       updated_at=NOW()
                 WHERE incident_id=:iid
            """),
            {"st": payload.status, "iid": incident_id, "rs": payload.resolution_summary}
        )

    _neo4j_update_incident_status(incident_id, payload.status, payload.resolution_summary)

    await _emit({
        "type": "incident.updated",
        "incident_id": incident_id,
        "status": payload.status,
        "resolution_summary": payload.resolution_summary
    })

    return {"incident_id": incident_id, "status": payload.status, "resolution_summary": payload.resolution_summary}


@router.post("/{incident_id}/entities", summary="Link entities to an incident")
async def link_incident_entities(incident_id: str, entities: List[IncidentEntity]):
    """
    1) Insert links into Postgres (idempotent)
    2) Create/Update relationships in Neo4j: (:Incident)-[:AFFECTS {role}]->(:<Label>)
    3) Emit 'incident.entities_linked' to Kafka
    """
    if not entities:
        return {"incident_id": incident_id, "linked": []}

    with engine.begin() as conn:
        for ent in entities:
            conn.execute(
                text("""
                    INSERT INTO incident_entities (incident_id, entity_type, entity_id, role)
                    VALUES (:iid, :etype, :eid, :role)
                    ON CONFLICT (incident_id, entity_type, entity_id, role) DO NOTHING
                """),
                {"iid": incident_id, "etype": ent.entity_type, "eid": ent.entity_id, "role": ent.role}
            )

    for ent in entities:
        props = _affects_rel_props(ent.role)
        _neo4j_link_incident_entity(incident_id, ent.entity_type, ent.entity_id, props["role"])

    await _emit({
        "type": "incident.entities_linked",
        "incident_id": incident_id,
        "entities": [e.model_dump() for e in entities]
    })

    return {"incident_id": incident_id, "linked": [e.model_dump() for e in entities]}


# --- keep your existing create/update endpoints here ---

@router.get("/search")
def search_incidents(
    status: Optional[str] = Query(None, description="active | open | investigating | mitigated | resolved | closed"),
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    window: Optional[str] = Query(None, description="Postgres interval like '2h' or '15 minutes'"),
    incident_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    """
    Returns incidents filtered by:
    - status:
        * active -> NOT IN ('resolved','closed')
        * open   -> IN ('investigating','mitigating')
        * any other exact status value
      If omitted, returns last N incidents.
    - (entity_type, entity_id): joins incident_entities
    - window: e.g. 2h, 15 minutes, 1 day
    """
    where = []
    params: Dict[str, Any] = {"limit": limit}
    join_ie = ""

    if status:
        st = status.lower()
        if st == "active":
            where.append("i.status NOT IN ('resolved','closed')")
        elif st == "open":
            where.append("i.status IN ('investigating','mitigating')")
        else:
            where.append("i.status = :status")
            params["status"] = st

    if incident_id:
        where.append("i.incident_id = :incident_id")
        params["incident_id"] = incident_id

    if entity_type and entity_id:
        join_ie = "JOIN incident_entities ie ON ie.incident_id = i.incident_id"
        where.append("ie.entity_type = :etype AND ie.entity_id = :eid")
        params.update({"etype": entity_type, "eid": entity_id})

    if window:
        # Let Postgres parse intervals (safe parameterized)
        where.append("i.created_at >= (NOW() - CAST(:window AS INTERVAL))")
        params["window"] = window

    wsql = " AND ".join(where) if where else "TRUE"

    sql = f"""
        SELECT
          i.incident_id,
          i.summary,
          i.severity,
          i.status,
          i.created_at,
          i.updated_at
        FROM incidents i
        {join_ie}
        WHERE {wsql}
        ORDER BY i.created_at DESC
        LIMIT :limit
    """

    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    return {"incidents": [dict(r) for r in rows]}


@router.post("/create_ticket", summary="Create a ticket for an incident")
async def create_ticket(payload: TicketCreate):
    """
    1) Create ticket in Postgres (internal id TIC-xxxxxx). External id is mocked.
    2) Mirror :Ticket in Neo4j and TRACKS -> :Incident.
    3) Emit 'ticket.created' to Kafka.
    """
    ticket_id = _new_ticket_id()
    # For dev/mock: generate a fake external id if system != mock
    external_id = None
    if payload.system != "mock":
        prefix = "JIRA" if payload.system == "jira" else "SNOW"
        external_id = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO tickets (ticket_id, system, external_id, status, incident_id)
                VALUES (:tid, :sys, :ext, 'open', :iid)
            """),
            {"tid": ticket_id, "sys": payload.system, "ext": external_id, "iid": payload.incident_id}
        )

    # Neo4j mirror
    _neo4j_merge_ticket(
        ticket_id=ticket_id,
        system=payload.system,
        status="open",
        incident_id=payload.incident_id,
        title=payload.title,
        assignee_team=payload.assignee_team,
        external_id=external_id
    )

    await _emit({
        "type": "ticket.created",
        "ticket_id": ticket_id,
        "system": payload.system,
        "external_id": external_id,
        "status": "open",
        "incident_id": payload.incident_id,
        "title": payload.title,
        "assignee_team": payload.assignee_team
    })

    return {
        "ticket_id": ticket_id,
        "system": payload.system,
        "external_id": external_id,
        "status": "open",
        "incident_id": payload.incident_id
    }


@router.patch("/update_ticket_status", summary="Update ticket status")
async def update_ticket_status(payload: TicketUpdateStatus):
    """
    1) Update Postgres
    2) Mirror :Ticket status in Neo4j
    3) Emit 'ticket.updated' to Kafka
    """
    with engine.begin() as conn:
        row = conn.execute(
            text("""UPDATE tickets SET status=:st, updated_at=NOW() WHERE ticket_id=:tid RETURNING system, incident_id, external_id"""),
            {"st": payload.status, "tid": payload.ticket_id}
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="ticket not found")

    _neo4j_merge_ticket(
        ticket_id=payload.ticket_id,
        system=row["system"],
        status=payload.status,
        incident_id=row["incident_id"],
        title=None,
        assignee_team=None,
        external_id=row["external_id"]
    )

    await _emit({
        "type": "ticket.updated",
        "ticket_id": payload.ticket_id,
        "status": payload.status
    })

    return {"ticket_id": payload.ticket_id, "status": payload.status}
