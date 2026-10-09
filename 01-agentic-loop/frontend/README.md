# Agentic Loop — Frontend

A Next.js (App Router, TypeScript, Tailwind CSS) UI for the agentic-loop demo:
a LangGraph-based agent that watches a wiring-harness product's stock level,
auto-handles low/medium-risk decisions, and genuinely pauses (via a real
`interrupt()`) when a decision is high-risk — waiting for a human to click
Approve or Decline before continuing.

## Prerequisites

The FastAPI backend (in `../backend`) must be running first, on port 8000:

```bash
cd ../backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Confirm it's up: `curl http://localhost:8000/api/health` → `{"status":"ok"}`.

## Setup

```bash
npm install
cp .env.local.example .env.local   # optional — defaults to http://localhost:8000 anyway
npm run dev
```

Open http://localhost:3000.

## Configuration

`NEXT_PUBLIC_API_URL` — base URL of the backend (REST + WebSocket + images).
Defaults to `http://localhost:8000` if unset. Set it in `.env.local`.

## What's here

- `app/page.tsx` — product grid, server-fetched from `GET /api/products`.
- `app/products/[sku]/page.tsx` — run view: product header + `<RunView>` +
  `<ChatBox>`.
- `components/RunView.tsx` — starts a run (`POST /api/runs`), opens the
  run's WebSocket, and renders the observe/decide/act timeline live as
  messages arrive. Renders a dedicated "Pending Human Approval" card when
  the server sends an `interrupt` message, and sends the `resume` reply
  on Approve/Decline.
- `components/Timeline.tsx`, `PendingApprovalCard.tsx`, `RiskBadge.tsx` —
  timeline row rendering and the approval card.
- `components/ChatBox.tsx` — small Q&A box against `POST /api/chat`.
- `lib/api.ts`, `lib/types.ts` — API client and the backend's message
  shapes, typed as a discriminated union.

## Build

```bash
npm run build
```

Builds clean with zero TypeScript/ESLint errors. Both `/` and
`/products/[sku]` are dynamically server-rendered on each request (not
statically generated) so they always reflect the live backend.
