"""All 14 R.I.O. Modular Agents."""

from agents.base import BaseAgent
from agents.conversation.agent import ConversationAgent
from agents.planner.agent import PlannerAgent
from agents.research.agent import ResearchAgent
from agents.coding.agent import CodingAgent
from agents.browser.agent import BrowserAgent
from agents.computer.agent import ComputerAgent
from agents.vision.agent import VisionAgent
from agents.document.agent import DocumentAgent
from agents.filesystem.agent import FileSystemAgent
from agents.github.agent import GitHubAgent
from agents.device.agent import DeviceAgent
from agents.verification.agent import VerificationAgent
from agents.memory.agent import MemoryAgent
from agents.quantum.agent import QuantumAgent
from agents.system.agent import LocalSystemAgent

__all__ = [
    "BaseAgent",
    "ConversationAgent",
    "PlannerAgent",
    "ResearchAgent",
    "CodingAgent",
    "BrowserAgent",
    "ComputerAgent",
    "VisionAgent",
    "DocumentAgent",
    "FileSystemAgent",
    "GitHubAgent",
    "DeviceAgent",
    "VerificationAgent",
    "MemoryAgent",
    "QuantumAgent",
    "LocalSystemAgent",
]
