from pathlib import Path
from inboxhero.loader import load_inbox
from inboxhero.security import detect_threat,scan_inbox
ROOT=Path(__file__).resolve().parents[1]

def test_four_assignment_injections_detected():
    ids={t.message_id for t in scan_inbox(load_inbox(ROOT/'inbox.json'))}
    assert {'m017','m024','m039','m047'} <= ids

def test_known_injections_are_prompt_injection():
    ms={m.id:m for m in load_inbox(ROOT/'inbox.json')}
    for mid in ['m017','m024','m039','m047']:
        t=detect_threat(ms[mid]); assert t and t.category=='prompt-injection'

def test_detector_only_returns_data():
    assert all(t.attempted_action for t in scan_inbox(load_inbox(ROOT/'inbox.json')))
