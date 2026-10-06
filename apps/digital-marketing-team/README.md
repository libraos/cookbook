# Digital Marketing Team

Give LibraOS one marketing mission and watch a Head of Marketing assemble and
run the department needed to finish it.

> Most AI gives you an answer. This gives you a team.

This cookbook is a thin reference client for LibraOS's native mission runtime.
It does not choose agents, create tasks, advance progress, or assemble the
report in the browser. It makes one job request:

```http
POST /agents/v1/head-of-marketing/jobs
```

LibraOS then plans a mission-specific team and task DAG, runs ready tasks in
parallel, passes structured outputs between employees, pauses dependent work
when a genuine executive decision is required, and returns one attributed
report. The UI is driven entirely by durable runtime events.

## What the demo proves

- One CEO instruction becomes organizational work rather than one long reply.
- The Head of Marketing decides which specialists and tasks the mission needs.
- Independent work runs concurrently, with explicit dependencies and handoffs.
- Every downstream employee consumes structured outputs rather than raw chat.
- Human authority is reserved for a real decision or external action.
- The final report derives sources, contributors, and totals from runtime data.
- Native LibraOS tools provide knowledge and research. No GBrain or MCP server
  is required; an MCP tool can be made available later when a mission needs it.

## Architecture

```text
CEO chat box
    │ one POST
    ▼
Head of Marketing employee
    │
    ├─ mission planner ──► dynamic employees + validated task DAG
    │
    ├─ durable scheduler ─► ready tasks, concurrency 3, checkpoints
    │                         │
    │                         └─ structured output handoffs
    │
    ├─ approval gate ◄──── CEO decision, when required
    │
    └─ lead synthesis ───► attributed, source-backed report
```

The runtime implementation lives in LibraOS core under
`internal/workflow/mission.go`. PostgreSQL stores the job event log and workflow
checkpoints, which lets the browser reconnect and the kernel resume an orphaned
mission without replaying completed work.

## Run it

The kernel must include the autonomous mission workflow and run with PostgreSQL:

```dotenv
LIBRA_OS_WORKFLOWS_ENABLED=true
LIBRA_OS_OIDC_CLIENTS=digital-marketing-team=http://localhost:5181/callback
```

Use a model endpoint that supports structured JSON and tool calls for the
kernel's skill tier. The implementation and validation for this cookbook were
completed with Sol, as required by the project decision.

Create a normal demo user using the same `.env` as `get-started/`:

```bash
DM_DEMO_PASSWORD='choose-a-12-character-password' \
  apps/digital-marketing-team/scripts/setup.sh
```

The setup script also ingests [`packs/marketing-team/knowledge/libraos-product-brief.md`](../../packs/marketing-team/knowledge/libraos-product-brief.md) into the
native LibraOS `default` knowledge collection. Research employees cite that
runtime source directly; no GBrain or mandatory MCP dependency is involved.

Then run the browser app:

```bash
cd apps/digital-marketing-team/web
npm install
npm run dev
```

Open <http://localhost:5181> and submit the prefilled mission. The request is
sent once. After submission the only write the UI can make is resolving a
decision emitted by that same mission.

## Runtime event contract

The execution screen is reduced from these persisted events:

```text
mission.created
mission.planned
agent.created
task.created
task.started
task.completed | task.failed
handoff.created
approval.required | approval.resolved
report.synthesis_started
report.completed
mission.completed
```

Animations occur only when one of those state transitions arrives. Reopening
the stream replays the stored event log before following live work.

## Files

```text
digital-marketing-team/
├── README.md
├── scripts/setup.sh
└── web/
    ├── src/api.ts       one mission call, replayable stream, decision call
    ├── src/App.tsx      mission, department, approval, and report views
    └── src/styles.css   calm responsive presentation
```

The team itself (mission contract, example mission and knowledge) lives in the
[`marketing-team` pack](../../packs/marketing-team/): see
[`missions/autonomous-marketing-department.yaml`](../../packs/marketing-team/missions/autonomous-marketing-department.yaml)
and its [example input](../../packs/marketing-team/missions/autonomous-marketing-department.example.yaml).
The mission YAML documents the contract. It is not a second scheduler;
LibraOS core remains the source of execution truth.

## Product boundary

This directory is the public cookbook and reference UI. It intentionally does
not contain the internal epic, proprietary routing policy, production policy
engine, enterprise permissions, or control-plane code. Apache-2.0 applies under
the repository license.
