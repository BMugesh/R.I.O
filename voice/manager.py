"""Central Voice Manager for R.I.O.

Coordinates permission checks, audio capture, local wake-word detection,
transcription via Groq Whisper, and dispatching to RIOOrchestrator.
Enforces single-listener safety and resource cleanups.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional
from packages.schemas.chat import ChatRequest, ChatResponse
from packages.schemas.input import InputType
from runtime.event_listener import EventListener, RuntimeEvent
from runtime.permissions import PermissionManager
from services.orchestrator.orchestrator import RIOOrchestrator
from voice.audio_capture import AudioCaptureEngine, AudioConfig
from voice.permissions import VoicePermissionManager
from voice.session import VoiceSession, VoiceState
from voice.transcription import TranscriptionService
from voice.wake_word import WakeWordDetector

logger = logging.getLogger("rio.voice.manager")


class VoiceManager:
    """Full lifecycle coordinator for R.I.O. Voice & Wake-Word interface."""

    def __init__(
        self,
        orchestrator: Optional[RIOOrchestrator] = None,
        permission_manager: Optional[PermissionManager] = None,
        event_listener: Optional[EventListener] = None,
        wake_words: Optional[List[str]] = None,
        audio_config: Optional[AudioConfig] = None,
    ):
        self.orchestrator = orchestrator or RIOOrchestrator()
        self.permission_checker = VoicePermissionManager(permission_manager)
        self.event_listener = event_listener or EventListener()

        self.audio_engine = AudioCaptureEngine(audio_config)
        self.wake_word_detector = WakeWordDetector(wake_words)
        self.transcription_service = TranscriptionService(self.orchestrator.model_router)

        self.current_session: Optional[VoiceSession] = None
        self._listener_lock = asyncio.Lock()
        self._is_running: bool = False
        self._command_callbacks: List[Callable[[str, str], Any]] = []

    @property
    def is_listening(self) -> bool:
        """Check if voice manager is actively listening."""
        return self._is_running and self.current_session is not None and self.current_session.state == VoiceState.LISTENING

    def register_command_callback(self, callback: Callable[[str, str], Any]) -> None:
        """Register callback for executed voice commands: (command_text, response_reply) -> None."""
        self._command_callbacks.append(callback)

    async def start(self) -> bool:
        """Initialize and start voice listener if microphone permission is granted."""
        async with self._listener_lock:
            if self._is_running:
                logger.info("VoiceManager is already running.")
                return True

            # 1. Enforce permission check
            if not self.permission_checker.has_microphone_permission():
                err = "Cannot start VoiceManager: 'microphone.read' capability is denied."
                logger.warning(err)
                if self.current_session:
                    self.current_session.transition_to(VoiceState.ERROR, error_message=err)
                return False

            self.current_session = VoiceSession()
            self.current_session.transition_to(VoiceState.LISTENING)
            self._is_running = True

            await self.event_listener.emit(RuntimeEvent("voice_started", {"session_id": self.current_session.session_id}))
            logger.info("🎙️ VoiceManager active and listening for wake-word...")
            return True

    async def stop(self) -> None:
        """Cleanly stop voice listener and release audio resources."""
        async with self._listener_lock:
            if not self._is_running:
                return

            if self.audio_engine.is_capturing:
                self.audio_engine.stop_capture()

            if self.current_session:
                self.current_session.transition_to(VoiceState.IDLE)

            self._is_running = False
            if self.current_session:
                await self.event_listener.emit(RuntimeEvent("voice_stopped", {"session_id": self.current_session.session_id}))
            logger.info("VoiceManager cleanly stopped.")

    async def process_audio_chunk(self, chunk: bytes) -> Optional[ChatResponse]:
        """Process real-time streaming audio chunk."""
        if not self._is_running or not self.current_session:
            return None

        # Calculate energy
        energy = self.audio_engine.buffer.calculate_rms(chunk)

        # In LISTENING state: check energy to trigger wake capture
        if self.current_session.state == VoiceState.LISTENING:
            if energy >= self.audio_engine.config.ENERGY_THRESHOLD:
                logger.info(f"Acoustic activity detected (RMS: {energy:.1f}). Triggering capture buffer.")
                self.current_session.transition_to(VoiceState.WAKE_DETECTED)
                self.current_session.transition_to(VoiceState.CAPTURING)
                self.audio_engine.start_capture()
                self.audio_engine.feed_chunk(chunk)
                await self.event_listener.emit(RuntimeEvent("voice_capturing", {"session_id": self.current_session.session_id}))
            return None

        # In CAPTURING state: feed audio and check for silence limit
        if self.current_session.state == VoiceState.CAPTURING:
            _, is_silence = self.audio_engine.feed_chunk(chunk)
            if is_silence or self.audio_engine.buffer.duration_seconds() >= 10.0:
                logger.info("Speech utterance completed. Processing audio container...")
                wav_bytes = self.audio_engine.stop_capture()
                return await self.process_audio_bytes(wav_bytes)

        return None

    async def process_audio_bytes(
        self,
        audio_bytes: bytes,
        device_id: Optional[str] = None,
    ) -> ChatResponse:
        """Process full audio payload through transcription, wake-word parsing, and orchestration."""
        if not self.permission_checker.has_microphone_permission():
            msg = "Microphone access denied: 'microphone.read' capability is not permitted."
            if self.current_session:
                self.current_session.transition_to(VoiceState.ERROR, error_message=msg)
            raise PermissionError(msg)

        if not self.current_session:
            self.current_session = VoiceSession()

        # 1. State: TRANSCRIBING
        self.current_session.transition_to(VoiceState.TRANSCRIBING)
        self.current_session.audio_bytes_length = len(audio_bytes)
        await self.event_listener.emit(RuntimeEvent("voice_transcribing", {"bytes": len(audio_bytes)}))

        transcription = await self.transcription_service.transcribe(audio_bytes)
        self.current_session.transcribed_text = transcription

        if not transcription:
            logger.warning("Empty transcription result.")
            self.current_session.reset_for_listening()
            return ChatResponse(
                session_id=self.current_session.session_id,
                reply="I could not hear any speech. Please try again.",
                status="no_speech_detected",
            )

        # 2. Check wake-word
        is_wake, matched_word, command = self.wake_word_detector.check_text_for_wake_word(transcription)
        self.current_session.wake_word_detected = matched_word
        self.current_session.command_text = command if is_wake else transcription

        target_command = command if is_wake and command else transcription

        # 3. State: PROCESSING (Dispatch into Unified Orchestrator DAG)
        self.current_session.transition_to(VoiceState.PROCESSING)
        await self.event_listener.emit(RuntimeEvent("voice_processing", {"command": target_command}))

        chat_req = ChatRequest(
            message=target_command,
            session_id=self.current_session.session_id,
            device_id=device_id,
            input_type=InputType.VOICE,
        )

        chat_res = await self.orchestrator.process_chat(chat_req)
        self.current_session.orchestrator_reply = chat_res.reply

        # Notify callbacks
        for cb in self._command_callbacks:
            try:
                cb(target_command, chat_res.reply)
            except Exception as ex:
                logger.warning(f"Error in command callback: {ex}")

        await self.event_listener.emit(RuntimeEvent("voice_executed", {
            "command": target_command,
            "reply": chat_res.reply,
            "status": chat_res.status,
        }))

        # Reset back to LISTENING
        self.current_session.reset_for_listening()
        return chat_res

    async def execute_voice_command_text(
        self,
        voice_text: str,
        device_id: Optional[str] = None,
    ) -> ChatResponse:
        """Simulate or execute a voice command from text (e.g. from tests or CLI)."""
        if not self.permission_checker.has_microphone_permission():
            msg = "Microphone access denied: 'microphone.read' capability is not permitted."
            raise PermissionError(msg)

        if not self.current_session:
            self.current_session = VoiceSession()

        is_wake, matched_word, command = self.wake_word_detector.check_text_for_wake_word(voice_text)
        self.current_session.wake_word_detected = matched_word
        target_command = command if is_wake and command else voice_text
        self.current_session.command_text = target_command
        self.current_session.transcribed_text = voice_text

        self.current_session.transition_to(VoiceState.PROCESSING)

        chat_req = ChatRequest(
            message=target_command,
            session_id=self.current_session.session_id,
            device_id=device_id,
            input_type=InputType.VOICE,
        )

        chat_res = await self.orchestrator.process_chat(chat_req)
        self.current_session.orchestrator_reply = chat_res.reply
        self.current_session.reset_for_listening()
        return chat_res
