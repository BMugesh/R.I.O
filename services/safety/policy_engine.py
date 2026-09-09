"""Risk Classification and Policy Engine for R.I.O.

Classifies requested actions into risk tiers:
- LOW: Auto-execute (e.g. read files, search web, take screenshot, basic navigation)
- MEDIUM: Confirmation or auto-execute depending on user trust policy (e.g. send message, write file)
- HIGH: Mandatory confirmation (e.g. delete file, edit repository, change settings)
- CRITICAL: Strict explicit approval (e.g. financial transactions, system destruction, secret exposure)
"""

import re
from typing import Any, Dict, Optional
from packages.schemas.agents import AgentRiskLevel
from packages.schemas.safety import SafetyPolicy


class PolicyEngine:
    """Evaluates safety and risk levels for proposed actions."""

    # Explicit risk mappings
    ACTION_RISK_MAP = {
        "search_web": AgentRiskLevel.LOW,
        "screenshot": AgentRiskLevel.LOW,
        "get_device_status": AgentRiskLevel.LOW,
        "read_file": AgentRiskLevel.LOW,
        "open_application": AgentRiskLevel.LOW,
        "mouse_click": AgentRiskLevel.LOW,
        "mouse_move": AgentRiskLevel.LOW,
        "browser_navigate": AgentRiskLevel.LOW,
        "send_message": AgentRiskLevel.MEDIUM,
        "write_file": AgentRiskLevel.MEDIUM,
        "keyboard_type": AgentRiskLevel.MEDIUM,
        "create_github_issue": AgentRiskLevel.MEDIUM,
        "delete_file": AgentRiskLevel.HIGH,
        "kill_process": AgentRiskLevel.HIGH,
        "git_push": AgentRiskLevel.HIGH,
        "execute_shell_command": AgentRiskLevel.HIGH,
        "financial_transaction": AgentRiskLevel.CRITICAL,
        "credential_update": AgentRiskLevel.CRITICAL,
    }

    def __init__(self, policy: Optional[SafetyPolicy] = None):
        self.policy = policy or SafetyPolicy()

    def evaluate_action_risk(self, action_type: str, parameters: Optional[Dict[str, Any]] = None) -> AgentRiskLevel:
        """Determine risk level of an action."""
        params = parameters or {}

        # Check blocked destructive patterns
        command_str = str(params.get("command", "")).lower()
        for blocked in self.policy.blocked_commands:
            if blocked.lower() in command_str:
                return AgentRiskLevel.CRITICAL

        # Check delete or force flags
        if "delete" in action_type or params.get("force", False) is True:
            return AgentRiskLevel.HIGH

        return self.ACTION_RISK_MAP.get(action_type, AgentRiskLevel.MEDIUM)

    def requires_approval(self, risk_level: AgentRiskLevel) -> bool:
        """Check if risk level meets or exceeds the approval threshold."""
        hierarchy = {
            AgentRiskLevel.LOW: 1,
            AgentRiskLevel.MEDIUM: 2,
            AgentRiskLevel.HIGH: 3,
            AgentRiskLevel.CRITICAL: 4,
        }
        threshold_num = hierarchy.get(self.policy.require_approval_threshold, 3)
        current_num = hierarchy.get(risk_level, 1)
        return current_num >= threshold_num
