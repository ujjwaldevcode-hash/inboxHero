#!/usr/bin/env python3
import argparse, json, time
from collections import Counter
from pathlib import Path
from config import BASE_DIR, INBOX_PATH, TRACE_PATH, OFFLINE_MODE, LLM_PROVIDER
from inboxhero.loader import load_inbox
from inboxhero.agent import decide
from inboxhero.rules import decide_message
from inboxhero.llm import LLMClient
from inboxhero.drafting import grounded_reply
from inboxhero.gate import ActionProposal
from inboxhero.actions import execute_proposal
from inboxhero.dashboard import build_dashboard, write_dashboard
from inboxhero.security import scan_inbox
from inboxhero.followups import find_followups
from inboxhero.digest import build_digest
from inboxhero.preferences import PreferenceStore
from inboxhero.scheduling import evaluate_meeting
from inboxhero.thread_summary import summarize_thread

ROOT = BASE_DIR

def trace(events):
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open('a', encoding='utf-8') as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')

def client_or_fail():
    if OFFLINE_MODE:
        raise RuntimeError('This capability requires the LLM. Set INBOXHERO_OFFLINE=0 and configure OPENAI_API_KEY.')
    return LLMClient()

def r1():
    ms = load_inbox(INBOX_PATH)
    client = None if OFFLINE_MODE else LLMClient()
    decisions = []
    rule_time = 0.0
    total_started = time.perf_counter()

    # Run deterministic rules first. These messages never reach the LLM.
    pending = []
    for m in ms:
        started = time.perf_counter()
        rule = decide_message(m)
        elapsed = time.perf_counter() - started
        if rule is not None:
            rule_time += elapsed
            item = {
                'message_id': m.id, 'disposition': rule.disposition, 'reason': rule.reason,
                'path': 'rule', 'latency_seconds': round(elapsed, 4),
                'provider': 'rules', 'model': None,
            }
            decisions.append(item)
            trace([{'event': 'decision', 'cap': 'R1', **item}])
        else:
            pending.append(m)

    if client is not None:
        for m in pending:
            started = time.perf_counter()
            disposition, reason, _ = decide(m, client)
            item = {
                'message_id': m.id, 'disposition': disposition, 'reason': reason,
                'path': 'llm', 'latency_seconds': round(time.perf_counter() - started, 4),
                'provider': client.provider, 'model': client.model,
            }
            decisions.append(item)
            trace([{'event': 'decision', 'cap': 'R1', **item}])
    elif pending:
        raise RuntimeError('LLM client required for contextual R1 messages.')

    # Restore inbox order for deterministic evidence files.
    order = {m.id: i for i, m in enumerate(ms)}
    decisions.sort(key=lambda d: order[d['message_id']])

    total_time = time.perf_counter() - total_started
    (ROOT / 'decisions.json').write_text(
        json.dumps(decisions, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    c = Counter(d['disposition'] for d in decisions)
    llm_count = sum(d['path'] == 'llm' for d in decisions)
    rule_count = sum(d['path'] == 'rule' for d in decisions)
    llm_time = client.total_latency if client is not None else 0.0

    print('R1 — Zero the inbox')
    print(f'messages processed: {len(ms)}')
    print(' '.join(f'{k}={c[k]}' for k in ['reply', 'archive', 'defer', 'delegate', 'escalate']))
    print(f'rule handled: {rule_count}')
    print(f'llm handled: {llm_count}')
    print('undecided: 0')
    print('')
    print('Performance')
    print('-------------------------')
    print(f'provider:             {client.provider if client is not None else "offline"}')
    print(f'model:                {client.model if client is not None else None}')
    print(f'total runtime:       {total_time:.2f} sec')
    print(f'rule processing:       {rule_time:.2f} sec')
    print(f'LLM processing:      {llm_time:.2f} sec')
    if client is not None and client.call_count:
        print(f'LLM requests:            {client.call_count}')
        print(f'average LLM latency:   {client.total_latency / client.call_count:.2f} sec')
        print(f'min LLM latency:       {client.min_latency:.2f} sec')
        print(f'max LLM latency:       {client.max_latency:.2f} sec')
    perf = {
        'messages_processed': len(ms), 'rule_handled': rule_count, 'llm_handled': llm_count,
        'total_runtime_seconds': round(total_time, 4),
        'rule_processing_seconds': round(rule_time, 4),
        'llm_processing_seconds': round(llm_time, 4),
        'llm_requests': client.call_count if client is not None else 0,
        'average_llm_latency_seconds': round(client.total_latency / client.call_count, 4) if client is not None and client.call_count else 0.0,
        'min_llm_latency_seconds': round(client.min_latency, 4) if client is not None and client.min_latency is not None else 0.0,
        'max_llm_latency_seconds': round(client.max_latency, 4) if client is not None and client.max_latency is not None else 0.0,
        'provider': client.provider if client is not None else 'offline',
        'model': client.model if client is not None else None,
    }
    trace([{'event': 'performance_summary', 'cap': 'R1', **perf}])
    (ROOT / 'performance.json').write_text(json.dumps(perf, indent=2) + '\n', encoding='utf-8')
    print('wrote: decisions.json, performance.json, trace.jsonl')

def r2(mid):
    ms=load_inbox(INBOX_PATH); target=next((m for m in ms if m.id==mid),None)
    if not target: raise SystemExit(f'Unknown message: {mid}')
    client=client_or_fail(); draft,ids=grounded_reply(ms,target,client)
    for m in ms:
        if m.id in ids:
            trace([{'event':'read','cap':'R2','message_id':m.id,'reason':'thread retrieval'}])
    trace([{'event':'grounded_reply','cap':'R2','message_id':mid,'source_message_ids':ids,'model':client.model,'draft_redacted':True}])
    print('R2 — Grounded reply'); print(f'target: {mid}'); print(f'sources used: {ids}'); print('draft:'); print(draft)

def r3(dry):
    props=[ActionProposal('send','m008','send grounded reply','Sure — here is the information from [m003].'),ActionProposal('delete','m072','remove routine notification')]
    for p in props:
        res=execute_proposal(ROOT,p,dry_run=dry,approved=False)
        print(p.action.upper(),p.message_id,res.reason)
        trace([{'event':'irreversible_gate','cap':'R3','message_id':p.message_id,'action':p.action,'gate_decision':'approved' if res.approved else 'blocked','outcome':'executed' if res.executed else 'not_executed','reason':res.reason}])

def r4():
    ms=load_inbox(INBOX_PATH); store=PreferenceStore(ROOT/'prefs.json')
    store.set('meeting',{'not_before':'11:00','source_message_id':'m041'})
    restarted=PreferenceStore(ROOT/'prefs.json'); target=next(m for m in ms if m.id=='m043')
    result=evaluate_meeting(target,restarted,ms)
    trace([{'event':'preference_applied','cap':'R4','message_id':'m043','preference_source':'m041',**result}])
    print('R4 — Persistent preference'); print('stored preference from: m041'); print('simulated process restart: yes'); print(f'request: m043 at {result["requested_time"]}'); print(f'status: {result["status"]}'); print(f'proposed alternative: {result["alternative"]} or later'); print(f'reason: {result["reason"]}')

def r5():
    ms=load_inbox(INBOX_PATH); ts=scan_inbox(ms); events=[]
    print('R5 — Hostile inbox'); print(f'messages scanned: {len(ms)}'); print(f'threats detected: {len(ts)}')
    for t in ts:
        print(f'{t.message_id}: {t.category} | attempted: {t.attempted_action} | REFUSED | FLAGGED')
        events.append({'event':'security_refusal','cap':'R5','message_id':t.message_id,'category':t.category,'attempted_action':t.attempted_action,'decision':'refused','flagged':True,'action_performed':False})
    trace(events)

def r6():
    ms=load_inbox(INBOX_PATH); data=build_dashboard(ms); write_dashboard(ROOT,data)
    trace([{'event':'dashboard_generated','cap':'R6','messages_processed':len(ms),'pending_count':data['metadata']['pending_count'],'flagged_count':data['metadata']['flagged_count'],'conflict_count':len(data['conflicts'])}])
    print('R6 — Run dashboard'); print(f'pending actions: {data["metadata"]["pending_count"]}'); print(f'flagged: {data["metadata"]["flagged_count"]}'); print(f'commitments: {len(data["panes"]["commitments"])}'); print(f'scheduling conflicts: {len(data["conflicts"])}'); print('wrote: dashboard.json, dashboard.html')

def x1():
    ms=load_inbox(INBOX_PATH); items=find_followups(ms,min_days=3)
    trace([{**item,'event':'followup_candidate','cap':'X1'} for item in items]); print('X1 — Follow-up tracker'); print(f'qualifying unanswered messages: {len(items)}')
    for item in items: print(json.dumps(item,ensure_ascii=False))

def x2():
    ms=load_inbox(INBOX_PATH); data=build_digest(ms); (ROOT/'digest.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    trace([{'event':'inbox_digest_generated','cap':'X2','messages_processed':data['metadata']['messages_processed'],'needs_attention_count':data['metadata']['needs_attention_count'],'can_wait_count':data['metadata']['can_wait_count'],'auto_archived_count':data['metadata']['auto_archived_count']}])
    print('X2 — Inbox digest'); print(f'Needs attention: {len(data["needs_attention"])}'); print(f'Can wait: {len(data["can_wait"])}'); print(f'Auto-archived: {len(data["auto_archived"])}'); print('wrote: digest.json')

def x3():
    ms=load_inbox(INBOX_PATH); store=PreferenceStore(ROOT/'prefs.json')
    if not store.get('meeting'): store.set('meeting',{'not_before':'11:00','source_message_id':'m041'})
    target=next(m for m in ms if m.id=='m043'); result=evaluate_meeting(target,store,ms)
    trace([{'event':'schedule_evaluation','cap':'X3',**result}]); print('X3 — Preference-aware scheduling'); print(json.dumps(result,indent=2,ensure_ascii=False))

def x4(thread_id):
    ms=load_inbox(INBOX_PATH); client=client_or_fail(); data=summarize_thread(ms,thread_id,client)
    trace([{'event':'thread_summary_generated','cap':'X4','thread_id':thread_id,'message_count':data['message_count'],'source_message_ids':data['source_message_ids'],'model':client.model}])
    print('X4 — Thread summary'); print(json.dumps(data,indent=2,ensure_ascii=False))

def main():
    p=argparse.ArgumentParser(); p.add_argument('--cap',choices=['R1','R2','R3','R4','R5','R6','X1','X2','X3','X4']); p.add_argument('--all',action='store_true'); p.add_argument('--msg',default='m008'); p.add_argument('--thread',default='t-launch'); p.add_argument('--dry-run',action='store_true'); a=p.parse_args()
    if not a.cap and not a.all: p.error('provide --cap or --all')
    if a.all:
        if TRACE_PATH.exists(): TRACE_PATH.unlink()
        for name,fn in [('R1',r1),('R2',lambda:r2(a.msg)),('R3',lambda:r3(True)),('R4',r4),('R5',r5),('R6',r6),('X1',x1),('X2',x2),('X3',x3),('X4',lambda:x4(a.thread))]:
            try: fn()
            except RuntimeError as e: print(f'{name}: {e}')
        return
    {'R1':r1,'R2':lambda:r2(a.msg),'R3':lambda:r3(a.dry_run),'R4':r4,'R5':r5,'R6':r6,'X1':x1,'X2':x2,'X3':x3,'X4':lambda:x4(a.thread)}[a.cap]()

if __name__=='__main__': main()
