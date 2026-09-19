import json
from .gate import gate_action

def execute_proposal(root, proposal, *, dry_run=False, approved=False):
    result=gate_action(proposal,dry_run=dry_run,approved=approved)
    if result.executed and proposal.action=="send":
        out=root/"outbox"; out.mkdir(exist_ok=True)
        (out/f"{proposal.message_id}.json").write_text(json.dumps({"message_id":proposal.message_id,"action":"send","body":proposal.payload},indent=2)+"\n")
    return result
