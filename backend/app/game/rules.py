"""Reglas puras del juego. Única fuente de verdad: sin FastAPI ni LLMs."""

from dataclasses import dataclass
from functools import lru_cache

HUMAN = "X"
MACHINE = "O"
EMPTY = "."

Board = tuple[str, ...]


class InvalidMoveError(ValueError):
    pass


class CellOutOfRangeError(InvalidMoveError):
    pass


class CellOccupiedError(InvalidMoveError):
    pass


@dataclass(frozen=True)
class GameResult:
    winner: str | None
    line: tuple[int, ...] = ()
    draw: bool = False

    @property
    def finished(self) -> bool:
        return self.winner is not None or self.draw


def empty_board(board_size: int) -> Board:
    return (EMPTY,) * (board_size * board_size)


def opponent(player: str) -> str:
    return MACHINE if player == HUMAN else HUMAN


@lru_cache(maxsize=None)
def generate_lines(board_size: int, win_length: int) -> tuple[tuple[int, ...], ...]:
    """Todas las líneas ganadoras (horizontal, vertical y ambas diagonales)."""
    if win_length < 2 or win_length > board_size:
        raise ValueError("win_length debe estar entre 2 y board_size")
    lines: list[tuple[int, ...]] = []
    directions = ((0, 1), (1, 0), (1, 1), (1, -1))
    for row in range(board_size):
        for col in range(board_size):
            for dr, dc in directions:
                end_row = row + dr * (win_length - 1)
                end_col = col + dc * (win_length - 1)
                if not (0 <= end_row < board_size and 0 <= end_col < board_size):
                    continue
                lines.append(
                    tuple((row + dr * k) * board_size + col + dc * k for k in range(win_length))
                )
    return tuple(lines)


def legal_moves(board: Board) -> list[int]:
    return [i for i, cell in enumerate(board) if cell == EMPTY]


def validate_move(board: Board, index: int) -> None:
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(board):
        raise CellOutOfRangeError(f"Celda fuera de rango: {index}")
    if board[index] != EMPTY:
        raise CellOccupiedError(f"Celda ocupada: {index}")


def apply_move(board: Board, index: int, player: str) -> Board:
    """Devuelve un tablero nuevo; no muta el original."""
    validate_move(board, index)
    return board[:index] + (player,) + board[index + 1 :]


def check_result(board: Board, board_size: int, win_length: int) -> GameResult:
    for line in generate_lines(board_size, win_length):
        first = board[line[0]]
        if first != EMPTY and all(board[i] == first for i in line):
            return GameResult(winner=first, line=line)
    if EMPTY not in board:
        return GameResult(winner=None, draw=True)
    return GameResult(winner=None)


def next_player(board: Board, first: str = HUMAN) -> str:
    """Quién mueve, deducido del conteo de fichas. `first` es quien abre la partida
    (las fichas no cambian: humano = X, máquina = O)."""
    humans, machines = board.count(HUMAN), board.count(MACHINE)
    if humans == machines:
        return first
    return HUMAN if humans < machines else MACHINE
