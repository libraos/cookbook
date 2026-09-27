#!/usr/bin/env bash
# Create a normal user for the digital-marketing-team demo. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"
ENV_FILE="${ENV_FILE:-../../../get-started/.env}"
set -a; . "$ENV_FILE"; set +a
URL="${LIBRA_OS_URL:-http://localhost:${LIBRAOS_PORT:-8900}}"
SECRET="${LIBRA_OS_SERVICE_CLIENTS#*=}"
EMAIL="${DM_DEMO_EMAIL:-marketing@example.com}"
PASSWORD="${DM_DEMO_PASSWORD:?set DM_DEMO_PASSWORD (12+ characters)}"
json() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)"; }

TOKEN=$(curl -sS -X POST "$URL/oauth/token" -H 'content-type: application/json' \
  -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"quickstart\",\"client_secret\":\"$SECRET\"}" \
  | json '["access_token"]')

INVITE=$(curl -sS -X POST "$URL/api/admin/users/invite" -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"role\":\"employee\",\"display_name\":\"Demo CEO\"}")
if echo "$INVITE" | grep -q account_exists; then
  echo "user: $EMAIL already exists (password unchanged)"
else
  ACCEPT_PATH=$(echo "$INVITE" | python3 -c 'import sys,json,urllib.parse as u; d=json.load(sys.stdin); "invite_url" in d or sys.exit("invite failed: %s" % d); print(u.urlparse(d["invite_url"]).path)')
  CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$URL$ACCEPT_PATH" \
    --data-urlencode "password=$PASSWORD" --data-urlencode "confirm_password=$PASSWORD")
  [ "$CODE" = 303 ] || { echo "accept invite failed: HTTP $CODE"; exit 1; }
  echo "user: created $EMAIL"
fi
echo "Next: cd ../web && npm install && npm run dev, then open http://localhost:5181"
