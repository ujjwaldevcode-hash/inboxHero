from pathlib import Path

from inboxhero.loader import load_inbox
from inboxhero.preferences import PreferenceStore
from inboxhero.scheduling import evaluate_meeting


def test_x3_rejects_m043_before_11am(tmp_path):
    messages = load_inbox(Path("inbox.json"))
    store = PreferenceStore(tmp_path / "prefs.json")
    store.set("meeting", {"not_before": "11:00", "source_message_id": "m041"})

    m043 = next(m for m in messages if m.id == "m043")
    result = evaluate_meeting(m043, store, messages)

    assert result["status"] == "preference_conflict"
    assert result["alternative"] == "11:00"
    assert result["preference"] == "11:00"


def test_x3_survives_a_process_restart(tmp_path):
    path = tmp_path / "prefs.json"
    first = PreferenceStore(path)
    first.set("meeting", {"not_before": "11:00", "source_message_id": "m041"})

    second = PreferenceStore(path)  # simulates a new process
    assert second.get("meeting")["not_before"] == "11:00"


def test_x3_surfaces_existing_calendar_conflict(tmp_path):
    messages = load_inbox(Path("inbox.json"))
    store = PreferenceStore(tmp_path / "prefs.json")
    m043 = next(m for m in messages if m.id == "m043")
    result = evaluate_meeting(m043, store, messages)

    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0]["messages"] == ["m010", "m061"]
