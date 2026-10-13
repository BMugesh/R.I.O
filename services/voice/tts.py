"""Female Text-To-Speech (TTS) Subsystem for R.I.O. (Milestone 5.x).

Provides:
- TTSProvider abstract contract
- WindowsSAPITTSProvider with female voice selection (e.g. Microsoft Zira / Heera)
- MockTTSProvider for deterministic, leak-free test execution
- VoiceResponseQueue for non-overlapping sequential speech
- TTSManager with instant interruption ("RIO, stop") and clean speech filtering
"""

import asyncio
from dataclasses import dataclass, field
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rio.voice.tts")


@dataclass
class AudioResult:
    """Represents synthesized audio output."""
    audio_bytes: bytes = b""
    duration_seconds: float = 0.0
    text: str = ""
    voice_used: str = "female"
    success: bool = True
    error: Optional[str] = None


class TTSProvider:
    """Abstract Base Class for Text-to-Speech synthesis."""

    async def synthesize(
        self,
        text: str,
        voice: str = "female",
        language: str = "en-IN",
        speed: float = 1.0,
    ) -> AudioResult:
        raise NotImplementedError


class MockTTSProvider(TTSProvider):
    """In-memory mock TTS provider for testing and headless environments."""

    def __init__(self):
        self.spoken_history: List[str] = []
        self._interrupted: bool = False

    async def synthesize(
        self,
        text: str,
        voice: str = "female",
        language: str = "en-IN",
        speed: float = 1.0,
    ) -> AudioResult:
        self.spoken_history.append(text)
        logger.debug(f"[MockTTS] Spoke: '{text}' (voice: {voice}, lang: {language})")
        return AudioResult(
            audio_bytes=b"RIFF_MOCK_WAV",
            duration_seconds=max(0.1, len(text.split()) * 0.3),
            text=text,
            voice_used=voice,
            success=True,
        )

    def interrupt(self) -> None:
        self._interrupted = True

    def clear(self) -> None:
        self.spoken_history.clear()
        self._interrupted = False


class WindowsSAPITTSProvider(TTSProvider):
    """Windows SAPI5 / PowerShell Speech Synthesizer with female voice selection."""

    def __init__(self):
        self._active_voice: str = "female"

    def interrupt(self) -> None:
        """Immediately halt ongoing audio playback."""
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    def _sync_speak(self, text: str, voice_pref: str = "female", speed: float = 1.0) -> bool:
        if sys.platform != "win32" or not text.strip():
            return False

        # --- Method 1: SAPI to WAV Stream + winsound Playback (Reliable, Zero UI) ---
        try:
            import pythoncom
            import tempfile
            import win32com.client
            import winsound

            pythoncom.CoInitialize()
            temp_wav = os.path.join(
                tempfile.gettempdir(),
                f"rio_tts_{os.getpid()}_{int(time.time() * 1000)}.wav",
            )
            try:
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                stream = win32com.client.Dispatch("SAPI.SpFileStream")
                stream.Open(temp_wav, 3)  # 3 = SSFMCreateForWrite
                speaker.AudioOutputStream = stream

                # Select female voice
                voices = speaker.GetVoices()
                for v in voices:
                    desc = v.GetDescription().lower()
                    if any(n in desc for n in ("zira", "heera", "female", "hazel")):
                        speaker.Voice = v
                        break

                # Adjust rate (-10 to 10 scale, default 0 is 1.0x)
                rate = int((speed - 1.0) * 5)
                speaker.Rate = max(-10, min(10, rate))
                speaker.Speak(text)
                stream.Close()

                # Cleanly release COM pointers before CoUninitialize
                del stream
                del voices
                if "v" in locals():
                    del v
                del speaker
            finally:
                pythoncom.CoUninitialize()

            # Play synthesized audio via default Windows sound device
            if os.path.exists(temp_wav) and os.path.getsize(temp_wav) > 44:
                winsound.PlaySound(temp_wav, winsound.SND_FILENAME)
                try:
                    os.unlink(temp_wav)
                except Exception:
                    pass
                return True
        except Exception as e:
            logger.debug(f"SAPI WAV playback attempt failed: {e}. Trying direct SAPI Speak.")

        # --- Method 2: Direct SAPI Speak ---
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            try:
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                voices = speaker.GetVoices()
                for v in voices:
                    desc = v.GetDescription().lower()
                    if any(n in desc for n in ("zira", "heera", "female", "hazel")):
                        speaker.Voice = v
                        break
                rate = int((speed - 1.0) * 5)
                speaker.Rate = max(-10, min(10, rate))
                speaker.Speak(text)
                del voices
                if "v" in locals():
                    del v
                del speaker
                return True
            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.debug(f"Direct SAPI failed: {e}. Falling back to silent PowerShell SpeechSynthesizer.")

        # --- Method 3: PowerShell SpeechSynthesizer (Headless, CREATE_NO_WINDOW) ---
        try:
            import subprocess
            import tempfile

            clean_text = text.replace('"', '`"').replace("'", "''")
            ps_script = (
                "Add-Type -AssemblyName System.Speech;\n"
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;\n"
                "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Gender -eq 'Female' } | Select-Object -First 1;\n"
                "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) };\n"
                f"$s.Speak('{clean_text}');\n"
            )
            with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as ps_f:
                ps_f.write(ps_script)
                ps_path = ps_f.name

            try:
                CREATE_NO_WINDOW = 0x08000000
                subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW,
                    check=False,
                    timeout=10.0,
                )
                return True
            finally:
                try:
                    os.unlink(ps_path)
                except Exception:
                    pass
        except Exception as ex:
            logger.warning(f"PowerShell TTS fallback failed: {ex}")
            return False

    async def synthesize(
        self,
        text: str,
        voice: str = "female",
        language: str = "en-IN",
        speed: float = 1.0,
    ) -> AudioResult:
        t0 = time.perf_counter()
        success = await asyncio.to_thread(self._sync_speak, text, voice, speed)
        duration = time.perf_counter() - t0
        return AudioResult(
            text=text,
            duration_seconds=duration,
            voice_used=voice,
            success=success,
        )


class VoiceResponseQueue:
    """Serial FIFO queue ensuring voice responses never overlap."""

    def __init__(self, tts_manager: "TTSManager"):
        self.tts_manager = tts_manager
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._is_playing: bool = False

    def start(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_queue())

    async def enqueue(self, text: str) -> None:
        """Add speech text to the queue."""
        self.start()
        await self._queue.put(text)

    def clear(self) -> None:
        """Flush the queue immediately."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except (asyncio.QueueEmpty, ValueError):
                break

    async def _process_queue(self) -> None:
        while True:
            try:
                text = await self._queue.get()
                self._is_playing = True
                try:
                    await self.tts_manager.provider.synthesize(
                        text=text,
                        voice=self.tts_manager.voice,
                        language=self.tts_manager.language,
                        speed=self.tts_manager.speed,
                    )
                except Exception as e:
                    logger.warning(f"Error during queued speech synthesis: {e}")
                finally:
                    self._is_playing = False
                    self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in VoiceResponseQueue: {e}")

    async def stop(self) -> None:
        self.clear()
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass


class TTSManager:
    """High-level Female TTS subsystem manager."""

    def __init__(
        self,
        provider: Optional[TTSProvider] = None,
        voice: str = "female",
        language: str = "en-IN",
        speed: float = 1.0,
    ):
        self.voice = os.getenv("RIO_VOICE", voice).lower()
        self.language = os.getenv("RIO_VOICE_LANGUAGE", language)
        self.speed = float(os.getenv("RIO_VOICE_SPEED", str(speed)))

        # Choose provider: Mock in test mode or if specified
        if provider:
            self.provider = provider
        elif os.getenv("RIO_ENV") == "test" or os.getenv("RIO_TTS_PROVIDER") == "mock":
            self.provider = MockTTSProvider()
        elif sys.platform == "win32":
            self.provider = WindowsSAPITTSProvider()
        else:
            self.provider = MockTTSProvider()

        self.queue = VoiceResponseQueue(self)
        self._history: List[str] = []

    def clean_text_for_speech(self, text: str) -> str:
        """Filter out technical JSON, markdown formatting, code blocks, and traces."""
        if not text:
            return ""

        # Remove code blocks
        clean = re.sub(r"```[\s\S]*?```", "", text)
        # Remove inline backticks
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        # Remove raw JSON structures like {"status": "success", ...}
        clean = re.sub(r"\{[^{}]*\}", "", clean)
        # Remove markdown bold/italics
        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
        clean = re.sub(r"\*([^*]+)\*", r"\1", clean)
        # Remove URLs
        clean = re.sub(r"http\S+", "", clean)
        # Collapse extra whitespace
        clean = re.sub(r"\s+", " ", clean).strip()

        return clean

    async def speak(self, text: str, priority: bool = False) -> AudioResult:
        """Synthesize and speak text. If priority is True, plays immediately."""
        clean_text = self.clean_text_for_speech(text)
        if not clean_text:
            return AudioResult(text="", success=True)

        self._history.append(clean_text)

        if priority:
            self.queue.clear()
            return await self.provider.synthesize(
                text=clean_text,
                voice=self.voice,
                language=self.language,
                speed=self.speed,
            )
        else:
            await self.queue.enqueue(clean_text)
            return AudioResult(text=clean_text, success=True)

    def interrupt(self) -> None:
        """Immediately halt ongoing speech and flush queue (e.g. upon 'RIO, stop')."""
        logger.info("Voice interruption triggered. Halting TTS.")
        self.queue.clear()
        if hasattr(self.provider, "interrupt"):
            self.provider.interrupt()

    @property
    def spoken_history(self) -> List[str]:
        if isinstance(self.provider, MockTTSProvider):
            return self.provider.spoken_history
        return self._history
