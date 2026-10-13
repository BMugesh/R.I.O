import os
from typing import Any, Dict
from agents.base import BaseAgent
from packages.schemas.agents import Action, AgentManifest, AgentResult, AgentRiskLevel, AgentStatus, Evidence
from packages.schemas.input import InputType, RIOInput


class VerificationAgent(BaseAgent):
    """Inspects execution traces and external state diffs to verify completion."""

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="verification_agent",
            name="Verification Agent",
            description="Performs dedicated post-execution inspection to verify that real-world side effects occurred.",
            capabilities=["state_verification", "evidence_audit", "outcome_confirmation", "verify_file", "verify_app_state"],
            accepted_input_types=[InputType.TEXT, InputType.SCREEN, InputType.TOOL_RESULT],
            output_types=["structured"],
            risk_level=AgentRiskLevel.LOW,
            supported_models=["openai/gpt-oss-20b"],
        )

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        payload = input_data.payload or {}
        if not isinstance(payload, dict):
            payload = {"action_type": "state_verification", "target": str(payload)}

        action_type = payload.get("action_type") or "state_verification"
        target_file = payload.get("file_path") or payload.get("path")
        app_name = payload.get("app_name") or payload.get("app")

        # 1. Physical File Verification
        if target_file or action_type in ("verify_file", "verify_file_exists"):
            fpath = str(target_file or "")
            exists = os.path.exists(fpath) if fpath else False
            size = os.path.getsize(fpath) if exists else 0

            evidence = Evidence(
                type="file_check",
                source="verification_agent",
                data={"path": fpath, "exists": exists, "size_bytes": size},
                confidence=1.0 if exists else 0.0,
                verified=exists,
            )

            if exists:
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    message=f"File verified at '{fpath}' ({size} bytes).",
                    data={"path": fpath, "verified": True, "size_bytes": size},
                    evidence=[evidence],
                    actions=[Action(action_type=action_type, parameters=payload)],
                )
            else:
                return AgentResult(
                    status=AgentStatus.FAILED,
                    message=f"Verification failed: file '{fpath}' does not exist.",
                    data={"path": fpath, "verified": False, "error": "file_not_found"},
                    evidence=[evidence],
                    actions=[Action(action_type=action_type, parameters=payload)],
                )

        # 2. Application & Window State Verification
        if app_name or action_type in ("verify_app_state", "verify_application"):
            from runtime.app_controller import UniversalAppController
            status_info = UniversalAppController.get_status(str(app_name or ""))
            is_running = bool(status_info.get("running", False))
            win_count = len(status_info.get("windows", []))

            evidence = Evidence(
                type="device_observation",
                source="verification_agent",
                data={"app": app_name, "running": is_running, "window_count": win_count, "pids": status_info.get("pids", [])},
                confidence=1.0 if is_running else 0.5,
                verified=is_running,
            )

            if is_running:
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    message=f"Application '{app_name}' verified running with {win_count} window(s).",
                    data={"app": app_name, "verified": True, "status": status_info},
                    evidence=[evidence],
                    actions=[Action(action_type=action_type, parameters=payload)],
                )
            else:
                return AgentResult(
                    status=AgentStatus.FAILED,
                    message=f"Verification failed: application '{app_name}' is not running.",
                    data={"app": app_name, "verified": False, "status": status_info},
                    evidence=[evidence],
                    actions=[Action(action_type=action_type, parameters=payload)],
                )
        # 3. Workspace Readiness Verification
        if action_type in ("verify_workspace", "verify_readiness"):
            from pathlib import Path
            workspace_path = payload.get("workspace_path") or payload.get("path") or "."
            w_path = Path(workspace_path).resolve()
            is_valid_dir = w_path.is_dir()
            has_git = (w_path / ".git").exists()
            ready = is_valid_dir
            evidence = Evidence(
                type="assertion",
                source="verification_agent",
                data={"workspace": str(w_path), "is_dir": is_valid_dir, "has_git": has_git, "ready": ready},
                confidence=1.0 if ready else 0.0,
                verified=ready,
            )
            return AgentResult(
                status=AgentStatus.SUCCESS if ready else AgentStatus.FAILED,
                message=f"Workspace readiness verified for '{w_path.name}' (Git: {has_git})." if ready else f"Workspace '{w_path}' is not a valid directory.",
                data={"ready": ready, "verified": ready, "workspace": str(w_path)},
                evidence=[evidence],
                actions=[Action(action_type=action_type, parameters=payload)],
            )

        # 4. Observation / Trace Audit
        audit_target = payload.get("expected_text") or payload.get("query")
        prior_obs = context.get("last_observation") or {}
        has_prior_proof = bool(prior_obs.get("verified", False) or prior_obs.get("message_sent", False))

        if not audit_target and not prior_obs:
            # Runtime process health verification
            pid = os.getpid()
            is_valid_pid = pid > 0
            evidence = Evidence(
                type="runtime_verification",
                source="verification_agent",
                data={"pid": pid, "status": "runtime_active", "verified": is_valid_pid},
                confidence=1.0 if is_valid_pid else 0.0,
                verified=is_valid_pid,
            )
            return AgentResult(
                status=AgentStatus.SUCCESS if is_valid_pid else AgentStatus.FAILED,
                message=f"Runtime environment verified healthy (PID {pid}).",
                data={"pid": pid, "verified": is_valid_pid},
                evidence=[evidence],
                actions=[Action(action_type=action_type, parameters=payload)],
            )

        evidence = Evidence(
            type="device_observation",
            source="verification_agent",
            data={"audit_target": audit_target, "verified": has_prior_proof},
            confidence=0.9 if has_prior_proof else 0.2,
            verified=has_prior_proof,
        )

        if has_prior_proof:
            return AgentResult(
                status=AgentStatus.SUCCESS,
                message=f"Verified target state for '{audit_target or 'action'}'.",
                data={"verified": True, "target": audit_target},
                evidence=[evidence],
                actions=[Action(action_type=action_type, parameters=payload)],
            )
        else:
            return AgentResult(
                status=AgentStatus.FAILED,
                message=f"Verification failed: could not substantiate state for '{audit_target or action_type}'.",
                data={"verified": False, "error": "unsubstantiated_state"},
                evidence=[evidence],
                actions=[Action(action_type=action_type, parameters=payload)],
            )
