from dataclasses import dataclass

from app.agents.models import AgentMessage


@dataclass(frozen=True)
class NegotiationStarted:
    max_rounds: int
    agent_ids: tuple[str, ...]


@dataclass(frozen=True)
class RoundStarted:
    round_number: int


@dataclass(frozen=True)
class AgentMessageEvent:
    round_number: int
    message: AgentMessage


@dataclass(frozen=True)
class AgentErrorEvent:
    """Intervención inválida tras el reintento: se avisa y no cuenta como voto."""

    round_number: int
    agent_id: str
    reason: str


@dataclass(frozen=True)
class Consensus:
    move: int
    round_number: int


@dataclass(frozen=True)
class Tiebreak:
    """Sin consenso tras MAX_ROUNDS: se eligió entre las propuestas finales más votadas."""

    move: int
    candidates: tuple[int, ...]  # las más votadas (empate en el máximo)
    votes: dict[int, int]  # celda -> cantidad de votos finales

    @property
    def drawn(self) -> bool:
        """True si hubo sorteo real (más de un candidato)."""
        return len(self.candidates) > 1


@dataclass(frozen=True)
class Fallback:
    """Nadie aportó un voto válido: celda libre al azar."""

    move: int
    reason: str


Decision = Consensus | Tiebreak | Fallback
NegotiationEvent = (
    NegotiationStarted | RoundStarted | AgentMessageEvent | AgentErrorEvent | Decision
)
