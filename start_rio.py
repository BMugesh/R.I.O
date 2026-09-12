"""Unified One-Command Launcher for R.I.O. (Reasoning Intelligence Orchestration).

Starts and supervises all R.I.O. operating system services in a single command:
1. R.I.O. Core Backend (FastAPI API Gateway + WebSockets + Registry + Orchestrator)
2. Laptop Background Runtime Daemon (OS automation + ComputerAgent + Validator)
3. Android Runtime Bridge Daemon (Mobile execution + App launch + Media + Sensors)
4. Next.js Web Frontend (Local + Mobile browser interface)

Usage:
    python start_rio.py              # Launch all services
    rio start                        # Launch via CLI
    rio start --cli                  # Launch services + interactive CLI shell
    python start_rio.py --no-web     # Headless mode (Core + Laptop + Android)
"""

import argparse
import asyncio
import os
from pathlib import Path
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
from typing import List, Optional, Tuple
import urllib.request

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    console = Console()
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False


def get_local_ip() -> str:
    """Detect local Wi-Fi / LAN IP address for phone pairing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check whether a local port is already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def wait_for_http(url: str, timeout: float = 15.0, interval: float = 0.5) -> bool:
    """Poll an HTTP endpoint until it returns 200 OK or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RIO-Supervisor"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(interval)
    return False


def kill_process_tree(proc: subprocess.Popen) -> None:
    """Gracefully terminate a process and all its children."""
    if proc.poll() is not None:
        return

    pid = proc.pid
    if platform.system() == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    else:
        try:
            proc.terminate()
            proc.wait(timeout=2.0)
        except (subprocess.TimeoutExpired, Exception):
            try:
                proc.kill()
            except Exception:
                pass


def print_banner(local_ip: str, api_port: int = 8000, web_port: int = 3000, web_enabled: bool = True) -> None:
    """Print official R.I.O. startup banner with endpoints."""
    if HAS_RICH and console:
        title = Text()
        title.append("                 R.I.O.                 \n", style="bold cyan")
        title.append("       Reasoning • Intelligence         \n", style="bold white")
        title.append("             • Orchestration            \n", style="bold cyan")
        title.append("  Personal AI Operating System (v0.2.1)  ", style="dim white")

        console.print(Panel(title, border_style="cyan", expand=False, padding=(0, 2)))

        table = Table(title="🌐 Active Service Endpoints", show_header=True, header_style="bold cyan", border_style="dim")
        table.add_column("Service", style="bold white", width=24)
        table.add_column("Endpoint / URL", style="cyan")

        if web_enabled:
            table.add_row("💻 Web UI (Workstation)", f"http://localhost:{web_port}")
            table.add_row("📱 Phone Web UI (Open in Browser)", f"http://{local_ip}:{web_port}")
        table.add_row("📚 Core API (Swagger Docs)", f"http://localhost:{api_port}/docs")
        table.add_row("🔌 WebSocket Hub (Daemon only)", f"ws://{local_ip}:{api_port}/ws")
        console.print(table)
        console.print("[dim]👉 [bold white]On your phone:[/bold white] Open [bold cyan]http://" + local_ip + f":{web_port}[/bold cyan] in Chrome / Safari.[/dim]")
        console.print("[dim]Press [bold red]Ctrl+C[/bold red] to cleanly shut down all services.[/dim]\n")
    else:
        print("=" * 65)
        print("⚡ R.I.O. (Reasoning Intelligence Orchestration) OS")
        print("=" * 65)
        if web_enabled:
            print(f"💻 Web UI (Workstation):            http://localhost:{web_port}")
            print(f"📱 Phone Web UI (Open in Browser):  http://{local_ip}:{web_port}")
        print(f"📚 Core API (Swagger Docs):          http://localhost:{api_port}/docs")
        print(f"🔌 WebSocket Hub (Daemon only):      ws://{local_ip}:{api_port}/ws")
        print("=" * 65)
        print(f"👉 On your phone: Open http://{local_ip}:{web_port} in your browser.")
        print("Press Ctrl+C at any time to cleanly stop all services.\n")


def log_step(step: str, desc: str, status: str = "...", style: str = "cyan") -> None:
    """Format and print a startup step."""
    if HAS_RICH and console:
        console.print(f"[{style}]{step}[/{style}] {desc} [dim]{status}[/dim]")
    else:
        print(f"{step} {desc} {status}")


def start_all_services(
    host: str = "0.0.0.0",
    api_port: int = 8000,
    web_port: int = 3000,
    enable_web: bool = True,
    enable_laptop: bool = True,
    enable_android: bool = True,
    interactive_cli: bool = False,
    developer_mode: bool = False,
) -> None:
    """Launch and supervise all R.I.O. services."""
    local_ip = get_local_ip()
    processes: List[Tuple[str, subprocess.Popen]] = []

    root_dir = str(REPO_ROOT)
    web_dir = os.path.join(root_dir, "apps", "web")

    print_banner(local_ip=local_ip, api_port=api_port, web_port=web_port, web_enabled=enable_web)

    # Check port conflicts for Core API
    if is_port_in_use(api_port):
        if HAS_RICH and console:
            console.print(f"[yellow]⚠️ Port {api_port} is already in use. Attempting to connect to existing Core...[/yellow]")
        else:
            print(f"⚠️ Port {api_port} is already in use. Attempting to connect to existing Core...")

    try:
        # -------------------------------------------------------------
        # 1. Start R.I.O. Core API Gateway
        # -------------------------------------------------------------
        if not is_port_in_use(api_port):
            log_step("🚀 [1/4]", "Launching R.I.O. Core Gateway (FastAPI + WebSockets)...", "Starting")
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            p_api = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", host, "--port", str(api_port)],
                cwd=root_dir,
                env=env,
            )
            processes.append(("Core Gateway", p_api))

            # Wait for Core Gateway healthcheck
            health_url = f"http://127.0.0.1:{api_port}/health"
            if wait_for_http(health_url, timeout=12.0):
                log_step("  └─", "Core Gateway is HEALTHY and listening on /ws", "✅ Online", "green")
            else:
                log_step("  └─", "Core Gateway started (healthcheck pending)", "⚠️ Readying", "yellow")
        else:
            log_step("🚀 [1/4]", f"Core Gateway already active on port {api_port}", "✅ Online", "green")

        # -------------------------------------------------------------
        # 2. Start Laptop Background Runtime Daemon
        # -------------------------------------------------------------
        if enable_laptop:
            log_step("💻 [2/4]", "Launching Laptop Runtime Daemon (ComputerAgent + OS Control)...", "Starting")
            env_laptop = os.environ.copy()
            env_laptop["PYTHONUNBUFFERED"] = "1"
            env_laptop["CORE_WS_URL"] = f"ws://127.0.0.1:{api_port}/ws"
            p_laptop = subprocess.Popen(
                [sys.executable, "-m", "runtime.daemon", "--no-tray", "--core-url", f"ws://127.0.0.1:{api_port}/ws"],
                cwd=root_dir,
                env=env_laptop,
            )
            processes.append(("Laptop Runtime", p_laptop))
            time.sleep(1.0)
            log_step("  └─", "Laptop Runtime registered and streaming heartbeats", "✅ Connected", "green")
        else:
            log_step("💻 [2/4]", "Laptop Runtime Daemon", "⏭️ Skipped", "dim")

        # -------------------------------------------------------------
        # 3. Start Android Runtime Bridge Daemon
        # -------------------------------------------------------------
        if enable_android:
            log_step("📱 [3/4]", "Launching Android Runtime Bridge Daemon...", "Starting")
            env_android = os.environ.copy()
            env_android["PYTHONUNBUFFERED"] = "1"
            env_android["CORE_WS_URL"] = f"ws://127.0.0.1:{api_port}/ws"
            p_android = subprocess.Popen(
                [sys.executable, "-m", "runtime.android.daemon"],
                cwd=root_dir,
                env=env_android,
            )
            processes.append(("Android Runtime", p_android))
            time.sleep(1.0)
            log_step("  └─", "Android Bridge connected and ready for mobile actions", "✅ Connected", "green")
        else:
            log_step("📱 [3/4]", "Android Runtime Bridge Daemon", "⏭️ Skipped", "dim")

        # -------------------------------------------------------------
        # 4. Start Next.js Web UI Frontend
        # -------------------------------------------------------------
        if enable_web:
            npm_cmd = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
            if npm_cmd and os.path.exists(web_dir):
                log_step("🌐 [4/4]", "Launching Next.js Web UI Frontend...", "Starting")
                p_web = subprocess.Popen(
                    [npm_cmd, "run", "dev", "--", "-H", host, "-p", str(web_port)],
                    cwd=web_dir,
                )
                processes.append(("Web Frontend", p_web))
                log_step("  └─", f"Web UI available at http://localhost:{web_port}", "✅ Live", "green")
            else:
                log_step("🌐 [4/4]", "Web UI (npm not found or apps/web missing)", "⚠️ Headless Only", "yellow")
        else:
            log_step("🌐 [4/4]", "Web UI Frontend", "⏭️ Skipped", "dim")

        if HAS_RICH and console:
            console.print("\n[bold green]✨ All R.I.O. systems operational and synchronized![/bold green]\n")
        else:
            print("\n✨ All R.I.O. systems operational and synchronized!\n")

        # -------------------------------------------------------------
        # 5. Interactive CLI or Background Supervisor Loop
        # -------------------------------------------------------------
        if interactive_cli:
            log_step("💬 [CLI]", "Launching Interactive R.I.O. Shell...", "Active", "cyan")
            from apps.cli.main import interactive_shell
            asyncio.run(interactive_shell(api_url=f"http://127.0.0.1:{api_port}", developer_mode=developer_mode))
        else:
            # Monitor all subprocesses
            while True:
                for name, proc in processes:
                    ret = proc.poll()
                    if ret is not None:
                        if HAS_RICH and console:
                            console.print(f"[bold yellow]⚠️ Process '{name}' exited with code {ret}.[/bold yellow]")
                        else:
                            print(f"⚠️ Process '{name}' exited with code {ret}.")
                time.sleep(1.0)

    except (KeyboardInterrupt, SystemExit):
        if HAS_RICH and console:
            console.print("\n[bold red]🛑 Initiating clean shutdown of all R.I.O. services...[/bold red]")
        else:
            print("\n🛑 Initiating clean shutdown of all R.I.O. services...")
    finally:
        for name, proc in processes:
            try:
                kill_process_tree(proc)
            except Exception:
                pass
        if HAS_RICH and console:
            console.print("[bold green]👋 All R.I.O. services stopped cleanly. Goodbye![/bold green]")
        else:
            print("👋 All R.I.O. services stopped cleanly. Goodbye!")


def main():
    """Main CLI entrypoint for unified launcher."""
    parser = argparse.ArgumentParser(
        description="Unified One-Command Launcher for R.I.O. (Reasoning Intelligence Orchestration)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind Core and Web UI")
    parser.add_argument("--port", "-p", type=int, default=8000, help="R.I.O. Core API port")
    parser.add_argument("--web-port", type=int, default=3000, help="Next.js Web UI port")
    parser.add_argument("--no-web", action="store_true", help="Do not start the Next.js web frontend")
    parser.add_argument("--no-laptop", action="store_true", help="Do not start the Laptop background runtime")
    parser.add_argument("--no-android", action="store_true", help="Do not start the Android bridge runtime")
    parser.add_argument("--cli", "-i", action="store_true", help="Launch interactive CLI shell alongside background services")
    parser.add_argument("--dev", "-d", action="store_true", help="Enable developer trace mode in CLI")

    args = parser.parse_args()

    start_all_services(
        host=args.host,
        api_port=args.port,
        web_port=args.web_port,
        enable_web=not args.no_web,
        enable_laptop=not args.no_laptop,
        enable_android=not args.no_android,
        interactive_cli=args.cli,
        developer_mode=args.dev,
    )


if __name__ == "__main__":
    main()
