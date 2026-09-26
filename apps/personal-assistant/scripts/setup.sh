#!/usr/bin/env bash
# Install the personal-assistant app on your local kernel and create a normal
# (non-admin) demo user to sign in with. Safe to re-run.
#
# Uses the kernel from get-started/: run `docker compose up -d` there first.
set -euo pipefail
cd "$(dirname "$0")"
ENV_FILE="${ENV_FILE:-../../../get-started/.env}"
set -a; . "$ENV_FILE"; set +a
URL="${LIBRA_OS_URL:-http://localhost:${LIBRAOS_PORT:-8900}}"
SECRET="${LIBRA_OS_SERVICE_CLIENTS#*=}"   # quickstart:admin=<secret>
EMAIL="${PA_DEMO_EMAIL:-demo@example.com}"
PASSWORD="${PA_DEMO_PASSWORD:?set PA_DEMO_PASSWORD (12+ characters) in $ENV_FILE}"
json() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)"; }

# 1. An admin token from the laptop-only quickstart client (see get-started/).
TOKEN=$(curl -sS -X POST "$URL/oauth/token" -H 'content-type: application/json' \
  -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"quickstart\",\"client_secret\":\"$SECRET\"}" \
  | json '["access_token"]')

# 2. Register the app folder the compose file mounts into the kernel. The
#    kernel also scans it at boot; installing again just reloads the agents.
curl -sS -X POST "$URL/v1/apps/personal-assistant/install" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); d.get("status")=="active" or sys.exit("install failed: %s" % d); print("app: personal-assistant %s, %d agent(s)" % (d["version"], d["agents_registered"]))'

# 3. The demo user. Admins invite; the invitee sets their own password on the
#    accept page. We play both parts. An existing account is left untouched.
INVITE=$(curl -sS -X POST "$URL/api/admin/users/invite" -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"role\":\"employee\",\"display_name\":\"Demo User\"}")
if echo "$INVITE" | grep -q account_exists; then
  echo "user: $EMAIL already exists (password unchanged)"
else
  # invite_url names LIBRA_OS_PUBLIC_URL; keep only its path so this works
  # whatever host the kernel is published on.
  ACCEPT_PATH=$(echo "$INVITE" | python3 -c 'import sys,json,urllib.parse as u; d=json.load(sys.stdin); "invite_url" in d or sys.exit("invite failed: %s" % d); print(u.urlparse(d["invite_url"]).path)')
  CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$URL$ACCEPT_PATH" \
    --data-urlencode "password=$PASSWORD" --data-urlencode "confirm_password=$PASSWORD")
  [ "$CODE" = 303 ] || { echo "accept invite failed: HTTP $CODE (password must be 12+ characters)"; exit 1; }
  echo "user: created $EMAIL"
fi
echo "Next: cd ../web && npm install && npm run dev, then open http://localhost:5180"
