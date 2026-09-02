import React from "react";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Saleha Web Studio v2.6 — Autonomous Developer Platform",
  description: "Zero-leak, AST-verified autonomous multi-agent coding platform.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
