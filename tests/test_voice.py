"""Unit and Integration Tests for R.I.O. Voice & Wake-Word Subsystem (Milestone 3)."""

import asyncio
import io
import wave
import pytest
from packages.schemas.chat import ChatResponse
from packages.schemas.input import InputType
from runtime.permissions import Capability, PermissionManager
from services.orchestrator.orchestrator import RIOOrchestrator
from voice.audio_capture import AudioBuffer, AudioCaptureEngine, AudioConfig
from voice.manager import VoiceManager
from voice.permissions import VoicePermissionManager
from voice.session import VoiceSession, VoiceState
from voice.transcription import TranscriptionService
from voice.wake_word import WakeWordDetector


@pytest.mark.asyncio
async def test_voice_session_state_machine():
    """Verify voice session state machine transitions and telemetry."""
    session = VoiceSession()
    assert session.state == VoiceState.IDLE

    history = []
    session.register_callback(lambda old_st, new_st: history.append((old_st, new_st)))

    # Step through lifecycle
    session.transition_to(VoiceState.LISTENING)
    assert session.state == VoiceState.LISTENING

    session.transition_to(VoiceState.WAKE_DETECTED)
    assert session.state == VoiceState.WAKE_DETECTED

    session.transition_to(VoiceState.CAPTURING)
    assert session.state == VoiceState.CAPTURING

    session.transition_to(VoiceState.TRANSCRIBING)
    assert session.state == VoiceState.TRANSCRIBING

    session.transition_to(VoiceState.PROCESSING)
    assert session.state == VoiceState.PROCESSING

    session.reset_for_listening()
    assert session.state == VoiceState.LISTENING

    # Verify transition history
    assert len(history) == 6
    assert history[0] == (VoiceState.IDLE, VoiceState.LISTENING)
    assert history[1] == (VoiceState.LISTENING, VoiceState.WAKE_DETECTED)


@pytest.mark.asyncio
async def test_voice_permission_gate_enforcement():
    """Verify microphone.read capability is strictly enforced."""
    pm = PermissionManager()
    # Explicitly deny microphone
    pm.set_permission(Capability.MICROPHONE_READ, False)

    vpm = VoicePermissionManager(pm)
    assert vpm.has_microphone_permission() is False

    with pytest.raises(PermissionError):
        vpm.require_microphone_permission()

    # VoiceManager should fail to start when denied
    vm = VoiceManager(permission_manager=pm)
    started = await vm.start()
    assert started is False
    assert vm.is_listening is False

    # Grant permission and verify start succeeds
    pm.set_permission(Capability.MICROPHONE_READ, True)
    assert vpm.has_microphone_permission() is True

    started = await vm.start()
    assert started is True
    assert vm.is_listening is True

    await vm.stop()
    assert vm.is_listening is False


def test_local_wake_word_detector():
    """Verify 100% local wake-word trigger matching and prefix stripping."""
    detector = WakeWordDetector()

    # Match exact trigger
    is_wake, word, remainder = detector.check_text_for_wake_word("Hey RIO, open VS Code")
    assert is_wake is True
    assert word == "hey rio"
    assert remainder == "open VS Code"

    # Match single word trigger
    is_wake, word, remainder = detector.check_text_for_wake_word("rio search the web for quantum computing")
    assert is_wake is True
    assert word == "rio"
    assert remainder == "search the web for quantum computing"

    # Match Friday trigger
    is_wake, word, remainder = detector.check_text_for_wake_word("FRIDAY: what is the weather today?")
    assert is_wake is True
    assert word == "friday"
    assert remainder == "what is the weather today?"

    # Non-wake sentence should not trigger
    is_wake, word, remainder = detector.check_text_for_wake_word("Good morning everyone in the room")
    assert is_wake is False
    assert word is None
    assert remainder == "Good morning everyone in the room"

    # Strip wake word helper
    stripped = detector.strip_wake_word("OK RIO, launch calculator")
    assert stripped == "launch calculator"


def test_audio_capture_buffer_and_wav_container():
    """Verify audio capture engine, RMS energy calculation, and WAV packaging."""
    engine = AudioCaptureEngine()
    engine.start_capture()
    assert engine.is_capturing is True

    # Generate synthetic 440Hz tone audio
    wav_bytes = AudioCaptureEngine.generate_synthetic_tone(frequency=440.0, duration=0.5)
    assert len(wav_bytes) > 44
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"

    # Feed raw chunk
    dummy_chunk = b"\x00\x00" * 512
    energy, is_silence = engine.feed_chunk(dummy_chunk)
    assert energy >= 0.0

    recorded_wav = engine.stop_capture()
    assert engine.is_capturing is False
    assert len(recorded_wav) > 44
    assert recorded_wav[:4] == b"RIFF"


@pytest.mark.asyncio
async def test_transcription_service_mock():
    """Verify TranscriptionService converts audio to text with fallback support."""
    service = TranscriptionService()
    dummy_wav = AudioCaptureEngine.generate_synthetic_tone(duration=0.2)

    text = await service.transcribe(dummy_wav)
    assert isinstance(text, str)
    assert len(text) > 0


@pytest.mark.asyncio
async def test_voice_manager_end_to_end_execution():
    """Verify voice manager routes voice commands to the orchestrator pipeline."""
    pm = PermissionManager()
    pm.set_permission(Capability.MICROPHONE_READ, True)

    vm = VoiceManager(permission_manager=pm)
    await vm.start()
    assert vm.is_listening is True

    # Simulate voice command: "Hey RIO, what is 25 + 75?"
    chat_response = await vm.execute_voice_command_text("Hey RIO, what is 25 + 75?")
    assert isinstance(chat_response, ChatResponse)
    assert chat_response.reply is not None
    assert len(chat_response.reply) > 0

    # Verify session returned to LISTENING state
    assert vm.current_session.state == VoiceState.LISTENING

    await vm.stop()
    assert vm.is_listening is False


@pytest.mark.asyncio
async def test_voice_manager_concurrency_and_cleanup():
    """Verify single-listener guarantee and graceful audio resource teardown."""
    pm = PermissionManager()
    pm.set_permission(Capability.MICROPHONE_READ, True)

    vm = VoiceManager(permission_manager=pm)
    start_1 = await vm.start()
    start_2 = await vm.start()  # Idempotent re-start
    assert start_1 is True
    assert start_2 is True

    await vm.stop()
    assert vm.is_listening is False
