"""R.I.O. Background Daemon Runner (Milestone 5.x).

Main executable entrypoint for the R.I.O. Device Runtime.
Supports:
1. Local Persistent Voice Runtime (Default for M5.x — Local CLI, no WebSocket)
2. WebSocket Client Mode (Legacy M2/M2.5 multi-device runtime)
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
import signal
import sys
import time
from typing import Optional

from runtime.device_manager import get_rio_config_dir
from runtime.pidfile import PIDManager, get_data_dir
from runtime.shutdown import RuntimeShutdownHandler
from runtime.state import RuntimeState, RuntimeStateMachine
from runtime.supervisor import RuntimeSupervisor
from services.conversation.manager import ConversationManager
from services.voice.manager import VoiceRuntimeManager

logger = logging.getLogger("rio.runtime.daemon")


def setup_logging():
    """Configure robust file and stream logging for the daemon."""
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "runtime.log"

    handlers = [logging.FileHandler(log_file, encoding="utf-8")]
    if sys.stdout is not None:
        try:
            handlers.append(logging.StreamHandler(sys.stdout))
        except Exception:
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


class LocalVoiceRuntimeDaemon:
    """Local, detached background daemon powering always-on voice and conversational agent."""

    def __init__(self):
        self.pid_manager = PIDManager()
        self.state_machine = RuntimeStateMachine(initial_state=RuntimeState.STARTING)
        self.shutdown_handler = RuntimeShutdownHandler(
            state_machine=self.state_machine,
            pid_manager=self.pid_manager,
        )

        self.conversation_manager = ConversationManager()
        self.voice_manager = VoiceRuntimeManager(
            state_machine=self.state_machine,
            command_handler=self._handle_voice_command,
        )
        self.voice_manager.register_shutdown_callback(self.shutdown_handler.request_shutdown)
        self.shutdown_handler.register_cleanup_hook(self.voice_manager.stop)

    async def _handle_voice_command(self, text: str) -> str:
        """Route user voice command into conversation manager."""
        intent, reply = await self.conversation_manager.handle_user_utterance(text)
        return reply

    async def run(self) -> None:
        """Run the persistent local daemon until shutdown is requested."""
        logger.info("Initializing R.I.O. Local Persistent Voice Daemon...")
        self.pid_manager.write_pid(metadata={"status": "STANDBY", "mode": "local_voice"})
        await self.voice_manager.start()

        shutdown_flag = get_data_dir() / "runtime_shutdown.flag"

        try:
            while not self.shutdown_handler.is_shutting_down:
                # Check for shutdown trigger flag from CLI
                if shutdown_flag.exists():
                    logger.info("Detected shutdown flag file. Terminating daemon.")
                    self.shutdown_handler.request_shutdown("CLI stop command")
                    break

                # Sleep brief interval between background polls
                await asyncio.sleep(0.5)

        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Interrupt received in daemon loop.")
            self.shutdown_handler.request_shutdown("Process interrupted")

        finally:
            await self.shutdown_handler.execute_shutdown()
            if shutdown_flag.exists():
                try:
                    shutdown_flag.unlink()
                except Exception:
                    pass


def main():
    """Main daemon runner entry point."""
    parser = argparse.ArgumentParser(description="R.I.O. Background Runtime Daemon")
    parser.add_argument("--mode", default=os.getenv("RIO_DAEMON_MODE", "voice"), choices=["voice", "ws", "local"], help="Runtime mode: voice (local default) or ws (WebSocket)")
    parser.add_argument("--core-url", default=os.getenv("CORE_WS_URL", None), help="Target R.I.O. Core WebSocket URL (if in ws mode)")
    parser.add_argument("--no-tray", action="store_true", help="Disable system tray icon")
    args = parser.parse_args()

    setup_logging()
    logger.info("Starting R.I.O. Background Runtime Process...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # In voice or local mode (M5.x): Run local voice runtime without WebSocket
    if args.mode in ("voice", "local") and not args.core_url:
        daemon = LocalVoiceRuntimeDaemon()
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, daemon.shutdown_handler.request_shutdown)

        try:
            loop.run_until_complete(daemon.run())
        finally:
            loop.close()
    else:
        # Legacy WebSocket mode (M2/M2.5)
        core_url = args.core_url or "ws://localhost:8000/ws"
        supervisor = RuntimeSupervisor(
            core_ws_url=core_url,
            enable_tray=not args.no_tray,
        )
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, supervisor.request_shutdown)

        try:
            loop.run_until_complete(supervisor.run())
        except KeyboardInterrupt:
            supervisor.request_shutdown()
            loop.run_until_complete(asyncio.sleep(0.5))
        finally:
            loop.close()


if __name__ == "__main__":
    main()
