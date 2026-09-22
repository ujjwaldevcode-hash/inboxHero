#!/usr/bin/env python3

"""
InboxHero - Security-First Phase 3 Pipeline

Architecture:

    INBOX
      |
      v
    SECURITY GATE
      |
      +---- THREAT ----> QUARANTINE
      |
      +---- SAFE ------> THREAD GROUPING
                              |
                              v
                       PREFERENCE EXTRACTION
                              |
                              v
                     PERSISTENT PREFERENCES
                              |
                              v
                            TRIAGE
                              |
                 +------------+------------+
                 |            |            |
              ARCHIVE     ACTIONABLE    IMPORTANT
                 |            |            |
                 v            +-----+------+
              DIGEST                |
                                    v
                                LLM AGENT

Security invariant:

    A message classified as THREAT must never reach:

        - preference extraction
        - normal thread processing
        - normal LLM agent processing
        - downstream actions

Irreversible-action invariant:

    A message containing an irreversible/high-impact instruction must
    never reach:

        - preference persistence
        - normal LLM agent processing
        - downstream actions

    It must be refused and routed for human review.

Preference invariant:

    Only SAFE threads are eligible for preference extraction.

    Only explicit owner-authored preferences can become persistent
    preferences in the current prototype.
"""


import json
import sys
import time

from collections import Counter, defaultdict
from pathlib import Path


# ===================================================================
# PROJECT PATHS
# ===================================================================

# Final integrated structure:
#
# inboxhero_dev/
# ├── config.py
# ├── inbox.json
# ├── inboxhero/
# ├── security_gate.py
# ├── threat_labeler.py
# ├── irreversible_actions.py
# ├── preferences.py
# ├── preference_security.py
# ├── noise_filter.py
# ├── quadrant_triage.py
# ├── pipeline.py
# └── outputs/

PROJECT_ROOT = Path(__file__).resolve().parent

INBOX_FILE = PROJECT_ROOT / "inbox.json"

OUTPUT_DIR = PROJECT_ROOT / "outputs"

OUTPUT_FILE = (
    OUTPUT_DIR
    / "pipeline_results.json"
)

AUDIT_FILE = (
    OUTPUT_DIR
    / "pipeline_audit.json"
)


# ===================================================================
# SECURITY GATE
# ===================================================================

from security_gate import scan_message
from threat_labeler import label_threat


# ===================================================================
# NORMAL INBOXHERO IMPORTS
# ===================================================================

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from inboxhero.loader import load_inbox
from inboxhero.rules import decide_message
from inboxhero.agent import decide
from inboxhero.llm import LLMClient


# ===================================================================
# IRREVERSIBLE ACTION GUARD
# ===================================================================

from irreversible_actions import refuse_irreversible_action


# ===================================================================
# EXPERIMENTAL NOISE + QUADRANT TRIAGE
# ===================================================================

from noise_filter import filter_generic_noise
from quadrant_triage import classify, build_quadrant_summary


# ===================================================================
# PREFERENCE IMPORTS
# ===================================================================

from preferences import (
    extract_preferences_from_threads,
    format_preferences_for_prompt,
)


# ===================================================================
# CONFIG DIAGNOSTIC
# ===================================================================

LOADED_CONFIG = sys.modules.get(
    "config"
)

if LOADED_CONFIG is not None:

    loaded_config_path = getattr(
        LOADED_CONFIG,
        "__file__",
        None
    )

    if loaded_config_path:

        print(
            f"[config] Using: {loaded_config_path}"
        )


# ===================================================================
# LOAD RAW INBOX
# ===================================================================

def load_raw_messages():
    """
    Load raw inbox JSON.

    Returns:
        list[dict]
    """

    with INBOX_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    if isinstance(data, list):

        return data

    if isinstance(data, dict):

        return data["messages"]

    raise ValueError(
        "Unexpected inbox.json structure."
    )


# ===================================================================
# RAW MESSAGE HELPERS
# ===================================================================

def raw_message_id(message):
    """
    Return message ID from a raw JSON dictionary.
    """

    return message.get(
        "id"
    )


def raw_message_thread(message):
    """
    Return thread ID from a raw JSON dictionary.
    """

    return (
        message.get(
            "thread_id"
        )
        or
        f"message:{raw_message_id(message)}"
    )


# ===================================================================
# INBOXHERO MESSAGE HELPERS
# ===================================================================

def object_message_thread(message):
    """
    Return thread ID from an InboxHero Message object.
    """

    return (
        getattr(
            message,
            "thread_id",
            None
        )
        or
        f"message:{message.id}"
    )


# ===================================================================
# THREAD GROUPING
# ===================================================================

def group_threads(messages):
    """
    Group safe InboxHero Message objects by thread.

    IMPORTANT:

    This function receives only messages that passed the security
    gate.
    """

    threads = defaultdict(list)

    for message in messages:

        thread_id = object_message_thread(
            message
        )

        threads[
            thread_id
        ].append(
            message
        )

    return dict(
        threads
    )


def group_raw_threads(messages):
    """
    Group safe raw message dictionaries by thread.

    This representation is used by preference extraction.
    """

    threads = defaultdict(list)

    for message in messages:

        thread_id = raw_message_thread(
            message
        )

        threads[
            thread_id
        ].append(
            message
        )

    return dict(
        threads
    )


# ===================================================================
# TRIAGE ROUTING
# ===================================================================

def route_triage(
    disposition,
    risk
):
    """
    Convert InboxHero disposition into a Phase 3 route.

    Existing InboxHero dispositions:

        archive
        reply
        delegate
        defer
        escalate

    Phase 3 routes:

        ARCHIVE
        ACTIONABLE
        IMPORTANT
    """

    if disposition == "archive":

        return "ARCHIVE"

    if disposition in {
        "reply",
        "delegate",
    }:

        return "ACTIONABLE"

    if disposition in {
        "defer",
        "escalate",
    }:

        return "IMPORTANT"

    # Fail-safe:
    # Unknown dispositions should not silently disappear.

    return "IMPORTANT"


# ===================================================================
# MAIN PIPELINE
# ===================================================================

def run_pipeline():

    # ---------------------------------------------------------------
    # Prepare output directory
    # ---------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # ---------------------------------------------------------------
    # Load raw messages and InboxHero Message objects
    # ---------------------------------------------------------------

    raw_messages = load_raw_messages()

    messages = load_inbox(
        INBOX_FILE
    )

    # ---------------------------------------------------------------
    # Basic accounting
    # ---------------------------------------------------------------

    if len(raw_messages) != len(messages):

        raise RuntimeError(
            "Raw inbox and InboxHero inbox contain different "
            f"message counts: "
            f"{len(raw_messages)} vs {len(messages)}"
        )

    message_objects_by_id = {
        message.id: message
        for message in messages
    }

    if not message_objects_by_id:

        raise RuntimeError(
            "No InboxHero Message objects were loaded."
        )

    # ---------------------------------------------------------------
    # HEADER
    # ---------------------------------------------------------------

    print()
    print("=" * 72)
    print("InboxHero - Security-First Phase 3")
    print("=" * 72)

    print()

    print(
        f"Messages loaded: {len(messages)}"
    )

    print()

    print("Pipeline:")
    print("  Security Gate")
    print("       |")
    print("       +---- THREAT ----> Quarantine")
    print("       |")
    print("       +---- SAFE ------> Thread")
    print("                              |")
    print("                              v")
    print("                       Preferences")
    print("                              |")
    print("                              v")
    print("                    Irreversible Guard")
    print("                              |")
    print("                              v")
    print("                            Triage")
    print("                              |")
    print("                              v")
    print("                            Agent")

    # ===============================================================
    # PHASE 1 — SECURITY GATE
    # ===============================================================

    print()
    print("-" * 72)
    print("PHASE 1 — SECURITY GATE")
    print("-" * 72)

    threat_records = []

    threat_message_ids = set()

    security_start = time.perf_counter()

    # ---------------------------------------------------------------
    # IMPORTANT:
    #
    # Security receives RAW dictionaries.
    # ---------------------------------------------------------------

    for index, raw_message in enumerate(
        raw_messages,
        start=1
    ):

        message_id = raw_message_id(
            raw_message
        )

        decision = scan_message(
            raw_message
        )

        if decision.final_decision == "THREAT":

            # -------------------------------------------------------
            # Label an already-detected threat.
            # -------------------------------------------------------

            threat_label = label_threat(
                raw_message
            )

            threat_message_ids.add(
                message_id
            )

            threat_records.append({

                "message_id":
                    message_id,

                "thread_id":
                    raw_message_thread(
                        raw_message
                    ),

                "security_decision":
                    "THREAT",

                "decision_source":
                    decision.decision_source,

                "gate_agreement":
                    decision.gate_agreement,

                "rule_gate":
                    decision.rule_gate,

                "granite_gate":
                    decision.granite_gate,

                "threat_label":
                    threat_label,

                "normal_agent_processing":
                    False,

                "preference_extraction":
                    False,

                "quarantined":
                    True,
            })

            print(
                f"[{index:03d}/{len(raw_messages)}] "
                f"{message_id} -> THREAT -> QUARANTINE"
            )

        else:

            print(
                f"[{index:03d}/{len(raw_messages)}] "
                f"{message_id} -> SAFE"
            )

    security_time = (
        time.perf_counter()
        - security_start
    )

    # ===============================================================
    # SECURITY BOUNDARY
    # ===============================================================

    # ---------------------------------------------------------------
    # SAFE RAW MESSAGES
    #
    # Used for preference extraction.
    # ---------------------------------------------------------------

    safe_raw_messages = [

        message

        for message in raw_messages

        if message.get("id")
        not in threat_message_ids
    ]

    # ---------------------------------------------------------------
    # SAFE MESSAGE OBJECTS
    #
    # Used for normal InboxHero processing.
    # ---------------------------------------------------------------

    safe_message_objects = [

        message

        for message in messages

        if message.id
        not in threat_message_ids
    ]

    # ---------------------------------------------------------------
    # Security accounting invariant
    # ---------------------------------------------------------------

    if (
        len(threat_message_ids)
        + len(safe_message_objects)
        != len(messages)
    ):

        raise RuntimeError(
            "Security boundary accounting failed: "
            "threat + safe != total messages."
        )

    # ===============================================================
    # IRREVERSIBLE ACTION SCREEN
    # ===============================================================

    # This is a second security boundary after the threat gate.
    #
    # Threat messages have already been quarantined above.
    # Safe messages are screened here for explicit irreversible or
    # high-impact instructions. Refused messages are excluded from
    # preference extraction and normal agent processing.

    irreversible_refusals = []
    irreversible_message_ids = set()

    for raw_message in safe_raw_messages:

        irreversible_result = refuse_irreversible_action(
            raw_message.get("body", "")
        )

        if irreversible_result["refused"]:

            message_id = raw_message_id(
                raw_message
            )

            irreversible_message_ids.add(
                message_id
            )

            irreversible_refusals.append({

                "message_id":
                    message_id,

                "thread_id":
                    raw_message_thread(
                        raw_message
                    ),

                "decision":
                    "REFUSE",

                "action_type":
                    irreversible_result[
                        "action_type"
                    ],

                "matched_pattern":
                    irreversible_result[
                        "matched_pattern"
                    ],

                "reason":
                    irreversible_result[
                        "reason"
                    ],

                "human_review_required":
                    True,

                "agent_called":
                    False,

                "action_executed":
                    False,

                "normal_processing_blocked":
                    True,
            })

    # ---------------------------------------------------------------
    # Messages eligible for normal processing.
    # ---------------------------------------------------------------

    normal_raw_messages = [
        message
        for message in safe_raw_messages
        if message.get("id")
        not in irreversible_message_ids
    ]

    normal_message_objects = [
        message
        for message in safe_message_objects
        if message.id
        not in irreversible_message_ids
    ]

    # ===============================================================
    # GENERIC NOISE FILTER
    # ===============================================================
    #
    # Only common, low-value informational mail is removed here.
    # Security threats and irreversible-action messages were already
    # stopped above. Owner-authored mail, deadlines, requests,
    # incidents, approvals, security alerts, etc. remain eligible.
    #
    # Noise is recorded as Q4/archive without an LLM call.

    meaningful_raw_messages, noise_records = filter_generic_noise(
        normal_raw_messages
    )

    noise_message_ids = {
        item["message_id"]
        for item in noise_records
    }

    normal_raw_messages = meaningful_raw_messages

    normal_message_objects = [
        message
        for message in normal_message_objects
        if message.id not in noise_message_ids
    ]

    print()
    print(
        f"Irreversible-action refusals: "
        f"{len(irreversible_refusals)}"
    )

    print(
        f"Generic noise filtered: "
        f"{len(noise_records)}"
    )

    for noise in noise_records:
        print(
            f"  {noise['message_id']} -> "
            f"Q4 -> ARCHIVE -> "
            f"{noise['category']}"
        )

    for refusal in irreversible_refusals:

        print(
            f"  {refusal['message_id']} -> "
            f"REFUSE -> "
            f"{refusal['action_type']} -> "
            f"HUMAN REVIEW"
        )

    # ===============================================================
    # PHASE 2 — THREAD GROUPING
    # ===============================================================

    print()
    print("-" * 72)
    print("PHASE 2 — THREAD GROUPING")
    print("-" * 72)

    # ---------------------------------------------------------------
    # Message-object threads
    #
    # Used by normal InboxHero processing.
    # ---------------------------------------------------------------

    safe_threads = group_threads(
        normal_message_objects
    )

    # ---------------------------------------------------------------
    # Raw threads
    #
    # Used by preference extraction.
    # ---------------------------------------------------------------

    safe_raw_threads = group_raw_threads(
        normal_raw_messages
    )

    print(
        f"Normal messages grouped into "
        f"{len(safe_threads)} threads"
    )

    # ===============================================================
    # PHASE 3 — PREFERENCE EXTRACTION
    # ===============================================================

    print()
    print("-" * 72)
    print("PHASE 3 — PREFERENCE EXTRACTION")
    print("-" * 72)

    preference_result = (
        extract_preferences_from_threads(
            safe_raw_threads
        )
    )

    preferences = (
        preference_result[
            "preferences"
        ]
    )

    preference_candidates = (
        preference_result[
            "candidates"
        ]
    )

    new_preferences = (
        preference_result[
            "new_preferences"
        ]
    )

    # ---------------------------------------------------------------
    # Format persistent preference context.
    #
    # This will be injected into LLM prompts in the next phase.
    #
    # We prepare it here, but DO NOT modify the existing LLM API yet.
    # ---------------------------------------------------------------

    preference_context = (
        format_preferences_for_prompt(
            preferences
        )
    )

    print(
        f"Preference candidates : "
        f"{len(preference_candidates)}"
    )

    print(
        f"New preferences       : "
        f"{len(new_preferences)}"
    )

    print(
        f"Total active prefs    : "
        f"{len(preferences)}"
    )

    if new_preferences:

        print()

        for preference in new_preferences:

            print(
                f"  [{preference['category']}] "
                f"{preference['preference']} "
                f"(source: "
                f"{preference['source_message_id']})"
            )

    else:

        print(
            "  No new persistent preferences."
        )

    # ===============================================================
    # PHASE 4 — FOUR-QUADRANT INBOX TRIAGE
    # ===============================================================

    print()
    print("-" * 72)
    print("PHASE 4 — FOUR-QUADRANT INBOX TRIAGE")
    print("-" * 72)

    triage_results = []

    # Every meaningful, safe message now receives the same priority model:
    #
    #     Q1 = urgent + important
    #     Q2 = not urgent + important
    #     Q3 = urgent + not important
    #     Q4 = not urgent + not important
    #
    # Generic Q4 noise has already been removed deterministically and
    # therefore does not consume an LLM request.

    client = None

    for message in normal_message_objects:

        if client is None:
            client = LLMClient()

        quadrant_result = classify(
            message,
            client
        )

        triage_results.append({
            "message_id": message.id,
            "thread_id": object_message_thread(message),
            "urgent": quadrant_result["urgent"],
            "important": quadrant_result["important"],
            "quadrant": quadrant_result["quadrant"],
            "quadrant_title": {
                "Q1": "For Your Action or Response",
                "Q2": "Schedule / Follow Up",
                "Q3": "Delegate",
                "Q4": "Archive",
            }[quadrant_result["quadrant"]],
            "disposition": quadrant_result["disposition"],
            "reason": quadrant_result["reason"],
            "risk": (
                "high"
                if quadrant_result["disposition"] == "escalate"
                else "medium"
            ),
            "route": route_triage(
                quadrant_result["disposition"],
                "high"
                if quadrant_result["disposition"] == "escalate"
                else "medium"
            ),
            "processing_path": "QUADRANT_LLM",
        })

    quadrant_summary = build_quadrant_summary(
        triage_results,
        noise_count=len(noise_records),
    )

    rule_count = 0
    agent_count = len(triage_results)

    # ===============================================================
    # PHASE 5 — DOWNSTREAM ROUTING
    # ===============================================================


    print()
    print("-" * 72)
    print("PHASE 5 — DOWNSTREAM ROUTING")
    print("-" * 72)

    downstream = []

    for item in triage_results:

        # -----------------------------------------------------------
        # ARCHIVE
        # -----------------------------------------------------------

        if item["route"] == "ARCHIVE":

            downstream.append({

                "message_id":
                    item["message_id"],

                "route":
                    "ARCHIVE",

                "agent_called":
                    item["processing_path"]
                    == "LLM_AGENT",

                "action":
                    "DIGEST_ELIGIBLE",
            })

        # -----------------------------------------------------------
        # ACTIONABLE
        # -----------------------------------------------------------

        elif item["route"] == "ACTIONABLE":

            downstream.append({

                "message_id":
                    item["message_id"],

                "route":
                    "ACTIONABLE",

                "agent_called":
                    item["processing_path"]
                    == "LLM_AGENT",

                "action":
                    "REPLY_OR_DELEGATE",
            })

        # -----------------------------------------------------------
        # IMPORTANT
        # -----------------------------------------------------------

        else:

            downstream.append({

                "message_id":
                    item["message_id"],

                "route":
                    "IMPORTANT",

                "agent_called":
                    item["processing_path"]
                    == "LLM_AGENT",

                "action":
                    "REVIEW_REQUIRED",
            })

    # ===============================================================
    # SECURITY INVARIANT CHECK
    # ===============================================================

    print()
    print("-" * 72)
    print("SECURITY INVARIANT CHECK")
    print("-" * 72)

    # ---------------------------------------------------------------
    # IDs that reached normal LLM agent.
    # ---------------------------------------------------------------

    agent_message_ids = {

        item["message_id"]

        for item in triage_results

        if item["processing_path"]
        == "LLM_AGENT"
    }

    # ---------------------------------------------------------------
    # IDs that reached preference extraction.
    #
    # Preference extraction operates on safe_raw_messages only.
    # ---------------------------------------------------------------

    preference_message_ids = {

        message.get("id")

        for message in normal_raw_messages
    }

    # ---------------------------------------------------------------
    # Check for threat -> preference leakage.
    # ---------------------------------------------------------------

    threats_reaching_preferences = sorted(
        threat_message_ids
        &
        preference_message_ids
    )

    # ---------------------------------------------------------------
    # Check for threat -> agent leakage.
    # ---------------------------------------------------------------

    leaked_to_agent = sorted(
        threat_message_ids
        &
        agent_message_ids
    )

    # ---------------------------------------------------------------
    # Check for irreversible instruction -> normal agent leakage.
    # ---------------------------------------------------------------

    irreversible_reaching_agent = sorted(
        irreversible_message_ids
        &
        agent_message_ids
    )

    irreversible_reaching_preferences = sorted(
        irreversible_message_ids
        &
        preference_message_ids
    )

    security_invariant_passed = (

        len(
            threats_reaching_preferences
        ) == 0

        and

        len(
            leaked_to_agent
        ) == 0

        and

        len(
            irreversible_reaching_preferences
        ) == 0

        and

        len(
            irreversible_reaching_agent
        ) == 0
    )

    print(
        "Threats reaching preference extraction: "
        f"{len(threats_reaching_preferences)}"
    )

    print(
        "Threats reaching normal agent: "
        f"{len(leaked_to_agent)}"
    )

    print(
        "Irreversible instructions reaching preferences: "
        f"{len(irreversible_reaching_preferences)}"
    )

    print(
        "Irreversible instructions reaching normal agent: "
        f"{len(irreversible_reaching_agent)}"
    )

    if threats_reaching_preferences:

        print()
        print(
            "THREATS REACHING PREFERENCE EXTRACTION:"
        )

        for message_id in (
            threats_reaching_preferences
        ):

            print(
                f"  - {message_id}"
            )

    if leaked_to_agent:

        print()
        print(
            "THREATS REACHING NORMAL AGENT:"
        )

        for message_id in leaked_to_agent:

            print(
                f"  - {message_id}"
            )

    print(
        "STATUS: "
        + (
            "PASS"
            if security_invariant_passed
            else "FAIL"
        )
    )

    # ===============================================================
    # SUMMARY COUNTS
    # ===============================================================

    route_counts = Counter(
        item["route"]
        for item in triage_results
    )

    processing_counts = Counter(
        item["processing_path"]
        for item in triage_results
    )

    # ===============================================================
    # RESULT OBJECT
    # ===============================================================

    result = {

        "architecture":
            "security_first_v4_quadrants",

        "messages_processed":
            len(messages),

        "security": {

            "threat_count":
                len(threat_records),

            "safe_count":
                len(safe_message_objects),

            "quarantined_count":
                len(threat_records),

            "irreversible_action_refusal_count":
                len(irreversible_refusals),

            "security_runtime_seconds":
                round(
                    security_time,
                    4
                ),
        },

        "irreversible_action_refusals":
            irreversible_refusals,

        "thread_grouping": {

            "safe_messages":
                len(safe_message_objects),

            "irreversible_blocked_messages":
                len(irreversible_message_ids),

            "generic_noise_filtered":
                len(noise_records),

            "normal_messages":
                len(normal_message_objects),

            "safe_threads":
                len(safe_threads),
        },

        "noise_filter": {
            "filtered_count": len(noise_records),
            "records": noise_records,
        },

        "preferences": {

            "candidate_count":
                len(preference_candidates),

            "new_count":
                len(new_preferences),

            "active_count":
                len(preferences),

            "items":
                preferences,

            "context":
                preference_context,
        },

        "triage": {

            "model":
                getattr(client, "model", None),

            "quadrant_llm_handled":
                agent_count,

            "generic_noise_filtered":
                len(noise_records),

            "archive":
                route_counts["ARCHIVE"],

            "actionable":
                route_counts["ACTIONABLE"],

            "important":
                route_counts["IMPORTANT"],

            "quadrant_counts":
                quadrant_summary["quadrant_counts"],

            "disposition_counts":
                quadrant_summary["disposition_counts"],

            "sections":
                quadrant_summary["sections"],
        },

        "processing_paths": {

            "QUADRANT_LLM":
                processing_counts["QUADRANT_LLM"],

            "NOISE_FILTER":
                len(noise_records),

            "IRREVERSIBLE_REFUSAL":
                len(irreversible_refusals),
        },

        "security_invariant": {

            "threats_reaching_preference_extraction":
                len(
                    threats_reaching_preferences
                ),

            "threats_reaching_agent":
                len(
                    leaked_to_agent
                ),

            "threat_message_ids_reaching_preference_extraction":
                threats_reaching_preferences,

            "threat_message_ids_reaching_agent":
                leaked_to_agent,

            "irreversible_instructions_reaching_preferences":
                irreversible_reaching_preferences,

            "irreversible_instructions_reaching_agent":
                irreversible_reaching_agent,

            "passed":
                security_invariant_passed,
        },

        "threats":
            threat_records,

        "safe_triage":
            triage_results,

        "downstream":
            downstream,
    }

    # ===============================================================
    # AUDIT
    # ===============================================================

    audit = []

    # ---------------------------------------------------------------
    # Threat audit
    # ---------------------------------------------------------------

    for record in threat_records:

        audit.append({

            "message_id":
                record["message_id"],

            "security_decision":
                "THREAT",

            "final_route":
                "QUARANTINE",

            "preference_extraction":
                False,

            "agent_called":
                False,

            "normal_processing_blocked":
                True,

            "irreversible_action_refused":
                False,

            "human_review_required":
                True,

            "action_executed":
                False,
        })

    # ---------------------------------------------------------------
    # Irreversible-action refusal audit
    # ---------------------------------------------------------------

    for record in irreversible_refusals:

        audit.append({

            "message_id":
                record["message_id"],

            "security_decision":
                "SAFE",

            "final_route":
                "IMPORTANT",

            "preference_extraction":
                False,

            "agent_called":
                False,

            "normal_processing_blocked":
                True,

            "irreversible_action_refused":
                True,

            "human_review_required":
                True,

            "action_executed":
                False,

            "action_type":
                record["action_type"],

            "matched_pattern":
                record["matched_pattern"],
        })

    # ---------------------------------------------------------------
    # Generic-noise audit
    # ---------------------------------------------------------------

    for record in noise_records:

        audit.append({

            "message_id":
                record["message_id"],

            "security_decision":
                "SAFE",

            "final_route":
                "ARCHIVE",

            "quadrant":
                "Q4",

            "preference_extraction":
                False,

            "agent_called":
                False,

            "normal_processing_blocked":
                False,

            "generic_noise_filtered":
                True,

            "noise_category":
                record["category"],

            "reason":
                record["reason"],

            "irreversible_action_refused":
                False,

            "human_review_required":
                False,

            "action_executed":
                False,
        })

    # ---------------------------------------------------------------
    # Safe-message audit
    # ---------------------------------------------------------------

    for item in triage_results:

        audit.append({

            "message_id":
                item["message_id"],

            "security_decision":
                "SAFE",

            "final_route":
                item["route"],

            "quadrant":
                item["quadrant"],

            "disposition":
                item["disposition"],

            "reason":
                item["reason"],

            "preference_extraction":
                True,

            "agent_called":
                item["processing_path"]
                == "QUADRANT_LLM",

            "normal_processing_blocked":
                False,

            "irreversible_action_refused":
                False,

            "human_review_required":
                False,

            "action_executed":
                False,
        })

    # ---------------------------------------------------------------
    # Preserve original inbox order
    # ---------------------------------------------------------------

    inbox_order = {

        message.id: index

        for index, message
        in enumerate(messages)
    }

    audit.sort(
        key=lambda item:
        inbox_order[
            item["message_id"]
        ]
    )

    # ===============================================================
    # SAVE OUTPUTS
    # ===============================================================

    OUTPUT_FILE.write_text(

        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
        + "\n",

        encoding="utf-8",
    )

    AUDIT_FILE.write_text(

        json.dumps(
            audit,
            indent=2,
            ensure_ascii=False
        )
        + "\n",

        encoding="utf-8",
    )

    # ===============================================================
    # FINAL SUMMARY
    # ===============================================================

    print()
    print("=" * 72)
    print("PHASE 3 SUMMARY")
    print("=" * 72)

    print()

    print(
        f"Messages processed       : "
        f"{len(messages)}"
    )

    print()

    print("SECURITY")

    print(
        f"  Threat                 : "
        f"{len(threat_records)}"
    )

    print(
        f"  Safe                   : "
        f"{len(safe_message_objects)}"
    )

    print(
        f"  Quarantined            : "
        f"{len(threat_records)}"
    )

    print(
        f"  Irreversible refused   : "
        f"{len(irreversible_refusals)}"
    )

    print()

    print("THREAD GROUPING")

    print(
        f"  Safe messages          : "
        f"{len(safe_message_objects)}"
    )

    print(
        f"  Irreversible blocked   : "
        f"{len(irreversible_message_ids)}"
    )

    print(
        f"  Normal messages        : "
        f"{len(normal_message_objects)}"
    )

    print(
        f"  Safe threads           : "
        f"{len(safe_threads)}"
    )

    print()

    print("PREFERENCES")

    print(
        f"  Candidates             : "
        f"{len(preference_candidates)}"
    )

    print(
        f"  New                   : "
        f"{len(new_preferences)}"
    )

    print(
        f"  Active                : "
        f"{len(preferences)}"
    )

    print()

    print("TRIAGE")

    print(
        f"  Generic noise filtered : "
        f"{len(noise_records)}"
    )

    print(
        f"  Quadrant LLM handled   : "
        f"{agent_count}"
    )

    print(
        f"  Q1 Action/Response     : "
        f"{quadrant_summary['quadrant_counts'].get('Q1', 0)}"
    )

    print(
        f"  Q2 Schedule/Follow Up : "
        f"{quadrant_summary['quadrant_counts'].get('Q2', 0)}"
    )

    print(
        f"  Q3 Delegate            : "
        f"{quadrant_summary['quadrant_counts'].get('Q3', 0)}"
    )

    print(
        f"  Q4 Archive             : "
        f"{quadrant_summary['quadrant_counts'].get('Q4', 0)}"
    )

    print(
        f"  Reply                  : "
        f"{quadrant_summary['disposition_counts'].get('reply', 0)}"
    )

    print(
        f"  Escalate               : "
        f"{quadrant_summary['disposition_counts'].get('escalate', 0)}"
    )

    print(
        f"  Defer                  : "
        f"{quadrant_summary['disposition_counts'].get('defer', 0)}"
    )

    print(
        f"  Delegate               : "
        f"{quadrant_summary['disposition_counts'].get('delegate', 0)}"
    )

    print(
        f"  Archive                : "
        f"{quadrant_summary['disposition_counts'].get('archive', 0)}"
    )

    print()

    print("SECURITY INVARIANT")

    print(
        f"  Threats reaching prefs : "
        f"{len(threats_reaching_preferences)}"
    )

    print(
        f"  Threats reaching agent : "
        f"{len(leaked_to_agent)}"
    )

    print(
        f"  Irrev. -> preferences  : "
        f"{len(irreversible_reaching_preferences)}"
    )

    print(
        f"  Irrev. -> agent        : "
        f"{len(irreversible_reaching_agent)}"
    )

    print(
        "  STATUS                 : "
        + (
            "PASS"
            if security_invariant_passed
            else "FAIL"
        )
    )

    print()

    print(
        f"Security runtime        : "
        f"{security_time:.4f} sec"
    )

    print()

    print(
        f"wrote: {OUTPUT_FILE}"
    )

    print(
        f"wrote: {AUDIT_FILE}"
    )

    print()

    print(
        "=" * 72
    )

    print(
        "Security-First Phase 3 complete."
    )

    print(
        "=" * 72
    )


# ===================================================================
# ENTRY POINT
# ===================================================================

if __name__ == "__main__":

    run_pipeline()