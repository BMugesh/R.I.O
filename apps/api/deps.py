"""Dependency Injection and Shared Services for R.I.O. API."""

from agents.browser.agent import BrowserAgent
from agents.coding.agent import CodingAgent
from agents.computer.agent import ComputerAgent
from agents.conversation.agent import ConversationAgent
from agents.device.agent import DeviceAgent
from agents.document.agent import DocumentAgent
from agents.filesystem.agent import FileSystemAgent
from agents.github.agent import GitHubAgent
from agents.memory.agent import MemoryAgent
from agents.planner.agent import PlannerAgent
from agents.quantum.agent import QuantumAgent
from agents.research.agent import ResearchAgent
from agents.verification.agent import VerificationAgent
from agents.vision.agent import VisionAgent
from services.device_registry.registry import DeviceRegistry
from services.device_router.router import DeviceRouter
from services.mcp.registry import MCPRegistry
from services.memory.memory_manager import MemoryManager
from services.model_router.router import ModelRouter
from services.orchestrator.orchestrator import RIOOrchestrator
from services.quantum.engine import QuantumEngine
from services.safety.approval_engine import ApprovalEngine
from services.safety.policy_engine import PolicyEngine
from services.tool_router.registry import ToolRegistry
from services.verification.engine import VerificationEngine


class Container:
    """Singleton Service Container."""

    def __init__(self):
        self.model_router = ModelRouter()
        self.memory_manager = MemoryManager()
        self.policy_engine = PolicyEngine()
        self.approval_engine = ApprovalEngine()
        self.verification_engine = VerificationEngine()
        self.device_registry = DeviceRegistry()
        self.device_router = DeviceRouter(registry=self.device_registry)
        self.tool_registry = ToolRegistry()
        self.mcp_registry = MCPRegistry(tool_registry=self.tool_registry)
        self.quantum_engine = QuantumEngine()

        # Orchestrator
        self.orchestrator = RIOOrchestrator(
            model_router=self.model_router,
            memory_manager=self.memory_manager,
            policy_engine=self.policy_engine,
            approval_engine=self.approval_engine,
            verification_engine=self.verification_engine,
            device_router=self.device_router,
        )


        # Register all 14 Agents
        self.agents = {
            "conversation_agent": ConversationAgent(model_router=self.model_router),
            "planner_agent": PlannerAgent(model_router=self.model_router),
            "research_agent": ResearchAgent(model_router=self.model_router),
            "coding_agent": CodingAgent(model_router=self.model_router),
            "browser_agent": BrowserAgent(model_router=self.model_router),
            "computer_agent": ComputerAgent(model_router=self.model_router),
            "vision_agent": VisionAgent(model_router=self.model_router),
            "document_agent": DocumentAgent(model_router=self.model_router),
            "filesystem_agent": FileSystemAgent(model_router=self.model_router),
            "github_agent": GitHubAgent(model_router=self.model_router),
            "device_agent": DeviceAgent(model_router=self.model_router),
            "verification_agent": VerificationAgent(model_router=self.model_router),
            "memory_agent": MemoryAgent(model_router=self.model_router),
            "quantum_agent": QuantumAgent(quantum_engine=self.quantum_engine, model_router=self.model_router),
        }

        for agent_id, agent_inst in self.agents.items():
            self.orchestrator.register_agent(agent_id, agent_inst)


# Global container instance
container = Container()


def get_container() -> Container:
    return container
