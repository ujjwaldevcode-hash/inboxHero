import json
from pathlib import Path
from inboxhero.loader import load_inbox
from inboxhero.dashboard import build_dashboard, write_dashboard

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_has_required_three_panes():
    data = build_dashboard(load_inbox(ROOT / "inbox.json"))
    assert set(data["panes"]) == {"pending_actions", "flagged", "commitments"}
    assert data["metadata"]["messages_processed"] == 100


def test_dashboard_surfaces_hostile_messages_and_conflict():
    data = build_dashboard(load_inbox(ROOT / "inbox.json"))
    flagged = {x["message_id"] for x in data["panes"]["flagged"]}
    assert {"m017", "m024", "m039", "m047"}.issubset(flagged)
    assert len(data["conflicts"]) == 1
    assert data["conflicts"][0]["messages"] == ["m010", "m061"]


def test_dashboard_writes_json_and_html(tmp_path):
    data = build_dashboard(load_inbox(ROOT / "inbox.json"))
    write_dashboard(tmp_path, data)
    assert (tmp_path / "dashboard.json").exists()
    assert (tmp_path / "dashboard.html").exists()
    saved = json.loads((tmp_path / "dashboard.json").read_text())
    assert saved["metadata"]["messages_processed"] == 100
    assert "pending_actions" in saved["panes"]
