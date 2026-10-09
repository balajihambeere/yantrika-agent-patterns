"""
FastAPI wrapper around reasoning_graph.py — exposes the same LangGraph
Sense -> Weigh -> Recommend -> (Escalate interrupt) -> Act -> Log loop used
by demo.py, over HTTP + a WebSocket, so a browser can drive it instead of a
terminal auto-approving/overriding every interrupt.

No business logic lives here. reasoning_graph.py and reasoning_factors.py
(alongside demo.py, in this same directory) remain the single source of
truth for the loop and the five-factor weighing arithmetic — this file only
does three things:
  1. Serves the 3 scripted sensing-cycle scenarios (from
     data/sensing_cycles.json) as summaries for a card grid.
  2. Creates a "run" (one graph thread) for a chosen scenario.
  3. Streams that run's sense/weigh/recommend/interrupt/act/log events over
     a WebSocket, and accepts the human's approve/override decision back
     over the same socket, exactly the way demo.py drives the graph from a
     terminal loop — just over the wire instead of scripted.

Run with:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent  # .../03-reasoning-loop-allocation/backend

from reasoning_graph import SensingCycle, build_graph, make_initial_state  # noqa: E402
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.types import Command  # noqa: E402


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

app = FastAPI(title="Reasoning Loop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

SKU = "4200-series-harness"  # the one constrained SKU every scripted cycle below competes over

SCENARIOS_PATH = BASE_DIR / "data" / "sensing_cycles.json"
_cycles_raw: list[SensingCycle] = json.loads(SCENARIOS_PATH.read_text())

# Hand-written, honest summaries of what each scripted cycle demonstrates —
# metadata for the card grid, not a business-logic field. Falls back to a
# generic description (built from the cycle's own data) for any cycle this
# map doesn't recognize, so adding a 4th scenario to the JSON later never
# breaks the API.
_SCENARIO_DESCRIPTIONS: dict[str, str] = {
    "Cycle 1 — routine replenishment, low stakes": (
        "Two small accounts, factors clearly agree, exposure on the losing side is "
        "comfortably under the bounded-autonomy threshold — expect the system to "
        "allocate on its own, no escalation."
    ),
    "Cycle 2 — the three-way harness-batch conflict": (
        "3-way allocation: Bosch / Continental Fasteners / Shivaji Precision Works, "
        "all competing for the same shrinking batch. Exposure is well above threshold — "
        "expect an escalation carrying the full per-factor reasoning."
    ),
    "Cycle 3 — the divergence: a shutdown nobody told the model about": (
        "The weighted factors flag a contracted account as urgent, but a plant "
        "shutdown the model has no input for argues the opposite. Expect an "
        "escalation — try overriding the recommendation."
    ),
}


def _describe(cycle: SensingCycle) -> str:
    label = cycle["label"]
    if label in _SCENARIO_DESCRIPTIONS:
        return _SCENARIO_DESCRIPTIONS[label]
    accounts = " / ".join(o["account"] for o in cycle["orders"])
    return f"{len(cycle['orders'])}-way allocation: {accounts}."


# scenario_id -> SensingCycle, so a run can be created for a chosen scenario
# and the WS handler can look up the cycle it should drive the graph through.
_scenarios_by_id: dict[str, SensingCycle] = {str(i): cycle for i, cycle in enumerate(_cycles_raw)}

_checkpointer = InMemorySaver()
_graph = build_graph().compile(checkpointer=_checkpointer)

# thread_id -> scenario_id, so the WS handler knows which scripted cycle a
# run uses.
_run_scenario: dict[str, str] = {}

# scenario_id -> most recently completed run's log, used as chat context.
# Kept in memory only — this is a demo app, not a system of record.
_last_completed_log: dict[str, list[dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# REST: scenarios
# ---------------------------------------------------------------------------

class OrderSummary(BaseModel):
    account: str
    requested_units: int
    note: str


class Scenario(BaseModel):
    id: str
    label: str
    sku: str
    available_units: int
    orders: list[OrderSummary]
    description: str


@app.get("/api/scenarios", response_model=list[Scenario])
def list_scenarios() -> list[Scenario]:
    return [
        Scenario(
            id=scenario_id,
            label=cycle["label"],
            sku=SKU,
            available_units=cycle["available_units"],
            orders=[
                OrderSummary(account=o["account"], requested_units=o["requested_units"], note=o["note"])
                for o in cycle["orders"]
            ],
            description=_describe(cycle),
        )
        for scenario_id, cycle in _scenarios_by_id.items()
    ]


# ---------------------------------------------------------------------------
# REST: create a run
# ---------------------------------------------------------------------------

class CreateRunRequest(BaseModel):
    scenario_id: str


class CreateRunResponse(BaseModel):
    thread_id: str


@app.post("/api/runs", response_model=CreateRunResponse)
def create_run(req: CreateRunRequest) -> CreateRunResponse:
    if req.scenario_id not in _scenarios_by_id:
        raise HTTPException(status_code=404, detail=f"Unknown scenario_id: {req.scenario_id}")

    thread_id = str(uuid.uuid4())
    _run_scenario[thread_id] = req.scenario_id
    return CreateRunResponse(thread_id=thread_id)


# ---------------------------------------------------------------------------
# WebSocket: stream a run, accept resume decisions
# ---------------------------------------------------------------------------
#
# Message shapes (server -> client), one JSON object per message:
#   {"type": "sense",     "data": {"label", "available_units", "orders"}}
#   {"type": "weigh",     "data": [FactorScores, ...]}
#   {"type": "recommend", "data": {"sku", "cycle_label", "available_units",
#                                   "ranking", "allocation", "requires_human",
#                                   "clear_agreement", "exposure_on_losing_side", "reason"}}
#   {"type": "interrupt", "data": {"sku", "cycle_label", "reason",
#                                   "exposure_on_losing_side", "clear_agreement",
#                                   "reasoning", "recommended_allocation"}}   # waiting for the client now
#   {"type": "act",       "data": {"allocation", "decided_by", "autonomous",
#                                   "overridden", "override_reason"}}
#   {"type": "log",       "data": {...full log entry...}}
#   {"type": "done",      "data": {"log": [...]}}                           # graph reached END, socket closes
#   {"type": "error",     "data": {"message"}}
#
# Message shape (client -> server), sent only in reply to an "interrupt":
#   {"type": "resume", "decision": "approve", "decided_by": "Arjun"}
#   {"type": "resume", "decision": "override", "decided_by": "Arjun",
#    "allocation": {"Account A": 50, "Account B": 150}, "reason": "..."}

@app.websocket("/api/runs/{thread_id}/stream")
async def stream_run(websocket: WebSocket, thread_id: str) -> None:
    await websocket.accept()

    scenario_id = _run_scenario.get(thread_id)
    if scenario_id is None:
        await websocket.send_json({"type": "error", "data": {"message": f"Unknown thread_id: {thread_id}"}})
        await websocket.close()
        return

    cycle = _scenarios_by_id[scenario_id]
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = make_initial_state(sku=SKU, pending_cycles=[cycle])
    stream_input: Any = initial_state

    try:
        while True:
            interrupt_payload: Optional[dict[str, Any]] = None

            for chunk in _graph.stream(stream_input, config=config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    interrupt_payload = chunk["__interrupt__"][0].value
                    continue
                for node_name, node_update in chunk.items():
                    if node_name == "sense" and node_update.get("cycle"):
                        await websocket.send_json({"type": "sense", "data": node_update["cycle"]})
                    elif node_name == "weigh":
                        await websocket.send_json({"type": "weigh", "data": node_update["reasoning"]})
                    elif node_name == "recommend":
                        await websocket.send_json({"type": "recommend", "data": node_update["recommendation"]})
                    elif node_name == "act":
                        await websocket.send_json({"type": "act", "data": node_update["decision"]})
                    elif node_name == "log":
                        await websocket.send_json({"type": "log", "data": node_update["log"][-1]})

            if interrupt_payload is not None:
                await websocket.send_json({"type": "interrupt", "data": interrupt_payload})
                reply = await websocket.receive_json()
                if reply.get("type") != "resume":
                    await websocket.send_json(
                        {"type": "error", "data": {"message": f"Expected a 'resume' message, got {reply.get('type')!r}"}}
                    )
                    await websocket.close()
                    return

                resume_payload: dict[str, Any] = {
                    "decision": reply.get("decision"),
                    "decided_by": reply.get("decided_by"),
                }
                if reply.get("decision") == "override":
                    resume_payload["allocation"] = reply.get("allocation")
                    resume_payload["reason"] = reply.get("reason")

                stream_input = Command(resume=resume_payload)
                continue

            # No interrupt this pass — the graph either just finished
            # (checked below) or, structurally, has nothing else that would
            # pause it mid-stream, so there's nothing else to loop on here.
            snapshot = _graph.get_state(config)
            if not snapshot.next:  # reached END
                log = snapshot.values.get("log", [])
                _last_completed_log[scenario_id] = log
                await websocket.send_json({"type": "done", "data": {"log": log}})
            break

    except WebSocketDisconnect:
        return
    finally:
        await websocket.close()


# ---------------------------------------------------------------------------
# REST: chat — answers questions using the most recently completed run's log
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str
    scenario_id: Optional[str] = None


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

    context_parts = [
        f"Known scenarios: {', '.join(c['label'] for c in _cycles_raw)}. All compete over SKU {SKU}."
    ]
    if req.scenario_id and req.scenario_id in _last_completed_log:
        log = _last_completed_log[req.scenario_id]
        context_parts.append(f"Most recent run log for scenario {req.scenario_id}:\n{json.dumps(log, indent=2)}")
    elif req.scenario_id:
        context_parts.append(f"No completed run yet for scenario {req.scenario_id} — only its scripted cycle data is known.")

    system_prompt = (
        "You are an allocation-reasoning assistant for a constrained-component supply demo. "
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
