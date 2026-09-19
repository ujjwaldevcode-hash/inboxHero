from collections import Counter
from .rules import triage
from .security import scan_inbox


def build_digest(messages):
    decisions = triage(messages)
    by_id = {m.id: m for m in messages}
    flagged = {t.message_id for t in scan_inbox(messages)}

    attention = []
    wait = []
    archived = []

    for d in decisions:
        item = {
            "message_id": d.message_id,
            "subject": by_id[d.message_id].subject,
            "disposition": d.disposition,
            "reason": d.reason,
        }
        if d.message_id in flagged or d.disposition in {"escalate", "reply", "delegate"}:
            attention.append(item)
        elif d.disposition == "archive":
            archived.append(item)
        else:
            wait.append(item)

    counts = Counter(d.disposition for d in decisions)
    return {
        "needs_attention": attention,
        "can_wait": wait,
        "auto_archived": archived,
        "metadata": {
            "messages_processed": len(messages),
            "needs_attention_count": len(attention),
            "can_wait_count": len(wait),
            "auto_archived_count": len(archived),
            "dispositions": dict(counts),
            "flagged_count": len(flagged),
        },
    }
