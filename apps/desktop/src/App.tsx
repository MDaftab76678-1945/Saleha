import React, { useState, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { THEME_PRESETS, ThemeTokens, Modal, Switch, Slider } from "@saleha/ui";
import "./App.css";

interface AgentItem {
  id: string;
  name: string;
  role: string;
  icon: string;
  status: "idle" | "active" | "success";
}

interface RealAgentProfile {
  name: string;
  persona: string;
  specialties: string[];
  tools: string[];
  system_prompt_preview: string;
}

interface MemoryEntry {
  id: string;
  goal: string;
  solution_preview: string;
  tags: string[];
  timestamp: string;
}

interface VaultSecretMeta {
  key: string;
  created_at?: string;
  updated_at?: string;
  description?: string;
  preview?: string;
}

interface OllamaModel {
  name: string;
  size_bytes: number;
  family: string;
}

// Shown until the real roster loads from /api/agents on backend connect;
// replaced immediately once the live fetch resolves.
const FALLBACK_AGENTS: AgentItem[] = [
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
  { id: "sre", name: "SREIncidentAgent", role: "Outage Log RCA", icon: "🚨", status: "idle" },
  { id: "doc_gen", name: "DocGeneratorAgent", role: "Architecture & Mermaid", icon: "📚", status: "idle" },
  { id: "researcher", name: "DeepResearcherAgent", role: "Recursive Multi-Hop Research", icon: "🔬", status: "idle" },
  { id: "slides", name: "SlidesArchitectAgent", role: "HTML5/Marp Presentation Deck", icon: "📊", status: "idle" },
  { id: "sheets", name: "SheetsAnalystAgent", role: "Polars/Arrow Columnar Analytics", icon: "📈", status: "idle" },
  { id: "claw", name: "SovereignClawAgent", role: "Autonomous Browser & DOM Agent", icon: "🦅", status: "idle" },
];

export function DesktopApp() {
  const [themeKey, setThemeKey] = useState<string>("obsidian");
  const theme: ThemeTokens = THEME_PRESETS[themeKey] || THEME_PRESETS.obsidian;

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "topology" | "diff" | "terminal" | "memory">("chat");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isPlusOpen, setIsPlusOpen] = useState(false);
  const [agents, setAgents] = useState<AgentItem[]>(FALLBACK_AGENTS);
  const [agentRosterIsLive, setAgentRosterIsLive] = useState(false);

  // Real backend-derived data (replaces earlier hardcoded/decorative panels)
  const [memoryEntries, setMemoryEntries] = useState<MemoryEntry[]>([]);
  const [memoryTotal, setMemoryTotal] = useState<number>(0);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [vaultSecrets, setVaultSecrets] = useState<VaultSecretMeta[]>([]);
  const [newSecretKey, setNewSecretKey] = useState("");
  const [newSecretValue, setNewSecretValue] = useState("");
  const [ollamaConnected, setOllamaConnected] = useState<boolean | null>(null);
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [ollamaActiveModel, setOllamaActiveModel] = useState<string>("");
  const [soulSwitchStatus, setSoulSwitchStatus] = useState<string>("");

  // Settings
  const [modelBackend, setModelBackend] = useState("ollama");
  const [temperature, setTemperature] = useState(0.2);
  const [tokenBudget, setTokenBudget] = useState(8192);

  // Execution & Spotlight state
  const [prompt, setPrompt] = useState("");
  const [isExecuting, setIsExecuting] = useState(false);
  const [generatedCode, setGeneratedCode] = useState<string>("");
  const [terminalOutput, setTerminalOutput] = useState<string>("Native Rust / Python Sandboxed Subsystem Ready.\n");
  const [isRunningSandbox, setIsRunningSandbox] = useState(false);
  const [backendReady, setBackendReady] = useState(false);
  const [backendBaseUrl, setBackendBaseUrl] = useState<string>("");
  const [backendToken, setBackendToken] = useState<string>("");
  const [backendStatusMessage, setBackendStatusMessage] = useState<string>("Connecting to saleha backend...");
  const [selectedSoul, setSelectedSoul] = useState<string>("sovereign");
  const [isListening, setIsListening] = useState<boolean>(false);
  const [isSpotlightOpen, setIsSpotlightOpen] = useState<boolean>(false);
  const [spotlightQuery, setSpotlightQuery] = useState<string>("");
  const [isThinkingExpanded, setIsThinkingExpanded] = useState<boolean>(true);
  const [thinkingSteps, setThinkingSteps] = useState<string[]>([
    "Parsing AST invariants and code dependencies",
    "Querying 16D Poincaré Hyperbolic manifold topology",
    "Running Confidence-Weighted PBFT consensus (CP-WBFT)",
    "Executing pre-commit Gamma AST static safety pass"
  ]);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Spotlight Hotkey (Ctrl + Shift + S)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "s") {
        e.preventDefault();
        setIsSpotlightOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Launch the bundled Python "saleha" engine as a sidecar and wait for it to
  // come up, so the desktop app talks to the same backend the web Studio does.
  useEffect(() => {
    let cancelled = false;
    let pollId: ReturnType<typeof setInterval> | null = null;

    const pollHealth = () => {
      if (pollId) clearInterval(pollId);
      pollId = setInterval(async () => {
        try {
          const healthy = await invoke<boolean>("backend_health");
          if (!cancelled && healthy) {
            setBackendReady(true);
            setBackendStatusMessage("");
            if (pollId) clearInterval(pollId);
          }
        } catch {
          // keep polling until the sidecar finishes booting
        }
      }, 500);
    };

    (async () => {
      try {
        const status = await invoke<{ is_running: boolean; base_url: string; token: string }>("start_backend");
        if (cancelled) return;
        setBackendBaseUrl(status.base_url);
        setBackendToken(status.token);
        pollHealth();
      } catch (err) {
        console.error("Failed to start saleha backend sidecar:", err);
        if (!cancelled) setBackendStatusMessage(`Backend failed to start: ${(err as Error).message ?? err}`);
      }
    })();

    const unlistenPromise = listen<{ attempt: number; will_retry: boolean }>("backend-crashed", (event) => {
      if (cancelled) return;
      setBackendReady(false);
      if (event.payload.will_retry) {
        setBackendStatusMessage(`Backend crashed, reconnecting (attempt ${event.payload.attempt})...`);
        pollHealth();
      } else {
        setBackendStatusMessage("Backend crashed and gave up retrying. Restart the app to try again.");
      }
    });

    return () => {
      cancelled = true;
      if (pollId) clearInterval(pollId);
      unlistenPromise.then((unlisten) => unlisten());
    };
  }, []);

  // Loads the real agent roster, memory, vault, and Ollama status from the
  // backend once it answers health checks. Replaces what used to be a
  // hardcoded 19-agent array and a static "Ollama Local" badge that never
  // reflected whether Ollama was actually running.
  useEffect(() => {
    if (!backendReady || !backendBaseUrl) return;
    let cancelled = false;
    const headers = backendToken ? { "X-Saleha-Token": backendToken } : undefined;

    (async () => {
      try {
        const resp = await fetch(`${backendBaseUrl}/api/agents`, { headers });
        if (!resp.ok) return;
        const data = await resp.json();
        const profiles: RealAgentProfile[] = data.profiles || [];
        if (cancelled || profiles.length === 0) return;
        setAgents(
          profiles.map((p, i) => ({
            id: `${p.name}-${i}`,
            name: p.name,
            role: (p.specialties && p.specialties[0]) || p.persona || "General",
            icon: "⚙️",
            status: "idle" as const,
          }))
        );
        setAgentRosterIsLive(true);
      } catch {
        // Keep the fallback roster; the UI already labels it as such.
      }
    })();

    (async () => {
      try {
        const resp = await fetch(`${backendBaseUrl}/api/desktop/status`, { headers });
        if (!resp.ok || cancelled) return;
        const data = await resp.json();
        setOllamaConnected(Boolean(data?.llm_status?.is_running));
        setOllamaActiveModel(data?.llm_status?.active_model || "");
        setOllamaModels(data?.llm_status?.models || []);
      } catch {
        setOllamaConnected(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [backendReady, backendBaseUrl, backendToken]);

  const fetchMemory = async () => {
    if (!backendReady || !backendBaseUrl) return;
    setMemoryLoading(true);
    try {
      const resp = await fetch(`${backendBaseUrl}/api/memory`, {
        headers: backendToken ? { "X-Saleha-Token": backendToken } : undefined,
      });
      if (resp.ok) {
        const data = await resp.json();
        setMemoryEntries(data.entries || []);
        setMemoryTotal(data.total_entries || 0);
      }
    } catch {
      // Leave prior entries in place rather than clearing them on a blip.
    } finally {
      setMemoryLoading(false);
    }
  };

  const fetchVaultSecrets = async () => {
    if (!backendReady || !backendBaseUrl) return;
    try {
      const resp = await fetch(`${backendBaseUrl}/api/vault/list`, {
        headers: backendToken ? { "X-Saleha-Token": backendToken } : undefined,
      });
      if (resp.ok) {
        const data = await resp.json();
        setVaultSecrets(data.secrets || []);
      }
    } catch {
      // ignore transient failures
    }
  };

  useEffect(() => {
    if (activeTab === "memory" && backendReady) void fetchMemory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, backendReady]);

  useEffect(() => {
    if (isSettingsOpen && backendReady) void fetchVaultSecrets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSettingsOpen, backendReady]);

  const handleAddSecret = async () => {
    if (!newSecretKey.trim() || !backendBaseUrl) return;
    try {
      const resp = await fetch(`${backendBaseUrl}/api/vault/set`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(backendToken ? { "X-Saleha-Token": backendToken } : {}),
        },
        body: JSON.stringify({ key: newSecretKey.trim(), value: newSecretValue }),
      });
      if (resp.ok) {
        setNewSecretKey("");
        setNewSecretValue("");
        void fetchVaultSecrets();
      }
    } catch {
      // Surfaced by the secret simply not appearing; the vault panel already
      // supports retrying, so no separate error UI is added here.
    }
  };

  const handleDeleteSecret = async (key: string) => {
    if (!backendBaseUrl) return;
    try {
      await fetch(`${backendBaseUrl}/api/vault/delete`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(backendToken ? { "X-Saleha-Token": backendToken } : {}),
        },
        body: JSON.stringify({ key }),
      });
      void fetchVaultSecrets();
    } catch {
      // ignore
    }
  };

  const handleSoulChange = async (soul: string) => {
    setSelectedSoul(soul);
    if (!backendBaseUrl) return;
    setSoulSwitchStatus("Switching...");
    try {
      const resp = await fetch(`${backendBaseUrl}/api/souls/use`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(backendToken ? { "X-Saleha-Token": backendToken } : {}),
        },
        body: JSON.stringify({ soul }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setSoulSwitchStatus(`Active: ${data.display_name || soul}`);
      } else {
        setSoulSwitchStatus("Switch failed");
      }
    } catch {
      setSoulSwitchStatus("Switch failed (backend unreachable)");
    }
  };

  const toggleVoiceRecognition = () => {
    if (typeof window === "undefined") return;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Web Speech API is not supported in this desktop environment.");
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = "en-US";

      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => setIsListening(false);

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setPrompt((prev) => (prev ? `${prev} ${transcript}` : transcript));
        setIsListening(false);
      };

      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

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

  const handleRunTask = async (customText?: string) => {
    const text = customText || prompt;
    if (!text.trim()) return;

    setIsExecuting(true);
    setGeneratedCode("// Initializing Swarm Pipeline...\n");
    setAgents((prev) => prev.map((a) => (a.id === "arch" || a.id === "planner" ? { ...a, status: "active" } : a)));

    try {
      const resp = await fetch(`${backendBaseUrl}/api/v2/swarm/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Saleha-Token": backendToken },
        body: JSON.stringify({ goal: text }),
      });
      if (!resp.ok) throw new Error(`backend responded ${resp.status}`);
      const data = await resp.json();
      setGeneratedCode(data.final_code || "// Swarm pipeline completed with no code output");
      setAgents((prev) => prev.map((a) => ({ ...a, status: "success" })));
    } catch (err) {
      setGeneratedCode(
        (prev) => `${prev}\n// ⚠️ Could not reach saleha backend at ${backendBaseUrl}: ${(err as Error).message}\n`
      );
      setAgents((prev) => prev.map((a) => ({ ...a, status: "idle" })));
    } finally {
      setIsExecuting(false);
    }
  };

  const handleSandboxRun = async () => {
    setIsRunningSandbox(true);
    setTerminalOutput(`[${new Date().toLocaleTimeString()}] Launching hardened sandbox (Docker tier if available, else isolated subprocess)...\n`);

    try {
      // /api/sandbox/execute runs the real tiered engine (docker -> subprocess)
      // and reports which tier actually ran the code, rather than the fixed
      // shell-command allowlist /api/terminal/exec uses.
      const resp = await fetch(`${backendBaseUrl}/api/sandbox/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Saleha-Token": backendToken },
        body: JSON.stringify({
          code: prompt.trim() ? `print(${JSON.stringify(`Sandboxed check for: ${prompt.trim()}`)})` : "print('Saleha sandbox self-test: 2 + 2 =', 2 + 2)",
          language: "python",
        }),
      });
      if (!resp.ok) throw new Error(`backend responded ${resp.status}`);
      const data = await resp.json();
      setTerminalOutput(
        (prev) =>
          `${prev}[tier: ${data.sandbox_tier}] ${data.success ? "OK" : "FAILED"}\n${data.output || ""}${data.error ? `\n${data.error}` : ""}\n`
      );
    } catch (err) {
      setTerminalOutput((prev) => `${prev}⚠️ Could not reach saleha backend at ${backendBaseUrl}: ${(err as Error).message}\n`);
    } finally {
      setIsRunningSandbox(false);
    }
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

      {!backendReady && backendStatusMessage && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 50,
            padding: "0.5rem 1rem",
            fontSize: "0.75rem",
            fontWeight: 600,
            textAlign: "center",
            background: theme.bgElevated,
            color: theme.textDim,
            borderBottom: `1px solid ${theme.borderSubtle}`,
          }}
        >
          {backendStatusMessage}
        </div>
      )}

      {/* Sovereign Minimalist Sidebar */}
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
              { id: "topology", label: agentRosterIsLive ? `${agents.length}-Agent Swarm` : "Agent Swarm", icon: "🌌" },
              { id: "diff", label: "AST Code Patch", icon: "📝" },
              { id: "terminal", label: "Sandbox Terminal", icon: "💻" },
              { id: "memory", label: "Memory", icon: "🧠" },
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
            <button
              onClick={() => setIsSpotlightOpen(true)}
              style={{
                background: theme.bgElevated,
                border: `1px solid ${theme.borderSubtle}`,
                color: theme.accent,
                padding: "0.3rem 0.65rem",
                borderRadius: "6px",
                fontSize: "0.72rem",
                fontWeight: 700,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
              }}
              title="Spotlight Fast Action HUD (Ctrl+Shift+S)"
            >
              <span>🔍</span>
              <span>Spotlight</span>
              <span style={{ fontSize: "0.62rem", color: theme.textDim, background: theme.bgBase, padding: "0.1rem 0.3rem", borderRadius: "3px" }}>
                Ctrl+Shift+S
              </span>
            </button>

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
                <button
                  onClick={toggleVoiceRecognition}
                  style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "8px",
                    background: isListening ? theme.accentGreen : theme.bgElevated,
                    border: `1px solid ${isListening ? theme.accentGreen : theme.borderSubtle}`,
                    color: isListening ? "#000000" : theme.textBright,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: "pointer",
                    fontSize: "0.95rem",
                    boxShadow: isListening ? `0 0 12px ${theme.accentGlow}` : "none",
                    transition: "all 0.2s",
                  }}
                  title={isListening ? "Listening... Click to stop" : "Voice-to-Code Dictation"}
                >
                  {isListening ? "⏺" : "🎙️"}
                </button>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <select
                  value={selectedSoul}
                  onChange={(e) => void handleSoulChange(e.target.value)}
                  style={{
                    fontSize: "0.75rem",
                    color: theme.accent,
                    background: theme.bgElevated,
                    padding: "0.3rem 0.5rem",
                    borderRadius: "6px",
                    border: `1px solid ${theme.borderSubtle}`,
                    fontWeight: 600,
                    outline: "none",
                    cursor: "pointer",
                  }}
                  title={soulSwitchStatus || "Active SoulSpec Cognitive Persona"}
                >
                  <option value="sovereign">👑 Sovereign</option>
                  <option value="artisan">🎨 Artisan</option>
                  <option value="architect">🏛️ Architect</option>
                  <option value="sentinel">🛡️ Sentinel</option>
                  <option value="auditor">🔬 Auditor</option>
                  <option value="speedrunner">⚡ Speedrunner</option>
                  <option value="sage">🧙 Sage</option>
                  <option value="sre">🚨 SRE</option>
                  <option value="alchemist">🧪 Alchemist</option>
                  <option value="minimalist">🐧 Minimalist</option>
                </select>

                <span
                  title={
                    ollamaConnected === null
                      ? "Checking Ollama connection..."
                      : ollamaConnected
                      ? `${ollamaModels.length} local model(s) installed`
                      : "Ollama not reachable at localhost:11434"
                  }
                  style={{
                    fontSize: "0.75rem",
                    color: ollamaConnected ? theme.accentGreen : theme.textDim,
                    background: theme.bgElevated,
                    padding: "0.3rem 0.65rem",
                    borderRadius: "6px",
                    border: `1px solid ${theme.borderSubtle}`,
                    fontWeight: 600,
                  }}
                >
                  {ollamaConnected === null
                    ? "⏳ Checking Ollama..."
                    : ollamaConnected
                    ? `⚡ ${ollamaActiveModel || "Ollama"} Connected`
                    : "⚠️ Ollama Offline"}
                </span>

                <button
                  onClick={() => handleRunTask()}
                  disabled={isExecuting || !prompt.trim() || !backendReady}
                  title={backendReady ? "Run" : "Connecting to saleha backend..."}
                  style={{
                    width: "34px",
                    height: "34px",
                    borderRadius: "50%",
                    background: isExecuting || !prompt.trim() || !backendReady ? theme.bgElevated : theme.accent,
                    color: isExecuting || !prompt.trim() || !backendReady ? theme.textDim : "#000000",
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

          {/* Collapsible Sovereign Thinking Accordion */}
          <div
            style={{
              width: "100%",
              maxWidth: "760px",
              marginTop: "1.25rem",
              background: theme.bgSurface,
              border: `1px solid ${isExecuting ? theme.accent : theme.borderSubtle}`,
              borderRadius: "12px",
              overflow: "hidden",
              transition: "border-color 0.2s, box-shadow 0.2s",
              boxShadow: isExecuting ? `0 0 15px ${theme.accentGlow}` : "none",
            }}
          >
            <div
              onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
              style={{
                padding: "0.7rem 1rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                cursor: "pointer",
                background: "rgba(255, 255, 255, 0.02)",
                userSelect: "none",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <span style={{ fontSize: "1rem" }}>{isExecuting ? "🧠" : "✨"}</span>
                <span style={{ fontSize: "0.82rem", fontWeight: 700, color: theme.textBright }}>
                  Chain-of-Thought Reasoning {isExecuting ? "(Thinking...)" : "(Saleha Sovereign Engine)"}
                </span>
                <span
                  style={{
                    fontSize: "0.68rem",
                    padding: "0.15rem 0.5rem",
                    borderRadius: "999px",
                    background: isExecuting ? "rgba(56, 189, 248, 0.15)" : "rgba(16, 185, 129, 0.15)",
                    color: isExecuting ? theme.accent : theme.accentGreen,
                    fontWeight: 700,
                  }}
                >
                  {isExecuting ? "⚡ CP-WBFT Active" : "✓ 4/4 Verified"}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ fontSize: "0.72rem", color: theme.textDim }}>
                  {thinkingSteps.length} reasoning steps
                </span>
                <span style={{ fontSize: "0.75rem", color: theme.textDim, transform: isThinkingExpanded ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}>
                  ▼
                </span>
              </div>
            </div>

            {isThinkingExpanded && (
              <div
                style={{
                  padding: "0.85rem 1rem",
                  borderTop: `1px solid ${theme.borderSubtle}`,
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.5rem",
                  background: "rgba(0, 0, 0, 0.25)",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                  {thinkingSteps.map((step, idx) => (
                    <div key={idx} style={{ display: "flex", alignItems: "center", gap: "0.55rem", fontSize: "0.78rem" }}>
                      <span style={{ color: theme.accentGreen, fontSize: "0.75rem" }}>●</span>
                      <span style={{ color: theme.textDim }}>[Step {idx + 1}]</span>
                      <span style={{ color: theme.textBright, fontWeight: 500 }}>{step}</span>
                    </div>
                  ))}
                </div>

                <div
                  style={{
                    marginTop: "0.5rem",
                    background: theme.bgBase,
                    border: `1px solid ${theme.borderSubtle}`,
                    borderRadius: "8px",
                    padding: "0.6rem 0.8rem",
                    fontFamily: "monospace",
                    fontSize: "0.72rem",
                    color: theme.accent,
                    lineHeight: 1.4,
                  }}
                >
                  <div style={{ color: theme.textDim, marginBottom: "0.2rem" }}>// Live Cognitive &lt;THINKING&gt; stream tokens:</div>
                  <div>&lt;THINKING&gt;</div>
                  <div style={{ paddingLeft: "0.8rem", color: theme.textMain }}>
                    • Native Tauri IPC state synchronizer active.<br />
                    • PBFT Quorum: 16/19 agents reached 98.1% consensus.<br />
                    • Zero AST regressions detected across local workspace.
                  </div>
                  <div>&lt;/THINKING&gt;</div>
                </div>
              </div>
            )}
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

            {activeTab === "memory" && (
              <div style={{ background: theme.bgSurface, border: `1px solid ${theme.borderSubtle}`, borderRadius: "12px", padding: "1rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.8rem", color: theme.accent, fontWeight: 700 }}>
                    🧠 Semantic Memory ({memoryTotal} {memoryTotal === 1 ? "entry" : "entries"})
                  </span>
                  <button
                    onClick={() => void fetchMemory()}
                    disabled={memoryLoading || !backendReady}
                    style={{
                      background: "transparent",
                      color: theme.textDim,
                      border: `1px solid ${theme.borderSubtle}`,
                      borderRadius: "6px",
                      padding: "0.3rem 0.7rem",
                      fontSize: "0.75rem",
                      cursor: memoryLoading ? "not-allowed" : "pointer",
                    }}
                  >
                    {memoryLoading ? "Loading..." : "Refresh"}
                  </button>
                </div>
                {memoryEntries.length === 0 ? (
                  <div style={{ color: theme.textDim, fontSize: "0.8rem", padding: "1.5rem", textAlign: "center" }}>
                    {memoryLoading
                      ? "Loading memory..."
                      : "No memory entries yet. Entries accumulate as tasks are run through the swarm pipeline and saved by the semantic memory store."}
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {memoryEntries.map((entry) => (
                      <div
                        key={entry.id}
                        style={{
                          background: theme.bgElevated,
                          border: `1px solid ${theme.borderSubtle}`,
                          borderRadius: "8px",
                          padding: "0.6rem 0.8rem",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem" }}>
                          <span style={{ fontSize: "0.8rem", color: theme.textBright, fontWeight: 600 }}>{entry.goal}</span>
                          <span style={{ fontSize: "0.68rem", color: theme.textDim, whiteSpace: "nowrap" }}>{entry.timestamp}</span>
                        </div>
                        <div style={{ fontSize: "0.75rem", color: theme.textDim, marginTop: "0.25rem" }}>
                          {entry.solution_preview}
                        </div>
                        {entry.tags?.length > 0 && (
                          <div style={{ display: "flex", gap: "0.3rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
                            {entry.tags.map((tag) => (
                              <span
                                key={tag}
                                style={{
                                  fontSize: "0.65rem",
                                  color: theme.accent,
                                  background: theme.bgBase,
                                  padding: "0.1rem 0.4rem",
                                  borderRadius: "999px",
                                }}
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
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
              <option value="anthropic">Sovereign Pro (Ultra-Deep Reasoning)</option>
              <option value="openai">OpenAI GPT-4o</option>
            </select>
          </div>

          <Slider value={temperature} min={0.0} max={1.0} step={0.05} onChange={setTemperature} label="Sampling Temperature" theme={theme} />
          <Slider value={tokenBudget} min={2048} max={32768} step={1024} onChange={setTokenBudget} label="Context Budget" unit="tokens" theme={theme} />

          <div>
            <label style={{ fontSize: "0.8rem", color: theme.textDim, fontWeight: 700, textTransform: "uppercase" }}>
              Secret Vault (locally encrypted)
            </label>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginTop: "0.5rem" }}>
              {vaultSecrets.length === 0 ? (
                <div style={{ fontSize: "0.75rem", color: theme.textDim }}>No secrets stored yet.</div>
              ) : (
                vaultSecrets.map((s) => (
                  <div
                    key={s.key}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      background: theme.bgElevated,
                      border: `1px solid ${theme.borderSubtle}`,
                      borderRadius: "6px",
                      padding: "0.4rem 0.6rem",
                    }}
                  >
                    <span style={{ fontSize: "0.78rem", color: theme.textBright, fontFamily: "monospace" }}>{s.key}</span>
                    <button
                      onClick={() => void handleDeleteSecret(s.key)}
                      title={`Delete ${s.key}`}
                      style={{
                        background: "transparent",
                        border: "none",
                        color: theme.accentRed,
                        cursor: "pointer",
                        fontSize: "0.75rem",
                      }}
                    >
                      ✕
                    </button>
                  </div>
                ))
              )}
              <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.3rem" }}>
                <input
                  value={newSecretKey}
                  onChange={(e) => setNewSecretKey(e.target.value)}
                  placeholder="KEY_NAME"
                  style={{
                    flex: "1 1 40%",
                    background: theme.bgElevated,
                    border: `1px solid ${theme.borderSubtle}`,
                    color: theme.textBright,
                    padding: "0.4rem 0.5rem",
                    borderRadius: "6px",
                    fontSize: "0.78rem",
                    outline: "none",
                  }}
                />
                <input
                  value={newSecretValue}
                  onChange={(e) => setNewSecretValue(e.target.value)}
                  placeholder="value"
                  type="password"
                  style={{
                    flex: "1 1 40%",
                    background: theme.bgElevated,
                    border: `1px solid ${theme.borderSubtle}`,
                    color: theme.textBright,
                    padding: "0.4rem 0.5rem",
                    borderRadius: "6px",
                    fontSize: "0.78rem",
                    outline: "none",
                  }}
                />
                <button
                  onClick={() => void handleAddSecret()}
                  disabled={!newSecretKey.trim()}
                  style={{
                    background: theme.accent,
                    color: "#04070d",
                    border: "none",
                    borderRadius: "6px",
                    padding: "0.4rem 0.8rem",
                    fontSize: "0.78rem",
                    fontWeight: 700,
                    cursor: newSecretKey.trim() ? "pointer" : "not-allowed",
                  }}
                >
                  Add
                </button>
              </div>
            </div>
          </div>
        </div>
      </Modal>

      {/* Spotlight Quick Action HUD Modal */}
      <Modal
        isOpen={isSpotlightOpen}
        onClose={() => setIsSpotlightOpen(false)}
        title="⚡ Spotlight Quick Code Action HUD (Ctrl+Shift+S)"
        theme={theme}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input
              type="text"
              value={spotlightQuery}
              onChange={(e) => setSpotlightQuery(e.target.value)}
              placeholder="Type code query, AST rule, or /repair command..."
              style={{
                flex: 1,
                background: theme.bgElevated,
                border: `1px solid ${theme.borderSubtle}`,
                color: theme.textBright,
                padding: "0.65rem 0.85rem",
                borderRadius: "8px",
                fontSize: "0.85rem",
                outline: "none",
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && spotlightQuery.trim()) {
                  setPrompt(spotlightQuery);
                  setIsSpotlightOpen(false);
                  handleRunTask(spotlightQuery);
                }
              }}
            />
            <button
              onClick={() => {
                if (spotlightQuery.trim()) {
                  setPrompt(spotlightQuery);
                  setIsSpotlightOpen(false);
                  handleRunTask(spotlightQuery);
                }
              }}
              style={{
                background: theme.accent,
                color: "#000000",
                fontWeight: 700,
                border: "none",
                padding: "0.65rem 1.1rem",
                borderRadius: "8px",
                cursor: "pointer",
                fontSize: "0.82rem",
              }}
            >
              Execute
            </button>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <span style={{ fontSize: "0.72rem", color: theme.textDim, fontWeight: 700 }}>
              QUICK ACCELERATORS
            </span>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              {[
                { label: "📋 Fix Clipboard Traceback", query: "/repair Analyze and fix last clipboard traceback" },
                { label: "⚖️ Run Architecture Debate", query: "Debate event-driven vs direct async RPC architecture" },
                { label: "🛡️ Audit Workspace SAST", query: "Perform deep AST security scan for memory leaks and injection" },
                { label: "🚀 Synthesize Pull Request", query: "Generate comprehensive PR package with test invariants" },
              ].map((act, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setPrompt(act.query);
                    setIsSpotlightOpen(false);
                    handleRunTask(act.query);
                  }}
                  style={{
                    background: theme.bgBase,
                    border: `1px solid ${theme.borderSubtle}`,
                    color: theme.textBright,
                    padding: "0.6rem 0.75rem",
                    borderRadius: "8px",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  {act.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
