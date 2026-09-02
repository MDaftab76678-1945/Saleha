import React, { useEffect } from "react";
import { ThemeTokens } from "../tokens/theme";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  theme?: ThemeTokens;
  maxWidth?: string;
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  theme,
  maxWidth = "600px",
}: ModalProps) {
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
        background: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(12px)",
        WebkitBackdropFilter: "blur(12px)",
        animation: "fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "90%",
          maxWidth,
          maxHeight: "85vh",
          overflowY: "auto",
          background: bgSurface,
          border: `1px solid ${borderBright}`,
          borderRadius: "16px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 35px rgba(56, 189, 248, 0.15)",
          display: "flex",
          flexDirection: "column",
          animation: "scaleUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "1.25rem 1.5rem",
            borderBottom: `1px solid ${borderSubtle}`,
          }}
        >
          <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 700, color: textBright }}>
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
              padding: "0.25rem 0.5rem",
              borderRadius: "6px",
              transition: "all 0.15s ease",
            }}
            aria-label="Close modal"
          >
            ✕
          </button>
        </div>
        <div style={{ padding: "1.5rem" }}>{children}</div>
      </div>
    </div>
  );
}
