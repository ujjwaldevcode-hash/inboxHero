import json
from pathlib import Path
from .models import Message

def load_inbox(path: Path) -> list[Message]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("messages", raw) if isinstance(raw, dict) else raw
    messages = []
    for x in items:
        messages.append(Message(
            id=x["id"], thread_id=x.get("thread_id", ""), sender=x.get("from", ""),
            recipients=x.get("to", []), subject=x.get("subject", ""),
            timestamp=x.get("timestamp", ""), body=x.get("body", ""),
            unread=x.get("unread", False)))
    if len({m.id for m in messages}) != len(messages):
        raise ValueError("Duplicate message IDs")
    return messages
