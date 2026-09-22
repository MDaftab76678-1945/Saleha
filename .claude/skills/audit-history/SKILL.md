---
name: audit-history
description: History of Saleha's audit passes and the engineering principles behind them. Use when you need to know whether a file or command was already audited, what a past pass found or fixed, why a design decision was made, or whether an open item was ever closed.
---

# Saleha audit history

Two references, loaded only when you need them:

- **`passes.md`** — summary of the audit passes: what was found, what was fixed,
  what was measured.
- **`principles.md`** — the engineering rules this project works by, each paired
  with the real defect in this repo that it would have caught.

## When to read `passes.md`

- Before auditing a file, to check whether a past pass already covered it and
  what it found.
- When a fix looks familiar — the same defect shape often recurs across modules,
  and the earlier entry names the fix that worked.
- When the user refers to past work ("pass 106 ka gap", "jaisa pehle kiya tha").

Grep it rather than reading it end to end — it is long, and entries are ordered
by pass number.

## What these files are not

Entries are **snapshots, never updated**. A pass that recorded a file as fixed
may have been superseded; a path may have moved in a later migration. Treat
every claim as "true when written" and verify against current code before acting.

`NOTEBOOK_IMPORT.md` in the repo root holds the full evidence for each pass —
probes, measurements, before/after. Go there when the summary is not enough.
