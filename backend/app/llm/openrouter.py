"""Cliente OpenRouter (API compatible con OpenAI chat/completions) sobre httpx."""

import time

import httpx

from app.llm.base import LLMError, LLMResponse, LLMUsage, Message


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        *,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY es obligatoria cuando LLM_MOCK=false")
        if not model:
            raise ValueError("OPENROUTER_MODEL es obligatorio cuando LLM_MOCK=false")
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(
        self, messages: list[Message], *, temperature: float = 0.7, json_mode: bool = True
    ) -> LLMResponse:
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "usage": {"include": True},
            # El debate ya es el "razonamiento": con modelos que piensan (p. ej. deepseek-v4-flash)
            # una sola llamada tardaba ~150 s y ~10k tokens. Se desactiva el thinking.
            "reasoning": {"enabled": False},
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        try:
            response = await self._client.post("/chat/completions", json=payload)
            if json_mode and response.status_code == 400:
                # El modelo no soporta response_format: reintentar sin él.
                payload.pop("response_format")
                response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"OpenRouter respondió HTTP {exc.response.status_code}") from None
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"Fallo al llamar a OpenRouter: {type(exc).__name__}") from None
        latency_ms = (time.perf_counter() - started) * 1000
        return self._parse(data, latency_ms)

    @staticmethod
    def _parse(data: dict, latency_ms: float) -> LLMResponse:
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("Respuesta de OpenRouter sin contenido") from None
        usage = data.get("usage") or {}
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        cost = usage.get("cost")
        return LLMResponse(
            content=content,
            usage=LLMUsage(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=int(usage.get("total_tokens") or prompt + completion),
                latency_ms=latency_ms,
                cost=float(cost) if cost is not None else None,
            ),
        )
