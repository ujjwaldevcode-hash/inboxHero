from inboxhero.retrieval import select_grounding_sources
from inboxhero.drafting import grounded_reply
from inboxhero.thread_summary import summarize_thread

class FakeClient:
    def json(self, system, user):
        if 'draft email replies' in system:
            return {'draft':'Here is the staging URL from the earlier message.','source_message_ids':['m003']}
        return {'summary':'Launch is targeted for Sep 20; pricing approval remains open.','open_question':'Can Sam approve the pricing copy by the 12th?','source_message_ids':['m026','m030','m036']}

def test_r2_retrieves_m003(messages):
    target=next(m for m in messages if m.id=='m008')
    assert 'm003' in [m.id for m in select_grounding_sources(messages,target)]

def test_r2_validates_grounding(messages):
    target=next(m for m in messages if m.id=='m008')
    draft,cited=grounded_reply(messages,target,FakeClient())
    assert draft and cited==['m003']

def test_x4_llm_summary_is_source_bounded(messages):
    r=summarize_thread(messages,'t-launch',FakeClient())
    assert r['open_question']
    assert set(r['source_message_ids']) <= {m.id for m in messages if m.thread_id=='t-launch'}
