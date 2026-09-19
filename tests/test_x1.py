from pathlib import Path

from inboxhero.followups import find_followups
from inboxhero.loader import load_inbox


def test_x1_finds_unanswered_owner_message():
    items = find_followups(load_inbox(Path("inbox.json")), min_days=3)
    ids = [x["message_id"] for x in items]
    assert "m044" in ids


def test_x1_does_not_flag_answered_or_hostile_threads():
    items = find_followups(load_inbox(Path("inbox.json")), min_days=3)
    ids = [x["message_id"] for x in items]
    assert "m003" not in ids  # m005 is a later inbound reply.
    assert "m039" not in ids  # hostile self-message is not a follow-up.
