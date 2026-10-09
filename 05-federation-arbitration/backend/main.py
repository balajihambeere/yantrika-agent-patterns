"""
FastAPI wrapper around federation_graph.py — exposes the two-plant
arbitration layer (parallel sense_pune / sense_nashik -> arbitrate ->
[act_independent | act_unilateral | confirm_neha -> confirm_shalini ->
coordinated_act] -> log) used by demo.py, over HTTP + a WebSocket, so a
browser can drive the two *separate* named-human confirmations — Neha's,
then Shalini's — instead of a terminal auto-resuming every interrupt.

No business logic lives here. This file only does three things:
  1. Serves the 3 scripted scenarios (from data/federation_scenarios.json)
     for a scenario picker.
  2. Creates a "run" (one graph thread) for a chosen scenario.
  3. Streams that run's sense/arbitrate/interrupt/act/log events over a
     WebSocket, and accepts the human's confirm/decline decision back
     over the same socket for each of Neha's and Shalini's interrupts,
     exactly the way demo.py drives the graph from a terminal loop — just
     over the wire, with a real human at each step instead of a scripted
     response.

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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from federation_graph import (
    DEFAULT_CONNECTION_TIER,
    NASHIK_CONFIRMER,
    PUNE_CONFIRMER,
    build_graph,
    make_initial_state,
)
from site_agents import SitePosition, SupplierCapacity
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

BASE_DIR = Path(__file__).resolve().parent  # .../05-federation-arbitration/backend


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

app = FastAPI(title="Federation Arbitration API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared, repo-level fastener product images (this example's domain is a
# fastener SKU family, not wiring harnesses — see shared-fastener-images/).
FASTENER_IMAGES_DIR = BASE_DIR.parent.parent / "shared-fastener-images"
if FASTENER_IMAGES_DIR.exists():
    app.mount("/fastener-images", StaticFiles(directory=str(FASTENER_IMAGES_DIR)), name="fastener-images")

# All 3 scenarios are the same SKU family (fastener_family_F12), so one
# representative image is used consistently across all of them, rather than
# implying they're different physical parts.
SCENARIO_IMAGE = "/fastener-images/m8x40-hex-flange-bolt.png"

DATA_PATH = BASE_DIR / "data" / "federation_scenarios.json"
_SCENARIO_DATA = json.loads(DATA_PATH.read_text())
SKU_FAMILY = _SCENARIO_DATA["sku_family"]
SUPPLIER: SupplierCapacity = {
    "supplier": _SCENARIO_DATA["supplier"]["supplier"],
    "sku_family": SKU_FAMILY,
    "open_capacity": _SCENARIO_DATA["supplier"]["open_capacity"],
}


def _site_position(key: str) -> SitePosition:
    data = _SCENARIO_DATA["site_positions"][key]
    return {
        "site": data["site"],
        "sku_family": SKU_FAMILY,
        "on_hand": data["on_hand"],
        "buffer_target": data["buffer_target"],
    }


# The 3 scripted scenarios, mirroring demo.py's three cases. Scenarios
# "near_miss" and "shalini_declines" share the same underlying site
# positions (Pune's surplus, Nashik's shortfall) — the near-miss collision
# is always there; what differs is only what a real human decides at
# Neha's and Shalini's confirmation steps, which in this interactive app is
# a live decision made by whoever is running it, not scripted data. Both
# cards exist, described by what to try, rather than by distinct inputs.
SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "near_miss",
        "title": "Pune's surplus vs. Nashik's rush order",
        "description": (
            "Fastener family F12 — Pune is sitting on real surplus, Nashik is genuinely short, "
            "six weeks running. Both sites' agents are individually right; acted on at the same "
            "time they'd over-commit. Approve both Neha's and Shalini's confirmations to watch "
            "the collision resolve into one coordinated transfer instead."
        ),
        "pune_key": "pune_surplus",
        "nashik_key": "nashik_short",
        "expect_collision": True,
    },
    {
        "id": "observe_only",
        "title": "Pune observes Nashik, finds nothing to flag",
        "description": (
            "Fastener family F12 — Pune still has surplus and genuinely looks at Nashik's "
            "position under the pilot connection, but Nashik is comfortably within its own "
            "buffer target this cycle. No collision, no interrupt — the observe tier doing "
            "what it's supposed to do most of the time: inform a decision not to act."
        ),
        "pune_key": "pune_surplus",
        "nashik_key": "nashik_comfortable",
        "expect_collision": False,
    },
    {
        "id": "shalini_declines",
        "title": "The same near-miss, except Shalini isn't convinced",
        "description": (
            "Fastener family F12 — the identical near-miss as above. Try approving Neha's "
            "confirmation but declining Shalini's: the run falls back to each site handling its "
            "own shortfall independently — visible and logged, instead of silently colliding."
        ),
        "pune_key": "pune_surplus",
        "nashik_key": "nashik_short",
        "expect_collision": True,
    },
]
_SCENARIOS_BY_ID = {s["id"]: s for s in SCENARIOS}

_checkpointer = InMemorySaver()
_graph = build_graph().compile(checkpointer=_checkpointer)

# thread_id -> scenario_id, so the WS handler knows which scenario's data a
# run uses.
_run_scenario: dict[str, str] = {}

# scenario_id -> most recently completed run's log, used as chat context.
# Kept in memory only — this is a demo app, not a system of record.
_last_completed_log: dict[str, list[dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# REST: scenarios
# ---------------------------------------------------------------------------

class SitePositionSummary(BaseModel):
    site: str
    on_hand: int
    buffer_target: int


class Scenario(BaseModel):
    id: str
    title: str
    description: str
    sku_family: str
    connection_tier: str
    supplier: str
    pune_position: SitePositionSummary
    nashik_position: SitePositionSummary
    expect_collision: bool
    image: Optional[str] = None


@app.get("/api/scenarios", response_model=list[Scenario])
def list_scenarios() -> list[Scenario]:
    out: list[Scenario] = []
    for s in SCENARIOS:
        pune = _site_position(s["pune_key"])
        nashik = _site_position(s["nashik_key"])
        out.append(
            Scenario(
                id=s["id"],
                title=s["title"],
                description=s["description"],
                sku_family=SKU_FAMILY,
                connection_tier=DEFAULT_CONNECTION_TIER,
                supplier=SUPPLIER["supplier"],
                pune_position=SitePositionSummary(
                    site=pune["site"], on_hand=pune["on_hand"], buffer_target=pune["buffer_target"]
                ),
                nashik_position=SitePositionSummary(
                    site=nashik["site"], on_hand=nashik["on_hand"], buffer_target=nashik["buffer_target"]
                ),
                expect_collision=s["expect_collision"],
                image=SCENARIO_IMAGE,
            )
        )
    return out


# ---------------------------------------------------------------------------
# REST: create a run
# ---------------------------------------------------------------------------

class CreateRunRequest(BaseModel):
    scenario_id: str


class CreateRunResponse(BaseModel):
    thread_id: str


@app.post("/api/runs", response_model=CreateRunResponse)
def create_run(req: CreateRunRequest) -> CreateRunResponse:
    scenario = _SCENARIOS_BY_ID.get(req.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"Unknown scenario_id: {req.scenario_id}")

    thread_id = str(uuid.uuid4())
    _run_scenario[thread_id] = req.scenario_id
    return CreateRunResponse(thread_id=thread_id)


# ---------------------------------------------------------------------------
# WebSocket: stream a run, accept resume decisions
# ---------------------------------------------------------------------------
#
# Message shapes (server -> client), one JSON object per message:
#   {"type": "sense_pune",   "data": LocalRecommendation}
#   {"type": "sense_nashik", "data": LocalRecommendation}
#   {"type": "arbitrate",    "data": {"collision": CollisionReport | null}}
#   {"type": "interrupt",    "data": {"approver_key": "neha"|"shalini", "confirmer", "role",
#                                      "collision", "proposed_action"}}   # waiting for the client now
#   {"type": "act",          "data": decision}        # decision["type"] says which branch fired
#   {"type": "log",          "data": LogEntry}
#   {"type": "done",         "data": {"log": [...]}}  # graph reached END, socket closes
#   {"type": "error",        "data": {"message"}}
#
# Message shape (client -> server), sent only in reply to an "interrupt":
#   {"type": "resume", "confirmed": true, "confirmed_by": "Neha Joshi", "note": "..."}
#
# `confirmed_by` is informational only — the server always falls back to the
# interrupt's own named confirmer if the client omits it, so a reply can
# never be misattributed to the wrong approver.

def _approver_key(confirmer: str) -> str:
    return "neha" if confirmer == PUNE_CONFIRMER else "shalini"


@app.websocket("/api/runs/{thread_id}/stream")
async def stream_run(websocket: WebSocket, thread_id: str) -> None:
    await websocket.accept()

    scenario_id = _run_scenario.get(thread_id)
    if scenario_id is None:
        await websocket.send_json({"type": "error", "data": {"message": f"Unknown thread_id: {thread_id}"}})
        await websocket.close()
        return

    scenario = _SCENARIOS_BY_ID[scenario_id]
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = make_initial_state(
        pune_position=_site_position(scenario["pune_key"]),
        nashik_position=_site_position(scenario["nashik_key"]),
        supplier=SUPPLIER,
        connection_tier=DEFAULT_CONNECTION_TIER,
        observe_nashik_from_pune=True,
    )

    stream_input: Any = initial_state

    try:
        while True:
            interrupt_payload: Optional[dict[str, Any]] = None

            for chunk in _graph.stream(stream_input, config=config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    interrupt_payload = chunk["__interrupt__"][0].value
                    continue
                for node_name, node_update in chunk.items():
                    if node_name == "sense_pune":
                        await websocket.send_json(
                            {"type": "sense_pune", "data": node_update["pune_recommendation"]}
                        )
                    elif node_name == "sense_nashik":
                        await websocket.send_json(
                            {"type": "sense_nashik", "data": node_update["nashik_recommendation"]}
                        )
                    elif node_name == "arbitrate":
                        await websocket.send_json(
                            {"type": "arbitrate", "data": {"collision": node_update["collision"]}}
                        )
                    elif node_name in (
                        "act_independent",
                        "act_unilateral",
                        "coordinated_act",
                        "fallback_independent",
                    ):
                        await websocket.send_json({"type": "act", "data": node_update["decision"]})
                    elif node_name == "log":
                        await websocket.send_json({"type": "log", "data": node_update["log"][-1]})

            if interrupt_payload is not None:
                payload = dict(interrupt_payload)
                payload["approver_key"] = _approver_key(payload["confirmer"])
                await websocket.send_json({"type": "interrupt", "data": payload})
                reply = await websocket.receive_json()
                if reply.get("type") != "resume":
                    await websocket.send_json(
                        {
                            "type": "error",
                            "data": {"message": f"Expected a 'resume' message, got {reply.get('type')!r}"},
                        }
                    )
                    await websocket.close()
                    return
                stream_input = Command(
                    resume={
                        "confirmed": bool(reply.get("confirmed")),
                        "confirmed_by": reply.get("confirmed_by") or payload["confirmer"],
                        "note": reply.get("note", ""),
                    }
                )
                continue

            # No interrupt this pass — the graph either just finished (checked
            # below) or, structurally, has nothing else that would pause it
            # mid-stream, so there's nothing else to loop on here.
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
        f"Known scenarios: {', '.join(s['id'] + ' (' + s['title'] + ')' for s in SCENARIOS)}.",
        f"The two named human confirmers are {PUNE_CONFIRMER} (Pune procurement lead) and "
        f"{NASHIK_CONFIRMER} (Nashik procurement lead). Neha's confirmation is always asked "
        f"before Shalini's, and a decline by either one skips the other and falls back to "
        f"independent action.",
    ]
    if req.scenario_id and req.scenario_id in _last_completed_log:
        log = _last_completed_log[req.scenario_id]
        context_parts.append(f"Most recent run log for {req.scenario_id}:\n{json.dumps(log, indent=2)}")
    elif req.scenario_id:
        context_parts.append(
            f"No completed run yet for {req.scenario_id} — only its static scenario data is known."
        )

    system_prompt = (
        "You are an assistant for a two-plant federation-arbitration demo. "
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
