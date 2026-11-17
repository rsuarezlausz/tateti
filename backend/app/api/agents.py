from fastapi import APIRouter

from app.agents.spec import AgentSpec
from app.factory.catalog import CATALOG

router = APIRouter(prefix="/api")


@router.get("/agents")
def list_agents() -> list[AgentSpec]:
    return list(CATALOG)
