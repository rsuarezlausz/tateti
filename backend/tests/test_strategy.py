import json
import random

import pytest

from app.agents.agent import Agent
from app.agents.prompts import build_system_prompt
from app.factory.catalog import CATALOG
from app.game.hints import positional_values, render_hints
from app.game.lookahead import assess_move, render_assessment
from app.game.rules import HUMAN, MACHINE, apply_move, empty_board
from app.llm.base import LLMResponse, LLMUsage
from app.negotiation.engine import Negotiator


def board_from(size, placements):
    board = empty_board(size)
    for idx, p in placements.items():
        board = apply_move(board, idx, p)
    return board


PAIR = {14: HUMAN, 15: HUMAN, 30: MACHINE}  # X en C3 y D3 con extremos libres


# ---- evaluación de una propuesta ----
def test_far_move_is_unsafe_against_open_pair():
    a = assess_move(board_from(6, PAIR), 6, 4, 4, 5)  # F1: no previene nada
    assert not a.wins and a.human_win and a.human_win.plies == 3
    text = render_assessment(a, 6)
    assert text.startswith("INSEGURA") and "3 jugadas" in text


def test_blocking_an_end_is_safe():
    a = assess_move(board_from(6, PAIR), 6, 4, 4, 13)  # B3
    assert a.human_win is None
    assert render_assessment(a, 6).startswith("segura")


def test_winning_move_is_reported():
    board = board_from(6, {1: MACHINE, 2: MACHINE, 3: MACHINE, 14: HUMAN, 15: HUMAN, 20: HUMAN})
    a = assess_move(board, 6, 4, 4, 0)
    assert a.wins and render_assessment(a, 6) == "esta jugada gana la partida"


def test_own_threat_is_reported():
    board = board_from(6, {1: MACHINE, 2: MACHINE, 35: HUMAN})
    a = assess_move(board, 6, 4, 4, 3)  # O: B1 C1 D1 -> amenaza A1 y E1
    assert len(a.own_threats) == 2 and "doble amenaza propia" in render_assessment(a, 6)


# ---- valor posicional (estrategia por perfil) ----
def test_positional_values_favor_center_on_empty_board():
    v = positional_values(empty_board(6), 6, 4)
    assert v[14][0] > v[0][0] and v[14][1] > v[0][1]  # C3 vale más que la esquina A1
    assert all(i in v for i in range(36))


def test_defensive_value_grows_near_human_stones():
    board = board_from(6, {14: HUMAN, 15: HUMAN})
    v = positional_values(board, 6, 4)
    assert v[13][1] > v[35][1] and v[16][1] > v[35][1]  # B3/E3 cortan líneas del humano


def test_occupied_cells_have_no_value():
    v = positional_values(board_from(6, {14: HUMAN}), 6, 4)
    assert 14 not in v


def test_hints_text_lists_offensive_and_defensive_cells_without_free_cells_phrase():
    text = render_hints(board_from(6, PAIR), 6, 4)
    assert "mayor potencial ofensivo" in text and "mayor valor defensivo" in text
    assert not any(line.startswith("Celdas libres") for line in text.splitlines())


# ---- prompts: prioridades y perfiles ----
def test_system_prompt_has_common_priorities_for_every_profile():
    for spec in CATALOG:
        text = build_system_prompt(spec, 4)
        assert "Prioridades comunes" in text and "INSEGURA" in text
        assert "Si puedes ganar ya" in text and "bloquéala" in text


def test_profiles_are_distinct_data():
    prompts = [s.system_prompt for s in CATALOG]
    assert len(set(prompts)) == 4
    joined = {s.id: s.system_prompt.lower() for s in CATALOG}
    assert "defensivo" in joined["defensivo"] and "ofensivo" in joined["agresivo"]
    assert "centro" in joined["estratega"] and "menos obvia" in joined["caotico"]
    # todos respetan las prioridades urgentes antes que su estilo
    assert "seguras" in joined["caotico"] and "seguras" in joined["agresivo"]


# ---- el debate incluye la evaluación de cada propuesta ----
class ScriptedLLM:
    def __init__(self, move):
        self.move, self.prompts = move, []

    async def complete(self, messages, *, temperature=0.7, json_mode=True):
        self.prompts.append(messages[1]["content"])
        content = json.dumps({"message": f"voy a {self.move}", "proposed_move": self.move, "confidence": 0.6})
        return LLMResponse(content, LLMUsage(1, 1, 2, 1.0, None))


async def negotiate(moves, *, plies=4, hints=True, rounds=2):
    llms = [ScriptedLLM(m) for m in moves]
    agents = [Agent(CATALOG[i], llm) for i, llm in enumerate(llms)]
    neg = Negotiator(agents, max_rounds=rounds, tactical_hints=hints, lookahead_plies=plies,
                     rng=random.Random(0))
    [e async for e in neg.run(board_from(6, PAIR), 6, 4)]
    return llms


async def test_next_speaker_sees_unsafe_assessment_of_previous_proposal():
    first, second = await negotiate([5, 13])  # Estratega propone F1 (insegura), Defensivo ve eso
    seen_by_second = second.prompts[0]
    assert "Estratega (ronda 1) propone F1" in seen_by_second
    assert "evaluación del sistema: INSEGURA" in seen_by_second
    # en la ronda 2 el primero ve la evaluación de ambas propuestas
    round2 = first.prompts[1]
    assert "INSEGURA" in round2 and "segura: no deja victorias forzadas" in round2


async def test_first_speaker_has_no_assessments_yet():
    first, _ = await negotiate([13, 13], rounds=1)
    assert "evaluación del sistema" not in first.prompts[0]


@pytest.mark.parametrize("kwargs", [{"hints": False, "plies": 4}, {"hints": True, "plies": 0},
                                    {"hints": True, "plies": 1}])
async def test_no_assessment_without_hints_or_enough_horizon(kwargs):
    _, second = await negotiate([5, 13], **kwargs)
    assert "evaluación del sistema" not in second.prompts[0]
