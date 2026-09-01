import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  glass?: boolean;
}

export const Card: React.FC<CardProps> = ({
  glass = true,
  children,
  style,
  ...props
}) => {
  return (
    <div
      style={{
        background: glass ? "rgba(12, 16, 26, 0.75)" : "#0c101a",
        backdropFilter: glass ? "blur(16px)" : "none",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: "12px",
        padding: "1.25rem",
        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.35)",
        fontFamily: "'Plus Jakarta Sans', sans-serif",
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
};

