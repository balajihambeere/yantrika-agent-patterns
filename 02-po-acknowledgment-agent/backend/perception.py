"""
Perception logic for the PO-acknowledgment agent.

This module is the "perceive" box from the six-box productivity-agent
anatomy (Trigger -> Perceive -> Decide -> Act -> Escalate -> Log),
extended with three guardrails that belong at the perception layer
rather than the decide layer:

  1. A stamped-PDF attachment gets its OWN confidence score, separate from
     the text-reading confidence: it gets its own confidence score,
     separate from the text-reading confidence, and if that score comes
     in low, it escalates rather than silently reading it as a match.
  2. Matching a supplier's reply to a PO no longer depends on which email
     thread it landed in. `find_supplier_message` scans every message in
     the inbox for a reference-number match against a known supplier
     contact, regardless of thread — the fix Kiran made "the same
     afternoon" after realizing the system was asking "did anyone reply
     on THIS thread" instead of "did this supplier say anything relevant,
     anywhere."
  3. A small, named, per-supplier exception table — owned and edited by
     Neha, not tuned as a global model threshold — captures tacit
     knowledge that is true of one supplier's correspondence habits and
     does not generalize to the others. It is layered as an explicit
     override ON TOP OF the general reading, never folded into it.

A fourth guardrail — the hard invariant on date/quantity mismatches — is
deliberately NOT here. It is a decide-level rule, enforced unconditionally
in agent_graph.decide(), and must never be something a confidence score
can out-vote. Keeping it out of this module is the point: this file only
reads and classifies; it never decides what should happen as a result of
what it read.

Everything here is deterministic, rule-based pattern matching over plain
text. No LLM call, no API key required — the same rule-based philosophy
as the agent's decide() function.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# --- Tunable knobs -------------------------------------------------------
# The confidence line between "confident enough to treat as a clean read"
# and "not confident, escalate instead." This is the genuinely hard
# design decision: we don't get to pick that threshold from principle.
# We pick a starting value, we run it against everything, and we see
# where it actually breaks.
CONFIDENCE_ESCALATION_THRESHOLD = 0.7

# The first guardrail: the stamped-PDF parser gets its OWN confidence
# score, never borrowed from the text-reading confidence.
ATTACHMENT_CONFIDENCE_THRESHOLD = 0.6

# The "noted, will advise" supplier's literal stalling phrase.
# This is a general rule — it applies no matter which supplier writes it.
# Neha's supplier-specific exception below is a *different, broader* rule
# that catches the same supplier's other date-less replies that don't use
# this exact phrase.
NON_COMMITTAL_PHRASES = (
    "noted, will advise",
    "noted. will advise",
    "will advise",
)

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_QTY_RE = re.compile(r"(\d+)\s*(?:units|pcs|pieces)", re.IGNORECASE)


# --- Guardrail #3: Neha's per-supplier exception table ------------------
#
# One row per supplier, a plain-language rule attached, owned and edited
# directly by the domain expert who has the tacit knowledge — not a
# change to the general model, and not a global threshold. Add or edit
# rows here; nothing else in this module needs to change for a new
# supplier-specific exception. This is deliberately a plain dict, not a
# database or a config file, because the whole point is that Neha can
# maintain it "without needing Kiran or Aditi in the room."
SUPPLIER_EXCEPTIONS: dict[str, dict[str, Any]] = {
    "Bharat Precision Forge": {
        "owner": "Neha",
        "rule": (
            "If this supplier's reply contains no explicit date anywhere, "
            "treat as unclear, not confirmed — the tell for this supplier "
            "specifically is whether he names a date, even a vague one. "
            "No date at all means he's stalling, not agreeing."
        ),
        "applies": lambda extracted_date: extracted_date is None,
        "override_situation": "unclear",
        "override_confidence": 0.3,
    },
}


def apply_supplier_exception(
    supplier: str,
    extracted_date: Optional[str],
    base_situation: str,
    base_confidence: float,
) -> tuple[str, float, Optional[str]]:
    """
    Layer Neha's supplier-specific exception on top of the general
    reading, scoped to exactly the supplier it was written for.

    Returns (situation, confidence, note) — note is None if no exception
    applied, which is the common case for every supplier not in the table.
    """
    exception = SUPPLIER_EXCEPTIONS.get(supplier)
    if exception is None or not exception["applies"](extracted_date):
        return base_situation, base_confidence, None
    note = (
        f"overridden by {exception['owner']}'s supplier exception for "
        f"{supplier}: {exception['rule']}"
    )
    return exception["override_situation"], exception["override_confidence"], note


def find_supplier_message(
    po_number: str, supplier: str, inbox: list[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    """
    Guardrail #2: match ANY message from this supplier whose reference
    number matches this PO, regardless of which email thread it was
    filed under.

    The mis-threaded-reply bug was asking "did anyone reply on THIS
    thread." The right question, per Kiran, was always "did this supplier
    say anything relevant, anywhere." This scans the whole inbox, not a
    single thread, and is the mechanical fix — no judgment call involved.
    """
    candidates = [
        message
        for message in inbox
        if message.get("supplier") == supplier and message.get("po_reference") == po_number
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda m: m.get("received_at_hours", 0))


def _extract_fields(text: str) -> tuple[Optional[int], Optional[str]]:
    qty_match = _QTY_RE.search(text)
    date_match = _DATE_RE.search(text)
    qty = int(qty_match.group(1)) if qty_match else None
    date = date_match.group(0) if date_match else None
    return qty, date


def _classify_text(text: str) -> dict[str, Any]:
    """The general, supplier-agnostic reading of a plain-text reply."""
    lowered = text.lower()

    if any(phrase in lowered for phrase in NON_COMMITTAL_PHRASES):
        return {
            "situation": "unclear",
            "confidence": 0.3,
            "extracted_qty": None,
            "extracted_date": None,
            "notes": "non-committal reply — commits to nothing, treated as unclear, not a confirmation",
        }

    qty, date = _extract_fields(text)

    if qty is not None and date is not None:
        return {
            "situation": "confirmed_with_change",
            "confidence": 0.92,
            "extracted_qty": qty,
            "extracted_date": date,
            "notes": "quantity and delivery date both read explicitly from the reply",
        }

    if qty is not None or date is not None:
        return {
            "situation": "confirmed_with_change",
            "confidence": 0.6,
            "extracted_qty": qty,
            "extracted_date": date,
            "notes": "only one of quantity/date read explicitly from the reply — partial read, lower confidence",
        }

    # Deliberately naive fallback: a bare keyword match, with no negation
    # handling. This is a known, intentional blind spot (see
    # shadow_mode.py's "new edge case" N1) — the same shape of problem as
    # the "noted, will advise" supplier: a rule this simple will
    # occasionally read a hedge, or a negated reply, as a clear one.
    # Shadow-mode testing exists precisely to keep finding blind spots
    # like this one before a live inbox does.
    if "confirm" in lowered or "received" in lowered:
        return {
            "situation": "confirmed_as_ordered",
            "confidence": 0.75,
            "extracted_qty": None,
            "extracted_date": None,
            "notes": "no explicit quantity/date found — read as a plain-language confirmation",
        }

    return {
        "situation": "unclear",
        "confidence": 0.4,
        "extracted_qty": None,
        "extracted_date": None,
        "notes": "nothing in the reply matched a known pattern",
    }


def classify_reply(po: dict[str, Any], message: Optional[dict[str, Any]]) -> dict[str, Any]:
    """
    Turn one matched inbox message (or its absence) into a perception
    result: a situation, a confidence score, and — for attachments — a
    second, separate confidence score for that input type.

    Returns a dict with: situation, confidence, extracted_qty,
    extracted_date, attachment_confidence (Optional), notes, source.

    `situation` is one of: "pending", "no_acknowledgment", "unclear",
    "confirmed_as_ordered", "confirmed_with_change".
    """
    if message is None:
        if po["hours_since_po"] >= 48:
            result: dict[str, Any] = {
                "situation": "no_acknowledgment",
                "confidence": 1.0,
                "extracted_qty": None,
                "extracted_date": None,
                "attachment_confidence": None,
                "notes": "48 hours elapsed with nothing resembling an acknowledgment in the canonical record",
                "source": "none",
            }
        else:
            result = {
                "situation": "pending",
                "confidence": 1.0,
                "extracted_qty": None,
                "extracted_date": None,
                "attachment_confidence": None,
                "notes": "still inside the 48-hour window, nothing to react to yet",
                "source": "none",
            }
        return result

    attachment = message.get("attachment")
    if attachment is not None:
        # Guardrail #1: the attachment gets its OWN confidence score. A
        # low scan confidence escalates, even if the parsed fields would
        # otherwise look like a clean match.
        parse_confidence = attachment["parse_confidence"]
        qty, date = attachment.get("parsed_qty"), attachment.get("parsed_date")
        if parse_confidence < ATTACHMENT_CONFIDENCE_THRESHOLD:
            situation, confidence = "unclear", parse_confidence
            notes = "stamped-PDF attachment parsed, but scan confidence is too low to trust silently"
        else:
            situation, confidence = "confirmed_with_change", parse_confidence
            notes = "stamped-PDF attachment parsed with acceptable confidence"
        result = {
            "situation": situation,
            "confidence": confidence,
            "extracted_qty": qty,
            "extracted_date": date,
            "attachment_confidence": parse_confidence,
            "notes": notes,
            "source": "attachment",
        }
    else:
        text = message.get("body", "")
        base = _classify_text(text)
        result = {**base, "attachment_confidence": None, "source": "text"}

    # If what was read matches the PO exactly, call it what it is instead
    # of leaving it labeled "confirmed_with_change" with a zero-sized
    # change. decide() still re-checks the numbers independently either
    # way (that re-check IS the hard invariant) — this relabeling only
    # affects the bounded action space's confidence-based branch, never
    # the invariant.
    if result["situation"] == "confirmed_with_change":
        qty_matches = result["extracted_qty"] in (None, po["ordered_qty"])
        date_matches = result["extracted_date"] in (None, po["ordered_date"])
        if qty_matches and date_matches and (result["extracted_qty"] or result["extracted_date"]):
            result["situation"] = "confirmed_as_ordered"

    # Guardrail #3: Neha's supplier exception, layered on top of the
    # general reading above, scoped to exactly the supplier it was
    # written for.
    situation, confidence, note = apply_supplier_exception(
        po["supplier"], result["extracted_date"], result["situation"], result["confidence"]
    )
    if note:
        result["situation"], result["confidence"] = situation, confidence
        result["notes"] = f"{result['notes']}; {note}"

    return result
