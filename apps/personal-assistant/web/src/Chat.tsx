import { useEffect, useRef, useState } from "react";
import { chat, getConversation, renameConversation, type Message } from "./api";

type Props = {
  conversationId: string | null; // null = a new conversation
  onSaved: (id: string) => void;
  onError: (e: unknown) => void;
};

export function Chat({ conversationId, onSaved, onError }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [id, setId] = useState(conversationId);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [sources, setSources] = useState<string[]>([]);
  const bottom = useRef<HTMLDivElement>(null);

  // Resuming: the kernel stored every turn, so load them and carry on.
  useEffect(() => {
    if (!conversationId) return;
    getConversation(conversationId)
      .then((c) => setMessages(c.messages.map(({ role, content }) => ({ role, content }))))
      .catch(onError);
  }, [conversationId, onError]);

  useEffect(() => bottom.current?.scrollIntoView({ block: "end" }), [messages, busy]);

  async function send() {
    const text = draft.trim();
    if (!text || busy) return;
    const history: Message[] = [...messages, { role: "user", content: text }];
    setMessages(history);
    setDraft("");
    setSources([]);
    setBusy(true);
    try {
      const reply = await chat(history, id);
      setMessages([...history, { role: "assistant", content: reply.text }]);
      setSources(reply.sources);
      if (!id) {
        // The kernel leaves new conversations untitled; name it after the
        // first question so the list is readable.
        await renameConversation(reply.conversationId, text.length > 60 ? text.slice(0, 57) + "…" : text);
        setId(reply.conversationId);
      }
      onSaved(reply.conversationId);
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="chat" aria-busy={busy}>
      <div className="messages">
        {messages.length === 0 && !busy && (
          <div className="empty">
            <h2>How can I help?</h2>
            <p className="muted">Ask anything. Upload documents on the right and I'll answer from them.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>{m.content}</div>
        ))}
        {busy && <div className="msg assistant muted">Thinking…</div>}
        {sources.length > 0 && (
          <div className="sources muted">From: {sources.map((s) => s.split("/").pop()).join(", ")}</div>
        )}
        <div ref={bottom} />
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea
          value={draft}
          placeholder="Message your assistant"
          rows={2}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
        />
        <button className="primary" disabled={!draft.trim() || busy}>Send</button>
      </form>
    </main>
  );
}
