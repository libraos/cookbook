# Mission client

A dependency-free TypeScript client for the LibraOS mission runtime. Use it from a browser app or a server to:
1. submit a mission to a team lead;
2. follow the job's durable event stream, reconnecting with `Last-Event-ID`;
3. answer decision gates;
4. fold events into one `MissionState`: plan, task statuses, task outputs, the pending decision, and the final report.

[`apps/mission-console`](../../apps/mission-console/) uses it. Partner products can use it too, for example to import a team's report and per-task outputs into their own records.

```ts
import { createMissionClient, initialMissionState, reduceMission } from "../../shared/mission-client/src";

const client = createMissionClient({ lead: "head-of-marketing", fetch: authFetch });
const jobID = await client.create("Create a 14-day developer campaign … Do not publish anything.");

let state = initialMissionState();
const job = await client.stream(jobID, (event, sequence) => {
  state = reduceMission(state, event, sequence);
  if (state.decision) { /* show the decision; then */ }
});
// await client.resolveDecision(jobID, state.decision.id, optionID)
// job.status is done, failed or cancelled; state.report holds the deliverable
```

| Call | Kernel route |
| --- | --- |
| `create(message)` | `POST /agents/v1/{lead}/jobs` |
| `get(jobID)` | `GET /agents/v1/{lead}/jobs/{id}` |
| `stream(jobID, onEvent, signal?)` | `GET /agents/v1/{lead}/jobs/{id}/stream`; replays the stored log, then follows live work; resolves once the job ends |
| `resolveDecision(jobID, decisionID, choice, instruction?)` | `POST /agents/v1/{lead}/jobs/{id}/decisions/{decision_id}` |

**Authentication:** pass a `fetch` that adds the bearer token. The stream needs it too, which is why the client uses `fetch` rather than `EventSource`.

**Events:** the reducer reads `mission.created`, `mission.planned`, `task.*`, `approval.*`, `report.completed` and `response_complete`, and ignores others. Replayed sequences are ignored, so reconnecting never double-counts.

**Today the lead is the kernel's built-in `head-of-marketing`.** [libraos/libraos#1660](https://github.com/libraos/libraos/issues/1660) proposes mission templates in packs, so other teams' leads can run missions through the same routes.

## Test

```bash
node --test src/*.test.ts   # Node 22.6+ (type stripping)
```
