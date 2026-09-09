"""Voice Capability & Permission Boundaries for R.I.O.

Enforces deny-by-default access to the device microphone.
Requires capability: microphone.read
"""

import logging
from typing import Optional
from runtime.permissions import Capability, PermissionManager

logger = logging.getLogger("rio.voice.permissions")


class VoicePermissionManager:
    """Manages explicit permission checks for audio capture and microphone hardware."""

    def __init__(self, permission_manager: Optional[PermissionManager] = None):
        self.permission_manager = permission_manager or PermissionManager()

    def has_microphone_permission(self) -> bool:
        """Check if microphone.read is granted in active permissions."""
        return self.permission_manager.is_permitted(Capability.MICROPHONE_READ)

    def require_microphone_permission(self) -> None:
        """Enforce microphone permission or raise explicit PermissionError."""
        if not self.has_microphone_permission():
            msg = (
                "Permission Denied: Voice interface requires 'microphone.read' capability. "
                "Enable it via CLI: 'rio runtime permissions allow microphone.read'"
            )
            logger.warning(msg)
            raise PermissionError(msg)

    def allow_microphone(self) -> None:
        """Grant microphone.read capability."""
        self.permission_manager.set_permission(Capability.MICROPHONE_READ, True)

    def deny_microphone(self) -> None:
        """Revoke microphone.read capability."""
        self.permission_manager.set_permission(Capability.MICROPHONE_READ, False)
