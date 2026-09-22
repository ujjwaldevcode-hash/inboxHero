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

inboxHero is a local Python agentic-system prototype with **no external agent framework**. It uses deterministic rules for obvious inbox cases and a **three-model local Ollama stack** for contextual and security work: **Gemma 4 26B** for general InboxHero reasoning, grounded drafting and thread summarisation; **Granite Guardian 4.1 8B** for the dedicated security gate; and **Gemma 4 12B** for specialized threat labeling and persistent-preference security validation. Retrieval uses the supplied inbox's `thread_id` structure, persistent scheduling preferences are stored in `prefs.json`, and irreversible actions are isolated behind a dry-run/approval gate. Email content is treated as untrusted data throughout the architecture rather than as executable instructions.

## System facts

| Field | Choice |
|---|---|
| Framework | `none` |
| General model | `gemma4:26b` via local Ollama |
| Security gate | `granite4.1-guardian:8b` via local Ollama |
| Security labeling / preference validation | `gemma4:12b` via local Ollama |
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

The final system uses model specialization rather than asking one model to perform every task.

- **Gemma 4 26B (`gemma4:26b`)** is the general-purpose InboxHero model. It handles contextual R1 classification, grounded drafting and thread summarisation. During development, it was compared with Qwen 3.8, GPT-OSS 20B and Gemma 4 12B; the observed 100-message R1 benchmark for Gemma 4 26B was 20.34 seconds with 0 undecided messages, so it was selected for the general contextual workload.
- **Granite Guardian 4.1 8B (`granite4.1-guardian:8b`)** is the dedicated security gate. It evaluates untrusted email content before normal processing and produces a binary threat decision. Keeping this role separate prevents the general agent from being the sole security boundary.
- **Gemma 4 12B (`gemma4:12b`)** handles narrower security tasks: threat labeling/explanation after the security gate has detected a threat, and validation of candidate persistent preferences before they are stored. A smaller model is sufficient for these constrained classification tasks and avoids using the larger general model for every security check.

All models run locally through Ollama. Provider/model settings are configured through the project configuration where applicable, while the security components explicitly select their specialized models. The separation is intentional: the security gate, security labeling, preference validation and general inbox reasoning have distinct responsibilities.

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

## Security-first pipeline

The final prototype can be run independently of the original R1-R6 capability commands using the security-first pipeline. The security pipeline adds an explicit boundary before normal inbox reasoning:

```text
INBOX
  |
  v
Rule Gate + Granite Guardian
  |
  +---- THREAT ----> QUARANTINE / FLAGGED
  |
  +---- SAFE ------> Irreversible Guard
                         |
                         v
                 Preference Security
                         |
                         v
                 Generic Noise Filter
                         |
                         v
                  Q1-Q4 Triage
                         |
                         v
                 Existing Agent
```

Email content is treated as **untrusted data** throughout this flow. The deterministic rule gate catches known high-risk patterns, while Granite Guardian provides an independent LLM security decision. Threats are quarantined and do not proceed to preference persistence, normal triage or the general InboxHero agent. Candidate owner preferences are separately validated before persistence. Irreversible-action instructions are refused and require human review rather than becoming autonomous actions.

### Security-first commands

Run the complete security-first pipeline:

```bash
python3 pipeline.py
```

This reads the supplied `inbox.json`, runs the rule + Granite security gate, quarantines threats, applies the irreversible-action boundary, validates persistent preferences, filters deterministic generic noise, runs Q1-Q4 triage on the remaining safe messages, and writes:

```text
outputs/pipeline_results.json
outputs/pipeline_audit.json
```

Generate the presentation dashboard from the completed pipeline artifacts:

```bash
python3 dashboard.py
```

The generated `dashboard.html` contains exactly the three R6 Inbox Overview panes:

1. **Commitments**
2. **Flagged / Security**
3. **Pending Actions**

It also contains a separate **Triage Q1-Q4** tab. The triage tab is a visualization/analysis view and is not counted as an additional R6 pane.

To run the deterministic security tests without requiring an LLM:

```bash
pytest -q tests/test_irreversible_actions.py tests/test_security_rule_gate.py
```

The full security-first pipeline requires Ollama with the configured local models available.

### Security-first observed run

The latest recorded security-first run processed **100 messages**:

- **8** threats quarantined
- **92** messages passed the security gate
- **13** generic-noise messages filtered deterministically
- **79** normal messages reached quadrant LLM triage
- Q1: **14**
- Q2: **17**
- Q3: **4**
- Q4: **57**
- **0** irreversible-action refusals in this fixture
- Security invariant: **PASS**

The invariant checks that no threat reached preference extraction or the normal agent, and that no irreversible instruction reached either path.

### Q1-Q4 triage interpretation

The quadrant classifier separates **priority** from **disposition**. Q1-Q4 describe urgency and importance; the final disposition still determines the handling action. The mapping shown in the dashboard is: Q1 **For Your Action or Response**, Q2 **Schedule / Follow Up**, Q3 **Delegate**, and Q4 **Archive**. This is a presentation/priority framework, not a rule that forces every message in a quadrant to have the same disposition.

The triage tab displays the four quadrants in a 2x2 layout, with expandable messages and the original disposition visible for each message. Generic noise is included in Q4/Archive, while security threats remain outside triage in the Flagged / Security pane.

## Security-first integration

### Security model stack

| Stage | Model | Responsibility |
|---|---|---|
| Rule gate | Deterministic Python rules | Catches known prompt-injection, phishing and payment-fraud patterns without an LLM. |
| Security gate | **Granite Guardian 4.1 8B** (`granite4.1-guardian:8b`) | Independent binary threat screening of untrusted email content. |
| Threat labeling | **Gemma 4 12B** (`gemma4:12b`) | Adds threat category/reason explanation after a security threat has been detected. |
| Preference security | **Gemma 4 12B** (`gemma4:12b`) | Validates candidate owner preferences before persistence. |
| General agent | **Gemma 4 26B** (`gemma4:26b`) | Contextual inbox triage, grounded drafting and thread summarisation for messages that pass the security boundary. |

The model selection follows a **specialized-role principle**: the larger general model is reserved for
context-heavy inbox tasks, while dedicated/smaller models handle security decisions and constrained
classification tasks. Threats are quarantined before normal agent processing.

- Rule + Granite security gate
- Threat quarantine and owner review
- Irreversible-action refusal boundary
- Secure persistent preferences
- Generic-noise filtering
- Q1-Q4 triage dashboard
