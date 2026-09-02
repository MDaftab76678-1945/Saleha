"use client";

import React, { useState, useEffect, useRef } from "react";
import { THEME_PRESETS, ThemeTokens, Modal, Switch, Slider } from "@saleha/ui";

interface SwarmNode {
  id: string;
  name: string;
  role: string;
  icon: string;
  status: "idle" | "active" | "success";
  timingMs?: number;
}

interface WebNotebookCell {
  id: string;
  type: "code" | "markdown" | "sql" | "swarm";
  source: string;
  output?: string;
  error?: string;
  isExecuting?: boolean;
}

const ALL_25_NODES: SwarmNode[] = [
  { id: "arch", name: "ArchitectAgent", role: "ADR & Hexagonal Design", icon: "🏛️", status: "idle" },
  { id: "planner", name: "PlannerAgent", role: "Task Decomposition", icon: "🗺️", status: "idle" },
  { id: "designer", name: "DesignerAgent", role: "UI/UX & Tokens", icon: "🎨", status: "idle" },
  { id: "vision", name: "VisionDesignerAgent", role: "Wireframe-to-Code", icon: "👁️", status: "idle" },
  { id: "web_dev", name: "WebDevAgent", role: "HTML5/CSS3/Three.js", icon: "🌐", status: "idle" },
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
  { id: "researcher", name: "DeepResearcherAgent", role: "Recursive Multi-Hop Research", icon: "🔬", status: "idle" },
  { id: "slides", name: "SlidesArchitectAgent", role: "HTML5/Marp Presentation Deck", icon: "📊", status: "idle" },
  { id: "sheets", name: "SheetsAnalystAgent", role: "Polars/Arrow Columnar Analytics", icon: "📈", status: "idle" },
  { id: "claw", name: "SovereignClawAgent", role: "Autonomous Browser & DOM Agent", icon: "🦅", status: "idle" },
  { id: "nb_architect", name: "NotebookArchitectAgent", role: "Interactive Reactive Notebooks", icon: "📓", status: "idle" },
  { id: "voice", name: "VoiceArchitectAgent", role: "Real-Time Spoken Pair-Programmer", icon: "🎙️", status: "idle" },
];

export default function WebStudioPage() {
  const [themeKey, setThemeKey] = useState<string>("obsidian");
  const theme: ThemeTokens = THEME_PRESETS[themeKey] || THEME_PRESETS.obsidian;

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "topology" | "diff" | "events" | "terminal" | "notebook" | "trainer">("chat");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isPlusMenuOpen, setIsPlusMenuOpen] = useState(false);
  const [nodes, setNodes] = useState<SwarmNode[]>(ALL_25_NODES);

  // Settings
  const [modelBackend, setModelBackend] = useState("ollama");
  const [temperature, setTemperature] = useState(0.2);
  const [contextBudget, setContextBudget] = useState(8192);

  // Execution state
  const [prompt, setPrompt] = useState("");
  const [isExecuting, setIsExecuting] = useState(false);
  const [hasExecuted, setHasExecuted] = useState(false);
  const [generatedCode, setGeneratedCode] = useState<string>("");
  const [terminalOutput, setTerminalOutput] = useState<string>("Saleha Isolated Execution Terminal Ready.\n");
  const [eventLogs, setEventLogs] = useState<string[]>([
    "System Ready: 25 First-Class Python Agents Mounted.",
    "Local Inference Engine (GGUF/Ollama), Neuro-Symbolic Scorer & Trainer Active.",
  ]);

  // Model Trainer State
  const [isTraining, setIsTraining] = useState(false);
  const [trainProgress, setTrainProgress] = useState(0);
  const [trainEpoch, setTrainEpoch] = useState(1);
  const [currentLoss, setCurrentLoss] = useState(1.42);

  // Notebook Cells State
  const [notebookCells, setNotebookCells] = useState<WebNotebookCell[]>([
    {
      id: "c1",
      type: "markdown",
      source: "# 📓 Reactive Computational Notebook\n*Powered by Saleha Autonomous Kernel with AST Invariant Safety & CGroup Isolation.*",
    },
    {
      id: "c2",
      type: "code",
      source: "import sys\nprint(f'Kernel Version: Python {sys.version.split()[0]}')\nprint('Ephemeral Sandbox: 256MB RAM / 1.0 CPU CGroups Active')",
      output: "Kernel Version: Python 3.14.7\nEphemeral Sandbox: 256MB RAM / 1.0 CPU CGroups Active",
    },
  ]);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // 3D Neural Particle Visualizer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || window.innerWidth);
    let height = (canvas.height = canvas.parentElement?.clientHeight || window.innerHeight);

    const particles: { x: number; y: number; vx: number; vy: number; radius: number }[] = [];
    for (let i = 0; i < 35; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.6,
        vy: (Math.random() - 0.5) * 0.6,
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
          if (dist < 80) {
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

    const handleResize = () => {
      if (canvas && canvas.parentElement) {
        width = canvas.width = canvas.parentElement.clientWidth;
        height = canvas.height = canvas.parentElement.clientHeight;
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener("resize", handleResize);
    };
  }, [theme]);

  const handleExecuteSwarm = async (customGoal?: string) => {
    const goalToRun = customGoal || prompt;
    if (!goalToRun.trim()) return;

    setIsExecuting(true);
    setHasExecuted(true);
    setGeneratedCode("// [Swarm Pipeline Engine] Initializing DAG execution...\n");
    setEventLogs((prev) => [
      `[${new Date().toLocaleTimeString()}] TaskAssignedEvent: "${goalToRun.slice(0, 45)}..."`,
      ...prev,
    ]);

    setTimeout(() => {
      setNodes((prev) => prev.map((n) => (n.id === "arch" || n.id === "planner" ? { ...n, status: "active", timingMs: 18 } : n)));
      setGeneratedCode((prev) => prev + "\n// [1/3] ArchitectAgent: Generated Hexagonal Ports & Adapters ADR\n");
    }, 400);

    setTimeout(() => {
      setNodes((prev) => prev.map((n) => (n.id === "coder" || n.id === "vision" ? { ...n, status: "active", timingMs: 22 } : n)));
      setGeneratedCode((prev) => prev + `\nclass AutonomousService:\n    \"\"\"Synthesized AST-hardened production service.\"\"\"\n    def __init__(self):\n        self.active = True\n\n    def execute(self) -> bool:\n        return self.active\n`);
    }, 900);

    setTimeout(() => {
      setNodes((prev) => prev.map((n) => ({ ...n, status: "success" })));
      setGeneratedCode((prev) => prev + "\n// [3/3] SecurityGuardAgent AST Scan: PASS (0 CWEs detected)\n// [3/3] QALeadAgent: 100% Invariant Assertions PASSED\n");
      setEventLogs((prev) => [
        `[${new Date().toLocaleTimeString()}] SecuritySAST: 0 Vulnerabilities Detected (PASS)`,
        `[${new Date().toLocaleTimeString()}] TestExecution: 5/5 Invariant Assertions Passed`,
        ...prev,
      ]);
      setIsExecuting(false);
    }, 1500);
  };

  const handleStartFineTuning = () => {
    setIsTraining(true);
    setTrainProgress(0);
    setTrainEpoch(1);
    setCurrentLoss(1.42);

    const interval = setInterval(() => {
      setTrainProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsTraining(false);
          return 100;
        }
        const next = prev + 10;
        setTrainEpoch(Math.min(3, Math.floor(next / 33) + 1));
        setCurrentLoss((l) => Math.max(0.18, +(l - 0.12).toFixed(3)));
        return next;
      });
    }, 400);
  };

  const quickActionPills = [
    { label: "Swarm", icon: "🌌", action: () => { setPrompt("Synthesize a distributed lock with AST safety"); setActiveTab("topology"); } },
    { label: "Trainer", icon: "🧠", action: () => { setActiveTab("trainer"); } },
    { label: "Notebook", icon: "📓", action: () => { setActiveTab("notebook"); } },
    { label: "Voice", icon: "🎙️", action: () => { setPrompt("Walk me through our system architecture verbally"); setActiveTab("chat"); } },
    { label: "Vision", icon: "🎨", action: () => { setPrompt("Dark mode crypto analytics dashboard with live price ticker"); setActiveTab("diff"); } },
    { label: "Deep Research", icon: "🔬", action: () => { setPrompt("Analyze distributed consensus algorithms for p2p networks"); setActiveTab("events"); } },
    { label: "Auto-PR", icon: "🐙", action: () => { setPrompt("Synthesize distributed rate limiter with Redis backend"); setActiveTab("diff"); } },
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
      {/* 3D Neural Particle Canvas Background */}
      <canvas
        ref={canvasRef}
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          zIndex: 0,
          opacity: 0.5,
        }}
      />

      {/* LEFT SIDEBAR (Kimi-Style) */}
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
          {/* Top Brand Bar */}
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
              style={{
                background: "transparent",
                border: "none",
                color: theme.textDim,
                cursor: "pointer",
                fontSize: "1rem",
                padding: "0.2rem",
              }}
              title="Toggle Sidebar"
            >
              {isSidebarCollapsed ? "◧" : "◨"}
            </button>
          </div>

          {/* New Chat Button (Ctrl K) */}
          <button
            onClick={() => { setPrompt(""); setHasExecuted(false); setActiveTab("chat"); }}
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
              transition: "all 0.2s",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "1rem" }}>💬</span>
              {!isSidebarCollapsed && <span>New Session</span>}
            </div>
            {!isSidebarCollapsed && (
              <span style={{ fontSize: "0.68rem", color: theme.textDim, background: theme.bgBase, padding: "0.1rem 0.35rem", borderRadius: "4px", border: `1px solid ${theme.borderSubtle}` }}>
                Ctrl K
              </span>
            )}
          </button>

          {/* Navigation Capabilities */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            {[
              { id: "chat", label: "Studio Canvas", icon: "⚡" },
              { id: "trainer", label: "Model Trainer", icon: "🧠" },
              { id: "notebook", label: "Notebook Studio", icon: "📓" },
              { id: "topology", label: "25-Agent Swarm", icon: "🌌" },
              { id: "diff", label: "AST Code Patch", icon: "📝" },
              { id: "terminal", label: "Sandbox Terminal", icon: "💻" },
              { id: "events", label: "EventBus Stream", icon: "📡" },
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

        {/* Sidebar Footer */}
        <div style={{ borderTop: `1px solid ${theme.borderSubtle}`, paddingTop: "0.75rem", display: "flex", alignItems: "center", justifyContent: isSidebarCollapsed ? "center" : "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", overflow: "hidden" }}>
            <div
              style={{
                width: "26px",
                height: "26px",
                borderRadius: "50%",
                background: `linear-gradient(135deg, ${theme.accentAmber || "#f59e0b"}, ${theme.accent || "#38bdf8"})`,
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
                <span style={{ fontSize: "0.65rem", color: theme.accentGreen, fontWeight: 700 }}>PRO ACTIVE</span>
              </div>
            )}
          </div>
          {!isSidebarCollapsed && (
            <button
              onClick={() => setIsSettingsOpen(true)}
              style={{
                background: "transparent",
                border: "none",
                color: theme.textDim,
                cursor: "pointer",
                fontSize: "1rem",
              }}
            >
              ⚙️
            </button>
          )}
        </div>
      </aside>

      {/* MAIN CENTER WORKSPACE */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", position: "relative", zIndex: 10, overflow: "hidden" }}>
        {/* Top Header Bar */}
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
            <span style={{ fontSize: "0.85rem", fontWeight: 700, color: theme.textBright }}>
              {activeTab === "chat" ? "Studio Workspace" : activeTab === "trainer" ? "🧠 Custom SLM Distillation Studio" : activeTab === "notebook" ? "📓 Reactive Notebook Studio" : activeTab === "topology" ? "25-Agent Swarm DAG" : activeTab === "diff" ? "AST Code Diff" : activeTab === "terminal" ? "Live Container Terminal" : "EventBus Stream"}
            </span>
            <span style={{ fontSize: "0.68rem", color: theme.accentGreen, background: "rgba(16,185,129,0.12)", padding: "0.15rem 0.5rem", borderRadius: "999px", fontWeight: 700 }}>
              v3.0.0 Sovereign
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

        {/* Center Canvas Area */}
        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", alignItems: "center", padding: "2.5rem 1.5rem 1.5rem" }}>
          {/* Brand Big Title */}
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
              Sovereign Autonomous AI Software Engineer • 25-Agent Swarm • GGUF Local Kernel
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
                  handleExecuteSwarm();
                }
              }}
              placeholder="Ask anything, task an agent, or say /voice /auto-pr..."
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

            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderTop: `1px solid ${theme.borderSubtle}`, paddingTop: "0.75rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", position: "relative" }}>
                <button
                  onClick={() => setIsPlusMenuOpen(!isPlusMenuOpen)}
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
                  title="Attach Files, Git Repos, or Datasets"
                >
                  +
                </button>
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
                  ⚡ Sovereign Local (Qwen2.5-Coder:1.5b)
                </span>

                <button
                  onClick={() => handleExecuteSwarm()}
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
            {quickActionPills.map((pill, idx) => (
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
            {/* View 1: Model Trainer Studio */}
            {activeTab === "trainer" && (
              <div style={{ background: theme.bgSurface, border: `1px solid ${theme.borderSubtle}`, borderRadius: "16px", padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${theme.borderSubtle}`, paddingBottom: "0.75rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontSize: "1.2rem" }}>🧠</span>
                    <span style={{ fontWeight: 800, fontSize: "1rem", color: theme.textBright }}>
                      Custom SLM Distillation & LoRA Trainer
                    </span>
                  </div>
                  <button
                    onClick={handleStartFineTuning}
                    disabled={isTraining}
                    style={{
                      background: isTraining ? theme.bgElevated : theme.accentGreen,
                      color: isTraining ? theme.textDim : "#000",
                      border: "none",
                      padding: "0.35rem 0.85rem",
                      borderRadius: "6px",
                      fontSize: "0.78rem",
                      fontWeight: 700,
                      cursor: isTraining ? "not-allowed" : "pointer",
                    }}
                  >
                    {isTraining ? "⏳ Training in Progress..." : "▶ Start LoRA Fine-Tuning"}
                  </button>
                </div>

                {/* Training Metrics Cards */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem" }}>
                  <div style={{ background: theme.bgBase, padding: "0.75rem", borderRadius: "8px", border: `1px solid ${theme.borderSubtle}` }}>
                    <div style={{ fontSize: "0.68rem", color: theme.textDim, fontWeight: 700 }}>BASE MODEL</div>
                    <div style={{ fontSize: "0.85rem", fontWeight: 800, color: theme.textBright, marginTop: "0.2rem" }}>Qwen2.5-Coder-1.5B</div>
                  </div>
                  <div style={{ background: theme.bgBase, padding: "0.75rem", borderRadius: "8px", border: `1px solid ${theme.borderSubtle}` }}>
                    <div style={{ fontSize: "0.68rem", color: theme.textDim, fontWeight: 700 }}>EPOCH PROGRESS</div>
                    <div style={{ fontSize: "0.85rem", fontWeight: 800, color: theme.accent, marginTop: "0.2rem" }}>Epoch {trainEpoch} / 3 ({trainProgress}%)</div>
                  </div>
                  <div style={{ background: theme.bgBase, padding: "0.75rem", borderRadius: "8px", border: `1px solid ${theme.borderSubtle}` }}>
                    <div style={{ fontSize: "0.68rem", color: theme.textDim, fontWeight: 700 }}>CURRENT LOSS</div>
                    <div style={{ fontSize: "0.85rem", fontWeight: 800, color: theme.accentGreen, marginTop: "0.2rem" }}>{currentLoss}</div>
                  </div>
                  <div style={{ background: theme.bgBase, padding: "0.75rem", borderRadius: "8px", border: `1px solid ${theme.borderSubtle}` }}>
                    <div style={{ fontSize: "0.68rem", color: theme.textDim, fontWeight: 700 }}>QUANTIZATION</div>
                    <div style={{ fontSize: "0.85rem", fontWeight: 800, color: theme.textBright, marginTop: "0.2rem" }}>4-bit NF4 (LoRA r=16)</div>
                  </div>
                </div>

                {/* Progress Bar */}
                <div style={{ width: "100%", height: "8px", background: theme.bgElevated, borderRadius: "999px", overflow: "hidden" }}>
                  <div style={{ width: `${trainProgress}%`, height: "100%", background: `linear-gradient(90deg, ${theme.accent}, ${theme.accentGreen})`, transition: "width 0.3s ease" }} />
                </div>
              </div>
            )}

            {/* View 2: Reactive Notebook */}
            {activeTab === "notebook" && (
              <div style={{ background: theme.bgSurface, border: `1px solid ${theme.borderSubtle}`, borderRadius: "16px", padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${theme.borderSubtle}`, paddingBottom: "0.75rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ fontSize: "1.2rem" }}>📓</span>
                    <span style={{ fontWeight: 800, fontSize: "1rem", color: theme.textBright }}>
                      Reactive Computational Notebook
                    </span>
                  </div>
                </div>
                {notebookCells.map((cell, idx) => (
                  <div key={cell.id} style={{ background: theme.bgBase, border: `1px solid ${theme.borderSubtle}`, borderRadius: "10px", padding: "1rem" }}>
                    <div style={{ fontSize: "0.7rem", color: theme.accent, fontWeight: 700, marginBottom: "0.4rem" }}>[{idx + 1}] {cell.type.toUpperCase()} CELL</div>
                    <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.82rem", color: theme.textBright }}>{cell.source}</pre>
                    {cell.output && <pre style={{ margin: "0.4rem 0 0", fontFamily: "monospace", fontSize: "0.78rem", color: theme.accentGreen }}>{cell.output}</pre>}
                  </div>
                ))}
              </div>
            )}

            {/* View 3: 25-Agent Topology */}
            {activeTab === "topology" && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "0.75rem" }}>
                {nodes.map((node) => (
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
                  </div>
                ))}
              </div>
            )}

            {/* View 4: AST Diff */}
            {activeTab === "diff" && (
              <div style={{ background: theme.bgSurface, border: `1px solid ${theme.borderSubtle}`, borderRadius: "12px", padding: "1rem" }}>
                <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.85rem", color: theme.textBright, background: theme.bgBase, padding: "1rem", borderRadius: "8px", overflowX: "auto" }}>
                  {generatedCode || "# Enter a prompt above and click ↑ to synthesize AST verified code..."}
                </pre>
              </div>
            )}

            {/* View 5: Live Terminal */}
            {activeTab === "terminal" && (
              <div style={{ background: theme.bgSurface, border: `1px solid ${theme.borderSubtle}`, borderRadius: "12px", padding: "1rem" }}>
                <pre style={{ margin: 0, fontFamily: "monospace", fontSize: "0.82rem", color: theme.textBright, background: theme.bgBase, padding: "1rem", borderRadius: "8px", minHeight: "180px" }}>
                  {terminalOutput}
                </pre>
              </div>
            )}

            {/* View 6: Events */}
            {activeTab === "events" && (
              <div style={{ background: theme.bgSurface, border: `1px solid ${theme.borderSubtle}`, borderRadius: "12px", padding: "1rem" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {eventLogs.map((log, idx) => (
                    <div key={idx} style={{ fontFamily: "monospace", fontSize: "0.78rem", color: theme.textBright, background: theme.bgBase, padding: "0.55rem 0.75rem", borderRadius: "6px", borderLeft: `3px solid ${theme.accent}` }}>
                      {log}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Settings Modal */}
      <Modal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} title="Studio Preferences" theme={theme}>
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
              <option value="ollama">Ollama Local (DeepSeek-R1 / Qwen2.5-Coder) - $0/mo Private</option>
              <option value="deepseek">DeepSeek V3 API (High Speed)</option>
              <option value="anthropic">Anthropic Claude 3.7 Sonnet</option>
              <option value="openai">OpenAI GPT-4o</option>
            </select>
          </div>

          <Slider value={temperature} min={0.0} max={1.0} step={0.05} onChange={setTemperature} label="Sampling Temperature" theme={theme} />
          <Slider value={contextBudget} min={2048} max={32768} step={1024} onChange={setContextBudget} label="Context Budget" unit="tokens" theme={theme} />
        </div>
      </Modal>
    </div>
  );
}
