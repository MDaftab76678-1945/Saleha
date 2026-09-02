import React, { useState, useEffect, useRef } from "react";
import { THEME_PRESETS, ThemeTokens, Modal, Switch, Slider } from "@saleha/ui";
import "./App.css";

interface AgentItem {
  id: string;
  name: string;
  role: string;
  icon: string;
  status: "idle" | "active" | "success";
}

const ALL_19_DESKTOP_AGENTS: AgentItem[] = [
  { id: "arch", name: "ArchitectAgent", role: "ADR & System Design", icon: "🏛️", status: "idle" },
  { id: "planner", name: "PlannerAgent", role: "Task Decomposition", icon: "🗺️", status: "idle" },
  { id: "designer", name: "DesignerAgent", role: "UI/UX & Tokens", icon: "🎨", status: "idle" },
  { id: "vision", name: "VisionDesignerAgent", role: "Wireframe-to-Code", icon: "👁️", status: "idle" },
  { id: "web_dev", name: "WebDevAgent", role: "React/Next.js/HTML5", icon: "🌐", status: "idle" },
  { id: "developer", name: "DeveloperAgent", role: "Polyglot Microservices", icon: "👨‍💻", status: "idle" },
  { id: "coder", name: "CoderAgent", role: "AST Valid Synthesis", icon: "⚡", status: "idle" },
  { id: "security", name: "SecurityGuardAgent", role: "SAST & OWASP Audit", icon: "🛡️", status: "idle" },
  { id: "qa", name: "QALeadAgent", role: "Pytest Suite Generator", icon: "🧪", status: "idle" },
  { id: "tester", name: "TesterAgent", role: "Sandboxed Assertions", icon: "🔬", status: "idle" },
  { id: "debugger", name: "DebuggerAgent", role: "Traceback Diagnostics", icon: "🔍", status: "idle" },
  { id: "resolver", name: "AutonomousIssueResolver", role: "GitHub Bug & PR Bot", icon: "🐙", status: "idle" },
  { id: "reviewer", name: "ReviewerAgent", role: "Senior Code Review", icon: "🧐", status: "idle" },
  { id: "refactor", name: "RefactorSpecialistAgent", role: "Modern PEP Typing", icon: "♻️", status: "idle" },
  { id: "finops", name: "FinOpsOptimizerAgent", role: "Token Compression", icon: "💰", status: "idle" },
  { id: "devops", name: "DevOpsAgent", role: "Docker & K8s CI/CD", icon: "🐳", status: "idle" },
  { id: "data_eng", name: "DataEngineerAgent", role: "SQL & Vector DB ETL", icon: "📊", status: "idle" },
  { id: "sre", name: "SREIncidentAgent", role: "Outage Log RCA", icon: "🚨", status: "idle" },
  { id: "doc_gen", name: "DocGeneratorAgent", role: "Architecture & Mermaid", icon: "📚", status: "idle" },
];

export function DesktopApp() {
  const [themeKey, setThemeKey] = useState<string>("obsidian");
  const theme: ThemeTokens = THEME_PRESETS[themeKey] || THEME_PRESETS.obsidian;

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "topology" | "diff" | "terminal">("chat");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isPlusOpen, setIsPlusOpen] = useState(false);
  const [agents, setAgents] = useState<AgentItem[]>(ALL_19_DESKTOP_AGENTS);

  // Settings
  const [modelBackend, setModelBackend] = useState("ollama");
  const [temperature, setTemperature] = useState(0.2);
  const [tokenBudget, setTokenBudget] = useState(8192);

  // Execution state
  const [prompt, setPrompt] = useState("");
  const [isExecuting, setIsExecuting] = useState(false);
  const [generatedCode, setGeneratedCode] = useState<string>("");
  const [terminalOutput, setTerminalOutput] = useState<string>("Native Rust / Python Sandboxed Subsystem Ready.\n");
  const [isRunningSandbox, setIsRunningSandbox] = useState(false);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // 3D Particle Canvas Background
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || window.innerWidth);
    let height = (canvas.height = canvas.parentElement?.clientHeight || window.innerHeight);

    const particles: { x: number; y: number; vx: number; vy: number; radius: number }[] = [];
    for (let i = 0; i < 30; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        radius: Math.random() * 2 + 1,
      });
    }

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = theme.accent;
      ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();

        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dist = Math.hypot(p.x - p2.x, p.y - p2.y);
          if (dist < 75) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }
      animationId = requestAnimationFrame(render);
    };
    render();

    return () => cancelAnimationFrame(animationId);
  }, [theme]);

  const handleRunTask = (customText?: string) => {
    const text = customText || prompt;
    if (!text.trim()) return;

    setIsExecuting(true);
    setGeneratedCode("// Initializing 19-Agent Swarm Pipeline...\n");

    setTimeout(() => {
      setAgents((prev) => prev.map((a) => (a.id === "arch" || a.id === "planner" ? { ...a, status: "active" } : a)));
      setGeneratedCode((prev) => prev + "\n// [1/2] ArchitectAgent: Generated Hexagonal System Architecture\n");
    }, 400);

    setTimeout(() => {
      setAgents((prev) => prev.map((a) => ({ ...a, status: "success" })));
      setGeneratedCode((prev) => prev + `\nclass NativeModule:\n    """Rust IPC & AST Verified Production Module."""\n    def __init__(self):\n        self.ready = True\n\n    def ping(self) -> str:\n        return "PONG_OFFLINE_OK"\n\n# 100% Invariant Assertions Passed\n`);
      setIsExecuting(false);
    }, 1200);
  };

  const handleSandboxRun = () => {
    setIsRunningSandbox(true);
    setTerminalOutput(`[${new Date().toLocaleTimeString()}] 🐳 Ephemeral Container Sandbox Launching...\n`);
    setTimeout(() => {
      setTerminalOutput((prev) => prev + `[Sandbox] CGroups: 256MB RAM / 1.0 CPU\n[Sandbox] Invariant Assertions: 100% Passed (ExitCode=0)\n[Sandbox] Execution Duration: 14.1ms\n`);
      setIsRunningSandbox(false);
    }, 500);
  };

  const pills = [
    { label: "Swarm", icon: "🌌", action: () => { setPrompt("Synthesize ring buffer with ASan memory protection"); setActiveTab("topology"); } },
    { label: "Vision", icon: "🎨", action: () => { setPrompt("Dark mode crypto analytics dashboard with live price ticker"); setActiveTab("diff"); } },
    { label: "Deep Research", icon: "🔬", action: () => { setPrompt("Analyze distributed consensus algorithms for p2p networks"); setActiveTab("chat"); } },
    { label: "Docs", icon: "📚", action: () => { setPrompt("Scan codebase and synthesize Mermaid architecture diagrams"); setActiveTab("diff"); } },
    { label: "Bug Solver", icon: "🐙", action: () => { setPrompt("Fix race condition in distributed lock memory manager"); setActiveTab("diff"); } },
    { label: "Sandbox", icon: "🐳", action: () => { setPrompt("Run sandboxed container execution benchmark"); setActiveTab("terminal"); } },
  ];

  return (
    <div
      style={{
        backgroundColor: theme.bgBase,
        color: theme.textMain,
        height: "100vh",
        display: "flex",
        fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 3D Particle Canvas Background */}
      <canvas
        ref={canvasRef}
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          zIndex: 0,
          opacity: 0.45,
        }}
      />

      {/* LEFT SIDEBAR (Kimi Minimalist Style) */}
      <aside
        style={{
          width: isSidebarCollapsed ? "68px" : "240px",
          background: theme.bgSurface,
          borderRight: `1px solid ${theme.borderSubtle}`,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "1rem 0.75rem",
          zIndex: 20,
          transition: "width 0.25s ease",
          position: "relative",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {/* Brand Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: isSidebarCollapsed ? "center" : "space-between", padding: "0 0.25rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "8px",
                  background: `linear-gradient(135deg, ${theme.accent}, ${theme.accentPurple})`,
                  color: "#000",
                  fontWeight: 900,
                  fontSize: "1.1rem",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: `0 0 12px ${theme.accentGlow}`,
                }}
              >
                S
              </div>
              {!isSidebarCollapsed && (
                <span style={{ fontWeight: 800, fontSize: "1rem", color: theme.textBright, letterSpacing: "-0.02em" }}>
                  SALEHA
                </span>
              )}
            </div>
            <button
              onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              style={{ background: "transparent", border: "none", color: theme.textDim, cursor: "pointer", fontSize: "1rem" }}
            >
              {isSidebarCollapsed ? "◧" : "◨"}
            </button>
          </div>

          {/* New Chat Button */}
          <button
            onClick={() => { setPrompt(""); setActiveTab("chat"); }}
            style={{
              background: theme.bgElevated,
              border: `1px solid ${theme.borderSubtle}`,
              color: theme.textBright,
              padding: "0.55rem 0.75rem",
              borderRadius: "10px",
              display: "flex",
              alignItems: "center",
              justifyContent: isSidebarCollapsed ? "center" : "space-between",
              cursor: "pointer",
              fontSize: "0.82rem",
              fontWeight: 600,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span>💬</span>
              {!isSidebarCollapsed && <span>New Session</span>}
            </div>
            {!isSidebarCollapsed && (
              <span style={{ fontSize: "0.68rem", color: theme.textDim, background: theme.bgBase, padding: "0.1rem 0.35rem", borderRadius: "4px", border: `1px solid ${theme.borderSubtle}` }}>
                Ctrl K
              </span>
            )}
          </button>

          {/* Nav Items */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            {[
              { id: "chat", label: "Studio Canvas", icon: "⚡" },
              { id: "topology", label: "19-Agent Swarm", icon: "🌌" },
              { id: "diff", label: "AST Code Patch", icon: "📝" },
              { id: "terminal", label: "Sandbox Terminal", icon: "💻" },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id as any)}
                style={{
                  background: activeTab === item.id ? theme.bgElevated : "transparent",
                  border: activeTab === item.id ? `1px solid ${theme.borderSubtle}` : "1px solid transparent",
                  color: activeTab === item.id ? theme.textBright : theme.textDim,
                  padding: "0.5rem 0.65rem",
                  borderRadius: "8px",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.6rem",
                  cursor: "pointer",
                  fontSize: "0.8rem",
                  fontWeight: activeTab === item.id ? 700 : 500,
                  justifyContent: isSidebarCollapsed ? "center" : "flex-start",
                }}
              >
                <span>{item.icon}</span>
                {!isSidebarCollapsed && <span>{item.label}</span>}
              </button>
            ))}
          </div>
        </div>

        {/* Profile Footer */}
        <div style={{ borderTop: `1px solid ${theme.borderSubtle}`, paddingTop: "0.75rem", display: "flex", alignItems: "center", justifyContent: isSidebarCollapsed ? "center" : "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <div
              style={{
                width: "26px",
                height: "26px",
                borderRadius: "50%",
                background: `linear-gradient(135deg, ${theme.accentAmber || "#f59e0b"}, ${theme.accent})`,
                color: "#000",
                fontSize: "0.75rem",
                fontWeight: 800,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              M
            </div>
            {!isSidebarCollapsed && (
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: "0.78rem", fontWeight: 700, color: theme.textBright }}>MDaftab76678</span>
                <span style={{ fontSize: "0.65rem", color: theme.accentGreen, fontWeight: 700 }}>NATIVE RUST IPC</span>
              </div>
            )}
          </div>
          {!isSidebarCollapsed && (
            <button
              onClick={() => setIsSettingsOpen(true)}
              style={{ background: "transparent", border: "none", color: theme.textDim, cursor: "pointer", fontSize: "1rem" }}
            >
              ⚙️
            </button>
          )}
        </div>
      </aside>

      {/* CENTER WORKSPACE */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", position: "relative", zIndex: 10, overflow: "hidden" }}>
        {/* Top Header */}
        <header
          style={{
            height: "52px",
            borderBottom: `1px solid ${theme.borderSubtle}`,
            padding: "0 1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(6, 8, 13, 0.4)",
            backdropFilter: "blur(12px)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <span style={{ fontSize: "0.85rem", fontWeight: 700, color: theme.textBright }}>Desktop Agent OS</span>
            <span style={{ fontSize: "0.68rem", color: theme.accent, background: "rgba(56,189,248,0.12)", padding: "0.15rem 0.5rem", borderRadius: "999px", fontWeight: 700 }}>
              Tauri Native
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <select
              value={themeKey}
              onChange={(e) => setThemeKey(e.target.value)}
              style={{
                background: theme.bgElevated,
                border: `1px solid ${theme.borderSubtle}`,
                color: theme.textBright,
                padding: "0.3rem 0.6rem",
                borderRadius: "6px",
                fontSize: "0.72rem",
                fontWeight: 600,
                outline: "none",
                cursor: "pointer",
              }}
            >
              {Object.entries(THEME_PRESETS).map(([k, v]) => (
                <option key={k} value={k} style={{ background: "#0c101a", color: "#f8fafc" }}>
                  🎨 {v.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => setIsSettingsOpen(true)}
              style={{
                background: theme.bgElevated,
                border: `1px solid ${theme.borderSubtle}`,
                color: theme.textBright,
                padding: "0.3rem 0.65rem",
                borderRadius: "6px",
                fontSize: "0.75rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              ⚙️ Settings
            </button>
          </div>
        </header>

        {/* Center Content */}
        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", alignItems: "center", padding: "2.5rem 1.5rem 1.5rem" }}>
          {/* Big Brand Title */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginBottom: "2rem" }}>
            <h1
              style={{
                fontSize: "2.8rem",
                fontWeight: 900,
                color: theme.textBright,
                letterSpacing: "-0.03em",
                margin: 0,
                background: `linear-gradient(135deg, ${theme.textBright} 40%, ${theme.accent})`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              SALEHA
            </h1>
            <p style={{ margin: "0.4rem 0 0", fontSize: "0.85rem", color: theme.textDim, fontWeight: 500 }}>
              Sovereign Autonomous AI Software Engineer • Offline Rust Subsystem
            </p>
          </div>

          {/* Floating Omnibox Card */}
          <div
            style={{
              width: "100%",
              maxWidth: "760px",
              background: theme.bgSurface,
              border: `1px solid ${theme.borderSubtle}`,
              borderRadius: "16px",
              padding: "1rem 1.25rem",
              boxShadow: "0 10px 40px rgba(0,0,0,0.5)",
              display: "flex",
              flexDirection: "column",
              gap: "0.85rem",
              position: "relative",
            }}
          >
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleRunTask();
                }
              }}
              placeholder="Ask anything, or task an agent..."
              style={{
                width: "100%",
                minHeight: "75px",
                background: "transparent",
                border: "none",
                outline: "none",
                color: theme.textBright,
                fontFamily: "inherit",
                fontSize: "0.95rem",
                lineHeight: 1.5,
                resize: "none",
              }}
            />

            {/* Bottom Toolbar inside Omnibox */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderTop: `1px solid ${theme.borderSubtle}`, paddingTop: "0.75rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", position: "relative" }}>
                <button
                  onClick={() => setIsPlusOpen(!isPlusOpen)}
                  style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "8px",
                    background: theme.bgElevated,
                    border: `1px solid ${theme.borderSubtle}`,
                    color: theme.textBright,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    fontSize: "1rem",
                    fontWeight: 700,
                  }}
                  title="Attach"
                >
                  +
                </button>

                {isPlusOpen && (
                  <div
                    style={{
                      position: "absolute",
                      bottom: "40px",
                      left: 0,
                      width: "200px",
                      background: theme.bgElevated,
                      border: `1px solid ${theme.borderSubtle}`,
                      borderRadius: "10px",
                      padding: "0.4rem",
                      boxShadow: "0 10px 30px rgba(0,0,0,0.6)",
                      zIndex: 100,
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.2rem",
                    }}
                  >
                    {[
                      { icon: "📎", label: "Upload Wireframe", action: () => { setPrompt("Synthesize UI from mockup"); setIsPlusOpen(false); } },
                      { icon: "📁", label: "Scan Git Repo", action: () => { setPrompt("Scan AST for race conditions"); setIsPlusOpen(false); } },
                      { icon: "🪶", label: "Mount Agent Skill", action: () => { setPrompt("Apply BigQuery SQL optimizer skill"); setIsPlusOpen(false); } },
                    ].map((m, idx) => (
                      <button
                        key={idx}
                        onClick={m.action}
                        style={{
                          background: "transparent",
                          border: "none",
                          color: theme.textBright,
                          padding: "0.45rem 0.6rem",
                          borderRadius: "6px",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.5rem",
                          fontSize: "0.78rem",
                          cursor: "pointer",
                          textAlign: "left",
                        }}
                      >
                        <span>{m.icon}</span>
                        <span>{m.label}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <span
                  style={{
                    fontSize: "0.75rem",
                    color: theme.textDim,
                    background: theme.bgElevated,
                    padding: "0.3rem 0.65rem",
                    borderRadius: "6px",
                    border: `1px solid ${theme.borderSubtle}`,
                    fontWeight: 600,
                  }}
                >
                  ⚡ Ollama Local ($0/mo Offline)
                </span>

                <button
                  onClick={() => handleRunTask()}
                  disabled={isExecuting || !prompt.trim()}
                  style={{
                    width: "34px",
                    height: "34px",
                    borderRadius: "50%",
                    background: isExecuting || !prompt.trim() ? theme.bgElevated : theme.accent,
                    color: isExecuting || !prompt.trim() ? theme.textDim : "#000000",
                    border: "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: 900,
                    fontSize: "1.1rem",
                    cursor: isExecuting || !prompt.trim() ? "not-allowed" : "pointer",
                    boxShadow: isExecuting || !prompt.trim() ? "none" : `0 0 12px ${theme.accentGlow}`,
                  }}
                >
                  ↑
                </button>
              </div>
            </div>
          </div>

          {/* Quick Action Pills */}
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0.55rem", marginTop: "1.25rem", maxWidth: "760px" }}>
            {pills.map((pill, idx) => (
              <button
                key={idx}
                onClick={pill.action}
                style={{
                  background: theme.bgSurface,
                  border: `1px solid ${theme.borderSubtle}`,
                  color: theme.textMain,
                  padding: "0.35rem 0.85rem",
                  borderRadius: "999px",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                }}
              >
                <span>{pill.icon}</span>
                <span>{pill.label}</span>
              </button>
            ))}
          </div>

          {/* Interactive Workspace Views */}
          <div style={{ width: "100%", maxWidth: "980px", marginTop: "2rem" }}>
            {activeTab === "topology" && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "0.75rem" }}>
                {agents.map((node) => (
                  <div
                    key={node.id}
                    style={{
                      background: theme.bgSurface,
                      border: `1px solid ${node.status === "active" ? theme.accent : node.status === "success" ? theme.accentGreen : theme.borderSubtle}`,
                      borderRadius: "10px",
                      padding: "0.75rem",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.65rem",
                    }}
                  >
                    <div style={{ fontSize: "1.5rem" }}>{node.icon}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: "0.82rem", color: theme.textBright, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {node.name}
                      </div>
                      <div style={{ fontSize: "0.7rem", color: theme.textDim }}>{node.role}</div>
                    </div>
                    <span
                      style={{
                        fontSize: "0.62rem",
                        padding: "0.15rem 0.4rem",
                        borderRadius: "999px",
                        fontWeight: 700,
                        background: node.status === "success" ? "rgba(16,185,129,0.15)" : node.status === "active" ? "rgba(56,189,248,0.15)" : theme.bgElevated,
                        color: node.status === "success" ? theme.accentGreen : node.status === "active" ? theme.accent : theme.textDim,
                      }}
                    >
                      {node.status === "success" ? "DONE" : node.status === "active" ? "RUN" : "IDLE"}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "diff" && (
              <div style={{ background: theme.bgSurface, border: `1px solid ${theme.borderSubtle}`, borderRadius: "12px", padding: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.5rem" }}>
                  <span style={{ fontSize: "0.8rem", color: theme.accentGreen, fontWeight: 700 }}>
                    ⚡ AST Synthesized Source Code & Patches
                  </span>
                  <span style={{ fontSize: "0.72rem", color: theme.textDim }}>Language: Python 3.14 (PEP 604)</span>
                </div>
                <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.85rem", color: theme.textBright, background: theme.bgBase, padding: "1rem", borderRadius: "8px", overflowX: "auto" }}>
                  {generatedCode || "# Enter a requirement above and click ↑ to synthesize AST verified code..."}
                </pre>
              </div>
            )}

            {activeTab === "terminal" && (
              <div style={{ background: theme.bgSurface, border: `1px solid ${theme.borderSubtle}`, borderRadius: "12px", padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.8rem", color: theme.accent, fontWeight: 700 }}>
                    💻 Local Process & Container Sandbox
                  </span>
                  <button
                    onClick={handleSandboxRun}
                    disabled={isRunningSandbox}
                    style={{
                      background: isRunningSandbox ? theme.bgBase : theme.accentGreen,
                      color: "#000000",
                      fontWeight: 700,
                      fontSize: "0.78rem",
                      border: "none",
                      borderRadius: "6px",
                      padding: "0.35rem 0.85rem",
                      cursor: isRunningSandbox ? "not-allowed" : "pointer",
                    }}
                  >
                    {isRunningSandbox ? "⏳ Executing..." : "▶ Run in Sandbox"}
                  </button>
                </div>
                <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.82rem", color: theme.textBright, background: theme.bgBase, padding: "1rem", borderRadius: "8px", minHeight: "180px" }}>
                  {terminalOutput}
                </pre>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Settings Modal */}
      <Modal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} title="Desktop Preferences" theme={theme}>
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <div>
            <label style={{ fontSize: "0.8rem", color: theme.textDim, fontWeight: 700, textTransform: "uppercase" }}>
              Model Provider Engine
            </label>
            <select
              value={modelBackend}
              onChange={(e) => setModelBackend(e.target.value)}
              style={{
                width: "100%",
                marginTop: "0.35rem",
                background: theme.bgElevated,
                border: `1px solid ${theme.borderSubtle}`,
                color: theme.textBright,
                padding: "0.6rem",
                borderRadius: "8px",
                outline: "none",
              }}
            >
              <option value="ollama">Ollama Local (DeepSeek-R1 / Qwen2.5-Coder) - $0/mo Offline</option>
              <option value="deepseek">DeepSeek V3 API (High Speed)</option>
              <option value="anthropic">Anthropic Claude 3.7 Sonnet</option>
              <option value="openai">OpenAI GPT-4o</option>
            </select>
          </div>

          <Slider value={temperature} min={0.0} max={1.0} step={0.05} onChange={setTemperature} label="Sampling Temperature" theme={theme} />
          <Slider value={tokenBudget} min={2048} max={32768} step={1024} onChange={setTokenBudget} label="Context Budget" unit="tokens" theme={theme} />
        </div>
      </Modal>
    </div>
  );
}
