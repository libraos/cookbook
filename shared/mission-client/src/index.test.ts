import assert from "node:assert/strict";
import test from "node:test";
import { createMissionClient, initialMissionState, parseFrames, reduceMission, type MissionEvent } from "./index.ts";

const frame = (id: number, event: MissionEvent) => `id: ${id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;

test("parseFrames keeps a partial frame for the next chunk and skips comments", () => {
  const whole = frame(1, { type: "mission.created" }) + ": keepalive\n\n" + frame(2, { type: "task.started" });
  const cut = whole.length - 5;
  const first = parseFrames(whole.slice(0, cut));
  assert.deepEqual(first.frames.map((f) => f.id), [1]);
  const second = parseFrames(first.rest + whole.slice(cut));
  assert.deepEqual(second.frames.map((f) => f.id), [2]);
  assert.equal(second.rest, "");
  assert.equal(parseFrames("id: 3\r\ndata: {}\r\n\r\n").frames[0].id, 3);
});

const plan = {
  title: "Launch", goal: "g", lead_agent_id: "lead", decisions: [],
  employees: [{ id: "a", name: "Ada", role: "Research", objective: "o" }],
  tasks: [
    { id: "t1", title: "Research", objective: "", owner_agent: "a", dependencies: [], expected_output: "", completion_criteria: [] },
    { id: "t2", title: "Write", objective: "", owner_agent: "a", dependencies: ["t1"], expected_output: "", completion_criteria: [] },
  ],
};

test("reduceMission follows plan, tasks, decisions and the report, and ignores replays", () => {
  const events: MissionEvent[] = [
    { type: "mission.created", content: "Run a launch" },
    { type: "mission.planned", metadata: { plan } },
    { type: "task.started", metadata: { task_id: "t1" } },
    { type: "task.completed", metadata: { task_id: "t1", output: { summary: "s", sources: ["k1"] } } },
    { type: "approval.required", metadata: { decision: { id: "d1", question: "Ok?", options: [], recommendation: "", reason: "", before_tasks: ["t2"] } } },
  ];
  let state = events.reduce((s, e, i) => reduceMission(s, e, i + 1), initialMissionState());
  assert.equal(state.objective, "Run a launch");
  assert.deepEqual(state.tasks, { t1: "completed", t2: "waiting_dependency" });
  assert.deepEqual(state.outputs.t1, { summary: "s", sources: ["k1"] });
  assert.equal(state.status, "waiting_approval");
  assert.equal(state.decision?.id, "d1");
  assert.equal(reduceMission(state, { type: "task.failed", metadata: { task_id: "t1" } }, 4), state, "replayed sequence is ignored");
  state = reduceMission(state, { type: "approval.resolved" }, 6);
  state = reduceMission(state, { type: "report.completed", metadata: { source_count: 3 } }, 7);
  state = reduceMission(state, { type: "response_complete", content: "# Report" }, 8);
  assert.equal(state.decision, null);
  assert.equal(state.sourceCount, 3);
  assert.equal(state.report, "# Report");
  assert.equal(state.status, "completed");
});

test("stream reconnects with Last-Event-ID and stops when the job is done", async () => {
  const requests: { path: string; init?: RequestInit }[] = [];
  const pages = [frame(1, { type: "mission.created" }) + frame(2, { type: "mission.planned" }), frame(2, { type: "mission.planned" }) + frame(3, { type: "response_complete" })];
  const statuses = ["running", "done"];
  const fake = async (path: string, init?: RequestInit) => {
    requests.push({ path, init });
    if (path.endsWith("/stream")) return new Response(pages.shift()!);
    return Response.json({ job_id: "job_1", status: statuses.shift() });
  };
  const client = createMissionClient({ lead: "head-of-marketing", fetch: fake, baseURL: "http://kernel" });
  const seen: number[] = [];
  const job = await client.stream("job_1", (_e, seq) => seen.push(seq));
  assert.equal(job.status, "done");
  assert.deepEqual(seen, [1, 2, 3], "the replayed event 2 is delivered once");
  const streams = requests.filter((r) => r.path.endsWith("/stream"));
  assert.equal(streams[0].path, "http://kernel/agents/v1/head-of-marketing/jobs/job_1/stream");
  assert.deepEqual(streams[1].init?.headers, { "Last-Event-ID": "2" });
});

test("errors carry the kernel's message and status", async () => {
  const client = createMissionClient({ lead: "lead", fetch: async () => Response.json({ message: "workflows disabled" }, { status: 404 }) });
  await assert.rejects(client.create("x"), { message: "workflows disabled", status: 404 });
});
