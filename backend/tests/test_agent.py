import pytest

from app.agents.agent import Agent, extract_json_object
from app.agents.models import AgentResponseError, NegotiationContext, TranscriptEntry
from app.agents.prompts import build_system_prompt, build_user_prompt
from app.factory.catalog import CATALOG
from app.game.rules import HUMAN, MACHINE, apply_move, empty_board
from app.llm.base import LLMResponse, LLMUsage
from app.llm.mock import MockLLMClient


class StubLLM:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def complete(self, messages, *, temperature=0.7, json_mode=True):
        self.calls.append((messages, temperature, json_mode))
        return LLMResponse(self.content, LLMUsage(total_tokens=7, cost=None))


def ctx(**kw):
    board = apply_move(empty_board(6), 14, HUMAN)
    base = dict(board=board, board_size=6, win_length=4, round_number=1, max_rounds=3)
    return NegotiationContext(**(base | kw))


def test_extract_json_tolerant():
    assert extract_json_object('texto ```json\n{"a": 1}\n``` fin') == {"a": 1}
    assert extract_json_object("sin json") is None
    assert extract_json_object('{roto {"b": 2}') == {"b": 2}


async def test_speak_parses_valid_reply():
    llm = StubLLM('{"message": "Tomo C3", "proposed_move": 14, "confidence": 0.9}')
    msg = await Agent(CATALOG[0], llm).speak(ctx())
    assert (msg.agent_id, msg.proposed_move, msg.confidence) == ("estratega", 14, 0.9)
    assert msg.usage.total_tokens == 7 and msg.usage.cost is None


async def test_speak_uses_spec_temperature_and_json_mode():
    llm = StubLLM('{"message": "x", "proposed_move": 1, "confidence": 0.5}')
    await Agent(CATALOG[3], llm).speak(ctx())
    _, temperature, json_mode = llm.calls[0]
    assert temperature == CATALOG[3].temperature and json_mode is True


async def test_speak_clamps_confidence_and_truncates_message():
    llm = StubLLM('{"message": "' + "a" * 500 + '", "proposed_move": 1, "confidence": 4}')
    msg = await Agent(CATALOG[0], llm).speak(ctx())
    assert msg.confidence == 1.0 and len(msg.message) == 280


@pytest.mark.parametrize(
    "content",
    ["no es json", '{"message": "x"}', '{"message": "", "proposed_move": 1, "confidence": 1}',
     '{"message": "x", "proposed_move": "abc", "confidence": 1}'],
)
async def test_speak_raises_on_invalid_with_usage(content):
    with pytest.raises(AgentResponseError) as exc:
        await Agent(CATALOG[0], StubLLM(content)).speak(ctx())
    assert exc.value.usage.total_tokens == 7 and exc.value.raw == content


async def test_correction_is_sent_as_extra_message():
    llm = StubLLM('{"message": "x", "proposed_move": 1, "confidence": 0.5}')
    await Agent(CATALOG[0], llm).speak(ctx(), correction="Corrige: celda ocupada")
    messages = llm.calls[0][0]
    assert messages[-1]["content"] == "Corrige: celda ocupada"


def test_system_prompt_comes_from_spec():
    text = build_system_prompt(CATALOG[1], 4)
    assert CATALOG[1].system_prompt in text and "4 fichas" in text


def test_user_prompt_contents():
    transcript = (TranscriptEntry("defensivo", "Defensivo", 1, "Bloqueo", 15),)
    text = build_user_prompt(ctx(round_number=2, transcript=transcript))
    assert "Ronda 2 de 3" in text and "C3=14" not in text.split("Celdas libres")[0]
    assert "Ayudas tácticas" in text and "Defensivo (ronda 1) propone D3" in text
    assert "Considera las propuestas" in text


def test_user_prompt_without_hints_or_transcript():
    text = build_user_prompt(ctx(tactical_hints=False))
    assert "Ayudas tácticas" not in text and "Debate hasta ahora" not in text
    assert "Considera las propuestas" not in text


async def test_mock_round1_disagrees_round2_converges():
    team = [Agent(s, MockLLMClient()) for s in CATALOG]
    r1 = {(await a.speak(ctx())).proposed_move for a in team}
    r2 = {(await a.speak(ctx(round_number=2))).proposed_move for a in team}
    assert len(r1) > 1 and len(r2) == 1
    assert 14 not in r1 | r2  # solo propone celdas libres


async def test_mock_is_deterministic_and_reports_usage():
    a = Agent(CATALOG[0], MockLLMClient())
    m1, m2 = await a.speak(ctx()), await a.speak(ctx())
    assert m1 == m2
    assert m1.usage.total_tokens > 0 and m1.usage.latency_ms > 0 and m1.usage.cost is not None


async def test_mock_proposes_only_free_cells_late_game():
    board = empty_board(3)
    for i in range(8):
        board = apply_move(board, i, HUMAN if i % 2 == 0 else MACHINE)
    c = NegotiationContext(board=board, board_size=3, win_length=3, round_number=2, max_rounds=3)
    msg = await Agent(CATALOG[0], MockLLMClient()).speak(c)
    assert msg.proposed_move == 8
