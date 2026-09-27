import { authFetch } from "./auth";

const EMPLOYEE = "head-of-marketing";

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
export type MissionEvent = {
  type: string;
  content?: string;
  metadata?: Record<string, unknown>;
};
export type Job = { job_id: string; status: string; result?: string; error?: string };

async function body<T>(response: Response): Promise<T> {
  const value = await response.json();
  if (!response.ok) throw new Error(value.message ?? value.error ?? `HTTP ${response.status}`);
  return value;
}

export async function createMission(message: string): Promise<string> {
  const response = await authFetch(`/agents/v1/${EMPLOYEE}/jobs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message }),
  });
  return (await body<{ job_id: string }>(response)).job_id;
}

export async function getMission(jobID: string): Promise<Job> {
  return body<Job>(await authFetch(`/agents/v1/${EMPLOYEE}/jobs/${jobID}`));
}

export async function resolveDecision(jobID: string, decisionID: string, choice: string, instruction = ""): Promise<void> {
  await body(await authFetch(`/agents/v1/${EMPLOYEE}/jobs/${jobID}/decisions/${decisionID}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ choice, instruction }),
  }));
}

// fetch is used instead of EventSource because the durable stream is protected
// by the signed-in user's bearer token. The server replays the event log first,
// then follows live state, so reconnecting never fabricates progress.
export async function streamMission(
  jobID: string,
  onEvent: (event: MissionEvent, sequence: number) => void,
  signal: AbortSignal,
): Promise<void> {
  let after = 0;
  for (;;) {
    const response = await authFetch(`/agents/v1/${EMPLOYEE}/jobs/${jobID}/stream`, {
      headers: after ? { "Last-Event-ID": String(after) } : undefined,
      signal,
    });
    if (!response.ok || !response.body) await body(response);
    const reader = response.body!.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value.replace(/\r\n/g, "\n");
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        if (!frame || frame.startsWith(":")) continue;
        const lines = frame.split("\n");
        const id = Number(lines.find((line) => line.startsWith("id:"))?.slice(3).trim() ?? 0);
        const data = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("");
        if (!data) continue;
        after = Math.max(after, id);
        onEvent(JSON.parse(data), id);
      }
    }
    const job = await getMission(jobID);
    if (["done", "failed", "cancelled"].includes(job.status)) return;
  }
}
