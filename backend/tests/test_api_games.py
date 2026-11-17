import json
import random
import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.game.rules import HUMAN, apply_move
from app.llm.base import LLMResponse, LLMUsage
from app.llm.mock import MockLLMClient
from app.main import create_app


class FixedLLM:
    """Todos los agentes proponen la misma celda libre (por defecto la última libre)."""

    def __init__(self, cell=None, raw=None):
        self.cell, self.raw, self.calls = cell, raw, 0

    async def complete(self, messages, *, temperature=0.7, json_mode=True):
        self.calls += 1
        if isinstance(self.raw, Exception):
            raise self.raw
        if self.raw is not None:
            return LLMResponse(self.raw, LLMUsage(1, 1, 2, 5.0, None))
        user = "\n".join(m["content"] for m in messages if m["role"] == "user")
        line = [ln for ln in user.splitlines() if ln.startswith("Celdas libres")][-1]
        free = [int(x) for x in re.findall(r"=(\d+)", line)]
        cell = self.cell if self.cell in free else free[-1]
        content = json.dumps({"message": f"Voy por {cell}", "proposed_move": cell, "confidence": 0.9})
        return LLMResponse(content, LLMUsage(10, 5, 15, 20.0, 0.001))


def make_client(llm=None, **settings):
    app = create_app(Settings(llm_mock=True, **settings), llm=llm or MockLLMClient(),
                     rng=random.Random(0))
    return TestClient(app)


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def create(client, n=3):
    r = client.post("/api/games", json={"num_agents": n})
    assert r.status_code == 201
    return r.json()


def move(client, gid, cell):
    return client.post(f"/api/games/{gid}/move", json={"cell": cell})


def names(events, skip=("metrics_update",)):
    return [n for n, _ in events if n not in skip]


def test_create_game_returns_state():
    g = create(make_client(), 3)
    assert (g["board_size"], g["win_length"]) == (6, 4)
    assert g["board"] == [None] * 36 and g["status"] == "in_progress" and g["turn"] == "human"
    assert [a["id"] for a in g["agents"]] == ["estratega", "defensivo", "agresivo"]
    assert g["game_id"]


def test_board_size_comes_from_config():
    g = create(make_client(board_size=4, win_length=3))
    assert len(g["board"]) == 16 and g["board_size"] == 4 and g["win_length"] == 3


@pytest.mark.parametrize("n", [0, 5, -1])
def test_create_game_rejects_invalid_team_size(n):
    assert make_client().post("/api/games", json={"num_agents": n}).status_code == 422


def test_create_game_requires_num_agents():
    assert make_client().post("/api/games", json={}).status_code == 422


def test_create_game_503_when_llm_not_configured():
    client = TestClient(create_app(Settings()))
    assert client.post("/api/games", json={"num_agents": 1}).status_code == 503
    assert client.get("/api/health").status_code == 200


def test_get_game_and_404():
    client = make_client()
    g = create(client)
    assert client.get(f"/api/games/{g['game_id']}").json() == g
    assert client.get("/api/games/nope").status_code == 404
    assert client.get("/api/games/nope/metrics").status_code == 404
    assert move(client, "nope", 0).status_code == 404


def test_move_streams_events_in_order():
    client = make_client(FixedLLM(cell=0))
    g = create(client, 3)
    r = move(client, g["game_id"], 14)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert names(events) == [
        "human_move", "negotiation_started", "round_started",
        "agent_message", "agent_message", "agent_message",
        "consensus", "machine_move",
    ]
    assert events[0][1]["coord"] == "C3" and events[0][1]["board"][14] == "X"
    by_name = dict(events)
    assert by_name["negotiation_started"] == {
        "max_rounds": 3, "agents": ["estratega", "defensivo", "agresivo"]}
    assert by_name["consensus"] == {"move": 0, "coord": "A1", "round": 1}
    assert by_name["machine_move"]["board"][0] == "O"
    msg = next(d for n, d in events if n == "agent_message")
    assert msg["agent_id"] == "estratega" and msg["coord"] == "A1"
    assert msg["usage"]["total_tokens"] == 15 and msg["usage"]["cost"] == 0.001


def test_metrics_update_emitted_during_negotiation_and_after_move():
    client = make_client(FixedLLM(cell=0))
    g = create(client, 3)
    events = parse_sse(move(client, g["game_id"], 14).text)
    order = [n for n, _ in events]
    assert order.count("metrics_update") == 4  # 3 mensajes + tras machine_move
    assert order[-1] == "metrics_update"
    assert order.index("machine_move") < len(order) - 1
    updates = [d for n, d in events if n == "metrics_update"]
    assert [u["total"]["calls"] for u in updates] == [1, 2, 3, 3]


def test_state_after_move_and_turn_back_to_human():
    client = make_client(FixedLLM(cell=0))
    g = create(client)
    move(client, g["game_id"], 14)
    s = client.get(f"/api/games/{g['game_id']}").json()
    assert s["board"][14] == "X" and s["board"][0] == "O" and s["turn"] == "human"
    assert s["last_moves"] == {"human": 14, "machine": 0}


def test_metrics_endpoint_aggregates():
    client = make_client(FixedLLM(cell=0))
    g = create(client, 2)
    empty = client.get(f"/api/games/{g['game_id']}/metrics").json()
    assert empty["total"]["calls"] == 0 and empty["agents"] == []
    move(client, g["game_id"], 14)
    m = client.get(f"/api/games/{g['game_id']}/metrics").json()
    assert m["total"]["calls"] == 2 and m["total"]["total_tokens"] == 30
    assert {a["agent_id"] for a in m["agents"]} == {"estratega", "defensivo"}
    assert m["total"]["total_cost"] == pytest.approx(0.002)


def test_occupied_cell_409_out_of_range_422():
    client = make_client(FixedLLM(cell=0))
    g = create(client)
    gid = g["game_id"]
    move(client, gid, 14)
    assert move(client, gid, 14).status_code == 409
    assert move(client, gid, 0).status_code == 409  # ocupada por la máquina
    assert move(client, gid, 36).status_code == 422
    assert move(client, gid, -1).status_code == 422


def test_wrong_turn_409():
    client = make_client()
    g = create(client)
    session = client.app.state.store.get(g["game_id"])
    session.board = apply_move(session.board, 14, HUMAN)  # humano ya movió; turno de la máquina
    r = move(client, g["game_id"], 20)
    assert r.status_code == 409 and "turno" in r.json()["detail"]


def test_human_win_emits_game_over_and_blocks_further_moves():
    client = make_client(FixedLLM(), board_size=3, win_length=3)  # la máquina juega la última libre
    g = create(client, 1)
    gid = g["game_id"]
    move(client, gid, 0)  # máquina: 8
    move(client, gid, 1)  # máquina: 7
    events = parse_sse(move(client, gid, 2).text)
    assert names(events) == ["human_move", "game_over"]
    assert events[-1][1] == {"status": "human_won", "winner": "X", "line": [0, 1, 2], "draw": False}
    s = client.get(f"/api/games/{gid}").json()
    assert s["status"] == "human_won" and s["turn"] is None and s["winning_line"] == [0, 1, 2]
    assert move(client, gid, 3).status_code == 409


def test_machine_win_emits_game_over_after_machine_move():
    client = make_client(FixedLLM(), board_size=3, win_length=3)
    g = create(client, 1)
    gid = g["game_id"]
    move(client, gid, 0)  # máquina 8
    move(client, gid, 1)  # máquina 7
    # humano juega 3 (no gana) y la máquina completa 6-7-8
    events = parse_sse(move(client, gid, 3).text)
    assert names(events)[-2:] == ["machine_move", "game_over"]
    assert events[-1][1]["status"] == "machine_won" and events[-1][1]["line"] == [6, 7, 8]


def test_full_game_with_mock_runs_to_the_end():
    client = make_client(board_size=3, win_length=3)
    g = create(client, 4)
    gid = g["game_id"]
    last = None
    for _ in range(9):
        s = client.get(f"/api/games/{gid}").json()
        if s["status"] != "in_progress":
            break
        cell = next(i for i, c in enumerate(s["board"]) if c is None)
        last = parse_sse(move(client, gid, cell).text)
    assert client.get(f"/api/games/{gid}").json()["status"] != "in_progress"
    assert last[-1][0] == "game_over"


def test_garbage_llm_emits_agent_error_and_fallback_then_machine_moves():
    client = make_client(FixedLLM(raw="no json"))
    g = create(client, 2)
    events = parse_sse(move(client, g["game_id"], 14).text)
    ns = names(events)
    assert ns.count("agent_error") == 6  # 2 agentes x 3 rondas
    assert ns[-2:] == ["fallback", "machine_move"]
    fb = dict(events)["fallback"]
    assert fb["move"] != 14 and "azar" in fb["reason"]
    assert [d for n, d in events if n == "metrics_update"][-1]["total"]["failed_calls"] == 12


def test_unexpected_error_reverts_human_move():
    client = make_client(FixedLLM(raw=RuntimeError("secreto-sk-123")))
    g = create(client)
    r = move(client, g["game_id"], 14)
    events = parse_sse(r.text)
    assert events[-1][0] == "error" and "secreto" not in r.text
    s = client.get(f"/api/games/{g['game_id']}").json()
    assert s["board"] == [None] * 36 and s["turn"] == "human" and s["last_moves"]["human"] is None
    assert move(client, g["game_id"], 14).status_code == 200  # se puede reintentar


def test_cors_header_for_allowed_origin():
    client = make_client()
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
