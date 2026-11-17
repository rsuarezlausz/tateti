import json
import random

import pytest

from app.agents.agent import Agent
from app.factory.catalog import CATALOG
from app.game.rules import HUMAN, MACHINE, apply_move, empty_board
from app.llm.base import LLMError, LLMResponse, LLMUsage
from app.metrics.collector import MetricsCollector
from app.negotiation.engine import Negotiator
from app.negotiation.events import (
    AgentErrorEvent,
    AgentMessageEvent,
    Consensus,
    Fallback,
    NegotiationStarted,
    RoundStarted,
    Tiebreak,
)

BOARD = apply_move(apply_move(empty_board(6), 14, HUMAN), 15, MACHINE)  # C3 y D3 ocupadas


def reply(move, msg="ok", conf=0.8):
    return json.dumps({"message": msg, "proposed_move": move, "confidence": conf})


class ScriptedLLM:
    """Responde en orden; un Exception se lanza. Repite la última si se agota."""

    def __init__(self, *script, cost=0.001):
        self.script = list(script)
        self.calls = []
        self.cost = cost

    async def complete(self, messages, *, temperature=0.7, json_mode=True):
        self.calls.append(messages)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return LLMResponse(
            item, LLMUsage(10, 5, 15, latency_ms=100.0, cost=self.cost)
        )


def team(*llms):
    return [Agent(CATALOG[i], llm) for i, llm in enumerate(llms)]


async def run(agents, max_rounds=3, seed=0, metrics=None, hints=True):
    neg = Negotiator(
        agents, max_rounds=max_rounds, tactical_hints=hints,
        metrics=metrics, rng=random.Random(seed),
    )
    return [e async for e in neg.run(BOARD, 6, 4)]


def kinds(events):
    return [type(e).__name__ for e in events]


async def test_consensus_in_round_1_event_order():
    events = await run(team(ScriptedLLM(reply(0)), ScriptedLLM(reply(0)), ScriptedLLM(reply(0))))
    assert kinds(events) == [
        "NegotiationStarted", "RoundStarted", "AgentMessageEvent", "AgentMessageEvent",
        "AgentMessageEvent", "Consensus",
    ]
    assert events[0] == NegotiationStarted(3, ("estratega", "defensivo", "agresivo"))
    assert events[-1] == Consensus(0, 1)


async def test_agents_speak_in_catalog_order():
    events = await run(team(ScriptedLLM(reply(0)), ScriptedLLM(reply(0))))
    spoken = [e.message.agent_id for e in events if isinstance(e, AgentMessageEvent)]
    assert spoken == ["estratega", "defensivo"]


async def test_single_agent_consensus_round_1():
    events = await run(team(ScriptedLLM(reply(5))))
    assert events[-1] == Consensus(5, 1)


async def test_consensus_in_round_2_and_transcript_visible():
    a = ScriptedLLM(reply(0), reply(1))
    b = ScriptedLLM(reply(1))
    events = await run(team(a, b))
    assert events[-1] == Consensus(1, 2)
    assert RoundStarted(2) in events
    # En ronda 2 el prompt de A incluye lo dicho en ronda 1 (A y B)
    round2_user = a.calls[1][1]["content"]
    assert "Debate hasta ahora" in round2_user and "Considera las propuestas" in round2_user
    assert "Estratega (ronda 1)" in round2_user and "Defensivo (ronda 1)" in round2_user
    assert len(b.calls) == 2


async def test_no_consensus_draws_only_among_most_voted():
    agents = team(
        ScriptedLLM(reply(0)), ScriptedLLM(reply(1)), ScriptedLLM(reply(0)), ScriptedLLM(reply(2))
    )
    events = await run(agents)
    decision = events[-1]
    assert isinstance(decision, Tiebreak)
    assert decision.candidates == (0,) and decision.move == 0 and not decision.drawn
    assert decision.votes == {0: 2, 1: 1, 2: 1}


@pytest.mark.parametrize("seed", range(10))
async def test_tie_draw_picks_among_top_candidates(seed):
    agents = team(
        ScriptedLLM(reply(0)), ScriptedLLM(reply(1)), ScriptedLLM(reply(0)), ScriptedLLM(reply(1))
    )
    decision = (await run(agents, seed=seed))[-1]
    assert isinstance(decision, Tiebreak) and decision.drawn
    assert decision.candidates == (0, 1) and decision.move in (0, 1)


async def test_tie_draw_is_reproducible_with_seed():
    def build():
        return team(ScriptedLLM(reply(0)), ScriptedLLM(reply(1)))

    assert (await run(build(), seed=7))[-1] == (await run(build(), seed=7))[-1]


async def test_stops_after_max_rounds():
    a, b = ScriptedLLM(reply(0)), ScriptedLLM(reply(1))
    events = await run(team(a, b), max_rounds=2)
    assert len(a.calls) == 2 and len(b.calls) == 2
    assert kinds(events).count("RoundStarted") == 2


async def test_illegal_move_retries_once_with_free_cells():
    a = ScriptedLLM(reply(14), reply(20))  # 14 = C3, ocupada
    events = await run(team(a), max_rounds=1)
    assert events[-1] == Consensus(20, 1)
    assert len(a.calls) == 2
    correction = a.calls[1][-1]["content"]
    assert "C3" in correction and "no está libre" in correction
    assert "B1=1" in correction and "C3=14" not in correction


async def test_out_of_range_move_is_illegal():
    a = ScriptedLLM(reply(99), reply(20))
    assert (await run(team(a), max_rounds=1))[-1] == Consensus(20, 1)


async def test_invalid_json_twice_emits_error_and_no_vote():
    bad = ScriptedLLM("no es json")
    good = ScriptedLLM(reply(3))
    events = await run(team(bad, good), max_rounds=1)
    errors = [e for e in events if isinstance(e, AgentErrorEvent)]
    assert len(errors) == 1 and errors[0].agent_id == "estratega" and errors[0].round_number == 1
    assert len(bad.calls) == 2  # un único reintento
    decision = events[-1]
    assert isinstance(decision, Tiebreak) and decision.move == 3 and decision.votes == {3: 1}


async def test_no_consensus_if_an_agent_fails_even_if_others_agree():
    events = await run(team(ScriptedLLM("x"), ScriptedLLM(reply(3)), ScriptedLLM(reply(3))), 2)
    assert not any(isinstance(e, Consensus) for e in events)
    assert isinstance(events[-1], Tiebreak)


async def test_invalid_json_then_valid_retry_counts():
    a = ScriptedLLM("basura", reply(4))
    events = await run(team(a), max_rounds=1)
    assert events[-1] == Consensus(4, 1)
    assert not any(isinstance(e, AgentErrorEvent) for e in events)


async def test_all_invalid_falls_back_to_random_free_cell():
    agents = team(ScriptedLLM("x"), ScriptedLLM(reply(14)))  # JSON inválido / siempre ilegal
    events = await run(agents, max_rounds=2, seed=3)
    decision = events[-1]
    assert isinstance(decision, Fallback)
    assert decision.move not in (14, 15) and 0 <= decision.move < 36
    assert "azar" in decision.reason
    assert sum(isinstance(e, AgentErrorEvent) for e in events) == 4  # 2 agentes x 2 rondas


async def test_last_valid_vote_is_kept_if_agent_fails_later():
    a = ScriptedLLM(reply(2), "x")  # ronda 1 válida, luego inválida
    b = ScriptedLLM(reply(3))
    decision = (await run(team(a, b), max_rounds=2))[-1]
    assert isinstance(decision, Tiebreak) and decision.votes == {2: 1, 3: 1}


async def test_provider_error_is_handled_like_invalid_response():
    a = ScriptedLLM(LLMError("boom"), reply(5))
    assert (await run(team(a), max_rounds=1))[-1] == Consensus(5, 1)
    b = ScriptedLLM(LLMError("boom"))
    events = await run(team(b), max_rounds=1)
    assert isinstance(events[-2], AgentErrorEvent) and isinstance(events[-1], Fallback)


async def test_metrics_record_every_call_including_failed():
    metrics = MetricsCollector()
    a = ScriptedLLM(reply(14), reply(20))
    b = ScriptedLLM(reply(20))
    await run(team(a, b), max_rounds=1, metrics=metrics)
    s = metrics.summary()
    by_id = {m.agent_id: m for m in s.agents}
    assert by_id["estratega"].calls == 2 and by_id["estratega"].failed_calls == 1
    assert by_id["defensivo"].calls == 1 and by_id["defensivo"].failed_calls == 0
    assert s.total.calls == 3 and s.total.total_tokens == 45
    assert s.total.avg_latency_ms == 100.0 and s.total.total_latency_ms == 300.0
    assert s.total.total_cost == pytest.approx(0.003)
    assert {r.round_number for r in metrics.records} == {1}


async def test_metrics_cost_none_when_provider_reports_none():
    metrics = MetricsCollector()
    await run(team(ScriptedLLM(reply(0), cost=None)), max_rounds=1, metrics=metrics)
    assert metrics.summary().total.total_cost is None
    assert MetricsCollector().summary().total.calls == 0


async def test_hints_flag_is_forwarded():
    a = ScriptedLLM(reply(0))
    await run(team(a), max_rounds=1, hints=False)
    assert "Ayudas tácticas" not in a.calls[0][1]["content"]


def test_negotiator_validates_args():
    with pytest.raises(ValueError):
        Negotiator([], max_rounds=3)
    with pytest.raises(ValueError):
        Negotiator(team(ScriptedLLM(reply(0))), max_rounds=0)


async def test_full_board_cannot_be_negotiated():
    board = tuple("X" for _ in range(36))
    neg = Negotiator(team(ScriptedLLM(reply(0))), max_rounds=1)
    with pytest.raises(ValueError):
        [e async for e in neg.run(board, 6, 4)]


async def test_end_to_end_with_mock_client_reaches_consensus():
    from app.factory.factory import AgentFactory
    from app.llm.mock import MockLLMClient

    agents = AgentFactory(MockLLMClient()).create_team(4)
    events = await run(agents)
    assert isinstance(events[-1], Consensus) and events[-1].round_number == 2
    assert events[-1].move not in (14, 15)
