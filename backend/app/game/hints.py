"""Ayudas tácticas: solo informan a los agentes, nunca eligen la jugada."""

from dataclasses import dataclass

from app.game.coords import index_to_coord
from app.game.rules import EMPTY, HUMAN, MACHINE, Board, generate_lines, opponent


@dataclass(frozen=True)
class OpenThreat:
    """`win_length - 1` fichas consecutivas con ambos extremos libres."""

    player: str
    cells: tuple[int, ...]
    ends: tuple[int, int]


def winning_moves(board: Board, board_size: int, win_length: int, player: str) -> list[int]:
    """Celdas que dan victoria inmediata a `player`."""
    result: set[int] = set()
    for line in generate_lines(board_size, win_length):
        values = [board[i] for i in line]
        if values.count(player) == win_length - 1 and values.count(EMPTY) == 1:
            result.add(line[values.index(EMPTY)])
    return sorted(result)


def blocking_moves(board: Board, board_size: int, win_length: int, me: str = MACHINE) -> list[int]:
    """Celdas que bloquean una victoria inmediata del rival."""
    return winning_moves(board, board_size, win_length, opponent(me))


def open_threats(board: Board, board_size: int, win_length: int) -> list[OpenThreat]:
    run = win_length - 1
    threats: list[OpenThreat] = []
    for row in range(board_size):
        for col in range(board_size):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                before = (row - dr, col - dc)
                after = (row + dr * run, col + dc * run)
                last = (row + dr * (run - 1), col + dc * (run - 1))
                if not all(
                    0 <= r < board_size and 0 <= c < board_size for r, c in (before, after, last)
                ):
                    continue
                cells = tuple((row + dr * k) * board_size + col + dc * k for k in range(run))
                player = board[cells[0]]
                if player == EMPTY or any(board[i] != player for i in cells):
                    continue
                end_a = before[0] * board_size + before[1]
                end_b = after[0] * board_size + after[1]
                if board[end_a] == EMPTY and board[end_b] == EMPTY:
                    threats.append(OpenThreat(player, cells, (end_a, end_b)))
    return threats


def positional_values(
    board: Board, board_size: int, win_length: int
) -> dict[int, tuple[int, int]]:
    """Por celda libre: (valor ofensivo para O, valor defensivo frente a X).

    Ofensivo: suma, sobre las líneas ganadoras que pasan por la celda y no tienen fichas de X,
    de 2**(fichas de O en la línea). Defensivo: lo mismo con los roles invertidos
    (cuántas líneas abiertas del humano corta esa celda y cuán avanzadas están)."""
    values = {i: [0, 0] for i, cell in enumerate(board) if cell == EMPTY}
    for line in generate_lines(board_size, win_length):
        cells = [board[i] for i in line]
        o, x = cells.count(MACHINE), cells.count(HUMAN)
        for i in line:
            if i not in values:
                continue
            if x == 0:
                values[i][0] += 2**o
            if o == 0:
                values[i][1] += 2**x
    return {i: (v[0], v[1]) for i, v in values.items()}


def _top(values: dict[int, tuple[int, int]], which: int, n: int = 5) -> list[int]:
    ranked = sorted(values, key=lambda i: (-values[i][which], i))
    return [i for i in ranked[:n] if values[i][which] > 0]

def _coords(cells: list[int] | tuple[int, ...], board_size: int) -> str:
    return ", ".join(index_to_coord(i, board_size) for i in cells)


def render_hints(board: Board, board_size: int, win_length: int) -> str:
    """Texto de ayudas para el prompt de los agentes."""
    machine_wins = winning_moves(board, board_size, win_length, MACHINE)
    blocks = blocking_moves(board, board_size, win_length, MACHINE)
    lines = ["Ayudas tácticas (informativas; la decisión es de ustedes):"]
    lines.append(
        "- Victoria inmediata para la máquina (O): "
        + (_coords(machine_wins, board_size) if machine_wins else "ninguna")
    )
    lines.append(
        "- Jugadas para bloquear una victoria inmediata del humano (X): "
        + (_coords(blocks, board_size) if blocks else "ninguna")
    )
    threats = open_threats(board, board_size, win_length)
    if threats:
        for t in threats:
            who = "máquina (O)" if t.player == MACHINE else "humano (X)"
            lines.append(
                f"- Amenaza abierta de {who}: {_coords(t.cells, board_size)} "
                f"con extremos libres {_coords(t.ends, board_size)}"
            )
    else:
        lines.append(f"- Amenazas abiertas de {win_length - 1} en línea: ninguna")
    values = positional_values(board, board_size, win_length)
    offense, defense = _top(values, 0), _top(values, 1)
    if offense:
        lines.append(
            "- Celdas de mayor potencial ofensivo (más líneas abiertas propias): "
            + _coords(offense, board_size)
        )
    if defense:
        lines.append(
            "- Celdas de mayor valor defensivo (cortan más líneas abiertas del humano): "
            + _coords(defense, board_size)
        )
    return "\n".join(lines)


__all__ = [
    "HUMAN",
    "OpenThreat",
    "blocking_moves",
    "open_threats",
    "positional_values",
    "render_hints",
    "winning_moves",
]
