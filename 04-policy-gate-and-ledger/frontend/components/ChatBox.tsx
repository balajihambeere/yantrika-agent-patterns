"use client";

import { useState } from "react";
import { askChat } from "@/lib/api";

type ChatMessage = {
  id: number;
  role: "user" | "assistant" | "error";
  text: string;
};

export default function ChatBox({ decisionId, agentId }: { decisionId?: string; agentId?: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [nextId, setNextId] = useState(0);

  async function handleSend() {
    const q = question.trim();
    if (!q || sending) return;

    const userId = nextId;
    setMessages((prev) => [...prev, { id: userId, role: "user", text: q }]);
    setQuestion("");
    setSending(true);
    setNextId((n) => n + 2);

    try {
      const { answer } = await askChat(q, { decisionId, agentId });
      setMessages((prev) => [...prev, { id: userId + 1, role: "assistant", text: answer }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: userId + 1, role: "error", text: "Couldn't reach the chat endpoint. Is the backend running?" },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="rounded-lg border border-border bg-panel p-4 space-y-3">
      <h2 className="font-semibold text-base text-soft uppercase tracking-wide">Ask about the policy gate</h2>

      <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
        {messages.length === 0 && (
          <p className="text-base text-soft font-mono">
            Ask about agent tiers{decisionId ? `, this run's decision (${decisionId})` : ""}, or the ledger.
          </p>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`text-base rounded-md px-3 py-2 ${
              m.role === "user"
                ? "bg-bg text-ink ml-auto max-w-[85%]"
                : m.role === "error"
                  ? "bg-danger/10 text-danger max-w-[85%]"
                  : "bg-accent/10 text-ink max-w-[85%]"
            }`}
          >
            {m.text}
          </div>
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void handleSend();
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Why was this proposal rejected?"
          disabled={sending}
          className="flex-1 rounded-md border border-border bg-bg px-3 py-2 text-base text-ink focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={sending || !question.trim()}
          className="rounded-md bg-accent px-4 py-2 text-base font-medium text-on-accent hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {sending ? "…" : "Send"}
        </button>
      </form>
    </section>
  );
}
