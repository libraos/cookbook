// Every kernel call the app makes, in one place. All of them run as the
// signed-in user, so the kernel scopes each answer to that user: their
// conversations, their documents, their memory.
import { authFetch } from "./auth";

// The agent from ../libraos-app: app "personal-assistant", agent "assistant".
const APP = "personal-assistant";
export const AGENT = "assistant";

export type Message = { role: "user" | "assistant"; content: string };
export type Conversation = { id: string; title: string | null; last_active_at: string; message_count: number };
export type Me = { sub: string; email: string; name: string };
export type Doc = { name: string };

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.url.replace(location.origin, "")}: HTTP ${res.status}`);
  return res.json();
}

export const getMe = async () => json<Me>(await authFetch("/oauth/userinfo"));

// ── Chat ────────────────────────────────────────────────────────────────────
// The kernel does not replay history: send the whole conversation each turn,
// plus its conversation_id so the turn is saved to the same thread.
//
// With "stream": true the reply comes back as server-sent events, one JSON
// object per `data:` line, told apart by `type`:
//   {"type":"text","content":"…"}      a piece of the reply, in order
//   {"type":"content","content":"…"}   the whole reply once more, at the end
//   {"type":"error","error":"…"}       the turn failed (a `done` still follows)
//   {"type":"done","conversation_id":"…","cited_sources":[…], …}
// Streamed turns are saved and remembered like any other (kernel v0.1.21+).
export async function chat(
  messages: Message[],
  conversationId: string | null,
  onText: (textSoFar: string) => void,
): Promise<{ text: string; conversationId: string; sources: string[] }> {
  const res = await authFetch(`/v1/apps/${APP}/agents/${AGENT}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messages, conversation_id: conversationId ?? undefined, stream: true }),
  });
  if (!res.ok || !res.body) await json(res); // throws with the status

  let text = "";
  let done: { conversation_id: string; cited_sources?: string[] } | null = null;
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done: ended } = await reader.read();
    if (ended) break;
    buffer += value;
    // Events are separated by a blank line; keep any partial one for later.
    const events = buffer.split("\n\n");
    buffer = events.pop()!;
    for (const event of events) {
      const data = event.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("");
      if (!data) continue;
      const frame = JSON.parse(data);
      if (frame.type === "text") onText((text += frame.content));
      else if (frame.type === "content") onText((text = frame.content)); // authoritative full text
      else if (frame.type === "error") throw new Error(`chat: ${frame.error}`);
      else if (frame.type === "done") done = frame;
    }
  }
  if (!done) throw new Error("chat: the stream ended before the reply was complete");
  return { text, conversationId: done.conversation_id, sources: done.cited_sources ?? [] };
}

// ── Conversations ───────────────────────────────────────────────────────────
export const listConversations = async () =>
  (await json<{ conversations: Conversation[] }>(await authFetch(`/v1/conversations?agent=${AGENT}&limit=50`))).conversations;

export const getConversation = async (id: string) =>
  json<Conversation & { messages: Message[] }>(await authFetch(`/v1/conversations/${id}`));

// The kernel can finish a reply a moment before it has saved a NEW
// conversation, so a rename sent straight away may 404. Retry briefly.
export async function renameConversation(id: string, title: string): Promise<void> {
  for (let attempt = 0; ; attempt++) {
    const res = await authFetch(`/v1/conversations/${id}`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (res.status !== 404 || attempt === 4) return void (await json(res));
    await new Promise((r) => setTimeout(r, 250));
  }
}

export const deleteConversation = async (id: string) => {
  const res = await authFetch(`/v1/conversations/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`delete: HTTP ${res.status}`);
};

// ── My documents ────────────────────────────────────────────────────────────
// A normal user's files live in their own private area, and the kernel
// indexes them into a collection only they (and admins) can search. The
// agent's `knowledge_bindings: ["*"]` means "search what the caller may read".
const FOLDER = "my-documents";

export const listDocuments = async () =>
  (await json<{ files: Doc[] }>(await authFetch(`/api/documents/tree/${FOLDER}`))).files;

export async function uploadDocument(file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  await json(await authFetch(`/api/documents/upload/${FOLDER}`, { method: "POST", body: form }));
}

// Use /rm/, not DELETE /api/documents/file/: both remove the file, but only
// /rm/ also removes its indexed text, so the assistant stops answering from it.
export async function deleteDocument(name: string): Promise<void> {
  await json(await authFetch(`/api/documents/rm/${FOLDER}/${encodeURIComponent(name)}`, { method: "DELETE" }));
}

// ── Memory ──────────────────────────────────────────────────────────────────
// What the kernel has condensed about this user for this agent. Recent turns
// are used right away; condensing into this summary happens in batches.
export const getMemory = async () =>
  (await json<{ content: string }>(await authFetch(`/v1/managed/memory?agent_id=${AGENT}`))).content;
