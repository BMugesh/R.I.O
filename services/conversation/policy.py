"""Conversation Policies and Limits for R.I.O. (Milestone 5.x)."""

from pydantic import BaseModel, Field


class ConversationPolicy(BaseModel):
    """Runtime limits and safety policies governing voice conversations."""
    inactivity_timeout_seconds: float = Field(
        default=0.0,
        description="Inactivity seconds before automatic standby. 0.0 disables timeout.",
    )
    max_history_turns: int = 20
    max_response_sentences: int = 4
    allow_destructive_without_confirmation: bool = False
