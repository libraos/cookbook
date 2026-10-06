import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createMissionClient,
  initialMissionState,
  reduceMission,
  type Decision,
  type Employee,
  type MissionEvent,
  type MissionPlan,
  type MissionState,
  type Task,
  type TaskStatus,
} from "../../../shared/mission-client/src";
import { authFetch, isSignedIn, signIn, signOut, SignedOut } from "./auth";
import { catalog, findMission, type CatalogMission } from "./catalog";
import { Markdown } from "./Markdown";

type Activity = { sequence: number; type: string; text: string };
type ActiveMission = { jobID: string; missionID: string; objective: string };
type Phase = "empty" | "submitting" | MissionState["status"];

const activeMissionKey = "libraos.mission-console.active-mission";

function loadActiveMission(): ActiveMission | null {
  let stored: ActiveMission | null = null;
  try {
    const parsed = JSON.parse(sessionStorage.getItem(activeMissionKey) ?? "null") as Partial<ActiveMission> | null;
    stored = parsed?.jobID && parsed.missionID && findMission(parsed.missionID) ? parsed as ActiveMission : null;
  } catch {
    sessionStorage.removeItem(activeMissionKey);
  }
  const params = new URL(location.href).searchParams;
  const jobID = params.get("job");
  const missionID = params.get("mission");
  if (jobID?.startsWith("job_") && findMission(missionID)) {
    const requested = { jobID, missionID: missionID!, objective: stored?.jobID === jobID ? stored.objective : "Recovering saved mission…" };
    sessionStorage.setItem(activeMissionKey, JSON.stringify(requested));
    return requested;
  }
  return stored;
}

function saveActiveMission(mission: ActiveMission | null) {
  if (mission) sessionStorage.setItem(activeMissionKey, JSON.stringify(mission));
  else sessionStorage.removeItem(activeMissionKey);
}

function showMissionInURL(mission: ActiveMission | null) {
  const url = new URL(location.href);
  if (mission) {
    url.searchParams.set("mission", mission.missionID);
    url.searchParams.set("job", mission.jobID);
  } else {
    url.searchParams.delete("mission");
    url.searchParams.delete("job");
  }
  history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
}

function downloadReport(report: string, title: string | undefined, fallback: string) {
  const filename = (title ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || fallback;
  const url = URL.createObjectURL(new Blob([report], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${filename}.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function eventText(event: MissionEvent, lead: string): string | null {
  const labels: Record<string, string> = {
    "mission.created": `Mission received by the ${lead}`,
    "mission.planned": "Created the team and execution plan",
    "agent.created": `Added ${event.content ?? "a specialist"}`,
    "task.started": `Started ${event.content ?? "a task"}`,
    "task.completed": `Completed ${event.content ?? "a task"}`,
    "task.failed": `Could not complete ${event.content ?? "a task"}`,
    "handoff.created": `Passed ${event.content ?? "structured work"} to the next owner`,
    "approval.required": "Requested a decision",
    "approval.resolved": "Decision recorded; dependent work resumed",
    "report.synthesis_started": `${lead} started final synthesis`,
    "report.completed": "Final report is ready",
    "mission.completed": "Mission completed",
  };
  return labels[event.type] ?? null;
}

export function App({ initialError }: { initialError: string | null }) {
  const [restored] = useState(loadActiveMission);
  const [signedIn, setSignedIn] = useState(isSignedIn());
  const [error, setError] = useState(initialError);
  const [selected, setSelected] = useState<CatalogMission>(findMission(restored?.missionID) ?? catalog[0]);
  const [objective, setObjective] = useState(restored?.objective ?? selected.example);
  const [active, setActive] = useState<ActiveMission | null>(restored);
  const [submitting, setSubmitting] = useState(false);
  const [mission, setMission] = useState<MissionState>(initialMissionState(restored?.objective));
  const [activities, setActivities] = useState<Activity[]>([]);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const streamAbort = useRef<AbortController | null>(null);
  const client = useMemo(() => createMissionClient({ lead: selected.lead, fetch: authFetch }), [selected.lead]);

  const onError = useCallback((cause: unknown) => {
    if (cause instanceof SignedOut) setSignedIn(false);
    else setError((cause as Error).message);
  }, []);

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    streamAbort.current = controller;
    let last = 0;
    client.stream(active.jobID, (event, sequence) => {
      if (sequence && sequence <= last) return;
      last = Math.max(last, sequence);
      setMission((state) => reduceMission(state, event, sequence));
      const text = eventText(event, selected.leadName);
      if (text) setActivities((items) => [...items, { sequence, type: event.type, text }].slice(-60));
      if (event.type === "mission.created" && event.content) saveActiveMission({ ...active, objective: event.content });
    }, controller.signal).catch((cause) => {
      if (!controller.signal.aborted) onError(cause);
    });
    return () => controller.abort();
  }, [active, client, selected.leadName, onError]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = objective.trim();
    if (!message || active || submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const jobID = await client.create(message);
      const next = { jobID, missionID: selected.id, objective: message };
      saveActiveMission(next);
      showMissionInURL(next);
      setMission(initialMissionState(message));
      setActive(next);
    } catch (cause) {
      onError(cause);
    } finally {
      setSubmitting(false);
    }
  }

  async function decide(choice: string, customInstruction = "") {
    if (!active || !mission.decision) return;
    setDecisionBusy(true);
    try {
      await client.resolveDecision(active.jobID, mission.decision.id, choice, customInstruction);
      setInstruction("");
    } catch (cause) {
      onError(cause);
    } finally {
      setDecisionBusy(false);
    }
  }

  function reset() {
    streamAbort.current?.abort();
    saveActiveMission(null);
    showMissionInURL(null);
    setActive(null);
    setMission(initialMissionState());
    setActivities([]);
    setReportOpen(false);
    setError(null);
  }

  function choose(entry: CatalogMission) {
    if (objective === selected.example) setObjective(entry.example);
    setSelected(entry);
  }

  const { plan, tasks, decision, report, sourceCount } = mission;
  const phase: Phase = !active ? (submitting ? "submitting" : "empty") : error ? "failed" : mission.status;
  const states = Object.values(tasks);
  const completed = states.filter((task) => task === "completed").length;
  const failed = states.filter((task) => task === "failed").length;
  const total = plan?.tasks.length ?? 0;
  const progress = total ? Math.round(((completed + failed) / total) * 100) : 0;

  if (!signedIn) {
    return <main className="signin">
      <div className="mark">L</div>
      <p className="eyebrow">LibraOS Cookbook</p>
      <h1>Give a team one mission.</h1>
      <p>Pick a pack, describe the outcome, and watch LibraOS plan and run the work, then return one accountable deliverable.</p>
      {error && <p className="error">{error}</p>}
      <button className="primary" onClick={() => signIn()}>Sign in with LibraOS</button>
    </main>;
  }

  if (reportOpen && report) {
    return <ReportView report={report} plan={plan} filename={selected.reportFilename} onClose={() => setReportOpen(false)} />;
  }

  return <div className="shell">
    <header className="topbar">
      <div className="brand"><span className="brand-mark">L</span><span>LibraOS</span><span className="cookbook">Mission Console</span></div>
      <div className={`mission-state ${phase}`}><span />{statusLabel(phase)}</div>
      <button className="quiet" onClick={() => signOut()}>Sign out</button>
    </header>

    {!active ? <Start mission={selected} choose={choose} objective={objective} setObjective={setObjective} submit={submit} submitting={submitting} error={error} /> :
      <main className="workspace">
        <section className="conversation">
          <div className="conversation-scroll">
            <p className="panel-label">You → {selected.leadName}</p>
            <article className="message user-message"><span className="speaker">You</span>{mission.objective || active.objective}</article>
            <article className="message system-message">
              <span className="speaker">{selected.leadName}</span>
              I’ll own this mission, assemble the specialists it requires, and return one finished report. Any decision reserved for you will come back here.
            </article>
            {phase === "planning" && <Planning />}
            {plan && <article className="message system-message compact">
              <span className="speaker">{selected.leadName}</span>
              I created a {plan.employees.length}-person team and a {plan.tasks.length}-task execution plan for <strong>{plan.title}</strong>.
            </article>}
            {decision && <ApprovalCard lead={selected.leadName} decision={decision} instruction={instruction} setInstruction={setInstruction} busy={decisionBusy} decide={decide} />}
            {phase === "completed" && <article className="complete-card">
              <span className="completion-check">✓</span>
              <div><p className="eyebrow">Mission complete</p><h2>{plan?.title}</h2>
                <p>{plan?.employees.length} employees · {completed} tasks completed · {sourceCount} sources used</p>
                <div className="actions"><button className="primary" onClick={() => setReportOpen(true)}>Open report</button><button onClick={() => downloadReport(report, plan?.title, selected.reportFilename)}>Download report</button><button onClick={reset}>New mission</button></div>
              </div>
            </article>}
            {(error || mission.error) && <div className="error-banner">{error ?? mission.error}<button className="quiet" onClick={reset}>New mission</button></div>}
          </div>
        </section>

        <section className="execution">
          <div className="execution-head"><div><p className="panel-label">{selected.teamName}</p><h2>{plan?.title ?? "Assembling the team"}</h2></div><span className="task-total">{completed}/{total || "—"} tasks</span></div>
          {!plan ? <TeamSkeleton /> : <Team employees={plan.employees} tasks={plan.tasks} states={tasks} />}
          <ActivityStream activities={activities} />
        </section>
      </main>}

    {active && <footer className="progress-footer">
      <div className="progress-copy"><strong>Mission progress</strong><span>{completed} complete · {states.filter((task) => task === "running").length} running · {states.filter((task) => task.startsWith("waiting")).length} waiting</span></div>
      <div className="progress-track"><span style={{ width: `${progress}%` }} /></div><b>{progress}%</b>
    </footer>}
  </div>;
}

function Start({ mission, choose, objective, setObjective, submit, submitting, error }: {
  mission: CatalogMission; choose: (entry: CatalogMission) => void; objective: string;
  setObjective: (value: string) => void; submit: (event: FormEvent) => void; submitting: boolean; error: string | null;
}) {
  return <main className="start">
    <div className="start-copy">
      <p className="eyebrow">Pack · {mission.pack}</p>
      {catalog.length > 1 && <div className="mission-picker" role="tablist" aria-label="Mission">{catalog.map((entry) =>
        <button key={entry.id} role="tab" aria-selected={entry.id === mission.id} className={entry.id === mission.id ? "selected" : ""} onClick={() => choose(entry)}>{entry.teamName}</button>)}</div>}
      <h1>{mission.headline}</h1><p>{mission.description}</p>
    </div>
    <form className="mission-composer" onSubmit={submit}>
      <textarea aria-label="Mission objective" value={objective} onChange={(event) => setObjective(event.target.value)} rows={6} />
      <div className="composer-bottom"><span>Public actions always require approval.</span><button className="primary" type="submit" disabled={submitting}>{submitting ? "Starting…" : <>Start mission <span>→</span></>}</button></div>
    </form>
    {error && <p className="error">{error}</p>}
    <div className="promise"><span>01</span><p><strong>One instruction</strong>No agent setup or workflow builder.</p><span>02</span><p><strong>Autonomous execution</strong>Real tasks, dependencies, and handoffs.</p><span>03</span><p><strong>One deliverable</strong>Sources and contributors remain inspectable.</p></div>
  </main>;
}

function Planning() {
  return <div className="planning-card"><p className="panel-label">Understanding the mission</p><div className="planning-step done">Goal and constraints identified</div><div className="planning-step active">Creating the team and execution plan</div><div className="planning-step">Preparing parallel work</div></div>;
}

function Team({ employees, tasks, states }: { employees: Employee[]; tasks: Task[]; states: Record<string, TaskStatus> }) {
  return <div className="team">{employees.map((employee) => {
    const owned = tasks.filter((task) => task.owner_agent === employee.id);
    const done = owned.filter((task) => states[task.id] === "completed").length;
    const working = owned.find((task) => states[task.id] === "running");
    return <article className="employee" key={employee.id}>
      <div className="employee-top"><div className="avatar">{employee.name.slice(0, 1)}</div><div><h3>{employee.name}</h3><p>{employee.role}</p></div><span className={`employee-status ${working ? "working" : done === owned.length ? "done" : "waiting"}`}>{working ? "Working" : done === owned.length ? "Complete" : "Waiting"}</span></div>
      <div className="employee-progress"><span style={{ width: `${owned.length ? done / owned.length * 100 : 0}%` }} /></div>
      <p className="count">{done} / {owned.length} tasks complete</p>
      <div className="task-list">{owned.map((task) => <TaskRow key={task.id} task={task} status={states[task.id] ?? "ready"} />)}</div>
    </article>;
  })}</div>;
}

function TaskRow({ task, status }: { task: Task; status: TaskStatus }) {
  const icon = status === "completed" ? "✓" : status === "failed" ? "!" : status === "running" ? "●" : status === "waiting_approval" ? "◆" : "○";
  return <div className={`task-row ${status}`} title={task.objective}><span className="task-icon">{icon}</span><div><span>{task.title}</span>{task.dependencies.length > 0 && <small>after {task.dependencies.join(", ")}</small>}</div></div>;
}

function ApprovalCard({ lead, decision, instruction, setInstruction, busy, decide }: { lead: string; decision: Decision; instruction: string; setInstruction: (value: string) => void; busy: boolean; decide: (choice: string, instruction?: string) => void }) {
  return <article className="approval-card"><p className="eyebrow">Decision required</p><h2>{decision.question}</h2><p className="recommendation">{lead} recommends <strong>{decision.options.find((option) => option.id === decision.recommendation)?.label}</strong>. {decision.reason}</p>
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

function ReportView({ report, plan, filename, onClose }: { report: string; plan: MissionPlan | null; filename: string; onClose: () => void }) {
  const sections = useMemo(() => report.split("\n").filter((line) => line.startsWith("## ")).map((line) => line.slice(3)), [report]);
  return <div className="report-shell"><header className="topbar"><div className="brand"><span className="brand-mark">L</span><span>LibraOS</span><span className="cookbook">Deliverable</span></div><div className="report-actions"><button className="primary" onClick={() => downloadReport(report, plan?.title, filename)}>Download report</button><button onClick={onClose}>← Back to mission</button></div></header><main className="report-layout"><aside className="toc"><p className="panel-label">Contents</p>{sections.map((section) => <span key={section}>{section}</span>)}</aside><article className="report-document"><Markdown text={report} /></article><aside className="contributors"><p className="panel-label">Contributors</p>{plan?.employees.map((employee) => <div key={employee.id}><span className="mini-avatar">{employee.name.slice(0, 1)}</span><p><strong>{employee.name}</strong><small>{employee.role}</small></p></div>)}</aside></main></div>;
}

function statusLabel(phase: Phase) {
  return ({ empty: "Ready", submitting: "Starting", planning: "Planning", running: "Running", waiting_approval: "Needs decision", completed: "Complete", failed: "Needs attention" } as Record<Phase, string>)[phase];
}
