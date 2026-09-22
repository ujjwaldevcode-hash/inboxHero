
"""Build the final security-first InboxHero R6 dashboard.

Presentation-only:
- Reads the completed security-first pipeline artifacts.
- Does NOT call an LLM.
- Does NOT rerun triage.
- Keeps exactly three R6 panes:
    1. Commitments
    2. Flagged / Security
    3. Pending Actions

Quadrant classification and original InboxHero disposition are displayed
as separate dimensions.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Locate the actual project root robustly.
#
# The dashboard is inside experiment_g/security_first_v2, but we do not
# assume a fixed number of parent directories. Walk upward until we find
# the directory containing the inboxhero package.
# ---------------------------------------------------------------------------
PROJECT_ROOT = None

for parent in [SCRIPT_DIR, *SCRIPT_DIR.parents]:
    candidate = parent / "inboxhero"
    if candidate.is_dir():
        PROJECT_ROOT = parent
        break

if PROJECT_ROOT is None:
    raise RuntimeError(
        "Could not locate the 'inboxhero' package. "
        f"Started searching from: {SCRIPT_DIR}"
    )

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

print(f"[dashboard] Project root: {PROJECT_ROOT}")
print(f"[dashboard] inboxhero package: {PROJECT_ROOT / 'inboxhero'}")

from inboxhero.commitments import extract_commitments, scheduling_conflicts
from inboxhero.loader import load_inbox

# The baseline inboxhero package does not necessarily expose BASE_DIR or
# INBOX_PATH from config.py. Resolve the project paths locally instead.
BASE_DIR = PROJECT_ROOT

_INBOX_CANDIDATES = [
    PROJECT_ROOT / "inbox.json",
    PROJECT_ROOT / "inboxhero" / "inbox.json",
    PROJECT_ROOT / "experiment_g" / "security_first_v1" / "inbox.json",
    PROJECT_ROOT / "experiment_g" / "security_first_v2" / "inbox.json",
]

INBOX_PATH = next(
    (path for path in _INBOX_CANDIDATES if path.is_file()),
    None,
)

if INBOX_PATH is None:
    discovered = list(PROJECT_ROOT.rglob("inbox.json"))

    if len(discovered) == 1:
        INBOX_PATH = discovered[0]
    elif len(discovered) > 1:
        raise RuntimeError(
            "Multiple inbox.json files found. Please choose one:\n"
            + "\n".join(str(path) for path in discovered)
        )
    else:
        raise RuntimeError(
            f"No inbox.json found below project root: {PROJECT_ROOT}"
        )

print(f"[dashboard] Inbox: {INBOX_PATH}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def recipient_text(message) -> str:
    value = getattr(message, "recipients", "")
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(x) for x in value)
    return str(value or "")


def message_dict(message) -> dict:
    return {
        "message_id": str(getattr(message, "id", "")),
        "sender": str(getattr(message, "sender", "")),
        "recipient": recipient_text(message),
        "subject": str(getattr(message, "subject", "")),
        "timestamp": str(getattr(message, "timestamp", "")),
        "body": str(getattr(message, "body", "")),
        "thread_id": str(getattr(message, "thread_id", "") or ""),
    }


def sender_type(sender: str, owner_domain: str = "paperjet.io") -> str:
    sender = (sender or "").strip().lower()
    if "@" not in sender:
        return "UNKNOWN"
    return "INTERNAL" if sender.rsplit("@", 1)[1] == owner_domain else "EXTERNAL"


def email_details(message: dict, label: str = "View email") -> str:
    return f"""
    <details class="email-details">
      <summary>{html.escape(label)}</summary>
      <div class="email-view">
        <div class="email-meta-grid">
          <div><span>From</span><strong>{html.escape(message.get("sender", ""))}</strong></div>
          <div><span>To</span><strong>{html.escape(message.get("recipient", ""))}</strong></div>
          <div><span>Subject</span><strong>{html.escape(message.get("subject", ""))}</strong></div>
          <div><span>Timestamp</span><strong>{html.escape(message.get("timestamp", ""))}</strong></div>
          <div><span>Thread</span><strong>{html.escape(message.get("thread_id", ""))}</strong></div>
          <div><span>Message ID</span><strong>{html.escape(message.get("message_id", ""))}</strong></div>
        </div>
        <div class="email-body-label">Message</div>
        <div class="email-body">{html.escape(message.get("body", "")).replace(chr(10), "<br>")}</div>
      </div>
    </details>
    """


def badge(value: str, kind: str = "neutral") -> str:
    return f'<span class="badge badge-{kind}">{html.escape(str(value).replace("_", " ").upper())}</span>'


def disposition_badge(disposition: str) -> str:
    mapping = {
        "reply": "info",
        "escalate": "danger",
        "defer": "warn",
        "delegate": "info",
        "archive": "success",
    }
    return badge(disposition, mapping.get(disposition, "neutral"))


def quadrant_badge(quadrant: str, label: str) -> str:
    return badge(f"{quadrant} · {label}", "neutral")


def group_details(title: str, count: int, body: str, css: str = "") -> str:
    return f"""
    <details class="subgroup {css}">
      <summary>
        <span class="sub-arrow">▶</span>
        <span class="sub-title">{html.escape(title)}</span>
        <span class="sub-count">{count}</span>
      </summary>
      <div class="sub-body">{body}</div>
    </details>
    """


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------

def load_artifacts(root: Path) -> dict:
    output_dir = root / "outputs"
    v1_output_dir = root / "outputs"

    pipeline = read_json(output_dir / "pipeline_results.json", {})
    audit = read_json(output_dir / "pipeline_audit.json", [])
    quadrant = read_json(output_dir / "quadrant_summary.json", {})
    potential = read_json(v1_output_dir / "potential_threats.json", {})

    if isinstance(potential, dict):
        potential = potential.get("threats", [])

    if not isinstance(pipeline, dict):
        pipeline = {}

    if not isinstance(quadrant, dict):
        quadrant = {}

    return {
        "output_dir": output_dir,
        "pipeline": pipeline,
        "audit": audit,
        "quadrant": quadrant,
        "potential": potential if isinstance(potential, list) else [],
    }


# ---------------------------------------------------------------------------
# Dashboard data
# ---------------------------------------------------------------------------

def build_dashboard(messages: list, root: Path) -> dict:
    artifacts = load_artifacts(root)
    pipeline = artifacts["pipeline"]
    quadrant = artifacts["quadrant"]
    potential = artifacts["potential"]

    by_id = {str(m.id): m for m in messages}

    # -----------------------------------------------------------------------
    # Security gate
    # -----------------------------------------------------------------------
    security_results = pipeline.get("security", {})
    threat_records = pipeline.get("threats", [])

    if not threat_records:
        # Some artifact versions store the detailed list under another field.
        threat_records = pipeline.get("quarantined", [])

    threat_ids = {
        str(t.get("message_id"))
        for t in threat_records
        if isinstance(t, dict) and t.get("message_id")
    }

    safe_messages = [
        m for m in messages
        if str(m.id) not in threat_ids
    ]

    # -----------------------------------------------------------------------
    # Threat rows
    # -----------------------------------------------------------------------
    potential_by_id = {
        str(x.get("message_id")): x
        for x in potential
        if isinstance(x, dict) and x.get("message_id")
    }

    security_rows = []

    for threat in threat_records:
        if not isinstance(threat, dict):
            continue

        message_id = str(threat.get("message_id", ""))
        message = by_id.get(message_id)

        label = threat.get("threat_label", {})
        if not isinstance(label, dict):
            label = {}

        potential_record = potential_by_id.get(message_id, {})

        row = message_dict(message) if message else {
            "message_id": message_id,
            "sender": str(threat.get("sender", "")),
            "recipient": "",
            "subject": "",
            "timestamp": "",
            "body": "",
            "thread_id": "",
        }

        sender = row["sender"]

        row.update({
            "category": label.get("category", "SECURITY_THREAT"),
            "severity": label.get("severity", "UNKNOWN"),
            "sender_type": (
                potential_record.get("sender_type")
                or sender_type(sender)
            ),
            "decision_source": threat.get(
                "decision_source", "SECURITY_GATE"
            ),
            "owner_review": (
                potential_record.get("display_action")
                or "Review Required"
            ),
            "status": "QUARANTINED",
        })

        security_rows.append(row)

    # -----------------------------------------------------------------------
    # Quadrant + disposition results
    # -----------------------------------------------------------------------
    safe_triage = pipeline.get("safe_triage", [])
    if not isinstance(safe_triage, list):
        safe_triage = []

    noise_records = (
        pipeline.get("noise_filter", {}).get("records", [])
        if isinstance(pipeline.get("noise_filter", {}), dict)
        else []
    )

    if not isinstance(noise_records, list):
        noise_records = []

    noise_ids = {
        str(r.get("message_id"))
        for r in noise_records
        if isinstance(r, dict) and r.get("message_id")
    }

    # Only safe messages are allowed into the normal dashboard.
    safe_triage = [
        r for r in safe_triage
        if str(r.get("message_id", "")) not in threat_ids
    ]

    pending = []

    for result in safe_triage:
        disposition = str(result.get("disposition", ""))

        # Archive is not pending.
        if disposition == "archive":
            continue

        message_id = str(result.get("message_id", ""))
        message = by_id.get(message_id)

        if not message:
            continue

        row = message_dict(message)
        row.update({
            "disposition": disposition,
            "reason": str(result.get("reason", "")),
            "quadrant": str(result.get("quadrant", "")),
            "quadrant_label": str(result.get("quadrant_label", "")),
            "quadrant_action": str(result.get("quadrant_action", "")),
            "urgent": result.get("urgent"),
            "important": result.get("important"),
            "source": result.get("source", "quadrant_triage"),
        })

        pending.append(row)

    # -----------------------------------------------------------------------
    # Commitments
    #
    # Security-first rule: commitments are extracted only from messages
    # that passed the security gate.
    # -----------------------------------------------------------------------
    commitments = extract_commitments(safe_messages)

    for commitment in commitments:
        source_emails = []

        for source_id in commitment.get("source_message_ids", []):
            message = by_id.get(str(source_id))
            if message:
                source_emails.append(message_dict(message))

        commitment["source_emails"] = source_emails

    conflicts = scheduling_conflicts(safe_messages)

    multi_source_count = sum(
        1
        for c in commitments
        if len(c.get("source_message_ids", [])) > 1
    )

    # -----------------------------------------------------------------------
    # Pending subgrouping
    # -----------------------------------------------------------------------
    actionable = [
        x for x in pending
        if x["disposition"] in {"reply", "delegate"}
    ]

    deferred = [
        x for x in pending
        if x["disposition"] == "defer"
    ]

    escalated = [
        x for x in pending
        if x["disposition"] == "escalate"
    ]

    # -----------------------------------------------------------------------
    # Security invariant
    # -----------------------------------------------------------------------
    invariant = pipeline.get("security_invariant", {})
    if not isinstance(invariant, dict):
        invariant = {}

    return {
        "panes": {
            "commitments": commitments,
            "flagged": security_rows,
            "pending_actions": pending,
        },
        "pending_groups": {
            "actionable": actionable,
            "deferred": deferred,
            "escalated": escalated,
        },
        "noise_records": noise_records,
        "conflicts": conflicts,
        "security": {
            "threat_count": len(security_rows),
            "internal_count": sum(
                1 for x in security_rows if x["sender_type"] == "INTERNAL"
            ),
            "external_count": sum(
                1 for x in security_rows if x["sender_type"] == "EXTERNAL"
            ),
            "unknown_count": sum(
                1 for x in security_rows if x["sender_type"] == "UNKNOWN"
            ),
            "baseline_flagged_count": len(
                pipeline.get("baseline_flagged", [])
            ) if isinstance(pipeline.get("baseline_flagged"), list) else 0,
            "invariant": invariant,
        },
        "quadrant": {
            "counts": quadrant.get(
                "quadrant_counts",
                {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0},
            ),
            "dispositions": quadrant.get("disposition_counts", {}),
        },
        "_messages": {
            str(m.id): message_dict(m)
            for m in messages
        },
        "_pipeline": pipeline,
        "metadata": {
            "messages_processed": len(messages),
            "safe_count": len(safe_messages),
            "noise_count": len(noise_records),
            "meaningful_count": len(safe_triage),
            "pending_count": len(pending),
            "actionable_count": len(actionable),
            "deferred_count": len(deferred),
            "escalated_count": len(escalated),
            "commitment_count": len(commitments),
            "conflict_count": len(conflicts),
            "multi_source_count": multi_source_count,
        },
    }


# ---------------------------------------------------------------------------
# Triage tab rendering
# ---------------------------------------------------------------------------

def render_triage_tab(data: dict) -> str:
    """Render the separate Q1/Q2/Q3/Q4 triage overview tab."""

    quadrant_info = {
        "Q1": {
            "label": "Q1 · Urgent + Important",
            "title": "For Your Action or Response",
            "description": (
                "Urgent and important messages requiring owner action, "
                "response, decision, or intervention."
            ),
            "css": "q1",
        },
        "Q2": {
            "label": "Q2 · Important + Not Urgent",
            "title": "Schedule / Follow Up",
            "description": (
                "Important work that is not immediately urgent and can "
                "be scheduled or followed up."
            ),
            "css": "q2",
        },
        "Q3": {
            "label": "Q3 · Urgent + Not Important",
            "title": "Delegate",
            "description": (
                "Urgent but lower-owner-importance work that may be "
                "delegated or handled routinely."
            ),
            "css": "q3",
        },
        "Q4": {
            "label": "Q4 · Not Urgent + Not Important",
            "title": "Archive",
            "description": (
                "Low-priority information and generic noise that does "
                "not require action."
            ),
            "css": "q4",
        },
    }

    pipeline = data.get("_pipeline", {})
    safe_triage = pipeline.get("safe_triage", [])
    noise_records = pipeline.get("noise_filter", {}).get("records", [])

    if not isinstance(safe_triage, list):
        safe_triage = []
    if not isinstance(noise_records, list):
        noise_records = []

    # Exclude security threats from the quadrant tab.
    threat_ids = {
        str(x.get("message_id"))
        for x in data["panes"]["flagged"]
        if x.get("message_id")
    }

    records = [
        r for r in safe_triage
        if str(r.get("message_id", "")) not in threat_ids
    ]

    # Add deterministic generic-noise records as Q4.
    records = list(records)

    for noise in noise_records:
        record = dict(noise)
        record["quadrant"] = "Q4"
        record["quadrant_label"] = quadrant_info["Q4"]["label"]
        record["quadrant_action"] = quadrant_info["Q4"]["title"]
        record["disposition"] = "archive"
        record["source"] = "generic_noise_filter"
        records.append(record)

    by_quadrant = {q: [] for q in quadrant_info}

    for record in records:
        q = record.get("quadrant")
        if q in by_quadrant:
            by_quadrant[q].append(record)

    # Message lookup is stored on the dashboard data by build_dashboard().
    messages = data.get("_messages", {})
    sections = []

    for q, info in quadrant_info.items():
        rows = by_quadrant[q]

        disposition_counts = {}
        for row in rows:
            disposition = str(row.get("disposition", "unknown"))
            disposition_counts[disposition] = (
                disposition_counts.get(disposition, 0) + 1
            )

        disposition_summary = " · ".join(
            f"{d.replace('_', ' ').title()} {count}"
            for d, count in sorted(disposition_counts.items())
        ) or "No messages"

        cards = []

        for row in rows:
            message_id = str(row.get("message_id", ""))
            message = messages.get(message_id)

            if message:
                email = message
            else:
                email = {
                    "message_id": message_id,
                    "sender": str(row.get("sender", "")),
                    "recipient": str(row.get("recipient", "")),
                    "subject": str(row.get("subject", "")),
                    "timestamp": str(row.get("timestamp", "")),
                    "body": str(row.get("body", "")),
                    "thread_id": str(row.get("thread_id", "")),
                }

            disposition = str(row.get("disposition", "archive"))
            source = str(row.get("source", "quadrant_triage"))

            cards.append(f"""
            <div class="triage-message">
              <div class="triage-message-head">
                <div>
                  <div class="message-id">{html.escape(message_id)}</div>
                  <div class="triage-message-subject">
                    {html.escape(email.get("subject", ""))}
                  </div>
                  <div class="item-meta">
                    {html.escape(email.get("sender", ""))}
                  </div>
                </div>

                <div class="badges">
                  {disposition_badge(disposition)}
                  {badge(
                      "NOISE" if source == "generic_noise_filter"
                      else "QUADRANT",
                      "neutral",
                  )}
                </div>
              </div>

              <div class="triage-reason">
                {html.escape(str(row.get("reason", "")))}
              </div>

              {email_details(
                  email,
                  f"View email · {message_id}",
              )}
            </div>
            """)

        cards_html = "".join(cards) or (
            '<div class="empty">No messages in this quadrant.</div>'
        )

        sections.append(f"""
        <details class="quadrant-card {info["css"]}" {"open" if q == "Q1" else ""}>
          <summary>
            <span class="quadrant-arrow">▶</span>

            <div class="quadrant-heading">
              <div class="quadrant-label">{html.escape(info["label"])}</div>
              <div class="quadrant-title">{html.escape(info["title"])}</div>
              <div class="quadrant-description">
                {html.escape(info["description"])}
              </div>
            </div>

            <div class="quadrant-count">
              <strong>{len(rows)}</strong>
              <span>messages</span>
            </div>
          </summary>

          <div class="quadrant-body">
            <div class="quadrant-dispositions">
              {html.escape(disposition_summary)}
            </div>
            {cards_html}
          </div>
        </details>
        """)

    counts = {
        q: len(by_quadrant[q])
        for q in by_quadrant
    }

    return f"""
    <section class="triage-tab" id="triage-tab">
      <div class="triage-header">
        <div>
          <div class="triage-eyebrow">INBOX TRIAGE</div>
          <h2>Four-Quadrant Overview</h2>
          <p>
            92 safe messages classified by urgency and importance.
            The original InboxHero disposition remains independent from
            the quadrant classification.
          </p>
        </div>

        <div class="triage-total">
          <strong>{sum(counts.values())}</strong>
          <span>safe messages</span>
        </div>
      </div>

      <div class="triage-note">
        <strong>How to read this view:</strong>
        the quadrant describes <em>priority</em>; the InboxHero disposition
        describes <em>handling</em>. Security threats are excluded from
        this view. Generic noise is deterministically routed to Q4 / Archive.
      </div>

      <div class="quadrant-summary-grid">
        <div class="quadrant-mini q1">
          <strong>{counts["Q1"]}</strong>
          <span>Q1 · Action / Response</span>
        </div>
        <div class="quadrant-mini q2">
          <strong>{counts["Q2"]}</strong>
          <span>Q2 · Schedule / Follow Up</span>
        </div>
        <div class="quadrant-mini q3">
          <strong>{counts["Q3"]}</strong>
          <span>Q3 · Delegate</span>
        </div>
        <div class="quadrant-mini q4">
          <strong>{counts["Q4"]}</strong>
          <span>Q4 · Archive</span>
        </div>
      </div>

      <div class="quadrant-grid">
        {''.join(sections)}
      </div>
    </section>
    """

# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def render_dashboard(root: Path, data: dict) -> None:
    p = data["panes"]
    pg = data["pending_groups"]
    sec = data["security"]
    q = data["quadrant"]
    meta = data["metadata"]

    inv = sec["invariant"]
    inv_status = "PASS" if inv.get("passed") else "CHECK"

    # -----------------------------------------------------------------------
    # Commitments
    # -----------------------------------------------------------------------
    commitment_items = []

    for c in p["commitments"]:
        sources = c.get("source_message_ids", [])
        source_emails = c.get("source_emails", [])

        source_html = "".join(
            email_details(
                email,
                f"View source email · {email.get('message_id', '')}",
            )
            for email in source_emails
        )

        multi = len(sources) > 1

        commitment_items.append(f"""
        <div class="commitment-card">
          <div class="item-head">
            <div>
              <div class="item-title">{html.escape(str(c.get("title", "")))}</div>
              <div class="item-meta">
                {html.escape(str(c.get("when", "")))} ·
                {html.escape(str(c.get("status", "")))}
              </div>
            </div>
            <div class="badges">
              {badge("MULTI-SOURCE", "info") if multi else ""}
              {badge(str(c.get("status", "commitment")), "neutral")}
            </div>
          </div>

          <div class="source-line">
            Sources: {html.escape(", ".join(str(x) for x in sources))}
          </div>

          {f'<div class="source-emails">{source_html}</div>' if source_html else ""}
        </div>
        """)

    commitments_body = "".join(commitment_items) or '<div class="empty">No commitments found.</div>'

    # Conflicts
    conflict_items = []

    for conflict in data["conflicts"]:
        description = conflict.get("description", "")
        source_ids = conflict.get("messages", [])

        conflict_items.append(f"""
        <div class="conflict-card">
          <div class="conflict-title">⚠ Scheduling conflict</div>
          <div class="conflict-description">{html.escape(str(description))}</div>
          <div class="source-line">
            Sources: {html.escape(", ".join(str(x) for x in source_ids))}
          </div>
        </div>
        """)

    conflict_body = "".join(conflict_items) or '<div class="empty">No scheduling conflicts detected.</div>'

    # -----------------------------------------------------------------------
    # Security
    # -----------------------------------------------------------------------
    security_groups = {
        "INTERNAL": [],
        "EXTERNAL": [],
        "UNKNOWN": [],
    }

    for row in p["flagged"]:
        security_groups.setdefault(row["sender_type"], []).append(row)

    security_group_html = ""

    for group_name in ["INTERNAL", "EXTERNAL", "UNKNOWN"]:
        rows = security_groups.get(group_name, [])

        if not rows:
            continue

        cards = ""

        for row in rows:
            cards += f"""
            <div class="message-card security-card">
              <div class="item-head">
                <div>
                  <div class="message-id">{html.escape(row["message_id"])}</div>
                  <div class="item-title">{html.escape(row["subject"])}</div>
                  <div class="item-meta">{html.escape(row["sender"])}</div>
                </div>
                <div class="badges">
                  {badge(row["severity"], "danger" if row["severity"].upper() == "HIGH" else "warn")}
                  {badge("QUARANTINED", "danger")}
                </div>
              </div>

              <div class="security-meta">
                <span>{html.escape(row["category"])}</span>
                <span>{html.escape(row["decision_source"])}</span>
                <span>Owner: {html.escape(row["owner_review"])}</span>
              </div>

              {email_details(row)}
            </div>
            """

        security_group_html += group_details(
            group_name.title(),
            len(rows),
            cards,
            "security-subgroup",
        )

    # -----------------------------------------------------------------------
    # Pending
    # -----------------------------------------------------------------------
    def pending_cards(rows: list[dict]) -> str:
        if not rows:
            return '<div class="empty">No messages in this section.</div>'

        output = ""

        for row in rows:
            output += f"""
            <div class="message-card">
              <div class="item-head">
                <div>
                  <div class="message-id">{html.escape(row["message_id"])}</div>
                  <div class="item-title">{html.escape(row["subject"])}</div>
                  <div class="item-meta">{html.escape(row["sender"])}</div>
                </div>

                <div class="badges">
                  {disposition_badge(row["disposition"])}
                  {quadrant_badge(row["quadrant"], row["quadrant_label"])}
                </div>
              </div>

              <div class="quadrant-line">
                <strong>Quadrant handling:</strong>
                {html.escape(row["quadrant_action"])}
              </div>

              <div class="reason">
                {html.escape(row["reason"])}
              </div>

              {email_details(row)}
            </div>
            """

        return output

    pending_groups_html = (
        group_details(
            "For Your Action or Response",
            len(pg["actionable"]),
            pending_cards(pg["actionable"]),
            "pending-subgroup",
        )
        +
        group_details(
            "Schedule / Follow Up",
            len(pg["deferred"]),
            pending_cards(pg["deferred"]),
            "pending-subgroup",
        )
        +
        group_details(
            "Escalate / Important",
            len(pg["escalated"]),
            pending_cards(pg["escalated"]),
            "pending-subgroup",
        )
    )

    # -----------------------------------------------------------------------
    # Page
    # -----------------------------------------------------------------------
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>InboxHero · Security-First Dashboard</title>
<style>
:root {{
  --bg:#f4f7fb;
  --card:#ffffff;
  --line:#dce3ec;
  --text:#172033;
  --muted:#667085;
  --accent:#315efb;
  --accent-soft:#edf2ff;
  --danger:#c62828;
  --danger-soft:#fff0f0;
  --warn:#9a6700;
  --warn-soft:#fff8df;
  --success:#18794e;
  --success-soft:#eaf8f1;
  --shadow:0 10px 28px rgba(16,24,40,.06);
}}

* {{ box-sizing:border-box; }}

body {{
  margin:0;
  background:var(--bg);
  color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
}}

main {{
  width:min(1500px,calc(100% - 32px));
  margin:0 auto;
  padding:28px 0 48px;
}}

header {{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:20px;
  margin-bottom:22px;
}}

.brand {{
  display:flex;
  align-items:center;
  gap:13px;
}}

.logo {{
  width:44px;
  height:44px;
  border-radius:13px;
  display:grid;
  place-items:center;
  background:var(--accent);
  color:white;
  font-weight:900;
  letter-spacing:-.05em;
}}

h1 {{
  margin:0;
  font-size:1.55rem;
  letter-spacing:-.035em;
}}

.subtitle {{
  color:var(--muted);
  font-size:.75rem;
  margin-top:3px;
}}

.header-status {{
  padding:8px 12px;
  border:1px solid var(--line);
  border-radius:999px;
  background:white;
  color:var(--muted);
  font-size:.68rem;
  font-weight:800;
}}

.status-dot {{
  display:inline-block;
  width:7px;
  height:7px;
  border-radius:50%;
  background:var(--success);
  margin-right:6px;
}}

.metrics {{
  display:grid;
  grid-template-columns:repeat(5,1fr);
  gap:10px;
  margin-bottom:18px;
}}

.metric {{
  background:var(--card);
  border:1px solid var(--line);
  border-radius:13px;
  padding:14px;
  box-shadow:var(--shadow);
}}

.metric-value {{
  font-size:1.2rem;
  font-weight:900;
  letter-spacing:-.03em;
}}

.metric-label {{
  color:var(--muted);
  font-size:.63rem;
  text-transform:uppercase;
  letter-spacing:.06em;
  font-weight:800;
  margin-top:3px;
}}

.dashboard {{
  display:grid;
  gap:12px;
}}

.pane {{
  background:white;
  border:1px solid var(--line);
  border-radius:15px;
  box-shadow:var(--shadow);
  overflow:hidden;
}}

.pane > summary {{
  list-style:none;
  cursor:pointer;
  display:flex;
  align-items:center;
  gap:12px;
  padding:16px 18px;
  background:#fff;
}}

.pane > summary::-webkit-details-marker {{
  display:none;
}}

.pane-arrow {{
  font-size:.65rem;
  transition:transform .15s ease;
}}

.pane[open] > summary .pane-arrow {{
  transform:rotate(90deg);
}}

.pane-title-wrap {{
  min-width:220px;
}}

.pane-title {{
  font-size:.92rem;
  font-weight:950;
}}

.pane-kicker {{
  color:var(--muted);
  font-size:.66rem;
  margin-top:3px;
}}

.pane-summary {{
  margin-left:auto;
  display:flex;
  flex-wrap:wrap;
  justify-content:flex-end;
  gap:6px;
}}

.summary-pill {{
  border-radius:999px;
  padding:5px 8px;
  background:#eef2f6;
  color:#526071;
  font-size:.59rem;
  font-weight:900;
}}

.summary-pill.danger {{
  background:var(--danger-soft);
  color:var(--danger);
}}

.summary-pill.info {{
  background:var(--accent-soft);
  color:var(--accent);
}}

.summary-pill.warn {{
  background:var(--warn-soft);
  color:var(--warn);
}}

.pane-body {{
  border-top:1px solid var(--line);
  padding:14px;
  background:#f9fbfd;
}}

.subgroup {{
  background:white;
  border:1px solid var(--line);
  border-radius:12px;
  overflow:hidden;
  margin-bottom:10px;
}}

.subgroup > summary {{
  list-style:none;
  cursor:pointer;
  display:flex;
  align-items:center;
  gap:8px;
  padding:11px 13px;
  font-size:.74rem;
  font-weight:900;
}}

.subgroup > summary::-webkit-details-marker {{
  display:none;
}}

.sub-arrow {{
  font-size:.55rem;
  transition:transform .15s ease;
}}

.subgroup[open] > summary .sub-arrow {{
  transform:rotate(90deg);
}}

.sub-count {{
  margin-left:auto;
  min-width:24px;
  text-align:center;
  padding:3px 7px;
  border-radius:999px;
  background:#eef2f6;
  color:#526071;
  font-size:.6rem;
}}

.sub-body {{
  border-top:1px solid var(--line);
  padding:10px;
}}

.message-card,
.commitment-card {{
  background:white;
  border:1px solid var(--line);
  border-radius:11px;
  padding:12px;
  margin-bottom:8px;
}}

.message-card:last-child,
.commitment-card:last-child {{
  margin-bottom:0;
}}

.item-head {{
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:flex-start;
}}

.message-id {{
  color:var(--accent);
  font:800 .61rem ui-monospace,SFMono-Regular,Menlo,monospace;
  margin-bottom:3px;
}}

.item-title {{
  font-size:.79rem;
  font-weight:900;
  line-height:1.35;
}}

.item-meta {{
  color:var(--muted);
  font-size:.66rem;
  margin-top:4px;
}}

.badges {{
  display:flex;
  gap:5px;
  flex-wrap:wrap;
  justify-content:flex-end;
}}

.badge {{
  display:inline-flex;
  align-items:center;
  padding:4px 7px;
  border-radius:999px;
  font-size:.55rem;
  font-weight:950;
  letter-spacing:.035em;
  white-space:nowrap;
}}

.badge-danger {{ background:var(--danger-soft); color:var(--danger); }}
.badge-warn {{ background:var(--warn-soft); color:var(--warn); }}
.badge-info {{ background:var(--accent-soft); color:var(--accent); }}
.badge-success {{ background:var(--success-soft); color:var(--success); }}
.badge-neutral {{ background:#eef2f6; color:#526071; }}

.reason,
.quadrant-line,
.security-meta,
.source-line {{
  font-size:.68rem;
  line-height:1.5;
  color:var(--muted);
  margin-top:8px;
}}

.quadrant-line {{
  padding:8px 10px;
  background:#f7f9fc;
  border-radius:8px;
}}

.security-meta {{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
}}

.security-meta span {{
  padding:4px 7px;
  background:var(--danger-soft);
  color:var(--danger);
  border-radius:999px;
  font-size:.57rem;
  font-weight:850;
}}

.email-details {{
  border:1px solid var(--line);
  border-radius:9px;
  overflow:hidden;
  margin-top:9px;
  background:#fbfcfe;
}}

.email-details summary {{
  list-style:none;
  cursor:pointer;
  padding:8px 10px;
  color:var(--accent);
  font-size:.66rem;
  font-weight:900;
}}

.email-details summary::-webkit-details-marker {{
  display:none;
}}

.email-details summary:before {{
  content:"▶";
  display:inline-block;
  margin-right:7px;
  font-size:.5rem;
  transition:transform .15s ease;
}}

.email-details[open] summary:before {{
  transform:rotate(90deg);
}}

.email-view {{
  padding:11px;
  border-top:1px solid var(--line);
  background:#f8fafc;
}}

.email-meta-grid {{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:7px;
  margin-bottom:10px;
}}

.email-meta-grid > div {{
  background:white;
  border:1px solid var(--line);
  border-radius:8px;
  padding:7px 9px;
  min-width:0;
}}

.email-meta-grid span {{
  display:block;
  color:var(--muted);
  font-size:.53rem;
  text-transform:uppercase;
  letter-spacing:.06em;
  font-weight:900;
  margin-bottom:3px;
}}

.email-meta-grid strong {{
  display:block;
  font-size:.66rem;
  overflow-wrap:anywhere;
}}

.email-body-label {{
  color:var(--muted);
  font-size:.55rem;
  text-transform:uppercase;
  letter-spacing:.06em;
  font-weight:900;
  margin-bottom:4px;
}}

.email-body {{
  background:white;
  border:1px solid var(--line);
  border-radius:8px;
  padding:10px;
  font-size:.7rem;
  line-height:1.55;
  overflow-wrap:anywhere;
}}

.conflict-card {{
  background:var(--danger-soft);
  border:1px solid #f0c0bc;
  border-left:4px solid var(--danger);
  border-radius:10px;
  padding:11px 12px;
  margin-bottom:8px;
}}

.conflict-title {{
  color:var(--danger);
  font-size:.72rem;
  font-weight:950;
}}

.conflict-description {{
  font-size:.69rem;
  line-height:1.5;
  margin-top:4px;
}}

.empty {{
  padding:18px;
  text-align:center;
  color:var(--muted);
  font-size:.69rem;
}}

.dashboard-note {{
  padding:10px 12px;
  background:#f7f9fc;
  border:1px solid var(--line);
  border-radius:10px;
  color:var(--muted);
  font-size:.67rem;
  line-height:1.5;
  margin-bottom:10px;
}}

.footer {{
  text-align:center;
  color:var(--muted);
  font-size:.64rem;
  line-height:1.5;
  margin-top:16px;
}}


/* -----------------------------------------------------------------------
   Tab navigation
   ----------------------------------------------------------------------- */

.tab-controls {{
  display:flex;
  gap:8px;
  margin-bottom:12px;
}}

.tab-button {{
  border:1px solid var(--line);
  background:white;
  color:var(--muted);
  border-radius:10px;
  padding:9px 14px;
  font-size:.68rem;
  font-weight:950;
  cursor:pointer;
}}

.tab-button.active {{
  background:var(--accent);
  color:white;
  border-color:var(--accent);
}}

.tab-panel {{
  display:none;
}}

.tab-panel.active {{
  display:block;
}}

/* -----------------------------------------------------------------------
   Triage overview
   ----------------------------------------------------------------------- */

.triage-tab {{
  background:white;
  border:1px solid var(--line);
  border-radius:15px;
  box-shadow:var(--shadow);
  padding:18px;
}}

.triage-header {{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:20px;
  margin-bottom:12px;
}}

.triage-eyebrow {{
  color:var(--accent);
  font-size:.57rem;
  letter-spacing:.09em;
  font-weight:950;
}}

.triage-header h2 {{
  margin:3px 0 4px;
  font-size:1.15rem;
  letter-spacing:-.025em;
}}

.triage-header p {{
  margin:0;
  color:var(--muted);
  font-size:.68rem;
  line-height:1.5;
  max-width:760px;
}}

.triage-total {{
  min-width:90px;
  text-align:center;
  padding:11px;
  border:1px solid var(--line);
  border-radius:11px;
  background:#f8fafc;
}}

.triage-total strong {{
  display:block;
  font-size:1.15rem;
}}

.triage-total span {{
  color:var(--muted);
  font-size:.57rem;
  font-weight:800;
}}

.triage-note {{
  padding:10px 12px;
  border:1px solid var(--line);
  border-radius:10px;
  background:#f7f9fc;
  color:var(--muted);
  font-size:.66rem;
  line-height:1.5;
  margin-bottom:12px;
}}

.quadrant-summary-grid {{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:9px;
  margin-bottom:12px;
}}

.quadrant-mini {{
  border:1px solid var(--line);
  border-radius:11px;
  padding:11px;
  background:#fbfcfe;
}}

.quadrant-mini strong {{
  display:block;
  font-size:1.2rem;
}}

.quadrant-mini span {{
  color:var(--muted);
  font-size:.58rem;
  font-weight:850;
}}

.quadrant-grid {{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:10px;
}}

.quadrant-card {{
  border:1px solid var(--line);
  border-radius:12px;
  overflow:hidden;
  background:#fff;
}}

.quadrant-card > summary {{
  list-style:none;
  cursor:pointer;
  display:flex;
  align-items:center;
  gap:10px;
  padding:13px;
}}

.quadrant-card > summary::-webkit-details-marker {{
  display:none;
}}

.quadrant-arrow {{
  font-size:.55rem;
  transition:transform .15s ease;
}}

.quadrant-card[open] .quadrant-arrow {{
  transform:rotate(90deg);
}}

.quadrant-heading {{
  min-width:0;
}}

.quadrant-label {{
  font-size:.65rem;
  font-weight:950;
}}

.quadrant-title {{
  font-size:.82rem;
  font-weight:950;
  margin-top:2px;
}}

.quadrant-description {{
  color:var(--muted);
  font-size:.61rem;
  line-height:1.4;
  margin-top:3px;
}}

.quadrant-count {{
  margin-left:auto;
  min-width:55px;
  text-align:center;
}}

.quadrant-count strong {{
  display:block;
  font-size:1.05rem;
}}

.quadrant-count span {{
  color:var(--muted);
  font-size:.55rem;
}}

.quadrant-body {{
  border-top:1px solid var(--line);
  padding:10px;
  background:#f9fbfd;
}}

.quadrant-dispositions {{
  padding:7px 9px;
  margin-bottom:8px;
  border-radius:8px;
  background:#f0f3f7;
  color:#526071;
  font-size:.59rem;
  font-weight:850;
}}

.triage-message {{
  background:white;
  border:1px solid var(--line);
  border-radius:9px;
  padding:10px;
  margin-bottom:7px;
}}

.triage-message:last-child {{
  margin-bottom:0;
}}

.triage-message-head {{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:10px;
}}

.triage-message-subject {{
  font-size:.72rem;
  font-weight:900;
  line-height:1.35;
}}

.triage-reason {{
  color:var(--muted);
  font-size:.63rem;
  line-height:1.45;
  margin-top:6px;
}}

@media(max-width:1000px) {{
  .metrics {{ grid-template-columns:repeat(3,1fr); }}
  .email-meta-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
}}

@media(max-width:700px) {{
  main {{ width:min(100% - 20px,1500px); padding-top:18px; }}
  .quadrant-summary-grid {{ grid-template-columns:repeat(2,1fr); }}
  .quadrant-grid {{ grid-template-columns:1fr; }}
  .triage-header {{ flex-direction:column; }}
  .triage-total {{ align-self:flex-start; }}
  header {{ flex-direction:column; align-items:flex-start; }}
  .metrics {{ grid-template-columns:repeat(2,1fr); }}
  .pane > summary {{ align-items:flex-start; flex-wrap:wrap; }}
  .pane-summary {{ margin-left:34px; width:100%; justify-content:flex-start; }}
  .item-head {{ flex-direction:column; }}
  .badges {{ justify-content:flex-start; }}
  .email-meta-grid {{ grid-template-columns:1fr; }}
}}
</style>
</head>

<body>
<main>

<header>
  <div class="brand">
    <div class="logo">IH</div>
    <div>
      <h1>InboxHero</h1>
      <div class="subtitle">
        Security-first · Quadrant-aware inbox management ·
        {meta["messages_processed"]} messages
      </div>
    </div>
  </div>

  <div class="header-status">
    <span class="status-dot"></span>
    Security invariant {inv_status}
  </div>
</header>

<div class="metrics">
  <div class="metric">
    <div class="metric-value">{meta["commitment_count"]}</div>
    <div class="metric-label">Commitments</div>
  </div>

  <div class="metric">
    <div class="metric-value">{meta["conflict_count"]}</div>
    <div class="metric-label">Conflicts</div>
  </div>

  <div class="metric">
    <div class="metric-value">{sec["threat_count"]}</div>
    <div class="metric-label">Security threats</div>
  </div>

  <div class="metric">
    <div class="metric-value">{meta["pending_count"]}</div>
    <div class="metric-label">Pending actions</div>
  </div>

  <div class="metric">
    <div class="metric-value">{meta["noise_count"]}</div>
    <div class="metric-label">Auto-archived noise</div>
  </div>
</div>

<div class="tab-controls">
  <button class="tab-button active" data-tab="inbox-tab">Inbox Overview</button>
  <button class="tab-button" data-tab="triage-tab-panel">Triage Q1–Q4</button>
</div>

<div class="tab-panel active" id="inbox-tab">
<div class="dashboard">

<!-- ================================================================
     1. COMMITMENTS
     ================================================================ -->
<details class="pane" id="commitments-pane" open>
  <summary>
    <span class="pane-arrow">▶</span>

    <div class="pane-title-wrap">
      <div class="pane-title">1. Commitments</div>
      <div class="pane-kicker">
        Source-linked obligations, deadlines and scheduling conflicts
      </div>
    </div>

    <div class="pane-summary">
      <span class="summary-pill info">{meta["commitment_count"]} Commitments</span>
      <span class="summary-pill danger">{meta["conflict_count"]} Conflict</span>
      <span class="summary-pill info">{meta["multi_source_count"]} Multi-source</span>
    </div>
  </summary>

  <div class="pane-body">

    <div class="dashboard-note">
      Commitments are extracted only from messages that passed the security
      gate. Multi-source commitments retain links to each supporting email.
    </div>

    {group_details(
        "Commitments",
        len(p["commitments"]),
        commitments_body,
    )}

    {group_details(
        "Conflicts",
        len(data["conflicts"]),
        conflict_body,
        "conflict-group",
    )}

  </div>
</details>


<!-- ================================================================
     2. FLAGGED / SECURITY
     ================================================================ -->

<details class="pane" id="security-pane" open>
  <summary>
    <span class="pane-arrow">▶</span>

    <div class="pane-title-wrap">
      <div class="pane-title">2. Flagged / Security</div>
      <div class="pane-kicker">
        Security-gated messages stopped before normal processing
      </div>
    </div>

    <div class="pane-summary">
      <span class="summary-pill danger">{sec["threat_count"]} Threats</span>
      <span class="summary-pill info">{sec["internal_count"]} Internal</span>
      <span class="summary-pill info">{sec["external_count"]} External</span>
      <span class="summary-pill">Invariant {inv_status}</span>
    </div>
  </summary>

  <div class="pane-body">

    <div class="dashboard-note">
      All {sec["threat_count"]} quarantined messages are excluded from normal
      triage, preference extraction and downstream agent processing.
      Each threat email is expandable for evidence review.
    </div>

    {security_group_html or '<div class="empty">No quarantined messages.</div>'}

  </div>
</details>


<!-- ================================================================
     3. PENDING ACTIONS
     ================================================================ -->

<details class="pane" id="pending-pane" open>
  <summary>
    <span class="pane-arrow">▶</span>

    <div class="pane-title-wrap">
      <div class="pane-title">3. Pending Actions</div>
      <div class="pane-kicker">
        Safe messages requiring action, follow-up or owner intervention
      </div>
    </div>

    <div class="pane-summary">
      <span class="summary-pill">{meta["pending_count"]} Pending</span>
      <span class="summary-pill info">{meta["actionable_count"]} Actionable</span>
      <span class="summary-pill warn">{meta["deferred_count"] + meta["escalated_count"]} Important</span>
    </div>
  </summary>

  <div class="pane-body">

    <div class="dashboard-note">
      <strong>Quadrant and disposition are separate.</strong>
      The quadrant describes urgency/importance; the InboxHero disposition
      describes the required handling. Threats never appear here.
    </div>

    {group_details(
        "For Your Action or Response",
        len(pg["actionable"]),
        pending_cards(pg["actionable"]),
        "pending-subgroup",
    )}

    {group_details(
        "Schedule / Follow Up",
        len(pg["deferred"]),
        pending_cards(pg["deferred"]),
        "pending-subgroup",
    )}

    {group_details(
        "Escalate / Important",
        len(pg["escalated"]),
        pending_cards(pg["escalated"]),
        "pending-subgroup",
    )}

  </div>
</details>

</div>
</div>

<div class="tab-panel" id="triage-tab-panel">
  {{TRIAGE_TAB_PLACEHOLDER}}
</div>

<script>
(function () {{
  const buttons = document.querySelectorAll(".tab-button");
  const panels = document.querySelectorAll(".tab-panel");

  buttons.forEach(function (button) {{
    button.addEventListener("click", function () {{
      const target = button.getAttribute("data-tab");

      buttons.forEach(function (b) {{
        b.classList.toggle("active", b === button);
      }});

      panels.forEach(function (panel) {{
        panel.classList.toggle("active", panel.id === target);
      }});
    }});
  }});
}})();
</script>

<div class="footer">
  InboxHero · three R6 panes · security-first quarantine ·
  quadrant-aware triage · source-message traceability · expandable emails
</div>

</main>
</body>
</html>
"""

    # The HTML page above is an f-string, so inject the generated
    # triage tab after all dashboard data is available.
    triage_html = render_triage_tab(data)
    page = page.replace("{TRIAGE_TAB_PLACEHOLDER}", triage_html)

    output_html = root / "dashboard.html"
    output_json = root / "dashboard.json"

    output_json.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    output_html.write_text(page, encoding="utf-8")

    print(f"wrote: {output_html}")
    print(f"wrote: {output_json}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = Path(BASE_DIR)

    messages = load_inbox(INBOX_PATH)
    data = build_dashboard(messages, root)
    render_dashboard(root, data)

    print()
    print("=" * 72)
    print("FINAL SECURITY-FIRST DASHBOARD")
    print("=" * 72)
    print(f"Messages processed : {data['metadata']['messages_processed']}")
    print(f"Security threats   : {data['security']['threat_count']}")
    print(f"Internal threats   : {data['security']['internal_count']}")
    print(f"External threats   : {data['security']['external_count']}")
    print(f"Commitments        : {data['metadata']['commitment_count']}")
    print(f"Conflicts          : {data['metadata']['conflict_count']}")
    print(f"Pending actions    : {data['metadata']['pending_count']}")
    print(f"Generic noise      : {data['metadata']['noise_count']}")
    invariant_status = (
        "PASS"
        if data["security"]["invariant"].get("passed")
        else "CHECK"
    )
    print(f"Invariant           : {invariant_status}")
