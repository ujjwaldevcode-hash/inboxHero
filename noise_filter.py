
"""Experimental generic-noise filter for InboxHero.

This module is intentionally conservative:
- It runs after the security gate and irreversible-action guard.
- It only removes common, low-value informational mail.
- It does NOT classify security alerts, operational incidents, direct requests,
  deadlines, approvals, commitments, or owner-authored preferences as noise.
"""

from __future__ import annotations

import re
from typing import Any


# Strong "no action required" phrases are useful when combined with an
# obviously transactional/informational subject or sender.
NO_ACTION_PHRASES = (
    "no action needed",
    "no action required",
    "for your records only",
    "for your records",
    "informational only",
    "nothing you need to do",
)

NEWSLETTER_SENDERS = (
    "newsletter@",
    "news@",
    "updates@",
    "digest@",
)

NEWSLETTER_SUBJECTS = (
    "newsletter",
    "weekly digest",
    "daily digest",
    "subscription",
    "what's new",
    "weekly analytics",
    "monthly digest",
    "new notifications",
)

RECEIPT_SUBJECTS = (
    "receipt",
    "invoice",
    "order confirmation",
    "payment confirmation",
    "statement",
)

ROUTINE_NOTIFICATION_SUBJECTS = (
    "new comments",
    "new notifications",
    "recording is ready",
    "recording ready",
    "campaign report",
    "weekly report",
    "monthly report",
)

# These terms make a message potentially actionable. A message containing
# them should not be swallowed by a broad newsletter/notification rule.
ACTION_SIGNALS = (
    "please",
    "can you",
    "could you",
    "need you",
    "needs your",
    "action required",
    "approve",
    "approval",
    "deadline",
    "due",
    "by ",
    "before ",
    "blocked",
    "blocking",
    "urgent",
    "asap",
    "respond",
    "reply",
    "confirm",
    "review",
    "issue",
    "incident",
    "outage",
    "failed",
    "failure",
    "security",
    "login",
    "sign-in",
    "password",
    "credential",
    "payment",
    "wire",
    "legal",
    "contract",
    "meeting",
    "schedule",
    "reschedule",
    "interview",
    "launch",
)

OWNER_DOMAIN = "paperjet.io"


def _text(message: Any) -> tuple[str, str, str, str]:
    """Return normalized sender, subject, body and combined text."""
    if isinstance(message, dict):
        sender = str(message.get("from", message.get("sender", "")) or "")
        subject = str(message.get("subject", "") or "")
        body = str(message.get("body", "") or "")
    else:
        sender = str(getattr(message, "sender", "") or "")
        subject = str(getattr(message, "subject", "") or "")
        body = str(getattr(message, "body", "") or "")

    combined = f"{subject}\n{body}".lower()
    return sender.lower().strip(), subject.lower().strip(), body.lower().strip(), combined


def _is_external(sender: str) -> bool:
    if "@" not in sender:
        return True
    return sender.rsplit("@", 1)[1] != OWNER_DOMAIN


def _has_action_signal(text: str) -> bool:
    return any(signal in text for signal in ACTION_SIGNALS)


def detect_generic_noise(message: Any) -> dict:
    """Return a deterministic noise decision.

    Output:
        {
            "is_noise": bool,
            "category": str | None,
            "reason": str,
        }
    """
    sender, subject, body, text = _text(message)

    # Never classify owner-authored mail as generic noise.
    if sender.endswith(f"@{OWNER_DOMAIN}"):
        return {
            "is_noise": False,
            "category": None,
            "reason": "Owner-authored message is retained for normal processing.",
        }

    # Never swallow anything that contains a concrete action/risk signal.
    if _has_action_signal(text):
        return {
            "is_noise": False,
            "category": None,
            "reason": "Message contains an action, risk, deadline, or response signal.",
        }

    # Explicit no-action transactional/informational messages.
    if any(p in body for p in NO_ACTION_PHRASES):
        if (
            any(p in subject for p in RECEIPT_SUBJECTS)
            or any(p in subject for p in NEWSLETTER_SUBJECTS)
            or any(p in subject for p in ROUTINE_NOTIFICATION_SUBJECTS)
            or "statement" in subject
            or "report" in subject
        ):
            return {
                "is_noise": True,
                "category": "routine_informational",
                "reason": "Routine informational/transactional email explicitly states that no action is required.",
            }

    # Newsletters/digests.
    if (
        any(subject_term in subject for subject_term in NEWSLETTER_SUBJECTS)
        and (
            any(sender_prefix in sender for sender_prefix in NEWSLETTER_SENDERS)
            or "unsubscribe" in body
            or "read in your browser" in body
        )
    ):
        return {
            "is_noise": True,
            "category": "newsletter",
            "reason": "Newsletter/digest content with no concrete owner action.",
        }

    # Receipts/statements/confirmations from typical automated senders.
    if any(term in subject for term in RECEIPT_SUBJECTS):
        if (
            sender.startswith(("no-reply@", "noreply@", "notifications@"))
            or "for your records" in body
            or "download your invoice" in body
        ):
            return {
                "is_noise": True,
                "category": "receipt_or_statement",
                "reason": "Routine receipt, invoice, order confirmation, or statement with no owner action.",
            }

    # Routine product/service notifications.
    if any(term in subject for term in ROUTINE_NOTIFICATION_SUBJECTS):
        if sender.startswith(("notify@", "notifications@", "noreply@", "no-reply@")):
            return {
                "is_noise": True,
                "category": "routine_notification",
                "reason": "Routine automated notification with no concrete owner action.",
            }

    # Generic automated report with explicit informational language.
    automated = sender.startswith(
        ("notify@", "notifications@", "noreply@", "no-reply@", "updates@")
    )
    if automated and (
        "report" in subject
        or "analytics" in subject
        or "digest" in subject
    ):
        if not re.search(r"\b(action|approve|review|respond|deadline|issue|incident)\b", text):
            return {
                "is_noise": True,
                "category": "automated_report",
                "reason": "Routine automated report with no concrete owner action.",
            }

    return {
        "is_noise": False,
        "category": None,
        "reason": "Message retained for meaningful triage.",
    }


def filter_generic_noise(messages: list[Any]) -> tuple[list[Any], list[dict]]:
    """Split messages into meaningful messages and generic noise."""
    meaningful = []
    noise = []

    for message in messages:
        decision = detect_generic_noise(message)
        message_id = (
            message.get("id")
            if isinstance(message, dict)
            else getattr(message, "id", "")
        )

        if decision["is_noise"]:
            noise.append({
                "message_id": message_id,
                **decision,
                "disposition": "archive",
                "quadrant": "Q4",
            })
        else:
            meaningful.append(message)

    return meaningful, noise
