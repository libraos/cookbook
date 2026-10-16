// Mission client for the LibraOS mission runtime: submit a mission to a team
// lead, follow its durable event stream, resolve decision gates, and fold the
// events into one state object. It has no UI and no dependencies, so browser
// apps and servers (for example a partner app importing the final report) share
// the same contract. Pass `fetch` to add authentication.

export type Employee = { id: string; name: string; role: string; objective: string };
export type Task = {
  id: string; title: string; objective: string; owner_agent: string;
  dependencies: string[]; expected_output: string; completion_criteria: string[];
};
export type DecisionOption = { id: string; label: string; description: string };
export type Decision = {
  id: string; question: string; options: DecisionOption[];
  recommendation: string; reason: string; before_tasks: string[];
};
export type MissionPlan = {
  title: string; goal: string; lead_agent_id: string;
  employees: Employee[]; tasks: Task[]; decisions: Decision[];
};
export type MissionEvent = { type: string; content?: string; metadata?: Record<string, unknown> };
export type Job = { job_id: string; status: string; result?: string; error?: string };

export type Fetch = (path: string, init?: RequestInit) => Promise<Response>;
export type MissionClientOptions = {
  /** The team lead that owns the mission, e.g. `head-of-marketing`. */
  lead: string;
  /** Defaults to the global fetch; pass one that adds a bearer token. */
  fetch?: Fetch;
  /** Prefix for kernel paths, e.g. `http://localhost:8900`. Empty means same origin. */
  baseURL?: string;
  /**
   * Reconnect when the stream is silent this long. The kernel sends a heartbeat
   * every 10 seconds, so silence means a dead connection (for example a proxy
   * that kept the browser side open after the kernel restarted). Default 30s.
   */
  idleTimeoutMs?: number;
};

const terminal = ["done", "failed", "cancelled"];

export class MissionError extends Error {
  readonly status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

async function body<T>(response: Response): Promise<T> {
  const text = await response.text();
  let value: Record<string, unknown> = {};
  try { value = text ? JSON.parse(text) : {}; } catch { /* non-JSON error page */ }
  if (!response.ok) {
    throw new MissionError(String(value.message ?? value.error ?? `HTTP ${response.status}`), response.status);
  }
  return value as T;
}

/** Splits buffered SSE text into complete frames and the unfinished remainder. */
export function parseFrames(buffer: string): { frames: { id: number; data: string }[]; rest: string } {
  const parts = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = parts.pop() ?? "";
  const frames = [];
  for (const frame of parts) {
    if (!frame || frame.startsWith(":")) continue;
    const lines = frame.split("\n");
    const id = Number(lines.find((line) => line.startsWith("id:"))?.slice(3).trim() ?? 0);
    const data = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("");
    if (data) frames.push({ id, data });
  }
  return { frames, rest };
}

export function createMissionClient({ lead, fetch: send = fetch, baseURL = "", idleTimeoutMs = 30_000 }: MissionClientOptions) {
  const jobs = `${baseURL}/agents/v1/${encodeURIComponent(lead)}/jobs`;
  return {
    lead,

    /** Submits one mission and returns its job id. */
    async create(message: string): Promise<string> {
      const response = await send(jobs, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message }),
      });
      return (await body<{ job_id: string }>(response)).job_id;
    },

    async get(jobID: string): Promise<Job> {
      return body<Job>(await send(`${jobs}/${jobID}`));
    },

    /** Answers a decision gate with an option id, or with a free-text instruction. */
    async resolveDecision(jobID: string, decisionID: string, choice: string, instruction = ""): Promise<void> {
      await body(await send(`${jobs}/${jobID}/decisions/${decisionID}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ choice, instruction }),
      }));
    },

    // fetch is used instead of EventSource because the stream needs a bearer
    // token. The server replays the stored log after Last-Event-ID, then
    // follows live work, and closes the stream once the job is terminal, so a
    // reconnect resumes without duplicating events. A dropped connection is
    // retried from the last event id; an aborted signal rejects.
    // Resolves once the job is done, failed or cancelled.
    async stream(jobID: string, onEvent: (event: MissionEvent, sequence: number) => void, signal?: AbortSignal): Promise<Job> {
      let after = 0;
      let failures = 0;
      for (;;) {
        // One controller per connection: the caller's signal or an idle
        // watchdog ends it. Every chunk, heartbeats included, resets the watchdog.
        const connection = new AbortController();
        const stop = () => connection.abort();
        signal?.addEventListener("abort", stop);
        let idle = false;
        let reader: ReadableStreamDefaultReader<string> | undefined;
        let watchdog: ReturnType<typeof setTimeout> | undefined;
        const arm = () => {
          clearTimeout(watchdog);
          watchdog = setTimeout(() => {
            idle = true;
            connection.abort();
            reader?.cancel().catch(() => {}); // in case the fetch ignores its signal
          }, idleTimeoutMs);
        };
        try {
          if (signal?.aborted) throw signal.reason;
          arm();
          const response = await send(`${jobs}/${jobID}/stream`, {
            headers: after ? { "Last-Event-ID": String(after) } : undefined,
            signal: connection.signal,
          });
          if (!response.ok) await body(response);
          if (!response.body) throw new MissionError("stream has no body", response.status);
          reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
          let buffer = "";
          for (;;) {
            arm();
            const { value, done } = await reader.read();
            if (done) break;
            const parsed = parseFrames(buffer + value);
            buffer = parsed.rest;
            for (const frame of parsed.frames) {
              if (frame.id && frame.id <= after) continue;
              after = Math.max(after, frame.id);
              failures = 0;
              onEvent(JSON.parse(frame.data), frame.id);
            }
          }
          if (idle) throw new TypeError("stream went silent");
        } catch (cause) {
          // Only a dropped connection (a TypeError from fetch or the reader) or
          // a silent one is retried; kernel errors, sign-out and bad frames are final.
          if (signal?.aborted) throw signal.reason ?? cause;
          if (!(idle || cause instanceof TypeError) || ++failures > 5) throw cause;
          await new Promise((resolve) => setTimeout(resolve, 1000 * failures));
          continue;
        } finally {
          clearTimeout(watchdog);
          signal?.removeEventListener("abort", stop);
        }
        const job = await this.get(jobID);
        if (terminal.includes(job.status)) return job;
      }
    },
  };
}

export type MissionClient = ReturnType<typeof createMissionClient>;

export type TaskStatus = "waiting_dependency" | "ready" | "running" | "waiting_approval" | "completed" | "failed";
export type MissionStatus = "planning" | "running" | "waiting_approval" | "completed" | "failed";
export type MissionState = {
  status: MissionStatus;
  objective: string;
  plan: MissionPlan | null;
  tasks: Record<string, TaskStatus>;
  /** Each completed task's structured output (with its sources), keyed by task id. */
  outputs: Record<string, unknown>;
  decision: Decision | null;
  report: string;
  sourceCount: number;
  error: string | null;
  lastSequence: number;
};

export const initialMissionState = (objective = ""): MissionState => ({
  status: "planning", objective, plan: null, tasks: {}, outputs: {}, decision: null,
  report: "", sourceCount: 0, error: null, lastSequence: 0,
});

const metadata = <T>(event: MissionEvent, key: string) => event.metadata?.[key] as T | undefined;
const taskTransitions: Record<string, TaskStatus> = {
  "task.started": "running",
  "task.completed": "completed",
  "task.failed": "failed",
  "task.waiting_approval": "waiting_approval",
};

/** Folds one stream event into the mission state. Replayed events are ignored. */
export function reduceMission(state: MissionState, event: MissionEvent, sequence: number): MissionState {
  if (sequence && sequence <= state.lastSequence) return state;
  const next: MissionState = { ...state, lastSequence: Math.max(state.lastSequence, sequence) };
  switch (event.type) {
    case "mission.created":
      next.status = "planning";
      if (event.content) next.objective = event.content;
      break;
    case "mission.planned": {
      const plan = metadata<MissionPlan>(event, "plan");
      if (plan) {
        next.plan = plan;
        next.tasks = Object.fromEntries(plan.tasks.map((task) => [task.id, task.dependencies.length ? "waiting_dependency" : "ready"]));
      }
      next.status = "running";
      break;
    }
    case "approval.required":
      next.decision = metadata<Decision>(event, "decision") ?? next.decision;
      next.status = "waiting_approval";
      break;
    case "approval.resolved":
      next.decision = null;
      next.status = "running";
      break;
    case "report.completed":
      next.sourceCount = metadata<number>(event, "source_count") ?? 0;
      break;
    case "response_complete":
      next.report = event.content ?? "";
      next.status = "completed";
      break;
    case "error":
    case "failed":
    case "authz_failed":
      next.error = event.content || "Mission failed";
      next.status = "failed";
      break;
    // The worker's terminal receipt. Its status is the job's final status, so a
    // job that ended without a report or an error event still leaves planning.
    case "done":
    case "cancelled": {
      const status = metadata<string>(event, "status") ?? event.type;
      if (status === "done" && !next.report && event.content) {
        next.report = event.content;
        next.status = "completed";
      } else if (status !== "done" && next.status !== "completed" && !next.error) {
        next.error = status === "cancelled" ? "Mission cancelled" : "Mission failed";
        next.status = "failed";
      }
      break;
    }
  }
  const taskID = metadata<string>(event, "task_id");
  const transition = taskTransitions[event.type];
  if (taskID && transition) {
    next.tasks = { ...next.tasks, [taskID]: transition };
    const output = metadata<unknown>(event, "output");
    if (event.type === "task.completed" && output !== undefined) next.outputs = { ...next.outputs, [taskID]: output };
  }
  return next;
}
