"""Configuración desde variables de entorno."""

import os
from dataclasses import dataclass

from app.game.coords import MAX_BOARD_SIZE
from app.game.lookahead import MAX_LOOKAHEAD_PLIES


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    board_size: int = 6
    win_length: int = 4
    max_rounds: int = 3
    tactical_hints: bool = True
    tactical_lookahead_plies: int = 4  # 0 = sin análisis futuro; 1..6 medias jugadas
    llm_mock: bool = False
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    openrouter_api_key: str = ""
    openrouter_model: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    def __post_init__(self) -> None:
        if not 2 <= self.board_size <= MAX_BOARD_SIZE:
            raise ValueError(f"BOARD_SIZE debe estar entre 2 y {MAX_BOARD_SIZE}")
        if not 2 <= self.win_length <= self.board_size:
            raise ValueError("WIN_LENGTH debe estar entre 2 y BOARD_SIZE")
        if self.max_rounds < 1:
            raise ValueError("MAX_ROUNDS debe ser >= 1")
        if not 0 <= self.tactical_lookahead_plies <= MAX_LOOKAHEAD_PLIES:
            raise ValueError(f"TACTICAL_LOOKAHEAD_PLIES debe estar entre 0 y {MAX_LOOKAHEAD_PLIES}")

    def __repr__(self) -> str:  # nunca exponer la API key en logs
        return (
            f"Settings(board_size={self.board_size}, win_length={self.win_length}, "
            f"max_rounds={self.max_rounds}, llm_mock={self.llm_mock}, "
            f"model={self.openrouter_model!r}, api_key={'***' if self.openrouter_api_key else ''})"
        )

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        origins = e.get("CORS_ORIGINS", "http://localhost:5173")
        return cls(
            board_size=int(e.get("BOARD_SIZE") or 6),
            win_length=int(e.get("WIN_LENGTH") or 4),
            max_rounds=int(e.get("MAX_ROUNDS") or 3),
            tactical_hints=_bool(e.get("TACTICAL_HINTS"), True),
            tactical_lookahead_plies=int(e.get("TACTICAL_LOOKAHEAD_PLIES") or 4),
            llm_mock=_bool(e.get("LLM_MOCK"), False),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            openrouter_api_key=e.get("OPENROUTER_API_KEY", ""),
            openrouter_model=e.get("OPENROUTER_MODEL", ""),
            openrouter_base_url=e.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
        )
