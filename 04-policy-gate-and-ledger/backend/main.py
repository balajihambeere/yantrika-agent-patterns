"""
FastAPI wrapper around policy_gate_graph.py — exposes the policy gate's
three request flows (operational / governance / reversal_check) over
HTTP + a WebSocket, so a browser can drive them instead of demo.py's
terminal loop.

No business logic lives here. This file only does five things:
  1. Serves the 5 demo.py scenarios (from data/demo_scenarios.json),
     tagged by request_type, so the frontend can build three
     "start a request" sections.
  2. Serves the live registry of agents and their current tier/boundary
     (a read of the one shared PolicyRegistry every run shares).
  3. Creates a "run" (one graph thread) for each of the three request
     types — operational, governance, reversal_check — each via its own
     endpoint, because the three take genuinely different inputs.
  4. Streams that run's nodes over a WebSocket, exactly the way demo.py
     drives the graph from a terminal loop — just over the wire instead
     of auto-approved — and accepts the human's approve/decline decision
     back over the same socket for the two flows that can interrupt.
  5. Serves the shared DecisionLedger — a live, growing audit trail —
     both as a list and as a full five-part reconstruction of one
     decision, mirroring mock_audit.py's "walk me through exactly why."

The PolicyRegistry and DecisionLedger below are created ONCE, at module
level, exactly like policy_gate_graph.build_graph()'s docstring
describes: real, shared, stateful objects that survive across however
many requests are streamed through the compiled graph, using the same
thread_id or different ones. Every run in this process shares the same
registry and ledger — a tier change made in one run is visible to every
run after it, for as long as this process keeps running.

Run with:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from decision_ledger import DecisionLedger
from policy_engine import (
    AutonomyTier,
    PolicyRegistry,
    ReversalTrigger,
    TierBoundary,
    TierChangeProposal,
)
from policy_gate_graph import (
    build_graph,
    make_initial_governance_state,
    make_initial_operational_state,
    make_initial_reversal_state,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

BASE_DIR = Path(__file__).resolve().parent  # .../04-policy-gate-and-ledger/backend


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no python-dotenv dependency). An explicit
    `export` in the real environment always wins over the file."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# app setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Policy Gate & Decision Ledger API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# the ONE shared registry, ledger, and compiled graph for this process.
# Every run — regardless of thread_id — reads and writes the same two
# stateful objects, matching build_graph()'s "real, shared, stateful
# objects... not graph state" contract.
# ---------------------------------------------------------------------------

_registry = PolicyRegistry()
_ledger = DecisionLedger()
_checkpointer = InMemorySaver()
_graph = build_graph(_registry, _ledger).compile(checkpointer=_checkpointer)

# thread_id -> {"flow": request_type, "initial_state": GraphState}, so the
# WS handler knows which flow a given run belongs to (and can replay its
# first stream_input), the same way 01-agentic-loop tracks thread_id -> sku.
_run_meta: dict[str, dict[str, Any]] = {}

# Append-order index of every decision_id this process has logged, built
# from the `decision_id` field each completed run's final state carries —
# avoids reaching into DecisionLedger's private attributes for a "list
# everything" view that its public API doesn't expose.
_ledger_order: list[str] = []
_ledger_seen: set[str] = set()


def _record_if_logged(final_values: dict[str, Any]) -> None:
    decision_id = final_values.get("decision_id")
    if decision_id and decision_id not in _ledger_seen:
        _ledger_seen.add(decision_id)
        _ledger_order.append(decision_id)


# ---------------------------------------------------------------------------
# scripted demo scenarios (data/demo_scenarios.json)
# ---------------------------------------------------------------------------

_SCENARIOS_PATH = BASE_DIR / "data" / "demo_scenarios.json"
_scenarios_raw: dict[str, Any] = json.loads(_SCENARIOS_PATH.read_text())
_STORY_TODAY = _scenarios_raw["story_today"]


def _build_scenarios() -> list[dict[str, Any]]:
    s = _scenarios_raw
    return [
        {
            "id": "scenario-1",
            "request_type": "operational",
            "title": "Within-boundary allocation action",
            "description": (
                "A single-claim, low-exposure shortfall on Arjun's allocation agent — "
                "inside its current boundary. check_boundary finds it in bounds; it "
                "auto-acts, no interrupt, and a five-part record is written."
            ),
            "payload": {"agent_id": s["scenario_1"]["agent_id"], "action": s["scenario_1"]["action"]},
        },
        {
            "id": "scenario-2",
            "request_type": "operational",
            "title": "Out-of-boundary allocation action",
            "description": (
                "Two competing claims, exposure over the agreed cap — outside the "
                "boundary. The graph genuinely pauses on interrupt() and routes to "
                "Aditi Kulkarni, the agent's named escalation contact, before anything happens."
            ),
            "payload": {"agent_id": s["scenario_2"]["agent_id"], "action": s["scenario_2"]["action"]},
        },
        {
            "id": "scenario-3",
            "request_type": "governance",
            "title": "Arjun's tier-widening proposal (valid)",
            "description": (
                "All four policy-as-code conditions are satisfied: a numeric 130-decision "
                "track record, Arjun as proposer and Suresh Rane as a structurally different "
                "named approver, an explicit reversal trigger, and a scheduled re-review date. "
                "Routes to Suresh via interrupt(); if approved, the boundary widens."
            ),
            "payload": {**s["scenario_3"]["proposal"], "today": _STORY_TODAY},
        },
        {
            "id": "scenario-4",
            "request_type": "governance",
            "title": "A further widening, missing conditions",
            "description": (
                "Requested quickly after scenario 3 landed — but with only 12 decisions "
                "at the new boundary (below the minimum) and no reversal trigger at all. "
                "policy_engine rejects it deterministically; no interrupt ever fires, and "
                "Suresh is never even asked."
            ),
            "payload": {**s["scenario_4"]["proposal"], "today": _STORY_TODAY},
        },
        {
            "id": "scenario-5",
            "request_type": "reversal_check",
            "title": "Reversal trigger check (fires)",
            "description": (
                "A run of recent decisions that includes one missed commitment is checked "
                "against the agent's predefined reversal trigger. It fires, and the boundary "
                "rolls back automatically — no interrupt, no human call, anywhere in this flow."
            ),
            "payload": {"agent_id": s["scenario_5"]["agent_id"], "recent_decisions": s["scenario_5"]["recent_decisions"]},
        },
    ]


_SCENARIOS = _build_scenarios()


@app.get("/api/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    return _SCENARIOS


# ---------------------------------------------------------------------------
# REST: the live agent registry (read-only view of the shared PolicyRegistry)
# ---------------------------------------------------------------------------


def _agent_to_dict(agent) -> dict[str, Any]:
    return {
        "agent_id": agent.agent_id,
        "display_name": agent.display_name,
        "tier": int(agent.tier),
        "tier_label": agent.tier.name,
        "boundary_description": agent.boundary.describe(),
        "escalation_contact": agent.escalation_contact,
        "policy_version": agent.policy_version,
        "reversal_trigger_description": agent.reversal_trigger.describe() if agent.reversal_trigger else None,
        "re_review_date": agent.re_review_date.isoformat() if agent.re_review_date else None,
        "track_record_count": agent.track_record_count,
        "track_record_label": agent.track_record_label,
    }


@app.get("/api/agents")
def list_agents() -> list[dict[str, Any]]:
    return [_agent_to_dict(a) for a in _registry.all_agents()]


# ---------------------------------------------------------------------------
# REST: create a run — three separate endpoints, one per request type
# ---------------------------------------------------------------------------


class CreateRunResponse(BaseModel):
    thread_id: str


class ActionIn(BaseModel):
    description: str = ""
    inputs: dict[str, Any]
    model_version: str = "n/a"
    reasoning_path: list[dict[str, Any]] = []


class OperationalRequestIn(BaseModel):
    agent_id: str
    action: ActionIn


@app.post("/api/operational-requests", response_model=CreateRunResponse)
def create_operational_request(req: OperationalRequestIn) -> CreateRunResponse:
    try:
        _registry.get(req.agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    state = make_initial_operational_state(req.agent_id, req.action.model_dump())
    thread_id = str(uuid.uuid4())
    _run_meta[thread_id] = {"flow": "operational", "initial_state": state}
    return CreateRunResponse(thread_id=thread_id)


class BoundaryIn(BaseModel):
    max_competing_orders: Optional[int] = None
    max_exposure_inr: Optional[float] = None
    notes: str = ""


class ReversalTriggerIn(BaseModel):
    name: str
    metric: str
    comparison: str
    threshold: float
    window_label: str


class GovernanceProposalIn(BaseModel):
    agent_id: str
    proposer: str
    approver: str
    from_tier: int
    to_tier: int
    new_boundary: BoundaryIn
    track_record_count: Optional[int] = None
    track_record_minimum: Optional[int] = None
    track_record_label: str = ""
    reversal_trigger: Optional[ReversalTriggerIn] = None
    re_review_date: Optional[str] = None
    rationale: str = ""
    today: str


@app.post("/api/governance-proposals", response_model=CreateRunResponse)
def create_governance_proposal(req: GovernanceProposalIn) -> CreateRunResponse:
    try:
        _registry.get(req.agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    proposal = TierChangeProposal(
        agent_id=req.agent_id,
        proposer=req.proposer,
        approver=req.approver,
        from_tier=AutonomyTier(req.from_tier),
        to_tier=AutonomyTier(req.to_tier),
        new_boundary=TierBoundary(
            max_competing_orders=req.new_boundary.max_competing_orders,
            max_exposure_inr=req.new_boundary.max_exposure_inr,
            notes=req.new_boundary.notes,
        ),
        track_record_count=req.track_record_count,
        track_record_minimum=req.track_record_minimum,
        track_record_label=req.track_record_label,
        reversal_trigger=(
            ReversalTrigger(
                name=req.reversal_trigger.name,
                metric=req.reversal_trigger.metric,
                comparison=req.reversal_trigger.comparison,
                threshold=req.reversal_trigger.threshold,
                window_label=req.reversal_trigger.window_label,
            )
            if req.reversal_trigger is not None
            else None
        ),
        re_review_date=date.fromisoformat(req.re_review_date) if req.re_review_date else None,
        rationale=req.rationale,
    )
    try:
        today = date.fromisoformat(req.today)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid today date: {req.today!r}") from exc

    state = make_initial_governance_state(proposal, today)
    thread_id = str(uuid.uuid4())
    _run_meta[thread_id] = {"flow": "governance", "initial_state": state}
    return CreateRunResponse(thread_id=thread_id)


class RecentDecisionIn(BaseModel):
    missed_commitment: bool = False
    escalated: bool = False


class ReversalCheckIn(BaseModel):
    agent_id: str
    recent_decisions: list[RecentDecisionIn]


@app.post("/api/reversal-checks", response_model=CreateRunResponse)
def create_reversal_check(req: ReversalCheckIn) -> CreateRunResponse:
    try:
        _registry.get(req.agent_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    state = make_initial_reversal_state(req.agent_id, [d.model_dump() for d in req.recent_decisions])
    thread_id = str(uuid.uuid4())
    _run_meta[thread_id] = {"flow": "reversal_check", "initial_state": state}
    return CreateRunResponse(thread_id=thread_id)


# ---------------------------------------------------------------------------
# WebSocket: stream a run, accept resume decisions
# ---------------------------------------------------------------------------
#
# Message shapes (server -> client), one JSON object per message:
#   {"type": "node",      "node": <node name>, "data": <that node's state update>}
#   {"type": "interrupt", "node": "escalate_operational" | "approver_signoff", "data": <interrupt payload>}
#   {"type": "done",      "data": <final graph state values>}
#   {"type": "error",     "data": {"message": ...}}
#
# Message shape (client -> server), sent only in reply to an "interrupt":
#   {"type": "resume", "approved": true, "approved_by": "Aditi Kulkarni", "notes": "..."}
#
# Only two nodes ever call interrupt(): escalate_operational (operational
# flow, out-of-boundary) and approver_signoff (governance flow, once all
# four policy-as-code conditions pass). reversal_check never interrupts,
# by design - the whole point of a reversal trigger is that it was
# decided in advance. Which node an interrupt belongs to is known from
# the run's own flow (tracked in _run_meta), since each flow has at most
# one interruptible node.


@app.websocket("/api/runs/{thread_id}/stream")
async def stream_run(websocket: WebSocket, thread_id: str) -> None:
    await websocket.accept()

    meta = _run_meta.get(thread_id)
    if meta is None:
        await websocket.send_json({"type": "error", "data": {"message": f"Unknown thread_id: {thread_id}"}})
        await websocket.close()
        return

    flow = meta["flow"]
    config = {"configurable": {"thread_id": thread_id}}
    stream_input: Any = meta["initial_state"]
    interrupt_node = "escalate_operational" if flow == "operational" else "approver_signoff"

    try:
        while True:
            interrupt_payload: Optional[dict[str, Any]] = None

            for chunk in _graph.stream(stream_input, config=config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    interrupt_payload = chunk["__interrupt__"][0].value
                    continue
                for node_name, node_update in chunk.items():
                    await websocket.send_json({"type": "node", "node": node_name, "data": node_update})

            if interrupt_payload is not None:
                await websocket.send_json({"type": "interrupt", "node": interrupt_node, "data": interrupt_payload})
                reply = await websocket.receive_json()
                if reply.get("type") != "resume":
                    await websocket.send_json(
                        {"type": "error", "data": {"message": f"Expected a 'resume' message, got {reply.get('type')!r}"}}
                    )
                    await websocket.close()
                    return
                stream_input = Command(
                    resume={
                        "approved": bool(reply.get("approved", False)),
                        "approved_by": reply.get("approved_by"),
                        "notes": reply.get("notes", ""),
                    }
                )
                continue

            # No interrupt this pass — the graph either just finished
            # (checked below) or, structurally, has nothing else that
            # would pause it mid-stream for this flow.
            snapshot = _graph.get_state(config)
            if not snapshot.next:  # reached END
                final_values = dict(snapshot.values)
                _record_if_logged(final_values)
                await websocket.send_json({"type": "done", "data": final_values})
            break

    except WebSocketDisconnect:
        return
    finally:
        await websocket.close()


# ---------------------------------------------------------------------------
# REST: the decision ledger — the live, growing audit trail
# ---------------------------------------------------------------------------


def _decision_record_to_dict(record) -> dict[str, Any]:
    return {
        "decision_id": record.decision_id,
        "agent_id": record.agent_id,
        "tier": record.tier,
        "timestamp": record.timestamp,
        "record_type": record.record_type,
        "inputs": record.inputs,
        "policy_version": record.policy_version,
        "model_version": record.model_version,
        "reasoning_path": [dict(s) for s in record.reasoning_path],
        "human_actions": [dict(h) for h in record.human_actions],
        "outcome": record.outcome,
        "amends": record.amends,
        "prev_hash": record.prev_hash,
        "record_hash": record.record_hash,
    }


@app.get("/api/ledger")
def list_ledger(limit: int = 50) -> dict[str, Any]:
    intact, broken_id = _ledger.verify_chain()
    recent_ids = list(reversed(_ledger_order))[: max(limit, 0)]
    records = [_decision_record_to_dict(_ledger.get(did)) for did in recent_ids]
    return {
        "records": records,
        "total_records": _ledger.records_count(),
        "chain_intact": intact,
        "chain_broken_at": broken_id,
    }


@app.get("/api/ledger/{decision_id}")
def get_ledger_decision(decision_id: str) -> dict[str, Any]:
    try:
        return _ledger.reconstruct(decision_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


# ---------------------------------------------------------------------------
# REST: chat — answers questions using the live registry + ledger
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str
    agent_id: Optional[str] = None
    decision_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ChatResponse(
            answer="Chat isn't configured — set OPENAI_API_KEY on the backend to enable it (see .env.example)."
        )

    from openai import OpenAI  # imported lazily so the rest of the API works without the package installed

    client = OpenAI(api_key=api_key)

    intact, _broken_id = _ledger.verify_chain()
    context_parts = [
        "Known agents and their current autonomy tier/boundary: "
        + json.dumps([_agent_to_dict(a) for a in _registry.all_agents()], indent=2),
        f"Decision ledger: {_ledger.records_count()} records written so far, chain_intact={intact}.",
    ]
    if req.agent_id:
        try:
            context_parts.append(f"Focused agent: {json.dumps(_agent_to_dict(_registry.get(req.agent_id)), indent=2)}")
        except KeyError:
            context_parts.append(f"No agent registered under id {req.agent_id!r}.")
    if req.decision_id:
        try:
            context_parts.append(f"Focused decision reconstruction:\n{json.dumps(_ledger.reconstruct(req.decision_id), indent=2)}")
        except KeyError:
            context_parts.append(f"No decision record found for id {req.decision_id!r}.")

    system_prompt = (
        "You are a policy-gate assistant for a fictional auto-components supply chain. "
        "Answer only from the context given; if the answer isn't in the context, say so "
        "plainly rather than guessing. Keep answers to 2-3 sentences.\n\n" + "\n\n".join(context_parts)
    )

    completion = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.question},
        ],
    )
    return ChatResponse(answer=completion.choices[0].message.content or "")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
