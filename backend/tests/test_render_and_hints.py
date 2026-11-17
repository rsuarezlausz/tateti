from app.game.hints import blocking_moves, open_threats, render_hints, winning_moves
from app.game.render import render_board, render_for_llm, render_free_cells
from app.game.rules import HUMAN, MACHINE, apply_move, empty_board


def board_from(size, placements):
    board = empty_board(size)
    for idx, p in placements.items():
        board = apply_move(board, idx, p)
    return board


def test_render_board_format():
    board = board_from(6, {14: HUMAN, 0: MACHINE})
    lines = render_board(board, 6).splitlines()
    assert lines[0] == "   A B C D E F"
    assert lines[1] == " 1 O . . . . ."
    assert lines[3] == " 3 . . X . . ."
    assert len(lines) == 7


def test_free_cells_include_coord_and_index():
    board = board_from(6, {0: HUMAN})
    free = render_free_cells(board, 6)
    assert "C3=14" in free
    assert "A1" not in free
    assert free.startswith("B1=1")


def test_render_for_llm_contains_both():
    text = render_for_llm(empty_board(6), 6)
    assert "A B C D E F" in text and "F6=35" in text


def test_render_uses_board_size():
    text = render_board(empty_board(3), 3)
    assert text.splitlines()[0] == "   A B C"


def test_immediate_win_detected():
    board = board_from(6, {0: MACHINE, 1: MACHINE, 2: MACHINE})
    assert winning_moves(board, 6, 4, MACHINE) == [3]


def test_immediate_win_gap_in_middle():
    board = board_from(6, {0: MACHINE, 1: MACHINE, 3: MACHINE})
    assert winning_moves(board, 6, 4, MACHINE) == [2]


def test_blocking_move_vs_human():
    board = board_from(6, {7: HUMAN, 8: HUMAN, 9: HUMAN, 10: MACHINE})
    assert blocking_moves(board, 6, 4, MACHINE) == [6]


def test_no_win_when_blocked_both_ends():
    board = board_from(6, {0: MACHINE, 1: MACHINE, 2: MACHINE, 3: HUMAN})
    assert winning_moves(board, 6, 4, MACHINE) == []


def test_open_threat_with_both_ends_free():
    board = board_from(6, {7: HUMAN, 8: HUMAN, 9: HUMAN})
    threats = open_threats(board, 6, 4)
    assert len(threats) == 1
    t = threats[0]
    assert t.player == HUMAN and t.cells == (7, 8, 9) and set(t.ends) == {6, 10}


def test_no_open_threat_when_end_blocked():
    board = board_from(6, {7: HUMAN, 8: HUMAN, 9: HUMAN, 6: MACHINE})
    assert open_threats(board, 6, 4) == []


def test_no_open_threat_at_board_edge():
    board = board_from(6, {0: HUMAN, 1: HUMAN, 2: HUMAN})
    assert open_threats(board, 6, 4) == []


def test_open_threat_diagonal():
    board = board_from(6, {7: MACHINE, 14: MACHINE, 21: MACHINE})
    t = open_threats(board, 6, 4)
    assert len(t) == 1 and set(t[0].ends) == {0, 28}


def test_render_hints_text():
    board = board_from(6, {0: MACHINE, 1: MACHINE, 2: MACHINE, 12: HUMAN})
    text = render_hints(board, 6, 4)
    assert "D1" in text and "informativas" in text
