# GEMINI.md

The contract for every agent in this repo, Gemini / Antigravity included, is
**`AGENTS.md`**. Read it in full before doing anything; it overrides anything
else you remember about this project.

Gemini-only notes:

- Antigravity also loads `.agents/rules/*.md`. Those must agree with
  `AGENTS.md`; if one conflicts, `AGENTS.md` wins -- fix the rule file.
- Claude works in the same worktree. Check `git status` and `COORDINATION.md`
  before editing, and never revert changes you did not make.
- Do not add shared rules here. Put them in `AGENTS.md` so every agent sees the
  same text.
