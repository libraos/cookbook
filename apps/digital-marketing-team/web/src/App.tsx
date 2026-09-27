import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createMission,
  resolveDecision,
  streamMission,
  type Decision,
  type Employee,
  type MissionEvent,
  type MissionPlan,
  type Task,
} from "./api";
import { isSignedIn, signIn, signOut, SignedOut } from "./auth";
import { Markdown } from "./Markdown";

type TaskStatus = "planned" | "waiting_dependency" | "ready" | "running" | "waiting_approval" | "completed" | "failed";
type Activity = { sequence: number; type: string; text: string };

const example = "Create a 14-day developer marketing campaign for LibraOS. Target AI developers and aim for 500 qualified signups. Produce the strategy, channel plan, launch examples, developer messaging, KPI model, and final report. Ask me to approve the positioning before it is used in launch drafts. Do not publish anything.";

function value<T>(event: MissionEvent, key: string): T | undefined {
  return event.metadata?.[key] as T | undefined;
}

function eventText(event: MissionEvent): string | null {
  const labels: Record<string, string> = {
    "mission.created": "Mission received by the Head of Marketing",
    "mission.planned": "Created the department and execution plan",
    "agent.created": `Added ${event.content ?? "a specialist"}`,
    "task.started": `Started ${event.content ?? "a task"}`,
    "task.completed": `Completed ${event.content ?? "a task"}`,
    "task.failed": `Could not complete ${event.content ?? "a task"}`,
    "handoff.created": `Passed ${event.content ?? "structured work"} to the next owner`,
    "approval.required": "Requested an executive decision",
    "approval.resolved": "Executive decision recorded; dependent work resumed",
    "report.synthesis_started": "Head of Marketing started final synthesis",
    "report.completed": "Final report is ready",
    "mission.completed": "Mission completed",
  };
  return labels[event.type] ?? null;
}

export function App({ initialError }: { initialError: string | null }) {
  const [signedIn, setSignedIn] = useState(isSignedIn());
  const [error, setError] = useState(initialError);
  const [objective, setObjective] = useState(example);
  const [submittedObjective, setSubmittedObjective] = useState("");
  const [jobID, setJobID] = useState<string | null>(null);
  const [status, setStatus] = useState<"empty" | "submitting" | "planning" | "running" | "waiting_approval" | "completed" | "failed">("empty");
  const [plan, setPlan] = useState<MissionPlan | null>(null);
  const [tasks, setTasks] = useState<Record<string, TaskStatus>>({});
  const [activities, setActivities] = useState<Activity[]>([]);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [report, setReport] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
	const [sourceCount, setSourceCount] = useState(0);
  const streamAbort = useRef<AbortController | null>(null);

  const onError = useCallback((cause: unknown) => {
    if (cause instanceof SignedOut) setSignedIn(false);
    else {
      setError((cause as Error).message);
      setStatus("failed");
    }
  }, []);

  const applyEvent = useCallback((event: MissionEvent, sequence: number) => {
    const text = eventText(event);
    if (text) setActivities((items) => [...items, { sequence, type: event.type, text }].slice(-60));
    if (event.type === "mission.created") setStatus("planning");
    if (event.type === "mission.planned") {
      const nextPlan = value<MissionPlan>(event, "plan");
      if (nextPlan) {
        setPlan(nextPlan);
        setTasks(Object.fromEntries(nextPlan.tasks.map((task) => [task.id, task.dependencies.length ? "waiting_dependency" : "ready"])));
      }
      setStatus("running");
    }
    const taskID = value<string>(event, "task_id");
    if (taskID) {
      const next: Partial<Record<string, TaskStatus>> = {
        "task.started": "running",
        "task.completed": "completed",
        "task.failed": "failed",
        "task.waiting_approval": "waiting_approval",
      };
      const taskStatus = next[event.type];
      if (taskStatus) setTasks((current) => ({ ...current, [taskID]: taskStatus }));
    }
    if (event.type === "approval.required") {
      const nextDecision = value<Decision>(event, "decision");
      if (nextDecision) setDecision(nextDecision);
      setStatus("waiting_approval");
    }
    if (event.type === "approval.resolved") {
      setDecision(null);
      setInstruction("");
      setStatus("running");
    }
		if (event.type === "response_complete") {
			setReport(event.content ?? "");
			setStatus("completed");
		}
		if (event.type === "report.completed") setSourceCount(value<number>(event, "source_count") ?? 0);
    if (event.type === "error") {
      setError(event.content ?? "Mission failed");
      setStatus("failed");
    }
  }, []);

  useEffect(() => {
    if (!jobID) return;
    const controller = new AbortController();
    streamAbort.current = controller;
    streamMission(jobID, applyEvent, controller.signal).catch((cause) => {
      if (!controller.signal.aborted) onError(cause);
    });
    return () => controller.abort();
  }, [jobID, applyEvent, onError]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = objective.trim();
    if (!message || status !== "empty") return;
    setError(null);
    setStatus("submitting");
    setSubmittedObjective(message);
    try {
      setJobID(await createMission(message));
      setStatus("planning");
    } catch (cause) {
      onError(cause);
    }
  }

  async function decide(choice: string, customInstruction = "") {
    if (!jobID || !decision) return;
    setDecisionBusy(true);
    try {
      await resolveDecision(jobID, decision.id, choice, customInstruction);
    } catch (cause) {
      onError(cause);
    } finally {
      setDecisionBusy(false);
    }
  }

  function reset() {
    streamAbort.current?.abort();
    setJobID(null);
    setSubmittedObjective("");
    setPlan(null);
    setTasks({});
    setActivities([]);
    setDecision(null);
    setReport("");
		setSourceCount(0);
    setReportOpen(false);
    setError(null);
    setStatus("empty");
  }

  const completed = Object.values(tasks).filter((task) => task === "completed").length;
  const failed = Object.values(tasks).filter((task) => task === "failed").length;
  const total = plan?.tasks.length ?? 0;
  const progress = total ? Math.round(((completed + failed) / total) * 100) : 0;

  if (!signedIn) {
    return <main className="signin">
      <div className="mark">L</div>
      <p className="eyebrow">LibraOS Cookbook</p>
      <h1>Give your marketing department one mission.</h1>
      <p>Watch LibraOS assemble and run a digital team, then return one accountable deliverable.</p>
      {error && <p className="error">{error}</p>}
      <button className="primary" onClick={() => signIn()}>Sign in with LibraOS</button>
    </main>;
  }

  if (reportOpen && report) {
    return <ReportView report={report} plan={plan} onClose={() => setReportOpen(false)} />;
  }

  return <div className="shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">L</span><span>LibraOS</span><span className="cookbook">Cookbook</span></div>
      <div className={`mission-state ${status}`}><span />{statusLabel(status)}</div>
      <button className="quiet" onClick={() => signOut()}>Sign out</button>
    </header>

    {status === "empty" ? <Start objective={objective} setObjective={setObjective} submit={submit} /> :
      <main className="workspace">
        <section className="conversation">
          <div className="conversation-scroll">
            <p className="panel-label">CEO → Head of Marketing</p>
            <article className="message user-message"><span className="speaker">You</span>{submittedObjective}</article>
            <article className="message system-message">
              <span className="speaker">Head of Marketing</span>
              I’ll own this mission, assemble the specialists it requires, and return one finished report. Any reserved executive decision will come back to you here.
            </article>
            {status === "planning" && <Planning />}
            {plan && <article className="message system-message compact">
              <span className="speaker">Head of Marketing</span>
              I created a {plan.employees.length}-person department and a {plan.tasks.length}-task execution plan for <strong>{plan.title}</strong>.
            </article>}
            {decision && <ApprovalCard decision={decision} instruction={instruction} setInstruction={setInstruction} busy={decisionBusy} decide={decide} />}
            {status === "completed" && <article className="complete-card">
              <span className="completion-check">✓</span>
              <div><p className="eyebrow">Mission complete</p><h2>{plan?.title}</h2>
                <p>{plan?.employees.length} employees · {completed} tasks completed · {sourceCount} sources used</p>
                <div className="actions"><button className="primary" onClick={() => setReportOpen(true)}>Open report</button><button onClick={reset}>New mission</button></div>
              </div>
            </article>}
            {error && <div className="error-banner">{error}</div>}
          </div>
        </section>

        <section className="execution">
          <div className="execution-head"><div><p className="panel-label">Digital department</p><h2>{plan?.title ?? "Assembling the team"}</h2></div><span className="task-total">{completed}/{total || "—"} tasks</span></div>
          {!plan ? <TeamSkeleton /> : <Team employees={plan.employees} tasks={plan.tasks} states={tasks} />}
          <ActivityStream activities={activities} />
        </section>
      </main>}

    {status !== "empty" && <footer className="progress-footer">
      <div className="progress-copy"><strong>Mission progress</strong><span>{completed} complete · {Object.values(tasks).filter((task) => task === "running").length} running · {Object.values(tasks).filter((task) => task.startsWith("waiting")).length} waiting</span></div>
      <div className="progress-track"><span style={{ width: `${progress}%` }} /></div><b>{progress}%</b>
    </footer>}
  </div>;
}

function Start({ objective, setObjective, submit }: { objective: string; setObjective: (value: string) => void; submit: (event: FormEvent) => void }) {
  return <main className="start">
    <div className="start-copy"><p className="eyebrow">One mission · One runtime · A complete digital department</p><h1>What should your marketing team accomplish?</h1><p>The Head of Marketing will choose the team, break down the work, run it in parallel, and bring back one finished deliverable.</p></div>
    <form className="mission-composer" onSubmit={submit}>
      <textarea aria-label="Mission objective" value={objective} onChange={(event) => setObjective(event.target.value)} rows={6} />
      <div className="composer-bottom"><span>Public actions always require approval.</span><button className="primary" type="submit">Start mission <span>→</span></button></div>
    </form>
    <div className="promise"><span>01</span><p><strong>One instruction</strong>No agent setup or workflow builder.</p><span>02</span><p><strong>Autonomous execution</strong>Real tasks, dependencies, and handoffs.</p><span>03</span><p><strong>One deliverable</strong>Sources and contributors remain inspectable.</p></div>
  </main>;
}

function Planning() {
  return <div className="planning-card"><p className="panel-label">Understanding the mission</p><div className="planning-step done">Goal and constraints identified</div><div className="planning-step active">Creating the department and execution plan</div><div className="planning-step">Preparing parallel work</div></div>;
}

function Team({ employees, tasks, states }: { employees: Employee[]; tasks: Task[]; states: Record<string, TaskStatus> }) {
  return <div className="team">{employees.map((employee) => {
    const owned = tasks.filter((task) => task.owner_agent === employee.id);
    const done = owned.filter((task) => states[task.id] === "completed").length;
    const active = owned.find((task) => states[task.id] === "running");
    return <article className="employee" key={employee.id}>
      <div className="employee-top"><div className="avatar">{employee.name.slice(0, 1)}</div><div><h3>{employee.name}</h3><p>{employee.role}</p></div><span className={`employee-status ${active ? "working" : done === owned.length ? "done" : "waiting"}`}>{active ? "Working" : done === owned.length ? "Complete" : "Waiting"}</span></div>
      <div className="employee-progress"><span style={{ width: `${owned.length ? done / owned.length * 100 : 0}%` }} /></div>
      <p className="count">{done} / {owned.length} tasks complete</p>
      <div className="task-list">{owned.map((task) => <TaskRow key={task.id} task={task} status={states[task.id] ?? "planned"} />)}</div>
    </article>;
  })}</div>;
}

function TaskRow({ task, status }: { task: Task; status: TaskStatus }) {
  const icon = status === "completed" ? "✓" : status === "failed" ? "!" : status === "running" ? "●" : status === "waiting_approval" ? "◆" : "○";
  return <div className={`task-row ${status}`} title={task.objective}><span className="task-icon">{icon}</span><div><span>{task.title}</span>{task.dependencies.length > 0 && <small>after {task.dependencies.join(", ")}</small>}</div></div>;
}

function ApprovalCard({ decision, instruction, setInstruction, busy, decide }: { decision: Decision; instruction: string; setInstruction: (value: string) => void; busy: boolean; decide: (choice: string, instruction?: string) => void }) {
  return <article className="approval-card"><p className="eyebrow">Decision required</p><h2>{decision.question}</h2><p className="recommendation">Head of Marketing recommends <strong>{decision.options.find((option) => option.id === decision.recommendation)?.label}</strong>. {decision.reason}</p>
    <div className="options">{decision.options.map((option) => <button key={option.id} disabled={busy} className={option.id === decision.recommendation ? "recommended" : ""} onClick={() => decide(option.id)}><span>{option.label}</span><small>{option.description}</small></button>)}</div>
    <div className="instruction"><input placeholder="Or give a specific instruction…" value={instruction} onChange={(event) => setInstruction(event.target.value)} /><button disabled={busy || !instruction.trim()} onClick={() => decide("", instruction)}>Send</button></div>
  </article>;
}

function ActivityStream({ activities }: { activities: Activity[] }) {
  const visible = activities.slice(-7).reverse();
  return <section className="activity"><p className="panel-label">Activity</p>{visible.length === 0 ? <p className="muted">Runtime events will appear here.</p> : visible.map((item) => <div className="activity-row" key={item.sequence}><span className={item.type.includes("failed") ? "failure" : item.type.includes("completed") ? "success" : ""} />{item.text}</div>)}</section>;
}

function TeamSkeleton() {
  return <div className="team skeleton-team">{[0, 1, 2].map((item) => <div className="employee skeleton" key={item}><i /><b /><span /></div>)}</div>;
}

function ReportView({ report, plan, onClose }: { report: string; plan: MissionPlan | null; onClose: () => void }) {
  const sections = useMemo(() => report.split("\n").filter((line) => line.startsWith("## ")).map((line) => line.slice(3)), [report]);
  return <div className="report-shell"><header className="topbar"><div className="brand"><span className="brand-mark">L</span><span>LibraOS</span><span className="cookbook">Deliverable</span></div><button onClick={onClose}>← Back to mission</button></header><main className="report-layout"><aside className="toc"><p className="panel-label">Contents</p>{sections.map((section) => <span key={section}>{section}</span>)}</aside><article className="report-document"><Markdown text={report} /></article><aside className="contributors"><p className="panel-label">Contributors</p>{plan?.employees.map((employee) => <div key={employee.id}><span className="mini-avatar">{employee.name.slice(0, 1)}</span><p><strong>{employee.name}</strong><small>{employee.role}</small></p></div>)}</aside></main></div>;
}

function statusLabel(status: string) {
  return ({ empty: "Ready", submitting: "Starting", planning: "Planning", running: "Running", waiting_approval: "Needs decision", completed: "Complete", failed: "Needs attention" } as Record<string, string>)[status];
}
