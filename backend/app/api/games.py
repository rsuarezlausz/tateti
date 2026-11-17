from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.sse import board_json, map_event, metrics_data, sse
from app.config import Settings
from app.factory.factory import AgentFactory, InvalidTeamSizeError
from app.game.coords import index_to_coord
from app.game.rules import (
    HUMAN,
    MACHINE,
    CellOccupiedError,
    CellOutOfRangeError,
    apply_move,
)
from app.llm.provider import build_llm_client
from app.negotiation.engine import Negotiator
from app.negotiation.events import AgentErrorEvent, AgentMessageEvent, Consensus, Fallback, Tiebreak
from app.sessions import GameSession, GameStore

router = APIRouter(prefix="/api")


class CreateGameRequest(BaseModel):
    num_agents: int
    starting_player: Literal["human", "machine"] = "human"


class MoveRequest(BaseModel):
    cell: int


def _state(session: GameSession) -> dict:
    result = session.result()
    return {
        "game_id": session.id,
        "board_size": session.board_size,
        "win_length": session.win_length,
        "board": board_json(session.board),
        "status": session.status,
        "turn": session.turn,
        "starting_player": session.starting_player,
        "winning_line": list(result.line),
        "last_moves": {"human": session.last_human, "machine": session.last_machine},
        "agents": [a.spec.model_dump() for a in session.agents],
    }


def _session(request: Request, game_id: str) -> GameSession:
    store: GameStore = request.app.state.store
    found = store.get(game_id)
    if found is None:
        raise HTTPException(404, "Partida inexistente")
    return found


def _factory(request: Request) -> AgentFactory:
    state = request.app.state
    if state.llm is None:
        try:
            state.llm = build_llm_client(state.settings)
        except ValueError as exc:
            raise HTTPException(503, f"LLM no configurado: {exc}") from None
    return AgentFactory(state.llm)


@router.post("/games", status_code=201)
async def create_game(body: CreateGameRequest, request: Request) -> dict:
    settings: Settings = request.app.state.settings
    try:
        agents = _factory(request).create_team(body.num_agents)
    except InvalidTeamSizeError as exc:
        raise HTTPException(422, str(exc)) from None
    first = MACHINE if body.starting_player == "machine" else HUMAN
    session = request.app.state.store.create(
        settings.board_size, settings.win_length, agents, first=first
    )
    return _state(session)


@router.get("/games/{game_id}")
async def get_game(game_id: str, request: Request) -> dict:
    return _state(_session(request, game_id))


@router.get("/games/{game_id}/metrics")
async def get_metrics(game_id: str, request: Request) -> dict:
    return metrics_data(_session(request, game_id).metrics.summary())


@router.post("/games/{game_id}/move")
async def move(game_id: str, body: MoveRequest, request: Request) -> StreamingResponse:
    session = _session(request, game_id)
    if session.result().finished:
        raise HTTPException(409, "La partida ya terminó")
    if session.to_move != HUMAN:
        raise HTTPException(409, "No es tu turno: la máquina está negociando")
    try:
        new_board = apply_move(session.board, body.cell, HUMAN)
    except CellOutOfRangeError as exc:
        raise HTTPException(422, str(exc)) from None
    except CellOccupiedError as exc:
        raise HTTPException(409, str(exc)) from None

    # Sin awaits desde la validación hasta aquí: la jugada humana queda aplicada de forma atómica.
    previous = (session.board, session.last_human)
    session.board, session.last_human = new_board, body.cell
    return StreamingResponse(
        _stream(request, session, body.cell, previous),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class _Commit:
    """Marca que la jugada de la máquina ya quedó aplicada (para saber si hay que deshacer)."""

    done = False


async def _machine_turn(
    request: Request, session: GameSession, commit: _Commit
) -> AsyncIterator[str]:
    """Negocia y aplica la jugada de la máquina, emitiendo los eventos SSE."""
    settings: Settings = request.app.state.settings
    size = session.board_size
    negotiator = Negotiator(
        session.agents,
        max_rounds=settings.max_rounds,
        tactical_hints=settings.tactical_hints,
        lookahead_plies=settings.tactical_lookahead_plies,
        metrics=session.metrics,
        rng=request.app.state.rng,
    )
    decision = None
    async for event in negotiator.run(session.board, size, session.win_length):
        name, data = map_event(event, size)
        yield sse(name, data)
        if isinstance(event, AgentMessageEvent | AgentErrorEvent):
            yield sse("metrics_update", metrics_data(session.metrics.summary()))
        if isinstance(event, Consensus | Tiebreak | Fallback):
            decision = event
    session.board = apply_move(session.board, decision.move, MACHINE)
    session.last_machine = decision.move
    commit.done = True
    yield sse(
        "machine_move",
        {"cell": decision.move, "coord": index_to_coord(decision.move, size),
         "board": board_json(session.board)},
    )
    yield sse("metrics_update", metrics_data(session.metrics.summary()))


def _game_over_event(session: GameSession) -> str | None:
    result = session.result()
    if not result.finished:
        return None
    return sse(
        "game_over",
        {"status": session.status, "winner": result.winner,
         "line": list(result.line), "draw": result.draw},
    )


async def _stream(
    request: Request, session: GameSession, human_cell: int, previous: tuple
) -> AsyncIterator[str]:
    size = session.board_size
    commit = _Commit()
    try:
        yield sse(
            "human_move",
            {"cell": human_cell, "coord": index_to_coord(human_cell, size),
             "board": board_json(session.board)},
        )
        if session.result().finished:
            commit.done = True
        else:
            async for chunk in _machine_turn(request, session, commit):
                yield chunk
        over = _game_over_event(session)
        if over:
            yield over
    except Exception:  # noqa: BLE001 - se informa genérico y no se filtran detalles/credenciales
        if not commit.done:
            session.board, session.last_human = previous
        yield sse("error", {"detail": "Error interno durante la negociación; puedes reintentar."})
    finally:
        if not commit.done:  # cliente desconectado o error: se deshace la jugada humana
            session.board, session.last_human = previous


@router.post("/games/{game_id}/start")
async def start(game_id: str, request: Request) -> StreamingResponse:
    """La máquina hace la apertura cuando la partida se creó con `starting_player=machine`."""
    session = _session(request, game_id)
    if session.first != MACHINE:
        raise HTTPException(409, "En esta partida empieza el humano")
    if session.negotiating or session.board.count(HUMAN) + session.board.count(MACHINE) > 0:
        raise HTTPException(409, "La máquina ya hizo su apertura")
    session.negotiating = True  # sin awaits desde la validación: evita aperturas concurrentes
    return StreamingResponse(
        _start_stream(request, session),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _start_stream(request: Request, session: GameSession) -> AsyncIterator[str]:
    commit = _Commit()
    try:
        async for chunk in _machine_turn(request, session, commit):
            yield chunk
        over = _game_over_event(session)
        if over:
            yield over
    except Exception:  # noqa: BLE001
        yield sse("error", {"detail": "Error interno durante la negociación; puedes reintentar."})
    finally:
        session.negotiating = False  # si no se aplicó la apertura, el tablero sigue vacío