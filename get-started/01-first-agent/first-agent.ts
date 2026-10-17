// Create an agent on your local LibraOS kernel and hold a short conversation.
// Node 20+, no dependencies:  npx tsx first-agent.ts
import { existsSync, readFileSync } from "node:fs";

// get-started/.env, when the kernel runs from get-started/ (optional if
// LIBRA_OS_API_KEY is set).
const envFile = new URL("../.env", import.meta.url);
const env: Record<string, string> = existsSync(envFile)
  ? Object.fromEntries(
      readFileSync(envFile, "utf8")
        .split("\n")
        .filter((l) => /^[A-Z_]+=/.test(l))
        .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
    )
  : {};
const URL_ = process.env.LIBRA_OS_URL ?? `http://localhost:${process.env.LIBRAOS_PORT ?? env.LIBRAOS_PORT ?? 8900}`;
const NO_CREDENTIALS =
  "No LibraOS credentials. Either set LIBRA_OS_API_KEY to a token that can create agents " +
  "(in VS Code: LibraOS > Copy Setup Token, or turn on Examples' Run and Debug), " +
  "or create get-started/.env from .env.example and start the kernel there (see get-started/README.md).";

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

// 1. A bearer token: LIBRA_OS_API_KEY if set, otherwise one for the
//    laptop-only quickstart client in get-started/.env.
let token: string;
if (process.env.LIBRA_OS_API_KEY) {
  token = process.env.LIBRA_OS_API_KEY;
} else {
  if (!env.LIBRA_OS_SERVICE_CLIENTS) {
    console.error(NO_CREDENTIALS);
    process.exit(1);
  }
  const secret = env.LIBRA_OS_SERVICE_CLIENTS.split("=").slice(1).join("=");
  const tok = await call("/oauth/token", { grant_type: "client_credentials", client_id: "quickstart", client_secret: secret });
  if (tok.status !== 200) throw new Error(`token: ${tok.status} ${JSON.stringify(tok.body)}`);
  token = tok.body.access_token;
}

// 2. A persona agent. Re-running the script is safe. tool_scope "none": it
//    only talks, so the kernel offers it no tools (and logs no warning).
const agent = await call("/v1/agents", {
  name: "first-assistant",
  agent_type: "persona",
  tool_scope: "none",
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
