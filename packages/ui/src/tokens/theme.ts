/**
 * @saleha/ui - Semantic Design Tokens & Theme Engine
 * Style Dictionary compliant tokens supporting:
 * 1. Obsidian Dark Luxury (Default)
 * 2. Midnight OLED (#000000)
 * 3. Cyberpunk Neon
 * 4. Minimalist Clean Light
 */

export interface ThemeTokens {
  name: string;
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
    name: "Midnight OLED",
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
};

export const DEFAULT_THEME = THEME_PRESETS.obsidian;

