import os
os.environ['INBOXHERO_OFFLINE'] = '1'

from inboxhero.loader import load_inbox
from inboxhero.agent import decide
from pathlib import Path


def test_rule_path_does_not_require_llm():
    messages = load_inbox(Path(__file__).parents[1] / 'inbox.json')
    m017 = next(m for m in messages if m.id == 'm017')
    disposition, reason, path = decide(m017, None)
    assert disposition == 'escalate'
    assert path == 'rule'


def test_all_hostile_messages_are_rule_covered_offline():
    messages = load_inbox(Path(__file__).parents[1] / 'inbox.json')
    ids = {'m017', 'm024', 'm039', 'm047'}
    covered = sum(decide(m, None)[2] == 'rule' for m in messages if m.id in ids)
    assert covered == 4
