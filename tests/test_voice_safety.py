"""Unit tests for Voice Safety and Permission Boundaries (Milestone 5.x)."""

import pytest
from services.conversation.intent import IntentClassifier, IntentType

pytestmark = pytest.mark.unit


def test_destructive_operations_tagged_high_risk():
    """Verify destructive actions are classified as high risk for approval enforcement."""
    destructive_commands = [
        "Delete my project folder",
        "Remove all temporary files",
        "Kill all system processes",
        "Format drive C",
    ]

    for cmd in destructive_commands:
        intent, contract = IntentClassifier.classify(cmd)
        assert intent == IntentType.ACTION
        assert contract is not None
        assert contract.risk == "high"


def test_benign_operations_tagged_low_risk():
    """Verify benign operations are classified as low risk."""
    benign_commands = [
        "Open Chrome",
        "Open VS Code",
        "Take a screenshot",
        "Search YouTube",
    ]

    for cmd in benign_commands:
        intent, contract = IntentClassifier.classify(cmd)
        assert intent == IntentType.ACTION
        assert contract is not None
        assert contract.risk == "low"
