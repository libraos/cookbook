# Mission console

A browser app that runs any team mission from the cookbook's [packs](../../packs/). Pick a mission, describe the outcome, and follow the work:
- the team and task plan;
- live progress and an activity stream;
- decisions reserved for you;
- the final report, which you can read and download.

The console is the [digital marketing team](../digital-marketing-team/) app generalized. Mission-specific text (lead name, headline, example) comes from [`src/catalog.ts`](src/catalog.ts). All kernel calls go through the shared [mission client](../../shared/mission-client/).

**Today the catalog has one entry, the [`marketing-team`](../../packs/marketing-team/) pack's mission.** It runs on the kernel's built-in `head-of-marketing` lead. When [libraos/libraos#1660](https://github.com/libraos/libraos/issues/1660) lets packs declare mission templates, other teams join the catalog.

## Run it

The console runs against the kernel from [`get-started/`](../../get-started/), which already enables the mission workflow (`LIBRA_OS_WORKFLOWS_ENABLED=true`) and PostgreSQL. Register the console as an OIDC client by appending it to the `LIBRA_OS_OIDC_CLIENTS` list in `get-started/.env`, then restart the kernel from `get-started/` (`docker compose up -d --force-recreate libraos`):

```dotenv
LIBRA_OS_OIDC_CLIENTS=signin-example=http://localhost:5173/callback,…,mission-console=http://localhost:5182/callback
```

Create a demo user and seed the marketing knowledge with the marketing app's setup script. It reads the same `.env`:

```bash
DM_DEMO_PASSWORD='choose-a-12-character-password' \
  apps/digital-marketing-team/scripts/setup.sh
```

Then start the console (Node 22.12 or newer):

```bash
cd apps/mission-console
npm install
npm run dev        # http://localhost:5182, proxies /oauth, /agents and /api to LIBRA_OS_URL (default http://localhost:8900)
```

If the kernel listens elsewhere (a different `LIBRAOS_PORT`, or another machine), point the proxy at it: `LIBRA_OS_URL=http://localhost:9000 npm run dev`, or put `LIBRA_OS_URL=…` in `apps/mission-console/.env`.

Sign in as the demo user, start the prefilled mission, and answer the decision the Head of Marketing brings back. To reuse an existing OIDC client, set `VITE_LIBRA_OS_CLIENT_ID`. Its redirect URI must point to this app's `/callback`.

A mission in progress survives reloads: the URL carries `?mission=…&job=…`, and the console replays the job's stored events before following live work. A dropped stream resumes from the last event. If the kernel ends the job without a report (for example the model returned an invalid plan), the console shows the kernel's error and offers a new mission.

The model matters: mission planning asks the brain model for a strict JSON task graph, and the task runs use the skill model's tool calls. A small or quantized model may return a plan the kernel rejects (`mission planning returned an invalid plan: …`); the console reports that as a failed mission, so retry or use a stronger model.

## Add a mission

1. Describe the team in `packs/<pack>/pack.yaml` and the mission contract in `packs/<pack>/missions/`.
2. Add a `catalog.ts` entry with the lead agent that owns the mission on the kernel.

## Files

```text
mission-console/
├── src/catalog.ts   the missions this console can run
├── src/App.tsx      picker, conversation, team, approvals, report
├── src/auth.ts      Sign in with LibraOS (OIDC + PKCE)
└── src/Markdown.tsx report rendering
```
