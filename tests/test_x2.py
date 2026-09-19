import json
from pathlib import Path
from inboxhero.loader import load_inbox
from inboxhero.digest import build_digest


def test_digest_covers_every_message():
    messages = load_inbox(Path("inbox.json"))
    data = build_digest(messages)
    total = sum(len(data[k]) for k in ("needs_attention", "can_wait", "auto_archived"))
    assert total == len(messages)
    ids = [x["message_id"] for k in ("needs_attention", "can_wait", "auto_archived") for x in data[k]]
    assert len(ids) == len(set(ids))


def test_digest_has_required_three_sections():
    messages = load_inbox(Path("inbox.json"))
    data = build_digest(messages)
    assert set(("needs_attention", "can_wait", "auto_archived")) <= data.keys()


def test_digest_surfaces_hostile_messages():
    messages = load_inbox(Path("inbox.json"))
    data = build_digest(messages)
    attention_ids = {x["message_id"] for x in data["needs_attention"]}
    assert {"m017", "m024", "m039", "m047"}.issubset(attention_ids)
