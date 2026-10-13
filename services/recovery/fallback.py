"""Fallback Strategies for R.I.O. (Milestone 5).

Provides deterministic fallback chains across Compute Targets, Models, and Tools
while respecting privacy policies, device boundaries, and safety constraints.
"""

import logging
from typing import Optional

logger = logging.getLogger("rio.recovery.fallback")


class FallbackManager:
    """Manages graceful degradation and alternative execution targets."""

    MODEL_FALLBACKS = {
        "openai/gpt-oss-120b": "openai/gpt-oss-20b",
        "groq/compound": "openai/gpt-oss-120b",
        "openai/gpt-oss-20b": "llama-3.1-8b-instant",
    }

    @staticmethod
    def get_compute_fallback(current_target: str, privacy: str = "remote_allowed") -> Optional[str]:
        """Compute target fallback: GPU -> CPU -> Remote (only if remote is allowed)."""
        curr = current_target.lower()
        if curr == "gpu":
            logger.info("Compute fallback triggered: GPU -> CPU")
            return "cpu"
        elif curr == "cpu":
            if privacy in ("remote_allowed", "preferred_remote"):
                logger.info("Compute fallback triggered: CPU -> Remote")
                return "remote"
            else:
                logger.warning(f"Remote compute fallback blocked due to privacy constraint: {privacy}")
                return None
        return None

    @classmethod
    def get_model_fallback(cls, current_model: str) -> Optional[str]:
        """Model fallback chain: Heavy -> Medium -> Lightweight."""
        fallback = cls.MODEL_FALLBACKS.get(current_model)
        if fallback:
            logger.info(f"Model fallback triggered: {current_model} -> {fallback}")
        return fallback

    @staticmethod
    def get_tool_fallback(action_type: str) -> Optional[str]:
        """Alternative tool strategy for failed action types."""
        clean_action = str(action_type).replace("_fallback", "")
        fallbacks = {
            "browser.navigate": "http.get",
            "device.launch_app": "system.open_process",
            "document.create_pdf": "document.create_markdown",
            "mouse_click": "application.control",
            "mouse.click": "application.control",
            "send_message": "keyboard.type",
            "open_application": "application.launch",
        }
        return fallbacks.get(clean_action)
