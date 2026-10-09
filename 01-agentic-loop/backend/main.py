"""
FastAPI wrapper around agentic_graph.py — exposes the same LangGraph
Observe -> Decide -> (human_review interrupt) -> Act -> Log loop used by
demo.py, over HTTP + a WebSocket, so a browser can drive it instead of a
terminal auto-approving every interrupt.

No business logic lives here. This file only does three things:
  1. Serves the 8 harness products (from data/harness_products_100.json)
     and their images, for a product grid.
  2. Creates a "run" (one graph thread) for a chosen product.
  3. Streams that run's observe/decide/act/interrupt events over a
     WebSocket, and accepts the human's approve/decline decision back
     over the same socket, exactly the way demo.py drives the graph from
     a terminal loop — just over the wire instead of auto-approved.

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

from agentic_graph import build_graph, make_initial_state
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

BASE_DIR = Path(__file__).resolve().parent  # .../01-agentic-loop/backend


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

app = FastAPI(title="Agentic Loop API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGES_DIR = BASE_DIR / "images"
if IMAGES_DIR.exists():
    app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

PRODUCTS_PATH = BASE_DIR / "data" / "harness_products_100.json"
_products_raw: list[dict[str, Any]] = json.loads(PRODUCTS_PATH.read_text())["products"]
_products_by_sku: dict[str, dict[str, Any]] = {p["sku"]: p for p in _products_raw}

_checkpointer = InMemorySaver()
_graph = build_graph().compile(checkpointer=_checkpointer)

# thread_id -> sku, so the WS handler knows which product's data a run uses.
_run_sku: dict[str, str] = {}

# sku -> most recently completed run's log, used as chat context. Kept
# in memory only — this is a demo app, not a system of record.
_last_completed_log: dict[str, list[dict[str, Any]]] = {}


# ---------------------------------------------------------------------------
# REST: products
# ---------------------------------------------------------------------------

class Product(BaseModel):
    sku: str
    name: str
    image: str
    opening_balance: int
    run_rate_per_minute: float
    event_count: int


@app.get("/api/products", response_model=list[Product])
def list_products() -> list[Product]:
    return [
        Product(
            sku=p["sku"],
            name=p["name"],
            image=f"/images/{p['sku'].lower()}.png",
            opening_balance=p["opening_balance"],
            run_rate_per_minute=p["run_rate_per_minute"],
            event_count=len(p["events"]),
        )
        for p in _products_raw
    ]


# ---------------------------------------------------------------------------
# REST: create a run
# ---------------------------------------------------------------------------

class CreateRunRequest(BaseModel):
    sku: str


class CreateRunResponse(BaseModel):
    thread_id: str


@app.post("/api/runs", response_model=CreateRunResponse)
def create_run(req: CreateRunRequest) -> CreateRunResponse:
    product = _products_by_sku.get(req.sku)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Unknown sku: {req.sku}")

    thread_id = str(uuid.uuid4())
    _run_sku[thread_id] = req.sku
    return CreateRunResponse(thread_id=thread_id)


# ---------------------------------------------------------------------------
# WebSocket: stream a run, accept resume decisions
# ---------------------------------------------------------------------------
#
# Message shapes (server -> client), one JSON object per message:
#   {"type": "observe",   "data": {"minutes_after_start", "balance", "last_transaction"}}
#   {"type": "decide",    "data": {"action", "rationale", "risk"}}
#   {"type": "interrupt", "data": {"action", "rationale", "risk"}}   # waiting for the client now
#   {"type": "act",       "data": {"outcome"}}
#   {"type": "done",      "data": {"log": [...]}}                   # graph reached END, socket closes
#   {"type": "error",     "data": {"message"}}
#
# Message shape (client -> server), sent only in reply to an "interrupt":
#   {"type": "resume", "approved": true, "approved_by": "Aditi Kulkarni"}

@app.websocket("/api/runs/{thread_id}/stream")
async def stream_run(websocket: WebSocket, thread_id: str) -> None:
    await websocket.accept()

    sku = _run_sku.get(thread_id)
    if sku is None:
        await websocket.send_json({"type": "error", "data": {"message": f"Unknown thread_id: {thread_id}"}})
        await websocket.close()
        return

    product = _products_by_sku[sku]
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = make_initial_state(
        sku=product["sku"],
        opening_balance=product["opening_balance"],
        run_rate_per_minute=product["run_rate_per_minute"],
        pending_events=product["events"],
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
                    if node_name == "observe" and node_update.get("observation"):
                        await websocket.send_json({"type": "observe", "data": node_update["observation"]})
                    elif node_name == "decide":
                        await websocket.send_json({"type": "decide", "data": node_update["decision"]})
                    elif node_name == "act":
                        await websocket.send_json({"type": "act", "data": {"outcome": node_update["log"][-1]["outcome"]}})

            if interrupt_payload is not None:
                await websocket.send_json({"type": "interrupt", "data": interrupt_payload})
                reply = await websocket.receive_json()
                if reply.get("type") != "resume":
                    await websocket.send_json(
                        {"type": "error", "data": {"message": f"Expected a 'resume' message, got {reply.get('type')!r}"}}
                    )
                    await websocket.close()
                    return
                stream_input = Command(resume={"approved": bool(reply.get("approved")), "approved_by": reply.get("approved_by")})
                continue

            # No interrupt this pass — the graph either just finished (checked
            # below) or, structurally, has nothing else that would pause it
            # mid-stream, so there's nothing else to loop on here.
            snapshot = _graph.get_state(config)
            if not snapshot.next:  # reached END
                log = snapshot.values.get("log", [])
                _last_completed_log[sku] = log
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

    context_parts = [f"Known products: {', '.join(p['sku'] + ' (' + p['name'] + ')' for p in _products_raw)}."]
    if req.sku and req.sku in _last_completed_log:
        log = _last_completed_log[req.sku]
        context_parts.append(f"Most recent run log for {req.sku}:\n{json.dumps(log, indent=2)}")
    elif req.sku:
        context_parts.append(f"No completed run yet for {req.sku} — only its static catalog data is known.")

    system_prompt = (
        "You are an inventory assistant for a wiring-harness supply demo. "
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
