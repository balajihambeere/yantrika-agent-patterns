"""
Shadow-mode testing for the PO-acknowledgment agent.

An agent's perceive and decide boxes should never meet a live system for
the first time. Shadow mode runs the full decision pipeline against
historical messages, logs what the agent *would* have done, and changes
nothing -- no email sent, no record touched -- so failure modes surface
on the team's own schedule, against known outcomes, instead of live.

This script calls `perceive` (via `classify_reply`) and `decide` directly
as plain functions -- illustrating the shadow-mode practice -- not
through the full interrupting graph, because shadow mode by definition
never reaches the act/escalate/interrupt machinery at all.

A worked example ran shadow mode against roughly 210 historical messages
and surfaced 4 failure modes:
  1. a stamped-PDF confirmation misread as no-reply (twice),
  2. a non-committal "noted, will advise" misread as a clear confirmation,
  3. a genuine 6-day schedule slip buried in routine text, misread as clean,
  4. a mis-threaded reply that looked like silence because it was read on
     the wrong thread.

This script recreates all four as fixtures and runs them through the
*current* perceive/decide (which already has the guardrails built in).
Three of the four guardrails live inside perceive/decide itself
(attachment confidence, the supplier exception table, the hard
invariant) and are exercised directly here. The fourth -- matching a
reply by reference number regardless of which thread it landed in --
lives in `trigger()`, one layer up, so this script can only show that
perceive reads the message correctly *once it has been found*; the
end-to-end fix (finding it in the first place) is demonstrated in
demo.py's `clean_confirmation()` scenario, which runs the full graph.
This script then adds two new, deliberately-not-yet-fixed edge cases to
make the point that shadow mode is a standing practice, not a one-time
test: there is always a next failure mode to find.

Illustrative scale: 12 scripted messages, not a literal replay of the
historical ~210 -- labeled honestly throughout.

Run with:
    python3 shadow_mode.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_graph import decide
from perception import classify_reply

Fixture = dict[str, Any]


def _fixture(
    label: str,
    category: str,
    po_number: str,
    supplier: str,
    ordered_qty: int,
    ordered_date: str,
    ground_truth_action: str,
    message: dict[str, Any] | None,
    hours_since_po: float = 20,
) -> Fixture:
    return {
        "label": label,
        "category": category,
        "po": {
            "po_number": po_number,
            "supplier": supplier,
            "ordered_qty": ordered_qty,
            "ordered_date": ordered_date,
            "hours_since_po": hours_since_po,
        },
        "message": message,
        "ground_truth_action": ground_truth_action,
    }


_FIXTURES_PATH = Path(__file__).parent / "data" / "shadow_mode_fixtures.json"


def build_fixtures() -> list[Fixture]:
    """
    Load the 12 scripted historical-message fixtures from
    data/shadow_mode_fixtures.json and reconstruct them via `_fixture()`,
    exactly as if they had been built inline here -- see that file for
    the baseline cases, the 4 historical failure modes (now closed), and
    the 2 new, deliberately-not-yet-fixed edge cases.
    """
    with open(_FIXTURES_PATH, encoding="utf-8") as f:
        raw_fixtures: list[dict[str, Any]] = json.load(f)
    return [_fixture(**raw) for raw in raw_fixtures]


def run_shadow_mode(fixtures: list[Fixture]) -> list[dict[str, Any]]:
    """
    Calls perceive (classify_reply) and decide directly, bypassing the
    graph, act, escalate, and every interrupt() -- shadow mode never
    acts, so there is nothing to approve and nothing to send.
    """
    results = []
    for fx in fixtures:
        perception = classify_reply(fx["po"], fx["message"])
        decision = decide({"po": fx["po"], "perception": perception})["decision"]
        matched = decision["action"] == fx["ground_truth_action"]
        results.append({
            "label": fx["label"],
            "category": fx["category"],
            "ground_truth_action": fx["ground_truth_action"],
            "agent_action": decision["action"],
            "confidence": perception["confidence"],
            "matched": matched,
        })
    return results


def print_report(results: list[dict[str, Any]]) -> None:
    total = len(results)
    matches = sum(1 for r in results if r["matched"])
    mismatches = [r for r in results if not r["matched"]]

    print("=" * 76)
    print("SHADOW-MODE REPORT")
    print("(illustrative scale -- 12 scripted messages, not a literal replay")
    print(" of the ~210-message historical run)")
    print("=" * 76)
    for r in results:
        flag = "match" if r["matched"] else "MISMATCH"
        print(f"[{flag:8}] {r['label']}")
        print(f"            category: {r['category']}")
        print(f"            ground truth: {r['ground_truth_action']:20} agent: {r['agent_action']:20} "
              f"(confidence {r['confidence']:.2f})")

    print("-" * 76)
    print(f"Total messages:         {total}")
    print(f"Matched ground truth:   {matches} ({matches / total:.0%})")
    print(f"Mismatches:             {len(mismatches)}")
    if mismatches:
        print("\nSpecific failure modes surfaced this run:")
        for r in mismatches:
            print(f"  - {r['label']}")
            print(f"    category: {r['category']}")
            print(f"    would have done '{r['agent_action']}', should have been '{r['ground_truth_action']}'")
    print(
        "\nA known list of specific failure modes is worth more than an aggregate\n"
        "accuracy number. The four historical failure modes are all closed by the\n"
        "guardrails now built into perceive/decide. The remaining mismatches above are\n"
        "new, illustrative edge cases this run surfaced -- exactly the kind of punch\n"
        "list the next guardrail round should start from, not a sign the practice is\n"
        "ever 'done.'"
    )


def main() -> None:
    results = run_shadow_mode(build_fixtures())
    print_report(results)


if __name__ == "__main__":
    main()
