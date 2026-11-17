import json
import random
import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.game.rules import HUMAN, MACHINE, apply_move, empty_board, next_player
from app.llm.base import LLMResponse, LLMUsage
from app.llm.mock import MockLLMClient
from app.main import create_app


class FirstFreeLLM:
    """Todos proponen la primera celda libre; opcionalmente falla las primeras `fail` llamadas."""

    def __init__(self, fail=0):
        self.fail, self.calls = fail, 0

    async def complete(self, messages, *, temperature=0.7, json_mode=True):
        self.calls += 1
        if self.calls <= self.fail:
            raise RuntimeError("boom")
        user = "\n".join(m["content"] for m in messages if m["role"] == "user")
        line = [ln for ln in user.splitlines() if ln.startswith("Celdas libres")][-1]
        cell = int(re.findall(r"=(\d+)", line)[0])
        content = json.dumps({"message": "ok", "proposed_move": cell, "confidence": 0.9})
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


def create(client, starting=None, n=2):
    body = {"num_agents": n} | ({"starting_player": starting} if starting else {})
    r = client.post("/api/games", json=body)
    assert r.status_code == 201
    return r.json()


def start(client, gid):
    return client.post(f"/api/games/{gid}/start")


def move(client, gid, cell):
    return client.post(f"/api/games/{gid}/move", json={"cell": cell})


def state(client, gid):
    return client.get(f"/api/games/{gid}").json()


def count(board, who):
    return sum(1 for c in board if c == who)


# ---- reglas puras ----
def test_next_player_with_machine_first():
    board = empty_board(6)
    assert next_player(board, MACHINE) == MACHINE
    board = apply_move(board, 0, MACHINE)
    assert next_player(board, MACHINE) == HUMAN
    board = apply_move(board, 1, HUMAN)
    assert next_player(board, MACHINE) == MACHINE


def test_next_player_defaults_to_human_first():
    assert next_player(empty_board(6)) == HUMAN


# ---- creación ----
def test_default_starting_player_is_human():
    g = create(make_client())
    assert g["starting_player"] == "human" and g["turn"] == "human"


def test_create_with_machine_first():
    g = create(make_client(), "machine")
    assert g["starting_player"] == "machine" and g["turn"] == "machine"
    assert g["board"] == [None] * 36 and g["status"] == "in_progress"


def test_invalid_starting_player_is_rejected():
    r = make_client().post("/api/games", json={"num_agents": 1, "starting_player": "nadie"})
    assert r.status_code == 422


# ---- apertura de la máquina ----
def test_human_cannot_move_before_machine_opens():
    client = make_client(FirstFreeLLM())
    g = create(client, "machine")
    r = move(client, g["game_id"], 14)
    assert r.status_code == 409 and "turno" in r.json()["detail"]


def test_start_streams_negotiation_and_places_machine_piece():
    client = make_client(FirstFreeLLM())
    g = create(client, "machine", n=3)
    r = start(client, g["game_id"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    names = [n for n, _ in events if n != "metrics_update"]
    assert names == ["negotiation_started", "round_started", "agent_message", "agent_message",
                     "agent_message", "consensus", "machine_move"]
    assert "human_move" not in names
    assert [n for n, _ in events][-1] == "metrics_update"
    s = state(client, g["game_id"])
    assert count(s["board"], "O") == 1 and count(s["board"], "X") == 0
    assert s["turn"] == "human" and s["last_moves"] == {"human": None, "machine": 0}


def test_turns_alternate_after_machine_opening():
    client = make_client(FirstFreeLLM())
    gid = create(client, "machine")["game_id"]
    start(client, gid)
    move(client, gid, 20)  # humano; la máquina responde
    s = state(client, gid)
    assert count(s["board"], "O") == 2 and count(s["board"], "X") == 1 and s["turn"] == "human"


def test_start_is_only_allowed_once():
    client = make_client(FirstFreeLLM())
    gid = create(client, "machine")["game_id"]
    assert start(client, gid).status_code == 200
    r = start(client, gid)
    assert r.status_code == 409 and "ya hizo" in r.json()["detail"]


def test_start_rejected_when_human_starts():
    client = make_client(FirstFreeLLM())
    gid = create(client, "human")["game_id"]
    r = start(client, gid)
    assert r.status_code == 409 and "humano" in r.json()["detail"]


def test_start_unknown_game_404():
    assert start(make_client(), "nope").status_code == 404


def test_concurrent_start_is_rejected():
    client = make_client(FirstFreeLLM())
    gid = create(client, "machine")["game_id"]
    client.app.state.store.get(gid).negotiating = True  # otra apertura en curso
    assert start(client, gid).status_code == 409


def test_failed_opening_leaves_board_empty_and_can_be_retried():
    llm = FirstFreeLLM(fail=1)  # la primera llamada revienta con un error inesperado
    client = make_client(llm)
    gid = create(client, "machine", n=1)["game_id"]
    r = start(client, gid)
    events = parse_sse(r.text)
    assert events[-1][0] == "error" and "boom" not in r.text
    assert state(client, gid)["board"] == [None] * 36
    assert start(client, gid).status_code == 200  # reintento posible
    assert count(state(client, gid)["board"], "O") == 1


def test_full_game_with_machine_first_runs_to_the_end():
    client = make_client(board_size=3, win_length=3)
    gid = create(client, "machine", n=2)["game_id"]
    start(client, gid)
    for _ in range(9):
        s = state(client, gid)
        if s["status"] != "in_progress":
            break
        cell = next(i for i, c in enumerate(s["board"]) if c is None)
        move(client, gid, cell)
    s = state(client, gid)
    assert s["status"] != "in_progress"
    assert count(s["board"], "O") >= count(s["board"], "X")  # la máquina abrió


def test_machine_first_game_over_on_machine_move_is_reported():
    # 3x3: la máquina juega primero y siempre la primera celda libre; el humano la ayuda a ganar.
    client = make_client(FirstFreeLLM(), board_size=3, win_length=3)
    gid = create(client, "machine", n=1)["game_id"]
    start(client, gid)  # O en 0
    move(client, gid, 8)  # X en 8; O en 1
    ev = parse_sse(move(client, gid, 7).text)  # X en 7; O completa 0-1-2
    assert [n for n, _ in ev if n != "metrics_update"][-2:] == ["machine_move", "game_over"]
    assert ev[-1][1]["status"] == "machine_won"
