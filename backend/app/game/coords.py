"""Conversión entre índice de celda y coordenada humana (A1, C3...)."""

import re
import string

MAX_BOARD_SIZE = len(string.ascii_uppercase)

_COORD_RE = re.compile(r"^([A-Za-z])(\d{1,2})$")


def column_labels(board_size: int) -> list[str]:
    return list(string.ascii_uppercase[:board_size])


def index_to_coord(index: int, board_size: int) -> str:
    """Índice `fila * board_size + columna` -> coordenada (columna letra, fila 1-based)."""
    if not 0 <= index < board_size * board_size:
        raise ValueError(f"Índice fuera de rango: {index}")
    row, col = divmod(index, board_size)
    return f"{string.ascii_uppercase[col]}{row + 1}"


def coord_to_index(coord: str, board_size: int) -> int:
    match = _COORD_RE.match(coord.strip())
    if not match:
        raise ValueError(f"Coordenada inválida: {coord!r}")
    col = string.ascii_uppercase.index(match.group(1).upper())
    row = int(match.group(2)) - 1
    if not (0 <= col < board_size and 0 <= row < board_size):
        raise ValueError(f"Coordenada fuera del tablero: {coord!r}")
    return row * board_size + col
