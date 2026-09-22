#!/usr/bin/env python3

"""
Thread-aware persistent preference extraction for InboxHero.

Design:

    SAFE THREAD
        |
        v
    Owner-authored message?
        |
        +---- no ----------------------> ignore
        |
        v
    Preference extraction
        |
        +---- no preference -----------> ignore
        |
        +---- temporary constraint ----> do not persist
        |
        v
    Preference security validation
        |
        +---- unsafe ------------------> reject + audit
        |
        +---- safe preference ---------> persistent store
        |
        v
    Persistent preference store


Security rules:

1. This module must only receive messages that have already
   passed the security gate.

2. Quarantined/threat messages must never reach this module.

3. Only explicit preferences authored by the inbox owner
   are eligible for persistence.

4. Preference candidates are security-checked before they
   are persisted.

5. A preference must never grant permission to perform an
   irreversible action or bypass the human approval gate.
"""

import json
import re

from datetime import datetime, timezone
from pathlib import Path


# ===================================================================
# Paths
# ===================================================================

BASE_DIR = Path(__file__).resolve().parent

PREFERENCE_FILE = (
    BASE_DIR
    / "outputs"
    / "preferences.json"
)

PREFERENCE_AUDIT_FILE = (
    BASE_DIR
    / "outputs"
    / "preference_security_audit.json"
)


# ===================================================================
# Owner identity
# ===================================================================

OWNER_EMAIL = "sam@paperjet.io"


# ===================================================================
# Preference categories
# ===================================================================

VALID_CATEGORIES = {
    "scheduling",
    "communication",
    "email_handling",
    "notifications",
    "work_style",
    "general",
}


# ===================================================================
# Utility functions
# ===================================================================

def utc_timestamp():
    """Return the current UTC timestamp."""

    return datetime.now(
        timezone.utc
    ).isoformat()


def normalize_email(value):
    """Normalize an email address."""

    if not value:
        return ""

    return str(value).strip().lower()


def sender_email(message):
    """
    Extract sender email from a raw message dictionary.

    Supports common inbox formats such as:

        "sam@paperjet.io"

    or:

        {
            "email": "sam@paperjet.io"
        }
    """

    sender = message.get("from")

    if isinstance(sender, dict):

        value = (
            sender.get("email")
            or sender.get("address")
            or ""
        )

    elif isinstance(sender, str):

        value = sender

    else:

        value = (
            message.get("sender_email")
            or ""
        )

    value = normalize_email(value)

    # Handle formats such as:
    # "Sam <sam@paperjet.io>"
    match = re.search(
        r"<([^<>@\s]+@[^<>@\s]+)>",
        value,
    )

    if match:
        return match.group(1).lower()

    # Handle an email embedded in arbitrary text.
    match = re.search(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        value,
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(0).lower()

    return value


def is_owner_message(message):
    """
    Return True only when the message was explicitly sent by
    the inbox owner.

    Ownership is determined from the sender email address.
    We do not infer ownership from a display name or domain.
    """

    return (
        sender_email(message)
        == OWNER_EMAIL
    )


# ===================================================================
# Preference signal detection
# ===================================================================

PREFERENCE_SIGNALS = [

    # Explicit preference language
    r"\bi always\b",
    r"\bi never\b",
    r"\bi prefer\b",
    r"\bi'd prefer\b",
    r"\bmy preference\b",

    # Explicit persistent instructions
    r"\bplease always\b",
    r"\bplease never\b",
    r"\bplease remember\b",
    r"\bremember this\b",
    r"\bremember that\b",

    # Persistent preference language
    r"\bfrom now on\b",
    r"\bgoing forward\b",
    r"\bin the future\b",
    r"\bfor future\b",

    # Explicit constraints
    r"\bi do not\b",
    r"\bi don't\b",
    r"\bi will not\b",
    r"\bi won't\b",

    # Scheduling constraints
    r"\bdo not schedule\b",
    r"\bdon't schedule\b",

    # Communication preferences
    r"\bdo not send\b",
    r"\bdon't send\b",
    r"\bdo not call\b",
    r"\bdon't call\b",

    # Action-oriented preferences.
    # These are only candidate signals.
    # The security LLM decides whether they are safe.
    r"\bautomatically\b",
    r"\bwithout asking\b",
    r"\bwithout approval\b",
    r"\bwithout confirmation\b",
]


def has_preference_signal(text):
    """
    Detect whether text contains language that could represent
    a preference.

    This is only candidate detection.

    It does NOT mean that a persistent preference should be created.
    """

    if not text:
        return False

    text = text.lower()

    for pattern in PREFERENCE_SIGNALS:

        if re.search(
            pattern,
            text,
        ):
            return True

    return False


# ===================================================================
# Preference type detection
# ===================================================================

def detect_category(text):
    """
    Infer a simple preference category from the thread text.

    This is intentionally conservative.
    """

    text = text.lower()

    scheduling_terms = [
        "meeting",
        "meetings",
        "calendar",
        "schedule",
        "scheduling",
        "call",
        "calls",
        "appointment",
    ]

    communication_terms = [
        "reply",
        "email",
        "message",
        "respond",
        "communication",
    ]

    notification_terms = [
        "notification",
        "notifications",
        "alert",
        "alerts",
        "notify",
    ]

    email_handling_terms = [
        "archive",
        "delete",
        "inbox",
        "email",
        "emails",
    ]

    work_style_terms = [
        "work",
        "focus",
        "deep work",
        "working hours",
    ]

    if any(
        term in text
        for term in scheduling_terms
    ):
        return "scheduling"

    if any(
        term in text
        for term in notification_terms
    ):
        return "notifications"

    if any(
        term in text
        for term in email_handling_terms
    ):
        return "email_handling"

    if any(
        term in text
        for term in communication_terms
    ):
        return "communication"

    if any(
        term in text
        for term in work_style_terms
    ):
        return "work_style"

    return "general"


# ===================================================================
# Preference text extraction
# ===================================================================

def extract_preference_text(body):
    """
    Extract the relevant preference statement from the owner's body.

    Instead of returning only the first matching sentence, this
    preserves consecutive sentences that form the same preference.

    For example:

        I do not take meetings before 11:00am, ever.
        If anyone proposes something earlier, don't accept it --
        offer 11:00am or later instead.
        Please remember this for future scheduling.

    is kept as one preference statement.
    """

    if not body:
        return None

    sentences = re.split(
        r"(?<=[.!?])\s+",
        body.strip(),
    )

    selected = []

    preference_found = False

    for sentence in sentences:

        sentence = sentence.strip()

        if not sentence:
            continue

        if has_preference_signal(sentence):

            selected.append(sentence)
            preference_found = True

            continue

        # Once a preference has started, keep the immediately
        # following sentence because it may contain the operational
        # part of the preference.
        if preference_found:

            selected.append(sentence)

            # Stop after capturing the first non-signal sentence.
            break

    if not selected:
        return None

    return " ".join(selected)


# ===================================================================
# Candidate preference extraction
# ===================================================================

def extract_preference_candidate(
    thread_messages,
):
    """
    Extract a conservative preference candidate from a thread.

    IMPORTANT:

    Only explicit owner-authored statements are eligible for
    persistent preferences.

    Thread context from other participants may help explain the
    conversation, but it cannot create a persistent preference.
    """

    if not thread_messages:
        return None

    # ---------------------------------------------------------------
    # Search owner messages only.
    # ---------------------------------------------------------------

    owner_messages = [

        message

        for message in thread_messages

        if is_owner_message(message)

    ]

    if not owner_messages:
        return None

    # ---------------------------------------------------------------
    # Examine owner-authored messages.
    # ---------------------------------------------------------------

    for message in owner_messages:

        body = (
            message.get("body")
            or ""
        )

        subject = (
            message.get("subject")
            or ""
        )

        text = (
            f"{subject}\n{body}"
        ).strip()

        if not has_preference_signal(text):
            continue

        # -----------------------------------------------------------
        # Preserve the owner's original wording.
        # -----------------------------------------------------------

        preference_text = extract_preference_text(
            body,
        )

        if not preference_text:
            continue

        category = detect_category(
            text,
        )

        return {

            "preference":
                preference_text,

            "category":
                category,

            "source_message_id":
                message.get("id"),

            "source_thread_id":
                message.get("thread_id"),

            "is_explicit_owner_preference":
                True,

            "is_persistent":
                True,

            "extracted_at":
                utc_timestamp(),
        }

    return None


# ===================================================================
# Preference storage
# ===================================================================

def load_preferences():
    """
    Load persistent preferences.

    Returns:
        list[dict]
    """

    if not PREFERENCE_FILE.exists():
        return []

    try:

        with PREFERENCE_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        return data.get(
            "preferences",
            [],
        )

    return []


def save_preferences(
    preferences,
):
    """Persist preferences to disk."""

    PREFERENCE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {

        "updated_at":
            utc_timestamp(),

        "preferences":
            preferences,
    }

    PREFERENCE_FILE.write_text(

        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",

        encoding="utf-8",
    )


# ===================================================================
# Preference security audit
# ===================================================================

def load_preference_security_audit():
    """Load preference security validation records."""

    if not PREFERENCE_AUDIT_FILE.exists():
        return []

    try:

        with PREFERENCE_AUDIT_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        return data.get(
            "records",
            [],
        )

    return []


def save_preference_security_audit(
    records,
):
    """Persist preference security validation records."""

    PREFERENCE_AUDIT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {

        "updated_at":
            utc_timestamp(),

        "records":
            records,
    }

    PREFERENCE_AUDIT_FILE.write_text(

        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",

        encoding="utf-8",
    )


def record_preference_security_result(
    candidate,
    security_result,
):
    """
    Record the LLM security decision for a preference candidate.

    This creates an audit trail regardless of whether the candidate
    is accepted or rejected.
    """

    records = load_preference_security_audit()

    record = {

        "timestamp":
            utc_timestamp(),

        "source_message_id":
            candidate.get(
                "source_message_id",
            ),

        "source_thread_id":
            candidate.get(
                "source_thread_id",
            ),

        "preference":
            candidate.get(
                "preference",
            ),

        "category":
            candidate.get(
                "category",
            ),

        "decision":
            security_result.get(
                "decision",
                "UNKNOWN",
            ),

        "risk":
            security_result.get(
                "risk",
                "UNKNOWN",
            ),

        "reason":
            security_result.get(
                "reason",
                "",
            ),

        "model":
            security_result.get(
                "model",
                "",
            ),

        "raw_response":
            security_result.get(
                "raw_response",
                "",
            ),
    }

    records.append(record)

    save_preference_security_audit(
        records,
    )

    return record


# ===================================================================
# Preference identity
# ===================================================================

def preference_key(
    preference,
):
    """
    Build a stable key for a preference.

    Source message + category gives us a simple deterministic
    identity for this prototype.
    """

    return (
        preference.get(
            "source_message_id",
        ),
        preference.get(
            "category",
        ),
    )


# ===================================================================
# Add / update preference
# ===================================================================

def persist_preference(
    candidate,
    preferences=None,
):
    """
    Add a preference if it does not already exist.

    This function assumes that the candidate has already passed
    preference security validation.
    """

    if preferences is None:
        preferences = load_preferences()

    # ---------------------------------------------------------------
    # Defense-in-depth: only owner-authored candidates may persist.
    # ---------------------------------------------------------------

    if not candidate.get(
        "is_explicit_owner_preference",
        False,
    ):
        return (
            preferences,
            False,
        )

    key = preference_key(
        candidate,
    )

    # ---------------------------------------------------------------
    # Avoid duplicate insertion.
    # ---------------------------------------------------------------

    for existing in preferences:

        if preference_key(
            existing,
        ) == key:

            return (
                preferences,
                False,
            )

    # ---------------------------------------------------------------
    # Assign an ID.
    # ---------------------------------------------------------------

    candidate = dict(
        candidate,
    )

    candidate["id"] = (
        f"pref_{len(preferences) + 1:03d}"
    )

    candidate["status"] = "active"

    preferences.append(
        candidate,
    )

    save_preferences(
        preferences,
    )

    return (
        preferences,
        True,
    )


# ===================================================================
# Process safe threads
# ===================================================================

def extract_preferences_from_threads(
    raw_threads,
):
    """
    Extract persistent preferences from safe threads.

    Args:
        raw_threads:
            dict mapping thread_id -> list[raw message dict]

    Returns:
        {
            "preferences": [...],
            "candidates": [...],
            "new_preferences": [...],
            "rejected_preferences": [...]
        }

    IMPORTANT:

    A candidate is persisted only after it passes the preference
    security validation performed by preference_security.py.
    """

    # Import here to avoid circular imports and keep the preference
    # extraction module usable on its own.
    from preference_security import (
        validate_preference_security,
    )

    preferences = load_preferences()

    candidates = []

    new_preferences = []

    rejected_preferences = []

    for thread_id, messages in raw_threads.items():

        candidate = extract_preference_candidate(
            messages,
        )

        if candidate is None:
            continue

        # Ensure thread ID is present even if the source message
        # itself did not contain one.

        if not candidate.get(
            "source_thread_id",
        ):

            candidate[
                "source_thread_id"
            ] = thread_id

        candidates.append(
            candidate,
        )

        # -----------------------------------------------------------
        # Security validation happens BEFORE persistence.
        # -----------------------------------------------------------

        security_result = (
            validate_preference_security(
                candidate,
            )
        )

        # Store the validation result with the candidate for
        # downstream reporting.
        candidate["security_validation"] = {
            "decision":
                security_result.get(
                    "decision",
                    "UNKNOWN",
                ),

            "risk":
                security_result.get(
                    "risk",
                    "UNKNOWN",
                ),

            "reason":
                security_result.get(
                    "reason",
                    "",
                ),

            "model":
                security_result.get(
                    "model",
                    "",
                ),
        }

        record_preference_security_result(
            candidate,
            security_result,
        )

        # -----------------------------------------------------------
        # Only SAFE_PREFERENCE can be persisted.
        # -----------------------------------------------------------

        if security_result.get(
            "decision",
        ) != "SAFE_PREFERENCE":

            rejected_preferences.append(
                candidate,
            )

            continue

        (
            preferences,
            changed,
        ) = persist_preference(
            candidate,
            preferences,
        )

        if changed:

            new_preferences.append(
                candidate,
            )

    return {

        "preferences":
            preferences,

        "candidates":
            candidates,

        "new_preferences":
            new_preferences,

        "rejected_preferences":
            rejected_preferences,
    }


# ===================================================================
# Format preferences for an LLM prompt
# ===================================================================

def format_preferences_for_prompt(
    preferences,
):
    """
    Convert persistent preferences into compact LLM context.
    """

    if not preferences:

        return (
            "OWNER PREFERENCES\n"
            "None recorded."
        )

    lines = [

        "OWNER PREFERENCES",

        "=================",
    ]

    for preference in preferences:

        if preference.get(
            "status",
        ) != "active":

            continue

        category = (
            preference.get(
                "category",
                "general",
            )
        )

        text = (
            preference.get(
                "preference",
                "",
            )
        )

        source = (
            preference.get(
                "source_message_id",
                "unknown",
            )
        )

        lines.append(
            f"- [{category}] {text} "
            f"(source: {source})"
        )

    if len(lines) == 2:

        lines.append(
            "None recorded."
        )

    return "\n".join(
        lines,
    )


# ===================================================================
# CLI test
# ===================================================================

if __name__ == "__main__":

    print(
        "Persistent preferences:"
    )

    preferences = load_preferences()

    if not preferences:

        print(
            "  None"
        )

    else:

        for preference in preferences:

            print(
                f"  [{preference['category']}] "
                f"{preference['preference']} "
                f"(source: "
                f"{preference['source_message_id']})"
            )