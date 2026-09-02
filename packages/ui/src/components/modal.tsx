import React, { useEffect } from "react";
import { ThemeTokens } from "../tokens/theme";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  theme?: ThemeTokens;
  maxWidth?: string;
  children?: React.ReactNode;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  theme,
  maxWidth = "600px",
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const bgBase = theme?.bgBase || "var(--bg-base, #06080d)";
  const bgSurface = theme?.bgSurface || "var(--bg-surface, #0c101a)";
  const borderSubtle = theme?.borderSubtle || "var(--border-subtle, rgba(255, 255, 255, 0.08))";
  const borderBright = theme?.borderBright || "var(--border-bright, rgba(56, 189, 248, 0.4))";
  const textBright = theme?.textBright || "var(--text-bright, #f8fafc)";
  const textDim = theme?.textDim || "var(--text-dim, #64748b)";

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(12px)",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth,
          backgroundColor: bgSurface,
          border: `1px solid ${borderBright}`,
          borderRadius: "16px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
          overflow: "hidden",
          fontFamily: "'Plus Jakarta Sans', sans-serif",
          animation: "modalFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "1.25rem 1.5rem",
            borderBottom: `1px solid ${borderSubtle}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <h3
            style={{
              margin: 0,
              fontSize: "1.1rem",
              fontWeight: 700,
              color: textBright,
            }}
          >
            {title}
          </h3>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: textDim,
              fontSize: "1.25rem",
              cursor: "pointer",
              padding: "0.25rem",
              lineHeight: 1,
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "1.5rem" }}>{children}</div>
      </div>
    </div>
  );
};
