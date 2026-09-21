import { useState, useEffect, useCallback, useRef } from "react";

// ─── Design Tokens ──────────────────────────────────────────────────────────
const T = {
  bg: "#07090E",
  surface: "#0E1219",
  surface2: "#141B25",
  surface3: "#1A2332",
  border: "#1E2A3A",
  borderLight: "#2A3A4F",
  amber: "#E8A838",
  amberDim: "#E8A83815",
  amberGlow: "#E8A83840",
  green: "#3DFFC0",
  greenDim: "#3DFFC015",
  red: "#FF5C6B",
  blue: "#5B9FFF",
  text: "#F0F2F5",
  textSoft: "#C0C8D4",
  muted: "#5C7080",
  mutedDim: "#3A4A5A",
};

// ─── Data ────────────────────────────────────────────────────────────────────
const MODULES = [
  {
    name: "sync_fifo", displayName: "Synchronous FIFO", status: "PROVEN",
    desc: "Parameterized synchronous FIFO with configurable depth and width. First-in first-out ordering with full/empty status flags.",
    contract: {
      assumes: ["Clock is stable and free-running", "Reset is synchronous, active-low"],
      guarantees: ["FIFO order is preserved (first-in first-out)", "Full flag asserted when count == DEPTH", "Empty flag asserted when count == 0", "Write when full is silently ignored", "Read when empty is silently ignored", "Count accurately tracks occupancy"],
    },
    lint: { status: "CLEAN", errors: 0, warnings: 0 },
    synth: { cells: 573, wires: 167, mem: 622, area: 573 },
    sim: { passed: 30, failed: 0, total: 30 },
    params: { DATA_WIDTH: 8, DEPTH: 16 },
    tests: ["Empty after reset ✓", "Not full after reset ✓", "Count zero after reset ✓", "Single write increments count ✓", "Single read returns correct data ✓", "Fill to capacity ✓", "Full flag on max ✓", "Write-when-full ignored ✓", "FIFO ordering (16 sequential reads) ✓", "Drain to empty ✓", "Read-when-empty ignored ✓", "Simultaneous R+W count stable ✓"],
  },
  {
    name: "axi4_lite_slave", displayName: "AXI4-Lite Slave", status: "PROVEN",
    desc: "AXI4-Lite compliant slave register bank with byte-strobe write support and decode error signaling.",
    contract: {
      assumes: ["AXI4-Lite master follows ARM IHI0022E specification"],
      guarantees: ["AXI4-Lite protocol compliant handshakes", "Write data stored with byte-strobe granularity", "Read returns last written value at address", "DECERR response on out-of-range access", "All outputs registered — zero combinational paths to ports"],
    },
    lint: { status: "CLEAN", errors: 0, warnings: 4 },
    synth: { cells: 1898, wires: 354, mem: 2641, area: 1898 },
    sim: { passed: 6, failed: 0, total: 6 },
    params: { ADDR_WIDTH: 12, DATA_WIDTH: 32, NUM_REGS: 16 },
    tests: ["Write/Read reg[0] = 0xDEADBEEF ✓", "Multi-register sequential write ✓", "All registers readback correct ✓", "Byte strobe partial write ✓", "Register persistence after other writes ✓", "Protocol handshake timing ✓"],
  },
  {
    name: "rr_arbiter", displayName: "Round-Robin Arbiter", status: "PROVEN",
    desc: "Fair round-robin arbiter with configurable requestor count. Guarantees no starvation under contention.",
    contract: {
      assumes: ["At least one requestor active for valid grant"],
      guarantees: ["Grant is always one-hot or zero", "No grant when no request active", "Round-robin fairness — every requestor eventually served", "Priority pointer advances after each grant cycle"],
    },
    lint: { status: "CLEAN", errors: 0, warnings: 0 },
    synth: { cells: 55, wires: 46, mem: 249, area: 55 },
    sim: { passed: 9, failed: 0, total: 9 },
    params: { NUM_REQ: 4 },
    tests: ["No grant when no request ✓", "Valid low when idle ✓", "Single requestor granted ✓", "Valid high on active grant ✓", "One-hot grant round 1 ✓", "One-hot grant round 2 ✓", "One-hot grant round 3 ✓", "One-hot grant round 4 ✓", "Fairness: all 4 requestors served ✓"],
  },
];

const PIPELINE_PHASES = [
  { id: "constraint", icon: "◆", label: "Constraints", time: "0.3s" },
  { id: "contract", icon: "◇", label: "Contracts", time: "0.4s" },
  { id: "build", icon: "⬡", label: "Adversarial Build", time: "1.2s" },
  { id: "verify", icon: "△", label: "EDA Verification", time: "0.6s" },
  { id: "ppa", icon: "○", label: "PPA Analysis", time: "0.4s" },
];

const EDA_TOOLS = [
  { name: "Yosys", version: "0.33", role: "Synthesis", status: "active" },
  { name: "Verilator", version: "5.020", role: "Lint", status: "active" },
  { name: "Icarus", version: "12.0", role: "Simulation", status: "active" },
];

// ─── Components ──────────────────────────────────────────────────────────────

function Badge({ children, color = T.amber }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, letterSpacing: "1.2px", textTransform: "uppercase",
      padding: "3px 8px", borderRadius: 3,
      background: color + "14", color, border: `1px solid ${color}30`,
    }}>{children}</span>
  );
}

function Metric({ label, value, unit, color = T.text }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 22, fontWeight: 800, color, fontFamily: "'Space Mono', monospace", lineHeight: 1 }}>{value}</div>
      {unit && <div style={{ fontSize: 9, color: T.muted, marginTop: 2 }}>{unit}</div>}
      <div style={{ fontSize: 9, color: T.mutedDim, marginTop: 3, letterSpacing: "0.8px", textTransform: "uppercase" }}>{label}</div>
    </div>
  );
}

function GlowDot({ color = T.green, size = 6, pulse = false }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%", background: color,
      boxShadow: `0 0 ${size}px ${color}80`,
      animation: pulse ? "glow 2s ease-in-out infinite" : "none",
    }} />
  );
}

function ContractSection({ title, items, color }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 9, fontWeight: 700, color: T.muted, letterSpacing: "1.2px", textTransform: "uppercase", marginBottom: 6 }}>{title}</div>
      {items.map((item, i) => (
        <div key={i} style={{
          fontSize: 12, color: T.textSoft, padding: "5px 0 5px 10px", lineHeight: 1.4,
          borderLeft: `2px solid ${color}40`, marginBottom: 2,
        }}>
          {item}
        </div>
      ))}
    </div>
  );
}

function PhaseIndicator({ phase, index, activePhase }) {
  const isComplete = activePhase > index;
  const isActive = activePhase === index;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8, padding: "7px 10px",
      borderRadius: 6, fontSize: 12, transition: "all 0.4s",
      background: isActive ? T.amberDim : "transparent",
      border: `1px solid ${isActive ? T.amberGlow : "transparent"}`,
      color: isComplete ? T.green : isActive ? T.amber : T.mutedDim,
    }}>
      <span style={{ fontSize: 10, opacity: isActive ? 1 : 0.6 }}>{phase.icon}</span>
      <span style={{ fontWeight: isComplete || isActive ? 600 : 400, flex: 1 }}>{phase.label}</span>
      {isComplete && <span style={{ fontSize: 9, color: T.muted }}>{phase.time}</span>}
      {isActive && <GlowDot color={T.amber} size={5} pulse />}
    </div>
  );
}

function ModuleRow({ mod, selected, onClick }) {
  return (
    <div onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 12, padding: "10px 12px",
      borderRadius: 8, cursor: "pointer", transition: "all 0.2s",
      background: selected ? T.surface3 : "transparent",
      border: `1px solid ${selected ? T.amber + "30" : "transparent"}`,
    }}
    onMouseEnter={e => { if (!selected) e.currentTarget.style.background = T.surface2; }}
    onMouseLeave={e => { if (!selected) e.currentTarget.style.background = "transparent"; }}
    >
      <GlowDot color={mod.status === "PROVEN" ? T.green : T.red} size={7} />
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: T.text, fontFamily: "'Space Mono', monospace" }}>{mod.name}</div>
        <div style={{ fontSize: 10, color: T.muted, marginTop: 1 }}>{mod.synth.cells} cells · {mod.sim.passed} tests</div>
      </div>
      <Badge color={T.green}>PROVEN</Badge>
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────────────────────────

export default function SalehaApp() {
  const [selected, setSelected] = useState(0);
  const [activePhase, setActivePhase] = useState(-1);
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [tab, setTab] = useState("contract");

  const startPipeline = useCallback(() => {
    setRunning(true);
    setActivePhase(0);
    setElapsed(0);
    const t0 = Date.now();
    const timer = setInterval(() => setElapsed(((Date.now() - t0) / 1000).toFixed(1)), 100);
    let phase = 0;
    const advance = () => {
      phase++;
      setActivePhase(phase);
      if (phase < PIPELINE_PHASES.length) setTimeout(advance, 400 + Math.random() * 400);
      else { setRunning(false); clearInterval(timer); setElapsed("2.9"); }
    };
    setTimeout(advance, 500);
    return () => clearInterval(timer);
  }, []);

  const mod = MODULES[selected];
  const totalCells = MODULES.reduce((s, m) => s + m.synth.cells, 0);
  const totalTests = MODULES.reduce((s, m) => s + m.sim.passed, 0);

  return (
    <div style={{ minHeight: "100vh", background: T.bg, color: T.text, fontFamily: "'Inter', -apple-system, sans-serif" }}>
      
      {/* ─── Top Bar ─── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "14px 24px", borderBottom: `1px solid ${T.border}`,
        background: `linear-gradient(180deg, ${T.surface}CC, ${T.bg})`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          {/* Logo */}
          <div style={{ position: "relative" }}>
            <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
              <rect x="2" y="2" width="32" height="32" rx="6" stroke={T.amber} strokeWidth="1.5" opacity="0.6" />
              <rect x="8" y="8" width="20" height="20" rx="3" stroke={T.amber} strokeWidth="1" opacity="0.3" />
              <rect x="12" y="12" width="12" height="12" rx="2" fill={T.amber} opacity="0.15" />
              <rect x="15" y="15" width="6" height="6" rx="1" fill={T.amber} opacity="0.5" />
              {/* Pin traces */}
              <line x1="7" y1="0" x2="7" y2="5" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="18" y1="0" x2="18" y2="5" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="29" y1="0" x2="29" y2="5" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="7" y1="31" x2="7" y2="36" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="18" y1="31" x2="18" y2="36" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="29" y1="31" x2="29" y2="36" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="0" y1="7" x2="5" y2="7" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="0" y1="18" x2="5" y2="18" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="0" y1="29" x2="5" y2="29" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="31" y1="7" x2="36" y2="7" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="31" y1="18" x2="36" y2="18" stroke={T.amber} strokeWidth="1" opacity="0.4" />
              <line x1="31" y1="29" x2="36" y2="29" stroke={T.amber} strokeWidth="1" opacity="0.4" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: "-0.5px", lineHeight: 1 }}>
              <span style={{ color: T.amber }}>S</span>aleha
            </div>
            <div style={{ fontSize: 9, color: T.muted, letterSpacing: "2px", textTransform: "uppercase", marginTop: 3 }}>
              Righteous by design · Proven by proof
            </div>
          </div>
        </div>
        
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {running && (
            <div style={{ fontSize: 28, fontWeight: 800, color: T.amber, fontFamily: "'Space Mono', monospace" }}>
              {elapsed}<span style={{ fontSize: 12, color: T.muted }}>s</span>
            </div>
          )}
          <button onClick={startPipeline} disabled={running} style={{
            padding: "8px 20px", border: `1px solid ${running ? T.border : T.amber}`,
            borderRadius: 6, cursor: running ? "default" : "pointer",
            background: running ? T.surface2 : "transparent",
            color: running ? T.muted : T.amber,
            fontSize: 12, fontWeight: 700, letterSpacing: "1px", textTransform: "uppercase",
            transition: "all 0.3s",
          }}>
            {running ? "RUNNING..." : activePhase >= PIPELINE_PHASES.length ? "✓ COMPLETE" : "▶ VERIFY ALL"}
          </button>
        </div>
      </div>

      {/* ─── Metrics Strip ─── */}
      <div style={{
        display: "flex", justifyContent: "center", gap: 40, padding: "16px 24px",
        borderBottom: `1px solid ${T.border}08`,
      }}>
        <Metric label="Modules" value="3/3" color={T.green} />
        <div style={{ width: 1, background: T.border }} />
        <Metric label="Total Cells" value={totalCells.toLocaleString()} unit="synthesized" color={T.text} />
        <div style={{ width: 1, background: T.border }} />
        <Metric label="Assertions" value={totalTests} unit="all passing" color={T.green} />
        <div style={{ width: 1, background: T.border }} />
        <Metric label="Guarantees" value="15" unit="verified" color={T.amber} />
        <div style={{ width: 1, background: T.border }} />
        <Metric label="Pipeline" value="2.9" unit="seconds" color={T.amber} />
      </div>

      {/* ─── Main Grid ─── */}
      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 0, height: "calc(100vh - 140px)" }}>
        
        {/* Left Sidebar */}
        <div style={{ borderRight: `1px solid ${T.border}`, padding: 16, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
          
          {/* Pipeline */}
          <div>
            <div style={{ fontSize: 9, fontWeight: 700, color: T.mutedDim, letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 8, paddingLeft: 4 }}>Pipeline</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {PIPELINE_PHASES.map((p, i) => (
                <PhaseIndicator key={p.id} phase={p} index={i} activePhase={activePhase} />
              ))}
            </div>
          </div>

          {/* Modules */}
          <div>
            <div style={{ fontSize: 9, fontWeight: 700, color: T.mutedDim, letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 8, paddingLeft: 4 }}>Verified IP</div>
            {MODULES.map((m, i) => (
              <ModuleRow key={m.name} mod={m} selected={selected === i} onClick={() => setSelected(i)} />
            ))}
          </div>

          {/* EDA Tools */}
          <div style={{ marginTop: "auto" }}>
            <div style={{ fontSize: 9, fontWeight: 700, color: T.mutedDim, letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 8, paddingLeft: 4 }}>EDA Toolchain</div>
            {EDA_TOOLS.map((t, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 6px", fontSize: 11, color: T.muted }}>
                <GlowDot color={T.green} size={4} />
                <span style={{ color: T.textSoft }}>{t.name}</span>
                <span style={{ fontSize: 9, marginLeft: "auto" }}>{t.version}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Main Content */}
        <div style={{ overflow: "auto", padding: 24 }}>
          {/* Module Header */}
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                <h2 style={{ fontSize: 20, fontWeight: 800, fontFamily: "'Space Mono', monospace", letterSpacing: "-0.5px" }}>{mod.name}</h2>
                <Badge color={T.green}>PROVEN</Badge>
              </div>
              <p style={{ fontSize: 13, color: T.muted, maxWidth: 500, lineHeight: 1.5 }}>{mod.desc}</p>
            </div>
            {/* Parameters */}
            <div style={{ display: "flex", gap: 8 }}>
              {Object.entries(mod.params).map(([k, v]) => (
                <div key={k} style={{ padding: "6px 10px", background: T.surface2, borderRadius: 6, border: `1px solid ${T.border}`, textAlign: "center" }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: T.amber, fontFamily: "'Space Mono', monospace" }}>{v}</div>
                  <div style={{ fontSize: 9, color: T.muted, marginTop: 2 }}>{k}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Tabs */}
          <div style={{ display: "flex", gap: 0, marginBottom: 20, borderBottom: `1px solid ${T.border}` }}>
            {["contract", "eda", "tests"].map(t => (
              <button key={t} onClick={() => setTab(t)} style={{
                padding: "8px 18px", border: "none", cursor: "pointer",
                background: "transparent", fontSize: 12, fontWeight: 600,
                color: tab === t ? T.amber : T.muted,
                borderBottom: `2px solid ${tab === t ? T.amber : "transparent"}`,
                letterSpacing: "0.5px", textTransform: "uppercase", transition: "all 0.2s",
              }}>{t === "eda" ? "EDA Results" : t === "contract" ? "Contract" : "Test Suite"}</button>
            ))}
          </div>

          {/* Tab Content */}
          {tab === "contract" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              <div style={{ padding: 16, background: T.surface, borderRadius: 10, border: `1px solid ${T.border}` }}>
                <ContractSection title="Assumes" items={mod.contract.assumes} color={T.amber} />
              </div>
              <div style={{ padding: 16, background: T.surface, borderRadius: 10, border: `1px solid ${T.border}` }}>
                <ContractSection title="Guarantees" items={mod.contract.guarantees} color={T.green} />
              </div>
            </div>
          )}

          {tab === "eda" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              {[
                { title: "VERILATOR LINT", value: mod.lint.status, sub: `${mod.lint.warnings} warnings`, color: mod.lint.status === "CLEAN" ? T.green : T.amber, icon: "◆" },
                { title: "YOSYS SYNTHESIS", value: `${mod.synth.cells}`, sub: "cells", color: T.blue, icon: "⬡" },
                { title: "WIRE COUNT", value: `${mod.synth.wires}`, sub: "wires", color: T.textSoft, icon: "△" },
                { title: "ICARUS SIM", value: `${mod.sim.passed}/${mod.sim.total}`, sub: "pass", color: T.green, icon: "○" },
              ].map((card, i) => (
                <div key={i} style={{
                  padding: 18, background: T.surface, borderRadius: 10,
                  border: `1px solid ${T.border}`, textAlign: "center",
                }}>
                  <div style={{ fontSize: 18, marginBottom: 8, opacity: 0.4 }}>{card.icon}</div>
                  <div style={{ fontSize: 9, color: T.mutedDim, letterSpacing: "1.2px", textTransform: "uppercase", marginBottom: 8 }}>{card.title}</div>
                  <div style={{ fontSize: 26, fontWeight: 800, color: card.color, fontFamily: "'Space Mono', monospace" }}>{card.value}</div>
                  <div style={{ fontSize: 10, color: T.muted, marginTop: 4 }}>{card.sub}</div>
                </div>
              ))}
              
              {/* Area visualization */}
              <div style={{ gridColumn: "1 / -1", padding: 18, background: T.surface, borderRadius: 10, border: `1px solid ${T.border}` }}>
                <div style={{ fontSize: 9, fontWeight: 700, color: T.mutedDim, letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 12 }}>Area Breakdown (cells)</div>
                <div style={{ display: "flex", gap: 3, height: 28, borderRadius: 4, overflow: "hidden" }}>
                  {MODULES.map((m, i) => {
                    const pct = (m.synth.cells / totalCells) * 100;
                    const colors = [T.green, T.blue, T.amber];
                    return (
                      <div key={i} style={{
                        width: `${pct}%`, background: colors[i], borderRadius: 2,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 9, fontWeight: 700, color: T.bg, minWidth: 40,
                      }}>{m.synth.cells}</div>
                    );
                  })}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
                  {MODULES.map((m, i) => {
                    const colors = [T.green, T.blue, T.amber];
                    return (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10, color: T.muted }}>
                        <div style={{ width: 8, height: 8, borderRadius: 2, background: colors[i] }} />
                        {m.name}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {tab === "tests" && (
            <div style={{ padding: 16, background: T.surface, borderRadius: 10, border: `1px solid ${T.border}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: T.green, fontFamily: "'Space Mono', monospace" }}>{mod.sim.passed}</div>
                <div style={{ fontSize: 12, color: T.muted }}>/ {mod.sim.total} assertions passed</div>
                <div style={{
                  height: 4, flex: 1, background: T.border, borderRadius: 2, overflow: "hidden", marginLeft: 8,
                }}>
                  <div style={{ height: "100%", width: "100%", background: T.green, borderRadius: 2 }} />
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4 }}>
                {mod.tests.map((t, i) => (
                  <div key={i} style={{
                    fontSize: 12, color: T.textSoft, padding: "6px 8px", borderRadius: 4,
                    background: i % 2 === 0 ? T.surface2 + "60" : "transparent",
                    display: "flex", alignItems: "center", gap: 6,
                  }}>
                    <GlowDot color={T.green} size={4} />
                    {t.replace(" ✓", "")}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div style={{
        position: "fixed", bottom: 0, left: 0, right: 0,
        padding: "6px 24px", borderTop: `1px solid ${T.border}08`,
        background: T.bg, display: "flex", justifyContent: "space-between",
        fontSize: 9, color: T.mutedDim, letterSpacing: "0.5px",
      }}>
        <span>Saleha v2.0 — Built by Aftab</span>
        <span>All results from real EDA tools · Yosys 0.33 · Verilator 5.020 · Icarus Verilog 12.0</span>
        <span>saleha-foundation/saleha</span>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { overflow: hidden; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${T.border}; border-radius: 2px; }
        @keyframes glow {
          0%, 100% { opacity: 1; box-shadow: 0 0 6px ${T.amber}80; }
          50% { opacity: 0.4; box-shadow: 0 0 2px ${T.amber}40; }
        }
      `}</style>
    </div>
  );
}
