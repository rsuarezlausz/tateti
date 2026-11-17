import json
import random
import time

import pytest

from app.agents.agent import Agent
from app.config import Settings
from app.factory.catalog import CATALOG
from app.game.lookahead import analyze, render_lookahead
from app.game.rules import HUMAN, MACHINE, apply_move, empty_board
from app.llm.base import LLMResponse, LLMUsage
from app.negotiation.engine import Negotiator


def board_from(size, placements):
    board = empty_board(size)
    for idx, p in placements.items():
        board = apply_move(board, idx, p)
    return board


# Índices 6x6: fila * 6 + columna. A1=0 ... F1=5, A3=12, B3=13, C3=14, D3=15, E3=16, F3=17
PAIR = {14: HUMAN, 15: HUMAN, 30: MACHINE}  # X en C3 y D3 (consecutivas, extremos libres)


def test_two_consecutive_open_x_are_a_forced_win_at_4_plies():
    r = analyze(board_from(6, PAIR), 6, 4, 4)
    assert r.human_threats and r.human_threats[0].plies == 3
    assert {13, 16} <= {t.first_move for t in r.human_threats}  # B3 o E3 forman tres abiertas


def test_safe_moves_prevent_the_fork_and_far_cells_do_not():
    r = analyze(board_from(6, PAIR), 6, 4, 4)
    assert r.safe_moves is not None
    assert 13 in r.safe_moves and 16 in r.safe_moves  # tapar un extremo evita la doble amenaza
    assert 5 not in r.safe_moves  # una celda lejana no previene nada
    assert not r.lost


def test_playing_a_safe_move_removes_the_threat():
    board = board_from(6, PAIR)
    after = apply_move(board, 13, MACHINE)  # O en B3
    assert analyze(after, 6, 4, 4).human_threats == ()


def test_horizon_of_two_plies_does_not_see_the_fork():
    r = analyze(board_from(6, PAIR), 6, 4, 2)
    assert r.human_threats == () and r.safe_moves is None


def test_no_threat_with_isolated_stone():
    r = analyze(board_from(6, {14: HUMAN, 15: MACHINE}), 6, 4, 4)
    assert r.human_threats == () and r.safe_moves is None


def test_immediate_threat_only_block_is_safe():
    board = board_from(6, {0: HUMAN, 1: HUMAN, 2: HUMAN, 35: MACHINE})  # X A1 B1 C1 -> gana en D1
    r = analyze(board, 6, 4, 4)
    assert r.human_threats[0].plies == 1 and r.safe_moves == (3,)


def test_two_immediate_threats_is_lost():
    board = board_from(6, {1: HUMAN, 2: HUMAN, 3: HUMAN, 35: MACHINE})  # B1 C1 D1: A1 y E1
    r = analyze(board, 6, 4, 4)
    assert r.lost and r.safe_moves == ()
    assert "Ninguna jugada evita la derrota" in render_lookahead(r, 6)


def test_machine_immediate_win_is_reported_and_counts_as_safe():
    board = board_from(6, {1: MACHINE, 2: MACHINE, 3: MACHINE, 14: HUMAN, 15: HUMAN, 20: HUMAN})
    r = analyze(board, 6, 4, 4)
    assert r.machine_win and r.machine_win.plies == 1 and r.machine_win.first_move in (0, 4)
    assert r.machine_win.first_move in (r.safe_moves or (r.machine_win.first_move,))


def test_machine_fork_detected_with_three_plies():
    board = board_from(6, {14: MACHINE, 15: MACHINE, 35: HUMAN})
    r = analyze(board, 6, 4, 3)
    assert r.machine_win and r.machine_win.plies == 3 and r.machine_win.first_move in (13, 16)
    assert analyze(board, 6, 4, 2).machine_win is None


def test_chain_of_single_threats_needs_deeper_horizon():
    # X fuerza con una amenaza simple (D3), la máquina bloquea y luego X tiene doble amenaza.
    board = board_from(
        6, {13: HUMAN, 14: HUMAN, 15: HUMAN, 12: MACHINE, 25: HUMAN, 26: HUMAN, 35: MACHINE}
    )
    shallow = analyze(board, 6, 4, 4)
    assert shallow.human_threats and shallow.human_threats[0].plies == 1  # amenaza inmediata en E3


def test_report_text_lists_threats_and_safe_moves_in_coordinates():
    text = render_lookahead(analyze(board_from(6, PAIR), 6, 4, 4), 6)
    assert "Análisis táctico a 4 jugadas" in text and "AMENAZA" in text
    assert "B3" in text and "E3" in text and "previenen" in text
    assert "Celdas libres" not in text  # el mock lee esa línea del prompt


def test_report_without_threat():
    text = render_lookahead(analyze(board_from(6, {14: HUMAN}), 6, 4, 4), 6)
    assert "Sin amenazas forzadas" in text


def test_works_on_other_board_sizes():
    board = board_from(3, {0: HUMAN, 1: HUMAN})
    r = analyze(board, 3, 3, 4)
    assert r.human_threats[0].first_move == 2 and r.human_threats[0].plies == 1
    # bloquear en C1 no basta en 3x3: X forma doble amenaza con el centro (análisis correcto)
    assert r.lost


def test_performance_on_crowded_board_at_max_horizon():
    board = board_from(
        6, {14: HUMAN, 15: HUMAN, 20: MACHINE, 21: HUMAN, 8: MACHINE, 9: HUMAN, 27: MACHINE, 28: HUMAN}
    )
    t0 = time.perf_counter()
    analyze(board, 6, 4, 6)
    assert time.perf_counter() - t0 < 5


# ---- configuración ----
def test_settings_default_and_env():
    assert Settings.from_env({}).tactical_lookahead_plies == 4
    assert Settings.from_env({"TACTICAL_LOOKAHEAD_PLIES": "0"}).tactical_lookahead_plies == 0
    assert Settings.from_env({"TACTICAL_LOOKAHEAD_PLIES": "6"}).tactical_lookahead_plies == 6


@pytest.mark.parametrize("value", ["-1", "7", "99"])
def test_settings_invalid_lookahead(value):
    with pytest.raises(ValueError):
        Settings.from_env({"TACTICAL_LOOKAHEAD_PLIES": value})


# ---- integración con la negociación ----
class CapturingLLM:
    def __init__(self):
        self.prompts = []

    async def complete(self, messages, *, temperature=0.7, json_mode=True):
        self.prompts.append(messages[1]["content"])
        content = json.dumps({"message": "ok", "proposed_move": 13, "confidence": 0.5})
        return LLMResponse(content, LLMUsage(1, 1, 2, 1.0, None))


async def run_negotiation(**kwargs):
    llm = CapturingLLM()
    neg = Negotiator([Agent(CATALOG[0], llm)], max_rounds=1, rng=random.Random(0), **kwargs)
    [e async for e in neg.run(board_from(6, PAIR), 6, 4)]
    return llm.prompts


async def test_prompt_includes_lookahead_report():
    prompts = await run_negotiation(tactical_hints=True, lookahead_plies=4)
    assert "Análisis táctico a 4 jugadas" in prompts[0] and "AMENAZA" in prompts[0]


@pytest.mark.parametrize("kwargs", [{"tactical_hints": True, "lookahead_plies": 0},
                                    {"tactical_hints": False, "lookahead_plies": 4}])
async def test_prompt_omits_lookahead_when_disabled(kwargs):
    assert "Análisis táctico" not in (await run_negotiation(**kwargs))[0]


async def test_report_is_computed_once_and_shared_by_all_rounds_and_agents():
    llm = CapturingLLM()
    agents = [Agent(CATALOG[0], llm), Agent(CATALOG[1], llm)]
    neg = Negotiator(agents, max_rounds=2, lookahead_plies=4, rng=random.Random(0))
    [e async for e in neg.run(board_from(6, PAIR), 6, 4)]
    assert len(llm.prompts) >= 2 and all("Análisis táctico a 4 jugadas" in p for p in llm.prompts)
