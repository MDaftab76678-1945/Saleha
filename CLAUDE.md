# CLAUDE.md

@AGENTS.md

`AGENTS.md` (imported above) is the shared contract for every agent in this
repo. Change a shared rule there, never here -- two copies are how Claude and
Gemini ended up following different rules.

## Claude-only notes

- Past audit passes live in the `audit-history` skill, not here -- ask for it
  when you need the history of a specific file or fix.
- Path-scoped rules load from `.claude/rules/` (auditing, core modules, tests).
- This file stays short: anything that applies to other agents too belongs in
  `AGENTS.md`.
