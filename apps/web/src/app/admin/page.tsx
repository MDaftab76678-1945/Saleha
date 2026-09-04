"use client";

import React, { useCallback, useEffect, useState } from "react";
import { THEME_PRESETS, ThemeTokens } from "@saleha/ui";
import {
  AccountUser,
  ApiError,
  DEFAULT_BASE_URL,
  apiGet,
  checkHealth,
  getStoredToken,
  login as apiLogin,
  logout as apiLogout,
  storeToken,
} from "../../lib/api";

type TabId = "overview" | "runs" | "audit" | "history" | "models";

interface FileInfo {
  path: string;
  exists: boolean;
  size_bytes: number;
  modified_at: number | null;
}

interface RunsPayload {
  summary: {
    total_runs?: number;
    successful_runs?: number;
    failed_runs?: number;
    success_rate?: number;
    avg_attempts?: number;
    avg_duration_sec?: number;
    by_model?: Record<string, { runs: number; wins: number }>;
  };
  summary_scope: string;
  recent: Array<Record<string, unknown>>;
  sources: Record<string, FileInfo>;
}

interface AuditPayload {
  recent: Array<{
    timestamp?: string;
    code_preview?: string;
    allowed?: boolean;
    reason?: string;
    executed?: boolean;
    success?: boolean;
    exit_code?: number;
  }>;
  blocked_count: number;
  blocked_recent: Array<{ timestamp?: string; code_preview?: string; reason?: string }>;
  sources: Record<string, FileInfo>;
}

interface HistoryPayload {
  recent: Array<{
    timestamp?: string;
    goal?: string;
    model?: string;
    success?: boolean;
    attempts?: number;
    error?: string;
  }>;
  failed_count: number;
  failed_recent: Array<{ timestamp?: string; goal?: string; error?: string }>;
  sources: Record<string, FileInfo>;
}

interface ModelsPayload {
  task_types: Array<{
    task_type: string;
    best_model: string | null;
    models: Array<{
      model: string;
      uses: number;
      successes: number;
      success_rate: number;
      avg_attempts: number;
      last_used: string | null;
    }>;
  }>;
  unavailable_reason?: string;
  sources: Record<string, FileInfo>;
}

interface OverviewPayload {
  version: string;
  approval_mode: string | null;
  sections: {
    runs?: RunsPayload;
    audit?: AuditPayload;
    history?: HistoryPayload;
  };
  errors: Record<string, string>;
  excluded_sources: Array<{ name: string; reason: string }>;
}

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "runs", label: "Runs" },
  { id: "audit", label: "Execution audit" },
  { id: "history", label: "Task history" },
  { id: "models", label: "Models" },
];

function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, exponent)).toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

function truncate(value: unknown, max = 110): string {
  const text = typeof value === "string" ? value : JSON.stringify(value ?? "");
  const collapsed = text.replace(/\s+/g, " ").trim();
  return collapsed.length > max ? `${collapsed.slice(0, max)}…` : collapsed;
}

export default function AdminPage() {
  const theme: ThemeTokens = THEME_PRESETS.obsidian;

  const [tab, setTab] = useState<TabId>("overview");
  const [token, setToken] = useState("");
  const [tokenDraft, setTokenDraft] = useState("");
  const [needsToken, setNeedsToken] = useState(false);
  const [serverUp, setServerUp] = useState<boolean | null>(null);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [account, setAccount] = useState<AccountUser | null>(null);
  const [signingIn, setSigningIn] = useState(false);
  const [signInError, setSignInError] = useState("");
  const [useSharedToken, setUseSharedToken] = useState(false);

  const [overview, setOverview] = useState<OverviewPayload | null>(null);
  const [runs, setRuns] = useState<RunsPayload | null>(null);
  const [audit, setAudit] = useState<AuditPayload | null>(null);
  const [history, setHistory] = useState<HistoryPayload | null>(null);
  const [models, setModels] = useState<ModelsPayload | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const stored = getStoredToken();
    setToken(stored);
    setNeedsToken(!stored);
  }, []);

  const load = useCallback(
    async (which: TabId, activeToken: string) => {
      setLoading(true);
      setError("");
      try {
        const health = await checkHealth();
        setServerUp(Boolean(health));
        if (!health) {
          setError(`No backend responding at ${DEFAULT_BASE_URL}. Start it with: saleha serve`);
          return;
        }

        if (which === "overview") setOverview(await apiGet<OverviewPayload>("/api/admin/overview", { token: activeToken }));
        if (which === "runs") setRuns(await apiGet<RunsPayload>("/api/admin/runs?limit=25", { token: activeToken }));
        if (which === "audit") setAudit(await apiGet<AuditPayload>("/api/admin/audit?limit=25", { token: activeToken }));
        if (which === "history") setHistory(await apiGet<HistoryPayload>("/api/admin/history?limit=25", { token: activeToken }));
        if (which === "models") setModels(await apiGet<ModelsPayload>("/api/admin/models", { token: activeToken }));
        setNeedsToken(false);
      } catch (err) {
        const apiError = err as ApiError;
        if (apiError.status === 403) {
          // Signed in, but without the admin role. Prompting for credentials
          // again would imply the sign-in failed, which it did not.
          setError(
            "This account is not an admin, so operational data is refused. Ask an admin to grant the role, or sign in as one."
          );
        } else {
          setError(apiError.message || "Request failed.");
          if (apiError.isAuthError) setNeedsToken(true);
        }
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (!token) return;
    void load(tab, token);
  }, [tab, token, load]);

  const submitToken = () => {
    const next = tokenDraft.trim();
    if (!next) return;
    storeToken(next);
    setToken(next);
    setTokenDraft("");
    setNeedsToken(false);
  };

  const submitSignIn = async () => {
    if (!username.trim() || !password) return;
    setSigningIn(true);
    setSignInError("");
    try {
      const result = await apiLogin(username.trim(), password);
      storeToken(result.token);
      setAccount(result.user);
      setToken(result.token);
      setPassword("");
      setNeedsToken(false);
      if (result.user.role !== "admin") {
        setSignInError(
          "Signed in, but this account is not an admin, so the panel's data will be refused."
        );
      }
    } catch (err) {
      setSignInError((err as ApiError).message || "Sign in failed.");
    } finally {
      setSigningIn(false);
    }
  };

  const signOut = async () => {
    await apiLogout();
    setToken("");
    setAccount(null);
    setNeedsToken(true);
  };

  const s = styles(theme);

  return (
    <div style={s.page}>
      <header style={s.header}>
        <div>
          <h1 style={s.title}>Saleha Admin</h1>
          <p style={s.subtitle}>
            Operational data recorded by this installation. Every figure here is read from a file on
            disk; nothing is estimated.
          </p>
        </div>
        <div style={s.headerMeta}>
          <StatusDot theme={theme} up={serverUp} />
          <span style={s.metaText}>
            {serverUp === null ? "Checking backend…" : serverUp ? DEFAULT_BASE_URL : "Backend offline"}
          </span>
          {overview?.version && <span style={s.badge}>v{overview.version}</span>}
          {overview?.approval_mode && (
            <span style={s.badge}>approval: {overview.approval_mode}</span>
          )}
          {account && (
            <span style={s.badge}>
              {account.username} · {account.role}
            </span>
          )}
        </div>
      </header>

      {needsToken && (
        <section style={s.tokenPanel}>
          <h2 style={s.sectionTitle}>Sign in</h2>
          <p style={s.muted}>
            The admin panel needs an account with the admin role. Create the first one on the
            machine running the backend:{" "}
            <code style={s.code}>saleha user create &lt;name&gt; --admin</code>
          </p>

          {!useSharedToken ? (
            <>
              <div style={s.tokenRow}>
                <input
                  style={s.input}
                  value={username}
                  placeholder="Username"
                  autoComplete="username"
                  onChange={(e) => setUsername(e.target.value)}
                />
                <input
                  style={s.input}
                  type="password"
                  value={password}
                  placeholder="Password"
                  autoComplete="current-password"
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void submitSignIn();
                  }}
                />
                <button style={s.primaryButton} onClick={() => void submitSignIn()} disabled={signingIn}>
                  {signingIn ? "Signing in…" : "Sign in"}
                </button>
              </div>
              <button style={s.linkButton} onClick={() => setUseSharedToken(true)}>
                Use the server&apos;s launch token instead
              </button>
            </>
          ) : (
            <>
              <p style={s.muted}>
                The backend prints a shared token when it starts, and regenerates it each launch
                unless <code style={s.code}>SALEHA_STUDIO_TOKEN</code> is set. It grants admin
                access, so treat it as a break-glass credential rather than a everyday login.
              </p>
              <div style={s.tokenRow}>
                <input
                  style={s.input}
                  type="password"
                  value={tokenDraft}
                  placeholder="Paste the launch token"
                  onChange={(e) => setTokenDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") submitToken();
                  }}
                />
                <button style={s.primaryButton} onClick={submitToken}>
                  Connect
                </button>
              </div>
              <button style={s.linkButton} onClick={() => setUseSharedToken(false)}>
                Back to signing in with an account
              </button>
            </>
          )}

          {signInError && <div style={s.signInError}>{signInError}</div>}
        </section>
      )}

      <nav style={s.tabs}>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={tab === t.id ? s.tabActive : s.tab}
          >
            {t.label}
          </button>
        ))}
        <span style={s.spacer} />
        <button style={s.ghostButton} onClick={() => token && load(tab, token)} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
        {token && (
          <button style={s.ghostButton} onClick={() => void signOut()}>
            Sign out
          </button>
        )}
      </nav>

      {error && <div style={s.errorBar}>{error}</div>}

      <main style={s.main}>
        {tab === "overview" && <OverviewTab data={overview} theme={theme} />}
        {tab === "runs" && <RunsTab data={runs} theme={theme} />}
        {tab === "audit" && <AuditTab data={audit} theme={theme} />}
        {tab === "history" && <HistoryTab data={history} theme={theme} />}
        {tab === "models" && <ModelsTab data={models} theme={theme} />}
      </main>
    </div>
  );
}

function StatusDot({ theme, up }: { theme: ThemeTokens; up: boolean | null }) {
  const color = up === null ? theme.textDim : up ? theme.accentGreen : theme.accentRed;
  return (
    <span
      aria-hidden
      style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }}
    />
  );
}

function Stat({
  theme,
  label,
  value,
  hint,
}: {
  theme: ThemeTokens;
  label: string;
  value: string;
  hint?: string;
}) {
  const s = styles(theme);
  return (
    <div style={s.statCard}>
      <div style={s.statLabel}>{label}</div>
      <div style={s.statValue}>{value}</div>
      {hint && <div style={s.statHint}>{hint}</div>}
    </div>
  );
}

function EmptyState({ theme, message }: { theme: ThemeTokens; message: string }) {
  const s = styles(theme);
  return <div style={s.empty}>{message}</div>;
}

function SourceNote({ theme, sources }: { theme: ThemeTokens; sources?: Record<string, FileInfo> }) {
  const s = styles(theme);
  if (!sources) return null;
  return (
    <div style={s.sourceNote}>
      {Object.entries(sources).map(([name, info]) => (
        <span key={name}>
          {name}: {info.exists ? `${info.path} (${formatBytes(info.size_bytes)})` : `${info.path} — not created yet`}
        </span>
      ))}
    </div>
  );
}

function OverviewTab({ data, theme }: { data: OverviewPayload | null; theme: ThemeTokens }) {
  const s = styles(theme);
  if (!data) return <EmptyState theme={theme} message="Connect to the backend to load data." />;

  const runsSummary = data.sections.runs?.summary;
  const hasRuns = typeof runsSummary?.total_runs === "number" && runsSummary.total_runs > 0;

  return (
    <>
      <div style={s.statGrid}>
        <Stat
          theme={theme}
          label="Recorded runs"
          value={hasRuns ? String(runsSummary?.total_runs) : "No data yet"}
          hint={hasRuns ? "Most recent 10,000 runs" : "Nothing has been recorded"}
        />
        <Stat
          theme={theme}
          label="Success rate"
          value={hasRuns ? `${runsSummary?.success_rate ?? 0}%` : "—"}
          hint={hasRuns ? `${runsSummary?.failed_runs ?? 0} failed` : undefined}
        />
        <Stat
          theme={theme}
          label="Blocked executions"
          value={
            data.sections.audit ? String(data.sections.audit.blocked_count) : "—"
          }
          hint="Code the executor refused to run"
        />
        <Stat
          theme={theme}
          label="Failed tasks"
          value={data.sections.history ? String(data.sections.history.failed_count) : "—"}
          hint="Across all recorded history"
        />
      </div>

      {Object.keys(data.errors).length > 0 && (
        <section style={s.card}>
          <h2 style={s.sectionTitle}>Sections that failed to load</h2>
          {Object.entries(data.errors).map(([name, message]) => (
            <div key={name} style={s.errorRow}>
              <strong>{name}</strong>: {message}
            </div>
          ))}
        </section>
      )}

      <section style={s.card}>
        <h2 style={s.sectionTitle}>Deliberately not shown</h2>
        <p style={s.muted}>
          These sources exist in the codebase and look like telemetry, but do not measure anything
          real, so this panel omits them rather than displaying invented numbers.
        </p>
        {data.excluded_sources.map((item) => (
          <div key={item.name} style={s.excludedRow}>
            <code style={s.code}>{item.name}</code>
            <span style={s.muted}>{item.reason}</span>
          </div>
        ))}
      </section>
    </>
  );
}

function RunsTab({ data, theme }: { data: RunsPayload | null; theme: ThemeTokens }) {
  const s = styles(theme);
  if (!data) return <EmptyState theme={theme} message="No run data loaded." />;
  const byModel = Object.entries(data.summary.by_model ?? {});

  return (
    <>
      <div style={s.statGrid}>
        <Stat theme={theme} label="Total runs" value={String(data.summary.total_runs ?? 0)} />
        <Stat theme={theme} label="Successful" value={String(data.summary.successful_runs ?? 0)} />
        <Stat theme={theme} label="Failed" value={String(data.summary.failed_runs ?? 0)} />
        <Stat
          theme={theme}
          label="Avg duration"
          value={`${data.summary.avg_duration_sec ?? 0}s`}
          hint={`avg ${data.summary.avg_attempts ?? 0} attempts`}
        />
      </div>
      <p style={s.scopeNote}>{data.summary_scope}</p>

      <section style={s.card}>
        <h2 style={s.sectionTitle}>By model</h2>
        {byModel.length === 0 ? (
          <EmptyState theme={theme} message="No per-model runs recorded." />
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Model</th>
                <th style={s.th}>Runs</th>
                <th style={s.th}>Wins</th>
              </tr>
            </thead>
            <tbody>
              {byModel.map(([model, stats]) => (
                <tr key={model}>
                  <td style={s.td}>{model}</td>
                  <td style={s.td}>{stats.runs}</td>
                  <td style={s.td}>{stats.wins}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section style={s.card}>
        <h2 style={s.sectionTitle}>Most recent runs</h2>
        {data.recent.length === 0 ? (
          <EmptyState theme={theme} message="No runs recorded yet." />
        ) : (
          <div style={s.logList}>
            {data.recent.map((entry, index) => (
              <div key={index} style={s.logRow}>
                {truncate(entry, 200)}
              </div>
            ))}
          </div>
        )}
        <SourceNote theme={theme} sources={data.sources} />
      </section>
    </>
  );
}

function AuditTab({ data, theme }: { data: AuditPayload | null; theme: ThemeTokens }) {
  const s = styles(theme);
  if (!data) return <EmptyState theme={theme} message="No audit data loaded." />;

  return (
    <>
      <div style={s.statGrid}>
        <Stat
          theme={theme}
          label="Blocked executions"
          value={String(data.blocked_count)}
          hint="Whole log, not just recent"
        />
        <Stat theme={theme} label="Recent attempts shown" value={String(data.recent.length)} />
      </div>

      <section style={s.card}>
        <h2 style={s.sectionTitle}>Recent blocked attempts</h2>
        <p style={s.muted}>
          The approval gate and safety guard return their verdicts without persisting them, so this
          log is the only record of what was refused.
        </p>
        {data.blocked_recent.length === 0 ? (
          <EmptyState theme={theme} message="Nothing has been blocked." />
        ) : (
          <div style={s.logList}>
            {data.blocked_recent.map((entry, index) => (
              <div key={index} style={{ ...s.logRow, borderLeft: `2px solid ${theme.accentRed}` }}>
                <span style={s.logTime}>{entry.timestamp ?? "—"}</span>
                <span style={s.logReason}>{entry.reason ?? "no reason recorded"}</span>
                <span>{truncate(entry.code_preview, 140)}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section style={s.card}>
        <h2 style={s.sectionTitle}>Recent execution attempts</h2>
        {data.recent.length === 0 ? (
          <EmptyState theme={theme} message="No execution attempts recorded." />
        ) : (
          <div style={s.logList}>
            {data.recent.map((entry, index) => (
              <div
                key={index}
                style={{
                  ...s.logRow,
                  borderLeft: `2px solid ${entry.allowed ? theme.accentGreen : theme.accentRed}`,
                }}
              >
                <span style={s.logTime}>{entry.timestamp ?? "—"}</span>
                <span style={s.logReason}>
                  {entry.allowed ? "allowed" : "blocked"}
                  {entry.executed ? ` · exit ${entry.exit_code ?? "?"}` : ""}
                </span>
                <span>{truncate(entry.code_preview, 140)}</span>
              </div>
            ))}
          </div>
        )}
        <SourceNote theme={theme} sources={data.sources} />
      </section>
    </>
  );
}

function HistoryTab({ data, theme }: { data: HistoryPayload | null; theme: ThemeTokens }) {
  const s = styles(theme);
  if (!data) return <EmptyState theme={theme} message="No history loaded." />;

  return (
    <>
      <div style={s.statGrid}>
        <Stat theme={theme} label="Failed tasks" value={String(data.failed_count)} />
        <Stat theme={theme} label="Recent shown" value={String(data.recent.length)} />
      </div>

      <section style={s.card}>
        <h2 style={s.sectionTitle}>Recent tasks</h2>
        {data.recent.length === 0 ? (
          <EmptyState theme={theme} message="No tasks recorded yet." />
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>When</th>
                <th style={s.th}>Goal</th>
                <th style={s.th}>Model</th>
                <th style={s.th}>Result</th>
              </tr>
            </thead>
            <tbody>
              {data.recent.map((row, index) => (
                <tr key={index}>
                  <td style={s.td}>{row.timestamp ?? "—"}</td>
                  <td style={s.td}>{truncate(row.goal, 90)}</td>
                  <td style={s.td}>{row.model ?? "—"}</td>
                  <td style={{ ...s.td, color: row.success ? theme.accentGreen : theme.accentRed }}>
                    {row.success ? "success" : "failed"}
                    {typeof row.attempts === "number" ? ` (${row.attempts})` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <SourceNote theme={theme} sources={data.sources} />
      </section>

      <section style={s.card}>
        <h2 style={s.sectionTitle}>Recent failures</h2>
        {data.failed_recent.length === 0 ? (
          <EmptyState theme={theme} message="No failures recorded." />
        ) : (
          <div style={s.logList}>
            {data.failed_recent.map((row, index) => (
              <div key={index} style={{ ...s.logRow, borderLeft: `2px solid ${theme.accentRed}` }}>
                <span style={s.logTime}>{row.timestamp ?? "—"}</span>
                <span>{truncate(row.goal, 90)}</span>
                <span style={s.logReason}>{truncate(row.error, 120)}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function ModelsTab({ data, theme }: { data: ModelsPayload | null; theme: ThemeTokens }) {
  const s = styles(theme);
  if (!data) return <EmptyState theme={theme} message="No model data loaded." />;
  if (data.unavailable_reason) {
    return <EmptyState theme={theme} message={data.unavailable_reason} />;
  }

  return (
    <>
      {data.task_types.length === 0 && (
        <EmptyState theme={theme} message="No model statistics have been recorded yet." />
      )}
      {data.task_types.map((bucket) => (
        <section key={bucket.task_type} style={s.card}>
          <h2 style={s.sectionTitle}>
            {bucket.task_type}
            {bucket.best_model && <span style={s.badge}>best: {bucket.best_model}</span>}
          </h2>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Model</th>
                <th style={s.th}>Uses</th>
                <th style={s.th}>Successes</th>
                <th style={s.th}>Success rate</th>
                <th style={s.th}>Avg attempts</th>
              </tr>
            </thead>
            <tbody>
              {bucket.models.map((row) => (
                <tr key={row.model}>
                  <td style={s.td}>{row.model}</td>
                  <td style={s.td}>{row.uses}</td>
                  <td style={s.td}>{row.successes}</td>
                  <td style={s.td}>{(row.success_rate * 100).toFixed(0)}%</td>
                  <td style={s.td}>{row.avg_attempts.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <SourceNote theme={theme} sources={data.sources} />
        </section>
      ))}
    </>
  );
}

function styles(theme: ThemeTokens): Record<string, React.CSSProperties> {
  return {
    page: {
      minHeight: "100vh",
      background: theme.bgBase,
      color: theme.textMain,
      fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
      padding: "2rem clamp(1rem, 4vw, 3rem)",
    },
    header: {
      display: "flex",
      flexWrap: "wrap",
      gap: "1rem",
      alignItems: "flex-start",
      justifyContent: "space-between",
      borderBottom: `1px solid ${theme.borderSubtle}`,
      paddingBottom: "1.25rem",
    },
    title: { margin: 0, fontSize: "1.6rem", color: theme.textBright, letterSpacing: "-0.02em" },
    subtitle: { margin: "0.4rem 0 0", color: theme.textDim, fontSize: "0.85rem", maxWidth: "52ch" },
    headerMeta: { display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap" },
    metaText: { color: theme.textDim, fontSize: "0.8rem" },
    badge: {
      background: theme.bgElevated,
      border: `1px solid ${theme.borderSubtle}`,
      borderRadius: 6,
      padding: "0.15rem 0.5rem",
      fontSize: "0.72rem",
      color: theme.textDim,
      marginLeft: "0.5rem",
    },
    tokenPanel: {
      marginTop: "1.5rem",
      padding: "1.1rem 1.25rem",
      background: theme.bgSurface,
      border: `1px solid ${theme.borderBright}`,
      borderRadius: 10,
    },
    tokenRow: { display: "flex", gap: "0.6rem", marginTop: "0.8rem", flexWrap: "wrap" },
    linkButton: {
      background: "none",
      border: "none",
      color: theme.accent,
      fontSize: "0.78rem",
      cursor: "pointer",
      padding: "0.6rem 0 0",
      textDecoration: "underline",
    },
    signInError: {
      marginTop: "0.8rem",
      color: theme.textMain,
      fontSize: "0.8rem",
      borderLeft: `3px solid ${theme.accentAmber}`,
      background: theme.bgElevated,
      borderRadius: 6,
      padding: "0.6rem 0.8rem",
    },
    input: {
      flex: "1 1 320px",
      background: theme.bgElevated,
      border: `1px solid ${theme.borderSubtle}`,
      borderRadius: 8,
      padding: "0.55rem 0.75rem",
      color: theme.textMain,
      fontSize: "0.85rem",
      outline: "none",
    },
    primaryButton: {
      background: theme.accent,
      color: "#04070d",
      border: "none",
      borderRadius: 8,
      padding: "0.55rem 1.1rem",
      fontWeight: 600,
      fontSize: "0.85rem",
      cursor: "pointer",
    },
    ghostButton: {
      background: "transparent",
      color: theme.textDim,
      border: `1px solid ${theme.borderSubtle}`,
      borderRadius: 8,
      padding: "0.4rem 0.8rem",
      fontSize: "0.78rem",
      cursor: "pointer",
    },
    tabs: {
      display: "flex",
      gap: "0.4rem",
      alignItems: "center",
      margin: "1.5rem 0 1rem",
      flexWrap: "wrap",
    },
    tab: {
      background: "transparent",
      color: theme.textDim,
      border: `1px solid ${theme.borderSubtle}`,
      borderRadius: 8,
      padding: "0.45rem 0.9rem",
      fontSize: "0.82rem",
      cursor: "pointer",
    },
    tabActive: {
      background: theme.bgElevated,
      color: theme.textBright,
      border: `1px solid ${theme.borderBright}`,
      borderRadius: 8,
      padding: "0.45rem 0.9rem",
      fontSize: "0.82rem",
      cursor: "pointer",
      fontWeight: 600,
    },
    spacer: { flex: 1 },
    errorBar: {
      background: theme.bgElevated,
      borderLeft: `3px solid ${theme.accentRed}`,
      borderRadius: 6,
      padding: "0.7rem 0.9rem",
      color: theme.textMain,
      fontSize: "0.82rem",
      marginBottom: "1rem",
    },
    main: { display: "flex", flexDirection: "column", gap: "1.25rem" },
    statGrid: {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
      gap: "0.9rem",
    },
    statCard: {
      background: theme.bgSurface,
      border: `1px solid ${theme.borderSubtle}`,
      borderRadius: 10,
      padding: "1rem 1.1rem",
    },
    statLabel: { color: theme.textDim, fontSize: "0.75rem", letterSpacing: "0.04em" },
    statValue: { color: theme.textBright, fontSize: "1.7rem", fontWeight: 700, marginTop: "0.3rem" },
    statHint: { color: theme.textDim, fontSize: "0.72rem", marginTop: "0.25rem" },
    scopeNote: { color: theme.textDim, fontSize: "0.75rem", margin: 0 },
    card: {
      background: theme.bgSurface,
      border: `1px solid ${theme.borderSubtle}`,
      borderRadius: 10,
      padding: "1.1rem 1.25rem",
    },
    sectionTitle: {
      margin: "0 0 0.7rem",
      fontSize: "0.95rem",
      color: theme.textBright,
      display: "flex",
      alignItems: "center",
    },
    muted: { color: theme.textDim, fontSize: "0.8rem", margin: "0 0 0.7rem", maxWidth: "72ch" },
    code: {
      background: theme.bgElevated,
      borderRadius: 4,
      padding: "0.1rem 0.35rem",
      fontSize: "0.78rem",
      fontFamily: "ui-monospace, monospace",
    },
    table: { width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" },
    th: {
      textAlign: "left",
      color: theme.textDim,
      fontWeight: 500,
      padding: "0.4rem 0.6rem 0.5rem 0",
      borderBottom: `1px solid ${theme.borderSubtle}`,
      fontSize: "0.75rem",
    },
    td: {
      padding: "0.45rem 0.6rem 0.45rem 0",
      borderBottom: `1px solid ${theme.borderSubtle}`,
      color: theme.textMain,
      verticalAlign: "top",
    },
    logList: { display: "flex", flexDirection: "column", gap: "0.4rem", overflowX: "auto" },
    logRow: {
      display: "flex",
      flexDirection: "column",
      gap: "0.15rem",
      background: theme.bgElevated,
      borderRadius: 6,
      padding: "0.5rem 0.7rem",
      fontSize: "0.78rem",
      fontFamily: "ui-monospace, monospace",
    },
    logTime: { color: theme.textDim, fontSize: "0.72rem" },
    logReason: { color: theme.accentAmber, fontSize: "0.75rem" },
    empty: {
      color: theme.textDim,
      fontSize: "0.82rem",
      padding: "1.2rem",
      textAlign: "center",
      border: `1px dashed ${theme.borderSubtle}`,
      borderRadius: 8,
    },
    sourceNote: {
      display: "flex",
      flexDirection: "column",
      gap: "0.2rem",
      marginTop: "0.8rem",
      color: theme.textDim,
      fontSize: "0.7rem",
      fontFamily: "ui-monospace, monospace",
      wordBreak: "break-all",
    },
    errorRow: { color: theme.textMain, fontSize: "0.8rem", marginBottom: "0.3rem" },
    excludedRow: {
      display: "flex",
      gap: "0.6rem",
      alignItems: "baseline",
      marginBottom: "0.4rem",
      flexWrap: "wrap",
    },
  };
}
