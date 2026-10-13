"""Unit tests for Intent Classification and Action Routing (Milestone 5.x)."""

import pytest
from services.conversation.intent import IntentClassifier, IntentType

pytestmark = pytest.mark.unit


def test_conversational_questions_classified_properly():
    """Verify conceptual inquiries are classified as conversational without triggering actions."""
    inquiries = [
        "What is RAG?",
        "Explain the difference between PyTorch and TensorFlow",
        "How does quantum computing work?",
        "Which model would you recommend for my coding project?",
        "Tell me about neural networks",
    ]

    for q in inquiries:
        intent, contract = IntentClassifier.classify(q)
        assert intent == IntentType.CONVERSATIONAL
        assert contract is None


def test_action_requests_classified_properly():
    """Verify desktop and laptop operations emit structured ActionRequestContract."""
    actions = [
        "Open Chrome",
        "Launch VS Code",
        "Run the fast tests",
        "Search YouTube for Python tutorials",
        "Play the first video",
        "Create a folder called benchmark_data",
        "Take a screenshot",
    ]

    for act in actions:
        intent, contract = IntentClassifier.classify(act)
        assert intent == IntentType.ACTION
        assert contract is not None
        assert contract.requires_execution is True
        assert contract.target == "local_laptop"


def test_system_commands_classified_properly():
    """Verify lifecycle voice commands (standby, shut down, stop)."""
    assert IntentClassifier.classify("RIO, standby")[0] == IntentType.SYSTEM_STANDBY
    assert IntentClassifier.classify("standby")[0] == IntentType.SYSTEM_STANDBY

    assert IntentClassifier.classify("RIO, shut down")[0] == IntentType.SYSTEM_SHUTDOWN
    assert IntentClassifier.classify("shut down")[0] == IntentType.SYSTEM_SHUTDOWN

    assert IntentClassifier.classify("RIO, stop")[0] == IntentType.SYSTEM_STOP
    assert IntentClassifier.classify("stop")[0] == IntentType.SYSTEM_STOP


def test_mixed_action_and_reasoning_classified_properly():
    """Verify mixed action + explanation requests are classified as MIXED."""
    mixed_request = "Open Chrome and explain how browser automation works"
    intent, contract = IntentClassifier.classify(mixed_request)
    assert intent == IntentType.MIXED
    assert contract is not None
