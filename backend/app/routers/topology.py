# backend/app/routers/topology.py
"""
Topology & Graph Service (Neo4j)
Endpoints:
- GET /graph/entity/{type}/{id}
- GET /graph/dependencies/{type}/{id}
- GET /graph/dependents/{type}/{id}
- GET /graph/blast-radius/{type}/{id}
- GET /graph/search?q=&type=
- GET /graph/topology-summary?scope=

Notes:
- We ALWAYS serialize nodes/relationships via node_to_dict()/rel_to_dict() (from app.graph)
  to coerce neo4j.time.* into JSON-safe values to avoid FastAPI/Pydantic 500s.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional

from ..graph import (
    run_cypher,
    sanitize_label,
    NODE_ID_PROP,
    REL_ALL,
    REL_DEP,
    uniq_nodes,
    uniq_rels,
    node_to_dict,  # <-- JSON-safe node serialization
)

router = APIRouter()
MAX_DEPTH = 4  # upper bound for variable-length patterns


# -----------------------------------------------------------------------------
# 1) Entity context: the node + key neighbors (both directions)
# -----------------------------------------------------------------------------
@router.get("/entity/{entity_type}/{entity_id}")
def get_entity_context(entity_type: str, entity_id: str) -> Dict[str, Any]:
    """
    Read a node and its 1-hop neighbors (incoming & outgoing) using an allowlist of rel types.
    The anchor node and neighbors are converted to JSON-safe dicts.
    """
    try:
        label = sanitize_label(entity_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 1) Anchor node
    q_node = f"""
        MATCH (n:{label} {{{NODE_ID_PROP}: $id}})
        RETURN n
        LIMIT 1
    """
    recs = run_cypher(q_node, {"id": entity_id})
    if not recs:
        raise HTTPException(status_code=404, detail=f"{label} with id '{entity_id}' not found")

    n = recs[0]["n"]  # neo4j.graph.Node

    # 2) Outgoing neighbors via allowed rels
    q_out = f"""
        MATCH (n:{label} {{{NODE_ID_PROP}: $id}})-[r]->(m)
        WHERE type(r) IN $rels
        RETURN r, m
        LIMIT 500
    """
    out_recs = run_cypher(q_out, {"id": entity_id, "rels": list(REL_ALL)})

    # 3) Incoming neighbors via allowed rels
    q_in = f"""
        MATCH (m)-[r]->(n:{label} {{{NODE_ID_PROP}: $id}})
        WHERE type(r) IN $rels
        RETURN r, m
        LIMIT 500
    """
    in_recs = run_cypher(q_in, {"id": entity_id, "rels": list(REL_ALL)})

    # Collect neighbors; uniq_* also JSON-coerces properties
    out_nodes = [r["m"] for r in out_recs]
    out_rels  = [r["r"] for r in out_recs]
    in_nodes  = [r["m"] for r in in_recs]
    in_rels   = [r["r"] for r in in_recs]

    return {
        "entity": {"type": label, "id": entity_id},
        # IMPORTANT: serialize anchor node via node_to_dict() to avoid DateTime serialization 500s
        "node": node_to_dict(n),
        "neighbors": {
            "outgoing": {"nodes": uniq_nodes(out_nodes), "rels": uniq_rels(out_rels)},
            "incoming": {"nodes": uniq_nodes(in_nodes), "rels": uniq_rels(in_rels)},
        },
    }


# -----------------------------------------------------------------------------
# 2) Dependencies: outgoing DEPENDS/USES... walks up to depth
# -----------------------------------------------------------------------------
@router.get("/dependencies/{entity_type}/{entity_id}")
def get_dependencies(
    entity_type: str,
    entity_id: str,
    depth: int = Query(2, ge=1, le=MAX_DEPTH),
) -> Dict[str, Any]:
    """
    Walk outgoing dependency-like relationships up to 'depth':
    DEPENDS_ON, RUNS_ON, USES_DB, CALLS_API, PUBLISHES_TO, CONSUMES_FROM
    """
    try:
        label = sanitize_label(entity_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rel_types = "|".join(sorted(list(REL_DEP)))
    q = f"""
        MATCH p = (n:{label} {{{NODE_ID_PROP}: $id}})
                  -[:{rel_types}*1..{MAX_DEPTH}]->(m)
        WHERE length(p) <= $depth
        RETURN p
        LIMIT 500
    """
    recs = run_cypher(q, {"id": entity_id, "depth": depth})

    nodes, rels = [], []
    for r in recs:
        p = r["p"]  # neo4j.graph.Path
        nodes.extend(p.nodes)
        rels.extend(p.relationships)

    return {
        "entity": {"type": label, "id": entity_id},
        "depth": depth,
        "graph": {"nodes": uniq_nodes(nodes), "rels": uniq_rels(rels)},
    }


# -----------------------------------------------------------------------------
# 3) Dependents: incoming DEPENDS/USES... walks up to depth
# -----------------------------------------------------------------------------
@router.get("/dependents/{entity_type}/{entity_id}")
def get_dependents(
    entity_type: str,
    entity_id: str,
    depth: int = Query(2, ge=1, le=MAX_DEPTH),
) -> Dict[str, Any]:
    """
    Reverse of dependencies: who depends on ME?
    """
    try:
        label = sanitize_label(entity_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rel_types = "|".join(sorted(list(REL_DEP)))
    q = f"""
        MATCH p = (n:{label} {{{NODE_ID_PROP}: $id}})
                  <-[:{rel_types}*1..{MAX_DEPTH}]-(m)
        WHERE length(p) <= $depth
        RETURN p
        LIMIT 500
    """
    recs = run_cypher(q, {"id": entity_id, "depth": depth})

    nodes, rels = [], []
    for r in recs:
        p = r["p"]
        nodes.extend(p.nodes)
        rels.extend(p.relationships)

    return {
        "entity": {"type": label, "id": entity_id},
        "depth": depth,
        "graph": {"nodes": uniq_nodes(nodes), "rels": uniq_rels(rels)},
    }


# -----------------------------------------------------------------------------
# 4) Blast radius: reverse dependency walk + criticality check
# -----------------------------------------------------------------------------
@router.get("/blast-radius/{entity_type}/{entity_id}")
def get_blast_radius(
    entity_type: str,
    entity_id: str,
    max_depth: int = Query(3, ge=1, le=MAX_DEPTH),
) -> Dict[str, Any]:
    """
    Opinionated impact set: reverse dependency walk + criticality check.
    Marks nodes as critical_impacted if any rel on the path has strength='critical'.
    """
    try:
        label = sanitize_label(entity_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rel_types = "|".join(sorted(list(REL_DEP)))
    q = f"""
        MATCH p = (seed:{label} {{{NODE_ID_PROP}: $id}})
                  <-[:{rel_types}*1..{MAX_DEPTH}]-(imp)
        WHERE length(p) <= $max_depth
        WITH seed, p, nodes(p) AS ns, relationships(p) AS rs
        WITH seed, ns[-1] AS impacted, any(r IN rs WHERE coalesce(r.strength, 'normal') = 'critical') AS via_critical
        RETURN impacted, max(CASE WHEN via_critical THEN 1 ELSE 0 END) AS critical
        LIMIT 1000
    """
    recs = run_cypher(q, {"id": entity_id, "max_depth": max_depth})

    def bucket(lbls: List[str]) -> str:
        for t in ["Service", "Machine", "Line", "Plant", "Database", "API", "Server", "Topic"]:
            if t in lbls:
                return t
        return "Other"

    impacted: List[Dict[str, Any]] = []
    for r in recs:
        n = r["impacted"]  # Node
        nd = node_to_dict(n)  # JSON-safe
        impacted.append({**nd, "critical_impacted": bool(r["critical"])})

    # Summarize by "type" bucket
    summary: Dict[str, int] = {}
    for item in impacted:
        b = bucket(item["labels"])
        summary[b] = summary.get(b, 0) + 1

    return {
        "entity": {"type": label, "id": entity_id},
        "max_depth": max_depth,
        "summary": summary,
        "impacted": impacted,
    }


# -----------------------------------------------------------------------------
# 5) Search entities (simple property search; optional type filter)
# -----------------------------------------------------------------------------
@router.get("/search")
def search_entities(q: str = "", type: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    """
    Simple property search by id / name / title (case-insensitive).
    Optional 'type' restricts to a specific label.
    All hits are JSON-safe via node_to_dict().
    """
    labels = [sanitize_label(type)] if type else [
        "Service", "Machine", "Line", "Plant", "Database", "Sensor",
        "API", "Server", "Topic", "Incident", "Alert", "Team"
    ]

    out: List[Dict[str, Any]] = []
    for lbl in labels:
        cq = f"""
            MATCH (n:{lbl})
            WHERE toLower(coalesce(n.{NODE_ID_PROP}, '')) CONTAINS $q
               OR toLower(coalesce(n.name, '')) CONTAINS $q
               OR toLower(coalesce(n.title, '')) CONTAINS $q
            RETURN n
            LIMIT $limit
        """
        recs = run_cypher(cq, {"q": q.lower(), "limit": limit})
        for r in recs:
            out.append(node_to_dict(r["n"]))  # JSON-safe

    # return only up to 'limit' overall to avoid flood
    return {"query": q, "type": type, "results": out[:limit]}


# -----------------------------------------------------------------------------
# 6) Topology summary (global or scoped)
# -----------------------------------------------------------------------------
@router.get("/topology-summary")
def topology_summary(scope: Optional[str] = None) -> Dict[str, Any]:
    """
    No scope: global counts.
    scope="plant:<id>": summarize lines/machines under Plant and incidents affecting them.
    scope="service:<id>": dependency/dependent counts for a Service.
    """
    if not scope:
        q = """
            CALL { MATCH (p:Plant)    RETURN count(p) AS plants }
            CALL { MATCH (s:Service)  RETURN count(s) AS services }
            CALL { MATCH (i:Incident) RETURN count(i) AS incidents }
            RETURN plants, services, incidents
        """
        rec = run_cypher(q, {})[0]
        return {
            "scope": None,
            "summary": {
                "plants": rec["plants"],
                "services": rec["services"],
                "incidents": rec["incidents"],
            }
        }

    try:
        kind, sid = scope.split(":", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="scope must look like 'plant:<id>' or 'service:<id>'")

    if kind.lower() == "plant":
        q = f"""
            MATCH (p:Plant {{ {NODE_ID_PROP}: $id }})
            OPTIONAL MATCH (p)-[:HAS_LINE]->(l:Line)
            OPTIONAL MATCH (l)-[:HAS_MACHINE]->(m:Machine)
            WITH p, collect(DISTINCT l) AS lines, collect(DISTINCT m) AS machines
            OPTIONAL MATCH (i:Incident)-[:AFFECTS]->(x)
            WHERE x IN machines OR x IN lines OR x = p
            RETURN size(lines) AS lines_count, size(machines) AS machines_count, count(DISTINCT i) AS incidents
        """
        recs = run_cypher(q, {"id": sid})
        if not recs:
            raise HTTPException(status_code=404, detail=f"Plant '{sid}' not found")
        r = recs[0]
        return {
            "scope": scope,
            "summary": {
                "lines": r["lines_count"],
                "machines": r["machines_count"],
                "incidents": r["incidents"],
            }
        }

    if kind.lower() == "service":
        rel_types = "|".join(sorted(list(REL_DEP)))
        q_dep = f"""
            MATCH p = (s:Service {{ {NODE_ID_PROP}: $id }})
                      -[:{rel_types}*1..{MAX_DEPTH}]->(x)
            RETURN count(DISTINCT x) AS deps
        """
        q_rev = f"""
            MATCH p = (s:Service {{ {NODE_ID_PROP}: $id }})
                      <-[:{rel_types}*1..{MAX_DEPTH}]-(x)
            RETURN count(DISTINCT x) AS dependents
        """
        r1 = run_cypher(q_dep, {"id": sid})
        r2 = run_cypher(q_rev, {"id": sid})
        deps = r1[0]["deps"] if r1 else 0
        dependents = r2[0]["dependents"] if r2 else 0
        return {"scope": scope, "summary": {"dependencies": deps, "dependents": dependents}}

    raise HTTPException(status_code=400, detail="Unsupported scope kind (use plant:<id> or service:<id>)")
