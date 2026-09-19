from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class Message:
    id: str
    thread_id: str
    sender: str
    recipients: list[str]
    subject: str
    timestamp: str
    body: str
    unread: bool = False

@dataclass(frozen=True)
class Decision:
    message_id: str
    disposition: str
    reason: str
    risk: str = "normal"
    tags: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]:
        return {"message_id": self.message_id, "disposition": self.disposition,
                "reason": self.reason, "risk": self.risk, "tags": self.tags}
