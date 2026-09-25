// Create an agent on your local LibraOS kernel and hold a short conversation.
// Node 20+, no dependencies:  npx tsx first-agent.ts
import { readFileSync } from "node:fs";

const env = Object.fromEntries(
  readFileSync(new URL("../.env", import.meta.url), "utf8")
    .split("\n")
    .filter((l) => /^[A-Z_]+=/.test(l))
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const URL_ = process.env.LIBRA_OS_URL ?? `http://localhost:${env.LIBRAOS_PORT ?? 8900}`;
const secret = env.LIBRA_OS_SERVICE_CLIENTS.split("=").slice(1).join("=");

async function call(path: string, body: unknown, token?: string) {
  const res = await fetch(URL_ + path, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "anthropic-beta": "managed-agents-2026-04-01",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: await res.json().catch(() => ({})) };
}

// 1. A bearer token for the laptop-only quickstart client.
const tok = await call("/oauth/token", { grant_type: "client_credentials", client_id: "quickstart", client_secret: secret });
if (tok.status !== 200) throw new Error(`token: ${tok.status} ${JSON.stringify(tok.body)}`);
const token: string = tok.body.access_token;

// 2. A persona agent. Re-running the script is safe.
const agent = await call("/v1/agents", {
  name: "first-assistant",
  agent_type: "persona",
  system: "You are a friendly assistant. Answer in two sentences or fewer.",
}, token);
console.log(`create agent: HTTP ${agent.status}`);

// 3. Two turns. The chat route does not replay history for you: send the
//    whole conversation in `messages` every turn, with the same conversation_id.
const messages: { role: "user" | "assistant"; content: string }[] = [];
let conversationId: string | undefined;
for (const question of ["My name is Sam. What can you help me with?", "What's my name?"]) {
  messages.push({ role: "user", content: question });
  const r = await call("/agents/v1/first-assistant/chat", { messages, conversation_id: conversationId }, token);
  if (r.status !== 200) throw new Error(`chat: ${r.status} ${JSON.stringify(r.body)}`);
  conversationId = r.body.conversation_id;
  messages.push({ role: "assistant", content: r.body.response });
  console.log(`\nyou:   ${question}\nagent: ${r.body.response}`);
}
