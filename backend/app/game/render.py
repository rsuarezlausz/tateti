"""Render del tablero como texto para los LLM (formato siempre igual)."""

from app.game.coords import column_labels, index_to_coord
from app.game.rules import EMPTY, Board, legal_moves


def render_board(board: Board, board_size: int) -> str:
    header = "   " + " ".join(column_labels(board_size))
    rows = [header]
    for row in range(board_size):
        cells = board[row * board_size : (row + 1) * board_size]
        rows.append(f"{row + 1:>2} " + " ".join(cells))
    return "\n".join(rows)


def render_free_cells(board: Board, board_size: int) -> str:
    return ", ".join(f"{index_to_coord(i, board_size)}={i}" for i in legal_moves(board))


def render_for_llm(board: Board, board_size: int) -> str:
    return (
        f"Tablero (X = humano, O = máquina, {EMPTY} = vacía):\n"
        f"{render_board(board, board_size)}\n\n"
        f"Celdas libres (coordenada=índice): {render_free_cells(board, board_size)}"
    )
