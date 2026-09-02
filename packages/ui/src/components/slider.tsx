import React from "react";
import { ThemeTokens } from "../tokens/theme";

export interface SliderProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
  label?: string;
  unit?: string;
  theme?: ThemeTokens;
}

export function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  label,
  unit = "",
  theme,
}: SliderProps) {
  const accent = theme?.accent || "var(--accent, #38bdf8)";
  const textBright = theme?.textBright || "var(--text-bright, #f8fafc)";
  const textDim = theme?.textDim || "var(--text-dim, #64748b)";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", width: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
        {label && <span style={{ color: textDim, fontWeight: 500 }}>{label}</span>}
        <span style={{ color: textBright, fontWeight: 700, fontFamily: "monospace" }}>
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{
          width: "100%",
          accentColor: accent,
          cursor: "pointer",
          height: "6px",
          borderRadius: "3px",
        }}
      />
    </div>
  );
}
