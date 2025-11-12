from fastapi import APIRouter
from strawberry.fastapi import GraphQLRouter
import strawberry
from typing import List, Optional

@strawberry.type
class Incident:
    incident_id: str
    summary: str
    severity: str
    status: str

@strawberry.type
class Event:
    kind: str
    ts: str
    message: str

@strawberry.type
class BlastRadius:
    impacted: List[str]

@strawberry.type
class Query:
    @strawberry.field
    def entity(self, id: str, type: str) -> str:
        return f"{type}:{id}"

    @strawberry.field
    def incidents(self, entityId: str, entityType: str) -> List[Incident]:
        return []

    @strawberry.field
    def recentEvents(self, entityId: str, entityType: str, window: Optional[str] = "15m") -> List[Event]:
        return []

    @strawberry.field
    def blastRadius(self, entityId: str, entityType: str, depth: Optional[int] = 2) -> BlastRadius:
        return BlastRadius(impacted=[])

schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)

router = APIRouter()
router.include_router(graphql_app, prefix="/graphql")
