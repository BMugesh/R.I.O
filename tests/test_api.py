"""Integration tests for FastAPI REST API endpoints."""
import pytest
pytestmark = pytest.mark.integration



import pytest
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_list_agents_api():
    res = client.get("/api/v1/agents")
    assert res.status_code == 200
    agents = res.json()
    assert len(agents) >= 14
    agent_ids = [a["id"] for a in agents]
    assert "conversation_agent" in agent_ids
    assert "quantum_agent" in agent_ids
    assert "computer_agent" in agent_ids


def test_list_tools_api():
    res = client.get("/api/v1/tools")
    assert res.status_code == 200
    tools = res.json()
    assert len(tools) >= 5


def test_list_devices_api():
    res = client.get("/api/v1/devices")
    assert res.status_code == 200
    devices = res.json()
    assert len(devices) >= 2


def test_chat_endpoint():
    payload = {
        "message": "Hi RIO, what's up?",
        "sessionId": "test_api_session",
        "developerMode": False,
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert data["developer_trace"] is None


def test_chat_endpoint_developer_mode():
    payload = {
        "message": "Open WhatsApp and send message to Arun",
        "sessionId": "test_api_session_2",
        "developerMode": True,
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert data["developer_trace"] is not None
