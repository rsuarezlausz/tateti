import pytest
from pydantic import ValidationError

from app.agents.spec import AgentSpec
from app.factory.catalog import CATALOG
from app.factory.factory import AgentFactory, InvalidTeamSizeError
from app.llm.mock import MockLLMClient


def make_factory():
    return AgentFactory(MockLLMClient())


def test_catalog_order_and_data():
    assert [s.name for s in CATALOG] == ["Estratega", "Defensivo", "Agresivo", "Caótico"]
    assert len({s.id for s in CATALOG}) == 4


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_create_team_sizes_in_order(n):
    team = make_factory().create_team(n)
    assert [a.spec.id for a in team] == [s.id for s in CATALOG[:n]]


@pytest.mark.parametrize("n", [0, 5, -1, True, "2"])
def test_create_team_rejects_invalid(n):
    with pytest.raises(InvalidTeamSizeError):
        make_factory().create_team(n)


def test_agents_share_injected_client():
    llm = MockLLMClient()
    team = AgentFactory(llm).create_team(3)
    assert all(a._llm is llm for a in team)


def test_factory_accepts_custom_spec_at_runtime():
    spec = AgentSpec(
        id="nuevo", name="Nuevo", personality="p", skills=["a"], system_prompt="s",
        temperature=0.3, color="#112233", avatar="🤖",
    )
    team = AgentFactory(MockLLMClient(), catalog=[spec]).create_team(1)
    assert team[0].spec is spec


@pytest.mark.parametrize(
    "override",
    [{"temperature": 3}, {"color": "rojo"}, {"skills": []}, {"id": ""}, {"avatar": ""}],
)
def test_spec_validation(override):
    data = CATALOG[0].model_dump() | override
    with pytest.raises(ValidationError):
        AgentSpec(**data)


def test_spec_has_no_model_field():
    assert "model" not in AgentSpec.model_fields
