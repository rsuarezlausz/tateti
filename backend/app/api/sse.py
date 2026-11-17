"""Mapeo de eventos de negociación a eventos SSE tipados."""

import json

from app.game.coords import index_to_coord
from app.game.rules import EMPTY, Board
from app.metrics.collector import MetricsSummary
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


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def board_json(board: Board) -> list[str | None]:
    return [None if c == EMPTY else c for c in board]


def metrics_data(summary: MetricsSummary) -> dict:
    return summary.model_dump()


def map_event(event: NegotiationEvent, board_size: int) -> tuple[str, dict]:
    def coord(i: int) -> str:
        return index_to_coord(i, board_size)

    match event:
        case NegotiationStarted():
            return "negotiation_started", {
                "max_rounds": event.max_rounds,
                "agents": list(event.agent_ids),
            }
        case RoundStarted():
            return "round_started", {"round": event.round_number}
        case AgentMessageEvent():
            m = event.message
            return "agent_message", {
                "round": event.round_number,
                "agent_id": m.agent_id,
                "message": m.message,
                "proposed_move": m.proposed_move,
                "coord": coord(m.proposed_move),
                "confidence": m.confidence,
                "usage": {
                    "prompt_tokens": m.usage.prompt_tokens,
                    "completion_tokens": m.usage.completion_tokens,
                    "total_tokens": m.usage.total_tokens,
                    "latency_ms": m.usage.latency_ms,
                    "cost": m.usage.cost,
                },
            }
        case AgentErrorEvent():
            return "agent_error", {
                "round": event.round_number,
                "agent_id": event.agent_id,
                "reason": event.reason,
            }
        case Consensus():
            return "consensus", {
                "move": event.move,
                "coord": coord(event.move),
                "round": event.round_number,
            }
        case Tiebreak():
            return "tiebreak", {
                "move": event.move,
                "coord": coord(event.move),
                "candidates": list(event.candidates),
                "candidate_coords": [coord(c) for c in event.candidates],
                "votes": {str(k): v for k, v in event.votes.items()},
                "drawn": event.drawn,
            }
        case Fallback():
            return "fallback", {
                "move": event.move,
                "coord": coord(event.move),
                "reason": event.reason,
            }
    raise TypeError(f"Evento desconocido: {event!r}")
