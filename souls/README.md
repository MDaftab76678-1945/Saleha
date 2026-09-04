# 🌌 Saleha SoulSpec Library

The **Saleha SoulSpec Library** provides a modular, portable collection of cognitive personas and behavioral archetypes for Saleha AI and autonomous agent swarms.

Compliant with the **[SoulSpec v1.0 Standard](https://soulspec.org)**, each soul defines an agent's foundational identity, core values, cognitive boundaries, communication tone, and operational heuristics.

---

## 📚 Soul Catalog

| Soul Name | Archetype | Tone | Primary Focus |
| --- | --- | --- | --- |
| `sovereign` | Swarm Commander | Decisive, Strategic | Multi-agent PBFT consensus, local sovereignty, game theory |
| `architect` | Principal Systems Architect | Methodical, Deep | Domain-driven design, decoupled boundaries, scalability |
| `sentinel` | Paranoid Security Officer | Vigilant, Zero-Trust | STRIDE threat modeling, AST SAST gates, sandbox containment |
| `artisan` | Frontend & UX Craftsman | Vibrant, Modern | Glassmorphic design, 60fps micro-animations, WCAG 2.1 AAA |
| `speedrunner` | High-Velocity Prototyper | Punchy, Pragmatic | Working code in record time, zero fluff, MVP velocity |
| `auditor` | Formal Verification Prover | Rigorous, Deductive | Lean 4 mathematical proofs, SMT Z3 constraints, zero assumptions |
| `sage` | Senior Mentor & Educator | Empathetic, Illuminating | Socratic explanations, clean mental models, constructive guidance |
| `sre` | Chaos & Reliability Engineer | Calm, Observability-First | Zero-downtime, circuit breakers, MTTR minimization, telemetry |
| `alchemist` | Neuro-Symbolic AI Researcher | Visionary, Scientific | Hyperbolic Poincaré manifolds, causal graphs, LoRA adapters |
| `minimalist` | UNIX Philosopher | Terse, Elegant | Zero dependencies, minimal LOC, standard library mastery |

---

## 🚀 Quick Start

### 1. List Available Souls

```bash
saleha soul list
```

### 2. Switch Active Soul

```bash
saleha soul use architect
```

### 3. Inspect a Soul Persona

```bash
saleha soul show sentinel
```

### 4. Validate SoulSpec Compliance

```bash
saleha soul validate
```

---

## 📁 Soul Package Structure

Each soul package contains the following standard files:

```text
souls/<name>/
├── soul.json       # Required: Manifest, metadata, parameters, and versioning
├── SOUL.md         # Required: Core personality, prime directives, and boundaries
├── IDENTITY.md     # Optional: Origin story, ethos, visual avatar, and motto
└── STYLE.md        # Optional: Communication guidelines, vocabulary, and formatting
```
