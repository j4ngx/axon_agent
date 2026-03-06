"""Data models for Axon's persistent memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Message:
    """A single message in a conversation.

    Attributes:
        id: Firestore document ID (optional before saving).
        user_id: Telegram user ID that owns the conversation.
        role: Message role — ``user``, ``assistant``, ``system``, or ``tool``.
        content: The message text.
        timestamp: UTC timestamp of the message.
    """

    user_id: int
    role: str
    content: str
    id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for Firestore."""
        return {
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], doc_id: str) -> Message:
        """Create a Message from a Firestore document data."""
        return cls(
            id=doc_id,
            user_id=data.get("user_id", 0),
            role=data.get("role", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", datetime.now(UTC)),
        )
