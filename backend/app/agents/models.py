from dataclasses import dataclass, field

from pydantic import BaseModel, field_validator

from app.agents.spec import AgentSpec  # noqa: F401  (reexport)
from app.game.rules import Board
from app.llm.base import LLMUsage

MAX_MESSAGE_CHARS = 280


class AgentReply(BaseModel):
    """JSON que debe devolver el LLM. `proposed_move` es un índice de celda."""

    message: str
    proposed_move: int
    confidence: float

    @field_validator("message")
    @classmethod
    def _message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message vacío")
        return v if len(v) <= MAX_MESSAGE_CHARS else v[: MAX_MESSAGE_CHARS - 1] + "…"

    @field_validator("confidence")
    @classmethod
    def _confidence(cls, v: float) -> float:
        return min(1.0, max(0.0, v))


class AgentMessage(BaseModel):
    agent_id: str
    message: str
    proposed_move: int
    confidence: float
    usage: LLMUsage

    model_config = {"arbitrary_types_allowed": True}


@dataclass(frozen=True)
class TranscriptEntry:
    agent_id: str
    agent_name: str
    round_number: int
    message: str
    proposed_move: int
    assessment: str | None = None  # evaluación táctica del sistema sobre la propuesta


@dataclass(frozen=True)
class NegotiationContext:
    board: Board
    board_size: int
    win_length: int
    round_number: int
    max_rounds: int
    transcript: tuple[TranscriptEntry, ...] = field(default_factory=tuple)
    tactical_hints: bool = True
    lookahead_report: str | None = None  # análisis táctico a N jugadas, ya renderizado


class AgentResponseError(Exception):
    """La respuesta del LLM no es utilizable (JSON inválido o fuera de esquema).
    Lleva el uso para que las métricas cuenten también las llamadas fallidas."""

    def __init__(self, reason: str, usage: LLMUsage, raw: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.usage = usage
        self.raw = raw
