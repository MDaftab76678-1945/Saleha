# 🧬 PRODUCT_BRIEF.md — Saleha AI Unified Ecosystem

## 1. Executive Summary & DNA
- **Product Name:** Saleha AI (Saleha Studio 2.0 / DooM Engine v2.0)
- **Tagline:** *The Autonomous Polyglot AI Software Engineering Platform*
- **One-Line Value Proposition:** Zero-leak, AST-verified, deterministic software engineering with sub-100μs local execution, mathematical multi-attractor swarm intelligence, and a unified desktop/web IDE ecosystem.

---

## 2. Market & Target Audience
- **Target Segments:** Universal developers (indie hackers, enterprise engineers, DevOps/SRE teams, software architects, students, and founders) across all skill tiers globally.
- **Top Competitors:** Cursor, Devin, Bolt.new, v0.dev, Windsurf, Lovable.
- **Core Competitive Moats:**
  1. **Deterministic Zero-Leak Safety:** Gamma AST Critic & ASan memory sandbox prevent syntax collisions and leaks.
  2. **Sub-100μs Local Latency & $0 Cost:** True local Ollama execution with pre-warmed worker process pools.
  3. **Non-Euclidean Swarm Architecture:** 250 Agents + 250 Copilots + 500 Swarm Pool on 16D Poincaré Hyperbolic Manifolds ($c=1.0$) with Čech Sheaf Cohomology consensus ($H^1=0$).
  4. **Tri-Tier Persistent Memory:** RAM Ring Buffer + NVMe Episodic Log + `.salehagraph` Knowledge Triples.

---

## 3. Product Architecture & Scope
A unified **Turborepo** monorepo containing:

| Package/App | Path | Technology Stack | Purpose |
| :--- | :--- | :--- | :--- |
| **Desktop App** | `/apps/desktop` | Tauri v2 + Rust + React 19 / TS | Offline-first native desktop IDE with system tray and local SQLite store. |
| **Web App** | `/apps/web` | Next.js 15 (App Router, RSC, Server Actions) | 3-Pane cloud studio, real-time Monaco editor, and live responsive preview. |
| **Landing Page** | `/apps/landing` | Astro 5 (Islands Architecture) | 100/100 Lighthouse performance, interactive pricing, live terminal preview. |
| **UI Kit** | `/packages/ui` | React + Tailwind CSS + Radix UI + Framer Motion | Shared accessible design system with Obsidian Dark & Multi-theme tokens. |
| **Core Logic** | `/packages/core` | TypeScript / Python bindings | Gamma AST engine, 2PC multi-file auto-repair, and swarm dispatch. |
| **Database & API** | `/packages/db` & `/packages/api` | Prisma ORM + PostgreSQL / SQLite + tRPC v11 | End-to-end type-safe API routers and schema. |

---

## 4. Monetization & Business Model
- **Tier 1 (Free Open-Core):** $0 unlimited local inference for solo developers and local sandboxing.
- **Tier 2 (Team SaaS):** Cloud synchronization, team swarm collaboration, and enterprise memory graph.
- **Tier 3 (Enterprise / One-Time License):** Air-gapped self-hosted deployment with custom SLA and security guarantees.

---

## 5. Master Recursive Validation Loop (LOOP_CHECK)
Every component produced in this ecosystem MUST pass:
1. **Feasibility:** 100% technically validated with zero syntax breakages.
2. **Scalability:** Handles 1M+ users and multi-gigabyte codebases with sub-5ms caching.
3. **Security:** Zero OWASP vulnerabilities, sandboxed MCP client, strict parameterization.
4. **Accessibility:** WCAG 2.1 AA compliant across all UI primitives.
5. **Performance:** Sub-100μs execution, 60fps animations, Lighthouse 100 on landing page.
6. **Maintainability:** DRY architecture, strict TypeScript types (no `any`), >90% test coverage.

