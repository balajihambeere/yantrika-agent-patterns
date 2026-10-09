"""
FastAPI wrapper around coordination_graph.py — exposes the shared-registry /
deterministic-precedence-rulebook arbitration layer demo.py drives from a
terminal, over HTTP + a WebSocket, so a browser can submit claims and watch
them race against a live `LotRegistry` instead of replaying a scripted log.

Unlike 01-agentic-loop's main.py (one graph run == one product's whole run),
this example's fundamental unit of action is a single CLAIM. One shared
`LotRegistry` and one compiled graph are created ONCE, at module level, and
EVERY claim submission — no matter which scenario or plant it comes from —
is a brand new graph thread (`thread_id`) run against that SAME registry.
That is exactly what makes cross-claim collision detection possible: a
second plant's claim on a lot a first plant already holds only collides
because the registry persists across those separate runs.

No business logic lives here. This file only does four things:
  1. Serves the 4 demo.py scenarios (data/coordination_scenarios.json) —
     some of which require the client to submit TWO separate claims, in
     order, to actually reproduce a collision.
  2. Accepts one claim's fields and hands back a thread_id.
  3. Streams that one claim's run (submit_claim / check_registry / grant /
     arbitrate / the rare interrupt / grant_winner /
     suggest_alternate_for_loser / log / done) over a WebSocket, exactly the
     way demo.py drives the graph from a terminal loop — just over the wire.
  4. Exposes a live snapshot of the shared registry's open holds, plus its
     cross-claim audit log, for a "what's currently held, by whom" view.

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

from coordination_graph import build_graph, make_claim, make_initial_state
from lot_registry import LotRegistry
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

BACKEND_DIR = Path(__file__).resolve().parent  # .../06-registry-precedence-arbitration/backend


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

app = FastAPI(title="Registry Precedence Arbitration API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

SCENARIOS_PATH = BACKEND_DIR / "data" / "coordination_scenarios.json"
_scenario_data: dict[str, Any] = json.loads(SCENARIOS_PATH.read_text())
SUPPLIER: str = _scenario_data["supplier"]
BOLT_SKU: str = _scenario_data["bolt_sku"]
_CLAIMS: dict[str, dict[str, Any]] = _scenario_data["claims"]

# Shared, repo-level fastener product images (every scenario here is the
# same bolt SKU — see shared-fastener-images/). One consistent image for
# the one product in this example, rather than implying variety.
FASTENER_IMAGES_DIR = BACKEND_DIR.parent.parent / "shared-fastener-images"
if FASTENER_IMAGES_DIR.exists():
    app.mount("/fastener-images", StaticFiles(directory=str(FASTENER_IMAGES_DIR)), name="fastener-images")
PRODUCT_IMAGE = "/fastener-images/m8x40-hex-flange-bolt.png"

# ONE shared registry, ONE compiled graph, created once at module level —
# every claim submitted through this API, from any scenario or plant, is a
# new thread_id against this SAME registry. That is the whole point: it is
# what lets a second claim actually "see" a first claim still open.
_registry = LotRegistry()
_checkpointer = InMemorySaver()
_graph = build_graph(_registry).compile(checkpointer=_checkpointer)

# thread_id -> the Claim dict waiting to be streamed. Populated by
# POST /api/claims, consumed once the client opens the matching WebSocket.
_pending_claims: dict[str, dict[str, Any]] = {}

# sku -> most recently completed claim's final log entry, used as chat
# context. Kept in memory only — this is a demo app, not a system of record.
_last_completed_entry: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# REST: scenarios
# ---------------------------------------------------------------------------
#
# Narrative text for each of demo.py's four cases, each referencing claims
# by the exact keys used in data/coordination_scenarios.json. Cases 1 and 2
# each require TWO separate claim submissions (one per plant, in order) to
# actually reproduce the collision the registry is built to catch; cases 3
# and 4 are one claim and two claims respectively.

_SCENARIO_DEFS: list[dict[str, Any]] = [
    {
        "id": "discovery",
        "title": "The Discovery Case",
        "summary": (
            "The original Monday collision: Pune and Plant Two both place a hold on the "
            "same Nashik Precision Fasteners lot, four minutes apart. The rulebook ties on "
            "commitment tier and falls to days-of-cover — Plant Two, genuinely more urgent, "
            "is who the rule says should win."
        ),
        "expected_outcome": "arbitrated",
        "claim_keys": ["pune_monday", "plant_two_monday"],
        "claim_labels": ["Pune's claim", "Plant Two's claim (4 minutes later)"],
    },
    {
        "id": "success",
        "title": "The Success Case",
        "summary": (
            "Three weeks later, Pune and Plant Four reach for the same lot within minutes "
            "of each other. The registry catches it before either hold confirms — "
            "commitment tier alone resolves it, and the loser gets an immediate "
            "alternate-cover suggestion instead of a worthless hold."
        ),
        "expected_outcome": "arbitrated",
        "claim_keys": ["pune_later", "plant_four_later"],
        "claim_labels": ["Pune's claim", "Plant Four's claim (3 minutes later)"],
    },
    {
        "id": "non_colliding",
        "title": "A Non-Colliding Claim",
        "summary": (
            "Plant Three requests a completely different lot. No other plant is anywhere "
            "near it — granted immediately, no arbitration, no human."
        ),
        "expected_outcome": "granted",
        "claim_keys": ["plant_three_claim"],
        "claim_labels": ["Plant Three's claim"],
    },
    {
        "id": "dead_heat",
        "title": "A Genuine Dead Heat",
        "summary": (
            "Pune and Plant Two collide again, later, on a lot where every tier of the "
            "rulebook comes back tied — identical commitment tier, identical days-of-cover, "
            "identical timestamp. The graph genuinely pauses on interrupt() and escalates, "
            "by name, to Kavita Iyer's team. This is the rare exception, not the rule."
        ),
        "expected_outcome": "escalated",
        "claim_keys": ["pune_tie", "plant_two_tie"],
        "claim_labels": ["Pune's claim", "Plant Two's claim (identical in every tier)"],
    },
]


def _claim_payload(key: str) -> dict[str, Any]:
    c = _CLAIMS[key]
    return {
        "key": key,
        "plant": c["plant"],
        "supplier": c["supplier"],
        "lot_id": c["lot_id"],
        "sku": c["sku"],
        "quantity_needed": c["quantity_needed"],
        "commitment_tier": c.get("commitment_tier"),
        "days_of_cover": c.get("days_of_cover"),
        "requested_at": c["requested_at"],
        "requested_at_display": c["requested_at_display"],
    }


@app.get("/api/scenarios")
def list_scenarios() -> dict[str, Any]:
    scenarios = []
    for s in _SCENARIO_DEFS:
        claims = [
            {**_claim_payload(key), "label": label}
            for key, label in zip(s["claim_keys"], s["claim_labels"])
        ]
        scenarios.append(
            {
                "id": s["id"],
                "title": s["title"],
                "summary": s["summary"],
                "expected_outcome": s["expected_outcome"],
                "claim_count": len(claims),
                "claims": claims,
            }
        )
    return {"supplier": SUPPLIER, "bolt_sku": BOLT_SKU, "image": PRODUCT_IMAGE, "scenarios": scenarios}


# ---------------------------------------------------------------------------
# REST: submit one claim
# ---------------------------------------------------------------------------


class ClaimRequest(BaseModel):
    plant: str
    supplier: str
    lot_id: str
    sku: str
    quantity_needed: int
    requested_at: float
    requested_at_display: str
    commitment_tier: Optional[int] = None
    days_of_cover: Optional[float] = None


class ClaimResponse(BaseModel):
    thread_id: str
    claim_id: str


@app.post("/api/claims", response_model=ClaimResponse)
def submit_claim(req: ClaimRequest) -> ClaimResponse:
    thread_id = str(uuid.uuid4())
    claim_id = f"claim-{uuid.uuid4().hex[:8]}"
    claim = make_claim(
        claim_id=claim_id,
        plant=req.plant,
        supplier=req.supplier,
        lot_id=req.lot_id,
        sku=req.sku,
        quantity_needed=req.quantity_needed,
        requested_at=req.requested_at,
        requested_at_display=req.requested_at_display,
        commitment_tier=req.commitment_tier,
        days_of_cover=req.days_of_cover,
    )
    _pending_claims[thread_id] = claim
    return ClaimResponse(thread_id=thread_id, claim_id=claim_id)


# ---------------------------------------------------------------------------
# WebSocket: stream one claim's run, accept a resume decision if (rarely)
# the rulebook escalates.
# ---------------------------------------------------------------------------
#
# Message shapes (server -> client), one JSON object per message:
#   {"type": "submit_claim",              "data": <log entry: event, plant, lot_id, claim>}
#   {"type": "check_registry",            "data": {"collisions": [<claim>, ...]}}
#   {"type": "grant",                     "data": <outcome>}                      # no collision
#   {"type": "arbitrate",                 "data": <arbitration>}                  # collision found
#   {"type": "interrupt",                 "data": {"reason", "competing_claims", "escalated_to"}}
#   {"type": "escalate_to_kavitas_team",  "data": <arbitration with resolved_by_human>}
#   {"type": "grant_winner",              "data": <outcome>}
#   {"type": "suggest_alternate_for_loser","data": {"alternate_suggestions": [...]}}
#   {"type": "log",                       "data": <full audit-log entry>}
#   {"type": "done",                      "data": {"log": [...]}}                 # graph reached END
#   {"type": "error",                     "data": {"message"}}
#
# Message shape (client -> server), sent only in reply to an "interrupt" —
# escalate_to_kavitas_team's interrupt() expects exactly this shape:
#   {"type": "resume", "winner_plant": "...", "decided_by": "...", "note": "..."}

@app.websocket("/api/claims/{thread_id}/stream")
async def stream_claim(websocket: WebSocket, thread_id: str) -> None:
    await websocket.accept()

    claim = _pending_claims.pop(thread_id, None)
    if claim is None:
        await websocket.send_json({"type": "error", "data": {"message": f"Unknown thread_id: {thread_id}"}})
        await websocket.close()
        return

    config = {"configurable": {"thread_id": thread_id}}
    stream_input: Any = make_initial_state(claim)

    try:
        while True:
            interrupt_payload: Optional[dict[str, Any]] = None

            for chunk in _graph.stream(stream_input, config=config, stream_mode="updates"):
                if "__interrupt__" in chunk:
                    interrupt_payload = chunk["__interrupt__"][0].value
                    continue
                for node_name, update in chunk.items():
                    if node_name == "submit_claim":
                        await websocket.send_json({"type": "submit_claim", "data": update["log"][-1]})
                    elif node_name == "check_registry":
                        await websocket.send_json(
                            {"type": "check_registry", "data": {"collisions": update["collisions"]}}
                        )
                    elif node_name == "grant":
                        await websocket.send_json({"type": "grant", "data": update["outcome"]})
                    elif node_name == "arbitrate":
                        await websocket.send_json({"type": "arbitrate", "data": update["arbitration"]})
                    elif node_name == "escalate_to_kavitas_team":
                        await websocket.send_json(
                            {"type": "escalate_to_kavitas_team", "data": update["arbitration"]}
                        )
                    elif node_name == "grant_winner":
                        await websocket.send_json({"type": "grant_winner", "data": update["outcome"]})
                    elif node_name == "suggest_alternate_for_loser":
                        await websocket.send_json(
                            {
                                "type": "suggest_alternate_for_loser",
                                "data": {"alternate_suggestions": update["arbitration"]["alternate_suggestions"]},
                            }
                        )
                    elif node_name == "log":
                        await websocket.send_json({"type": "log", "data": update["log"][-1]})

            if interrupt_payload is not None:
                await websocket.send_json({"type": "interrupt", "data": interrupt_payload})
                reply = await websocket.receive_json()
                if reply.get("type") != "resume":
                    await websocket.send_json(
                        {"type": "error", "data": {"message": f"Expected a 'resume' message, got {reply.get('type')!r}"}}
                    )
                    await websocket.close()
                    return
                stream_input = Command(
                    resume={
                        "winner_plant": reply.get("winner_plant"),
                        "decided_by": reply.get("decided_by", "Kavita Iyer's team"),
                        "note": reply.get("note", ""),
                    }
                )
                continue

            # No interrupt this pass — the graph either just finished
            # (checked below) or, structurally, has nothing else that would
            # pause it mid-stream.
            snapshot = _graph.get_state(config)
            if not snapshot.next:  # reached END
                final_log = snapshot.values.get("log", [])
                if final_log:
                    _last_completed_entry[claim["sku"]] = final_log[-1]
                await websocket.send_json({"type": "done", "data": {"log": final_log}})
            break

    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass  # already closed


# ---------------------------------------------------------------------------
# REST: registry snapshot — "what's currently held, by whom", live
# ---------------------------------------------------------------------------


@app.get("/api/registry")
def get_registry() -> dict[str, Any]:
    return {
        "holds": _registry.snapshot(),
        "audit_log": _registry.audit_log,
    }


# ---------------------------------------------------------------------------
# REST: chat — answers questions using the shared registry's current state
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str
    sku: Optional[str] = None


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
        f"Supplier in this demo: {SUPPLIER}. Primary SKU: {BOLT_SKU}.",
        f"Current registry holds: {json.dumps(_registry.snapshot(), indent=2)}",
        f"Audit log entries so far: {len(_registry.audit_log)}",
    ]
    if req.sku and req.sku in _last_completed_entry:
        context_parts.append(
            f"Most recent completed audit entry for {req.sku}:\n"
            f"{json.dumps(_last_completed_entry[req.sku], indent=2)}"
        )

    system_prompt = (
        "You are an allocation-arbitration assistant for a supplier-lot coordination demo. "
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
