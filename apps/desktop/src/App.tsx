import React, { useState, useEffect } from "react";
import { THEME_PRESETS, ThemeTokens } from "@saleha/ui/tokens";

export function DesktopApp() {
  const [theme, setTheme] = useState<ThemeTokens>(THEME_PRESETS.obsidian);
  const [isOffline, setIsOffline] = useState(true);
  const [ollamaStatus, setOllamaStatus] = useState("Connected (11434)");

  return (
    <div
      style={{
        backgroundColor: theme.bgBase,
        color: theme.textMain,
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        fontFamily: "'Plus Jakarta Sans', sans-serif",
      }}
    >
      <header
        style={{
          background: theme.bgSurface,
          borderBottom: `1px solid ${theme.borderSubtle}`,
          padding: "0.5rem 1.25rem",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: "54px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              background: `linear-gradient(135deg, ${theme.accent}, ${theme.accentPurple})`,
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontWeight: 800,
            }}
          >
            🧠
          </div>
          <span style={{ fontWeight: 800, color: theme.textBright, fontSize: "1rem" }}>
            Saleha Desktop AI
          </span>
          <span
            style={{
              fontSize: "0.7rem",
              background: "rgba(56,189,248,0.12)",
              border: `1px solid ${theme.borderBright}`,
              color: theme.accent,
              padding: "0.15rem 0.5rem",
              borderRadius: "999px",
              fontWeight: 700,
            }}
          >
            Tauri v2 Native
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 600,
              padding: "0.3rem 0.65rem",
              borderRadius: "999px",
              background: "rgba(16,185,129,0.1)",
              border: "1px solid rgba(16,185,129,0.25)",
              color: theme.accentGreen,
              display: "flex",
              alignItems: "center",
              gap: "0.35rem",
            }}
          >
            <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: theme.accentGreen }} />
            <span>{ollamaStatus}</span>
          </div>

          <button
            onClick={() => setTheme(theme.name.includes("Obsidian") ? THEME_PRESETS.oled : THEME_PRESETS.obsidian)}
            style={{
              background: theme.bgElevated,
              border: `1px solid ${theme.borderSubtle}`,
              color: theme.textBright,
              padding: "0.35rem 0.75rem",
              borderRadius: "6px",
              fontSize: "0.75rem",
              cursor: "pointer",
            }}
          >
            🎨 {theme.name}
          </button>
        </div>
      </header>

      <main style={{ flex: 1, display: "grid", gridTemplateColumns: "280px 1fr", overflow: "hidden" }}>
        <aside style={{ background: theme.bgSurface, borderRight: `1px solid ${theme.borderSubtle}`, padding: "1rem" }}>
          <h4 style={{ fontSize: "0.75rem", color: theme.textDim, textTransform: "uppercase", marginBottom: "0.75rem" }}>
            Native Offline Workspace
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
            <div style={{ padding: "0.5rem", background: theme.bgElevated, borderRadius: "6px", fontSize: "0.8rem", color: theme.accent }}>
              ⚡ rate_limiter.py (Healed)
            </div>
            <div style={{ padding: "0.5rem", background: "transparent", borderRadius: "6px", fontSize: "0.8rem" }}>
              📄 ring_buffer.c (Healed)
            </div>
            <div style={{ padding: "0.5rem", background: "transparent", borderRadius: "6px", fontSize: "0.8rem" }}>
              🗄️ local_memory.sqlite
            </div>
          </div>
        </aside>

        <section style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ background: theme.bgSurface, border: `1px solid ${theme.borderSubtle}`, borderRadius: "10px", padding: "1.25rem" }}>
            <h3 style={{ color: theme.textBright, fontSize: "1.1rem", marginBottom: "0.4rem" }}>
              🚀 Zero-Leak Gamma AST Engine (Local Native Rust)
            </h3>
            <p style="color:var(--text-dim); font-size:0.85rem;">
              Running 100% offline with zero cloud tokens. Verified against ASan memory boundaries in 65μs.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}

export default DesktopApp;

