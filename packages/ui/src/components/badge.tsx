import React from "react";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "success" | "info" | "warning" | "error" | "purple";
  pulse?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = "info",
  pulse = false,
  children,
  style,
  ...props
}) => {
  const variantStyles: Record<string, { bg: string; border: string; color: string; dot: string }> = {
    success: {
      bg: "rgba(16, 185, 129, 0.1)",
      border: "rgba(16, 185, 129, 0.25)",
      color: "#10b981",
      dot: "#10b981",
    },
    info: {
      bg: "rgba(56, 189, 248, 0.1)",
      border: "rgba(56, 189, 248, 0.25)",
      color: "#38bdf8",
      dot: "#38bdf8",
    },
    warning: {
      bg: "rgba(245, 158, 11, 0.1)",
      border: "rgba(245, 158, 11, 0.25)",
      color: "#f59e0b",
      dot: "#f59e0b",
    },
    error: {
      bg: "rgba(239, 68, 68, 0.1)",
      border: "rgba(239, 68, 68, 0.25)",
      color: "#ef4444",
      dot: "#ef4444",
    },
    purple: {
      bg: "rgba(129, 140, 248, 0.1)",
      border: "rgba(129, 140, 248, 0.25)",
      color: "#818cf8",
      dot: "#818cf8",
    },
  };

  const v = variantStyles[variant];

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.35rem",
        fontSize: "0.725rem",
        fontWeight: 700,
        padding: "0.2rem 0.55rem",
        borderRadius: "999px",
        background: v.bg,
        border: `1px solid ${v.border}`,
        color: v.color,
        fontFamily: "'Plus Jakarta Sans', sans-serif",
        ...style,
      }}
      {...props}
    >
      {pulse && (
        <span
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            background: v.dot,
            boxShadow: `0 0 6px ${v.dot}`,
          }}
        />
      )}
      {children}
    </span>
  );
};

