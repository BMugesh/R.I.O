"""Unit tests for LocalSystemAgent and Host Telemetry (Milestone 5.x)."""

import pytest
from agents.system.agent import LocalSystemAgent
from packages.schemas.agents import AgentStatus
from packages.schemas.input import InputType, RIOInput
from services.conversation.intent import IntentClassifier, IntentType
from services.conversation.manager import ConversationManager

pytestmark = pytest.mark.unit

@pytest.fixture
def system_agent():
    return LocalSystemAgent()

def test_system_agent_manifest(system_agent):
    manifest = system_agent.manifest
    assert manifest.id == "local_system_agent"
    assert "system_time_read" in manifest.capabilities
    assert "system_hardware_telemetry" in manifest.capabilities
    assert "system.time.read" in manifest.required_tools
    assert "system.gpu.read" in manifest.required_tools
    assert "system.memory.read" in manifest.required_tools

@pytest.mark.asyncio
async def test_system_time_and_date(system_agent):
    # Time
    res_time = await system_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "system.time.read"}),
        context={}
    )
    assert res_time.status == AgentStatus.SUCCESS
    assert res_time.data["verified"] is True
    assert "time_12h" in res_time.data
    assert "iso" in res_time.data
    assert len(res_time.evidence) > 0
    assert res_time.evidence[0].verified is True

    # Date
    res_date = await system_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "system.date.read"}),
        context={}
    )
    assert res_date.status == AgentStatus.SUCCESS
    assert res_date.data["verified"] is True
    assert "year" in res_date.data
    assert "day_of_week" in res_date.data

@pytest.mark.asyncio
async def test_system_hardware_telemetry(system_agent):
    # CPU
    res_cpu = await system_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "system.cpu.read"}),
        context={}
    )
    assert res_cpu.status == AgentStatus.SUCCESS
    assert res_cpu.data["verified"] is True
    assert res_cpu.data["logical_cores"] > 0

    # RAM / Memory
    res_mem = await system_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "system.memory.read"}),
        context={}
    )
    assert res_mem.status == AgentStatus.SUCCESS
    assert res_mem.data["verified"] is True
    assert res_mem.data["total_gb"] > 0
    assert res_mem.data["percent_used"] > 0

    # GPU
    res_gpu = await system_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "system.gpu.read"}),
        context={}
    )
    assert res_gpu.status == AgentStatus.SUCCESS
    assert res_gpu.data["verified"] is True
    assert "device" in res_gpu.data

    # Battery
    res_bat = await system_agent.run(
        RIOInput(type=InputType.TEXT, payload={"action": "system.battery.read"}),
        context={}
    )
    assert res_bat.status == AgentStatus.SUCCESS
    assert res_bat.data["verified"] is True

@pytest.mark.asyncio
async def test_natural_language_query_resolution(system_agent):
    # Natural query for time
    res_time = await system_agent.run(
        RIOInput(type=InputType.TEXT, payload="What time is it?"),
        context={}
    )
    assert res_time.status == AgentStatus.SUCCESS
    assert res_time.data["verified"] is True
    assert "time_12h" in res_time.data
    assert "current time is" in res_time.message.lower()

    # Natural query for GPU
    res_gpu = await system_agent.run(
        RIOInput(type=InputType.TEXT, payload="What GPU do I have?"),
        context={}
    )
    assert res_gpu.status == AgentStatus.SUCCESS
    assert res_gpu.data["verified"] is True
    assert "device" in res_gpu.data

def test_intent_classification_routes_system_queries():
    queries = [
        "What time is it?",
        "What is today's date?",
        "What GPU do I have?",
        "How much RAM am I using?",
        "What is my CPU usage?",
        "What is my battery level?",
    ]
    for q in queries:
        intent, contract = IntentClassifier.classify(q)
        assert intent == IntentType.ACTION
        assert contract is not None
        assert contract.target == "local_system"

@pytest.mark.asyncio
async def test_conversation_manager_handles_system_telemetry_locally():
    mgr = ConversationManager()
    intent, reply = await mgr.handle_user_utterance("What time is it?")
    assert intent == IntentType.ACTION
    assert "current time is" in reply.lower()

    intent_gpu, reply_gpu = await mgr.handle_user_utterance("What GPU do I have?")
    assert intent_gpu == IntentType.ACTION
    assert "gpu" in reply_gpu.lower()
