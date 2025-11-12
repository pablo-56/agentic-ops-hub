# backend/app/graph.py
"""
Graph utilities for Neo4j:
- Safe, cached driver creation
- Cypher runner
- JSON-safe serializers (coerce neo4j.time.* to native/ISO)
- Whitelists for labels / relationship types to prevent injection
"""

from typing import Any, Dict, Iterable, List, Optional
from neo4j import GraphDatabase, Driver
from neo4j.graph import Node, Relationship
from neo4j.time import DateTime, Date, Time, Duration  # <-- for coercion
from .config import settings

# --- Neo4j driver (lazy singleton) -------------------------------------------

_driver: Optional[Driver] = None

def get_driver() -> Driver:
    """ Lazily create and cache a single Driver for reuse. """
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
        )
    return _driver

def run_cypher(query: str, params: Dict[str, Any]) -> List[Any]:
    """
    Run a Cypher query with parameters using a short-lived session.
    NOTE: use 'parameters=' (v5 API) so named params are bound correctly.
    """
    drv = get_driver()
    with drv.session() as session:
        return list(session.run(query, parameters=(params or {})))

# --- Safety: whitelist labels & relationship types ---------------------------

ALLOWED_LABELS = {
    "Site", "Plant", "Line", "Machine", "Sensor",
    "Service", "Database", "Team", "Incident", "Alert", "Ticket",
    "Runbook", "AgentAction", "API", "Topic", "Server", "NetworkDevice",
    "User", "AlertType"
}

REL_ALL = {
    "HAS_LINE", "HAS_MACHINE", "HAS_SENSOR",
    "DEPENDS_ON", "OWNED_BY", "AFFECTS", "ABOUT", "CORRELATED_WITH",
    "TRACKS", "EXECUTED_BY", "RELATES_TO", "TARGETS", "BASED_ON",
    "APPROVED_BY", "APPLIES_TO", "ATTACHED_TO",
    "RUNS_ON", "USES_DB", "CALLS_API", "PUBLISHES_TO", "CONSUMES_FROM"
}

# Dependency-style relationships we walk for deps/dependents/blast-radius
REL_DEP = {"DEPENDS_ON", "USES_DB", "CALLS_API", "RUNS_ON", "PUBLISHES_TO", "CONSUMES_FROM"}

# Child topology rels (plant->line->machine->sensor). Kept for future use.
REL_CHILD = {"HAS_LINE", "HAS_MACHINE", "HAS_SENSOR"}

# Property used as business key on nodes
NODE_ID_PROP = "id"

def sanitize_label(label: str) -> str:
    """ Enforce allowlist for labels to avoid Cypher injection. """
    canonical = (label or "").strip()
    canonical = canonical[:1].upper() + canonical[1:]
    if canonical not in ALLOWED_LABELS:
        raise ValueError(f"Label '{label}' not allowed")
    return canonical

# --- JSON-safe coercion helpers ----------------------------------------------

def _coerce_neo4j_value(v: Any) -> Any:
    """
    Recursively coerce neo4j types to JSON-safe values:
    - neo4j.time.DateTime/Date/Time -> Python datetime/date/time (or ISO string)
    - neo4j.time.Duration -> str
    - lists/dicts -> recurse
    - other scalars left as-is
    """
    # time types
    if isinstance(v, (DateTime, Date, Time)):
        # Prefer Python native to keep FastAPI happy; fall back to ISO if needed
        try:
            return v.to_native()
        except Exception:
            return v.iso_format()
    if isinstance(v, Duration):
        return str(v)

    # container types
    if isinstance(v, dict):
        return {k: _coerce_neo4j_value(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_coerce_neo4j_value(x) for x in v]

    # basic scalars
    return v

def node_to_dict(n: Node) -> Dict[str, Any]:
    """ Serialize a Neo4j Node to a JSON-safe dict. """
    raw_props = dict(n)
    return {
        "labels": list(n.labels),
        "props": _coerce_neo4j_value(raw_props),
    }

def rel_to_dict(r: Relationship) -> Dict[str, Any]:
    """ Serialize a Neo4j Relationship to a JSON-safe dict. """
    raw_props = dict(r)
    return {
        "type": r.type,
        "props": _coerce_neo4j_value(raw_props),
        "start": r.start_node.id,
        "end": r.end_node.id,
    }

def uniq_nodes(nodes: Iterable[Node]) -> List[Dict[str, Any]]:
    """
    De-duplicate by (labels, props) after coercion so sets are JSON-stable.
    """
    seen = set()
    out: List[Dict[str, Any]] = []
    for n in nodes:
        nd = node_to_dict(n)
        key = (tuple(sorted(nd["labels"])), tuple(sorted(nd["props"].items())))
        if key in seen:
            continue
        seen.add(key)
        out.append(nd)
    return out

def uniq_rels(rels: Iterable[Relationship]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for r in rels:
        rd = rel_to_dict(r)
        key = (rd["type"], rd["start"], rd["end"], tuple(sorted(rd["props"].items())))
        if key in seen:
            continue
        seen.add(key)
        out.append(rd)
    return out
