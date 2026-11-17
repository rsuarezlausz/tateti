from pydantic import BaseModel, Field


class AgentSpec(BaseModel):
    """Especificación de un agente. El modelo LLM NO va aquí: viene de la config global."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    personality: str = Field(min_length=1)
    skills: list[str] = Field(min_length=1, max_length=6)
    system_prompt: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    avatar: str = Field(min_length=1, max_length=8)
