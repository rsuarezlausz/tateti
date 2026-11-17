import pytest

from app.game.rules import (
    EMPTY,
    HUMAN,
    MACHINE,
    CellOccupiedError,
    CellOutOfRangeError,
    apply_move,
    check_result,
    empty_board,
    generate_lines,
    legal_moves,
    next_player,
)


def board_from(size, placements):
    board = empty_board(size)
    for idx, p in placements.items():
        board = apply_move(board, idx, p)
    return board


@pytest.mark.parametrize(
    "size,win,expected",
    [(6, 4, 54), (3, 3, 8), (6, 5, 32)],
)
def test_line_count(size, win, expected):
    assert len(generate_lines(size, win)) == expected


def test_lines_are_unique_and_in_range():
    lines = generate_lines(6, 4)
    assert len(set(lines)) == len(lines)
    assert all(0 <= i < 36 for line in lines for i in line)
    assert all(len(line) == 4 for line in lines)


def test_invalid_line_params():
    with pytest.raises(ValueError):
        generate_lines(3, 4)


def test_horizontal_win():
    board = board_from(6, {0: HUMAN, 1: HUMAN, 2: HUMAN, 3: HUMAN})
    r = check_result(board, 6, 4)
    assert r.winner == HUMAN and r.line == (0, 1, 2, 3)


def test_horizontal_does_not_wrap_rows():
    board = board_from(6, {4: HUMAN, 5: HUMAN, 6: HUMAN, 7: HUMAN})
    assert check_result(board, 6, 4).winner is None


def test_vertical_win_at_border():
    board = board_from(6, {5: MACHINE, 11: MACHINE, 17: MACHINE, 23: MACHINE})
    assert check_result(board, 6, 4).winner == MACHINE


def test_diagonal_down_right():
    board = board_from(6, {0: HUMAN, 7: HUMAN, 14: HUMAN, 21: HUMAN})
    assert check_result(board, 6, 4).winner == HUMAN


def test_diagonal_down_left_at_border():
    board = board_from(6, {5: MACHINE, 10: MACHINE, 15: MACHINE, 20: MACHINE})
    assert check_result(board, 6, 4).winner == MACHINE


def test_three_in_row_does_not_win_with_win_length_4():
    board = board_from(6, {0: HUMAN, 1: HUMAN, 2: HUMAN})
    assert not check_result(board, 6, 4).finished


def test_three_in_row_wins_in_3x3():
    board = board_from(3, {0: HUMAN, 1: HUMAN, 2: HUMAN})
    assert check_result(board, 3, 3).winner == HUMAN


def test_five_needed_in_6x6_with_win_5():
    four = board_from(6, {0: HUMAN, 1: HUMAN, 2: HUMAN, 3: HUMAN})
    five = board_from(6, {0: HUMAN, 1: HUMAN, 2: HUMAN, 3: HUMAN, 4: HUMAN})
    assert check_result(four, 6, 5).winner is None
    assert check_result(five, 6, 5).winner == HUMAN


def test_draw_on_full_board_without_winner():
    # 3x3 empate clásico
    layout = "XOX" "XOO" "OXX"
    board = tuple(layout)
    r = check_result(board, 3, 3)
    assert r.draw and r.winner is None and r.finished


def test_occupied_cell():
    board = board_from(6, {0: HUMAN})
    with pytest.raises(CellOccupiedError):
        apply_move(board, 0, MACHINE)


@pytest.mark.parametrize("bad", [-1, 36, 100])
def test_out_of_range(bad):
    with pytest.raises(CellOutOfRangeError):
        apply_move(empty_board(6), bad, HUMAN)


def test_apply_move_does_not_mutate():
    board = empty_board(6)
    new = apply_move(board, 3, HUMAN)
    assert board[3] == EMPTY and new[3] == HUMAN


def test_legal_moves():
    board = board_from(3, {0: HUMAN, 4: MACHINE})
    assert legal_moves(board) == [1, 2, 3, 5, 6, 7, 8]


def test_turn_alternation_human_first():
    board = empty_board(6)
    assert next_player(board) == HUMAN
    board = apply_move(board, 0, HUMAN)
    assert next_player(board) == MACHINE
    board = apply_move(board, 1, MACHINE)
    assert next_player(board) == HUMAN
