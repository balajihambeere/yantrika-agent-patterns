"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import RunView from "@/components/RunView";
import ChatBox from "@/components/ChatBox";
import type { DoneData } from "@/lib/types";

export default function RunPage() {
  const params = useParams<{ threadId: string }>();
  const searchParams = useSearchParams();
  const flow = searchParams.get("flow") ?? "operational";
  const [decisionId, setDecisionId] = useState<string | undefined>(undefined);

  function handleDone(data: DoneData) {
    setDecisionId(typeof data.decision_id === "string" ? data.decision_id : undefined);
  }

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <div>
        <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Run</h1>
        <p className="font-mono text-base text-soft mt-1">thread {params.threadId}</p>
      </div>

      <RunView threadId={params.threadId} flow={flow} onDone={handleDone} />

      <ChatBox decisionId={decisionId} />
    </div>
  );
}
