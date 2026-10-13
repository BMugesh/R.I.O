"""Local System Agent for R.I.O. (Milestone 5.x).

Provides real, physical host telemetry: time, date, hardware (CPU, RAM, GPU/CUDA, Disk, Battery),
processes, windows, and installed applications without requiring remote LLM calls.
"""

import datetime
import logging
import os
import platform
import socket
import sys
from typing import Any, Dict, List, Optional

import psutil

from agents.base import BaseAgent
from packages.schemas.agents import (
    Action,
    AgentManifest,
    AgentResult,
    AgentRiskLevel,
    AgentStatus,
    Evidence,
)
from packages.schemas.input import InputType, RIOInput
from services.gpu.cuda import get_gpu_info
from services.recovery.classifier import FailureClassifier

logger = logging.getLogger("rio.agents.system")


class LocalSystemAgent(BaseAgent):
    """Answers local system, time, date, hardware, and OS queries directly from physical host telemetry."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="local_system_agent",
            name="Local System Agent",
            description="Reads and reports real local computer telemetry: time, date, CPU, memory, GPU, VRAM, disk, battery, processes, and windows.",
            capabilities=[
                "system_time_read",
                "system_hardware_telemetry",
                "system_gpu_telemetry",
                "system_process_telemetry",
                "system_battery_telemetry",
                "system_storage_telemetry",
                "system_network_telemetry",
                "system_os_telemetry",
            ],
            accepted_input_types=[InputType.TEXT],
            output_types=["structured", "text"],
            required_tools=[
                "system.time.read",
                "system.date.read",
                "system.timezone.read",
                "system.cpu.read",
                "system.memory.read",
                "system.gpu.read",
                "system.vram.read",
                "system.gpu_temperature.read",
                "system.disk.read",
                "system.battery.read",
                "system.processes.read",
                "system.windows.read",
                "system.applications.read",
                "system.network.read",
                "system.os.read",
                "system.summary",
            ],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["local/deterministic"],
        )

    def _resolve_action_from_query(self, query: str) -> str:
        q = query.lower()
        if any(w in q for w in ("time", "clock", "what's the time")):
            return "system.time.read"
        elif any(w in q for w in ("date", "today", "day of week")):
            return "system.date.read"
        elif any(w in q for w in ("timezone", "time zone", "utc offset")):
            return "system.timezone.read"
        elif any(w in q for w in ("vram", "video memory", "gpu memory")):
            return "system.vram.read"
        elif any(w in q for w in ("gpu temp", "temperature", "overheating")):
            return "system.gpu_temperature.read"
        elif any(w in q for w in ("gpu", "graphics", "cuda", "nvidia", "rtx", "geforce")):
            return "system.gpu.read"
        elif any(w in q for w in ("ram", "memory", "memory usage")):
            return "system.memory.read"
        elif any(w in q for w in ("cpu", "processor", "cores", "cpu usage")):
            return "system.cpu.read"
        elif any(w in q for w in ("battery", "charging", "plugged in", "power")):
            return "system.battery.read"
        elif any(w in q for w in ("disk", "drive", "storage", "hard drive", "free space", "space left")):
            return "system.disk.read"
        elif any(w in q for w in ("process", "processes", "task manager", "running tasks")):
            return "system.processes.read"
        elif any(w in q for w in ("window", "windows", "open window", "active apps")):
            return "system.windows.read"
        elif any(w in q for w in ("installed app", "applications", "installed software")):
            return "system.applications.read"
        elif any(w in q for w in ("network", "ip address", "hostname", "interface")):
            return "system.network.read"
        elif any(w in q for w in ("os", "operating system", "windows version", "platform")):
            return "system.os.read"
        else:
            return "system.summary"

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        payload = input_data.payload or {}
        if not isinstance(payload, dict):
            raw_text = str(payload).strip()
            action_type = self._resolve_action_from_query(raw_text)
            payload = {"action": action_type, "query": raw_text}
        else:
            action_type = payload.get("action_type") or payload.get("action")
            if not action_type:
                query = payload.get("query", "")
                action_type = self._resolve_action_from_query(query) if query else "system.summary"

        # Normalize action alias
        normalized = action_type.lower().replace("_", ".")
        if normalized in ("time", "time.read"):
            action_type = "system.time.read"
        elif normalized in ("date", "date.read"):
            action_type = "system.date.read"
        elif normalized in ("timezone", "timezone.read"):
            action_type = "system.timezone.read"
        elif normalized in ("cpu", "cpu.read"):
            action_type = "system.cpu.read"
        elif normalized in ("memory", "ram", "memory.read"):
            action_type = "system.memory.read"
        elif normalized in ("gpu", "gpu.read"):
            action_type = "system.gpu.read"
        elif normalized in ("vram", "vram.read"):
            action_type = "system.vram.read"
        elif normalized in ("gpu.temperature", "gpu.temperature.read", "temperature"):
            action_type = "system.gpu_temperature.read"
        elif normalized in ("disk", "storage", "disk.read"):
            action_type = "system.disk.read"
        elif normalized in ("battery", "battery.read"):
            action_type = "system.battery.read"
        elif normalized in ("processes", "processes.read"):
            action_type = "system.processes.read"
        elif normalized in ("windows", "windows.read"):
            action_type = "system.windows.read"
        elif normalized in ("applications", "apps", "applications.read"):
            action_type = "system.applications.read"
        elif normalized in ("network", "network.read"):
            action_type = "system.network.read"
        elif normalized in ("os", "os.read"):
            action_type = "system.os.read"
        elif normalized in ("summary", "status"):
            action_type = "system.summary"

        try:
            now = datetime.datetime.now().astimezone()

            if action_type == "system.time.read":
                formatted_time = now.strftime("%I:%M:%S %p %Z").strip()
                data = {
                    "time_12h": now.strftime("%I:%M %p"),
                    "time_24h": now.strftime("%H:%M:%S"),
                    "iso": now.isoformat(),
                    "timezone": now.tzname(),
                    "timestamp": now.timestamp(),
                }
                msg = f"The current time is {now.strftime('%I:%M %p')} ({now.tzname()})."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.date.read":
                formatted_date = now.strftime("%A, %B %d, %Y")
                data = {
                    "date": now.strftime("%Y-%m-%d"),
                    "formatted": formatted_date,
                    "day_of_week": now.strftime("%A"),
                    "day": now.day,
                    "month": now.month,
                    "year": now.year,
                }
                msg = f"Today is {formatted_date}."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.timezone.read":
                data = {
                    "timezone": now.tzname(),
                    "utc_offset": now.strftime("%z"),
                }
                msg = f"System timezone is {now.tzname()} (UTC{now.strftime('%z')})."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.cpu.read":
                cpu_pct = psutil.cpu_percent(interval=0.1)
                logical_cores = psutil.cpu_count(logical=True)
                physical_cores = psutil.cpu_count(logical=False)
                freq = psutil.cpu_freq()
                data = {
                    "cpu_percent": cpu_pct,
                    "logical_cores": logical_cores,
                    "physical_cores": physical_cores,
                    "current_freq_mhz": freq.current if freq else None,
                }
                msg = f"CPU usage is {cpu_pct}% across {logical_cores} logical cores ({physical_cores} physical)."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.memory.read":
                vm = psutil.virtual_memory()
                total_gb = round(vm.total / (1024 ** 3), 2)
                used_gb = round(vm.used / (1024 ** 3), 2)
                avail_gb = round(vm.available / (1024 ** 3), 2)
                data = {
                    "total_bytes": vm.total,
                    "used_bytes": vm.used,
                    "available_bytes": vm.available,
                    "percent_used": vm.percent,
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "available_gb": avail_gb,
                }
                msg = f"RAM usage is {used_gb} GB / {total_gb} GB ({vm.percent}% used, {avail_gb} GB available)."
                return self._make_result(action_type, payload, data, msg)

            elif action_type in ("system.gpu.read", "system.vram.read", "system.gpu_temperature.read"):
                gpu_info = get_gpu_info()
                data = gpu_info.to_dict()
                if not gpu_info.available:
                    msg = "No dedicated NVIDIA GPU detected on this host."
                elif action_type == "system.vram.read":
                    msg = f"VRAM usage: {gpu_info.vram_used_mb} MB / {gpu_info.vram_total_mb} MB ({gpu_info.vram_free_mb} MB free)."
                elif action_type == "system.gpu_temperature.read":
                    temp_str = f"{gpu_info.temperature_c}°C" if gpu_info.temperature_c else "unknown"
                    msg = f"GPU temperature is {temp_str}."
                else:
                    msg = f"GPU is an {gpu_info.device} with {gpu_info.vram_total_mb} MB VRAM (Temp: {gpu_info.temperature_c}°C, Driver/CUDA: {gpu_info.cuda_version})."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.disk.read":
                system_drive = os.path.abspath(os.getenv("SystemDrive", "C:") + os.sep)
                usage = psutil.disk_usage(system_drive)
                total_gb = round(usage.total / (1024 ** 3), 2)
                used_gb = round(usage.used / (1024 ** 3), 2)
                free_gb = round(usage.free / (1024 ** 3), 2)
                data = {
                    "drive": system_drive,
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "percent_used": usage.percent,
                }
                msg = f"Drive {system_drive} has {free_gb} GB free out of {total_gb} GB ({usage.percent}% used)."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.battery.read":
                bat = psutil.sensors_battery()
                if bat is None:
                    data = {"has_battery": False, "percent": 100, "plugged": True}
                    msg = "No battery detected (Desktop or VM running on AC power)."
                else:
                    data = {
                        "has_battery": True,
                        "percent": bat.percent,
                        "plugged": bat.power_plugged,
                        "secs_left": bat.secsleft if bat.secsleft != psutil.POWER_TIME_UNLIMITED else None,
                    }
                    plugged_str = "plugged in to AC power" if bat.power_plugged else "running on battery power"
                    msg = f"Battery is at {bat.percent}% and {plugged_str}."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.processes.read":
                procs = []
                for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                    try:
                        procs.append(p.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                procs.sort(key=lambda x: (x.get("memory_percent") or 0), reverse=True)
                top_procs = procs[:5]
                data = {
                    "total_processes": len(procs),
                    "top_by_memory": top_procs,
                }
                msg = f"Found {len(procs)} active processes. Top memory: {', '.join([p['name'] for p in top_procs[:3]])}."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.windows.read":
                from runtime.app_controller import UniversalAppController
                windows = UniversalAppController.list_windows()
                data = {"windows": windows, "count": len(windows)}
                titles = [w.get("title", "") for w in windows if w.get("title")]
                msg = f"{len(windows)} visible windows open: {', '.join(titles[:4])}" if titles else "No visible windows open."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.applications.read":
                from runtime.app_catalog import AppCatalog
                apps = AppCatalog.get_all_apps()
                search_q = payload.get("app_name") or payload.get("query")
                if search_q:
                    matched = [a for a in apps if search_q.lower() in a.name.lower()]
                    data = {"matched_apps": [a.name for a in matched], "count": len(matched)}
                    msg = f"Found {len(matched)} installed apps matching '{search_q}'."
                else:
                    data = {"total_apps": len(apps), "sample": [a.name for a in apps[:10]]}
                    msg = f"{len(apps)} indexed desktop applications available."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.network.read":
                hostname = socket.gethostname()
                try:
                    ip = socket.gethostbyname(hostname)
                except Exception:
                    ip = "127.0.0.1"
                data = {
                    "hostname": hostname,
                    "primary_ip": ip,
                    "platform": platform.node(),
                }
                msg = f"Host '{hostname}' (IP: {ip})."
                return self._make_result(action_type, payload, data, msg)

            elif action_type == "system.os.read":
                data = {
                    "os": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "platform": platform.platform(),
                    "architecture": platform.machine(),
                    "python_version": sys.version.split()[0],
                }
                msg = f"Running {platform.platform()} ({platform.machine()}) on Python {data['python_version']}."
                return self._make_result(action_type, payload, data, msg)

            else:  # system.summary
                gpu_info = get_gpu_info()
                vm = psutil.virtual_memory()
                cpu_pct = psutil.cpu_percent(interval=0.05)
                data = {
                    "time": now.strftime("%I:%M %p"),
                    "date": now.strftime("%Y-%m-%d"),
                    "os": platform.platform(),
                    "cpu_percent": cpu_pct,
                    "cpu_cores": psutil.cpu_count(logical=True),
                    "ram_used_gb": round(vm.used / (1024 ** 3), 2),
                    "ram_total_gb": round(vm.total / (1024 ** 3), 2),
                    "ram_percent": vm.percent,
                    "gpu": gpu_info.device,
                    "gpu_vram_total_mb": gpu_info.vram_total_mb,
                    "gpu_temperature_c": gpu_info.temperature_c,
                }
                msg = (
                    f"System Status: CPU {cpu_pct}%, RAM {data['ram_used_gb']}/{data['ram_total_gb']} GB ({vm.percent}%), "
                    f"GPU: {gpu_info.device} ({gpu_info.vram_total_mb} MB). Time: {data['time']}."
                )
                return self._make_result(action_type, payload, data, msg)

        except Exception as ex:
            failure_class = FailureClassifier.classify(ex)
            logger.error(f"LocalSystemAgent error executing {action_type}: {ex}", exc_info=True)
            return AgentResult(
                status=AgentStatus.FAILED,
                message=f"System telemetry query failed: {str(ex)}",
                data={"error": str(ex), "failure_class": failure_class.name, "verified": False},
                actions=[Action(action_type=action_type, parameters=payload)],
                evidence=[Evidence(type="telemetry_error", source="local_system", data={"error": str(ex)}, confidence=1.0, verified=False)],
            )

    def _make_result(self, action_type: str, payload: Dict[str, Any], data: Dict[str, Any], message: str) -> AgentResult:
        data["message"] = message
        data["verified"] = True
        evidence = Evidence(
            type="system_telemetry",
            source="local_system",
            data=data,
            confidence=1.0,
            verified=True,
        )
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message=message,
            data=data,
            actions=[Action(action_type=action_type, parameters=payload)],
            evidence=[evidence],
        )
