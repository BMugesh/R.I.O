"""Python Protocols for R.I.O. Subsystem Interfaces."""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from packages.schemas.agents import AgentManifest, AgentResult
from packages.schemas.input import RIOInput
from packages.schemas.tasks import TaskStep, VerificationStrategy
from packages.schemas.tools import ToolCall, ToolDefinition, ToolResult
from packages.schemas.memory import MemoryItem, MemoryQuery
from packages.schemas.devices import Device, DeviceCommand, DeviceObservation
from packages.schemas.quantum import QuantumJob, QuantumResult
from packages.schemas.safety import ApprovalRequest, ApprovalStatus


@runtime_checkable
class AgentProtocol(Protocol):
    """Contract for any R.I.O. Agent."""
    manifest: AgentManifest

    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        ...


@runtime_checkable
class ModelProviderProtocol(Protocol):
    """Contract for AI model providers (Groq, OpenAI, Anthropic, Gemini, Mock)."""
    provider_name: str

    async def generate(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ...

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        model: str = "whisper-large-v3-turbo",
        language: Optional[str] = "en",
    ) -> str:
        ...


@runtime_checkable
class ToolProtocol(Protocol):
    """Contract for an executable tool."""
    definition: ToolDefinition

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        ...


@runtime_checkable
class MemoryProtocol(Protocol):
    """Contract for memory storage and semantic retrieval."""
    async def store(self, item: MemoryItem) -> str:
        ...

    async def search(self, query: MemoryQuery) -> List[MemoryItem]:
        ...

    async def delete(self, memory_id: str) -> bool:
        ...

    async def forget_by_topic(self, user_id: str, topic: str) -> int:
        ...


@runtime_checkable
class VerificationProtocol(Protocol):
    """Contract for the Verification Engine."""
    async def verify_step(self, step: TaskStep, observation: Dict[str, Any]) -> bool:
        ...


@runtime_checkable
class SafetyProtocol(Protocol):
    """Contract for Safety & Approval Engine."""
    async def evaluate_risk(self, action_type: str, parameters: Dict[str, Any]) -> ApprovalRequest:
        ...

    async def check_approval(self, request_id: str) -> ApprovalStatus:
        ...


@runtime_checkable
class DeviceAdapterProtocol(Protocol):
    """Contract for Device Adapters (Desktop, Android)."""
    async def send_command(self, command: DeviceCommand) -> DeviceObservation:
        ...

    async def get_device_status(self, device_id: str) -> Device:
        ...


@runtime_checkable
class QuantumProviderProtocol(Protocol):
    """Contract for Quantum Computation Engine."""
    async def execute_job(self, job: QuantumJob) -> QuantumResult:
        ...
