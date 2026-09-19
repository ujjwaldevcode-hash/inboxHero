from pathlib import Path
from inboxhero.loader import load_inbox
from inboxhero.agent import decide

class FakeLLM:
    model='fake-test-model'
    def json(self, system, user):
        return {'disposition':'defer','reason':'Fake contextual reasoning for unit test.'}

def test_r1_covers_all_100_with_rule_and_llm_paths():
    messages=load_inbox(Path(__file__).parents[1]/'inbox.json')
    client=FakeLLM()
    results=[decide(m,client) for m in messages]
    assert len(results)==100
    assert all(r[0] in {'reply','archive','defer','delegate','escalate'} for r in results)
    assert all(r[1] for r in results)
    assert any(r[2]=='rule' for r in results)
    assert any(r[2]=='llm' for r in results)
