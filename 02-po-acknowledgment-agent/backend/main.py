"""
FastAPI wrapper around ../agent_graph.py — exposes the same LangGraph
Trigger -> Perceive -> Decide -> (human_approval | escalate) -> Act -> Log
anatomy used by ../demo.py, over HTTP + a WebSocket, so a browser can drive
one bounded PO-acknowledgment run instead of a terminal auto-approving
every interrupt.

No business logic lives here. This file only does four things:
  1. Serves the 8 scripted PO scenarios (from ../data/demo_scenarios.json)
     for a scenario grid.
  2. Creates a "run" (one graph thread) for a chosen scenario, with a
     `supervised` flag the caller controls.
  3. Streams that run's trigger/perceive/decide/interrupt/act/log events
     over a WebSocket, and accepts the human's decision back over the
     same socket — exactly the way demo.py drives the graph from a
     terminal loop, just over the wire instead of scripted.
  4. A graceful-degradation /api/chat that only ever calls OpenAI if an
     API key is configured; otherwise it answers from context, never
     crashes.

The graph itself (agent_graph.py, perception.py, data/) lives alongside
this file, along with demo.py and its own tests — this file reuses it
rather than duplicating it.

Run with:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import copy
import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_graph import build_graph, make_initial_state
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

BACKEND_DIR = Path(__file__).resolve().parent  # .../02-po-acknowledgment-agent/backend


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


_load_dotenv(BACKEND_DIR / ".env")

# ---------------------------------------------------------------------------
# app setup
# ---------------------------------------------------------------------------

app = FastAPI(title="PO Acknowledgment Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared, repo-level fastener product images (this example's domain is
# fastener suppliers, not wiring harnesses — see shared-fastener-images/).
FASTENER_IMAGES_DIR = BACKEND_DIR.parent.parent / "shared-fastener-images"
if FASTENER_IMAGES_DIR.exists():
    app.mount("/fastener-images", StaticFiles(directory=str(FASTENER_IMAGES_DIR)), name="fastener-images")

SCENARIOS_PATH = BACKEND_DIR / "data" / "demo_scenarios.json"
_scenarios_raw: dict[str, dict[str, Any]] = json.loads(SCENARIOS_PATH.read_text())

# One representative fastener product image per scenario, purely for visual
# variety on the scenario grid — the image doesn't correspond to a specific
# part named in the PO data, which doesn't go into that level of detail.
SCENARIO_IMAGES: dict[str, str] = {
    "clean_confirmation": "/fastener-images/m8x40-hex-flange-bolt.png",
    "chase_needed": "/fastener-images/m10x30-hex-flange-bolt.png",
    "schedule_slip": "/fastener-images/m6x20-socket-head-cap-screw.png",
    "ambiguous_reply": "/fastener-images/m8-hex-flange-nut.png",
    "exception_owner": "/fastener-images/m8-spring-washer.png",
    "no_exception": "/fastener-images/5mm-pop-rivet.png",
    "good_scan": "/fastener-images/m8x25-u-bolt-clamp.png",
    "bad_scan": "/fastener-images/m10-wheel-stud.png",
}

# One-line situation summaries for the scenario grid — not stored in the
# JSON itself (which only carries the PO/inbox data the graph needs), so
# they live here, next to the id they describe. Text mirrors demo.py's own
# docstrings for each scenario function.
SCENARIO_SUMMARIES: dict[str, str] = {
    "clean_confirmation": (
        "Deccan Fasteners confirms exactly, but the reply is mis-threaded under an "
        "old invoice thread — reference-number matching still finds it."
    ),
    "chase_needed": "Konkan Metal Works: 48 hours elapsed with nothing resembling an acknowledgment.",
    "schedule_slip": (
        "Satpura Components confirms the quantity but quietly slips the delivery date "
        "by six days, buried in routine-sounding text."
    ),
    "ambiguous_reply": "Bharat Precision Forge's standard non-answer: “Noted, will advise.”",
    "exception_owner": (
        "Bharat Precision Forge confirms with no date named — Neha's supplier-specific "
        "exception reads this as unclear, not confirmed."
    ),
    "no_exception": (
        "Girnar Components sends the same date-less confirmation text — no supplier "
        "exception applies, so it reads as a plain confirmation."
    ),
    "good_scan": "Matheran Precision Works' stamped-PO scan parses cleanly at high confidence.",
    "bad_scan": (
        "Matheran Precision Works' stamped-PO scan parses at low confidence — "
        "escalates rather than trusting a blurry read."
    ),
}

_checkpointer = InMemorySaver()
_graph = build_graph().compile(checkpointer=_checkpointer)

# thread_id -> {"scenario_id", "supervised"}, so the WS handler knows which
# scenario's PO data a run uses, and in which autonomy stage.
_run_meta: dict[str, dict[str, Any]] = {}

# scenario_id -> most recently completed run's log, used as chat context.
# Kept in memory only — this is a demo app, not a system of record.
_last_completed_log: dict[str, list[dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# REST: scenarios
# ---------------------------------------------------------------------------

class Scenario(BaseModel):
    id: str
    po_number: str
    supplier: str
    ordered_qty: int
    ordered_date: str
    hours_since_po: int
    summary: str
    image: Optional[str] = None


@app.get("/api/scenarios", response_model=list[Scenario])
def list_scenarios() -> list[Scenario]:
    return [
        Scenario(
            id=scenario_id,
            po_number=po["po_number"],
            supplier=po["supplier"],
            ordered_qty=po["ordered_qty"],
            ordered_date=po["ordered_date"],
            hours_since_po=po["hours_since_po"],
            summary=SCENARIO_SUMMARIES.get(scenario_id, ""),
            image=SCENARIO_IMAGES.get(scenario_id),
        )
        for scenario_id, po in _scenarios_raw.items()
    ]


# ---------------------------------------------------------------------------
# REST: create a run
# ---------------------------------------------------------------------------

class CreateRunRequest(BaseModel):
    scenario_id: str
    supervised: bool = True


class CreateRunResponse(BaseModel):
    thread_id: str


@app.post("/api/runs", response_model=CreateRunResponse)
def create_run(req: CreateRunRequest) -> CreateRunResponse:
    if req.scenario_id not in _scenarios_raw:
        raise HTTPException(status_code=404, detail=f"Unknown scenario_id: {req.scenario_id}")

    thread_id = str(uuid.uuid4())
    _run_meta[thread_id] = {"scenario_id": req.scenario_id, "supervised": req.supervised}
    return CreateRunResponse(thread_id=thread_id)


# ---------------------------------------------------------------------------
# WebSocket: stream a run, accept resume decisions
# ---------------------------------------------------------------------------
#
# Message shapes (server -> client), one JSON object per message:
#   {"type": "trigger",  "data": {po_number, supplier, reason, matched_via, hours_since_po}}
#   {"type": "perceive", "data": {situation, confidence, extracted_qty, extracted_date,
#                                  attachment_confidence, notes, source}}
#   {"type": "decide",   "data": {action, requires_escalation, hard_invariant_triggered,
#                                  risk, approved, approved_by, rationale}}
#   {"type": "interrupt","data": {...}}   # waiting for the client now. "kind" tells you which:
#       kind == "action_approval" -> {kind, po_number, supplier, proposed_action, rationale}
#       kind == "escalation"      -> {kind, po_number, supplier, action, rationale,
#                                      perceived_situation, confidence, extracted_qty,
#                                      extracted_date, ordered_qty, ordered_date,
#                                      hard_invariant_triggered}
#   {"type": "act",      "data": {outcome, approved, approved_by}}
#   {"type": "log",      "data": {...}}   # the one log entry this run appended
#   {"type": "done",     "data": {"log": [...]}}   # graph reached END, socket closes
#   {"type": "error",    "data": {"message"}}
#
# Message shapes (client -> server), sent only in reply to an "interrupt",
# shape depends on the interrupt's "kind":
#   {"type": "resume", "kind": "action_approval", "approved": true, "approved_by": "Neha"}
#   {"type": "resume", "kind": "escalation", "acknowledged_by": "Neha", "note": "..."}

@app.websocket("/api/runs/{thread_id}/stream")
async def stream_run(websocket: WebSocket, thread_id: str) -> None:
    await websocket.accept()

    meta = _run_meta.get(thread_id)
    if meta is None:
        await websocket.send_json({"type": "error", "data": {"message": f"Unknown thread_id: {thread_id}"}})
        await websocket.close()
        return

    scenario_id = meta["scenario_id"]
    supervised = meta["supervised"]
    po = copy.deepcopy(_scenarios_raw[scenario_id])
    config = {"configurable": {"thread_id": thread_id}}

    stream_input: Any = make_initial_state(po, supervised=supervised)

    try:
        while True:
            interrupt_payload: Optional[dict[str, Any]] = None

            for chunk in _graph.stream(stream_input, config=config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    interrupt_payload = chunk["__interrupt__"][0].value
                    continue
                for node_name, node_update in chunk.items():
                    if node_name == "trigger":
                        await websocket.send_json({"type": "trigger", "data": node_update["trigger"]})
                    elif node_name == "perceive":
                        await websocket.send_json({"type": "perceive", "data": node_update["perception"]})
                    elif node_name == "decide":
                        await websocket.send_json({"type": "decide", "data": node_update["decision"]})
                    elif node_name == "act":
                        decision = node_update["decision"]
                        data = {
                            **node_update["action_result"],
                            "approved": decision["approved"],
                            "approved_by": decision["approved_by"],
                        }
                        await websocket.send_json({"type": "act", "data": data})
                    elif node_name == "log":
                        await websocket.send_json({"type": "log", "data": node_update["log"][-1]})
                    # "human_approval" and "escalate" node updates are
                    # deliberately not forwarded as their own message —
                    # their content (the approved decision / the
                    # acknowledged escalation) is already carried by the
                    # "interrupt" message that preceded them and the "log"
                    # entry that follows them.

            if interrupt_payload is not None:
                await websocket.send_json({"type": "interrupt", "data": interrupt_payload})
                reply = await websocket.receive_json()
                if reply.get("type") != "resume":
                    await websocket.send_json(
                        {"type": "error", "data": {"message": f"Expected a 'resume' message, got {reply.get('type')!r}"}}
                    )
                    await websocket.close()
                    return
                resume_payload = {k: v for k, v in reply.items() if k not in ("type", "kind")}
                stream_input = Command(resume=resume_payload)
                continue

            # No interrupt this pass — the graph either just finished
            # (checked below) or, structurally, has nothing else that
            # would pause it mid-stream.
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
# REST: chat — answers questions using scenario data + the most recently
# completed run's log for that scenario
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
        "Known PO scenarios: "
        + ", ".join(f"{sid} ({po['po_number']}, {po['supplier']})" for sid, po in _scenarios_raw.items())
        + "."
    ]
    if req.scenario_id and req.scenario_id in _scenarios_raw:
        context_parts.append(f"Scenario data for {req.scenario_id}:\n{json.dumps(_scenarios_raw[req.scenario_id], indent=2)}")
    if req.scenario_id and req.scenario_id in _last_completed_log:
        log = _last_completed_log[req.scenario_id]
        context_parts.append(f"Most recent run log for {req.scenario_id}:\n{json.dumps(log, indent=2)}")
    elif req.scenario_id:
        context_parts.append(f"No completed run yet for {req.scenario_id} — only its scripted PO/inbox data is known.")

    system_prompt = (
        "You are an assistant for a PO-acknowledgment agent demo (trigger -> perceive -> "
        "decide -> human_approval/escalate -> act -> log). Answer only from the context "
        "given; if the answer isn't in the context, say so plainly rather than guessing. "
        "Keep answers to 2-3 sentences.\n\n" + "\n\n".join(context_parts)
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
