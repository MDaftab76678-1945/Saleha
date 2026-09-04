# Saleha Roadmap

This is a list of directions Saleha could go, not a set of commitments or dates. Nothing in this document is implemented yet — see [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md) for what exists today. Items are grouped by theme rather than quarter, since none of the previous dates reflected actual planning.

---

## Near-term, plausible next steps

- **Audit CORS origin handling** in `saleha/server/web_server.py`. The server now reflects only known-local origins (localhost, `127.0.0.1`, and the Tauri webview) and never emits a wildcard on authenticated JSON responses. If additional deployment targets are added later, the allowlist in `_is_allowed_origin` needs to be revisited deliberately rather than widened to `*`.
- **Decide the fate of the "formal verification" modules.** `formal_verifier.py`/`formal_smt_verifier.py` currently emit Lean 4-/SMT-shaped template text without invoking a real toolchain. Either wire them up to an actual Lean 4 or Z3 process and validate the output, or rename/relabel them clearly as "proof-template generators" so nobody mistakes their output for a checked proof.
- **Rename or clearly scope the "consensus"/"swarm" modules.** `swarm_consensus.py` implements a real in-process multi-phase voting scheme; deciding whether to (a) actually build out cross-process/distributed behavior, or (b) keep it in-process and rename away from "PBFT"/"Byzantine," would remove a recurring source of confusion (this rewrite of the docs took the second approach for now).
- **Harden the desktop (`apps/desktop`) sidecar integration.** It's newer than the CLI/web-app path; more end-to-end testing of startup, shutdown, and error states would be valuable before calling it stable.
- **Widen test coverage of the ~220 `saleha/core/` modules** relative to what the CLI actually calls — some modules currently have thin or no direct test coverage; auditing this would clarify which modules are "supported" versus experimental scaffolding.

## Medium-term ideas (unscheduled)

- **Sandboxed in-browser execution** for the web app (e.g. Pyodide/WebContainer-style), so simple demos don't require a local backend.
- **Local hardware acceleration** for model inference (better use of NPUs/GPUs via existing local runtimes), beyond whatever Ollama already provides.
- **Multi-user collaborative editing** in the web app, if there's demand — no CRDT or collaboration engine exists in the codebase today.
- **Deeper `rust/` and `contracts/` integration.** These subsystems (zkVM/blockchain research, Solidity contracts) are currently separate from the Python agent runtime. If real integration work happens, it should be documented in ARCHITECTURE.md once it's actually wired up, not described in advance here.

## Longer-term / speculative

- **A real formal-verification pipeline** (Lean 4 or another checker actually invoked and validated), if the templated scaffolding above is worth building out.
- **A genuinely distributed multi-agent protocol**, if a use case emerges that needs agents running across separate machines/processes rather than the current in-process model.
- **Post-quantum cryptography** for any secrets/vault storage, if and when there's a concrete security requirement driving it.

---

## Ground rules for adding to this roadmap

To avoid regressing to the previous version of this document:

1. Don't claim a feature is "coming next quarter" without an owner and a plan; put it in an unscheduled bucket instead.
2. Don't describe a template, stub, or heuristic as if it were the finished feature.
3. When something here ships, move its description to README.md/ARCHITECTURE.md and remove it from here — don't leave both versions in the repo at once.
