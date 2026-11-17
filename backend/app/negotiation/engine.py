"""Negociación por rondas. La jugada sale del debate de los agentes, nunca de una búsqueda."""

import random
from collections import Counter
from collections.abc import AsyncIterator, Sequence

from app.agents.agent import Agent
from app.agents.models import (
    AgentMessage,
    AgentResponseError,
    NegotiationContext,
    TranscriptEntry,
)
from app.game.coords import index_to_coord
from app.game.lookahead import analyze, assess_move, render_assessment, render_lookahead
from app.game.render import render_free_cells
from app.game.rules import Board, legal_moves
from app.llm.base import LLMError
from app.metrics.collector import MetricsCollector
from app.negotiation.events import (
    AgentErrorEvent,
    AgentMessageEvent,
    Consensus,
    Fallback,
    NegotiationEvent,
    NegotiationStarted,
    RoundStarted,
    Tiebreak,
)

MAX_ATTEMPTS = 2  # intento inicial + 1 reintento con corrección


class Negotiator:
    def __init__(
        self,
        agents: Sequence[Agent],
        *,
        max_rounds: int,
        tactical_hints: bool = True,
        lookahead_plies: int = 0,
        metrics: MetricsCollector | None = None,
        rng: random.Random | None = None,
    ) -> None:
        if not agents:
            raise ValueError("Se necesita al menos un agente")
        if max_rounds < 1:
            raise ValueError("max_rounds debe ser >= 1")
        self._agents = tuple(agents)
        self._max_rounds = max_rounds
        self._hints = tactical_hints
        self._lookahead = lookahead_plies
        self.metrics = metrics if metrics is not None else MetricsCollector()
        self._rng = rng or random.Random()

    async def run(
        self, board: Board, board_size: int, win_length: int
    ) -> AsyncIterator[NegotiationEvent]:
        """Emite eventos en orden; el último es siempre una decisión
        (Consensus, Tiebreak o Fallback)."""
        free = legal_moves(board)
        if not free:
            raise ValueError("No hay celdas libres para negociar")

        yield NegotiationStarted(self._max_rounds, tuple(a.spec.id for a in self._agents))
        # El análisis depende solo del tablero: se calcula una vez por negociación.
        lookahead_report = None
        if self._hints and self._lookahead > 0:
            lookahead_report = render_lookahead(
                analyze(board, board_size, win_length, self._lookahead), board_size
            )
        transcript: list[TranscriptEntry] = []
        final_votes: dict[str, int] = {}  # última propuesta válida de cada agente

        for round_number in range(1, self._max_rounds + 1):
            yield RoundStarted(round_number)
            round_votes: dict[str, int] = {}
            for agent in self._agents:
                ctx = NegotiationContext(
                    board=board,
                    board_size=board_size,
                    win_length=win_length,
                    round_number=round_number,
                    max_rounds=self._max_rounds,
                    transcript=tuple(transcript),
                    tactical_hints=self._hints,
                    lookahead_report=lookahead_report,
                )
                message, reason = await self._ask(agent, ctx, free)
                if message is None:
                    yield AgentErrorEvent(round_number, agent.spec.id, reason)
                    continue
                round_votes[agent.spec.id] = final_votes[agent.spec.id] = message.proposed_move
                assessment = None
                if self._hints and self._lookahead >= 2:  # permite al resto objetar o apoyar
                    assessment = render_assessment(
                        assess_move(board, board_size, win_length, self._lookahead, message.proposed_move),
                        board_size,
                    )
                transcript.append(
                    TranscriptEntry(
                        agent.spec.id,
                        agent.spec.name,
                        round_number,
                        message.message,
                        message.proposed_move,
                        assessment,
                    )
                )
                yield AgentMessageEvent(round_number, message)

            moves = set(round_votes.values())
            if len(round_votes) == len(self._agents) and len(moves) == 1:
                yield Consensus(moves.pop(), round_number)
                return

        yield self._resolve_without_consensus(final_votes, free)

    def _resolve_without_consensus(
        self, final_votes: dict[str, int], free: list[int]
    ) -> Tiebreak | Fallback:
        if not final_votes:
            return Fallback(
                self._rng.choice(free),
                "Ningún agente aportó un voto válido; se eligió una celda libre al azar.",
            )
        votes = Counter(final_votes.values())
        top = max(votes.values())
        candidates = tuple(sorted(m for m, v in votes.items() if v == top))
        return Tiebreak(self._rng.choice(candidates), candidates, dict(votes))

    async def _ask(
        self, agent: Agent, ctx: NegotiationContext, free: list[int]
    ) -> tuple[AgentMessage | None, str]:
        free_set = set(free)
        correction: str | None = None
        reason = ""
        for _ in range(MAX_ATTEMPTS):
            try:
                message = await agent.speak(ctx, correction)
            except AgentResponseError as exc:
                self.metrics.record(agent.spec.id, ctx.round_number, exc.usage, ok=False)
                reason = exc.reason
            except LLMError:
                reason = "Error al contactar al proveedor LLM"
            else:
                ok = message.proposed_move in free_set
                self.metrics.record(agent.spec.id, ctx.round_number, message.usage, ok=ok)
                if ok:
                    return message, ""
                reason = f"La celda propuesta ({_describe(message.proposed_move, ctx)}) no está libre"
            correction = (
                f"Tu respuesta anterior no es válida: {reason}. Responde solo con el JSON "
                "indicado y propone una de estas celdas libres (coordenada=índice): "
                f"{render_free_cells(ctx.board, ctx.board_size)}"
            )
        return None, f"{reason} (tras reintentar)"


def _describe(move: int, ctx: NegotiationContext) -> str:
    try:
        return index_to_coord(move, ctx.board_size)
    except ValueError:
        return f"índice {move}"
