---
name: grammar-constrained-engine
description: Context-Free Grammar (CFG) validator and AST token state machine that eliminates syntax hallucinations on 3B models.
---

# Grammar-Constrained Decoding Engine

## Overview

The `grammar-constrained-engine` prevents local 3B models from producing invalid Python code. It models Python syntax as a deterministic pushdown automaton / AST state machine. Every token transition is checked against grammar constraints:
- Parentheses, bracket, and brace balance
- Indentation block transitions following `:`
- Valid identifier and operator placement

This is a post-hoc validator (`tokenize` + `ast.parse`) run against a
complete code candidate -- it does not intercept or constrain token
generation live during model decoding, despite the "grammar-constrained
decoding" name. A candidate that passes `ast.parse()` is syntactically valid
Python by definition; that is the extent of the guarantee.

## Safety & Invariants

1. **Deterministic Verification:** Relies on Python lexer and AST token states; zero heuristic guessing.
2. **Early Rejection:** Catches indentation mismatches, missing colons, or unclosed strings prior to sandbox execution.

## Usage

Validate syntax state of a code candidate:

```bash
python .agents/skills/grammar-constrained-engine/scripts/grammar_masker.py --code "def foo(x): return x + 1"
```
