import React from "react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Saleha Web Studio 2.0 — Autonomous Developer Platform",
  description: "Zero-leak, AST-verified autonomous multi-agent coding platform.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" style={{ backgroundColor: "#06080d", color: "#f8fafc" }}>
      <body style={{ margin: 0, padding: 0, height: "100vh", overflow: "hidden", fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
        {children}
      </body>
    </html>
  );
}

