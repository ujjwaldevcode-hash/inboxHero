"""
Deterministic guard for irreversible or high-impact instructions.

This module does not execute any action.

Its purpose is to detect instructions that attempt to:
- send messages without approval
- delete data
- approve/transfer payments
- change credentials
- forward sensitive information
- disable security
- bypass confirmation/approval

The guard returns a refusal decision. The actual human approval/action
mechanism remains separate.
"""


IRREVERSIBLE_ACTION_PATTERNS = [
    # Explicit sending
    ("send", "send this email"),
    ("send", "send the message"),
    ("send", "send this reply"),
    ("send", "send the drafted response"),
    ("send", "send the draft"),
    ("send", "automatically send"),

    # Deletion
    ("delete", "delete the email"),
    ("delete", "delete all"),
    ("delete", "permanently delete"),
    ("delete", "remove all emails"),

    # Payments
    ("payment", "approve the payment"),
    ("payment", "transfer the money"),
    ("payment", "wire the money"),

    # Credentials / access
    ("credentials", "change the password"),
    ("credentials", "change the credentials"),
    ("credentials", "reset the password"),

    # Forwarding sensitive information
    ("forward", "forward the full contents"),
    ("forward", "forward all messages"),
    ("forward", "send the full contents"),

    # Security controls
    ("security", "disable security"),
    ("security", "disable the security controls"),
]


APPROVAL_BYPASS_PATTERNS = [
    "without asking",
    "without approval",
    "skip confirmation",
    "without confirmation",
    "do not ask me",
    "don't ask me",
]


def detect_irreversible_instruction(text):
    """
    Detect an irreversible/high-impact instruction.

    An instruction is considered dangerous when either:

    1. It explicitly contains a known irreversible action, OR
    2. It contains an irreversible action together with an approval bypass.

    Returns None when no dangerous instruction is detected.
    """

    if not text:
        return None

    normalized = text.lower()

    # ---------------------------------------------------------
    # Check explicit irreversible action patterns
    # ---------------------------------------------------------

    for action_type, pattern in IRREVERSIBLE_ACTION_PATTERNS:

        if pattern in normalized:
            return {
                "detected": True,
                "action_type": action_type,
                "matched_pattern": pattern,
            }

    # ---------------------------------------------------------
    # Check generic action + approval bypass combinations
    # ---------------------------------------------------------

    action_keywords = {
        "send": [
            "send ",
            "sending ",
        ],
        "delete": [
            "delete ",
            "deleting ",
            "remove ",
            "removing ",
        ],
        "payment": [
            "approve the payment",
            "transfer the money",
            "wire the money",
        ],
        "credentials": [
            "change the password",
            "change the credentials",
            "reset the password",
        ],
        "forward": [
            "forward ",
        ],
    }

    for action_type, keywords in action_keywords.items():

        action_found = any(
            keyword in normalized
            for keyword in keywords
        )

        if not action_found:
            continue

        bypass_found = any(
            pattern in normalized
            for pattern in APPROVAL_BYPASS_PATTERNS
        )

        if bypass_found:
            return {
                "detected": True,
                "action_type": action_type,
                "matched_pattern": "action + approval bypass",
            }

    return None


def refuse_irreversible_action(text):
    """
    Produce the security decision for an irreversible instruction.

    No action is executed by this function.
    """

    detection = detect_irreversible_instruction(text)

    if detection is None:
        return {
            "decision": "ALLOW_NORMAL_PROCESSING",
            "refused": False,
            "reason": None,
            "action_type": None,
            "matched_pattern": None,
        }

    return {
        "decision": "REFUSE",
        "refused": True,
        "reason": (
            "The message contains an instruction for an irreversible "
            "or high-impact action. Explicit human approval is required."
        ),
        "action_type": detection["action_type"],
        "matched_pattern": detection["matched_pattern"],
    }