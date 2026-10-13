"""FileSystem Agent for R.I.O. (Milestone 5.x).

Performs real, evidence-based filesystem reading, writing, directory listing,
metadata hashing, and file lifecycle management with strict security boundaries.
"""

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from services.recovery.classifier import FailureClassifier

logger = logging.getLogger("rio.agents.filesystem")


class FileSystemAgent(BaseAgent):
    """Manages physical filesystem operations with cryptographic verification and safety guards."""

    # Sensitive / credential files that must NEVER be accessed or modified
    PROTECTED_PATTERNS = {
        ".env",
        ".env.local",
        ".env.production",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "id_dsa",
        "authorized_keys",
        "known_hosts",
        "secrets.json",
        "credentials.json",
        "master.key",
        "sam",
        "system",
        "security",
        "ntuser.dat",
    }

    PROTECTED_DIRS = {
        ".ssh",
        ".aws",
        ".gnupg",
        ".azure",
    }

    @property
    def manifest(self) -> AgentManifest:
        return AgentManifest(
            id="filesystem_agent",
            name="FileSystem Agent",
            description="Performs safe, sandboxed, evidence-verified filesystem reading, writing, directory listing, and inspection.",
            capabilities=[
                "read_file",
                "write_file",
                "list_files",
                "verify_file_exists",
                "get_metadata",
                "delete_file",
                "copy_file",
                "move_file",
                "make_dir",
            ],
            accepted_input_types=[InputType.TEXT],
            output_types=["structured", "text"],
            required_tools=[
                "filesystem.read_file",
                "filesystem.write_file",
                "filesystem.list_dir",
                "filesystem.get_metadata",
                "filesystem.delete_file",
                "filesystem.copy_file",
                "filesystem.move_file",
                "filesystem.make_dir",
            ],
            risk_level=AgentRiskLevel.MEDIUM,
            supported_models=["local/deterministic"],
        )

    def _is_protected_path(self, target_path: Path) -> bool:
        """Verify whether a path targets sensitive credentials or protected system keys."""
        name_lower = target_path.name.lower()
        if name_lower in self.PROTECTED_PATTERNS:
            return True
        for part in target_path.parts:
            if part.lower() in self.PROTECTED_DIRS:
                return True
        return False

    def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 digest of a physical file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        payload = input_data.payload or {}
        if not isinstance(payload, dict):
            # Generic text probe or test string
            payload = {"action": "list_dir", "path": "."}

        action = (
            payload.get("action_type")
            or payload.get("action")
            or "read_file"
        )
        # Normalize action aliases
        normalized_act = action.lower().replace(".", "_")
        if normalized_act in ("read_file", "filesystem_read_file", "read"):
            action = "filesystem.read_file"
        elif normalized_act in ("write_file", "filesystem_write_file", "write"):
            action = "filesystem.write_file"
        elif normalized_act in ("list_dir", "list_files", "filesystem_list_dir", "ls", "dir"):
            action = "filesystem.list_dir"
        elif normalized_act in ("get_metadata", "metadata", "file_info", "filesystem_get_metadata"):
            action = "filesystem.get_metadata"
        elif normalized_act in ("delete_file", "delete", "filesystem_delete_file", "rm"):
            action = "filesystem.delete_file"
        elif normalized_act in ("copy_file", "copy", "filesystem_copy_file", "cp"):
            action = "filesystem.copy_file"
        elif normalized_act in ("move_file", "move", "filesystem_move_file", "mv"):
            action = "filesystem.move_file"
        elif normalized_act in ("make_dir", "mkdir", "create_dir", "filesystem_make_dir"):
            action = "filesystem.make_dir"

        raw_path = payload.get("path") or payload.get("file_path") or "."
        target_path = Path(raw_path).resolve()

        # 1. Security boundary check
        if self._is_protected_path(target_path):
            err_msg = f"Security Policy Violation: Access to protected credential or system file '{target_path.name}' is prohibited."
            logger.warning(err_msg)
            return AgentResult(
                status=AgentStatus.FAILED,
                message=err_msg,
                data={"error": "security_policy_violation", "path": str(target_path), "verified": False},
                actions=[Action(action_type=action, parameters=payload)],
                evidence=[
                    Evidence(
                        type="security_violation",
                        source="filesystem",
                        data={"path": str(target_path), "violation": "protected_credential_path"},
                        confidence=1.0,
                        verified=False,
                    )
                ],
            )

        try:
            # -----------------------------------------------------------------
            # READ FILE
            # -----------------------------------------------------------------
            if action == "filesystem.read_file":
                if not target_path.exists():
                    return AgentResult(
                        status=AgentStatus.FAILED,
                        message=f"File not found: '{target_path}'",
                        data={"path": str(target_path), "exists": False, "verified": False},
                        actions=[Action(action_type=action, parameters=payload)],
                        evidence=[
                            Evidence(type="file_check", source="filesystem", data={"path": str(target_path), "exists": False}, confidence=1.0, verified=False)
                        ],
                    )

                if not target_path.is_file():
                    return AgentResult(
                        status=AgentStatus.FAILED,
                        message=f"Path is a directory, not a file: '{target_path}'",
                        data={"path": str(target_path), "is_dir": True, "verified": False},
                        actions=[Action(action_type=action, parameters=payload)],
                        evidence=[
                            Evidence(type="file_check", source="filesystem", data={"path": str(target_path), "is_dir": True}, confidence=1.0, verified=False)
                        ],
                    )

                max_bytes = payload.get("max_bytes", 500_000)
                file_size = target_path.stat().st_size
                with open(target_path, "r", encoding=payload.get("encoding", "utf-8"), errors="replace") as f:
                    content = f.read(max_bytes)

                sha256 = self._compute_sha256(target_path)
                data = {
                    "path": str(target_path),
                    "size_bytes": file_size,
                    "sha256": sha256,
                    "truncated": file_size > max_bytes,
                    "content": content,
                    "verified": True,
                }
                evidence = Evidence(
                    type="file_content",
                    source="filesystem",
                    data={"path": str(target_path), "size_bytes": file_size, "sha256": sha256},
                    confidence=1.0,
                    verified=True,
                )
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    message=f"Read {len(content)} characters from '{target_path.name}' ({file_size} bytes).",
                    data=data,
                    actions=[Action(action_type=action, parameters=payload)],
                    evidence=[evidence],
                )

            # -----------------------------------------------------------------
            # WRITE FILE (WITH IMMEDIATE VERIFICATION)
            # -----------------------------------------------------------------
            elif action == "filesystem.write_file":
                content = payload.get("content", "")
                mode = payload.get("mode", "w")  # "w" or "a"

                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, mode, encoding=payload.get("encoding", "utf-8")) as f:
                    f.write(content)

                # Real physical verification: check existence, size, and hash
                exists = target_path.exists()
                actual_size = target_path.stat().st_size if exists else 0
                sha256 = self._compute_sha256(target_path) if exists else None
                verified = exists and actual_size >= len(content.encode("utf-8"))

                data = {
                    "path": str(target_path),
                    "size_bytes": actual_size,
                    "sha256": sha256,
                    "mode": mode,
                    "verified": verified,
                }
                evidence = Evidence(
                    type="file_write_verified",
                    source="filesystem",
                    data=data,
                    confidence=1.0 if verified else 0.0,
                    verified=verified,
                )
                if verified:
                    return AgentResult(
                        status=AgentStatus.SUCCESS,
                        message=f"Wrote {len(content)} characters to '{target_path.name}' ({actual_size} bytes, SHA256: {sha256[:8] if sha256 else ''}...).",
                        data=data,
                        actions=[Action(action_type=action, parameters=payload)],
                        evidence=[evidence],
                    )
                else:
                    return AgentResult(
                        status=AgentStatus.FAILED,
                        message=f"File write failed to verify on disk for '{target_path.name}'.",
                        data=data,
                        actions=[Action(action_type=action, parameters=payload)],
                        evidence=[evidence],
                    )

            # -----------------------------------------------------------------
            # LIST DIRECTORY
            # -----------------------------------------------------------------
            elif action == "filesystem.list_dir":
                if not target_path.exists():
                    return AgentResult(
                        status=AgentStatus.FAILED,
                        message=f"Directory not found: '{target_path}'",
                        data={"path": str(target_path), "exists": False, "verified": False},
                        actions=[Action(action_type=action, parameters=payload)],
                        evidence=[Evidence(type="directory_check", source="filesystem", data={"path": str(target_path), "exists": False}, confidence=1.0, verified=False)],
                    )

                entries = []
                for entry in os.scandir(target_path):
                    try:
                        stat = entry.stat()
                        entries.append({
                            "name": entry.name,
                            "is_dir": entry.is_dir(),
                            "size_bytes": stat.st_size if not entry.is_dir() else None,
                            "mtime": stat.st_mtime,
                        })
                    except Exception:
                        pass

                data = {
                    "path": str(target_path),
                    "exists": True,
                    "count": len(entries),
                    "entries": entries,
                    "verified": True,
                }
                evidence = Evidence(
                    type="directory_listing",
                    source="filesystem",
                    data={"path": str(target_path), "count": len(entries)},
                    confidence=1.0,
                    verified=True,
                )
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    message=f"Listed {len(entries)} items in directory '{target_path.name or target_path}'.",
                    data=data,
                    actions=[Action(action_type=action, parameters=payload)],
                    evidence=[evidence],
                )

            # -----------------------------------------------------------------
            # METADATA & EXISTENCE
            # -----------------------------------------------------------------
            elif action == "filesystem.get_metadata":
                exists = target_path.exists()
                if not exists:
                    return AgentResult(
                        status=AgentStatus.FAILED,
                        message=f"Target does not exist: '{target_path}'",
                        data={"path": str(target_path), "exists": False, "verified": False},
                        actions=[Action(action_type=action, parameters=payload)],
                        evidence=[Evidence(type="file_metadata", source="filesystem", data={"path": str(target_path), "exists": False}, confidence=1.0, verified=False)],
                    )

                stat = target_path.stat()
                is_file = target_path.is_file()
                sha256 = self._compute_sha256(target_path) if is_file else None

                data = {
                    "path": str(target_path),
                    "exists": True,
                    "is_file": is_file,
                    "is_dir": target_path.is_dir(),
                    "size_bytes": stat.st_size,
                    "mtime": stat.st_mtime,
                    "ctime": stat.st_ctime,
                    "sha256": sha256,
                    "verified": True,
                }
                evidence = Evidence(
                    type="file_metadata",
                    source="filesystem",
                    data=data,
                    confidence=1.0,
                    verified=True,
                )
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    message=f"Metadata retrieved for '{target_path.name}' ({stat.st_size} bytes).",
                    data=data,
                    actions=[Action(action_type=action, parameters=payload)],
                    evidence=[evidence],
                )

            # -----------------------------------------------------------------
            # DELETE FILE (VERIFIED DELETION)
            # -----------------------------------------------------------------
            elif action == "filesystem.delete_file":
                if not target_path.exists():
                    return AgentResult(
                        status=AgentStatus.FAILED,
                        message=f"Cannot delete non-existent file: '{target_path}'",
                        data={"path": str(target_path), "exists": False, "verified": False},
                        actions=[Action(action_type=action, parameters=payload)],
                        evidence=[Evidence(type="file_deletion", source="filesystem", data={"path": str(target_path), "deleted": False}, confidence=1.0, verified=False)],
                    )

                if target_path.is_dir():
                    shutil.rmtree(target_path)
                else:
                    target_path.unlink()

                deleted = not target_path.exists()
                evidence = Evidence(
                    type="file_deletion",
                    source="filesystem",
                    data={"path": str(target_path), "deleted": deleted},
                    confidence=1.0 if deleted else 0.0,
                    verified=deleted,
                )
                return AgentResult(
                    status=AgentStatus.SUCCESS if deleted else AgentStatus.FAILED,
                    message=f"Deleted '{target_path.name}' successfully." if deleted else f"Failed to delete '{target_path.name}'.",
                    data={"path": str(target_path), "deleted": deleted, "verified": deleted},
                    actions=[Action(action_type=action, parameters=payload)],
                    evidence=[evidence],
                )

            # -----------------------------------------------------------------
            # COPY FILE
            # -----------------------------------------------------------------
            elif action == "filesystem.copy_file":
                dest_raw = payload.get("destination") or payload.get("dest")
                if not dest_raw:
                    raise ValueError("filesystem.copy_file requires 'destination'")
                dest_path = Path(dest_raw).resolve()

                if self._is_protected_path(dest_path):
                    raise PermissionError(f"Target destination '{dest_path.name}' is protected.")

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                if target_path.is_dir():
                    shutil.copytree(target_path, dest_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(target_path, dest_path)

                dest_exists = dest_path.exists()
                evidence = Evidence(
                    type="file_copy",
                    source="filesystem",
                    data={"source": str(target_path), "destination": str(dest_path), "copied": dest_exists},
                    confidence=1.0 if dest_exists else 0.0,
                    verified=dest_exists,
                )
                return AgentResult(
                    status=AgentStatus.SUCCESS if dest_exists else AgentStatus.FAILED,
                    message=f"Copied '{target_path.name}' to '{dest_path.name}'.",
                    data={"source": str(target_path), "destination": str(dest_path), "verified": dest_exists},
                    actions=[Action(action_type=action, parameters=payload)],
                    evidence=[evidence],
                )

            # -----------------------------------------------------------------
            # MOVE FILE
            # -----------------------------------------------------------------
            elif action == "filesystem.move_file":
                dest_raw = payload.get("destination") or payload.get("dest")
                if not dest_raw:
                    raise ValueError("filesystem.move_file requires 'destination'")
                dest_path = Path(dest_raw).resolve()

                if self._is_protected_path(dest_path):
                    raise PermissionError(f"Target destination '{dest_path.name}' is protected.")

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target_path), str(dest_path))

                moved = dest_path.exists() and not target_path.exists()
                evidence = Evidence(
                    type="file_move",
                    source="filesystem",
                    data={"source": str(target_path), "destination": str(dest_path), "moved": moved},
                    confidence=1.0 if moved else 0.0,
                    verified=moved,
                )
                return AgentResult(
                    status=AgentStatus.SUCCESS if moved else AgentStatus.FAILED,
                    message=f"Moved '{target_path.name}' to '{dest_path.name}'.",
                    data={"source": str(target_path), "destination": str(dest_path), "verified": moved},
                    actions=[Action(action_type=action, parameters=payload)],
                    evidence=[evidence],
                )

            # -----------------------------------------------------------------
            # MAKE DIRECTORY
            # -----------------------------------------------------------------
            elif action == "filesystem.make_dir":
                target_path.mkdir(parents=True, exist_ok=True)
                created = target_path.is_dir()
                evidence = Evidence(
                    type="directory_creation",
                    source="filesystem",
                    data={"path": str(target_path), "created": created},
                    confidence=1.0 if created else 0.0,
                    verified=created,
                )
                return AgentResult(
                    status=AgentStatus.SUCCESS if created else AgentStatus.FAILED,
                    message=f"Directory created at '{target_path}'.",
                    data={"path": str(target_path), "created": created, "verified": created},
                    actions=[Action(action_type=action, parameters=payload)],
                    evidence=[evidence],
                )

            else:
                return AgentResult(
                    status=AgentStatus.FAILED,
                    message=f"Unsupported filesystem action: '{action}'",
                    data={"action": action, "verified": False},
                    actions=[Action(action_type=action, parameters=payload)],
                    evidence=[Evidence(type="error", source="filesystem", data={"unsupported_action": action}, confidence=1.0, verified=False)],
                )

        except Exception as ex:
            failure_class = FailureClassifier.classify(ex)
            logger.error(f"FileSystemAgent error executing {action} on '{target_path}': {ex}", exc_info=True)
            return AgentResult(
                status=AgentStatus.FAILED,
                message=f"Filesystem action '{action}' failed: {str(ex)}",
                data={"error": str(ex), "failure_class": failure_class.name, "verified": False},
                actions=[Action(action_type=action, parameters=payload)],
                evidence=[Evidence(type="filesystem_error", source="filesystem", data={"error": str(ex), "failure_class": failure_class.name}, confidence=1.0, verified=False)],
            )

