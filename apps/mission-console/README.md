# Mission console

A browser app that runs any team mission from the cookbook's [packs](../../packs/). Pick a mission, describe the outcome, and follow the work:
- the team and task plan;
- live progress and an activity stream;
- decisions reserved for you;
- the final report, which you can read and download.

The console is the [digital marketing team](../digital-marketing-team/) app generalized. Mission-specific text (lead name, headline, example) comes from [`src/catalog.ts`](src/catalog.ts). All kernel calls go through the shared [mission client](../../shared/mission-client/).

**Today the catalog has one entry, the [`marketing-team`](../../packs/marketing-team/) pack's mission.** It runs on the kernel's built-in `head-of-marketing` lead. When [libraos/libraos#1660](https://github.com/libraos/libraos/issues/1660) lets packs declare mission templates, other teams join the catalog.

## Run it

The kernel needs the mission workflow, PostgreSQL, and an OIDC client for the console:

```dotenv
LIBRA_OS_WORKFLOWS_ENABLED=true
LIBRA_OS_OIDC_CLIENTS=mission-console=http://localhost:5182/callback
```

Create a demo user and seed the marketing knowledge with the marketing app's setup script. It uses the same kernel and `.env` as [`get-started/`](../../get-started/):

```bash
DM_DEMO_PASSWORD='choose-a-12-character-password' \
  apps/digital-marketing-team/scripts/setup.sh
```

Then start the console:

```bash
cd apps/mission-console
npm install
npm run dev        # http://localhost:5182, proxies /oauth, /agents and /api to LIBRAOS_URL (default http://localhost:8900)
```

To reuse an existing OIDC client, set `VITE_LIBRAOS_CLIENT_ID`. Its redirect URI must point to this app's `/callback`.

A mission in progress survives reloads: the URL carries `?mission=…&job=…`, and the console replays the job's stored events before following live work.

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
