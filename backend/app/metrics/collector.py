"""Métricas de las llamadas al LLM, agregadas por agente y por partida."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.llm.base import LLMUsage


@dataclass(frozen=True)
class LLMCallRecord:
    agent_id: str
    round_number: int
    usage: LLMUsage
    ok: bool  # False: respuesta inválida o jugada ilegal (la llamada igual costó)


class UsageTotals(BaseModel):
    calls: int = 0
    failed_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    total_cost: float | None = None  # None = ninguna llamada informó costo


class AgentMetrics(UsageTotals):
    agent_id: str


class MetricsSummary(BaseModel):
    agents: list[AgentMetrics]
    total: UsageTotals


def _aggregate(records: list[LLMCallRecord]) -> dict:
    costs = [r.usage.cost for r in records if r.usage.cost is not None]
    latency = sum(r.usage.latency_ms for r in records)
    return {
        "calls": len(records),
        "failed_calls": sum(1 for r in records if not r.ok),
        "prompt_tokens": sum(r.usage.prompt_tokens for r in records),
        "completion_tokens": sum(r.usage.completion_tokens for r in records),
        "total_tokens": sum(r.usage.total_tokens for r in records),
        "total_latency_ms": round(latency, 3),
        "avg_latency_ms": round(latency / len(records), 3) if records else 0.0,
        "total_cost": round(sum(costs), 10) if costs else None,
    }


class MetricsCollector:
    def __init__(self) -> None:
        self._records: list[LLMCallRecord] = []

    @property
    def records(self) -> tuple[LLMCallRecord, ...]:
        return tuple(self._records)

    def record(self, agent_id: str, round_number: int, usage: LLMUsage, ok: bool = True) -> None:
        self._records.append(LLMCallRecord(agent_id, round_number, usage, ok))

    def summary(self) -> MetricsSummary:
        by_agent: dict[str, list[LLMCallRecord]] = {}
        for r in self._records:
            by_agent.setdefault(r.agent_id, []).append(r)
        return MetricsSummary(
            agents=[AgentMetrics(agent_id=a, **_aggregate(rs)) for a, rs in by_agent.items()],
            total=UsageTotals(**_aggregate(self._records)),
        )
