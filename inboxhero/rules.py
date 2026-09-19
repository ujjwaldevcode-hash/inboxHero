from .models import Decision, Message
from .security import detect_threat

DISPOSITIONS = {'reply','archive','defer','delegate','escalate'}

def has(text,*phrases):
    return any(p.lower() in text.lower() for p in phrases)


def decide_message(m: Message) -> Decision | None:
    """Deterministic fast path. Returns None when semantic reasoning is useful."""
    text=f"{m.subject}\n{m.body}"
    threat=detect_threat(m)
    if threat:
        return Decision(m.id,'escalate','Untrusted embedded instruction or social-engineering request; refuse and surface for review.','high',[threat.category,'security'])
    if has(text,'wire $','updated remittance','new account below','password was changed','new sign-in','new login','root password changed'):
        return Decision(m.id,'escalate','Security or financial action requires human verification.','high',['security'])
    # Obvious no-action records are safe to classify without an LLM.
    if has(text,'no action needed','no further action needed','auto-renews','receipt','invoice paid','daily digest','weekly digest','monthly report','analytics','campaign report','statement is available','order has shipped','order is delivered','your verification code','payout of','uptime report'):
        return Decision(m.id,'archive','Routine notification or record with no immediate owner action required.','normal',['routine'])
    if has(text,'that fixed it','incident resolved','nothing pending on my side','work from home'):
        return Decision(m.id,'archive','Resolved or informational update with no remaining owner action.','normal',['resolved-or-fyi'])
    # Everything else is intentionally sent to the LLM for contextual reasoning.
    return None


def triage(messages):
    """Deterministic-only triage used by dashboard/digest; LLM-backed R1 is in agent.py."""
    out=[]
    for m in messages:
        d=decide_message(m)
        if d is None:
            d=Decision(m.id,'defer','Requires contextual reasoning before an automatic disposition.','medium',['llm-needed'])
        out.append(d)
    assert len(out)==len(messages) and len({d.message_id for d in out})==len(messages)
    assert all(d.disposition in DISPOSITIONS for d in out)
    return out
