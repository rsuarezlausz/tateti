import random

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.games import router as games_router
from app.config import Settings
from app.llm.base import LLMClient
from app.sessions import GameStore


def create_app(
    settings: Settings | None = None,
    *,
    llm: LLMClient | None = None,
    rng: random.Random | None = None,
) -> FastAPI:
    """`llm`/`rng` solo se inyectan en tests; por defecto el cliente se arma desde la config
    (de forma perezosa, para que /api/health funcione sin credenciales)."""
    settings = settings or Settings.from_env()
    app = FastAPI(title="TicTacToe Agent Factory")
    app.state.settings = settings
    app.state.llm = llm
    app.state.rng = rng
    app.state.store = GameStore()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(agents_router)
    app.include_router(games_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
