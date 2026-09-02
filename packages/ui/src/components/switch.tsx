import React from "react";
import { ThemeTokens } from "../tokens/theme";

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  theme?: ThemeTokens;
  disabled?: boolean;
}

export function Switch({
  checked,
  onChange,
  label,
  theme,
  disabled = false,
}: SwitchProps) {
  const accent = theme?.accent || "var(--accent, #38bdf8)";
  const bgElevated = theme?.bgElevated || "var(--bg-elevated, #131929)";
  const borderSubtle = theme?.borderSubtle || "var(--border-subtle, rgba(255, 255, 255, 0.08))";
  const textMain = theme?.textMain || "var(--text-main, #cbd5e1)";

  return (
    <label
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.75rem",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        userSelect: "none",
      }}
    >
      <div
        onClick={() => !disabled && onChange(!checked)}
        style={{
          width: "44px",
          height: "24px",
          background: checked ? accent : bgElevated,
          borderRadius: "999px",
          border: `1px solid ${checked ? accent : borderSubtle}`,
          position: "relative",
          transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
          boxShadow: checked ? `0 0 12px ${accent}66` : "none",
        }}
      >
        <div
          style={{
            width: "18px",
            height: "18px",
            background: "#ffffff",
            borderRadius: "50%",
            position: "absolute",
            top: "2px",
            left: checked ? "22px" : "2px",
            transition: "left 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
            boxShadow: "0 2px 4px rgba(0, 0, 0, 0.3)",
          }}
        />
      </div>
      {label && <span style={{ fontSize: "0.85rem", color: textMain, fontWeight: 500 }}>{label}</span>}
    </label>
  );
}
