"""Cliente LLM determinista para desarrollo y tests sin credenciales (LLM_MOCK=true)."""

import json
import re
import zlib

from app.llm.base import LLMResponse, LLMUsage, Message

_FREE_LINE = re.compile(r"Celdas libres[^\n]*:\s*([^\n]+)")
_FREE_CELL = re.compile(r"([A-Z]\d+)=(\d+)")
_ROUND = re.compile(r"Ronda (\d+) de")
_ROWS = re.compile(r"^\s*\d+ [.XO]( [.XO])*$", re.MULTILINE)


class MockLLMClient:
    """Ronda 1: cada agente propone una celda según su system prompt (hay desacuerdo).
    Ronda 2+: todos convergen en la celda libre más central (hay consenso)."""

    async def complete(
        self, messages: list[Message], *, temperature: float = 0.7, json_mode: bool = True
    ) -> LLMResponse:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = "\n".join(m["content"] for m in messages if m["role"] == "user")
        cells = self._free_cells(user)
        if not cells:
            content = "no hay celdas libres"
        else:
            coord, index = self._choose(system, user, cells)
            content = json.dumps(
                {
                    "message": f"Propongo {coord}: me parece la mejor opción ahora.",
                    "proposed_move": index,
                    "confidence": 0.7,
                },
                ensure_ascii=False,
            )
        prompt_tokens = max(1, sum(len(m["content"]) for m in messages) // 4)
        completion_tokens = max(1, len(content) // 4)
        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=10.0 + completion_tokens,
            cost=round((prompt_tokens + completion_tokens) * 1e-6, 8),
        )
        return LLMResponse(content=content, usage=usage)

    @staticmethod
    def _free_cells(user: str) -> list[tuple[str, int]]:
        match = None
        for match in _FREE_LINE.finditer(user):
            pass
        if match is None:
            return []
        return [(c, int(i)) for c, i in _FREE_CELL.findall(match.group(1))]

    @staticmethod
    def _choose(system: str, user: str, cells: list[tuple[str, int]]) -> tuple[str, int]:
        rounds = [int(r) for r in _ROUND.findall(user)]
        current_round = rounds[-1] if rounds else 1
        if current_round <= 1:
            return cells[zlib.crc32(system.encode()) % len(cells)]
        size = len(_ROWS.findall(user)) or 6
        center = (size - 1) / 2

        def distance(cell: tuple[str, int]) -> tuple[float, int]:
            row, col = divmod(cell[1], size)
            return (abs(row - center) + abs(col - center), cell[1])

        return min(cells, key=distance)
