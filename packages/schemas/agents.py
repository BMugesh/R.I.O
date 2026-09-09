"""Agent Contract Schemas for R.I.O.

Defines the universal structure of Agent Manifests, Capabilities, Results,
Actions, and Evidence.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from packages.schemas.input import InputType


class AgentStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    NEEDS_APPROVAL = "needs_approval"
    PARTIAL = "partial"
    UNCERTAIN = "uncertain"


class AgentRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Action(BaseModel):
    """Action proposed or executed by an agent."""
    action_type: str  # e.g., 'open_app', 'click', 'send_message', 'run_tool'
    target: Optional[str] = None  # e.g., 'whatsapp', 'chrome', 'repo/issues'
    parameters: Dict[str, Any] = Field(default_factory=dict)
    risk_level: AgentRiskLevel = AgentRiskLevel.LOW
    description: str = ""


class Evidence(BaseModel):
    """Evidence supporting an agent's execution or verification."""
    type: str  # e.g., 'dom_element', 'file_exists', 'screenshot', 'api_status', 'text_match'
    source: str  # e.g., 'browser_dom', 'desktop_window', 'github_api', 'terminal_output'
    data: Any = None
    confidence: float = 1.0
    verified: bool = False
    timestamp: Optional[str] = None


class AgentResult(BaseModel):
    """Standardized result returned by any R.I.O. agent."""
    status: AgentStatus = AgentStatus.SUCCESS
    message: Optional[str] = None
    data: Optional[Any] = None
    actions: List[Action] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentManifest(BaseModel):
    """Declaration metadata for a R.I.O. Agent."""
    id: str
    name: str
    description: str
    capabilities: List[str] = Field(default_factory=list)
    accepted_input_types: List[InputType] = Field(default_factory=lambda: [InputType.TEXT])
    output_types: List[str] = Field(default_factory=lambda: ["text", "structured"])
    required_tools: List[str] = Field(default_factory=list)
    risk_level: AgentRiskLevel = AgentRiskLevel.LOW
    supported_models: List[str] = Field(default_factory=list)
    is_active: bool = True
