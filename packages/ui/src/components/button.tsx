import React from "react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "glow";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  variant = "primary",
  size = "md",
  isLoading = false,
  children,
  style,
  disabled,
  ...props
}) => {
  const baseStyles: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.45rem",
    fontWeight: 700,
    fontFamily: "'Plus Jakarta Sans', sans-serif",
    borderRadius: "8px",
    cursor: disabled || isLoading ? "not-allowed" : "pointer",
    opacity: disabled || isLoading ? 0.6 : 1,
    transition: "all 0.15s cubic-bezier(0.16, 1, 0.3, 1)",
    border: "1px solid transparent",
    outline: "none",
  };

  const sizeStyles: Record<string, React.CSSProperties> = {
    sm: { padding: "0.3rem 0.65rem", fontSize: "0.75rem" },
    md: { padding: "0.45rem 1rem", fontSize: "0.825rem" },
    lg: { padding: "0.75rem 1.5rem", fontSize: "0.95rem" },
  };

  const variantStyles: Record<string, React.CSSProperties> = {
    primary: {
      background: "linear-gradient(135deg, #0284c7, #2563eb)",
      color: "#ffffff",
      borderColor: "rgba(255, 255, 255, 0.15)",
      boxShadow: "0 0 14px rgba(37, 99, 235, 0.35)",
    },
    secondary: {
      background: "#131929",
      color: "#f8fafc",
      borderColor: "rgba(255, 255, 255, 0.08)",
    },
    ghost: {
      background: "transparent",
      color: "#cbd5e1",
      borderColor: "transparent",
    },
    danger: {
      background: "rgba(239, 68, 68, 0.15)",
      color: "#ef4444",
      borderColor: "rgba(239, 68, 68, 0.3)",
    },
    glow: {
      background: "rgba(56, 189, 248, 0.12)",
      color: "#38bdf8",
      borderColor: "rgba(56, 189, 248, 0.4)",
      boxShadow: "0 0 16px rgba(56, 189, 248, 0.25)",
    },
  };

  return (
    <button
      style={{
        ...baseStyles,
        ...sizeStyles[size],
        ...variantStyles[variant],
        ...style,
      }}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? "⚡ Processing..." : children}
    </button>
  );
};

