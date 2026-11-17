import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_defaults():
    s = Settings.from_env({})
    assert (s.board_size, s.win_length, s.max_rounds) == (6, 4, 3)
    assert s.tactical_hints is True and s.llm_mock is False


def test_env_override():
    s = Settings.from_env({"BOARD_SIZE": "8", "WIN_LENGTH": "5", "LLM_MOCK": "true"})
    assert (s.board_size, s.win_length, s.llm_mock) == (8, 5, True)


@pytest.mark.parametrize(
    "env", [{"WIN_LENGTH": "9"}, {"BOARD_SIZE": "1"}, {"BOARD_SIZE": "27"}, {"MAX_ROUNDS": "0"}]
)
def test_invalid_config(env):
    with pytest.raises(ValueError):
        Settings.from_env(env)


def test_api_key_not_in_repr():
    s = Settings.from_env({"OPENROUTER_API_KEY": "sk-secret"})
    assert "sk-secret" not in repr(s)


def test_health():
    client = TestClient(create_app(Settings()))
    assert client.get("/api/health").json() == {"status": "ok"}
