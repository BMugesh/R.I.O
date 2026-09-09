"""Evidence Collector for R.I.O. Verification Engine.

Collects multi-modal state evidence (DOM nodes, file hashes/stats, window titles, HTTP responses, visual diffs)
to substantiate whether an action actually succeeded in the real world.
"""

from datetime import datetime, timezone
import os
from typing import Any, Dict, Optional
from packages.schemas.agents import Evidence


class EvidenceCollector:
    """Collects and standardizes multi-modal execution evidence."""

    @staticmethod
    def collect_file_evidence(file_path: str) -> Evidence:
        """Verify that a file exists and capture its metadata."""
        exists = os.path.exists(file_path)
        size = os.path.getsize(file_path) if exists else 0
        return Evidence(
            type="file_check",
            source="local_filesystem",
            data={"path": file_path, "exists": exists, "size_bytes": size},
            confidence=1.0 if exists else 0.0,
            verified=exists,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def collect_api_evidence(status_code: int, response_body: Any) -> Evidence:
        """Verify API response status and content."""
        is_success = 200 <= status_code < 300
        return Evidence(
            type="api_status",
            source="http_client",
            data={"status_code": status_code, "body": response_body},
            confidence=1.0 if is_success else 0.0,
            verified=is_success,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def collect_dom_evidence(element_found: bool, selector: str, text: Optional[str] = None) -> Evidence:
        """Verify element existence in browser DOM."""
        return Evidence(
            type="dom_element",
            source="playwright_mcp",
            data={"selector": selector, "found": element_found, "matched_text": text},
            confidence=1.0 if element_found else 0.0,
            verified=element_found,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def collect_device_evidence(action: str, device_data: Dict[str, Any]) -> Evidence:
        """Verify device command observation (e.g. window opened, message in chat)."""
        is_verified = bool(device_data.get("verified", False) or device_data.get("success", False))
        return Evidence(
            type="device_observation",
            source="desktop_agent",
            data={"action": action, "observation": device_data},
            confidence=0.95 if is_verified else 0.1,
            verified=is_verified,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
