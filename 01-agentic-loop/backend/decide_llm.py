"""
An OpenAI-backed replacement for the deterministic `decide()` node in
agentic_graph.py — same signature, same return shape, opt-in, and fully
isolated from the free/deterministic core example.

Nothing in agentic_graph.py, demo.py, or test_agentic_graph.py imports this
module (or the `openai` package). Only demo_llm.py does. That keeps the base
example free of any required API key or paid dependency.

Usage:
    from decide_llm import decide as decide_llm
    graph = build_graph(decide_fn=decide_llm).compile(...)

decide(state) reads the same `GraphState` shape the rule-based `decide()`
reads (state["observation"], state["sku"], state["run_rate_per_minute"],
state["alerted"]), and returns the same update dict:
    {"decision": {...}, "alerted": True}  # "alerted" only when raising an alert

The decision dict always has: action, rationale, risk, requires_human,
approved, approved_by — identical convention to the rule-based version:
requires_human=True implies approved=False (pending human sign-off),
otherwise approved=True.
"""
from __future__ import annotations

import json
import os
from typing import Any

from agentic_graph import SAFETY_THRESHOLD_MINUTES

_DEFAULT_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = f"""You are the decision stage of an inventory-watching agentic loop for an \
automotive wiring-harness plant. Every cycle you are given one fresh observation of a single \
SKU's live stock ledger and must propose exactly one action.

You will be told:
  - the SKU
  - the current balance (units on hand right now)
  - the production run rate (units consumed per minute once the line is running)
  - minutes of cover remaining = balance / run_rate_per_minute
  - whether an alert has already been raised earlier in this same overnight run
  - the plant's safety threshold, {SAFETY_THRESHOLD_MINUTES} minutes of cover

There are exactly three possible actions:
  - "no_action": cover is comfortably above the safety threshold. Nothing needs to happen yet;
    routine draws and receipts are normal and expected. Risk is "low".
  - "alert_floor_and_stores": cover has fallen to or below the safety threshold, but no alert has
    been raised yet this run. Notifying the floor and the stores team now, ahead of the next batch
    report, is a cheap, reversible, low-cost action — it buys lead time without committing any
    money or disrupting production. Risk is usually "medium".
  - "expedite_replacement_shipment": cover is at or below the safety threshold AND an alert has
    already been raised earlier this run and the shortfall is still live (i.e. the alert alone
    clearly has not resolved the problem — the line is still at real risk of stopping). Expediting
    a shipment is costly and hard to reverse once placed, so this is the one action that should
    carry "high" risk and get a human's sign-off before it is actually executed.

Use judgment, not a rigid rule: weigh how far below threshold the cover is, how fast it is still
falling, and whether an alert already went out and the situation has or hasn't improved since.
Don't just mechanically check "alert already sent?" — if, for example, cover is only barely under
threshold and nothing suggests an imminent line stop, continuing to flag the situation without
expediting may be more sensible than jumping straight to an expensive expedite call. But if the
shortfall is severe or still worsening after an alert, escalate to expedite with risk "high".

Respond with a decision for THIS cycle only, as structured JSON matching the provided schema.
"""

_RESPONSE_SCHEMA = {
    "name": "inventory_decision",
    "schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "no_action",
                    "alert_floor_and_stores",
                    "expedite_replacement_shipment",
                ],
            },
            "rationale": {"type": "string"},
            "risk": {
                "type": "string",
                "enum": ["low", "medium", "high"],
            },
        },
        "required": ["action", "rationale", "risk"],
        "additionalProperties": False,
    },
    "strict": True,
}


class OpenAIApiKeyMissingError(RuntimeError):
    """Raised when decide_llm.decide() is called without OPENAI_API_KEY set."""


def _get_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIApiKeyMissingError(
            "OPENAI_API_KEY is not set. Set OPENAI_API_KEY (see .env.example) before "
            "running the OpenAI-backed decide path (decide_llm.py / demo_llm.py)."
        )
    from openai import OpenAI  # imported lazily so the base example never needs `openai` installed

    return OpenAI(api_key=api_key)


def _build_user_prompt(sku: str, balance: int, minutes_of_cover: float, alerted: bool, last_transaction: str) -> str:
    return (
        f"SKU: {sku}\n"
        f"Current balance: {balance} units\n"
        f"Minutes of cover remaining: {minutes_of_cover:.1f}\n"
        f"Safety threshold: {SAFETY_THRESHOLD_MINUTES} minutes\n"
        f"Alert already raised earlier this run: {alerted}\n"
        f"Most recent transaction: {last_transaction!r}\n"
        "What action should be taken this cycle?"
    )


def decide(state: dict[str, Any]) -> dict[str, Any]:
    """LLM-backed drop-in replacement for agentic_graph.decide(state).

    Same inputs, same output shape — see module docstring. The only
    behavioral difference is that the action/rationale/risk come from an
    OpenAI chat completion instead of a fixed threshold check.
    """
    client = _get_client()
    model = os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)

    observation = state["observation"]
    sku = state["sku"]
    balance = observation["balance"]
    run_rate = state["run_rate_per_minute"]
    minutes_of_cover = balance / run_rate if run_rate else float("inf")
    alerted = state["alerted"]

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_prompt(
                    sku=sku,
                    balance=balance,
                    minutes_of_cover=minutes_of_cover,
                    alerted=alerted,
                    last_transaction=observation["last_transaction"],
                ),
            },
        ],
        response_format={"type": "json_schema", "json_schema": _RESPONSE_SCHEMA},
    )

    payload = json.loads(response.choices[0].message.content)
    action = payload["action"]
    rationale = payload["rationale"]
    risk = payload["risk"]

    # The model's own notion of "does this need a human" isn't in the schema at
    # all — requires_human is derived here, not asked of the model. That's the
    # safety-net invariant: "high" risk ALWAYS forces human escalation, no
    # matter what the model says or doesn't say about it. A model can be wrong,
    # inconsistent, or simply omit the field; the risk level is the one thing
    # this code treats as a hard gate rather than a tunable, model-trusted
    # threshold. This mirrors the "hard invariant, not a tunable" guardrail
    # pattern used elsewhere in this project's sibling examples — an
    # escalation-worthy risk level always escalates, independent of model
    # confidence or self-report.
    requires_human = risk == "high"
    approved = not requires_human

    decision = {
        "action": action,
        "rationale": rationale,
        "risk": risk,
        "requires_human": requires_human,
        "approved": approved,
        "approved_by": None,
    }

    update: dict[str, Any] = {"decision": decision}
    if action == "alert_floor_and_stores":
        update["alerted"] = True
    return update
