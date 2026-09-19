# inboxHero

**Name :** Ujjwal Perla

**Roll Number:** cert-aai-2026-06-0035

**Email:** ujjwal.perla@gmail.com

**Repository:** https://github.com/ujjwaldevcode-hash/inboxHero


inboxHero is a local Python prototype for Assignment 6. It takes the supplied 100-message inbox from unread to a fully classified state, using deterministic rules for obvious cases and a locally hosted LLM for contextual cases. It can draft grounded replies, gate irreversible actions, persist preferences, refuse hostile inbox instructions, generate a three-pane dashboard, and expose four additional capabilities.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The current development configuration uses **Ollama** locally with **Gemma 4 26B**. Ollama must be running on the machine before LLM-backed capabilities are used.

Example `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=gemma4:26b
OLLAMA_BASE_URL=http://localhost:11434
INBOXHERO_OFFLINE=0
```

Do not commit `.env`. The submission should contain `.env.example` only.

## Run

Run each capability independently:

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

`python demo.py --all` runs the capabilities in manifest order. R1, R2 and X4 require the configured LLM. The deterministic/offline test suite can be run with:

```bash
INBOXHERO_OFFLINE=1 pytest -q
```

## Architecture

```text
                         inbox.json
                             |
                             v
                         inbox loader
                             |
              +--------------+--------------+
              |                             |
       security / rules              contextual cases
              |                             |
              v                             v
     deterministic decision          local Ollama LLM
              |                             |
              +--------------+--------------+
                             |
                       structured result
                             |
              +--------------+--------------+
              |                             |
        retrieval / memory             action proposal
              |                             |
              v                             v
       grounded draft/summary          safety gate
                                            |
                              +-------------+-------------+
                              |                           |
                         approved send/delete        blocked/flagged
                              |                           |
                         outbox/ + trace.jsonl       trace.jsonl
```

There is intentionally **no external agent framework**. The assignment permits `framework: none`, so the project implements explicit Python components that are easy to inspect and test.

### Main components

- `loader.py` — loads and validates the supplied inbox.
- `rules.py` — deterministic routing for obvious routine and high-risk cases.
- `security.py` — detects hostile instructions, phishing and payment-fraud patterns.
- `agent.py` — contextual R1 classification through the configured LLM.
- `llm.py` — provider boundary for Ollama (and the existing optional Gemini compatibility path).
- `retrieval.py` — thread-based retrieval used for grounded work.
- `drafting.py` — grounded reply generation.
- `thread_summary.py` — long-thread summarisation and open-question extraction.
- `preferences.py` / `scheduling.py` — persistent preference and scheduling evaluation.
- `gate.py` / `actions.py` — irreversible-action proposal and execution boundary.
- `dashboard.py` — reproducible R6 JSON/HTML dashboard generation.

## Design choices

### Framework

**Framework: none.** The workload is a small local JSON inbox with a clear set of observable capabilities. A crew/graph framework would add orchestration overhead without improving the required safety boundaries. Keeping the machinery explicit makes the routing, retrieval, memory and action gate straightforward to inspect.

### Model and routing

The development baseline is **Gemma 4 26B through local Ollama**, configured with environment variables and loaded by `config.py`. R1 first applies deterministic rules; in the recorded full run, **40 of 100 messages were handled without an LLM call**, while 60 contextual messages reached the model. The current R1 implementation processes those contextual messages as individual LLM requests rather than batching them, and records per-request latency plus aggregate performance in `performance.json`.

Recorded R1 evidence from the current run:

- Messages processed: **100**
- Rule handled: **40**
- LLM handled: **60**
- Undecided: **0**
- Total runtime: **20.34 seconds**
- Average LLM latency: **0.34 seconds**
- Provider: **Ollama**
- Model: **gemma4:26b**

These values describe the latest Gemma 4 26B benchmark supplied for this project; performance can vary by machine and model state.

### Model selection

Four local Ollama models were compared during development: Qwen 3.8 (84.72 s), GPT-OSS 20B (134.57 s), Gemma 4 12B (43.88 s), and Gemma 4 26B (20.34 s) for the 100-message R1 run. Gemma 4 26B was selected as the final baseline because it produced the fastest observed run while maintaining conservative triage behavior, including 20 escalations and 0 undecided messages. The benchmark is machine-dependent and is presented as observed development evidence rather than a universal performance guarantee.

### Disposition vocabulary

Every message receives exactly one of:

- `reply` — a response should be drafted or considered for response.
- `archive` — no further action is required and the message can be removed from the active inbox view.
- `defer` — keep it for later because context or timing matters.
- `delegate` — route responsibility to another person.
- `escalate` — require human attention because the message is ambiguous, sensitive, hostile or otherwise high consequence.

### Retrieval

**Retrieval method: thread-walk.** The supplied inbox already contains `thread_id`, so earlier messages can be retrieved precisely from the local mail store. R2 demonstrates this with `m008`, whose grounded answer uses the earlier message `m003`. The system records the source message IDs used for grounded output.

### Reversible vs irreversible actions

The design treats `draft`, `label`, `archive`, `defer` and `delegate` as reversible workflow operations. `send` and `delete` are treated as irreversible in the mock system because a sent message cannot be unsent and deletion is intentionally protected as a consequential state change. R3 supports both **dry-run** and **approval** gating.

Sending is simulated only by writing one file per message under `outbox/`; no real email account is connected.

### Safety boundary

Email subjects and bodies are **untrusted data**, not instructions to the system. R5 identifies prompt-injection, phishing and payment-fraud attempts, refuses the requested action, flags the message and records the attempted action. The LLM does not receive a send/delete tool: it can only return structured results, and the action layer is the only component allowed to execute an irreversible proposal through the gate.

The system deliberately draws the escalation line around ambiguity, security-sensitive requests, financial requests, legal/consequential requests and hostile instructions. The trade-off is reduced automation for higher-consequence messages.

## Evidence files

- `decisions.json` — R1 decision for every supplied message.
- `performance.json` — R1 timing/provider/model evidence.
- `trace.jsonl` — event-level audit trail, including capability events and source IDs.
- `prefs.json` — persistent preference state.
- `dashboard.json` / `dashboard.html` — reproducible R6 dashboard.
- `digest.json` — X2 digest output.
- `outbox/` — mock send output when an approved send is executed; dry-run does not create the irreversible result.

## Dashboard

R6 produces exactly three panes required by the assignment:

1. **Pending actions** — proposed work that needs a human because it cannot be performed autonomously under the irreversible-action policy.
2. **Flagged** — hostile, phishing, ungrounded or otherwise refused messages, including what was attempted and what the system did instead.
3. **Commitments** — dates, deadlines and obligations extracted from the inbox, including source message IDs and surfaced scheduling conflicts.

The HTML dashboard is generated from the run data rather than hand-assembled. The current dashboard evidence reports **70 pending actions, 7 flagged messages, 6 commitments and 1 scheduling conflict**.

## Custom capabilities

- **X1 — Follow-up tracker (Tier B):** finds sent messages unanswered for at least three days and drafts a follow-up.
- **X2 — Inbox digest (Tier A):** separates the inbox into Needs attention, Can wait and Auto-archived.
- **X3 — Preference-aware scheduling (Tier C):** evaluates meeting requests against the persisted 11:00 preference and existing commitments.
- **X4 — Thread summary (Tier B):** summarizes the launch thread and identifies the current open question with source IDs.

## Final Report

### 1. What did you refuse to automate?

inboxHero refuses to execute instructions embedded in untrusted messages. For example, `m024` attempts to override the agent's instructions, forward the mailbox externally and hide the action; inboxHero refuses and flags it instead of treating the email body as an instruction. It also refuses high-consequence payment/security requests such as `m021` and `m023` without the required human review. The trade-off is less automation, but the system avoids silently taking consequential actions on behalf of the owner.

### 2. Where does untrusted text enter your system?

Untrusted text enters through `inbox.json` and is carried through the loader as message data. The architecture separates that data from executable actions: security/rule handling classifies risky content, the LLM can return only structured results, and `gate.py` is the controlled boundary for irreversible actions. The model therefore cannot directly turn an embedded email instruction into a send or delete operation. An attacker would have to defeat both the untrusted-content boundary and the irreversible-action gate to cause such an action.

### 3. Who is accountable when it sends the wrong thing?

The owner remains accountable for an outgoing message that is explicitly approved because inboxHero is an assistant rather than an autonomous authority. The system records the proposal, gate decision and outcome in `trace.jsonl`, while grounded drafts record their source message IDs. This allows a reviewer to trace a failure back through the proposed action, model output, retrieval evidence and human approval. The mock outbox also makes the exact generated send artifact inspectable.

### 4. Name your own machinery.

`agent.py` plays the reasoning/triage role, the capability functions in `demo.py` act like tasks, and `demo.py` provides the command router. `retrieval.py` provides the retrieval role, `preferences.py` provides persistent memory, and `gate.py` provides the human-in-the-loop safety boundary. A framework could have supplied standardized agent/task routing and state orchestration, but for this small local fixture explicit Python components make the safety boundaries and evidence easier to inspect and test.
