"""Unit tests for Configurable Local Wake-Word Detector (Milestone 5.x)."""

import pytest
from services.voice.wakeword import WakeWordDetector

pytestmark = pytest.mark.unit


def test_default_wake_phrase_hey_rio():
    """Verify default phrase 'Hey RIO' is matched locally."""
    detector = WakeWordDetector()

    # Exact trigger
    matched, phrase, remainder = detector.check_text("Hey RIO")
    assert matched is True
    assert phrase == "hey rio"
    assert remainder == ""

    # Trigger with trailing command
    matched, phrase, remainder = detector.check_text("Hey RIO, open VS Code")
    assert matched is True
    assert phrase == "hey rio"
    assert remainder == "open VS Code"


def test_configurable_aliases():
    """Verify aliases like 'Friday', 'Wake up RIO', 'RIO' are supported."""
    detector = WakeWordDetector(wake_phrase="Hey RIO", aliases=["Friday", "Wake up RIO", "RIO"])

    matched, phrase, remainder = detector.check_text("Friday, what is 25 * 4?")
    assert matched is True
    assert phrase == "friday"
    assert remainder == "what is 25 * 4?"

    matched, phrase, remainder = detector.check_text("Wake up RIO")
    assert matched is True
    assert phrase == "wake up rio"

    matched, phrase, remainder = detector.check_text("RIO, check system stats")
    assert matched is True
    assert phrase == "rio"
    assert remainder == "check system stats"


def test_non_wake_phrases_rejected():
    """Verify ordinary conversational phrases do not trigger wake detector."""
    detector = WakeWordDetector()

    matched, phrase, remainder = detector.check_text("Hello there, how are you?")
    assert matched is False
    assert phrase is None

    matched, phrase, remainder = detector.check_text("I am talking to Rio de Janeiro")
    # 'Rio' alone at the start would match, but inside sentence it does not match
    matched, phrase, remainder = detector.check_text("Let's go to Paris")
    assert matched is False


def test_strip_wake_phrase():
    """Verify prefix removal leaves pristine command."""
    detector = WakeWordDetector()
    assert detector.strip_wake_phrase("Hey RIO: Open Chrome") == "Open Chrome"
    assert detector.strip_wake_phrase("Hey RIO, run the tests") == "run the tests"
    assert detector.strip_wake_phrase("Search YouTube") == "Search YouTube"
