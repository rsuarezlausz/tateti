"""Contrato del cliente LLM. Agentes y negociación solo dependen de esto."""

from dataclasses import dataclass
from typing import Protocol


class LLMError(RuntimeError):
    """Fallo al llamar al proveedor (red, HTTP, respuesta malformada)."""


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost: float | None = None  # None = el proveedor no lo informó; nunca inventarlo


@dataclass(frozen=True)
class LLMResponse:
    content: str
    usage: LLMUsage


Message = dict[str, str]  # {"role": "system"|"user"|"assistant", "content": str}


class LLMClient(Protocol):
    async def complete(
        self, messages: list[Message], *, temperature: float = 0.7, json_mode: bool = True
    ) -> LLMResponse: ...
