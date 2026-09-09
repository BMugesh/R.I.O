"""R.I.O. Windows Startup and Background Daemon Registrar.

Configures automatic background startup on Windows user login via the user-level
Registry (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run) or Startup folder.
Requires zero administrator privileges and provides clean enable/disable/status management.
"""

import logging
import os
from pathlib import Path
import platform
import sys
from typing import Any, Dict

logger = logging.getLogger("rio.runtime.windows")

REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "RIORuntime"


def _get_pythonw_executable() -> str:
    """Find pythonw.exe (windowless python) to run without popping a console window."""
    current_python = Path(sys.executable)
    pythonw = current_python.parent / "pythonw.exe"
    if pythonw.is_file():
        return str(pythonw)
    return sys.executable


def _get_runtime_command() -> str:
    """Construct the command line to start the R.I.O. Runtime daemon."""
    py_exe = _get_pythonw_executable()
    return f'"{py_exe}" -m runtime.daemon'


def is_autostart_enabled() -> bool:
    """Check if R.I.O. Runtime is registered for Windows user startup."""
    if platform.system() != "Windows":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_READ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, APP_NAME)
                return bool(val)
            except FileNotFoundError:
                return False
    except Exception as e:
        logger.debug(f"Could not check registry autostart: {e}")
        return False


def enable_autostart() -> bool:
    """Register R.I.O. Runtime to launch on Windows user login."""
    if platform.system() != "Windows":
        logger.warning("Windows autostart is only available on Windows OS.")
        return False
    try:
        import winreg
        cmd = _get_runtime_command()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        logger.info(f"Windows autostart enabled: {cmd}")
        return True
    except Exception as e:
        logger.error(f"Failed to enable Windows autostart: {e}")
        return False


def disable_autostart() -> bool:
    """Remove R.I.O. Runtime from Windows user startup."""
    if platform.system() != "Windows":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, APP_NAME)
                logger.info("Windows autostart disabled.")
                return True
            except FileNotFoundError:
                return True  # Already disabled
    except Exception as e:
        logger.error(f"Failed to disable Windows autostart: {e}")
        return False


def get_autostart_status() -> Dict[str, Any]:
    """Return structured autostart configuration status."""
    is_enabled = is_autostart_enabled()
    return {
        "platform": platform.system(),
        "autostart_supported": platform.system() == "Windows",
        "enabled": is_enabled,
        "command": _get_runtime_command() if is_enabled else None,
    }
