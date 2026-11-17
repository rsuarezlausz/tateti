import json

from pydantic import ValidationError

from app.agents.models import AgentMessage, AgentReply, AgentResponseError, NegotiationContext
from app.agents.prompts import build_system_prompt, build_user_prompt
from app.agents.spec import AgentSpec
from app.llm.base import LLMClient, LLMUsage


def extract_json_object(text: str) -> dict | None:
    """Parseo tolerante: primer objeto JSON dentro del texto (tolera ```json ... ```)."""
    decoder = json.JSONDecoder()
    for pos, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[pos:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


class Agent:
    """Toda la personalidad sale de `spec`; el comportamiento no depende del nombre."""

    def __init__(self, spec: AgentSpec, llm: LLMClient) -> None:
        self.spec = spec
        self._llm = llm

    async def speak(
        self, context: NegotiationContext, correction: str | None = None
    ) -> AgentMessage:
        messages = [
            {"role": "system", "content": build_system_prompt(self.spec, context.win_length)},
            {"role": "user", "content": build_user_prompt(context)},
        ]
        if correction:
            messages.append({"role": "user", "content": correction})
        response = await self._llm.complete(
            messages, temperature=self.spec.temperature, json_mode=True
        )
        return self._parse(response.content, response.usage)

    def _parse(self, raw: str, usage: LLMUsage) -> AgentMessage:
        data = extract_json_object(raw)
        if data is None:
            raise AgentResponseError("La respuesta no contiene JSON válido", usage, raw)
        try:
            reply = AgentReply.model_validate(data)
        except ValidationError:
            raise AgentResponseError("El JSON no cumple el esquema esperado", usage, raw) from None
        return AgentMessage(
            agent_id=self.spec.id,
            message=reply.message,
            proposed_move=reply.proposed_move,
            confidence=reply.confidence,
            usage=usage,
        )
