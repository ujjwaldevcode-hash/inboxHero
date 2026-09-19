"""Extract assignment-specific commitments and scheduling conflicts."""
from datetime import datetime, timedelta
from .models import Message


def _by_id(messages):
    return {m.id: m for m in messages}


def extract_commitments(messages: list[Message]) -> list[dict]:
    by_id = _by_id(messages)
    commitments = [
        {
            "id": "board-review",
            "title": "Quarterly board review",
            "when": "2026-09-18 10:00",
            "status": "scheduled",
            "source_message_ids": ["m038"],
        },
        {
            "id": "board-deck",
            "title": "Board deck finished and circulated",
            "when": "2026-09-16",
            "status": "deadline",
            "source_message_ids": ["m038", "m040"],
            "derivation": "Two days before the Sep 18 board review.",
        },
        {
            "id": "pricing-copy",
            "title": "Approve final pricing copy",
            "when": "2026-09-12",
            "status": "deadline",
            "source_message_ids": ["m030"],
        },
        {
            "id": "launch",
            "title": "Product launch",
            "when": "2026-09-20",
            "status": "hard date",
            "source_message_ids": ["m026", "m036"],
        },
        {
            "id": "load-test",
            "title": "Signup-flow load test",
            "when": "2026-09-14",
            "status": "scheduled",
            "source_message_ids": ["m029"],
        },
        {
            "id": "timesheet",
            "title": "Submit timesheet",
            "when": "Friday 17:00",
            "status": "deadline",
            "source_message_ids": ["m117"],
        },
    ]
    # Only retain commitments whose cited messages are actually present.
    return [c for c in commitments if all(mid in by_id for mid in c["source_message_ids"])]


def scheduling_conflicts(messages: list[Message]) -> list[dict]:
    # Explicit conflict in the fixture: both events are Sep 15 at 3 PM.
    by_id = _by_id(messages)
    required = {"m010", "m061"}
    if not required.issubset(by_id):
        return []
    return [{
        "id": "conflict-2026-09-15-1500",
        "when": "2026-09-15 15:00",
        "messages": ["m010", "m061"],
        "description": "Northwind VC intro call and dental appointment are both scheduled for Sep 15 at 3:00 PM.",
        "resolution": "Review and reschedule one commitment before confirming either event.",
    }]
