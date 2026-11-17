import pytest

from app.game.coords import coord_to_index, index_to_coord


def test_index_14_is_c3():
    assert index_to_coord(14, 6) == "C3"


def test_corners():
    assert index_to_coord(0, 6) == "A1"
    assert index_to_coord(35, 6) == "F6"


def test_roundtrip_all_cells():
    for i in range(36):
        assert coord_to_index(index_to_coord(i, 6), 6) == i


def test_lowercase_accepted():
    assert coord_to_index("c3", 6) == 14


@pytest.mark.parametrize("bad", ["G1", "A7", "A0", "", "11", "AA1", "A"])
def test_invalid_coords(bad):
    with pytest.raises(ValueError):
        coord_to_index(bad, 6)


def test_index_out_of_range():
    with pytest.raises(ValueError):
        index_to_coord(36, 6)
    with pytest.raises(ValueError):
        index_to_coord(-1, 6)


def test_other_board_size():
    assert index_to_coord(8, 3) == "C3"
