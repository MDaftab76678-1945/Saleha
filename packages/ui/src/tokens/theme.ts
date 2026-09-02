/**
 * @saleha/ui - Semantic Design Tokens & Theme Engine
 * Style Dictionary compliant tokens supporting 6 ultra-curated presets:
 * 1. Obsidian Dark Luxury (Default)
 * 2. Midnight OLED Titanium
 * 3. Cyberpunk Neon
 * 4. Aurora Emerald Glow
 * 5. Neon Matrix Terminal
 * 6. Hyper Light Minimalist
 */

export interface ThemeTokens {
  name: string;
  id: string;
  bgBase: string;
  bgSurface: string;
  bgElevated: string;
  bgHover: string;
  borderSubtle: string;
  borderBright: string;
  accent: string;
  accentGlow: string;
  accentPurple: string;
  accentGreen: string;
  accentAmber: string;
  accentRed: string;
  textBright: string;
  textMain: string;
  textDim: string;
  glassBlur: string;
}

export const THEME_PRESETS: Record<string, ThemeTokens> = {
  obsidian: {
    name: "Obsidian Dark Luxury",
    id: "obsidian",
    bgBase: "#06080d",
    bgSurface: "#0c101a",
    bgElevated: "#131929",
    bgHover: "#1b233a",
    borderSubtle: "rgba(255, 255, 255, 0.08)",
    borderBright: "rgba(56, 189, 248, 0.4)",
    accent: "#38bdf8",
    accentGlow: "rgba(56, 189, 248, 0.25)",
    accentPurple: "#818cf8",
    accentGreen: "#10b981",
    accentAmber: "#f59e0b",
    accentRed: "#ef4444",
    textBright: "#f8fafc",
    textMain: "#cbd5e1",
    textDim: "#64748b",
    glassBlur: "blur(20px)",
  },
  oled: {
    name: "Midnight OLED Titanium",
    id: "oled",
    bgBase: "#000000",
    bgSurface: "#080808",
    bgElevated: "#121212",
    bgHover: "#1c1c1c",
    borderSubtle: "rgba(255, 255, 255, 0.12)",
    borderBright: "#ffffff",
    accent: "#38bdf8",
    accentGlow: "rgba(56, 189, 248, 0.35)",
    accentPurple: "#a78bfa",
    accentGreen: "#34d399",
    accentAmber: "#fbbf24",
    accentRed: "#f87171",
    textBright: "#ffffff",
    textMain: "#e2e8f0",
    textDim: "#71717a",
    glassBlur: "blur(16px)",
  },
  cyber: {
    name: "Cyberpunk Neon",
    id: "cyber",
    bgBase: "#050510",
    bgSurface: "#0a0a23",
    bgElevated: "#14143c",
    bgHover: "#1f1f54",
    borderSubtle: "rgba(0, 255, 204, 0.2)",
    borderBright: "#00ffcc",
    accent: "#00ffcc",
    accentGlow: "rgba(0, 255, 204, 0.4)",
    accentPurple: "#ff007f",
    accentGreen: "#00ff66",
    accentAmber: "#ffcc00",
    accentRed: "#ff0033",
    textBright: "#ffffff",
    textMain: "#e0e7ff",
    textDim: "#818cf8",
    glassBlur: "blur(24px)",
  },
  aurora: {
    name: "Aurora Emerald Glow",
    id: "aurora",
    bgBase: "#04130e",
    bgSurface: "#09221b",
    bgElevated: "#0f3329",
    bgHover: "#154437",
    borderSubtle: "rgba(16, 185, 129, 0.15)",
    borderBright: "rgba(16, 185, 129, 0.5)",
    accent: "#10b981",
    accentGlow: "rgba(16, 185, 129, 0.3)",
    accentPurple: "#6ee7b7",
    accentGreen: "#34d399",
    accentAmber: "#fcd34d",
    accentRed: "#f87171",
    textBright: "#f0fdf4",
    textMain: "#d1fae5",
    textDim: "#6ee7b7",
    glassBlur: "blur(20px)",
  },
  matrix: {
    name: "Neon Matrix Terminal",
    id: "matrix",
    bgBase: "#020a04",
    bgSurface: "#06150a",
    bgElevated: "#0c2512",
    bgHover: "#13381c",
    borderSubtle: "rgba(0, 255, 65, 0.18)",
    borderBright: "#00ff41",
    accent: "#00ff41",
    accentGlow: "rgba(0, 255, 65, 0.35)",
    accentPurple: "#50fa7b",
    accentGreen: "#00ff41",
    accentAmber: "#f1fa8c",
    accentRed: "#ff5555",
    textBright: "#50fa7b",
    textMain: "#a8ffb2",
    textDim: "#2b8a3e",
    glassBlur: "blur(18px)",
  },
  hyperlight: {
    name: "Hyper Light Minimalist",
    id: "hyperlight",
    bgBase: "#f8fafc",
    bgSurface: "#ffffff",
    bgElevated: "#f1f5f9",
    bgHover: "#e2e8f0",
    borderSubtle: "rgba(0, 0, 0, 0.08)",
    borderBright: "#0284c7",
    accent: "#0284c7",
    accentGlow: "rgba(2, 132, 199, 0.2)",
    accentPurple: "#6366f1",
    accentGreen: "#059669",
    accentAmber: "#d97706",
    accentRed: "#dc2626",
    textBright: "#0f172a",
    textMain: "#334155",
    textDim: "#64748b",
    glassBlur: "blur(20px)",
  },
};

export const DEFAULT_THEME = THEME_PRESETS.obsidian;

/**
 * Injects CSS variables onto document.documentElement for instant reactive theme updates.
 */
export function applyThemeToDom(theme: ThemeTokens) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.style.setProperty("--bg-base", theme.bgBase);
  root.style.setProperty("--bg-surface", theme.bgSurface);
  root.style.setProperty("--bg-elevated", theme.bgElevated);
  root.style.setProperty("--bg-hover", theme.bgHover);
  root.style.setProperty("--border-subtle", theme.borderSubtle);
  root.style.setProperty("--border-bright", theme.borderBright);
  root.style.setProperty("--accent", theme.accent);
  root.style.setProperty("--accent-glow", theme.accentGlow);
  root.style.setProperty("--accent-purple", theme.accentPurple);
  root.style.setProperty("--accent-green", theme.accentGreen);
  root.style.setProperty("--accent-amber", theme.accentAmber);
  root.style.setProperty("--accent-red", theme.accentRed);
  root.style.setProperty("--text-bright", theme.textBright);
  root.style.setProperty("--text-main", theme.textMain);
  root.style.setProperty("--text-dim", theme.textDim);
  root.style.setProperty("--glass-blur", theme.glassBlur);
}
