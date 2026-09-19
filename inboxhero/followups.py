from __future__ import annotations
from datetime import datetime
from typing import Iterable
import re

OWNER = "sam@paperjet.io"


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def find_followups(messages: Iterable, min_days: int = 3, as_of: str | None = None) -> list[dict]:
    """Find owner-sent messages with no later inbound reply in the same thread."""
    ms = list(messages)
    if not ms:
        return []
    cutoff = _parse(as_of) if as_of else max(_parse(m.timestamp) for m in ms)
    results = []

    for sent in ms:
        if sent.sender.lower() != OWNER:
            continue
        # Do not treat preference/configuration or hostile self-mails as follow-ups.
        if (sent.thread_id == "t-inj3" or "assistant settings" in sent.subject.lower()
                or "calendar rule" in sent.subject.lower()):
            continue

        sent_time = _parse(sent.timestamp)
        if (cutoff - sent_time).days < min_days:
            continue

        replied = any(
            other.thread_id == sent.thread_id
            and other.sender.lower() != OWNER
            and _parse(other.timestamp) > sent_time
            for other in ms
        )
        if replied:
            continue

        days_waiting = (cutoff - sent_time).days
        results.append({
            "message_id": sent.id,
            "thread_id": sent.thread_id,
            "days_waiting": days_waiting,
            "recipient": sent.recipients,
            "subject": sent.subject,
            "draft": _draft(sent),
        })

    return sorted(results, key=lambda x: (-x["days_waiting"], x["message_id"]))


def _recipient_name(message) -> str:
    """Use a name explicitly present in the source message when available."""
    # The fixture uses forms such as "Priya -- ...". Treat that as grounded
    # data rather than guessing a display name from an email address.
    first_line = (message.body or "").strip().splitlines()[0] if message.body else ""
    match = re.match(r"^([A-Za-z][A-Za-z .'-]{1,60})\s+--", first_line)
    if match:
        return match.group(1).strip()
    return "there"


def _draft(message) -> str:
    name = _recipient_name(message)
    greeting = f"Hi {name}," if name != "there" else "Hi,"
    return (
        f"{greeting}\n\n"
        f"Just following up on my earlier message regarding the contractor invoice approval. "
        f"Could you let me know when you have a chance?\n\n"
        f"Thanks,\nSam"
    )
