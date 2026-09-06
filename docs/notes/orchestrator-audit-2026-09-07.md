# Orchestrator family audit — 2026-09-07

Audit of every orchestrator-shaped module in `saleha/core/`, prompted by the
question of whether they could reuse the new concurrency primitives
(`fast_inference.py`, `parallel_solver.py`).

They could — but that turned out to be the smaller finding. **Four of the six
had a fabricated centrepiece**: the step the module is named for did not call
a model at all, and reported a confident result regardless of input.

Every claim below was verified by running the code, not by reading it.

---

## What was actually wrong

### 1. `ttc_solver.py` — `/ttc` scored a hardcoded stub 90/100

`repl.py` calls `ttc_solver.solve(problem, num_candidates=3)` with neither
`candidate_generator_fn` nor `provided_candidates`. That hit a fallback that
emitted a fixed string:

```python
code=f"# Solution for: {problem}\ndef solve() -> str:\n    return 'solved'\n"
```

Measured before the fix, for `"write a function to merge two sorted lists"`:

```
candidate_count : 1
best score      : 90.0
passed          : True
code            : "def solve() -> str: return 'solved'"
```

`/ttc <anything>` reported a confident success without a model ever running.

**A second, worse bug sat underneath it.** The scorer rates *empty* code as
perfect, because the AST quality check finds no defects in nothing:

```
empty        quality_score=100.0
whitespace   quality_score=100.0
real code    quality_score= 96.0
```

The reranker sorts descending, so **a failed generation outranked a working
solution.** Pointing the solver at a dead port still returned `passed=True`
with score 77.0 and empty code.

Fixed: real candidates generated concurrently across three distinct
strategies; empty/whitespace candidates rejected with score 0 before scoring;
`passed` now means "proved by running tests" rather than `overall_score >= 70`.

After the fix, against a real model:

```
TTC-01 direct_idiomatic     score=92.0  chars=438
TTC-02 defensive_validated  score=92.0  chars=827
TTC-03 modular_decomposed   score=90.0  chars=974
```

Unreachable model now yields score 0.0, `passed=False`.

### 2. `debate_consensus_orchestrator.py` — no model, ever

`__init__` was `pass`. The whole "5-agent council" was f-string templates.
Every topic produced byte-identical reasoning and the same score:

```
topic=Postgres vs DynamoDB for the ledger   conf=0.948  Adopted Option A (Postgres)
topic=Should we rewrite the CLI in Rust     conf=0.948  Adopted Option A (Should)
```

The chosen "option" was the **first word of the topic**. Status was always
`ACCEPTED`, confidence always `94.8%`. `saleha debate` presented this as a
security and FinOps review.

Fixed: every persona is a real model call. The three critics within a round
are independent, so they run concurrently; the advocate runs first (critics
respond to it) and the arbiter last (it reads the transcript) — a real data
dependency, not a performance choice. Confidence is now measured
participation. Verified against a real model: topic-specific critiques,
`identical security critique for both topics: False`.

### 3. `recursive_solver.py` — `path_b` won every problem, forever

Node 3 returned three hardcoded `ReasoningPath` objects with literal scores
(8.5 / 9.0 / 8.0). Node 5 picks `max(score)`. So the "multi-path exploration"
never read the goal:

```
reverse a linked list          -> winner=path_b
parse an ISO-8601 timestamp    -> winner=path_b
compute SHA-256 in chunks      -> winner=path_b
all three goals identical paths: True
```

Fixed: three framings analysed concurrently via constrained JSON decoding,
each scoring its own suitability *for this problem*. Measured after:

```
reverse a singly linked list   [a=9.0 b=7.0 c=7.0] winner=path_a
count ways to climb n stairs   [a=8.0 b=8.0 c=8.0] winner=path_a  (tied)
stream a 50GB log file         [a=8.0 b=5.0 c=8.0] winner=path_a
```

Note the middle row: a 3-way tie means the model did not discriminate. Rather
than let an arbitrary pick look like a judgement, `last_evaluation_was_tied`
records it.

### 4. `tot_orchestrator.py` — "repairs" that changed nothing

`_generate_branch_code` accepted `error_msg` and **never read it** (one
occurrence in the file: its own parameter). The three "repair strategies"
were:

```python
branch 0: return f"# Guard Invariant Applied\nif not True:\n    pass\n{base_code}"
branch 1: return base_code + "\n\n# Boundary refinement\n"
branch 2: return base_code.strip()
```

None change behaviour, so a failing test still failed and the tree search only
ever explored cosmetic variants of the same broken code.

Fixed: each branch asks the model for a real repair, given the actual test
failure and a distinct repair angle. Verified end-to-end — `def add(a,b):
return a - b` with `assert add(2,3)==5` is now genuinely repaired to `a + b`
in ~1s, confirmed by real test execution.

### 5. `deliberation_engine.py` — a failed security review read as an all-clear

```python
sec_critique = sec_resp.content if sec_resp.success \
    else "No critical security blockers identified."
```

A model that failed to respond produced a written all-clear that nobody
issued. Now returns an explicit `[review unavailable: ... NOT an all-clear]`.
The two critics also now run concurrently — they review the same design and
never read each other.

### 6. `team_orchestrator.py` — sequential critics (only real finding)

Handled failure correctly. Its two independent critics ran in sequence; they
now share one batch.

---

## Honest limits

- **Concurrency is sublinear.** One GPU, one Ollama instance: 5 parallel calls
  take 15.5s vs ~34s sequential (2.2x), not 5x. `max_concurrency=4` comes from
  that measurement.
- **`should_parallelise()` is a heuristic**, not a cost model.
- **These fixes make the modules honest, not smart.** A real critique from a 3B
  model is still a 3B model's critique. The gain is that a *failure* now looks
  like a failure instead of a 94.8%-confidence ACCEPTED.
- **`recursive_solver` ties are common** at 3B — the model often scores all
  three approaches equally. That is now visible rather than hidden.

## Tests

37 new tests across `test_debate_consensus_orchestrator.py` (13),
`test_orchestrator_honesty.py` (15), plus regressions appended to
`test_ttc_solver.py` and `test_recursive_solver.py`. All inject a fake
inference engine — no test contacts a real model.

Two existing tests asserted the old broken behaviour and were corrected:

- `test_ttc_solver.py` asserted `result.passed is True` for candidates that
  were never executed.
- `test_specialized_orchestrators.py` asserted `elo_confidence_score >= 0.9`,
  which only held because the value was the hardcoded `0.948`.
