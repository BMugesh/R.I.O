"""Multi-Turn Conversation Context for R.I.O. (Milestone 5.x).

Tracks active entities, pronouns, and task targets across conversation turns
to resolve contextual follow-ups ("open it", "run the tests", "which one").
"""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class ConversationContext:
    """Carries conversation context across active voice dialogue turns."""
    session_id: str = field(default_factory=lambda: f"csess_{uuid.uuid4().hex[:8]}")
    active_entities: Dict[str, str] = field(default_factory=dict)
    last_action_target: Optional[str] = None
    last_action_type: Optional[str] = None
    last_topic: Optional[str] = None
    last_task_id: Optional[str] = None
    current_task: Optional[str] = None
    current_application: Optional[str] = None
    current_device: Optional[str] = None
    current_goal: Optional[str] = None
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)
    recent_observations: List[Dict[str, Any]] = field(default_factory=list)
    workspace_context: Dict[str, Any] = field(default_factory=dict)
    system_telemetry: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def set_entity(self, key: str, value: str) -> None:
        """Register an active context entity (e.g. 'app': 'Chrome', 'project': 'StockGenie')."""
        self.active_entities[key.lower()] = value
        self.updated_at = time.time()

    def get_entity(self, key: str) -> Optional[str]:
        return self.active_entities.get(key.lower())

    def record_action(self, action_type: str, target: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        self.last_action_type = action_type
        if target:
            self.last_action_target = target
            self.current_application = target
            self.set_entity("target", target)
            self.set_entity("it", target)
        action_record = {"action_type": action_type, "target": target, "timestamp": time.time(), "details": details or {}}
        self.recent_actions.append(action_record)
        if len(self.recent_actions) > 20:
            self.recent_actions = self.recent_actions[-20:]
        self.updated_at = time.time()

    def record_observation(self, observation: Dict[str, Any]) -> None:
        """Record an observed environment or verification state."""
        self.recent_observations.append({"observation": observation, "timestamp": time.time()})
        if len(self.recent_observations) > 20:
            self.recent_observations = self.recent_observations[-20:]
        self.updated_at = time.time()

    def set_workspace(self, workspace_path: str, git_branch: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        """Track current active project workspace and git branch."""
        self.workspace_context = {
            "path": workspace_path,
            "git_branch": git_branch,
            "details": details or {},
            "updated_at": time.time(),
        }
        self.set_entity("workspace", workspace_path)
        self.set_entity("project", workspace_path.split("/")[-1].split("\\")[-1])
        self.updated_at = time.time()

    def update_system_telemetry(self, telemetry: Dict[str, Any]) -> None:
        """Cache latest system telemetry state."""
        self.system_telemetry = telemetry
        self.updated_at = time.time()

    def record_topic(self, topic: str) -> None:
        self.last_topic = topic
        self.set_entity("topic", topic)
        self.updated_at = time.time()
