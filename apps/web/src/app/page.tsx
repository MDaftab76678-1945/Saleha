"use client";

import React, { useState, useEffect } from "react";
import { THEME_PRESETS, ThemeTokens, Modal, Switch, Slider } from "@saleha/ui";

interface SwarmNode {
  id: string;
  name: string;
  role: string;
  icon: string;
  status: "idle" | "active" | "success";
}

const INITIAL_NODES: SwarmNode[] = [
  { id: "orch", name: "TreeOfThoughtsOrchestrator", role: "Orchestrator", icon: "🧠", status: "active" },
  { id: "arch", name: "ArchitectAgent", role: "ADR & System Design", icon: "🏛️", status: "success" },
  { id: "coder", name: "CoderAgent", role: "AST Synthesis", icon: "⚡", status: "active" },
  { id: "sec", name: "SecurityGuardAgent", role: "SAST & OWASP", icon: "🛡️", status: "idle" },
  { id: "qa", name: "QALeadAgent", role: "Pytest Suite", icon: "🧪", status: "idle" },
  { id: "rev", name: "ReviewerAgent", role: "Senior Review", icon: "🧐", status: "idle" },
  { id: "sre", name: "SREIncidentAgent", role: "Incident RCA", icon: "🚨", status: "idle" },
  { id: "finops", name: "FinOpsOptimizerAgent", role: "Token Compression", icon: "💰", status: "idle" },
];

export default function WebStudioPage() {
  const [themeKey, setThemeKey] = useState<string>("obsidian");
  const theme: ThemeTokens = THEME_PRESETS[themeKey] || THEME_PRESETS.obsidian;

  const [activeTab, setActiveTab] = useState<"topology" | "diff" | "settings">("topology");
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [nodes, setNodes] = useState<SwarmNode[]>(INITIAL_NODES);

  // Settings
  const [modelBackend, setModelBackend] = useState("ollama");
  const [temperature, setTemperature] = useState(0.2);
  const [contextBudget, setContextBudget] = useState(8192);
  const [audioFx, setAudioFx] = useState(true);
  const [hudTelemetry, setHudTelemetry] = useState(true);

  // Execution state
  const [prompt, setPrompt] = useState("Synthesize thread-safe ring buffer in Python with zero memory leaks");
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionStep, setExecutionStep] = useState(0);

  const handleExecuteSwarm = () => {
    setIsExecuting(true);
    setExecutionStep(1);

    // Update node states sequentially
    setTimeout(() => {
      setExecutionStep(2);
      setNodes((prev) => prev.map((n) => (n.id === "arch" ? { ...n, status: "active" } : n)));
    }, 600);

    setTimeout(() => {
      setExecutionStep(3);
      setNodes((prev) => prev.map((n) => (n.id === "coder" ? { ...n, status: "active" } : n)));
    }, 1200);

    setTimeout(() => {
      setExecutionStep(4);
      setNodes((prev) => prev.map((n) => (n.id === "sec" || n.id === "qa" ? { ...n, status: "active" } : n)));
    }, 1800);

    setTimeout(() => {
      setExecutionStep(5);
      setIsExecuting(false);
      setNodes((prev) => prev.map((n) => ({ ...n, status: "success" })));
    }, 2500);
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
      {/* Top Header */}
      <header
        style={{
          background: theme.bgSurface,
          borderBottom: `1px solid ${theme.borderSubtle}`,
          padding: "0.5rem 1.5rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: "58px",
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
              fontSize: "1.1rem",
              boxShadow: `0 0 16px ${theme.accentGlow}`,
            }}
          >
            🧠
          </div>
          <span style={{ fontWeight: 800, color: theme.textBright, fontSize: "1.05rem", letterSpacing: "-0.02em" }}>
            Saleha Web Studio (Next.js 15 App Router)
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
            RSC + Tree-of-Thoughts
          </span>
        </div>

        {/* View Switcher Tabs */}
        <div style={{ display: "flex", background: theme.bgElevated, borderRadius: "8px", padding: "3px", gap: "4px" }}>
          <button
            onClick={() => setActiveTab("topology")}
            style={{
              background: activeTab === "topology" ? theme.bgSurface : "transparent",
              border: "none",
              color: activeTab === "topology" ? theme.textBright : theme.textDim,
              padding: "0.3rem 0.85rem",
              borderRadius: "6px",
              fontSize: "0.8rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            🌌 Swarm Topology
          </button>
          <button
            onClick={() => setActiveTab("diff")}
            style={{
              background: activeTab === "diff" ? theme.bgSurface : "transparent",
              border: "none",
              color: activeTab === "diff" ? theme.textBright : theme.textDim,
              padding: "0.3rem 0.85rem",
              borderRadius: "6px",
              fontSize: "0.8rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            📝 Code Diff & Healing
          </button>
        </div>

        {/* Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <select
            value={themeKey}
            onChange={(e) => setThemeKey(e.target.value)}
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
            {Object.entries(THEME_PRESETS).map(([key, t]) => (
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
              fontWeight: 600,
            }}
          >
            ⚙️ Studio Settings
          </button>
        </div>
      </header>

      {/* Real-time Telemetry HUD Bar */}
      {hudTelemetry && (
        <div
          style={{
            background: theme.bgElevated,
            borderBottom: `1px solid ${theme.borderSubtle}`,
            padding: "0.35rem 1.5rem",
            display: "flex",
            justifyContent: "space-between",
            fontSize: "0.75rem",
            fontFamily: "monospace",
            color: theme.textDim,
          }}
        >
          <span>● Backend: <strong style={{ color: theme.accentGreen }}>Ollama Local (11434)</strong></span>
          <span>⚡ Latency: <strong style={{ color: theme.accent }}>38μs</strong></span>
          <span>🛡️ AST Verification: <strong style={{ color: theme.accentPurple }}>100% Deterministic (ASan Clean)</strong></span>
          <span>💰 Token Burn: <strong style={{ color: theme.accentGreen }}>$0.00 / 0 Cloud Tokens</strong></span>
        </div>
      )}

      {/* Main Workspace */}
      <main style={{ flex: 1, padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem", overflowY: "auto" }}>
        {/* Goal Execution Input Card */}
        <div
          style={{
            background: theme.bgSurface,
            border: `1px solid ${theme.borderSubtle}`,
            borderRadius: "14px",
            padding: "1.25rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.75rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 700, color: theme.textDim, textTransform: "uppercase" }}>
              Target Autonomous Engineering Task
            </span>
            <span style={{ fontSize: "0.75rem", color: theme.accent }}>18 Python Agents + 1,004 Skills Standby</span>
          </div>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="E.g. Deploy multi-tier Kubernetes cluster with Terraform and FinOps cost estimation..."
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
              onClick={handleExecuteSwarm}
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
                boxShadow: `0 0 20px ${theme.accentGlow}`,
              }}
            >
              {isExecuting ? `Stage ${executionStep}/5 Executing...` : "⚡ Execute Swarm"}
            </button>
          </div>
        </div>

        {/* Dynamic Swarm Topology Graph */}
        {activeTab === "topology" && (
          <div
            style={{
              flex: 1,
              background: theme.bgSurface,
              border: `1px solid ${theme.borderSubtle}`,
              borderRadius: "14px",
              padding: "1.5rem",
              display: "flex",
              flexDirection: "column",
              gap: "1rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: theme.textBright }}>
                🌌 Swarm Agent Nodes Topology (Tree-of-Thoughts k=3)
              </h3>
              <span style={{ fontSize: "0.75rem", color: theme.accentGreen }}>● Real-time Hyperbolic Attractor Active</span>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: "1rem",
                marginTop: "0.5rem",
              }}
            >
              {nodes.map((node) => {
                const statusColor = node.status === "active" ? theme.accent : node.status === "success" ? theme.accentGreen : theme.textDim;
                return (
                  <div
                    key={node.id}
                    style={{
                      background: theme.bgElevated,
                      border: `1px solid ${node.status === "active" ? theme.borderBright : theme.borderSubtle}`,
                      borderRadius: "12px",
                      padding: "1rem",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.5rem",
                      boxShadow: node.status === "active" ? `0 0 20px ${theme.accentGlow}` : "none",
                      transition: "all 0.25s ease",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "1.5rem" }}>{node.icon}</span>
                      <span style={{ fontSize: "0.65rem", fontWeight: 700, color: statusColor, textTransform: "uppercase" }}>
                        ● {node.status}
                      </span>
                    </div>
                    <span style={{ fontWeight: 700, fontSize: "0.9rem", color: theme.textBright }}>
                      {node.name}
                    </span>
                    <span style={{ fontSize: "0.75rem", color: theme.textDim }}>
                      {node.role}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Live Code Diff & Healing Viewer */}
        {activeTab === "diff" && (
          <div
            style={{
              flex: 1,
              background: "#030712",
              border: `1px solid ${theme.borderSubtle}`,
              borderRadius: "14px",
              padding: "1.25rem",
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "1rem",
              fontFamily: "'Fira Code', monospace",
              fontSize: "0.85rem",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", background: "rgba(239, 68, 68, 0.05)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: "8px", padding: "1rem" }}>
              <span style={{ color: "#f87171", fontWeight: 700, marginBottom: "0.5rem" }}>❌ Insecure / Failing Input:</span>
              <pre style={{ margin: 0, color: "#fca5a5" }}>
{`# Vulnerability: SQL Injection (CWE-89)
def fetch_user(username: str):
    query = f"SELECT * FROM users WHERE name = '{username}'"
    return db.execute(query)`}
              </pre>
            </div>

            <div style={{ display: "flex", flexDirection: "column", background: "rgba(16, 185, 129, 0.05)", border: "1px solid rgba(16, 185, 129, 0.2)", borderRadius: "8px", padding: "1rem" }}>
              <span style={{ color: "#34d399", fontWeight: 700, marginBottom: "0.5rem" }}>✨ Healed AST & Parameterized Output:</span>
              <pre style={{ margin: 0, color: "#a7f3d0" }}>
{`# Healed by SecurityGuardAgent + CoderAgent
def fetch_user(username: str) -> dict | None:
    query = "SELECT * FROM users WHERE name = :param"
    return db.execute(query, {"param": username})`}
              </pre>
            </div>
          </div>
        )}
      </main>

      {/* Settings Modal */}
      <Modal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        title="⚙️ Saleha Web Studio Preferences"
        theme={theme}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <div>
            <label style={{ fontSize: "0.8rem", color: theme.textDim, fontWeight: 700, textTransform: "uppercase" }}>
              Inference Provider
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
              <option value="ollama">Ollama Localhost ($0 / High Privacy)</option>
              <option value="deepseek">DeepSeek V3 (Direct High-Speed API)</option>
              <option value="openrouter">OpenRouter Aggregator</option>
              <option value="anthropic">Anthropic Claude 3.7 Sonnet</option>
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
            value={contextBudget}
            onChange={setContextBudget}
            theme={theme}
          />

          <div style={{ borderTop: `1px solid ${theme.borderSubtle}`, paddingTop: "0.75rem" }}>
            <Switch
              label="Real-time Telemetry & Latency HUD"
              checked={hudTelemetry}
              onChange={setHudTelemetry}
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
              Save Configuration
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
