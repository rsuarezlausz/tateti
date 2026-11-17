from collections.abc import Sequence

from app.agents.agent import Agent
from app.agents.spec import AgentSpec
from app.factory.catalog import CATALOG
from app.llm.base import LLMClient

MIN_TEAM = 1


class InvalidTeamSizeError(ValueError):
    pass


class AgentFactory:
    """Crea agentes en runtime desde AgentSpec; todos comparten el LLMClient inyectado."""

    def __init__(self, llm: LLMClient, catalog: Sequence[AgentSpec] = CATALOG) -> None:
        self._llm = llm
        self._catalog = tuple(catalog)

    @property
    def catalog(self) -> tuple[AgentSpec, ...]:
        return self._catalog

    def create_team(self, n: int) -> list[Agent]:
        max_team = len(self._catalog)
        if isinstance(n, bool) or not isinstance(n, int) or not MIN_TEAM <= n <= max_team:
            raise InvalidTeamSizeError(
                f"El equipo debe tener entre {MIN_TEAM} y {max_team} agentes (recibido: {n!r})"
            )
        return [Agent(spec, self._llm) for spec in self._catalog[:n]]
