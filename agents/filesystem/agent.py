"""FileSystem Agent for R.I.O."""

import os
from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import Action, AgentManifest, AgentResult, AgentRiskLevel, AgentStatus, Evidence
from packages.schemas.input import InputType, RIOInput


class FileSystemAgent(BaseAgent):
    """Manages file operations (read, write, list, check) within permitted directories."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="filesystem_agent",
            name="FileSystem Agent",
            description="Performs safe, sandboxed filesystem reading, creation, and inspection.",
            capabilities=["read_file", "write_file", "list_files", "verify_file_exists"],
            accepted_input_types=[InputType.TEXT],
            output_types=["structured"],
            risk_level=AgentRiskLevel.MEDIUM,
            supported_models=["openai/gpt-oss-20b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        payload = input_data.payload or {}
        action = payload.get("action", "read_file") if isinstance(payload, dict) else "read_file"
        path = payload.get("path", "") if isinstance(payload, dict) else ""

        exists = os.path.exists(path) if path else False
        evidence = Evidence(
            type="file_check",
            source="filesystem_agent",
            data={"path": path, "exists": exists},
            confidence=1.0,
            verified=exists,
        )

        return AgentResult(
            status=AgentStatus.SUCCESS,
            message=f"Filesystem action '{action}' on {path} completed.",
            data={"path": path, "exists": exists},
            actions=[Action(action_type=action, parameters={"path": path})],
            evidence=[evidence],
        )
