"""Unit tests for all 14 R.I.O. modular agents."""

import pytest
from agents import (
    BrowserAgent,
    CodingAgent,
    ComputerAgent,
    ConversationAgent,
    DeviceAgent,
    DocumentAgent,
    FileSystemAgent,
    GitHubAgent,
    MemoryAgent,
    PlannerAgent,
    QuantumAgent,
    ResearchAgent,
    VerificationAgent,
    VisionAgent,
)
from packages.schemas.agents import AgentStatus
from packages.schemas.input import InputType, RIOInput
from services.model_router.router import ModelRouter


@pytest.mark.asyncio
async def test_all_14_agents_manifest_and_execution():
    model_router = ModelRouter(default_provider="mock")

    agents = [
        ConversationAgent(model_router=model_router),
        PlannerAgent(model_router=model_router),
        ResearchAgent(model_router=model_router),
        CodingAgent(model_router=model_router),
        BrowserAgent(model_router=model_router),
        ComputerAgent(model_router=model_router),
        VisionAgent(model_router=model_router),
        DocumentAgent(model_router=model_router),
        FileSystemAgent(model_router=model_router),
        GitHubAgent(model_router=model_router),
        DeviceAgent(model_router=model_router),
        VerificationAgent(model_router=model_router),
        MemoryAgent(model_router=model_router),
        QuantumAgent(model_router=model_router),
    ]

    assert len(agents) == 14

    for agent in agents:
        manifest = agent.manifest
        assert manifest.id is not None
        assert manifest.name is not None
        assert len(manifest.capabilities) > 0

        # Test execution
        inp = RIOInput(type=InputType.TEXT, payload="Test task execution")
        res = await agent.run(inp, context={"recent_turns": []})
        assert res.status == AgentStatus.SUCCESS
