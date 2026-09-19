from dataclasses import dataclass
@dataclass(frozen=True)
class ActionProposal:
    action:str; message_id:str; reason:str; payload:str=""
@dataclass(frozen=True)
class GateResult:
    approved:bool; executed:bool; reason:str

def gate_action(p,dry_run=False,approved=False):
    if p.action not in {"send","delete"}: return GateResult(True,True,"reversible action")
    if dry_run: return GateResult(False,False,"blocked by dry-run")
    if not approved: return GateResult(False,False,"explicit approval required")
    return GateResult(True,True,"explicit approval granted")
