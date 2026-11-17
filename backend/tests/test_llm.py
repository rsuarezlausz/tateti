import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.base import LLMError
from app.llm.mock import MockLLMClient
from app.llm.openrouter import OpenRouterClient
from app.llm.provider import build_llm_client
from app.main import create_app

MESSAGES = [{"role": "user", "content": "hola"}]


def client_with(handler):
    return OpenRouterClient("k", "modelo/x", transport=httpx.MockTransport(handler))


def ok_body(**usage):
    return {"choices": [{"message": {"content": "{}"}}], "usage": usage}


async def test_request_shape_and_usage_parsing():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json=ok_body(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.0003)
        )

    r = await client_with(handler).complete(MESSAGES, temperature=0.3)
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    body = seen["body"]
    assert body["model"] == "modelo/x" and body["temperature"] == 0.3
    assert body["usage"] == {"include": True}
    assert body["reasoning"] == {"enabled": False}
    assert body["response_format"] == {"type": "json_object"}
    assert (r.usage.prompt_tokens, r.usage.completion_tokens, r.usage.total_tokens) == (10, 5, 15)
    assert r.usage.cost == 0.0003 and r.usage.latency_ms >= 0


async def test_missing_cost_stays_none():
    r = await client_with(lambda req: httpx.Response(200, json=ok_body(total_tokens=3))).complete(
        MESSAGES
    )
    assert r.usage.cost is None and r.usage.total_tokens == 3


async def test_retries_without_response_format_on_400():
    bodies = []

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        if "response_format" in body:
            return httpx.Response(400, json={"error": "unsupported"})
        return httpx.Response(200, json=ok_body())

    await client_with(handler).complete(MESSAGES)
    assert len(bodies) == 2 and "response_format" not in bodies[1]


async def test_http_error_is_llm_error_without_leaking_key():
    with pytest.raises(LLMError) as exc:
        await client_with(lambda req: httpx.Response(500)).complete(MESSAGES)
    assert "500" in str(exc.value) and "Bearer" not in str(exc.value)


async def test_malformed_body_is_llm_error():
    with pytest.raises(LLMError):
        await client_with(lambda req: httpx.Response(200, json={"choices": []})).complete(MESSAGES)


def test_requires_key_and_model():
    with pytest.raises(ValueError):
        OpenRouterClient("", "m")
    with pytest.raises(ValueError):
        OpenRouterClient("k", "")


def test_provider_selects_client():
    assert isinstance(build_llm_client(Settings(llm_mock=True)), MockLLMClient)
    real = build_llm_client(Settings(openrouter_api_key="k", openrouter_model="m"))
    assert isinstance(real, OpenRouterClient)
    with pytest.raises(ValueError):
        build_llm_client(Settings())


def test_agents_endpoint_returns_catalog():
    data = TestClient(create_app(Settings())).get("/api/agents").json()
    assert [a["id"] for a in data] == ["estratega", "defensivo", "agresivo", "caotico"]
    assert {"system_prompt", "temperature", "color", "avatar", "skills"} <= data[0].keys()
