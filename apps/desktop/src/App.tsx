import React, { useState, useEffect, useRef } from "react";
import { THEME_PRESETS, ThemeTokens, Modal, Switch, Slider } from "@saleha/ui";
import "./App.css";

interface AgentItem {
  id: string;
  name: string;
  role: string;
  icon: string;
  domain: string;
  superpower: string;
}

const AGENT_CATALOG: AgentItem[] = [
  { id: "planner", name: "PlannerAgent", role: "Planning", icon: "🗺️", domain: "Architecture", superpower: "Task Decomposition & Dependency Graphs" },
  { id: "architect", name: "ArchitectAgent", role: "Architecture", icon: "🏛️", domain: "System Design", superpower: "Hexagonal Design & ADR.md Generation" },
  { id: "coder", name: "CoderAgent", role: "Coding", icon: "⚡", domain: "Core Synthesis", superpower: "Self-Healing Multi-Attempt Code Synthesis" },
  { id: "designer", name: "DesignerAgent", role: "UI/UX", icon: "🎨", domain: "Frontend", superpower: "Design Systems & Token Hierarchies" },
  { id: "web_dev", name: "WebDevAgent", role: "Web Dev", icon: "🌐", domain: "Fullstack Web", superpower: "React/Next.js/HTML5 & Three.js 3D Apps" },
  { id: "security", name: "SecurityGuardAgent", role: "Security", icon: "🛡️", domain: "DevSecOps", superpower: "AST SAST Scanner & OWASP Top-10 Audit" },
  { id: "qa_lead", name: "QALeadAgent", role: "QA Lead", icon: "🧪", domain: "Testing", superpower: "Automated Pytest Suites & Edge Boundaries" },
  { id: "debugger", name: "DebuggerAgent", role: "Debugging", icon: "🔍", domain: "Diagnostics", superpower: "Traceback Diagnostics & Targeted Patches" },
  { id: "reviewer", name: "ReviewerAgent", role: "Reviewer", icon: "🧐", domain: "Code Review", superpower: "LLM-Powered Senior Code Review" },
  { id: "sre", name: "SREIncidentAgent", role: "SRE Incident", icon: "🚨", domain: "Observability", superpower: "Outage Log RCA & Post-Mortem Runbooks" },
  { id: "finops", name: "FinOpsOptimizerAgent", role: "FinOps", icon: "💰", domain: "Token Economics", superpower: "40-70% Context Window Compression" },
  { id: "refactor", name: "RefactorSpecialistAgent", role: "Refactoring", icon: "♻️", domain: "Clean Code", superpower: "PEP 585/604 Modern Typing & Complexity Reducer" },
  { id: "devops", name: "DevOpsAgent", role: "DevOps", icon: "🐳", domain: "Infrastructure", superpower: "Docker Multi-Stage & CI/CD Pipelines" },
  { id: "data_eng", name: "DataEngineerAgent", role: "Data Eng", icon: "📊", domain: "Data & Storage", superpower: "SQL Schemas, Vector DBs & Polars Pipelines" },
  { id: "developer", name: "DeveloperAgent", role: "Developer", icon: "👨‍💻", domain: "Fullstack", superpower: "Polyglot Async Microservices & ORM Models" },
  { id: "skill_creator", name: "NewSkillCreatorAgent", role: "Skill Creator", icon: "🧬", domain: "Metaprogramming", superpower: "Autonomous AgentSkill Synthesis & Indexing" },
];

export function DesktopApp() {
  const [themeKey, setThemeKey] = useState<string>("obsidian");
  const theme: ThemeTokens = THEME_PRESETS[themeKey] || THEME_PRESETS.obsidian;
  
  const [selectedAgent, setSelectedAgent] = useState<AgentItem>(AGENT_CATALOG[0]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"workspace" | "terminal" | "swarm">("workspace");

  // Settings state
  const [modelBackend, setModelBackend] = useState("ollama");
  const [temperature, setTemperature] = useState(0.2);
  const [tokenBudget, setTokenBudget] = useState(8192);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [telemetryHud, setTelemetryHud] = useState(true);
  const [isOffline, setIsOffline] = useState(true);

  // Execution simulation state
  const [userPrompt, setUserPrompt] = useState("Build high-performance ring buffer with ASan memory safety");
  const [isExecuting, setIsExecuting] = useState(false);
  const [execStep, setExecStep] = useState(0);
  const [generatedCode, setGeneratedCode] = useState<string>("");

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // 3D Particle Canvas Background
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 300);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 200);

    const particles: { x: number; y: number; vx: number; vy: number; radius: number }[] = [];
    for (let i = 0; i < 35; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.8,
        vy: (Math.random() - 0.5) * 0.8,
        radius: Math.random() * 2 + 1,
      });
    }

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = theme.accent;
      ctx.strokeStyle = theme.borderSubtle;

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
          if (dist < 70) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }
      animationFrameId = requestAnimationFrame(render);
    };
    render();

    return () => cancelAnimationFrame(animationFrameId);
  }, [theme]);

  const handleRunExecution = () => {
    setIsExecuting(true);
    setExecStep(1);
    setGeneratedCode("// Initializing Tree-of-Thoughts Swarm Execution...\n");

    setTimeout(() => {
      setExecStep(2);
      setGeneratedCode("// [1/4] ArchitectAgent generating Hexagonal System Boundaries...\n// Status: ADR Created: RingBuffer (Memory-Safe)\n");
    }, 600);

    setTimeout(() => {
      setExecStep(3);
      setGeneratedCode(`// [2/4] ${selectedAgent.name} synthesizing implementation...\n\n` +
`class RingBuffer:\n` +
`    """Zero-allocation thread-safe circular ring buffer."""\n` +
`    def __init__(self, capacity: int = 1024):\n` +
`        self.capacity = capacity\n` +
`        self.buffer = [None] * capacity\n` +
`        self.head = 0\n` +
`        self.tail = 0\n` +
`        self.size = 0\n\n` +
`    def push(self, item: int) -> bool:\n` +
`        if self.size == self.capacity:\n` +
`            return False  # Buffer full\n` +
`        self.buffer[self.tail] = item\n` +
`        self.tail = (self.tail + 1) % self.capacity\n` +
`        self.size += 1\n` +
`        return True\n`
      );
    }, 1300);

    setTimeout(() => {
      setExecStep(4);
      setIsExecuting(false);
      setGeneratedCode((prev: string) => prev + `\n// [3/4] SecurityGuardAgent AST Scan: PASS (0 CWEs detected)\n` +
        `// [4/4] TesterAgent Sandboxed Verification: 5/5 PASSED in 42μs\n` +
        `// Result: 100% Deterministic Code Synthesized & Verified locally ($0 Token Cost)`
      );
    }, 2000);
  };

  return (
    <div
      style={{
        backgroundColor: theme.bgBase,
        color: theme.textMain,
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif",
        overflow: "hidden",
      }}
    >
      {/* Top Header Bar */}
      <header
        style={{
          background: theme.bgSurface,
          borderBottom: `1px solid ${theme.borderSubtle}`,
          padding: "0.5rem 1.25rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: "56px",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.85rem" }}>
          <div
            style={{
              width: "32px",
              height: "32px",
              background: `linear-gradient(135deg, ${theme.accent}, ${theme.accentPurple})`,
              borderRadius: "8px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontWeight: 800,
              fontSize: "1.1rem",
              boxShadow: `0 0 16px ${theme.accentGlow}`,
            }}
          >
            🧠
          </div>
          <span style={{ fontWeight: 800, color: theme.textBright, fontSize: "1.05rem", letterSpacing: "-0.02em" }}>
            Saleha Desktop AI
          </span>
          <span
            style={{
              fontSize: "0.7rem",
              background: "rgba(56,189,248,0.12)",
              border: `1px solid ${theme.borderBright}`,
              color: theme.accent,
              padding: "0.15rem 0.55rem",
              borderRadius: "999px",
              fontWeight: 700,
            }}
          >
            Tauri v2 Native Rust
          </span>
        </div>

        {/* Center Tabs */}
        <div style={{ display: "flex", background: theme.bgElevated, borderRadius: "8px", padding: "3px", gap: "4px" }}>
          <button
            onClick={() => setActiveTab("workspace")}
            style={{
              background: activeTab === "workspace" ? theme.bgSurface : "transparent",
              border: "none",
              color: activeTab === "workspace" ? theme.textBright : theme.textDim,
              padding: "0.3rem 0.85rem",
              borderRadius: "6px",
              fontSize: "0.8rem",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            ⚡ Workspace
          </button>
          <button
            onClick={() => setActiveTab("terminal")}
            style={{
              background: activeTab === "terminal" ? theme.bgSurface : "transparent",
              border: "none",
              color: activeTab === "terminal" ? theme.textBright : theme.textDim,
              padding: "0.3rem 0.85rem",
              borderRadius: "6px",
              fontSize: "0.8rem",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            💻 Execution Hub
          </button>
          <button
            onClick={() => setActiveTab("swarm")}
            style={{
              background: activeTab === "swarm" ? theme.bgSurface : "transparent",
              border: "none",
              color: activeTab === "swarm" ? theme.textBright : theme.textDim,
              padding: "0.3rem 0.85rem",
              borderRadius: "6px",
              fontSize: "0.8rem",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            🌌 Swarm Map
          </button>
        </div>

        {/* Right Tools: Theme & Settings */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <select
            value={themeKey}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setThemeKey(e.target.value)}
            style={{
              background: theme.bgElevated,
              border: `1px solid ${theme.borderSubtle}`,
              color: theme.textBright,
              padding: "0.35rem 0.65rem",
              borderRadius: "6px",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
              outline: "none",
            }}
          >
            {(Object.entries(THEME_PRESETS) as [string, ThemeTokens][]).map(([key, t]: [string, ThemeTokens]) => (
              <option key={key} value={key} style={{ background: "#0c101a", color: "#f8fafc" }}>
                🎨 {t.name}
              </option>
            ))}
          </select>

          <button
            onClick={() => setIsSettingsOpen(true)}
            style={{
              background: theme.bgElevated,
              border: `1px solid ${theme.borderSubtle}`,
              color: theme.textBright,
              padding: "0.35rem 0.75rem",
              borderRadius: "6px",
              fontSize: "0.8rem",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "0.35rem",
              fontWeight: 600,
            }}
          >
            ⚙️ Settings
          </button>
        </div>
      </header>

      {/* Main Content Body */}
      <main style={{ flex: 1, display: "grid", gridTemplateColumns: "300px 1fr", overflow: "hidden" }}>
        {/* Left Agent Swarm Sidebar */}
        <aside
          style={{
            background: theme.bgSurface,
            borderRight: `1px solid ${theme.borderSubtle}`,
            padding: "1rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.75rem",
            overflowY: "auto",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h4 style={{ fontSize: "0.75rem", color: theme.textDim, textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em" }}>
              Active Agents ({AGENT_CATALOG.length})
            </h4>
            <span style={{ fontSize: "0.65rem", color: theme.accentGreen, fontWeight: 700 }}>● ALL ONLINE</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
            {AGENT_CATALOG.map((agent) => {
              const isSelected = selectedAgent.id === agent.id;
              return (
                <div
                  key={agent.id}
                  onClick={() => setSelectedAgent(agent)}
                  style={{
                    padding: "0.55rem 0.75rem",
                    background: isSelected ? theme.bgElevated : "transparent",
                    border: `1px solid ${isSelected ? theme.borderBright : "transparent"}`,
                    borderRadius: "8px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.6rem",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span style={{ fontSize: "1.1rem" }}>{agent.icon}</span>
                  <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0 }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: 700, color: isSelected ? theme.textBright : theme.textMain, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {agent.name}
                    </span>
                    <span style={{ fontSize: "0.7rem", color: theme.textDim }}>
                      {agent.domain}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Right Central Workspace */}
        <section
          style={{
            padding: "1.5rem",
            display: "flex",
            flexDirection: "column",
            gap: "1.25rem",
            overflowY: "auto",
            position: "relative",
          }}
        >
          {/* Active Agent Hero Glass Card */}
          <div
            style={{
              background: theme.bgSurface,
              border: `1px solid ${theme.borderSubtle}`,
              borderRadius: "14px",
              padding: "1.5rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              boxShadow: `0 8px 30px rgba(0,0,0,0.25)`,
            }}
          >
            <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
              <div
                style={{
                  width: "48px",
                  height: "48px",
                  background: theme.bgElevated,
                  borderRadius: "12px",
                  border: `1px solid ${theme.borderBright}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "1.6rem",
                }}
              >
                {selectedAgent.icon}
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: "1.2rem", fontWeight: 800, color: theme.textBright }}>
                  {selectedAgent.name}
                </h3>
                <p style={{ margin: "0.2rem 0 0", fontSize: "0.85rem", color: theme.accent }}>
                  ⚡ {selectedAgent.superpower}
                </p>
              </div>
            </div>

            <div style={{ display: "flex", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.75rem", background: "rgba(16,185,129,0.1)", color: theme.accentGreen, border: "1px solid rgba(16,185,129,0.2)", padding: "0.3rem 0.65rem", borderRadius: "999px", fontWeight: 600 }}>
                Temp: 0.2
              </span>
              <span style={{ fontSize: "0.75rem", background: "rgba(56,189,248,0.1)", color: theme.accent, border: `1px solid ${theme.borderBright}`, padding: "0.3rem 0.65rem", borderRadius: "999px", fontWeight: 600 }}>
                $0 Token Cost
              </span>
            </div>
          </div>

          {/* Interactive Prompt & Execution Box */}
          <div
            style={{
              background: theme.bgSurface,
              border: `1px solid ${theme.borderSubtle}`,
              borderRadius: "14px",
              padding: "1.25rem",
              display: "flex",
              flexDirection: "column",
              gap: "0.85rem",
            }}
          >
            <label style={{ fontSize: "0.8rem", fontWeight: 700, color: theme.textDim, textTransform: "uppercase" }}>
              Instruction / Goal Input
            </label>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <input
                type="text"
                value={userPrompt}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUserPrompt(e.target.value)}
                placeholder="Describe your software requirement or engineering task..."
                style={{
                  flex: 1,
                  background: theme.bgElevated,
                  border: `1px solid ${theme.borderSubtle}`,
                  borderRadius: "8px",
                  padding: "0.65rem 1rem",
                  color: theme.textBright,
                  fontSize: "0.9rem",
                  outline: "none",
                }}
              />
              <button
                onClick={handleRunExecution}
                disabled={isExecuting}
                style={{
                  background: `linear-gradient(135deg, ${theme.accent}, ${theme.accentPurple})`,
                  color: "#000",
                  border: "none",
                  padding: "0.65rem 1.5rem",
                  borderRadius: "8px",
                  fontWeight: 700,
                  fontSize: "0.9rem",
                  cursor: isExecuting ? "wait" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  boxShadow: `0 0 20px ${theme.accentGlow}`,
                }}
              >
                {isExecuting ? `Running Step ${execStep}/4...` : "⚡ Run Swarm"}
              </button>
            </div>
          </div>

          {/* Code Viewer & Verification Terminal */}
          <div
            style={{
              flex: 1,
              background: "#030712",
              border: `1px solid ${theme.borderSubtle}`,
              borderRadius: "14px",
              padding: "1.25rem",
              display: "flex",
              flexDirection: "column",
              fontFamily: "'Fira Code', monospace",
              fontSize: "0.85rem",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: "0.5rem", marginBottom: "0.75rem" }}>
              <span style={{ color: theme.accent, fontWeight: 600 }}>🖥️ live_sandbox_terminal.py</span>
              <span style={{ color: theme.textDim, fontSize: "0.75rem" }}>Gamma AST Engine (Local Native Rust)</span>
            </div>
            <pre style={{ margin: 0, color: theme.textBright, whiteHeight: "100%", overflowY: "auto", flex: 1 }}>
              {generatedCode || "// Ready. Enter a goal above and click 'Run Swarm' to initiate local multi-agent synthesis."}
            </pre>
          </div>

          {/* 3D Background Canvas Preview */}
          <div
            style={{
              height: "120px",
              background: theme.bgSurface,
              border: `1px solid ${theme.borderSubtle}`,
              borderRadius: "14px",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <canvas ref={canvasRef} style={{ width: "100%", height: "100%", position: "absolute", top: 0, left: 0 }} />
            <div style={{ position: "absolute", bottom: "10px", left: "15px", zIndex: 2, fontSize: "0.75rem", color: theme.textDim, background: "rgba(0,0,0,0.6)", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>
              🌌 3D Neural Swarm Particle Mesh (Local GPU Accelerated)
            </div>
          </div>
        </section>
      </main>

      {/* Advanced Settings Modal */}
      <Modal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        title="⚙️ Saleha Desktop AI Settings"
        theme={theme}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <div>
            <label style={{ fontSize: "0.8rem", color: theme.textDim, fontWeight: 700, textTransform: "uppercase" }}>
              Model Provider Engine
            </label>
            <select
              value={modelBackend}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setModelBackend(e.target.value)}
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
              <option value="ollama">Ollama Local (http://127.0.0.1:11434) - $0/mo Private</option>
              <option value="deepseek">DeepSeek V3 (Direct High-Speed API)</option>
              <option value="openrouter">OpenRouter Multi-Model Routing</option>
              <option value="anthropic">Anthropic Claude 3.7 Sonnet</option>
              <option value="vllm">Custom vLLM / Localhost OpenAI-compatible</option>
            </select>
          </div>

          <Slider
            label="Inference Temperature"
            min={0.0}
            max={1.0}
            step={0.05}
            value={temperature}
            onChange={setTemperature}
            theme={theme}
          />

          <Slider
            label="Context Window Budget"
            min={2048}
            max={32768}
            step={1024}
            unit=" tokens"
            value={tokenBudget}
            onChange={setTokenBudget}
            theme={theme}
          />

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: `1px solid ${theme.borderSubtle}`, paddingTop: "0.75rem" }}>
            <Switch
              label="Audio Sound Effects (Chimes on completion)"
              checked={soundEnabled}
              onChange={setSoundEnabled}
              theme={theme}
            />
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Switch
              label="Real-time Latency & Token HUD"
              checked={telemetryHud}
              onChange={setTelemetryHud}
              theme={theme}
            />
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "0.5rem" }}>
            <button
              onClick={() => setIsSettingsOpen(false)}
              style={{
                background: theme.bgElevated,
                border: `1px solid ${theme.borderSubtle}`,
                color: theme.textBright,
                padding: "0.5rem 1rem",
                borderRadius: "8px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              onClick={() => setIsSettingsOpen(false)}
              style={{
                background: `linear-gradient(135deg, ${theme.accent}, ${theme.accentPurple})`,
                color: "#000",
                border: "none",
                padding: "0.5rem 1.25rem",
                borderRadius: "8px",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Save Changes
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export default DesktopApp;
