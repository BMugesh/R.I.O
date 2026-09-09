"""Base Agent Class for R.I.O.

All R.I.O. agents inherit from BaseAgent and implement the run() method,
declaring manifest metadata, risk levels, and capability requirements.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from packages.schemas.agents import AgentManifest, AgentResult
from packages.schemas.input import RIOInput
from services.model_router.router import ModelRouter


class BaseAgent(ABC):
    """Abstract Base Agent for R.I.O."""

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router or ModelRouter()

    @property
    @abstractmethod
    def manifest(self) -> AgentManifest:
        """Agent declaration manifest."""
        pass

    @abstractmethod
    async def run(self, input_data: RIOInput, context: Dict[str, Any]) -> AgentResult:
        """Execute agent reasoning and return structured AgentResult."""
        pass
