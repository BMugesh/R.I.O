"""Unified One-Command Launcher for R.I.O. (Reasoning Intelligence Orchestration).

Starts:
1. R.I.O. Core Backend (FastAPI on 0.0.0.0:8000)
2. Local Desktop Agent (Device Controller)
3. Next.js Web Frontend (0.0.0.0:3000)

Usage:
    python start_rio.py
"""

import os
import signal
import socket
import subprocess
import sys
import time


def get_local_ip() -> str:
    """Detect local Wi-Fi / LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(root_dir, "apps", "web")
    local_ip = get_local_ip()

    print("=" * 60)
    print("⚡ Starting R.I.O. Operating System (All Services)")
    print("=" * 60)
    print(f"💻 Local Laptop URL:   http://localhost:3000")
    print(f"📱 Phone / Wi-Fi URL:  http://{local_ip}:3000")
    print(f"📚 API Docs (Swagger): http://localhost:8000/docs")
    print(f"🔌 WebSocket Hub:      ws://{local_ip}:8000/ws")
    print("=" * 60)
    print("Press CTRL+C at any time to cleanly stop all services.\n")

    processes = []

    try:
        # 1. Start FastAPI Backend
        print("🚀 [1/3] Launching R.I.O. Core API Gateway...")
        p_api = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=root_dir,
        )
        processes.append(p_api)
        time.sleep(2)

        # 2. Start Desktop Agent
        print("🖥️ [2/3] Launching Local Desktop Agent...")
        p_desktop = subprocess.Popen(
            [sys.executable, "-m", "apps.desktop_agent.agent"],
            cwd=root_dir,
        )
        processes.append(p_desktop)
        time.sleep(1)

        # 3. Start Next.js Frontend
        print("🌐 [3/3] Launching Next.js Web Frontend...")
        # Check node / npm
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        p_web = subprocess.Popen(
            [npm_cmd, "run", "dev", "--", "-H", "0.0.0.0", "-p", "3000"],
            cwd=web_dir,
        )
        processes.append(p_web)

        print("\n✅ All R.I.O. services are live!")
        print(f"👉 Open http://localhost:3000 on this PC")
        print(f"👉 Open http://{local_ip}:3000 on your phone\n")

        # Keep running and monitor processes
        while True:
            for p in processes:
                if p.poll() is not None:
                    # One process exited
                    pass
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down all R.I.O. services...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
        print("👋 All services stopped.")


if __name__ == "__main__":
    main()
