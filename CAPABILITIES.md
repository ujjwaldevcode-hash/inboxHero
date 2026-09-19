# CAPABILITIES.md — inboxHero

**Name :** Ujjwal Perla

**Roll Number:** cert-aai-2026-06-0035

**Email:** ujjwal.perla@gmail.com

**Repository:** https://github.com/ujjwaldevcode-hash/inboxHero


## Commands

Run one capability at a time:

```bash
python demo.py --cap R1
python demo.py --cap R2 --msg m008
python demo.py --cap R3 --dry-run
python demo.py --cap R4
python demo.py --cap R5
python demo.py --cap R6
python demo.py --cap X1
python demo.py --cap X2
python demo.py --cap X3
python demo.py --cap X4 --thread t-launch
```

## System summary

inboxHero is a local Python agentic-system prototype with **no external agent framework**. It uses deterministic rules for obvious inbox cases and a locally hosted **Gemma 4 26B model through Ollama** for contextual triage, grounded drafting and thread summarisation. Retrieval uses the supplied inbox's `thread_id` structure, persistent scheduling preferences are stored in `prefs.json`, and irreversible actions are isolated behind a dry-run/approval gate. Email content is treated as untrusted data throughout the architecture rather than as executable instructions.

## System facts

| Field | Choice |
|---|---|
| Framework | `none` |
| Model | `gemma4:26b` via local Ollama for the recorded development run |
| Messages processed | 100 |
| Rule handled | 40 |
| LLM handled | 60 |
| Retrieval | `thread-walk` |
| Irreversible | `send`, `delete` |
| Reversible | `draft`, `label`, `archive`, `defer`, `delegate` |
| Gate | `both` — approval and dry-run |
| Preference demo | `m041`: no meetings before 11:00; affects `m043` |

## Disposition vocabulary

- **reply** — the message needs a response or response draft.
- **archive** — no active follow-up is needed.
- **defer** — retain for later because timing/context matters.
- **delegate** — route responsibility to another person.
- **escalate** — require human attention for ambiguity, risk, hostility or consequence.

## Required capabilities

### R1 — Zero the inbox — Tier B

**Claim:** Assigns every message exactly one disposition and a stated reason; deterministic rules handle obvious cases and the LLM handles remaining contextual cases.

**Command:** `python demo.py --cap R1`

**Observed evidence:** The recorded run processed 100 messages, with 40 handled by deterministic rules and 60 by the LLM, and reported `undecided: 0`. `decisions.json` contains one disposition/reason for every message, while `performance.json` records provider, model and timing information.

### R2 — Grounded reply — Tier B

**Claim:** Drafts a response grounded in earlier inbox messages and records the source message IDs used.

**Command:** `python demo.py --cap R2 --msg m008`

**Observed evidence:** `m008` is answered using the earlier source `m003`. The retrieval path checks the local mail store rather than inventing information, and the grounded-reply trace records the source ID.

### R3 — Gate irreversible actions — Tier C

**Claim:** Never executes send/delete in dry-run mode and requires explicit approval for an irreversible proposal.

**Command:** `python demo.py --cap R3 --dry-run`

**Observed evidence:** The run shows both SEND and DELETE proposals blocked by dry-run. The gate decision is written to `trace.jsonl`; no irreversible result is produced by the dry-run.

### R4 — Persistent preference — Tier C

**Claim:** Records a stated scheduling preference and applies it after a process restart.

**Command:** `python demo.py --cap R4`

**Observed evidence:** The system stores the preference from `m041`, creates a fresh preference store to simulate restart, and identifies `m043`'s 09:00 request as a conflict with the 11:00 minimum, proposing 11:00 or later.

### R5 — Refuse embedded instructions — Tier C

**Claim:** Detects hostile instructions inside untrusted messages, refuses them, flags them and reports the attempted action without executing it.

**Command:** `python demo.py --cap R5`

**Observed evidence:** Seven threats are reported and each is marked `REFUSED | FLAGGED`. The detected set includes prompt-injection, phishing and payment-fraud cases such as `m017`, `m024`, `m021`, `m045`, `m039`, `m023` and `m047`.

### R6 — Dashboard — Tier C

**Claim:** Generates exactly three panes for pending actions, flagged messages and commitments, with cited commitments and surfaced scheduling conflicts.

**Command:** `python demo.py --cap R6`

**Observed evidence:** The run writes `dashboard.json` and `dashboard.html` and reports 70 pending actions, 7 flagged messages, 6 commitments and 1 scheduling conflict. The commitments data includes source IDs and the dashboard surfaces the `m010`/`m061` same-time conflict.

## Custom capabilities

### X1 — Follow-up tracker — Tier B

**Claim:** Finds sent messages unanswered for at least three days and drafts a follow-up.

**Command:** `python demo.py --cap X1`

**Observed evidence:** The current run finds `m044` as the qualifying unanswered message, reports six days waiting, and produces a grounded follow-up draft without sending it.

### X2 — Inbox digest — Tier A

**Claim:** Produces a compact digest of what needs attention, what can wait and what was automatically archived.

**Command:** `python demo.py --cap X2`

**Observed evidence:** The current run reports Needs attention: 10, Can wait: 60, and Auto-archived: 30, and writes `digest.json`.

### X3 — Preference-aware scheduling — Tier C

**Claim:** Evaluates a meeting request against a persistent preference and existing commitments, proposing an alternative when needed.

**Command:** `python demo.py --cap X3`

**Observed evidence:** `m043` at 09:00 conflicts with the stored 11:00 preference and the system proposes 11:00. It also surfaces the Sep 15 15:00 conflict between `m010` and `m061` instead of silently selecting one.

### X4 — Thread summary — Tier B

**Claim:** Uses the configured LLM to summarize a multi-message thread and identify its current open question with supporting source IDs.

**Command:** `python demo.py --cap X4 --thread t-launch`

**Observed evidence:** The current run summarizes nine messages in `t-launch`, identifies the annual-discount pricing approval as the open question, and lists the supporting message IDs from the supplied inbox.

## Design justifications

### Framework choice

The framework choice is **none**. The assignment allows a framework or no framework, and this project benefits from explicit components because the important behavior is not complex multi-agent orchestration but routing, retrieval, persistent state and action safety. The code therefore makes the boundaries visible instead of hiding them inside framework abstractions.

### Model choice

The recorded development run uses **Gemma 4 26B through Ollama** locally. This avoids dependence on a remote API during development and gives predictable local execution. The provider/model are configured through environment variables loaded by `config.py`, so the model is not hard-coded into the application logic.

### Retrieval choice

The project uses **thread-walk retrieval**. Each message contains a `thread_id`, making it possible to retrieve earlier messages from the same thread without introducing a separate vector store. This is sufficient for the supplied fixture and provides explicit source IDs for auditability.

### Irreversible-action boundary

`send` and `delete` are classified as irreversible and are protected by `gate.py`. The LLM never receives a direct tool capable of performing either action; it can only produce a structured result/proposal. Dry-run and approval are both supported, and the mock send path writes to `outbox/` rather than contacting a real email service.

### Escalation line

The system deliberately escalates ambiguous, security-sensitive, financial, legal/consequential and hostile cases. This reduces the amount of work completed autonomously, but it prevents the system from guessing where the cost of being wrong is high. R5 is especially strict: an instruction contained in an email is treated as untrusted content and is not allowed to become an autonomous action.

## Final Report

### 1. What did you refuse to automate?

inboxHero refuses to execute instructions embedded in untrusted messages. `m024`, for example, attempts to override the assistant's instructions, forward the mailbox externally and hide the action; inboxHero refuses and flags it. The system also refuses high-consequence payment/security requests such as `m021` and `m023` without the required review. The trade-off is less automation in exchange for a safer boundary around consequential actions.

### 2. Where does untrusted text enter your system?

Untrusted text enters through `inbox.json` and is carried through the loader as message data. Security handling classifies risky content, the LLM can return structured results but has no send/delete tool, and `gate.py` is the only controlled path to an irreversible action. An attacker therefore cannot directly turn an instruction in an email into a tool call. They would have to defeat the untrusted-data boundary and the irreversible-action gate.

### 3. Who is accountable when it sends the wrong thing?

The owner remains accountable for an outgoing message that is explicitly approved because inboxHero is an assistant rather than an autonomous authority. `trace.jsonl` records the proposed action, gate decision and outcome, while grounded drafts record their source message IDs. This allows a reviewer to trace a bad result through the proposal, retrieval/model evidence and approval decision. The mock outbox also preserves the generated send artifact for inspection.

### 4. Name your own machinery.

`agent.py` plays the reasoning/triage role, the capability functions in `demo.py` act like tasks, and `demo.py` is the command router. `retrieval.py` provides retrieval, `preferences.py` provides persistent memory, and `gate.py` provides the human-in-the-loop safety boundary. A framework could have provided standardized agent/task routing and state orchestration, but explicit Python components are easier to inspect and test for this small local fixture.
