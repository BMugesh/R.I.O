"""Unit tests for Multi-Turn Context and Follow-up Reference Resolution (Milestone 5.x)."""

import pytest
from services.conversation.context import ConversationContext
from services.conversation.intent import IntentClassifier, IntentType

pytestmark = pytest.mark.unit


def test_follow_up_pronoun_resolution():
    """Verify 'open it' resolves to the previous target (e.g. VS Code)."""
    context = ConversationContext()
    context.record_action("open", "VS Code")

    resolved = IntentClassifier.resolve_follow_ups("Open it", context)
    assert resolved.lower() == "open vs code"

    resolved2 = IntentClassifier.resolve_follow_ups("Launch that", context)
    assert resolved2.lower() == "launch vs code"


def test_follow_up_project_resolution():
    """Verify 'run the tests' preserves project context."""
    context = ConversationContext()
    context.set_entity("project", "RIO")

    resolved = IntentClassifier.resolve_follow_ups("test the project", context)
    assert "rio" in resolved.lower()


def test_context_entity_persistence():
    """Verify context entities are correctly recorded and retrieved."""
    context = ConversationContext()
    context.set_entity("browser", "Chrome")
    context.record_topic("Quantum QAOA")

    assert context.get_entity("browser") == "Chrome"
    assert context.last_topic == "Quantum QAOA"
    assert context.get_entity("topic") == "Quantum QAOA"
