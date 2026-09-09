"""R.I.O. — Multi-Platform FRIDAY-Style Interactive CLI.

Usage:
    rio                          # Start interactive assistant shell
    rio "open chrome"            # Execute a single command
    rio --dev "what is react?"   # Execute with developer trace
"""

import argparse
import asyncio
import os
from pathlib import Path
import sys
import time
from typing import Optional

# Ensure repository root is on sys.path
_repo_root = str(Path(__file__).resolve().parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from rich.console import Console

from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

import httpx

console = Console()


def print_banner():
    """Print the official FRIDAY-style R.I.O. Banner."""
    banner_text = Text()
    banner_text.append("                 R.I.O.                 \n", style="bold cyan")
    banner_text.append("       Reasoning • Intelligence         \n", style="bold white")
    banner_text.append("             • Orchestration            ", style="bold cyan")

    panel = Panel(
        banner_text,
        border_style="cyan",
        expand=False,
        padding=(0, 2),
    )
    console.print(panel)
    console.print()


async def execute_via_api(
    prompt: str,
    api_url: str = "http://localhost:8000",
    developer_mode: bool = False,
    session_id: str = "cli_session",
) -> Optional[dict]:
    """Execute request via R.I.O. Core FastAPI gateway."""
    try:
        timeout_config = httpx.Timeout(timeout=60.0, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            payload = {
                "message": prompt,
                "sessionId": session_id,
                "developerMode": developer_mode,
            }
            res = await client.post(f"{api_url.rstrip('/')}/api/v1/chat", json=payload)
            if res.status_code == 200:
                return res.json()
            else:
                return {"reply": f"Server returned error HTTP {res.status_code}", "status": "failed"}
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException):
        return None  # Core API server offline -> trigger direct embedded core execution


async def execute_embedded(
    prompt: str,
    developer_mode: bool = False,
    session_id: str = "cli_session",
) -> dict:
    """Execute directly via embedded R.I.O. Core orchestrator if API server is not running."""
    from apps.api.deps import container
    from packages.schemas.chat import ChatRequest

    req = ChatRequest(
        message=prompt,
        sessionId=session_id,
        developerMode=developer_mode,
    )
    response = await container.orchestrator.process_chat(req)
    return {
        "reply": response.reply,
        "status": response.status,
        "developer_trace": response.developer_trace.model_dump() if response.developer_trace else None,
    }


async def process_prompt(
    prompt: str,
    api_url: str = "http://localhost:8000",
    developer_mode: bool = False,
    session_id: str = "cli_session",
):
    """Process a single user prompt with live feedback and output synthesis."""
    if not prompt.strip():
        return

    # Status spinner
    with console.status("[bold cyan]Understanding request & planning...[/bold cyan]", spinner="dots") as status:
        start_t = time.time()
        # 1. Attempt API Gateway
        res = await execute_via_api(prompt, api_url=api_url, developer_mode=developer_mode, session_id=session_id)
        if res is None:
            # 2. Fallback to Direct Embedded Core Engine
            status.update("[bold cyan]Executing via Embedded R.I.O. Core...[/bold cyan]")
            res = await execute_embedded(prompt, developer_mode=developer_mode, session_id=session_id)

        latency_ms = (time.time() - start_t) * 1000

    reply_text = res.get("reply", "")
    dev_trace = res.get("developer_trace") or res.get("developerTrace")

    # Render Assistant Response
    console.print()
    console.print("[bold cyan]RIO:[/bold cyan]")
    console.print(Markdown(reply_text))
    console.print()

    # If Developer Mode is active, render structured DAG Trace Table
    if developer_mode and dev_trace:
        table = Table(title="🛠️ Developer Execution Trace", border_style="dim cyan", show_header=True)
        table.add_column("Step", style="dim")
        table.add_column("Action / Goal", style="white")
        table.add_column("Agent", style="cyan")
        table.add_column("Risk", style="yellow")
        table.add_column("Status", style="green")

        steps = dev_trace.get("steps") or []
        for idx, s in enumerate(steps, 1):
            table.add_row(
                str(idx),
                s.get("name") or s.get("description", "Step"),
                s.get("agent_id", "orchestrator"),
                s.get("risk_level", "low"),
                s.get("status", "completed"),
            )

        console.print(table)
        console.print(f"[dim]Total Latency: {latency_ms:.1f}ms | Model: {dev_trace.get('model_id', 'Groq Auto')}[/dim]")
        console.print()


async def interactive_shell(api_url: str = "http://localhost:8000", developer_mode: bool = False):
    """Interactive Assistant REPL Loop."""
    print_banner()
    session_id = f"cli_{int(time.time())}"
    dev_mode = developer_mode

    console.print("[dim]Type your request or chat with R.I.O. Type 'exit' to quit, '/dev' to toggle debug trace.[/dim]\n")

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
            user_input_clean = user_input.strip()

            if not user_input_clean:
                continue

            if user_input_clean.lower() in ("exit", "quit", "q"):
                console.print("[cyan]Goodbye![/cyan]")
                break

            if user_input_clean.lower() == "clear":
                os.system("cls" if os.name == "nt" else "clear")
                print_banner()
                continue

            if user_input_clean.lower() == "/dev":
                dev_mode = not dev_mode
                console.print(f"[yellow]Developer Trace: {'ENABLED' if dev_mode else 'DISABLED'}[/yellow]\n")
                continue

            if user_input_clean.lower() in ("/help", "help"):
                console.print("[bold]R.I.O. Commands:[/bold]")
                console.print("  • Normal chat (e.g. 'What is React?')")
                console.print("  • Computer control (e.g. 'Open VS Code', 'Take a screenshot')")
                console.print("  • Web research (e.g. 'Search Google for latest tech news')")
                console.print("  • Quantum simulation (e.g. 'Solve max-cut with QAOA')")
                console.print("  • /dev - Toggle developer trace mode")
                console.print("  • exit / quit - Exit CLI\n")
                continue

            await process_prompt(
                prompt=user_input_clean,
                api_url=api_url,
                developer_mode=dev_mode,
                session_id=session_id,
            )

        except (KeyboardInterrupt, EOFError):
            console.print("\n[cyan]Session ended.[/cyan]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]\n")


def is_pid_running(pid: int) -> bool:
    """Check if process is active."""
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if h == 0:
                return False
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def handle_runtime_cli(args: list[str]):
    """Handle 'rio runtime ...' commands."""
    subcmd = args[0].lower() if args else "status"

    if subcmd == "status":
        from runtime.health import RuntimeHealth
        from runtime.device_manager import DeviceManager
        from runtime.permissions import PermissionManager
        from runtime.windows import is_autostart_enabled

        health_data = RuntimeHealth.read_persisted_health() or {}
        dev_mgr = DeviceManager()
        perm_mgr = PermissionManager()

        pid = health_data.get("pid")
        running = is_pid_running(pid) if pid else False

        status_style = "bold green" if running else "bold red"
        status_text = "ONLINE" if running else "OFFLINE"

        table = Table(title="🤖 R.I.O. Background Device Runtime", border_style="cyan", show_header=False)
        table.add_column("Field", style="bold cyan")
        table.add_column("Value", style="white")

        table.add_row("Status", Text(status_text, style=status_style))
        table.add_row("Process ID (PID)", str(pid or "None"))
        table.add_row("Device ID", dev_mgr.device_id)
        table.add_row("Device Name", dev_mgr.device_name)
        table.add_row("Platform", f"{health_data.get('platform', sys.platform)} (v1.0.0)")
        table.add_row("Core Target", health_data.get("core_url") or os.getenv("CORE_WS_URL", "ws://localhost:8000/ws"))
        table.add_row("Uptime", health_data.get("uptime", "0s") if running else "0s")
        table.add_row("Last Heartbeat", health_data.get("last_heartbeat", "None") if running else "None")
        table.add_row("Active Capabilities", f"{len(perm_mgr.get_active_capabilities())} enabled")
        table.add_row("Windows Autostart", "ENABLED" if is_autostart_enabled() else "DISABLED")

        console.print()
        console.print(table)
        console.print()

    elif subcmd == "start":
        from runtime.health import RuntimeHealth
        health_data = RuntimeHealth.read_persisted_health() or {}
        pid = health_data.get("pid")
        if pid and is_pid_running(pid):
            console.print(f"\n[yellow]R.I.O. Runtime is already running (PID: {pid}).[/yellow]\n")
            return

        import subprocess
        from runtime.windows import _get_pythonw_executable
        py_exe = _get_pythonw_executable()
        cmd = [py_exe, "-m", "runtime.daemon"]
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        console.print(f"\n[bold green]✓ R.I.O. Background Runtime started (PID: {p.pid}).[/bold green]")
        console.print("[dim]Run 'rio runtime status' to verify live connectivity.[/dim]\n")

    elif subcmd == "stop":
        from runtime.health import RuntimeHealth
        health_data = RuntimeHealth.read_persisted_health() or {}
        pid = health_data.get("pid")
        if not pid or not is_pid_running(pid):
            console.print("\n[yellow]R.I.O. Runtime is not currently running.[/yellow]\n")
            return

        try:
            if sys.platform == "win32":
                import ctypes
                PROCESS_TERMINATE = 1
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                if handle:
                    ctypes.windll.kernel32.TerminateProcess(handle, 0)
                    ctypes.windll.kernel32.CloseHandle(handle)
            else:
                import signal
                os.kill(pid, signal.SIGTERM)
            console.print(f"\n[bold red]🛑 Stopped R.I.O. Runtime (PID: {pid}).[/bold red]\n")
        except Exception as e:
            console.print(f"\n[red]Failed to stop runtime: {e}[/red]\n")

    elif subcmd == "restart":
        handle_runtime_cli(["stop"])
        time.sleep(1.0)
        handle_runtime_cli(["start"])

    elif subcmd == "autostart":
        from runtime.windows import enable_autostart, disable_autostart, get_autostart_status
        if len(args) > 1 and args[1].lower() in ("--enable", "enable", "on"):
            if enable_autostart():
                console.print("\n[bold green]✓ Windows user login autostart ENABLED.[/bold green]\n")
            else:
                console.print("\n[red]Failed to enable autostart.[/red]\n")
        elif len(args) > 1 and args[1].lower() in ("--disable", "disable", "off"):
            if disable_autostart():
                console.print("\n[bold yellow]✓ Windows autostart DISABLED.[/bold yellow]\n")
            else:
                console.print("\n[red]Failed to disable autostart.[/red]\n")
        else:
            status = get_autostart_status()
            console.print(f"\nWindows Autostart: [bold]{'ENABLED' if status['enabled'] else 'DISABLED'}[/bold]")
            console.print("[dim]Use 'rio runtime autostart --enable' or '--disable' to configure.[/dim]\n")

    elif subcmd == "permissions":
        from runtime.permissions import PermissionManager
        pm = PermissionManager()
        if len(args) >= 3 and args[1].lower() in ("--set", "set"):
            cap = args[2]
            val = args[3].lower() in ("true", "1", "yes", "enable") if len(args) > 3 else True
            pm.set_permission(cap, val)
            console.print(f"\n[bold green]Updated permission: {cap} -> {val}[/bold green]\n")
        else:
            table = Table(title="🔐 Capability Permissions", border_style="cyan", show_header=True)
            table.add_column("Capability", style="white")
            table.add_column("Status", style="bold")
            for cap, allowed in pm.get_all_permissions().items():
                style = "green" if allowed else "red"
                val_text = "ALLOWED" if allowed else "DENIED"
                table.add_row(cap, Text(val_text, style=style))
            console.print()
            console.print(table)
            console.print("[dim]Use 'rio runtime permissions --set <capability> true|false' to toggle.[/dim]\n")


def handle_voice_cli(args: list[str]):
    """Handle 'rio voice' subcommands."""
    subcmd = args[0].lower() if args else "status"

    if subcmd == "status":
        from voice.permissions import VoicePermissionManager
        vpm = VoicePermissionManager()
        has_mic = vpm.has_microphone_permission()
        console.print("\n[bold cyan]🎙️ R.I.O. Voice Subsystem Status[/bold cyan]")
        console.print(f"Microphone Capability (`microphone.read`): [{'green' if has_mic else 'red'}]{'ALLOWED' if has_mic else 'DENIED'}[/]")
        console.print(f"Wake Words: [white]RIO, Hey RIO, OK RIO, Hello RIO, FRIDAY[/white]")
        console.print(f"Transcription Engine: [white]Groq Whisper (whisper-large-v3-turbo)[/white]")
        console.print("[dim]Commands: 'rio voice trigger \"<speech_text>\"', 'rio runtime permissions set microphone.read true'[/dim]\n")

    elif subcmd == "trigger":
        if len(args) < 2:
            console.print("\n[yellow]Usage: rio voice trigger \"Hey RIO, open VS Code\"[/yellow]\n")
            return
        prompt_text = " ".join(args[1:])
        from voice.manager import VoiceManager
        vm = VoiceManager()
        console.print(f"\n[bold cyan]🎙️ Simulating Voice Input:[/bold cyan] [italic]\"{prompt_text}\"[/italic]")
        try:
            res = asyncio.run(vm.execute_voice_command_text(prompt_text))
            console.print(f"\n[bold green]R.I.O. Voice Response:[/bold green]\n{res.reply}\n")
        except PermissionError as pe:
            console.print(f"\n[bold red]❌ {pe}[/bold red]\n")
        except Exception as e:
            console.print(f"\n[bold red]❌ Voice execution failed: {e}[/bold red]\n")


def main():
    """Main CLI Entry Point."""
    raw_args = sys.argv[1:]
    dev_flag = False
    cleaned_args = []
    i = 0
    while i < len(raw_args):
        arg = raw_args[i]
        if arg in ("--dev", "-d"):
            dev_flag = True
        elif arg == "--" and i + 1 < len(raw_args) and raw_args[i + 1].lower() == "dev":
            dev_flag = True
            i += 1
        elif arg.lower() == "dev" and i == 0:
            dev_flag = True
        else:
            cleaned_args.append(arg)
        i += 1

    # Check for 'runtime' subcommand
    if cleaned_args and cleaned_args[0].lower() == "runtime":
        handle_runtime_cli(cleaned_args[1:])
        return

    # Check for 'voice' subcommand
    if cleaned_args and cleaned_args[0].lower() == "voice":
        handle_voice_cli(cleaned_args[1:])
        return

    parser = argparse.ArgumentParser(description="R.I.O. (Reasoning Intelligence Orchestration) CLI")
    parser.add_argument("prompt", nargs="*", help="Optional single-shot instruction for R.I.O.")
    parser.add_argument("--dev", "-d", action="store_true", help="Enable developer trace mode")
    parser.add_argument("--url", default=os.getenv("RIO_API_URL", "http://localhost:8000"), help="R.I.O. API Base URL")
    args = parser.parse_args(cleaned_args)

    dev_mode = dev_flag or args.dev
    if args.prompt:
        full_prompt = " ".join(args.prompt)
        asyncio.run(process_prompt(prompt=full_prompt, api_url=args.url, developer_mode=dev_mode))
    else:
        asyncio.run(interactive_shell(api_url=args.url, developer_mode=dev_mode))


if __name__ == "__main__":
    main()


