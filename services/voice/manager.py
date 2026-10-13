"""Always-On Voice Runtime Manager for R.I.O. (Milestone 5.x).

Coordinates the persistent local voice interaction loop:
- In STANDBY: monitors local microphone with zero cloud streaming
- On "Hey RIO": wakes, speaks "Yes?", transitions to ACTIVE
- In ACTIVE: continuous natural multi-turn conversation (remains ACTIVE!)
- On "RIO, standby": transitions to STANDBY ("Standing by.")
- On "RIO, shut down": executes graceful daemon shutdown ("Shutting down.")
- On "RIO, stop": interrupts speech and cancels in-flight operations
"""

import asyncio
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional

from runtime.state import RuntimeState, RuntimeStateMachine
from services.voice.session import VoiceSession, VoiceSessionState
from services.voice.stt import STTService
from services.voice.tts import AudioResult, TTSManager
from services.voice.vad import VoiceActivityDetector
from services.voice.wakeword import WakeWordDetector

logger = logging.getLogger("rio.voice.manager")


class VoiceRuntimeManager:
    """Manages continuous local microphone listening, wake detection, and speech dispatch."""

    def __init__(
        self,
        wake_detector: Optional[WakeWordDetector] = None,
        vad: Optional[VoiceActivityDetector] = None,
        stt: Optional[STTService] = None,
        tts_manager: Optional[TTSManager] = None,
        state_machine: Optional[RuntimeStateMachine] = None,
        command_handler: Optional[Callable[[str], Any]] = None,
    ):
        self.wake_detector = wake_detector or WakeWordDetector()
        self.vad = vad or VoiceActivityDetector()
        self.stt = stt or STTService()
        self.tts = tts_manager or TTSManager()
        self.state_machine = state_machine or RuntimeStateMachine()
        self.command_handler = command_handler

        self.session = VoiceSession()
        self._is_running = False
        self._listener_task: Optional[asyncio.Task] = None
        self._shutdown_callback: Optional[Callable[[], Any]] = None

    def register_shutdown_callback(self, cb: Callable[[], Any]) -> None:
        self._shutdown_callback = cb

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_active(self) -> bool:
        return self.state_machine.current_state == RuntimeState.ACTIVE

    @property
    def is_standby(self) -> bool:
        return self.state_machine.current_state == RuntimeState.STANDBY

    async def start(self) -> None:
        """Start always-on voice manager."""
        if self._is_running:
            return
        self._is_running = True
        self.state_machine.transition_to(RuntimeState.STANDBY)
        self.session.transition_to(VoiceSessionState.STANDBY)
        logger.info("🎙️ Always-on local voice runtime started. State: STANDBY.")

        # In non-test mode, start physical microphone listener
        if os.getenv("RIO_ENV") != "test" and not os.getenv("RIO_DISABLE_MIC"):
            self._listener_task = asyncio.create_task(self._microphone_listener_loop())

    async def stop(self) -> None:
        """Stop voice runtime and release audio resources."""
        if not self._is_running:
            return
        self._is_running = False
        self.tts.interrupt()
        await self.tts.queue.stop()
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        self.state_machine.transition_to(RuntimeState.STOPPED)
        logger.info("Voice runtime stopped cleanly.")

    async def _microphone_listener_loop(self) -> None:
        """Continuously capture audio from physical microphone and process voice activity."""
        try:
            import sounddevice as sd
        except ImportError:
            logger.info("sounddevice not available; live microphone listening disabled.")
            return

        loop = asyncio.get_running_loop()
        audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)

        def audio_callback(indata, frames, time_info, status):
            if status:
                pass
            pcm = indata.tobytes()
            try:
                loop.call_soon_threadsafe(audio_queue.put_nowait, pcm)
            except Exception:
                pass

        try:
            stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="int16",
                blocksize=1024,
                callback=audio_callback,
            )
        except Exception as e:
            logger.warning(f"Could not open microphone stream: {e}")
            return

        logger.info("🎤 Microphone listener active. Awaiting voice input...")

        try:
            with stream:
                while self._is_running:
                    try:
                        chunk = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break

                    in_speech, is_complete, energy = self.vad.process_chunk(chunk)

                    if is_complete:
                        audio_pcm = self.vad.get_audio_bytes()
                        self.vad.reset()
                        if audio_pcm and len(audio_pcm) >= 16000 * 2 * 0.3:  # > 300ms
                            asyncio.create_task(self._process_recorded_utterance(audio_pcm))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Error in microphone listener loop: {e}")
        finally:
            logger.info("Microphone listener stopped.")

    async def _process_recorded_utterance(self, pcm_data: bytes) -> None:
        """Transcribe and process recorded speech from microphone."""
        try:
            wav_bytes = self.stt.pcm_to_wav(pcm_data)
            text = await self.stt.transcribe(wav_bytes)
            if not text or not text.strip():
                return

            logger.info(f"🎙️ Heard speech: '{text}' [State: {self.state_machine.current_state.value}]")
            await self.process_user_speech(text)
        except Exception as e:
            logger.error(f"Error processing microphone utterance: {e}")

    async def handle_wake_trigger(self, wake_phrase: str = "Hey RIO") -> None:
        """Wake up R.I.O. from STANDBY to ACTIVE."""
        logger.info(f"Wake phrase detected: '{wake_phrase}'. Transitioning to ACTIVE.")
        self.state_machine.transition_to(RuntimeState.AWAKING)
        self.session.transition_to(VoiceSessionState.AWAKING)
        self.session.wake_phrase_detected = wake_phrase

        # Female TTS responds "Yes?"
        await self.tts.speak("Yes?", priority=True)

        self.state_machine.transition_to(RuntimeState.ACTIVE)
        self.session.transition_to(VoiceSessionState.ACTIVE)

    async def enter_standby(self) -> None:
        """Transition from ACTIVE to STANDBY."""
        logger.info("Transitioning to STANDBY on user command.")
        await self.tts.speak("Standing by.", priority=True)
        self.state_machine.transition_to(RuntimeState.STANDBY)
        self.session.transition_to(VoiceSessionState.STANDBY)

    async def trigger_shutdown(self) -> None:
        """Trigger graceful shutdown on voice command."""
        logger.info("Triggering shutdown on voice command.")
        await self.tts.speak("Shutting down.", priority=True)
        self.state_machine.transition_to(RuntimeState.SHUTTING_DOWN)
        if self._shutdown_callback:
            if asyncio.iscoroutinefunction(self._shutdown_callback):
                await self._shutdown_callback()
            else:
                res = self._shutdown_callback()
                if asyncio.iscoroutine(res):
                    await res

    async def process_user_speech(self, text: str) -> Optional[str]:
        """Process recognized user speech according to current state.
        
        Handles:
        - Standby wake phrase detection
        - Interruption ("RIO, stop")
        - Standby command ("RIO, standby")
        - Shutdown command ("RIO, shut down")
        - Conversation / Action dispatch
        """
        if not text or not text.strip():
            return None

        clean_text = text.strip()
        lower = clean_text.lower()

        # 1. Check for immediate interruption ("RIO, stop")
        if lower in ("rio stop", "rio, stop", "stop", "cancel", "halt"):
            self.tts.interrupt()
            return "Stopped."

        # 2. Check for shutdown command
        if lower in ("rio, shut down", "rio shut down", "shut down", "shutdown", "rio shutdown"):
            await self.trigger_shutdown()
            return "Shutting down."

        # 3. Check for standby command
        if lower in ("rio, standby", "rio standby", "standby", "go to sleep", "sleep"):
            await self.enter_standby()
            return "Standing by."

        # 4. If in STANDBY mode: check for wake word
        if self.state_machine.current_state in (RuntimeState.STANDBY, RuntimeState.STOPPED):
            is_wake, matched_phrase, remainder = self.wake_detector.check_text(clean_text)
            if is_wake:
                await self.handle_wake_trigger(matched_phrase or "Hey RIO")
                if remainder and not all(w in ("hello", "hi", "hey", "rio") for w in re.sub(r"[^\w\s]", " ", remainder).lower().split()):
                    # If user said e.g. "Hey RIO, open Chrome" in a single breath
                    return await self.process_user_speech(remainder)
                return "Yes?"
            else:
                logger.debug(f"[STANDBY] Non-wake utterance ignored: '{clean_text}'")
                return None

        # 5. If already ACTIVE: process the user's command directly!
        # Strip wake phrase if user repeated it out of habit
        clean_command = self.wake_detector.strip_wake_phrase(clean_text)

        self.state_machine.transition_to(RuntimeState.PROCESSING)
        self.session.transition_to(VoiceSessionState.PROCESSING)

        reply: Optional[str] = None
        if self.command_handler:
            try:
                res = self.command_handler(clean_command)
                if asyncio.iscoroutine(res):
                    res = await res
                if isinstance(res, tuple):
                    reply = str(res[1])
                else:
                    reply = str(res)
            except Exception as e:
                logger.error(f"Error handling command '{clean_command}': {e}")
                reply = "I encountered an error processing your request."
        else:
            reply = f"Acknowledged: {clean_command}"

        # 6. Speak the response
        if reply:
            self.state_machine.transition_to(RuntimeState.RESPONDING)
            self.session.transition_to(VoiceSessionState.RESPONDING)
            await self.tts.speak(reply)
            self.session.record_turn(user_text=clean_command, assistant_response=reply)

        # 7. CRITICAL RULE: Remain ACTIVE after completing the command!
        self.state_machine.transition_to(RuntimeState.ACTIVE)
        self.session.transition_to(VoiceSessionState.ACTIVE)

        return reply
