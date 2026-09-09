"""R.I.O. Background Daemon Runner.

Main executable entrypoint for the R.I.O. Device Runtime.
Usage:
    python -m runtime.daemon [--core-url ws://localhost:8000/ws] [--no-tray]
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
import signal
import sys
from runtime.device_manager import get_rio_config_dir
from runtime.supervisor import RuntimeSupervisor


def setup_logging():
    """Configure robust file and stream logging for the daemon."""
    log_dir = get_rio_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "runtime.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    """Main daemon runner entry point."""
    parser = argparse.ArgumentParser(description="R.I.O. Background Runtime Daemon")
    parser.add_argument("--core-url", default=os.getenv("CORE_WS_URL", "ws://localhost:8000/ws"), help="Target R.I.O. Core WebSocket URL")
    parser.add_argument("--no-tray", action="store_true", help="Disable system tray icon")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("rio.runtime")
    logger.info("Initializing R.I.O. Background Runtime Process...")

    supervisor = RuntimeSupervisor(
        core_ws_url=args.core_url,
        enable_tray=not args.no_tray,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Attach signal handlers where supported
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, supervisor.request_shutdown)

    try:
        loop.run_until_complete(supervisor.run())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received.")
        supervisor.request_shutdown()
        loop.run_until_complete(asyncio.sleep(0.5))
    finally:
        loop.close()


if __name__ == "__main__":
    main()
