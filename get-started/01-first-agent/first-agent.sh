#!/usr/bin/env bash
# Create an agent on your local LibraOS kernel and talk to it.
# Run from this folder after `docker compose up -d` in ../ (see ../README.md).
#   ./first-agent.sh                       # asks a default question
#   ./first-agent.sh 'Say "hi" in French'  # or your own
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ../.env; set +a
URL="${LIBRA_OS_URL:-http://localhost:${LIBRAOS_PORT:-8900}}"
SECRET="${LIBRA_OS_SERVICE_CLIENTS#*=}"   # quickstart:admin=<secret>

# 1. Exchange the quickstart client's secret for a bearer token.
TOKEN=$(curl -sS -X POST "$URL/oauth/token" \
  -H 'content-type: application/json' \
  -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"quickstart\",\"client_secret\":\"$SECRET\"}" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["access_token"]) if "access_token" in d else sys.exit("token failed: %s" % d)')

# 2. Create a persona agent. Re-running the script is safe. tool_scope "none":
#    it only talks, so the kernel offers it no tools (and logs no warning).
curl -sS -o /dev/null -w "create agent: HTTP %{http_code}\n" "$URL/v1/agents" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'anthropic-beta: managed-agents-2026-04-01' \
  -H 'content-type: application/json' \
  -d '{"name":"first-assistant","agent_type":"persona","tool_scope":"none","system":"You are a friendly assistant. Answer in two sentences or fewer."}'

# 3. Ask it something. The message is JSON-encoded, so quotes and newlines in
#    it are safe.
BODY=$(python3 -c 'import sys,json; print(json.dumps({"message": sys.argv[1]}))' "${1:-What can you help me with?}")
curl -sS "$URL/agents/v1/first-assistant/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d "$BODY" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); "response" in d or sys.exit("chat failed: %s" % d); print("\n" + d["response"] + "\n\n(model: " + d.get("model","?") + ", conversation: " + d["conversation_id"] + ")")'
