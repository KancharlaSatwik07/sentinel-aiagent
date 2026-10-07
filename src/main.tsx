import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Check,
  ChevronRight,
  Circle,
  FileCode2,
  FolderGit2,
  LoaderCircle,
  LockKeyhole,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Terminal,
  Upload,
  X,
} from "lucide-react";
import "./style.css";

type Files = Record<string, string>;
type Evidence = {
  passing: string[];
  failing: string[];
  skipped: string[];
  errors: string[];
  test_files: string[];
  mode?: "pytest" | "static";
  valid: boolean;
  output: string;
};
type Proposal = {
  explanation: string;
  edits: { file: string; content: string }[];
  model: string;
  mode: string;
};
type Verification = {
  accepted: boolean;
  regressions: string[];
  reason: string;
  after: Evidence;
  diff: string;
  files_changed: string[];
};
type ServerStatus = {
  openrouter_configured: boolean;
  ai_enabled: boolean;
  model: string;
  execution_enabled: boolean;
  hosted: boolean;
};
type TimelineItem = { title: string; detail: string; state: "ok" | "bad" | "working" };
type Attempt = { number: number; proposal?: Proposal; result?: Verification; error?: string };
type Workspace = { name: string; files: Files; task: string; active: string };
const STORAGE_KEY = "sentinel.workspace.v4";
const initialWorkspace: Workspace = {
  name: "Untitled project",
  files: {},
  task: "",
  active: "",
};

function loadWorkspace(): Workspace {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null") as Partial<Workspace> | null;
    if (saved?.files && typeof saved.files === "object" && Object.keys(saved.files).length) {
      const files = Object.fromEntries(Object.entries(saved.files).filter(([key, value]) => key.endsWith(".py") && typeof value === "string")) as Files;
      if (Object.keys(files).length) {
        if (saved.name === "Untitled project" && Object.values(files).every((content) => !content.trim()) && !saved.task?.trim()) {
          return { ...initialWorkspace };
        }
        return { ...initialWorkspace, ...saved, files, active: files[saved.active || ""] !== undefined ? saved.active! : Object.keys(files)[0] };
      }
    }
  } catch {
    // Corrupt or unavailable browser storage falls back to an empty workspace.
  }
  return { ...initialWorkspace, files: { ...initialWorkspace.files } };
}

async function api<T>(route: string, body?: unknown, timeout = 30000): Promise<T> {
  const response = await fetch(`/api/${route}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(timeout),
  });
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new Error("API unavailable. Start the local Python server or review the deployment configuration.");
  }
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "Request failed.");
  return value as T;
}

function App() {
  const [workspace, setWorkspace] = useState<Workspace>(loadWorkspace);
  const [config, setConfig] = useState<ServerStatus | null>(null);
  const [openrouterConnected, setOpenRouterConnected] = useState(false);
  const [checkingOpenRouter, setCheckingOpenRouter] = useState(false);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const [githubUrl, setGithubUrl] = useState("");
  const [newFile, setNewFile] = useState("");
  const [showNewFile, setShowNewFile] = useState(false);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [before, setBefore] = useState<Evidence | null>(null);
  const [result, setResult] = useState<Verification | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [attempts, setAttempts] = useState<Attempt[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState<"diff" | "explanation" | "logs">("diff");
  const [completed, setCompleted] = useState(false);
  const [testTask, setTestTask] = useState("");
  const fileNames = useMemo(() => Object.keys(workspace.files).sort(), [workspace.files]);
  const activeFile = workspace.files[workspace.active] === undefined ? fileNames[0] : workspace.active;

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...workspace, active: activeFile })); } catch { /* Storage may be disabled or full. */ }
  }, [workspace, activeFile]);

  useEffect(() => {
    api<ServerStatus>("status").then(setConfig).catch((e: Error) => setError(e.message));
  }, []);

  function clearEvidence() {
    setBefore(null); setResult(null); setProposal(null); setAttempts([]); setTimeline([]); setCompleted(false);
  }
  function updateWorkspace(next: Partial<Workspace>) {
    setWorkspace((current) => ({ ...current, ...next }));
    clearEvidence();
  }
  function newProject() {
    setWorkspace({ ...initialWorkspace, files: {} });
    setGithubUrl(""); setError(""); setNotice("New empty workspace created."); setOpenRouterConnected(false); clearEvidence();
  }
  function addFile(event: React.FormEvent) {
    event.preventDefault();
    const path = newFile.trim();
    if (!/^(?!.*\.\.)(?!\/)[\w/-]+\.py$/.test(path) || workspace.files[path] !== undefined) {
      setError("Use a unique relative Python file path, such as src/helpers.py."); return;
    }
    updateWorkspace({ files: { ...workspace.files, [path]: "" }, active: path });
    setNewFile(""); setShowNewFile(false); setError("");
  }
  async function importRepository(event: React.FormEvent) {
    event.preventDefault(); setImporting(true); setError(""); setNotice("");
    try {
      const imported = await api<{ name: string; default_branch: string; files: Files; source_url: string }>("import-github", { url: githubUrl }, 60000);
      const first = Object.keys(imported.files).sort()[0];
      setWorkspace({ name: imported.name, files: imported.files, task: "", active: first });
      setOpenRouterConnected(false); clearEvidence();
      setNotice(`Imported ${Object.keys(imported.files).length} Python files from ${imported.name} (${imported.default_branch}). Review the code before running it.`);
      setGithubUrl("");
    } catch (e) { setError(e instanceof Error ? e.message : "Repository import failed."); }
    finally { setImporting(false); }
  }
  async function checkOpenRouter() {
    setCheckingOpenRouter(true); setError(""); setNotice("");
    try {
      const checked = await api<{ connected: boolean; model: string; message: string }>("openrouter-check", {}, 35000);
      setOpenRouterConnected(checked.connected); setNotice(`${checked.message} Model: ${checked.model}.`);
    } catch (e) { setOpenRouterConnected(false); setError(e instanceof Error ? e.message : "OpenRouter connection failed."); }
    finally { setCheckingOpenRouter(false); }
  }
  async function runAgent() {
    if (!config || !config.ai_enabled || !openrouterConnected) return setError("OpenRouter requests are unavailable. Check server configuration and verify the API connection.");
    setBusy(true); setError(""); setNotice(""); setBefore(null); setResult(null); setProposal(null); setAttempts([]); setCompleted(false); setTestTask(workspace.task);
    const original = { ...workspace.files };
    let feedback = "";
    const history: Attempt[] = [];
    try {
      if (config.hosted) {
        setTimeline([{ title: "Requesting a hosted proposal", detail: "Vercel will not execute uploaded Python; OpenRouter is reviewing the source and task only.", state: "working" }]);
        const hostedProposal = await api<Proposal>("propose", {
          task: workspace.task,
          files: original,
          test_output: "Hosted preview: pytest execution is unavailable. Do not claim tests passed; provide the smallest safe source change and regression tests.",
        }, 60000);
        setProposal(hostedProposal);
        history.push({ number: 1, proposal: hostedProposal });
        setAttempts([...history]);
        setTimeline([{ title: "Hosted proposal ready", detail: "Review the suggested diff locally and run pytest before applying it.", state: "ok" }]);
        setNotice("Proposal ready. Hosted Vercel mode does not execute or apply Python; review and test this change locally.");
        setTab("explanation");
        setCompleted(true);
        return;
      }
      setTimeline([{ title: "Running baseline tests", detail: "Collecting pytest evidence from the current project.", state: "working" }]);
      const baseline = await api<Evidence>("baseline", { files: original }, 20000);
      setBefore(baseline);
      setTimeline([{ title: baseline.mode === "static" ? "Python syntax checked" : "Pytest baseline recorded", detail: baseline.mode === "static" ? `${baseline.failing.length ? `${baseline.failing.length} syntax error(s)` : "No syntax errors"} · no pytest suite yet` : baseline.valid ? `${baseline.passing.length} passed · ${baseline.failing.length} failed · ${baseline.skipped.length} skipped` : `${baseline.errors.length ? "Collection error" : "No tests collected"} · Open Test output for details`, state: baseline.valid ? "ok" : "bad" }]);
      if (baseline.mode === "static") {
        setTab("logs");
        setNotice(baseline.failing.length ? "Python syntax errors were found. Open Test output for the exact file and line; OpenRouter will propose a fix and add regression tests." : "No pytest suite was found. Static syntax checks are complete; describe the expected behavior and OpenRouter will add regression tests with its repair proposal.");
      }
      if (!baseline.valid) {
        setTab("logs");
        setNotice(`Pytest could not collect ${baseline.errors.join(", ")}. Open Test output to see the exact syntax or import error; OpenRouter will propose a repair.`);
      }
      for (let number = 1; number <= 3; number++) {
        setTimeline((items) => [...items, { title: `Attempt ${number} · requesting a proposal`, detail: "OpenRouter receives the task, source files, and test evidence.", state: "working" }]);
        let nextProposal: Proposal | undefined;
        try {
          nextProposal = await api<Proposal>("propose", { task: workspace.task, files: original, test_output: baseline.output, feedback }, 60000);
          setProposal(nextProposal);
          setTimeline((items) => [...items.slice(0, -1), { title: `Attempt ${number} · verifying candidate`, detail: `Testing ${nextProposal!.edits.length} proposed file change(s) in a temporary copy.`, state: "working" }]);
          const verification = await api<Verification>("verify", { files: original, edits: nextProposal.edits, baseline }, 30000);
          history.push({ number, proposal: nextProposal, result: verification }); setAttempts([...history]); setResult(verification);
          setTimeline((items) => [...items.slice(0, -1), { title: `Attempt ${number} · ${verification.accepted ? "accepted" : "discarded"}`, detail: `${verification.after.passing.length} passed · ${verification.after.failing.length} failed · ${verification.regressions.length} regressions. ${verification.reason}`, state: verification.accepted ? "ok" : "bad" }]);
          if (verification.accepted) {
            const accepted = { ...original };
            nextProposal.edits.forEach((edit) => { accepted[edit.file] = edit.content; });
            setWorkspace((current) => ({ ...current, files: accepted })); setCompleted(true); return;
          }
          feedback = `${verification.reason}\n${verification.after.output}`;
        } catch (e) {
          const message = e instanceof Error ? e.message : "Request failed.";
          history.push({ number, proposal: nextProposal, error: message }); setAttempts([...history]); feedback = message;
          setTimeline((items) => [...items.slice(0, -1), { title: `Attempt ${number} · discarded`, detail: message, state: "bad" }]);
        }
      }
      setTimeline((items) => [...items, { title: "Original files preserved", detail: "No verified fix was accepted after three attempts.", state: "bad" }]); setCompleted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setTimeline((items) => items.map((item) => item.state === "working" ? { ...item, state: "bad", detail: "Stopped. The original workspace was preserved." } : item));
    } finally { setBusy(false); }
  }
  function downloadReport() {
    const report = `# Sentinel verification report\n\nProject: ${workspace.name}\nTask: ${testTask}\nModel: ${proposal?.model || config?.model || "Not used"}\n\nBaseline: ${before?.passing.length ?? 0} passing / ${before?.failing.length ?? 0} failing\n\nDecision: ${result?.accepted ? "Accepted" : before?.failing.length === 0 ? "No repair needed" : "No verified repair; original files preserved"}\n\n` + attempts.map((attempt) => `## Attempt ${attempt.number}\n${attempt.error || attempt.result?.reason || "No result"}\n\nFiles changed: ${attempt.result?.files_changed.join(", ") || "none"}\n\n${attempt.proposal?.explanation || ""}\n\n\`\`\`diff\n${attempt.result?.diff || ""}\n\`\`\`\n`).join("\n");
    const url = URL.createObjectURL(new Blob([report], { type: "text/markdown" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "sentinel-verification-report.md"; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const passed = result?.accepted ? result.after.passing.length : before?.passing.length;
  const failed = result?.accepted ? result.after.failing.length : before?.failing.length;
  const evidenceMode = result?.accepted ? result.after.mode : before?.mode;
  const canRun = Boolean(config && (config.execution_enabled || config.hosted) && config.ai_enabled && openrouterConnected && workspace.task.trim() && !busy);

  return <div className="app-shell">
    <aside className="rail" aria-label="Primary navigation">
      <a href="#top" className="brand-icon" aria-label="Sentinel home"><ShieldCheck size={22} /></a>
      <div className="rail-line" />
      <a href="#workspace" className="rail-item selected" aria-label="Project workspace"><FileCode2 size={20} /></a>
      <a href="#evidence" className="rail-item" aria-label="Verification evidence"><Activity size={20} /></a>
      <span className="rail-bottom">S<span className="online-dot" /></span>
    </aside>
    <div className="main" id="top">
      <header>
        <a className="wordmark" href="#top">sentinel<span className="slash">/</span><span className="header-label">Engineering workspace</span></a>
        <div className="header-right"><span className="secure-label"><LockKeyhole size={13} /> Server-side credentials</span><span className="avatar" aria-label="Workspace">WS</span></div>
      </header>
      <main>
        <section className="intro">
          <div><div className="eyebrow"><span className="lime-dot" /> SAFE AI SOFTWARE ENGINEERING</div><h1>Build with confidence.</h1><p>Bring a Python project. Let tests decide which AI changes stay.</p></div>
          <button className="secondary-button" onClick={newProject}><Plus size={15} /> New project</button>
        </section>

        <section className={`connection-card ${openrouterConnected ? "connected" : ""}`} aria-label="Service status">
          <div className="connection-icon"><Sparkles size={17} /></div>
          <div className="connection-copy"><strong>{openrouterConnected ? "OpenRouter connection verified" : !config?.openrouter_configured ? "OpenRouter API key required" : !config.ai_enabled ? "Hosted AI needs deployment setup" : "OpenRouter API key configured"}</strong><span>{openrouterConnected ? `Live request succeeded using ${config?.model}.` : !config?.openrouter_configured ? "Add OPENROUTER_API_KEY to the server environment. It is never sent to the browser." : !config.ai_enabled ? "Add ENABLE_PUBLIC_AI=1 in Vercel after configuring authentication, rate limits, and spending controls." : "Run a live check before asking OpenRouter to propose code."}</span></div>
          <button className="connection-button" onClick={checkOpenRouter} disabled={!config?.ai_enabled || checkingOpenRouter || busy}>{checkingOpenRouter ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}{checkingOpenRouter ? "Checking…" : "Test connection"}</button>
          <span className={`connection-pill ${openrouterConnected ? "online" : config?.ai_enabled ? "pending" : "offline"}`}><i />{openrouterConnected ? "CONNECTED" : config?.ai_enabled ? "NOT VERIFIED" : "NOT ENABLED"}</span>
        </section>

        {!config?.hosted && !config?.execution_enabled && <div className="safety-banner" role="note"><ShieldCheck size={16} /><span><strong>Local test execution is off.</strong> For trusted local source only, configure <code>ALLOW_TRUSTED_CODE=1</code>; imported code runs with your local account permissions.</span></div>}
        {config?.execution_enabled && <div className="safety-banner"><LockKeyhole size={16} /><span>Local-only runner enabled. Never test code you do not trust; this runner is not a security sandbox.</span></div>}

        <section className="workflow" aria-label="Workflow">{["Add a project", "Run tests", "Ask OpenRouter", "Verify a copy", "Review evidence"].map((item, index) => <React.Fragment key={item}><div className="workflow-step"><span>{String(index + 1).padStart(2, "0")}</span>{item}</div>{index < 4 && <ChevronRight className="workflow-arrow" size={15} />}</React.Fragment>)}</section>

        <div className="workspace" id="workspace">
          <section className="panel project-panel">
            <div className="panel-title"><div><span className="tiny-square" /> Project workspace</div><span className="panel-meta">{fileNames.length} Python file{fileNames.length === 1 ? "" : "s"}</span></div>
            <div className="project-heading"><div><span className="project-kicker">CURRENT PROJECT</span><input aria-label="Project name" value={workspace.name} maxLength={120} onChange={(event) => updateWorkspace({ name: event.target.value })} /></div><span className="project-state"><Circle size={8} /> Local workspace</span></div>
            <form className="github-import" onSubmit={importRepository}><div className="github-form-copy"><FolderGit2 size={16} /><label htmlFor="github-url">IMPORT A PUBLIC GITHUB REPOSITORY</label></div><div className="github-form-row"><input id="github-url" type="url" placeholder="https://github.com/owner/repository" value={githubUrl} onChange={(event) => setGithubUrl(event.target.value)} disabled={importing || busy} required /><button type="submit" disabled={!githubUrl.trim() || importing || busy}>{importing ? <LoaderCircle size={15} className="spin" /> : <Upload size={15} />}{importing ? "Importing…" : "Import"}</button></div><small>Python source only · public repositories · up to 50 files / 200 KB</small></form>
            <div className="editor">
              <div className="file-tabs" role="tablist" aria-label="Python source files">{fileNames.map((path) => <button key={path} role="tab" aria-selected={activeFile === path} disabled={busy || importing} className={activeFile === path ? "file-tab active" : "file-tab"} onClick={() => setWorkspace((current) => ({ ...current, active: path }))}><FileCode2 size={13} />{path}</button>)}<button className="add-file" aria-label="Add Python file" disabled={busy || importing} onClick={() => setShowNewFile((visible) => !visible)}><Plus size={15} /></button></div>
              {showNewFile && <form className="add-row" onSubmit={addFile}><input autoFocus aria-label="New Python filename" placeholder="src/helpers.py" value={newFile} onChange={(event) => setNewFile(event.target.value)} /><button type="submit">Add file</button></form>}
              {activeFile ? <div className="editor-body"><div className="line-numbers" aria-hidden="true">{(workspace.files[activeFile] || "").split("\n").map((_, index) => <span key={index}>{index + 1}</span>)}</div><textarea className="code-input" aria-label={`Edit ${activeFile}`} spellCheck={false} disabled={busy || importing} value={workspace.files[activeFile] || ""} placeholder="# Write or review Python code here" onChange={(event) => updateWorkspace({ files: { ...workspace.files, [activeFile]: event.target.value } })} /></div> : <div className="empty-editor">Create a Python file or import a public GitHub repository to begin.</div>}
              <div className="editor-footer"><span><i className="python-dot" /> Python</span><span>UTF-8 <b>·</b> Saved in this browser</span></div>
            </div>
            <div className="task-input"><label htmlFor="task"><Sparkles size={14} /> TASK FOR OPENROUTER</label><textarea id="task" value={workspace.task} maxLength={8000} placeholder="Paste the traceback, describe expected behavior, and note the smallest acceptable fix…" disabled={busy} onChange={(event) => updateWorkspace({ task: event.target.value })} /><div className="run-row"><button className="run-button" onClick={runAgent} disabled={!canRun}>{busy ? <LoaderCircle className="spin" size={15} /> : <Terminal size={15} />}{busy ? "Working…" : config?.hosted ? "Request proposal" : "Run repair"}<ArrowRight size={14} /></button></div><p className="run-help">Add failing pytest cases under <code>tests/</code>. Your task, source files, and test output are sent to OpenRouter free-model providers; remove secrets. {config?.hosted ? "Hosted mode generates a proposal only; review and verify it locally." : !config?.execution_enabled && "Enable the local runner in the server environment before running trusted source."}</p></div>
          </section>

          <section className="panel observer-panel">
            <div className="panel-title"><div><Activity size={16} /> Verification status</div><span className={`status-badge ${busy ? "running" : result?.accepted ? "success" : ""}`}>{busy ? "RUNNING" : result?.accepted ? "VERIFIED" : completed ? "COMPLETE" : "READY"}</span></div>
            <div className="observer-heading"><div className="observer-orb"><ShieldCheck size={24} /></div><div><h2>{result?.accepted ? "A safer change, verified." : busy ? "Reviewing a candidate." : "Evidence before acceptance."}</h2><p>{result?.accepted ? "Previously passing tests stayed passing." : busy ? "Watch each verification step." : "AI proposes. Tests control what changes."}</p></div></div>
            <div className="metrics"><div><span>{evidenceMode === "static" ? "SYNTAX OK" : "PASSING"}</span><strong className={passed !== undefined ? "lime" : ""}>{passed ?? "—"}</strong></div><div><span>{evidenceMode === "static" ? "SYNTAX ERRORS" : "FAILING"}</span><strong className={failed ? "red" : ""}>{failed ?? "—"}</strong></div><div><span>REGRESSIONS</span><strong>{result ? result.regressions.length : "—"}</strong></div></div>
            <div className="timeline-label"><span>RUN TIMELINE</span><span>{attempts.length} / 3 attempts</span></div>
            <div className="timeline" aria-live="polite">{timeline.length ? timeline.map((item, index) => <div className={`timeline-entry ${item.state}`} key={`${item.title}-${index}`}><span className="timeline-dot">{item.state === "working" ? <LoaderCircle className="spin" size={13} /> : item.state === "ok" ? <Check size={13} /> : <X size={13} />}</span><div><h3>{item.title}</h3><p>{item.detail}</p></div></div>) : <><div className="timeline-entry"><span className="timeline-dot"><Circle size={11} /></span><div><h3>Workspace ready</h3><p>Add source and tests, connect OpenRouter, then review the safety settings.</p></div></div><div className="empty-terminal"><span>›</span> waiting for a verified run<div>Test evidence appears here.</div></div></>}</div>
            <div className="gate-note"><ShieldCheck size={16} /><span>Only changes with fewer failures and no lost passing tests are kept.</span></div>
          </section>
        </div>

        {(error || notice) && <div className={error ? "message error-banner" : "message notice-banner"} role={error ? "alert" : "status"}>{error ? <X size={16} /> : <Check size={16} />}{error || notice}<button onClick={() => { setError(""); setNotice(""); }} aria-label="Dismiss message"><X size={14} /></button></div>}

        <section className="panel evidence" id="evidence"><div className="panel-title"><div><Activity size={16} /> Verification evidence <span className="subtle-pill">{result ? `${result.files_changed.length} changed` : "Awaiting a run"}</span></div><div className="evidence-actions"><button disabled={busy} onClick={newProject}><Plus size={13} /><span>New project</span></button><button disabled={!completed || !before || busy} onClick={downloadReport}><ArrowDownToLine size={14} /><span>Export report</span></button></div></div>
          <div className="evidence-tabs">{(["diff", "explanation", "logs"] as const).map((item) => <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item === "diff" ? "Code diff" : item === "explanation" ? "Explanation" : "Test output"}</button>)}<span>{result?.accepted ? "Change accepted" : result ? "Candidate discarded" : "No candidate verified"}</span></div>
          {tab === "diff" ? result?.diff ? <pre className="diff">{result.diff}</pre> : <div className="evidence-empty"><div className="diff-symbol">±</div><div><h3>Every accepted edit is reviewable.</h3><p>Run a trusted local project to see its code diff and verification outcome.</p></div></div> : tab === "explanation" ? <div className="explanation"><h3>{proposal ? "OpenRouter's explanation" : "Root cause and decision"}</h3><p>{proposal?.explanation || "The proposal explanation and verification decision will appear here."}</p>{result && <p className="muted">{result.reason}</p>}</div> : <pre className="logs">{result?.after.output || before?.output || "No test output yet."}</pre>}
        </section>
        <footer><span><ShieldCheck size={13} /> Built to verify. Designed to explain.</span><span>Python + pytest <ArrowRight size={12} /></span></footer>
      </main>
    </div>
  </div>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
