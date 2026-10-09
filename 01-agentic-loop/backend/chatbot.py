"""
The other half of the agentic-loop diagram: ask -> answer -> the system's job
is over. No loop, no action inside any system, no log of what happened
after the answer was given — a human has to read the reply, decide what it
means, and go do something about it, entirely outside the system that
answered.
"""
from __future__ import annotations

from typing import Optional


class ConversationalStub:
    def __init__(self, knowledge: Optional[dict[str, str]] = None):
        self.knowledge = knowledge or {}

    def ask(self, query: str) -> str:
        return self.knowledge.get(
            query,
            "I can help you with HR queries, IT support requests, and general "
            "company information. For inventory questions, please refer to the "
            "daily Inventory Position report or contact your Stores team.",
        )
