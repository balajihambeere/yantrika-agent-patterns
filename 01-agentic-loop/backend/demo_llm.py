"""
Optional companion to demo.py: runs the SAME agentic-loop graph twice over
each of the 8 harness products in data/harness_products_100.json — once
with the deterministic, rule-based `decide()` from agentic_graph.py, and
once with the OpenAI-backed `decide()` from decide_llm.py — and compares
the two decision traces cycle by cycle.

This is opt-in and NOT part of the free/deterministic core example: it
requires `openai` installed (requirements-llm.txt) and a real
OPENAI_API_KEY, and it costs a small amount of real API usage (about 100
short chat-completion calls on gpt-4o-mini by default). Because the model's
output is non-deterministic, this script is a comparison report, not a
pass/fail test — see README.md's "Optional: live OpenAI-backed decide()"
section.

Run with:
    pip install -r requirements-llm.txt
    cp .env.example .env   # then fill in OPENAI_API_KEY, or export it directly
    python3 demo_llm.py
    python3 demo_llm.py --limit 10   # cheap smoke test: only the first 10 cycles
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agentic_graph import decide as decide_rule
from agentic_graph import build_graph, make_initial_state

_DATA_PATH = Path(__file__).parent / "data" / "harness_products_100.json"


def _fail_fast_if_no_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "ERROR: OPENAI_API_KEY is not set.\n"
            "Set it before running demo_llm.py — e.g. copy .env.example to .env and "
            "fill it in, or `export OPENAI_API_KEY=sk-...`.\n"
            "(demo_llm.py calls the real OpenAI API; the free/deterministic demo.py "
            "does not need this.)",
            file=sys.stderr,
        )
        sys.exit(1)


def auto_approve(payload: dict) -> dict:
    """Stands in for a human clicking 'approve' in a real review UI (same as demo.py)."""
    return {"approved": True, "approved_by": "Aditi Kulkarni"}


def run_trace(decide_fn, sku: str, opening_balance: float, run_rate: float, events: list[dict], thread_id: str) -> list[dict]:
    """
    Drives one full decision trace (observe -> decide -> [human_review] -> act,
    looping) through build_graph(decide_fn=...), auto-approving every
    interrupt, and returns the completed audit log. Same mechanics as
    demo.py's run_agent_part(), generalized over which decide_fn is wired in.
    """
    graph = build_graph(decide_fn=decide_fn).compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": thread_id}}
    state = make_initial_state(
        sku=sku,
        opening_balance=opening_balance,
        run_rate_per_minute=run_rate,
        pending_events=list(events),
    )

    resume_value = state
    is_resuming = False

    while True:
        stream_input = Command(resume=resume_value) if is_resuming else resume_value
        interrupt_payload = None

        for chunk in graph.stream(stream_input, config=config, stream_mode="updates"):
            if "__interrupt__" in chunk:
                interrupt_payload = chunk["__interrupt__"][0].value

        if interrupt_payload is not None:
            resume_value = auto_approve(interrupt_payload)
            is_resuming = True
            continue

        snapshot = graph.get_state(config)
        if not snapshot.next:
            return snapshot.values.get("log", [])


def compare_logs(
    sku: str, run_rate: float, rule_log: list[dict], llm_log: list[dict], disagreements: list[dict]
) -> dict:
    """Compares two logs cycle-by-cycle (they share the same event stream, so
    cycle i in both logs corresponds to the same observation/balance)."""
    stats = {"cycles": 0, "action_match": 0, "risk_match": 0, "human_match": 0}

    for i, (rule_entry, llm_entry) in enumerate(zip(rule_log, llm_log)):
        rule_d, llm_d = rule_entry["decision"], llm_entry["decision"]
        balance = rule_entry["observation"]["balance"]
        cover = balance / run_rate if run_rate else float("inf")

        action_match = rule_d["action"] == llm_d["action"]
        risk_match = rule_d["risk"] == llm_d["risk"]
        human_match = rule_d["requires_human"] == llm_d["requires_human"]

        stats["cycles"] += 1
        stats["action_match"] += int(action_match)
        stats["risk_match"] += int(risk_match)
        stats["human_match"] += int(human_match)

        match_str = "MATCH" if action_match and risk_match and human_match else "DIFFER"
        print(
            f"  [{sku}] balance={balance:>4} cover={cover:>5.0f}min  rule={rule_d['action']:<28} "
            f"llm={llm_d['action']:<28} {match_str}"
        )

        if not (action_match and risk_match and human_match):
            disagreements.append(
                {
                    "sku": sku,
                    "cycle": i + 1,
                    "balance": balance,
                    "rule_action": rule_d["action"],
                    "rule_risk": rule_d["risk"],
                    "rule_rationale": rule_d["rationale"],
                    "llm_action": llm_d["action"],
                    "llm_risk": llm_d["risk"],
                    "llm_rationale": llm_d["rationale"],
                }
            )

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run the first N cycles total (across all products, in dataset order) — "
        "a cheap smoke test before committing to a full ~100-call run.",
    )
    args = parser.parse_args()

    _fail_fast_if_no_api_key()

    # Imported here, after the API-key check, and ONLY from this module —
    # agentic_graph.py / demo.py / test_agentic_graph.py never import decide_llm
    # or openai, so the free/deterministic core example never needs either.
    from decide_llm import decide as decide_llm_fn

    with _DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    products = data["products"]
    remaining = args.limit  # cycles left to run, or None for unlimited
    totals = {"cycles": 0, "action_match": 0, "risk_match": 0, "human_match": 0}
    disagreements: list[dict] = []

    print("=" * 76)
    print("Comparing deterministic decide() vs. OpenAI-backed decide_llm.decide()")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    print(f"model={model}" + (f"  limit={args.limit} cycles" if args.limit else "  (full dataset)"))
    print("=" * 76)

    for product in products:
        if remaining is not None and remaining <= 0:
            break

        sku = product["sku"]
        events = product["events"]
        if remaining is not None:
            events = events[:remaining]
        if not events:
            continue

        print(f"\n--- {sku} ({product.get('name', '')}) ---")

        rule_log = run_trace(
            decide_rule, sku, product["opening_balance"], product["run_rate_per_minute"], events, thread_id=f"rule-{sku}"
        )
        llm_log = run_trace(
            decide_llm_fn, sku, product["opening_balance"], product["run_rate_per_minute"], events, thread_id=f"llm-{sku}"
        )

        stats = compare_logs(sku, product["run_rate_per_minute"], rule_log, llm_log, disagreements)
        for key in totals:
            totals[key] += stats[key]

        if remaining is not None:
            remaining -= len(events)

    print("\n" + "=" * 76)
    print("SUMMARY")
    print("=" * 76)
    cycles = totals["cycles"]
    if cycles == 0:
        print("No cycles were run.")
        return

    def pct(n: int) -> str:
        return f"{n}/{cycles} ({100.0 * n / cycles:.1f}%)"

    print(f"Total cycles compared:        {cycles}")
    print(f"Action agreement:             {pct(totals['action_match'])}")
    print(f"Risk agreement:                {pct(totals['risk_match'])}")
    print(f"Human-escalation agreement:    {pct(totals['human_match'])}")

    if disagreements:
        print(f"\nDisagreements ({len(disagreements)}):")
        for d in disagreements:
            print(f"\n  [{d['sku']}] cycle {d['cycle']}  balance={d['balance']}")
            print(f"    rule: {d['rule_action']} [{d['rule_risk']}] — {d['rule_rationale']}")
            print(f"    llm:  {d['llm_action']} [{d['llm_risk']}] — {d['llm_rationale']}")
    else:
        print("\nNo disagreements — the LLM matched the deterministic rule on every cycle run.")

    print(
        "\nReminder: this is a comparison report, not a pass/fail test — the LLM's "
        "output is non-deterministic, so re-running this script can produce different "
        "disagreement counts. The safety-net invariant (risk='high' always forces "
        "requires_human=True) is enforced in decide_llm.py's code, not left to the model."
    )


if __name__ == "__main__":
    main()
