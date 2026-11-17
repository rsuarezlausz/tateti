"""Estado de partidas en memoria (sin base de datos)."""

import uuid
from dataclasses import dataclass, field

from app.agents.agent import Agent
from app.game.rules import HUMAN, MACHINE, Board, GameResult, check_result, empty_board, next_player
from app.metrics.collector import MetricsCollector


@dataclass
class GameSession:
    id: str
    board_size: int
    win_length: int
    agents: list[Agent]
    board: Board
    metrics: MetricsCollector = field(default_factory=MetricsCollector)
    last_human: int | None = None
    last_machine: int | None = None
    first: str = HUMAN  # quién abre la partida (HUMAN o MACHINE)
    negotiating: bool = False  # la máquina está negociando su apertura (/start)

    def result(self) -> GameResult:
        return check_result(self.board, self.board_size, self.win_length)

    @property
    def status(self) -> str:
        r = self.result()
        if r.winner == HUMAN:
            return "human_won"
        if r.winner == MACHINE:
            return "machine_won"
        return "draw" if r.draw else "in_progress"

    @property
    def to_move(self) -> str:
        return next_player(self.board, self.first)

    @property
    def starting_player(self) -> str:
        return "human" if self.first == HUMAN else "machine"

    @property
    def turn(self) -> str | None:
        if self.result().finished:
            return None
        return "human" if self.to_move == HUMAN else "machine"


class GameStore:
    def __init__(self) -> None:
        self._games: dict[str, GameSession] = {}

    def create(
        self, board_size: int, win_length: int, agents: list[Agent], first: str = HUMAN
    ) -> GameSession:
        session = GameSession(
            id=uuid.uuid4().hex,
            board_size=board_size,
            win_length=win_length,
            agents=agents,
            board=empty_board(board_size),
            first=first,
        )
        self._games[session.id] = session
        return session

    def get(self, game_id: str) -> GameSession | None:
        return self._games.get(game_id)
