import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

const scenarios = [
  {
    value: "database_connection_saturation",
    label: "Database saturation",
    summary: "Connection pool exhaustion with queue pressure.",
  },
  {
    value: "network_dns_failure",
    label: "Network / DNS failure",
    summary: "Upstream timeout and DNS lookup failures.",
  },
  {
    value: "infrastructure_resource_exhaustion",
    label: "Infrastructure exhaustion",
    summary: "Memory pressure, OOM eviction, and throttling.",
  },
  {
    value: "application_bad_deploy",
    label: "Application bad deploy",
    summary: "Deployment introduced a crashing checkout route.",
  },
];

const defaultLogs = `2026-04-12T10:05:00Z ERROR upstream timeout contacting payments-api
2026-04-12T10:05:01Z ERROR dns lookup failed for payments-api.internal
2026-04-12T10:05:02Z WARN retry budget exhausted`;

function formatStatus(value) {
  return String(value ?? "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function StatCard({ label, value, tone = "neutral" }) {
  return (
    <div className={`stat-card stat-card--${tone}`}>
      <span className="stat-card__label">{label}</span>
      <strong className="stat-card__value">{value}</strong>
    </div>
  );
}

function Timeline({ history }) {
  if (!history?.length) {
    return <div className="empty-state">No workflow history yet.</div>;
  }

  return (
    <div className="timeline">
      {history.map((entry, index) => (
        <article className="timeline__item" key={`${entry.timestamp}-${index}`}>
          <div className="timeline__meta">
            <span>{entry.node}</span>
            <span>{entry.decision}</span>
          </div>
          <p>{entry.summary}</p>
        </article>
      ))}
    </div>
  );
}

function JsonPanel({ title, value }) {
  return (
    <section className="panel">
      <div className="panel__header">
        <h3>{title}</h3>
      </div>
      <pre className="code-block">{JSON.stringify(value, null, 2)}</pre>
    </section>
  );
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }
  return payload;
}

export default function App() {
  const [mode, setMode] = useState("simulate");
  const [scenarioName, setScenarioName] = useState(scenarios[0].value);
  const [logs, setLogs] = useState(defaultLogs);
  const [approvalRequired, setApprovalRequired] = useState(true);
  const [autoApprove, setAutoApprove] = useState(true);
  const [incidentIdInput, setIncidentIdInput] = useState("");
  const [response, setResponse] = useState(null);
  const [diagram, setDiagram] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadingIncident, setLoadingIncident] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    apiRequest("/workflow/diagram")
      .then((payload) => {
        if (active) {
          setDiagram(payload.mermaid ?? "");
        }
      })
      .catch(() => {
        if (active) {
          setDiagram("Workflow diagram unavailable.");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const state = response?.state;
  const report = response?.report;
  const waitingForApproval =
    state?.approval_required && state?.approved !== true && state?.execution_status === "pending";

  async function handleRun(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");

    try {
      const payload =
        mode === "simulate"
          ? {
              scenario_name: scenarioName,
              approval_required: approvalRequired,
              approved: approvalRequired ? (autoApprove ? true : null) : true,
            }
          : {
              logs,
              approval_required: approvalRequired,
              approved: approvalRequired ? (autoApprove ? true : null) : true,
            };

      const nextResponse = await apiRequest(mode === "simulate" ? "/simulate" : "/analyze", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setResponse(nextResponse);
      setIncidentIdInput(nextResponse.incident_id ?? "");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleApprove(approved) {
    if (!response?.incident_id) {
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      const nextResponse = await apiRequest(`/incidents/${response.incident_id}/approve`, {
        method: "POST",
        body: JSON.stringify({ approved }),
      });
      setResponse(nextResponse);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLoadIncident(event) {
    event.preventDefault();
    if (!incidentIdInput.trim()) {
      return;
    }

    setLoadingIncident(true);
    setError("");

    try {
      const nextResponse = await apiRequest(`/incidents/${incidentIdInput.trim()}`);
      setResponse(nextResponse);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoadingIncident(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero__copy">
          <span className="eyebrow">Self-Healing AI Agent</span>
          <h1>Minimal incident console for simulation, diagnosis, and approval.</h1>
          <p>
            Run the LangGraph workflow against sample incidents or paste real logs, inspect the
            decision path, and approve safe remediation without leaving the page.
          </p>
        </div>
        <div className="hero__status">
          <StatCard label="API Base" value={API_BASE.replace("http://", "")} />
          <StatCard
            label="Current Mode"
            value={mode === "simulate" ? "Simulation" : "Log Analysis"}
            tone="accent"
          />
        </div>
      </header>

      <main className="workspace">
        <section className="panel panel--form">
          <div className="panel__header">
            <h2>Run Workflow</h2>
            <div className="segmented">
              <button
                className={mode === "simulate" ? "is-active" : ""}
                type="button"
                onClick={() => setMode("simulate")}
              >
                Simulate
              </button>
              <button
                className={mode === "analyze" ? "is-active" : ""}
                type="button"
                onClick={() => setMode("analyze")}
              >
                Analyze Logs
              </button>
            </div>
          </div>

          <form className="form-grid" onSubmit={handleRun}>
            {mode === "simulate" ? (
              <label className="field">
                <span>Scenario</span>
                <select value={scenarioName} onChange={(event) => setScenarioName(event.target.value)}>
                  {scenarios.map((scenario) => (
                    <option key={scenario.value} value={scenario.value}>
                      {scenario.label}
                    </option>
                  ))}
                </select>
                <small>
                  {scenarios.find((scenario) => scenario.value === scenarioName)?.summary}
                </small>
              </label>
            ) : (
              <label className="field field--full">
                <span>Logs</span>
                <textarea
                  rows="8"
                  value={logs}
                  onChange={(event) => setLogs(event.target.value)}
                  placeholder="Paste structured or raw logs here"
                />
              </label>
            )}

            <div className="form-grid form-grid--compact">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={approvalRequired}
                  onChange={(event) => setApprovalRequired(event.target.checked)}
                />
                <span>Require approval before execution</span>
              </label>

              <label className="toggle">
                <input
                  type="checkbox"
                  checked={autoApprove}
                  onChange={(event) => setAutoApprove(event.target.checked)}
                  disabled={!approvalRequired}
                />
                <span>Auto-approve while testing</span>
              </label>
            </div>

            <button className="primary-button" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Running..." : mode === "simulate" ? "Run Simulation" : "Analyze Incident"}
            </button>
          </form>

          {error ? <div className="error-banner">{error}</div> : null}
        </section>

        <section className="panel panel--lookup">
          <div className="panel__header">
            <h2>Load Existing Incident</h2>
          </div>
          <form className="lookup-form" onSubmit={handleLoadIncident}>
            <input
              value={incidentIdInput}
              onChange={(event) => setIncidentIdInput(event.target.value)}
              placeholder="Paste an incident_id"
            />
            <button type="submit" disabled={loadingIncident}>
              {loadingIncident ? "Loading..." : "Load"}
            </button>
          </form>
        </section>

        <section className="results-grid">
          <section className="panel">
            <div className="panel__header">
              <h2>Incident Snapshot</h2>
            </div>
            {state ? (
              <>
                <div className="stats-grid">
                  <StatCard label="Incident ID" value={state.incident_id?.slice(0, 8) ?? "N/A"} />
                  <StatCard label="Issue Type" value={formatStatus(state.issue_type)} tone="accent" />
                  <StatCard
                    label="Validation"
                    value={formatStatus(state.validation_status)}
                    tone={state.validation_status === "resolved" ? "success" : "neutral"}
                  />
                  <StatCard label="Retries" value={String(state.retry_count ?? 0)} />
                </div>

                <div className="summary-stack">
                  <div>
                    <span className="summary-label">Root cause</span>
                    <p>{state.root_cause || "Waiting for diagnosis."}</p>
                  </div>
                  <div>
                    <span className="summary-label">Suggested fix</span>
                    <p>{state.suggested_fix || "No recommendation yet."}</p>
                  </div>
                  <div>
                    <span className="summary-label">Validation note</span>
                    <p>{state.validation_reason || "Validation has not completed yet."}</p>
                  </div>
                </div>

                {waitingForApproval ? (
                  <div className="approval-box">
                    <div>
                      <span className="summary-label">Approval required</span>
                      <p>The workflow is paused before executing the whitelisted fix.</p>
                    </div>
                    <div className="button-row">
                      <button className="primary-button" onClick={() => handleApprove(true)} type="button">
                        Approve and continue
                      </button>
                      <button className="ghost-button" onClick={() => handleApprove(false)} type="button">
                        Reject
                      </button>
                    </div>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                Run a simulation or analyze logs to see the workflow state here.
              </div>
            )}
          </section>

          <section className="panel">
            <div className="panel__header">
              <h2>Workflow History</h2>
            </div>
            <Timeline history={state?.history} />
          </section>

          <section className="panel panel--wide">
            <div className="panel__header">
              <h2>Workflow Diagram</h2>
            </div>
            <pre className="diagram-block">{diagram}</pre>
          </section>

          <JsonPanel title="Final Report" value={report ?? {}} />
          <JsonPanel title="Raw State" value={state ?? {}} />
        </section>
      </main>
    </div>
  );
}
