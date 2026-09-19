"""Preference- and commitment-aware scheduling helpers."""
from datetime import datetime
import re
from .models import Message
from .preferences import PreferenceStore
from .commitments import scheduling_conflicts


def extract_requested_time(message: Message) -> str | None:
    """Extract a simple 12-hour clock time such as 9:00am from an email."""
    match = re.search(r"\b(\d{1,2}):?(\d{2})?\s*(am|pm)\b", message.body, re.I)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    period = match.group(3).lower()
    if period == "pm" and hour != 12:
        hour += 12
    if period == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def evaluate_meeting(message: Message, store: PreferenceStore, messages: list[Message]) -> dict:
    prefs = store.load()
    min_time = prefs.get("meeting", {}).get("not_before")
    requested = extract_requested_time(message)

    result = {
        "message_id": message.id,
        "requested_time": requested,
        "preference": min_time,
        "status": "ok",
        "reason": "No stored meeting-time restriction applies.",
        "alternative": None,
        "conflicts": scheduling_conflicts(messages),
    }

    if min_time and requested and requested < min_time:
        result.update({
            "status": "preference_conflict",
            "reason": f"Requested {requested} is earlier than the stored preference of {min_time}.",
            "alternative": min_time,
        })

    return result
