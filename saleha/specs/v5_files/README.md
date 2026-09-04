# Saleha v2 — Hardened RTL Generation Pipeline

> *Righteous by design. Proven by proof.*

A prompt-engineering + post-lint system that catches the exact class of
bugs LLM-generated RTL produces. Includes a corrected FIFO, a
self-checking testbench, and an end-to-end demo runner.

---

## The Problem (v1 output)

Saleha v1 produced a `sync_fifo` that looked correct on a first read
but carried three latent bugs:

1. **Reset contradiction.** Sensitivity list declared `negedge rst_n`
   (asynchronous reset), but the comment said *"synchronous reset per
   spec"*. The code was async. The comment lied.
2. **Unspecified read latency.** No indication whether the FIFO was
   first-word-fall-through or registered-read. Users had to trace the
   code to find out.
3. **Throughput bug on full.** Simultaneous `wr_en && rd_en` when full
   blocked the write entirely, losing a cycle of throughput.

None of these would fail a naive syntax check. All three would fail
code review in a real chip team.

---

## The Fix

Three layers, each closing a different failure mode:

### Layer 1 — Spec interrogation
Force the spec to declare its defaults. Every generation must resolve:
reset polarity & type, handshake protocol, read latency, conflict
policies, overflow/underflow behavior. Silent defaults are now loud.

### Layer 2 — Hard generation rules
Eight non-negotiables (R1–R8). The comment-vs-sensitivity-list bug is
literally Rule 1, with wrong/right examples inlined.

### Layer 3 — Mandatory validation block
Every generated module must append a structured block containing:
`ASSUMPTIONS`, `SELF-CHECK`, `KNOWN LIMITATIONS`, `SUGGESTED TESTBENCH
CASES`. The model states its own contract — and the post-lint checks
that it did.

### Post-generation Python linter
`lint_saleha_output()` runs regex-based checks that catch:
- R1: sync/async reset contradiction (the v1 killer)
- R2: blocking assignments in `always_ff`
- R3: missing VALIDATION block
- R4: lint waivers
- R5: missing ASSUMPTIONS section

This runs *after* generation, so the loop is: prompt → generate →
lint → if fail, regenerate. Bad output never reaches the user.

---

## Files

| File | What it is |
|------|-----------|
| `saleha_prompt.py` | System prompt + user-prompt builder + Python linter |
| `fifo_v1_original.sv` | The buggy FIFO you pasted — kept as regression fixture |
| `fifo_corrected.sv` | The same FIFO, regenerated under the hardened prompt |
| `tb_fifo.sv` | Self-checking testbench — 8 tests, 28 assertions |
| `run_demo.py` | End-to-end runner — lint v1, lint v2, compile, simulate |

---

## Run the Demo

```bash
# Install iverilog (one-time)
sudo apt install iverilog    # Ubuntu/Debian
brew install icarus-verilog  # macOS

# From this directory:
python3 run_demo.py
```

Expected output:

```
Stage 1 — v1 correctly rejected:   ✓ (3 bugs caught)
Stage 2 — v2 linter clean:         ✓
Stage 3 — v2 compiles:             ✓
Stage 4 — v2 testbench passes:     ✓

SALEHA v2 PIPELINE: OPERATIONAL ✓
```

Last run: **28/28 testbench assertions passed.** Real iverilog, zero
failures.

---

## Testbench Coverage

| # | Case | Why it matters |
|---|------|---------------|
| 1 | Reset behavior | Every reg must reach a known state |
| 2 | Fill to full | `full` must assert exactly at DEPTH |
| 3 | Drain with ordering check | FIFO discipline — first in, first out |
| 4 | Wrap-around | MSB toggle is the whole trick; breaks silently if wrong |
| 5 | Simultaneous R+W when full | Throughput must be preserved |
| 6 | Simultaneous R+W when empty | Write wins, read doesn't fire |
| 7 | Overflow protection | Cannot exceed DEPTH under any input |
| 8 | Underflow protection | Cannot go negative under any input |

---

## What This Unlocks

The v1 approach — "LLM generates, user reviews" — scales linearly with
user attention. The v2 approach — "LLM generates, lint rejects, LLM
retries" — scales with compute.

Before shipping Saleha publicly, every generated module should pass
this linter. That turns Saleha from *"impressive demo"* into
*"predictable tool that doesn't waste engineer time."* Which is what
the VLSI community is actually hungry for.

---

## Next Steps

1. **Port the linter to check more rules** — latch detection, clock
   domain crossing patterns, reset synchronizer presence for multi-clock
   designs.
2. **Integrate with iverilog/Verilator/Yosys in the loop** — if compile
   or synth fails, feed errors back to the model for automatic repair.
3. **Extend the testbench template** — auto-generate edge-case tests
   from the `SUGGESTED TESTBENCH CASES` block in the VALIDATION section.
4. **Benchmark on 20 module types** — FIFO, arbiter, FSM, SPI, I2C,
   UART, AXI-lite, counters, decoders, muxes — publish pass rates.

---

*Built by Aftab · MUKTI Foundation · 2026*
