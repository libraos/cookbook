#!/usr/bin/env bash
# Create an agent on your local LibraOS kernel and talk to it.
# Run from this folder after `docker compose up -d` in ../ (see ../README.md).
#   ./first-agent.sh                       # asks a default question
#   ./first-agent.sh 'Say "hi" in French'  # or your own
set -euo pipefail
cd "$(dirname "$0")"
# get-started/.env, when the kernel runs from get-started/ (optional if
# LIBRA_OS_API_KEY is set).
if [ -f ../.env ]; then set -a; . ../.env; set +a; fi
URL="${LIBRA_OS_URL:-http://localhost:${LIBRAOS_PORT:-8900}}"

# 1. A bearer token: LIBRA_OS_API_KEY if set, otherwise exchange the
#    quickstart client's secret from get-started/.env.
if [ -n "${LIBRA_OS_API_KEY:-}" ]; then
  TOKEN="$LIBRA_OS_API_KEY"
else
  if [ -z "${LIBRA_OS_SERVICE_CLIENTS:-}" ]; then
    echo "No LibraOS credentials. Either set LIBRA_OS_API_KEY to a token that can create agents (in VS Code: LibraOS > Copy Setup Token, or turn on Examples' Run and Debug), or create get-started/.env from .env.example and start the kernel there (see get-started/README.md)." >&2
    exit 1
  fi
  SECRET="${LIBRA_OS_SERVICE_CLIENTS#*=}"   # quickstart:admin=<secret>
  TOKEN=$(curl -sS -X POST "$URL/oauth/token" \
    -H 'content-type: application/json' \
    -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"quickstart\",\"client_secret\":\"$SECRET\"}" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["access_token"]) if "access_token" in d else sys.exit("token failed: %s" % d)')
fi

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
